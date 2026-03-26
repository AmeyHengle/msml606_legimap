"""
src/api/app.py
--------------
Flask backend for LegiMap.

Routes
------
  GET  /                          Serve the frontend (index.html)
  GET  /api/search?q=<query>      Search by case name or citation string
  GET  /api/expand?id=<case_id>&depth=<d>&k=<k>
                                  Run Seed-and-Expand from a given case
  GET  /api/case?id=<case_id>     Fetch full metadata for one case
  GET  /api/stats                 Return index statistics for the UI footer

The index (hash table + N-ary tree) is built once at startup and reused
across all requests.  For the toy dataset this takes < 1 second.

Run:
    # From the project root:
    PYTHONPATH=. python src/api/app.py

    # Then open:  http://localhost:5000
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from flask import Flask, jsonify, render_template, request

from src.preprocessing.build_index import build_index
from src.algorithms.seed_expand    import SeedExpand
from src.preprocessing.normalise   import normalise_citation

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Index is built once at startup and stored as module-level globals.
# In a production system these would be passed via an application factory,
# but for a single-process demo server this is the simplest approach.
_table    = None
_tree     = None
_se       = None
_stats    = {}


def _build_startup_index(data_path: str = "data/toy_cases.jsonl") -> None:
    """
    Build the hash table and N-ary tree from the toy dataset.
    Called once when the Flask app starts.
    """
    global _table, _tree, _se, _stats

    print(f"\n[LegiMap] Building index from: {data_path}")
    t0 = time.perf_counter()

    _table, _tree = build_index(data_path)
    _se           = SeedExpand(_tree, in_degree_weight=0.2)

    elapsed = time.perf_counter() - t0

    _stats = {
        "cases"       : _table.size(),
        "edges"       : _tree.edge_count(),
        "load_factor" : round(_table.load_factor(), 4),
        "build_time_s": round(elapsed, 3),
        "data_file"   : os.path.basename(data_path),
        **_table.collision_stats(),
    }

    print(f"[LegiMap] Index ready — {_stats['cases']} cases, "
          f"{_stats['edges']} edges ({elapsed:.2f}s)\n")


# ---------------------------------------------------------------------------
# Helper: serialise a case record for the API response
# ---------------------------------------------------------------------------

def _serialise_case(record: dict) -> dict:
    """
    Extract the fields the frontend needs from a full CAP record.
    Keeps API responses small and avoids sending raw sha256 hashes, etc.
    """
    if record is None:
        return {}

    cites_to_preview = []
    for edge in record.get("cites_to", [])[:10]:   # cap at 10 for the sidebar
        cites_to_preview.append({
            "cite" : edge.get("cite", ""),
            "key"  : edge.get("canonical_key"),
        })

    return {
        "id"          : record.get("id"),
        "name"        : record.get("name"),
        "abbreviation": record.get("name_abbreviation"),
        "cite"        : record.get("citations", [{}])[0].get("cite", ""),
        "year"        : str(record.get("decision_date", ""))[:4],
        "date"        : record.get("decision_date", ""),
        "court"       : record.get("court", {}).get("name", ""),
        "docket"      : record.get("docket_number", ""),
        "in_degree"   : _tree.in_degree(record.get("id")) if _tree else 0,
        "out_degree"  : _tree.out_degree(record.get("id")) if _tree else 0,
        "word_count"  : record.get("analysis", {}).get("word_count", 0),
        "ocr_confidence": record.get("analysis", {}).get("ocr_confidence"),
        "pagerank_pct": record.get("analysis", {}).get("pagerank", {}).get("percentile"),
        "cites_to"    : cites_to_preview,
        "canonical_key": record.get("canonical_key"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page frontend."""
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """
    Search for cases by name or citation string.

    Query params:
        q : str   The search query (e.g. "Roe v. Wade" or "410 U.S. 113")

    Returns a list of matching cases, sorted by relevance (in-degree).
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": [], "error": "Empty query"})

    results = []

    # Strategy 1: try to normalise as a citation key and look up directly
    canonical = normalise_citation(query)
    if canonical:
        record = _table.get(canonical)
        if record:
            results.append(_serialise_case(record))

    # Strategy 2: case-insensitive substring match on name and abbreviation
    query_lower = query.lower()
    for key, record in _table.items():
        if record.get("id") in {r["id"] for r in results}:
            continue   # already found via citation lookup

        name  = record.get("name", "").lower()
        abbr  = record.get("name_abbreviation", "").lower()
        cite  = record.get("citations", [{}])[0].get("cite", "").lower()

        if query_lower in name or query_lower in abbr or query_lower in cite:
            results.append(_serialise_case(record))

    # Sort by in-degree (most-cited cases first) so the most important
    # cases appear at the top of the dropdown
    results.sort(key=lambda r: r.get("in_degree", 0), reverse=True)

    return jsonify({"results": results[:10], "query": query})


@app.route("/api/expand")
def api_expand():
    """
    Run Seed-and-Expand from a given case and return the citation subgraph.

    Query params:
        id    : int   The case_id to use as the seed
        depth : int   BFS depth limit (default 3, max 4)
        k     : int   Number of top results to return (default 10, max 20)

    Returns a vis.js-compatible node/edge graph plus ranked results list.
    """
    try:
        case_id = int(request.args.get("id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid or missing case id"}), 400

    depth = min(int(request.args.get("depth", 3)), 4)
    k     = min(int(request.args.get("k",     10)), 20)

    if not _tree.has_node(case_id):
        return jsonify({"error": f"Case id {case_id} not found in index"}), 404

    # Run the algorithm
    t0      = time.perf_counter()
    results = _se.search(case_id, max_depth=depth, top_k=k)
    elapsed = time.perf_counter() - t0

    # Build the subgraph for the visualisation
    subgraph = _se.get_subgraph_for_results(case_id, results)

    # Attach rank and score to each node for the frontend to use
    score_map = {r.case_id: {"rank": i + 1, "score": round(r.score, 4),
                              "shared_refs": len(r.shared_refs), "depth": r.depth}
                 for i, r in enumerate(results)}

    for node in subgraph["nodes"]:
        nid = node["id"]
        node.update(score_map.get(nid, {"rank": None, "score": None,
                                        "shared_refs": 0, "depth": 0}))

    # Ranked results list for the sidebar
    ranked = [
        {
            "rank"       : i + 1,
            "case_id"    : r.case_id,
            "name"       : r.name,
            "cite"       : r.cite,
            "year"       : r.year,
            "score"      : round(r.score, 4),
            "bib_coupling"   : round(r.bib_coupling, 4),
            "in_degree_bonus": round(r.in_degree_bonus, 4),
            "shared_refs": len(r.shared_refs),
            "depth"      : r.depth,
        }
        for i, r in enumerate(results)
    ]

    seed_record = _table.get(_tree.get_metadata(case_id).get("canonical_key", ""))
    seed_meta   = _serialise_case(_tree.get_metadata(case_id))

    return jsonify({
        "seed"        : seed_meta,
        "graph"       : subgraph,
        "ranked"      : ranked,
        "params"      : {"depth": depth, "k": k},
        "search_time_ms": round(elapsed * 1000, 2),
    })


@app.route("/api/case")
def api_case():
    """
    Return full metadata for a single case.

    Query params:
        id : int   The case_id to look up
    """
    try:
        case_id = int(request.args.get("id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid or missing case id"}), 400

    meta = _tree.get_metadata(case_id)
    if meta is None:
        return jsonify({"error": f"Case {case_id} not found"}), 404

    return jsonify(_serialise_case(meta))


@app.route("/api/stats")
def api_stats():
    """Return index statistics for the UI footer."""
    return jsonify(_stats)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Resolve the data path relative to the project root, not this file's dir
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    data_path    = os.path.join(project_root, "data", "toy_cases.jsonl")
    data_path    = os.path.normpath(data_path)

    _build_startup_index(data_path)

    print("=" * 50)
    print("  LegiMap is running at http://localhost:5000")
    print("  Press Ctrl+C to stop.")
    print("=" * 50 + "\n")

    app.run(debug=True, port=5000, use_reloader=False)
