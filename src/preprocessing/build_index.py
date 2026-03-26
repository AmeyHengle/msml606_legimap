"""
build_index.py — orchestrates the full preprocessing pipeline.

This is the entry point that connects everything:
  ingest -> normalise -> hash table -> N-ary tree

I do it in two passes to handle forward references cleanly:
  Pass 1: clean each record, insert into the hash table, register as a tree node.
  Pass 2: once all nodes exist, wire up the citation edges.

This way I never try to add an edge to a node that hasn't been registered yet,
which would silently drop edges if the cited case appears later in the file.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.preprocessing.ingest    import stream_records
from src.preprocessing.normalise import clean_record
from src.algorithms.hash_table   import HashTable
from src.algorithms.nary_tree    import NaryTree


def build_index(
    data_path: str,
    table_capacity: int = 256,
) -> tuple["HashTable", "NaryTree"]:
    """
    Build and return a populated hash table and N-ary tree from a data file.

    The table maps canonical citation keys to full case metadata dicts.
    The tree stores the citation network with weighted directed edges.
    """
    table = HashTable(capacity=table_capacity)
    tree  = NaryTree()

    # --- Pass 1: clean, hash table insert, register tree nodes ---
    print(f"[build_index] Pass 1 – ingesting records from: {data_path}")

    records_seen   = 0
    records_stored = 0
    skipped_no_key = 0
    cleaned_records: list[dict] = []

    for raw_record in stream_records(data_path):
        records_seen += 1
        record = clean_record(raw_record)

        canonical_key = record.get("canonical_key")
        case_id       = record.get("id")

        if canonical_key is None:
            skipped_no_key += 1
            continue

        table.insert(canonical_key, record)
        tree.add_node(case_id, metadata=record)
        cleaned_records.append(record)
        records_stored += 1

    print(f"  Records seen      : {records_seen}")
    print(f"  Records stored    : {records_stored}")
    print(f"  Skipped (no key)  : {skipped_no_key}")
    print(f"  Hash table load   : {table.load_factor():.3f}")
    print(f"  Tree nodes        : {tree.node_count()}")

    # --- Pass 2: wire citation edges ---
    print("\n[build_index] Pass 2 – wiring citation edges")

    edges_added   = 0
    edges_skipped = 0

    for record in cleaned_records:
        parent_id = record.get("id")

        for edge in record.get("cites_to", []):
            target_ids = edge.get("case_ids", [])

            # If case_ids is missing, try to resolve via canonical key
            if not target_ids:
                edge_key = edge.get("canonical_key")
                if edge_key:
                    cited_record = table.get(edge_key)
                    if cited_record:
                        target_ids = [cited_record["id"]]

            weight = edge.get("weight", 1)

            for target_id in target_ids:
                if tree.has_node(target_id):
                    tree.add_edge(parent_id=parent_id, child_id=target_id, weight=weight)
                    edges_added += 1
                else:
                    edges_skipped += 1

    print(f"  Edges added   : {edges_added}")
    print(f"  Edges skipped : {edges_skipped}  (cited cases outside dataset)")
    print(f"\n[build_index] Index build complete ✅")

    return table, tree


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/legimap_1M.jsonl"

    table, tree = build_index(path)

    print("\n── Hash table sample lookups ───────────────────────────────")
    for key in ["410US113", "381US479", "384US436", "999US000"]:
        result = table.get(key)
        print(f"  {key}  ->  {result['name'] if result else 'NOT FOUND'}")

    print("\n── Tree BFS from Roe v. Wade (id=1003, depth=2) ────────────")
    for node_id, depth in tree.bfs(root_id=1003, max_depth=2):
        meta = tree.get_metadata(node_id)
        print(f"  depth={depth}  id={node_id}  {meta.get('name', '?') if meta else '?'}")
