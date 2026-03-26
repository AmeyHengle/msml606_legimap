"""
normalise.py — citation string cleaning and OCR correction.

Two problems I'm solving here:
  1. The same case appears with different citation formats in the raw data
     ("410 U.S. 113", "410 US 113", "410 u.s. 113" all mean the same thing).
     I normalise everything to a terse key like "410US113" so the hash table
     can do a reliable O(1) lookup regardless of which variant shows up.

  2. Old case records were scanned via OCR and have predictable typos
     (digits substituted for letters: "C0urt", "Un1ted", etc.).
     I fix those before storing anything.
"""

from __future__ import annotations
import re


# Matches U.S. Reporter citations in any reasonable format.
# Handles: U.S. / US / U. S. / u.s. and extra whitespace.
_US_REPORTER = re.compile(
    r"""
    (\d+)               # volume
    \s+
    [Uu]\.?\s*[Ss]\.?   # reporter abbreviation
    \s+
    (\d+)               # page
    """,
    re.VERBOSE,
)


def normalise_citation(raw: str) -> str | None:
    """
    Convert any U.S. Reporter citation variant to a canonical key.
    Returns None if the string doesn't match (e.g. state reporters).

    "410 U. S. 113" -> "410US113"
    "1 Ala. 9"      -> None
    """
    if not raw or not isinstance(raw, str):
        return None
    match = _US_REPORTER.search(raw.strip())
    if not match:
        return None
    return f"{match.group(1)}US{match.group(2)}"


def normalise_citation_display(raw: str) -> str | None:
    """Same as above but returns a readable form for the UI: "410 U.S. 113"."""
    if not raw or not isinstance(raw, str):
        return None
    match = _US_REPORTER.search(raw.strip())
    if not match:
        return None
    return f"{match.group(1)} U.S. {match.group(2)}"


# Known OCR substitution errors I've seen in this dataset.
# More specific patterns come first to avoid partial matches.
_OCR_CORRECTIONS: list[tuple[str, str]] = [
    ("C0urt",     "Court"),
    ("c0urt",     "court"),
    ("Un1ted",    "United"),
    ("un1ted",    "united"),
    ("Sta1es",    "States"),
    ("sta1es",    "states"),
    ("B0ard",     "Board"),
    ("b0ard",     "board"),
    ("V1rginia",  "Virginia"),
    ("v1rginia",  "virginia"),
    ("0hio",      "Ohio"),
    ("Ca1ifornia","California"),
    ("lllinois",  "Illinois"),
    ("lndiana",   "Indiana"),
    ("1aw",       "law"),
    ("1egal",     "legal"),
    ("v ,",       "v."),
    (" v .",      " v."),
]

_OCR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(re.escape(p)), r) for p, r in _OCR_CORRECTIONS
]


def correct_ocr(raw: str) -> str:
    """Apply my OCR correction map to a case name. Returns unchanged if no match."""
    if not raw or not isinstance(raw, str):
        return raw
    result = raw
    for pattern, replacement in _OCR_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def clean_record(record: dict) -> dict:
    """
    Run all cleaning steps on a single CAP record, modifying it in-place.

    I OCR-correct the name fields, normalise the primary citation to a
    canonical_key, and attach canonical_key to every cites_to edge too.
    That last part is what lets build_index.py resolve dangling edge references
    via the hash table instead of only relying on the case_ids field.
    """
    record["name"] = correct_ocr(record.get("name", ""))
    record["name_abbreviation"] = correct_ocr(record.get("name_abbreviation", ""))

    own_cites = record.get("citations", [])
    record["canonical_key"] = normalise_citation(own_cites[0].get("cite", "")) if own_cites else None

    for edge in record.get("cites_to", []):
        edge["canonical_key"] = normalise_citation(edge.get("cite", ""))

    return record


if __name__ == "__main__":
    tests = [
        ("410 U.S. 113",       "410US113"),
        ("410 US 113",         "410US113"),
        ("410 U. S. 113",      "410US113"),
        ("410 u.s. 113",       "410US113"),
        ("  410  U.S.  113  ", "410US113"),
        ("381 U.S. 479",       "381US479"),
        ("1 Ala. 9",           None),
        ("",                   None),
    ]

    print("Citation normalisation tests")
    print("-" * 40)
    all_pass = True
    for raw, expected in tests:
        result = normalise_citation(raw)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}]  {raw!r:30s}  ->  {result!r}")

    ocr_tests = [
        ("C0urt of Appeals",       "Court of Appeals"),
        ("Un1ted States v. Jones", "United States v. Jones"),
        ("Griswold v. Connecticut","Griswold v. Connecticut"),
        ("B0ard of Education",     "Board of Education"),
        ("V1rginia v. Black",      "Virginia v. Black"),
    ]

    print("\nOCR correction tests")
    print("-" * 40)
    for raw, expected in ocr_tests:
        result = correct_ocr(raw)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}]  {raw!r:35s}  ->  {result!r}")

    print("\n" + ("All tests passed ✅" if all_pass else "Some tests FAILED ❌"))
