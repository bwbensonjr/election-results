# /// script
# requires-python = ">=3.11"
# ///
"""Compare each race's result with its polling average, and list the polls in every average, offline.

Run from the repository root: uv run scripts/build_results_vs_polls.py [--results PATH]
Writes 2026/results/results-vs-polls.csv and 2026/results/results-vs-polls-polls.csv.
The Big Board computes the same difference in the page; see docs/big-board.md.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from district_history import ROOT, publish_csvs, read_records

BASELINE = ROOT / "2026/baseline/election-baseline.json"
RESULTS = ROOT / "2026/results/ap-results.json"
HOUSE_INPUTS = ROOT / "2026/polls/house-poll-average-inputs.csv"
STATEWIDE_INPUTS = ROOT / "2026/polls/statewide-poll-average-inputs.csv"
OUTPUT_DIR = ROOT / "2026/results"
COMPARISON_FILE = "results-vs-polls.csv"
POLLS_FILE = "results-vs-polls-polls.csv"
STATUSES = ["compared", "no_polls", "no_votes", "principal_missing"]
COMPARISON_COLUMNS = [
    "race_key", "state", "office", "district", "poll_avg_status", "poll_dem_candidate", "poll_rep_candidate",
    "poll_dem_pct", "poll_rep_pct", "poll_dem_margin_pp", "poll_count", "poll_latest_end_date",
    "result_dem_pct", "result_rep_pct", "result_dem_margin_pp", "diff_pp", "called", "winner_party_group",
    "eevp", "total_votes", "status", "results_fetched_at",
]
POLL_COLUMNS = [
    "race_key", "office", "poll_id", "question_id", "pollster", "end_date", "population", "sample_size",
    "sample_size_imputed", "partisan", "dem_candidate", "rep_candidate", "dem_pct", "rep_pct", "dem_margin_pp",
    "weight",
]


class BuildError(Exception):
    pass


def fixed(value):
    return f"{round(value, 2) + 0.0:.2f}"


def text(value):
    return "" if value is None else str(value)


def compare_race(base, race):
    """Return the comparison row for one baseline race and its results entry.

    The margin is the poll principals' shares of the total vote, found by baseline
    candidate name, so an independent principal (AK-AL's Bill Hill) is compared
    with the Republican rather than the top Democrat.
    """
    winner = race.get("winner") or {}
    row = {c: "" for c in COMPARISON_COLUMNS}
    row.update(
        race_key=base["race_key"], state=base["state_postal"], office=base["office"], district=base["district"],
        poll_avg_status=base["poll_avg_status"], called=str(bool(race.get("called"))),
        winner_party_group=text(winner.get("party_group")), eevp=text(race.get("eevp")),
        total_votes=text(race.get("total_votes") or 0),
    )
    if base["poll_avg_status"] != "available":
        row["status"] = "no_polls"
        return row
    row.update(
        poll_dem_candidate=base["poll_avg_dem_candidate"], poll_rep_candidate=base["poll_avg_rep_candidate"],
        poll_dem_pct=base["poll_avg_dem_pct"], poll_rep_pct=base["poll_avg_rep_pct"],
        poll_dem_margin_pp=base["poll_avg_dem_margin_pp"], poll_count=base["poll_count"],
        poll_latest_end_date=base["poll_latest_end_date"],
    )
    by_name = {c.get("baseline_name"): c for c in race.get("candidates", []) if c.get("baseline_name")}
    dem, rep = by_name.get(base["poll_avg_dem_candidate"]), by_name.get(base["poll_avg_rep_candidate"])
    if dem is None or rep is None:
        row["status"] = "principal_missing"
        return row
    total = race.get("total_votes") or 0
    if not total:
        row["status"] = "no_votes"
        return row
    dem_pct, rep_pct = 100 * dem["votes"] / total, 100 * rep["votes"] / total
    margin = dem_pct - rep_pct
    row.update(
        result_dem_pct=fixed(dem_pct), result_rep_pct=fixed(rep_pct), result_dem_margin_pp=fixed(margin),
        diff_pp=fixed(margin - float(base["poll_avg_dem_margin_pp"])), status="compared",
    )
    return row


def comparisons(baseline, results):
    races = results.get("races", {})
    missing = [r["race_key"] for r in baseline["races"] if r["race_key"] not in races]
    if missing:
        raise BuildError(f"results file has no entry for baseline races: {', '.join(missing)}")
    rows = []
    for base in sorted(baseline["races"], key=lambda r: r["race_key"]):
        row = compare_race(base, races[base["race_key"]])
        row["results_fetched_at"] = text(results.get("fetched_at"))
        rows.append(row)
    return rows


def poll_list(house_rows, statewide_rows):
    """Every included poll question from both input logs, newest first within each race."""
    rows = []
    for source, key_column in ((house_rows, "district_id"), (statewide_rows, "race_id")):
        for r in source:
            if r["included"] != "True":
                continue
            row = {c: r.get(c, "") for c in POLL_COLUMNS}
            row["race_key"] = r[key_column]
            row["office"] = r.get("office") or "House"
            rows.append(row)
    rows.sort(key=lambda r: (r["race_key"], r["question_id"]))
    rows.sort(key=lambda r: r["pollster"])
    rows.sort(key=lambda r: r["end_date"], reverse=True)
    rows.sort(key=lambda r: r["race_key"])
    return rows


def check_counts(comparison_rows, polls):
    counts = Counter(p["race_key"] for p in polls)
    bad = []
    for row in comparison_rows:
        expected = int(row["poll_count"] or 0)
        if counts.get(row["race_key"], 0) != expected:
            bad.append(f"{row['race_key']} (average {expected}, list {counts.get(row['race_key'], 0)})")
    extra = sorted(set(counts) - {r["race_key"] for r in comparison_rows})
    bad += [f"{k} (not a baseline race)" for k in extra]
    if bad:
        raise BuildError(f"included poll counts differ from the averages: {', '.join(bad)}")


def build(results_path=RESULTS, baseline_path=BASELINE, house_inputs=HOUSE_INPUTS,
          statewide_inputs=STATEWIDE_INPUTS, output_dir=OUTPUT_DIR):
    baseline = json.loads(Path(baseline_path).read_text())
    results = json.loads(Path(results_path).read_text())
    rows = comparisons(baseline, results)
    polls = poll_list(read_records(house_inputs)[1], read_records(statewide_inputs)[1])
    check_counts(rows, polls)
    publish_csvs(output_dir, [(COMPARISON_FILE, COMPARISON_COLUMNS, rows), (POLLS_FILE, POLL_COLUMNS, polls)])
    return rows, polls


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare results with polling averages for every race.")
    parser.add_argument("--results", default=RESULTS, help="results file (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        rows, polls = build(args.results)
    except (BuildError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    counts = Counter(r["status"] for r in rows)
    print(f"Wrote {len(rows)} races and {len(polls)} polls to {OUTPUT_DIR}: "
          + ", ".join(f"{s} {counts.get(s, 0)}" for s in STATUSES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
