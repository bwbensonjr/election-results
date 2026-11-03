# /// script
# requires-python = ">=3.11"
# ///
"""Validate the election-night guide races CSV against its markdown source and the House field, offline.

With --statewide-field, also validate its Senate and governor rows against the statewide field.
Run from the repository root: uv run scripts/election_guide.py
See docs/district-data.md for the schema, vocabularies, and the House join, and
docs/statewide-data.md for the Senate and governor join.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from build_house_field import poll_candidates
from district_history import ROOT, STATES, district_key, read_records

GUIDE_DIR = ROOT / "2026/guide"
DEFAULT_GUIDE = GUIDE_DIR / "election-night-guide-races.csv"
DEFAULT_MARKDOWN = GUIDE_DIR / "election-night-guide-november-3-2026.md"
DEFAULT_CANDIDATES = ROOT / "2026/candidates/house-general-field.csv"
DEFAULT_STATEWIDE_CANDIDATES = ROOT / "2026/candidates/statewide-general-field.csv"
SOURCE_ID = "election-night-guide-2026-11-03"
RACE_COLUMNS = [
    "slot_et", "poll_close_et", "state", "office", "district", "card", "incumbent", "incumbent_party",
    "open_seat", "dem_candidate", "rep_candidate", "other_candidate", "rating", "silver_avg_dem_margin",
    "trump_2024_margin", "senate_path", "ladder_tier", "hell_yes", "ffs", "chill", "notes",
]
# Race columns carried into the House context, each prefixed with "guide_". The key columns are
# replaced by district_id, and senate_path never applies to a House race.
JOINED_COLUMNS = [c for c in RACE_COLUMNS if c not in ("state", "office", "district", "senate_path")]
GUIDE_COLUMNS = [f"guide_{c}" for c in JOINED_COLUMNS]
# Senate and governor rows join by race ID, so only their key columns are dropped.
STATEWIDE_JOINED_COLUMNS = [c for c in RACE_COLUMNS if c not in ("state", "office", "district")]
STATEWIDE_GUIDE_COLUMNS = [f"guide_{c}" for c in STATEWIDE_JOINED_COLUMNS]
STATEWIDE_OFFICE_CODES = {"Senate": "SEN", "Governor": "GOV"}
PARTY_SUFFIX = re.compile(r"\s*\([^()]*\)$")
OFFICES = ["House", "Senate", "Governor"]
SLOTS = ["6:00", "7:00", "7:30", "8:00", "9:00", "10 to 11", "12:00+"]
TIERS = ["We'll take it", "Solid", "2018-style", "Holy shit"]
PARTIES = ["D", "R", "I"]
BOOLEANS = ["True", "False"]
POLL_CLOSE = re.compile(r"(1[0-9]|2[0-4]):(00|30)")
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


def is_number(value):
    try:
        float(value)
    except ValueError:
        return False
    return True


def validate_race(row, location):
    """Check one race row's controlled values, raising ValueError with its location."""
    for column, allowed, blank_ok in [("office", OFFICES, False), ("state", STATES, False),
                                      ("slot_et", SLOTS, False), ("ladder_tier", TIERS, True),
                                      ("incumbent_party", PARTIES, True), ("open_seat", BOOLEANS, True)]:
        if row[column] not in allowed and not (blank_ok and row[column] == ""):
            raise ValueError(f"{location}: invalid {column} {row[column]!r}")
    if not POLL_CLOSE.fullmatch(row["poll_close_et"]):
        raise ValueError(f"{location}: invalid poll_close_et {row['poll_close_et']!r}")
    for column in ["silver_avg_dem_margin", "trump_2024_margin"]:
        if row[column] and not is_number(row[column]):
            raise ValueError(f"{location}: invalid {column} {row[column]!r}")
    if (row["office"] == "House") != (row["district"] != ""):
        raise ValueError(f"{location}: district must be set for House races and only for them")


