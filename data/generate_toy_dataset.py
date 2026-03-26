"""
generate_toy_dataset.py
-----------------------
Generates a toy CAP-schema dataset of ~100 landmark U.S. Supreme Court cases
with a realistic citation network.  Intentionally injects noise (OCR errors,
variant citation strings, missing fields) so the preprocessing pipeline has
real work to do.

The cases are drawn from four landmark legal lineages that make the
Seed-and-Expand algorithm visually compelling for a demo:

  Lineage A – Privacy / Reproductive Rights
    Griswold → Eisenstadt → Roe → Planned Parenthood → Lawrence → Dobbs

  Lineage B – First Amendment / Free Speech
    Schenck → Brandenberg → Tinker → Cohen → Texas v. Johnson → Snyder

  Lineage C – Equal Protection / Civil Rights
    Plessy → Brown → Loving → Frontiero → Craig → VMI

  Lineage D – Criminal Procedure
    Weeks → Mapp → Miranda → Terry → Katz → Kyllo → Riley

Cross-lineage citations are also added (e.g., Roe cites Griswold, which
creates a realistic multi-hop network).

Run:
    python data/generate_toy_dataset.py

Output:
    data/toy_cases.jsonl   – one JSON record per line (streaming-safe)
    data/toy_cases.json    – same data as a JSON array (for easy inspection)
"""

import json
import random
import re

random.seed(42)

# ── Master case registry ──────────────────────────────────────────────────────
# Each entry: (internal_id, name, abbreviation, citation, year, month)
# Citations follow real U.S. Reporter format: <volume> U.S. <page>

