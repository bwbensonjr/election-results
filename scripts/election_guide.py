# /// script
# requires-python = ">=3.11"
# ///
"""Validate the curated House election-night guide CSV against its markdown source, offline.

Run from the repository root: uv run scripts/election_guide.py
See docs/district-data.md for the schema, vocabularies, and transcription conventions.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from build_house_field import poll_candidates
from district_history import ROOT, STATES, district_key, read_records

GUIDE_DIR = ROOT / "2026/guide"
DEFAULT_GUIDE = GUIDE_DIR / "election-night-guide-house.csv"
DEFAULT_MARKDOWN = GUIDE_DIR / "election-night-guide-november-3-2026.md"
DEFAULT_CANDIDATES = ROOT / "2026/candidates/house-general-field.csv"
SOURCE_ID = "election-night-guide-2026-11-03"
GUIDE_COLUMNS = [
    "district_id", "guide_watch_time_et", "guide_section", "guide_role", "guide_dem_win_tier",
    "guide_seat_signal", "guide_dem_name", "guide_rep_name", "guide_incumbent_note",
    "guide_rating_note", "guide_hell_yes", "guide_ffs", "guide_chill", "guide_note",
]
# Listed in precedence order: a district gets the first role the guide gives it.
ROLES = ["bellwether", "wave_ladder", "majority_check", "battleground", "stretch", "reach",
         "tsunami_tell", "hold_check"]
TIERS = ["We'll take it", "Solid", "2018-style", "Holy shit"]
WATCH_TIMES = ["6:00", "7:00", "7:30", "8:00", "9:00", "10:00", "11:00", "12:00+"]
DISTRICT_REFERENCE = re.compile(r"\b([A-Z]{2})-([0-9]{1,2})\b")


def field_districts(candidate_path):
    """Return candidate-field rows grouped by canonical district key."""
    _, candidates = read_records(candidate_path)
    field = defaultdict(list)
    for row in candidates:
        field[district_key(f"{row['state']}-{row['district']}")].append(row)
    return field


def markdown_districts(markdown_path, at_large):
    """Return canonical district keys for every House reference in the guide markdown."""
    text = Path(markdown_path).read_text(encoding="utf-8")
    return {district_key(f"{state}-{'AL' if state in at_large else number}")
            for state, number in DISTRICT_REFERENCE.findall(text) if state in STATES}


def load_guide(guide_path=DEFAULT_GUIDE, markdown_path=DEFAULT_MARKDOWN, candidate_path=DEFAULT_CANDIDATES):
    """Validate the guide CSV and return its rows keyed by canonical district key."""
    _, rows = read_records(guide_path, GUIDE_COLUMNS)
    field = field_districts(candidate_path)
    at_large = {state for state in {k[0] for k in field} if {k[1] for k in field if k[0] == state} == {"00"}}
    guide = {}
    for line, row in enumerate(rows, 2):
        location = f"{guide_path} row {line}"
        try:
            key = district_key(row["district_id"])
        except ValueError:
            raise ValueError(f"{location}: invalid district_id {row['district_id']!r}") from None
        if row["district_id"] != key[2]:
            raise ValueError(f"{location}: district_id {row['district_id']!r} must be canonical {key[2]!r}")
        for column, allowed, blank_ok in [("guide_watch_time_et", WATCH_TIMES, False),
                                          ("guide_role", ROLES, False),
                                          ("guide_dem_win_tier", TIERS, True)]:
            if row[column] not in allowed and not (blank_ok and row[column] == ""):
                raise ValueError(f"{location}: invalid {column} {row[column]!r}")
        if key in guide:
            raise ValueError(f"{location}: duplicate district {key[2]}")
        if key not in field:
            raise ValueError(f"{location}: district {key[2]} is not in the candidate field")
        guide[key] = row
    referenced = markdown_districts(markdown_path, at_large)
    missing = sorted(k[2] for k in referenced - set(guide))
    extra = sorted(k[2] for k in set(guide) - referenced)
    if missing or extra:
        details = [f"missing from the CSV: {', '.join(missing)}"] if missing else []
        details += [f"absent from the guide: {', '.join(extra)}"] if extra else []
        raise ValueError(f"{guide_path}: guide districts differ from {markdown_path}; {'; '.join(details)}")
    return guide


def name_check(row, field_rows):
    """Compare guide names with the field's DEM and REP candidates by the poll surname rule."""
    results = []
    for column, party in [("guide_dem_name", "DEM"), ("guide_rep_name", "REP")]:
        name = row[column].strip()
        if name:
            results.append(len(poll_candidates(name, [r for r in field_rows if r["party"] == party])) == 1)
    if not results:
        return "not_named"
    return "matched" if all(results) else "mismatch"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guide", type=Path, default=DEFAULT_GUIDE)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    args = parser.parse_args()
    try:
        guide = load_guide(args.guide, args.markdown, args.candidates)
        field = field_districts(args.candidates)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Guide validation failed: {exc}")
    checks = defaultdict(int)
    for key, row in guide.items():
        checks[name_check(row, field[key])] += 1
    print(f"Guide valid: {len(guide)} districts; name checks {dict(sorted(checks.items()))}", file=sys.stderr)


if __name__ == "__main__":
    main()