def load_guide(guide_path=DEFAULT_GUIDE, markdown_path=DEFAULT_MARKDOWN, candidate_path=DEFAULT_CANDIDATES):
    """Validate the races CSV and return its House rows as guide columns keyed by canonical district key."""
    _, rows = read_records(guide_path, RACE_COLUMNS)
    field = field_districts(candidate_path)
    at_large = {state for state in {k[0] for k in field} if {k[1] for k in field if k[0] == state} == {"00"}}
    guide = {}
    for line, row in enumerate(rows, 2):
        location = f"{guide_path} row {line}"
        validate_race(row, location)
        if row["office"] != "House":
            continue
        district_id = f"{row['state']}-{row['district']}"
        try:
            key = district_key(district_id)
        except ValueError:
            raise ValueError(f"{location}: invalid House district {district_id!r}") from None
        if row["district"] != key[1]:
            raise ValueError(f"{location}: district {row['district']!r} must be canonical {key[1]!r}")
        if key in guide:
            raise ValueError(f"{location}: duplicate district {key[2]}")
        if key not in field:
            raise ValueError(f"{location}: district {key[2]} is not in the candidate field")
        guide[key] = {f"guide_{c}": row[c] for c in JOINED_COLUMNS}
    referenced = markdown_districts(markdown_path, at_large)
    missing = sorted(k[2] for k in referenced - set(guide))
    extra = sorted(k[2] for k in set(guide) - referenced)
    if missing or extra:
        details = [f"missing from the CSV: {', '.join(missing)}"] if missing else []
        details += [f"absent from the guide: {', '.join(extra)}"] if extra else []
        raise ValueError(f"{guide_path}: House districts differ from {markdown_path}; {'; '.join(details)}")
    return guide


def load_statewide_guide(guide_path=DEFAULT_GUIDE, statewide_path=DEFAULT_STATEWIDE_CANDIDATES):
    """Validate the races CSV's Senate and governor rows and return their guide columns by race ID."""
    _, rows = read_records(guide_path, RACE_COLUMNS)
    _, candidates = read_records(statewide_path)
    races = {row["race_id"] for row in candidates}
    guide = {}
    for line, row in enumerate(rows, 2):
        location = f"{guide_path} row {line}"
        validate_race(row, location)
        if row["office"] == "House":
            continue
        race_id = f"{row['state']}-{STATEWIDE_OFFICE_CODES[row['office']]}"
        if race_id in guide:
            raise ValueError(f"{location}: duplicate {row['office']} row for {row['state']}")
        if race_id not in races:
            raise ValueError(f"{location}: {row['state']} {row['office']} race {race_id} is not in the statewide field")
        guide[race_id] = {f"guide_{c}": row[c] for c in STATEWIDE_JOINED_COLUMNS}
    return guide


def statewide_name_check(row, field_rows):
    """Compare a statewide guide row's names with its race's field by the poll surname rule.

    Democratic and Republican names are checked against that party's candidates and the
    other name against everyone else, after dropping a trailing party note such as "(I)".
    """
    results = []
    for column, candidates in [
        ("guide_dem_candidate", [r for r in field_rows if r["party"] == "DEM"]),
        ("guide_rep_candidate", [r for r in field_rows if r["party"] == "REP"]),
        ("guide_other_candidate", [r for r in field_rows if r["party"] not in ("DEM", "REP")]),
    ]:
        name = PARTY_SUFFIX.sub("", row[column].strip())
        if name:
            results.append(len(poll_candidates(name, candidates)) == 1)
    if not results:
        return "not_named"
    return "matched" if all(results) else "mismatch"


def name_check(row, field_rows):
    """Compare guide candidate names with the field's DEM and REP candidates by the poll surname rule."""
    results = []
    for column, party in [("guide_dem_candidate", "DEM"), ("guide_rep_candidate", "REP")]:
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
    parser.add_argument("--statewide-field", type=Path,
                        help="Also validate Senate and governor rows against this statewide field")
    args = parser.parse_args()
    try:
        guide = load_guide(args.guide, args.markdown, args.candidates)
        field = field_districts(args.candidates)
        statewide = load_statewide_guide(args.guide, args.statewide_field) if args.statewide_field else None
        _, statewide_rows = read_records(args.statewide_field) if args.statewide_field else (None, [])
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Guide validation failed: {exc}")
    checks = defaultdict(int)
    for key, row in guide.items():
        checks[name_check(row, field[key])] += 1
    print(f"Guide valid: {len(guide)} House districts; name checks {dict(sorted(checks.items()))}", file=sys.stderr)
    if statewide is not None:
        races = defaultdict(list)
        for row in statewide_rows:
            races[row["race_id"]].append(row)
        checks = defaultdict(int)
        for race_id, row in statewide.items():
            checks[statewide_name_check(row, races[race_id])] += 1
        print(f"Guide valid: {len(statewide)} Senate and governor races; name checks "
              f"{dict(sorted(checks.items()))}", file=sys.stderr)


if __name__ == "__main__":
    main()