CASES = [
    # ── Lineage A: Privacy / Reproductive Rights ─────────────────────────────
    (1001, "Griswold v. Connecticut",          "Griswold v. Connecticut",    "381 U.S. 479", 1965, 6),
    (1002, "Eisenstadt v. Baird",              "Eisenstadt v. Baird",        "405 U.S. 438", 1972, 3),
    (1003, "Roe v. Wade",                      "Roe v. Wade",                "410 U.S. 113", 1973, 1),
    (1004, "Doe v. Bolton",                    "Doe v. Bolton",              "410 U.S. 179", 1973, 1),
    (1005, "Planned Parenthood v. Casey",      "Planned Parenthood v. Casey","505 U.S. 833", 1992, 6),
    (1006, "Lawrence v. Texas",                "Lawrence v. Texas",          "539 U.S. 558", 2003, 6),
    (1007, "Obergefell v. Hodges",             "Obergefell v. Hodges",       "576 U.S. 644", 2015, 6),
    (1008, "Dobbs v. Jackson Women's Health",  "Dobbs v. Jackson",           "597 U.S. 215", 2022, 6),
    (1009, "Carey v. Population Services",     "Carey v. Population Svcs.",  "431 U.S. 678", 1977, 5),
    (1010, "Webster v. Reproductive Health",   "Webster v. Reprod. Health",  "492 U.S. 490", 1989, 7),

    # ── Lineage B: First Amendment ────────────────────────────────────────────
    (2001, "Schenck v. United States",         "Schenck v. United States",   "249 U.S. 47",  1919, 3),
    (2002, "Brandenburg v. Ohio",              "Brandenburg v. Ohio",        "395 U.S. 444", 1969, 6),
    (2003, "Tinker v. Des Moines",             "Tinker v. Des Moines",       "393 U.S. 503", 1969, 2),
    (2004, "Cohen v. California",              "Cohen v. California",        "403 U.S. 15",  1971, 6),
    (2005, "Texas v. Johnson",                 "Texas v. Johnson",           "491 U.S. 397", 1989, 6),
    (2006, "R.A.V. v. City of St. Paul",       "R.A.V. v. St. Paul",         "505 U.S. 377", 1992, 6),
    (2007, "Snyder v. Phelps",                 "Snyder v. Phelps",           "562 U.S. 443", 2011, 3),
    (2008, "Matal v. Tam",                     "Matal v. Tam",               "582 U.S. 218", 2017, 6),
    (2009, "United States v. Stevens",         "United States v. Stevens",   "559 U.S. 460", 2010, 4),
    (2010, "Chaplinsky v. New Hampshire",      "Chaplinsky v. New Hampshire","315 U.S. 568", 1942, 3),

    # ── Lineage C: Equal Protection ───────────────────────────────────────────
    (3001, "Plessy v. Ferguson",               "Plessy v. Ferguson",         "163 U.S. 537", 1896, 5),
    (3002, "Brown v. Board of Education",      "Brown v. Board of Education","347 U.S. 483", 1954, 5),
    (3003, "Bolling v. Sharpe",                "Bolling v. Sharpe",          "347 U.S. 497", 1954, 5),
    (3004, "Loving v. Virginia",               "Loving v. Virginia",         "388 U.S. 1",   1967, 6),
    (3005, "Reed v. Reed",                     "Reed v. Reed",               "404 U.S. 71",  1971, 11),
    (3006, "Frontiero v. Richardson",          "Frontiero v. Richardson",    "411 U.S. 677", 1973, 5),
    (3007, "Craig v. Boren",                   "Craig v. Boren",             "429 U.S. 190", 1976, 12),
    (3008, "United States v. Virginia",        "United States v. Virginia",  "518 U.S. 515", 1996, 6),
    (3009, "City of Cleburne v. Cleburne",     "Cleburne v. Cleburne Living","473 U.S. 432", 1985, 7),
    (3010, "Regents v. Bakke",                 "Regents v. Bakke",           "438 U.S. 265", 1978, 6),

    # ── Lineage D: Criminal Procedure ────────────────────────────────────────
    (4001, "Weeks v. United States",           "Weeks v. United States",     "232 U.S. 383", 1914, 2),
    (4002, "Mapp v. Ohio",                     "Mapp v. Ohio",               "367 U.S. 643", 1961, 6),
    (4003, "Gideon v. Wainwright",             "Gideon v. Wainwright",       "372 U.S. 335", 1963, 3),
    (4004, "Miranda v. Arizona",               "Miranda v. Arizona",         "384 U.S. 436", 1966, 6),
    (4005, "Terry v. Ohio",                    "Terry v. Ohio",              "392 U.S. 1",   1968, 6),
    (4006, "Katz v. United States",            "Katz v. United States",      "389 U.S. 347", 1967, 12),
    (4007, "Kyllo v. United States",           "Kyllo v. United States",     "533 U.S. 27",  2001, 6),
    (4008, "Riley v. California",              "Riley v. California",        "573 U.S. 373", 2014, 6),
    (4009, "United States v. Jones",           "United States v. Jones",     "565 U.S. 400", 2012, 1),
    (4010, "Carpenter v. United States",       "Carpenter v. United States", "585 U.S. 296", 2018, 6),

    # ── Supporting cases (cross-lineage hubs) ────────────────────────────────
    (5001, "Meyer v. Nebraska",                "Meyer v. Nebraska",          "262 U.S. 390", 1923, 6),
    (5002, "Pierce v. Society of Sisters",     "Pierce v. Society of Sisters","268 U.S. 510",1925, 6),
    (5003, "Skinner v. Oklahoma",              "Skinner v. Oklahoma",        "316 U.S. 535", 1942, 6),
    (5004, "Prince v. Massachusetts",          "Prince v. Massachusetts",    "321 U.S. 158", 1944, 1),
    (5005, "Palko v. Connecticut",             "Palko v. Connecticut",       "302 U.S. 319", 1937, 12),
    (5006, "Rochin v. California",             "Rochin v. California",       "342 U.S. 165", 1952, 1),
    (5007, "Harisiades v. Shaughnessy",        "Harisiades v. Shaughnessy",  "342 U.S. 580", 1952, 3),
    (5008, "Marbury v. Madison",               "Marbury v. Madison",         "5 U.S. 137",   1803, 2),
    (5009, "McCulloch v. Maryland",            "McCulloch v. Maryland",      "17 U.S. 316",  1819, 3),
    (5010, "Lochner v. New York",              "Lochner v. New York",        "198 U.S. 45",  1905, 4),

    # ── Recent landmark cases ─────────────────────────────────────────────────
    (6001, "District of Columbia v. Heller",   "D.C. v. Heller",             "554 U.S. 570", 2008, 6),
    (6002, "McDonald v. City of Chicago",      "McDonald v. Chicago",        "561 U.S. 742", 2010, 6),
    (6003, "Citizens United v. FEC",           "Citizens United v. FEC",     "558 U.S. 310", 2010, 1),
    (6004, "National Federation v. Sebelius",  "NFIB v. Sebelius",           "567 U.S. 519", 2012, 6),
    (6005, "Shelby County v. Holder",          "Shelby County v. Holder",    "570 U.S. 529", 2013, 6),
    (6006, "Bostock v. Clayton County",        "Bostock v. Clayton County",  "590 U.S. 644", 2020, 6),
    (6007, "Trump v. Hawaii",                  "Trump v. Hawaii",            "585 U.S. 667", 2018, 6),
    (6008, "Masterpiece Cakeshop v. Colorado", "Masterpiece Cakeshop v. Colo.","584 U.S. 617",2018,6),
    (6009, "Whole Woman's Health v. Hellerstedt","Whole Woman's Health v. Hellerstedt","579 U.S. 582",2016,6),
    (6010, "Burwell v. Hobby Lobby",           "Burwell v. Hobby Lobby",     "573 U.S. 682", 2014, 6),
]

