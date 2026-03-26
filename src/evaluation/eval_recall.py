"""
eval_recall.py — evaluates the Seed-and-Expand algorithm against recall@K.

My target from the proposal: recall@K >= 85%, meaning that for a given seed,
at least 85% of the known-related cases appear in the top-K results.

I define four ground-truth lineages manually — sets of cases that legal
scholars agree are directly related through shared doctrine. The algorithm
should surface them without being told they're related.

Run: PYTHONPATH=. python src/evaluation/eval_recall.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.preprocessing.build_index import build_index
from src.algorithms.seed_expand    import SeedExpand


# Ground truth: four lineages with their seed and expected related cases.
# I exclude the seed itself from relevant_ids.
GROUND_TRUTH = [
    {
        "seed_id"     : 1003,
        "seed_name"   : "Roe v. Wade",
        "lineage"     : "Privacy / Reproductive Rights",
        "relevant_ids": {
            1001,   # Griswold — foundational precedent
            1002,   # Eisenstadt — cited heavily by Roe
            1005,   # Casey — reaffirms Roe
            1006,   # Lawrence — extends privacy doctrine
            1007,   # Obergefell — lineage endpoint
            1008,   # Dobbs — overturns Roe
            1009,   # Carey — cites Roe and Griswold
            1010,   # Webster — tests Roe
        },
    },
    {
        "seed_id"     : 2002,
        "seed_name"   : "Brandenburg v. Ohio",
        "lineage"     : "First Amendment / Free Speech",
        "relevant_ids": {
            2001,   # Schenck — earlier speech standard
            2004,   # Cohen — cites Brandenburg
            2005,   # Texas v. Johnson — cites Brandenburg heavily
            2006,   # R.A.V. — cites Brandenburg
            2007,   # Snyder — extends Brandenburg
            2010,   # Chaplinsky — cites Schenck
        },
    },
    {
        "seed_id"     : 3002,
        "seed_name"   : "Brown v. Board of Education",
        "lineage"     : "Equal Protection",
        "relevant_ids": {
            3001,   # Plessy — overturned by Brown
            3003,   # Bolling — companion case
            3004,   # Loving — extends Brown
            3005,   # Reed — follows Brown
            3006,   # Frontiero — gender equality, follows Brown
            3007,   # Craig — gender equality
            3010,   # Bakke — cites Brown
        },
    },
    {
        "seed_id"     : 4006,
        "seed_name"   : "Katz v. United States",
        "lineage"     : "Criminal Procedure / 4th Amendment",
        "relevant_ids": {
            4005,   # Terry — cross-cites Katz
            4007,   # Kyllo — cites Katz heavily
            4008,   # Riley — cites Katz
            4009,   # Jones — cites Katz
            4010,   # Carpenter — cites the Katz chain
            4002,   # Mapp — exclusionary rule, related
        },
    },
]


def recall_at_k(results, relevant_ids: set, k: int) -> float:
    """Fraction of relevant_ids that appear in the top-K results."""
    if not relevant_ids:
        return 0.0
    hits = {r.case_id for r in results[:k]} & relevant_ids
    return len(hits) / len(relevant_ids)


def precision_at_k(results, relevant_ids: set, k: int) -> float:
    """Fraction of top-K results that are actually relevant."""
    if k == 0:
        return 0.0
    hits = {r.case_id for r in results[:k]} & relevant_ids
    return len(hits) / k


def run_evaluation(
    data_path: str = "data/legimap_1M.jsonl",
    k_values: list = None,
    max_depth: int = 3,
    in_degree_weight: float = 0.2,
) -> None:
    if k_values is None:
        k_values = [5, 8, 10, 15]

    print("LegiMap — Seed-and-Expand Recall Evaluation")
    print(f"Data: {data_path}  |  BFS depth: {max_depth}  |  in_degree_weight: {in_degree_weight}")
    print("=" * 70)

    table, tree = build_index(data_path)
    se = SeedExpand(tree, in_degree_weight=in_degree_weight)

    summary = []

    for gt in GROUND_TRUTH:
        seed_id      = gt["seed_id"]
        relevant_ids = gt["relevant_ids"]

        print(f"\nLineage : {gt['lineage']}")
        print(f"Seed    : [{seed_id}] {gt['seed_name']}")
        print(f"Relevant: {len(relevant_ids)} cases")
        print("-" * 70)

        results = se.search(seed_id, max_depth=max_depth, top_k=max(k_values))

        print(f"  Top-{len(results)} results:")
        for i, r in enumerate(results, 1):
            mark = "✅" if r.case_id in relevant_ids else "  "
            print(f"    #{i:>2} {mark}  score={r.score:.3f}  [{r.year}]  {r.name}")

        print(f"\n  {'K':>4}  {'Recall@K':>10}  {'Precision@K':>13}  {'Assessment':>12}")
        print(f"  {'-'*4}  {'-'*10}  {'-'*13}  {'-'*12}")
        for k in k_values:
            rec  = recall_at_k(results, relevant_ids, k)
            prec = precision_at_k(results, relevant_ids, k)
            mark = "✅ PASS" if rec >= 0.85 else ("⚠️ close" if rec >= 0.70 else "❌ FAIL")
            print(f"  {k:>4}  {rec:>9.1%}  {prec:>12.1%}  {mark}")

        summary.append((gt["lineage"], recall_at_k(results, relevant_ids, k=10)))

    print("\n" + "=" * 70)
    print("  SUMMARY — Recall@10  (target ≥ 85%)")
    print("-" * 70)

    passed = 0
    for lineage, rec in summary:
        status = "✅ PASS" if rec >= 0.85 else "❌ FAIL"
        if rec >= 0.85:
            passed += 1
        print(f"  {status}  {rec:.1%}  {lineage}")

    overall = sum(r for _, r in summary) / len(summary)
    print(f"\n  Overall avg recall@10 : {overall:.1%}")
    print(f"  Lineages passing ≥85% : {passed}/{len(summary)}")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()
