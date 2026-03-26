"""
ingest.py — streaming reader for CAP-format JSONL and JSON array files.

I wrote this as a generator so the pipeline can handle arbitrarily large
files without loading everything into memory at once. 

Supports two formats:
  - JSONL (one JSON object per line) — preferred for large datasets
  - JSON array — used by the sample snapshot
The format is auto-detected from the first character of the file.
"""

from __future__ import annotations

import json
import os
from typing import Iterator


def stream_records(path: str) -> Iterator[dict]:
    """
    Yield one raw record at a time. No cleaning happens here — callers
    should pass each record through normalise.clean_record() themselves.

    Skips blank lines and malformed JSONL lines with a warning instead
    of crashing, since real-world datasets always have a few bad lines.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        # Peek at the first non-whitespace character to decide the format
        first_char = ""
        while not first_char.strip():
            ch = f.read(1)
            if not ch:
                return
            first_char = ch
        f.seek(0)

        if first_char == "[":
            try:
                records = json.load(f)
                if not isinstance(records, list):
                    raise ValueError("Expected a JSON array at the top level.")
                for record in records:
                    yield record
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON array in {path}: {e}") from e
        else:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  [ingest] WARNING: skipping malformed line {line_number}: {e}")
                    continue


def load_all_records(path: str) -> list[dict]:
    """Load everything into a list. Only use this for small datasets."""
    return list(stream_records(path))


def count_records(path: str) -> int:
    """Count records without storing them — useful as a quick sanity check."""
    return sum(1 for _ in stream_records(path))


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/legimap_1M.jsonl"

    print(f"Streaming records from: {path}")
    print("-" * 40)

    count = 0
    edges = 0
    for record in stream_records(path):
        count += 1
        edges += len(record.get("cites_to", []))

    print(f"  Records loaded : {count}")
    print(f"  Total edges    : {edges}")
    print(f"  Avg out-degree : {edges / max(count, 1):.2f}")
    print("\nStream test passed ✅")