# ── Citation network edges ────────────────────────────────────────────────────
# Format: (citing_case_id, cited_case_id, weight)
# weight > 1 means the cited case is referenced multiple times in the opinion

EDGES = [
    # Lineage A internal
    (1002, 1001, 2),  # Eisenstadt cites Griswold (heavily)
    (1003, 1001, 3),  # Roe cites Griswold
    (1003, 1002, 1),  # Roe cites Eisenstadt
    (1003, 5001, 1),  # Roe cites Meyer
    (1003, 5002, 1),  # Roe cites Pierce
    (1003, 5003, 1),  # Roe cites Skinner
    (1004, 1003, 2),  # Doe v Bolton cites Roe
    (1005, 1003, 3),  # Casey cites Roe (heavily)
    (1005, 1001, 2),  # Casey cites Griswold
    (1005, 1002, 1),  # Casey cites Eisenstadt
    (1005, 1010, 1),  # Casey cites Webster
    (1006, 1001, 2),  # Lawrence cites Griswold
    (1006, 1005, 2),  # Lawrence cites Casey
    (1007, 1006, 2),  # Obergefell cites Lawrence
    (1007, 1005, 1),  # Obergefell cites Casey
    (1007, 3004, 1),  # Obergefell cites Loving
    (1008, 1003, 3),  # Dobbs cites Roe (to overturn)
    (1008, 1005, 3),  # Dobbs cites Casey (to overturn)
    (1008, 5008, 1),  # Dobbs cites Marbury
    (1009, 1001, 2),  # Carey cites Griswold
    (1009, 1002, 1),  # Carey cites Eisenstadt
    (1010, 1003, 2),  # Webster cites Roe

    # Lineage B internal
    (2002, 2001, 1),  # Brandenburg cites Schenck (to limit)
    (2003, 2001, 1),  # Tinker cites Schenck
    (2004, 2002, 1),  # Cohen cites Brandenburg
    (2005, 2002, 2),  # Texas v Johnson cites Brandenburg
    (2005, 2004, 1),  # Texas v Johnson cites Cohen
    (2006, 2002, 2),  # RAV cites Brandenburg
    (2006, 2005, 1),  # RAV cites Texas v Johnson
    (2007, 2005, 1),  # Snyder cites Texas v Johnson
    (2007, 2006, 1),  # Snyder cites RAV
    (2008, 2006, 1),  # Matal cites RAV
    (2009, 2002, 1),  # Stevens cites Brandenburg
    (2010, 2001, 1),  # Chaplinsky cites Schenck

    # Lineage C internal
    (3002, 3001, 2),  # Brown cites Plessy (to overturn)
    (3003, 3002, 2),  # Bolling cites Brown
    (3004, 3002, 1),  # Loving cites Brown
    (3005, 3004, 1),  # Reed cites Loving
    (3006, 3005, 1),  # Frontiero cites Reed
    (3007, 3006, 1),  # Craig cites Frontiero
    (3007, 3005, 1),  # Craig cites Reed
    (3008, 3007, 2),  # VMI cites Craig
    (3008, 3006, 1),  # VMI cites Frontiero
    (3009, 3007, 1),  # Cleburne cites Craig
    (3010, 3002, 1),  # Bakke cites Brown

    # Lineage D internal
    (4002, 4001, 2),  # Mapp cites Weeks
    (4004, 4003, 1),  # Miranda cites Gideon
    (4005, 4006, 1),  # Terry and Katz are contemporary
    (4006, 4005, 1),  # Katz and Terry cross-cite
    (4007, 4006, 2),  # Kyllo cites Katz
    (4007, 4005, 1),  # Kyllo cites Terry
    (4008, 4007, 2),  # Riley cites Kyllo
    (4008, 4006, 1),  # Riley cites Katz
    (4009, 4006, 2),  # Jones cites Katz
    (4009, 4007, 1),  # Jones cites Kyllo
    (4010, 4009, 2),  # Carpenter cites Jones
    (4010, 4007, 1),  # Carpenter cites Kyllo
    (4010, 4008, 1),  # Carpenter cites Riley

    # Cross-lineage (privacy meets equal protection meets criminal procedure)
    (1001, 5005, 1),  # Griswold cites Palko
    (1001, 5001, 2),  # Griswold cites Meyer
    (1001, 5002, 2),  # Griswold cites Pierce
    (1001, 5006, 1),  # Griswold cites Rochin
    (1003, 5004, 1),  # Roe cites Prince
    (1006, 3004, 1),  # Lawrence cites Loving
    (3004, 1001, 1),  # Loving cites Griswold (right to marry = privacy)
    (6001, 5008, 1),  # Heller cites Marbury
    (6002, 6001, 2),  # McDonald cites Heller
    (6009, 1005, 2),  # Whole Woman's Health cites Casey
    (6009, 1003, 1),  # Whole Woman's Health cites Roe
    (6010, 6004, 1),  # Hobby Lobby cites NFIB
    (5010, 5008, 1),  # Lochner cites Marbury
    (3010, 3007, 1),  # Bakke cites Craig
    (1007, 1001, 2),  # Obergefell cites Griswold (directly)
]

