"""
eval_hash.py — verifies the hash table meets the proposal's O(1) metric.

Three tests:
  1. Live stats on the toy dataset (load factor, collision rate, lookups)
  2. Stress test: insert 10,000 synthetic keys, verify all are retrievable
  3. Timing benchmark: measure avg lookup time at 100, 1k, and 10k entries
     to confirm it stays roughly constant (O(1) behaviour)

Run: PYTHONPATH=. python src/evaluation/eval_hash.py
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.preprocessing.build_index import build_index
from src.algorithms.hash_table     import HashTable


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _print_stats(stats: dict) -> None:
    print(f"  Table size        : {stats['size']:>8,}")
    print(f"  Capacity          : {stats['capacity']:>8,}")
    print(f"  Load factor       : {stats['load_factor']:>8.4f}")
    print(f"  Total inserts     : {stats['total_inserts']:>8,}")
    print(f"  Total collisions  : {stats['total_collisions']:>8,}")
    print(f"  Collision rate    : {stats['collision_rate']:>8.4f}")
    print(f"  Avg probe length  : {stats['avg_probe_length']:>8.4f}")
    print(f"  Max probe length  : {stats['max_probe_length']:>8}")


def _synthetic_key() -> str:
    return f"{random.randint(1, 600)}US{random.randint(1, 999)}"


def test_live_dataset(data_path: str = "data/toy_cases.jsonl") -> None:
    _print_section("TEST 1 — Live dataset stats (toy_cases.jsonl)")

    table, _ = build_index(data_path)
    stats    = table.collision_stats()
    print()
    _print_stats(stats)

    known_keys = [
        ("410US113", "Roe v. Wade"),
        ("381US479", "Griswold v. Connecticut"),
        ("384US436", "Miranda v. Arizona"),
        ("505US833", "Planned Parenthood v. Casey"),
    ]

    print("\n  Spot-check lookups:")
    for key, expected_name in known_keys:
        result = table.get(key)
        if result:
            found = result.get("name", "?")
            mark  = "✅" if found == expected_name else "⚠️"
            print(f"    {mark}  {key}  ->  {found}")
        else:
            print(f"    ❌  {key}  ->  NOT FOUND")

    lf        = stats["load_factor"]
    avg_probe = stats["avg_probe_length"]
    print(f"\n  Assessment:")
    print(f"    Load factor {lf:.3f} {'✅ within [0.1, 0.7]' if lf <= 0.7 else '⚠️ ABOVE threshold'}")
    print(f"    Avg probe   {avg_probe:.3f} {'✅ ≈ O(1)' if avg_probe < 2.0 else '⚠️ elevated'}")


def test_stress_10k() -> None:
    _print_section("TEST 2 — Stress test: 10,000 synthetic citation keys")

    random.seed(42)
    ht   = HashTable(capacity=64)
    keys = []
    seen = set()

    while len(keys) < 10_000:
        k = _synthetic_key()
        if k not in seen:
            seen.add(k)
            keys.append(k)

    for k in keys:
        ht.insert(k, {"key": k})

    print()
    _print_stats(ht.collision_stats())

    failures = sum(1 for k in keys if ht.get(k) is None)
    print(f"\n  Correctness: {len(keys) - failures}/{len(keys)} keys retrievable")
    print(f"  {'✅ All 10,000 keys found correctly' if failures == 0 else f'❌ {failures} keys MISSING'}")

    print("\n  Load factor progression:")
    ht2 = HashTable(capacity=64)
    checkpoints  = [100, 500, 1000, 2500, 5000, 10000]
    checkpoint_i = 0
    for i, k in enumerate(keys, 1):
        ht2.insert(k, {})
        if checkpoint_i < len(checkpoints) and i == checkpoints[checkpoint_i]:
            s = ht2.collision_stats()
            print(f"    After {i:>6,} inserts:  load={s['load_factor']:.4f}  "
                  f"capacity={ht2.capacity():>6,}  avg_probe={s['avg_probe_length']:.3f}")
            checkpoint_i += 1


def test_lookup_timing() -> None:
    _print_section("TEST 3 — Lookup timing benchmark")

    random.seed(0)
    sizes        = [100, 1_000, 10_000]
    LOOKUPS      = 5_000

    print(f"\n  {'Table size':>12}  {'Avg lookup (µs)':>18}  {'Assessment':>12}")
    print(f"  {'-'*12}  {'-'*18}  {'-'*12}")

    prev_time = None
    for n in sizes:
        ht   = HashTable(capacity=64)
        keys = [f"{i+1}US{(i*7+13) % 999 + 1}" for i in range(n)]
        for k in keys:
            ht.insert(k, {"id": k})

        lookup_keys = [keys[i % n] for i in range(LOOKUPS)]
        t0 = time.perf_counter()
        for k in lookup_keys:
            _ = ht.get(k)
        avg_us = (time.perf_counter() - t0) / LOOKUPS * 1_000_000

        if prev_time is None:
            assessment = "baseline"
        else:
            ratio      = avg_us / prev_time
            assessment = f"✅ {ratio:.2f}x" if ratio < 4.0 else f"⚠️ {ratio:.2f}x"

        print(f"  {n:>12,}  {avg_us:>17.3f}µs  {assessment:>12}")
        prev_time = avg_us


if __name__ == "__main__":
    print("LegiMap — Hash Table Evaluation")
    print("Target: load factor ≤ 0.7, avg probe ≈ 1.0, O(1) timing\n")

    test_live_dataset()
    test_stress_10k()
    test_lookup_timing()

    print("\n" + "=" * 60)
    print("  Evaluation complete.")
    print("=" * 60)
