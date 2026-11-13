# /// script
# requires-python = ">=3.11"
# ///
"""Embed the Big Board's static data (district shapes, a slim race baseline, and poll lists) into bigboard/index.html.

Run from the repository root after the baseline, shape, and results-vs-polls builds: uv run scripts/build_bigboard_data.py
Only the block between the board-data markers is replaced; the rest of the page is hand-written.
"""

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "2026/baseline/election-baseline.json"
GEOMETRY = ROOT / "2026/geometry/us-house-2026.json"
POLLS = ROOT / "2026/results/results-vs-polls-polls.csv"
PAGE = ROOT / "bigboard/index.html"
BEGIN = "<!-- board-data:begin -->"
END = "<!-- board-data:end -->"
RACE_COLUMNS = [
    "race_key", "state_postal", "office", "district", "roster_incumbent_name", "roster_incumbent_party",
    "roster_vacant", "open_seat", "pres_2024_dem_margin_pp", "pres_2024_status", "cook_pvi_label",
    "cook_pvi_dem_lean_pp", "cook_pvi_status",
    "poll_avg_dem_candidate", "poll_avg_rep_candidate", "poll_avg_dem_pct", "poll_avg_rep_pct",
    "poll_avg_dem_margin_pp", "poll_count", "poll_avg_status", "guide_rating", "guide_card", "guide_notes",
]
POLL_COLUMNS = ["end_date", "pollster", "population", "sample_size", "partisan", "dem_pct", "rep_pct", "dem_margin_pp"]
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


class BuildError(Exception):
    pass


def poll_lists(polls_path=POLLS):
    """Each race's polls in its average, newest first, as compact rows of POLL_COLUMNS."""
    polls = {}
    with open(polls_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            polls.setdefault(row["race_key"], []).append([row[c] for c in POLL_COLUMNS])
    for rows in polls.values():
        rows.sort(key=lambda r: (r[0], r[1]))
        rows.sort(key=lambda r: r[0], reverse=True)
    return dict(sorted(polls.items()))


def board_data(baseline_path=BASELINE, geometry_path=GEOMETRY, polls_path=POLLS):
    baseline = json.loads(Path(baseline_path).read_text())
    geometry = json.loads(Path(geometry_path).read_text())
    candidates = {}
    for c in baseline["candidates"]:
        candidates.setdefault(c["race_key"], []).append([c["name"], c["party"], c["roster_incumbent"] == "True"])
    return {
        "schema_version": 1,
        "baseline_sha256": baseline["input_sha256"],
        "geometry": {k: geometry[k] for k in ("frame", "prior_line_states", "states", "districts", "no_race")},
        "state_names": STATE_NAMES,
        "race_columns": RACE_COLUMNS,
        "races": [[r[c] for c in RACE_COLUMNS] for r in baseline["races"]],
        "candidates": dict(sorted(candidates.items())),
        "poll_columns": POLL_COLUMNS,
        "polls": poll_lists(polls_path),
    }


def embed(page_text, data):
    if page_text.count(BEGIN) != 1 or page_text.count(END) != 1:
        raise BuildError(f"page must contain exactly one {BEGIN} and one {END}")
    head, rest = page_text.split(BEGIN)
    _, tail = rest.split(END)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    block = f'{BEGIN}\n<script type="application/json" id="board-data">{payload}</script>\n{END}'
    return head + block + tail


def build(page=PAGE, baseline_path=BASELINE, geometry_path=GEOMETRY, polls_path=POLLS):
    page = Path(page)
    text = embed(page.read_text(), board_data(baseline_path, geometry_path, polls_path))
    fd, tmp = tempfile.mkstemp(dir=page.parent, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, page)
    return len(text.encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Embed the Big Board's static data into its page.")
    parser.add_argument("--page", default=PAGE, help="page to update (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        size = build(args.page)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote board data into {args.page}: {size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