# ── Noise injection helpers ───────────────────────────────────────────────────

# OCR substitution noise: applied to a random 15% of case names
OCR_SUBS = [
    ("Court", "C0urt"),
    ("United", "Un1ted"),
    ("States", "Sta1es"),
    ("Board",  "B0ard"),
    ("Virginia", "V1rginia"),
]

# Citation string variant patterns (normaliser must handle all of these)
def cite_variants(cite: str) -> list[str]:
    """Returns 3-5 realistic noisy variants of a U.S. Reporter citation."""
    # canonical: "410 U.S. 113"
    variants = [cite]  # always include the canonical form
    no_dots  = cite.replace("U.S.", "US")          # "410 US 113"
    spaced   = cite.replace("U.S.", "U. S.")        # "410 U. S. 113"
    lower    = cite.replace("U.S.", "u.s.")         # "410 u.s. 113"
    padded   = re.sub(r"(\d+)\s+U\.S\.\s+(\d+)",
                      r"  \1  U.S.  \2  ", cite)   # extra whitespace
    variants += [no_dots, spaced, lower, padded]
    return variants


def inject_ocr_noise(name: str) -> str:
    for clean, noisy in OCR_SUBS:
        if clean in name:
            return name.replace(clean, noisy, 1)
    return name


def random_ocr_confidence(year: int) -> float:
    """Older cases have worse OCR. Adds realistic noise."""
    base = 0.72 if year >= 1970 else (0.55 if year >= 1920 else 0.42)
    return round(base + random.uniform(-0.08, 0.08), 3)


def pagerank_sim(case_id: int, in_degree: int) -> dict:
    raw = (in_degree + 1) * random.uniform(0.8e-6, 2.5e-6)
    return {"raw": round(raw, 12), "percentile": round(min(0.999, raw * 400000), 4)}


# ── Build id → case lookup ────────────────────────────────────────────────────
case_map = {c[0]: c for c in CASES}

# Compute in-degrees for pagerank simulation
in_degree_map = {c[0]: 0 for c in CASES}
for (src, dst, _) in EDGES:
    in_degree_map[dst] = in_degree_map.get(dst, 0) + 1

# Build outgoing edges per case
from collections import defaultdict
outgoing = defaultdict(list)
for (src, dst, weight) in EDGES:
    outgoing[src].append((dst, weight))


# ── Generate records ──────────────────────────────────────────────────────────

