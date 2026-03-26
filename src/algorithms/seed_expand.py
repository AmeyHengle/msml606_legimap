"""
seed_expand.py — the main discovery algorithm for LegiMap.

Given a seed case, I want to find other cases that are legally related.
My approach: bibliographic coupling — two cases are likely related if they
cite many of the same authorities. This is how legal researchers actually
think about precedent.

The algorithm runs in four steps:
  1. BFS on the N-ary tree to collect a candidate pool (cases within K hops)
  2. For each candidate, count shared references with the seed
  3. Add a small in-degree bonus so highly-cited seminal cases float up
  4. Sort by combined score, return top-K

The result feeds directly into the Flask API and vis.js visualisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.algorithms.nary_tree import NaryTree


@dataclass(order=True)
class SearchResult:
    """
    One ranked result from search().
    score is the first field so Python's default sort works descending by score.
    """
    score          : float  = field(compare=True)
    case_id        : object = field(compare=False)
    name           : str    = field(compare=False, default="")
    cite           : str    = field(compare=False, default="")
    year           : str    = field(compare=False, default="")
    depth          : int    = field(compare=False, default=0)
    shared_refs    : list   = field(compare=False, default_factory=list)
    bib_coupling   : float  = field(compare=False, default=0.0)
    in_degree_bonus: float  = field(compare=False, default=0.0)


class SeedExpand:
    """
    Seed-and-Expand search over the citation tree.

    in_degree_weight controls how much to boost highly-cited cases
    relative to raw bibliographic coupling. Default is 0.2 (20% bonus).
    """

    def __init__(self, tree: NaryTree, in_degree_weight: float = 0.2):
        self._tree             = tree
        self._in_degree_weight = in_degree_weight

    def search(
        self,
        seed_id,
        max_depth: int = 3,
        top_k: int = 10,
        direction: str = "both",
    ) -> list[SearchResult]:
        """
        Find the top-K cases most related to seed_id.

        I use "both" direction by default so I catch cases that cite the seed
        AND cases the seed cites — both are legally relevant neighbours.
        """
        if not self._tree.has_node(seed_id):
            return []

        bfs_result = self._tree.bfs(seed_id, max_depth=max_depth, direction=direction)
        depth_map  = {nid: depth for nid, depth in bfs_result}
        candidates = [nid for nid, _ in bfs_result if nid != seed_id]

        if not candidates:
            return []

        seed_refs    = self._get_reference_set(seed_id)
        max_in_degree = max(
            (self._tree.in_degree(nid) for nid in self._tree.all_node_ids()), default=1
        )

        results = []
        for candidate_id in candidates:
            shared        = seed_refs & self._get_reference_set(candidate_id)
            bib_score     = float(len(shared))
            in_deg_bonus  = (self._tree.in_degree(candidate_id) / max(max_in_degree, 1)) * self._in_degree_weight
            combined      = bib_score + in_deg_bonus

            meta = self._tree.get_metadata(candidate_id) or {}
            results.append(SearchResult(
                score           = combined,
                case_id         = candidate_id,
                name            = meta.get("name_abbreviation", meta.get("name", str(candidate_id))),
                cite            = meta.get("citations", [{}])[0].get("cite", ""),
                year            = str(meta.get("decision_date", ""))[:4],
                depth           = depth_map.get(candidate_id, -1),
                shared_refs     = sorted(shared),
                bib_coupling    = bib_score,
                in_degree_bonus = in_deg_bonus,
            ))

        results.sort(reverse=True)
        return results[:top_k]

    def get_subgraph_for_results(self, seed_id, results: list[SearchResult]) -> dict:
        """
        Build a vis.js-compatible node/edge dict covering the seed and all results.
        Used by the Flask API to send graph data to the frontend.
        """
        node_ids = {seed_id} | {r.case_id for r in results}
        score_map = {r.case_id: r.score for r in results}

        nodes = []
        for nid in node_ids:
            meta = self._tree.get_metadata(nid) or {}
            nodes.append({
                "id"       : nid,
                "label"    : meta.get("name_abbreviation", str(nid)),
                "full_name": meta.get("name", str(nid)),
                "cite"     : meta.get("citations", [{}])[0].get("cite", ""),
                "year"     : str(meta.get("decision_date", ""))[:4],
                "in_degree": self._tree.in_degree(nid),
                "is_seed"  : (nid == seed_id),
                "score"    : score_map.get(nid),
            })

        edges = []
        for nid in node_ids:
            node = self._tree.get_node(nid)
            if node is None:
                continue
            for edge in node.children:
                if edge.target_id in node_ids:
                    edges.append({"from": nid, "to": edge.target_id, "weight": edge.weight})

        return {"nodes": nodes, "edges": edges}

    def _get_reference_set(self, case_id) -> set:
        """
        Return the set of canonical citation keys that this case cites.
        I rely on the canonical_key field that build_index.py attaches to
        each cites_to edge during preprocessing.
        """
        meta = self._tree.get_metadata(case_id)
        if not meta:
            return set()
        return {
            edge["canonical_key"]
            for edge in meta.get("cites_to", [])
            if edge.get("canonical_key")
        }


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    from src.preprocessing.build_index import build_index

    path = "data/toy_cases.jsonl"
    print(f"Building index from: {path}\n")
    table, tree = build_index(path)

    se      = SeedExpand(tree, in_degree_weight=0.2)
    seed_id = 1003  # Roe v. Wade

    print(f"\nSeed: {tree.get_metadata(seed_id)['name']}")
    print("=" * 50)

    for i, r in enumerate(se.search(seed_id, max_depth=3, top_k=10), 1):
        print(f"  #{i:>2}  score={r.score:.3f}  [{r.year}]  {r.name}")
        print(f"        cite={r.cite}  depth={r.depth}  shared_refs={len(r.shared_refs)}")