def build_record(case: tuple, noisy: bool = False) -> dict:
    cid, name, abbrev, cite, year, month = case

    # Inject OCR noise into ~15% of names
    stored_name = inject_ocr_noise(name) if noisy else name

    # decision_date: real data mixes YYYY-MM and YYYY-MM-DD
    if random.random() < 0.3:
        day = random.randint(1, 28)
        decision_date = f"{year}-{month:02d}-{day:02d}"
    else:
        decision_date = f"{year}-{month:02d}"

    # Own citation: pick a random variant 20% of the time (noise)
    own_cite = random.choice(cite_variants(cite)) if noisy else cite

    # cites_to edges
    cites_to = []
    for (dst_id, weight) in outgoing.get(cid, []):
        dst = case_map[dst_id]
        dst_cite = dst[3]
        # 20% chance of a variant cite string in the edge
        edge_cite = random.choice(cite_variants(dst_cite)) if random.random() < 0.2 else dst_cite
        edge = {
            "cite": edge_cite,
            "category": "reporters:scotus",
            "reporter": "U.S.",
            "case_ids": [dst_id],
            "opinion_index": 0,
            "case_paths": [f"/us/{dst_cite.replace(' ', '_')}"]
        }
        if weight > 1:
            edge["weight"] = weight
        cites_to.append(edge)

    # Some edges intentionally drop case_ids (unresolvable, like real data)
    for edge in cites_to:
        if random.random() < 0.15:
            del edge["case_ids"]
            del edge["case_paths"]

    ocr_conf = random_ocr_confidence(year)
    word_count = random.randint(2000, 18000)

    return {
        "id": cid,
        "name": stored_name,
        "name_abbreviation": abbrev,
        "decision_date": decision_date,
        "docket_number": "" if random.random() < 0.3 else f"No. {random.randint(60,99)}-{random.randint(100,9999)}",
        "first_page": str(int(cite.split()[-1])),
        "last_page":  str(int(cite.split()[-1]) + random.randint(5, 60)),
        "citations": [{"type": "official", "cite": own_cite}],
        "court": {"name_abbreviation": "U.S.", "id": 9029, "name": "Supreme Court of the United States"},
        "jurisdiction": {"id": 39, "name_long": "United States", "name": "U.S."},
        "cites_to": cites_to,
        "analysis": {
            "cardinality": random.randint(300, 3000),
            "char_count": word_count * 6,
            "ocr_confidence": ocr_conf,
            "pagerank": pagerank_sim(cid, in_degree_map.get(cid, 0)),
            "sha256": f"{random.getrandbits(256):064x}",
            "simhash": f"1:{random.getrandbits(64):016x}",
            "word_count": word_count,
        },
        "last_updated": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T00:00:00+00:00",
        "provenance": {"date_added": f"{year}-{month:02d}-01", "source": "Harvard", "batch": "2018"},
        "file_name": f"{int(cite.split()[-1]):04d}-01",
        "first_page_order": int(cite.split()[-1]),
        "last_page_order":  int(cite.split()[-1]) + random.randint(5, 60),
    }


def generate(output_jsonl: str = "data/toy_cases.jsonl",
             output_json:  str = "data/toy_cases.json") -> None:

    # 15% of records get OCR noise
    noisy_ids = set(random.sample([c[0] for c in CASES], k=max(1, len(CASES)//7)))

    records = []
    for case in CASES:
        noisy = case[0] in noisy_ids
        records.append(build_record(case, noisy=noisy))

    # Write JSONL (streaming-safe, one record per line)
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Write JSON array (for easy human inspection)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    # ── Summary ──────────────────────────────────────────────────────────────
    total_edges = sum(len(r["cites_to"]) for r in records)
    with_ids    = sum(1 for r in records for e in r["cites_to"] if "case_ids" in e)
    noisy_names = sum(1 for r in records if any(sub in r["name"] for _, sub in OCR_SUBS))
    no_docket   = sum(1 for r in records if not r["docket_number"])

    print(f"✅  Generated {len(records)} case records")
    print(f"   Citation edges total   : {total_edges}")
    print(f"   Edges with case_ids    : {with_ids}  ({100*with_ids//max(total_edges,1)}%)")
    print(f"   OCR-noisy names        : {noisy_names}")
    print(f"   Missing docket numbers : {no_docket}")
    print(f"\n   Written to  → {output_jsonl}")
    print(f"               → {output_json}")
    print("\nGround-truth lineages for Seed-and-Expand eval:")
    print("  A (Privacy)   : 1001 → 1002 → 1003 → 1005 → 1006 → 1007")
    print("  B (1st Amend) : 2001 → 2002 → 2003 → 2005 → 2007")
    print("  C (Equal Prot): 3001 → 3002 → 3004 → 3007 → 3008")
    print("  D (Crim. Proc): 4001 → 4002 → 4004 → 4006 → 4007 → 4008 → 4010")


if __name__ == "__main__":
    generate()
