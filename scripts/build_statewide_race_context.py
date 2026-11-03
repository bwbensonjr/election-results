# /// script
# requires-python = ">=3.11"
# ///
"""Join state presidential margins, Cook state PVI, polling averages, and the election guide
to the 2026 Senate and governor field, offline.

Run from the repository root: uv run scripts/build_statewide_race_context.py [--require-complete]
See docs/statewide-data.md for schemas, statuses, and the rebuild order.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from build_statewide_poll_averages import (
    AVERAGE_COLUMNS, DEFAULT_MATCHUPS, DEFAULT_POLLS, OUTPUT_DIR as POLLS_DIR, POLL_COLUMNS,
    compute as compute_poll_averages,
)
from district_history import (
    DEFAULT_MANIFEST, RESULTS_DIR, ROOT, STATE_PRESIDENTIAL_COLUMNS, STATE_PVI_COLUMNS,
    normalized_state_sources, publish_csvs, read_records, require_unique,
)
from incumbent_roster import (
    CANDIDATE_COLUMNS as ROSTER_CANDIDATE_COLUMNS, DEFAULT_ROSTER, RACE_COLUMNS as ROSTER_COLUMNS, candidate_flag,
    load_roster, race_values,
)
from election_guide import (
    DEFAULT_GUIDE, SOURCE_ID as GUIDE_SOURCE_ID, STATEWIDE_GUIDE_COLUMNS, load_statewide_guide,
    statewide_name_check,
)

DEFAULT_CANDIDATES = ROOT / "2026/candidates/statewide-general-field.csv"
DEFAULT_HOUSE_CANDIDATES = ROOT / "2026/candidates/house-general-field.csv"
DEFAULT_POLL_AVERAGES = POLLS_DIR / "statewide-poll-averages.csv"
OUTPUT_DIR = ROOT / "2026/statewide"
IDENTITY_COLUMNS = ["state", "office", "race_id", "election_cycle"]
COUNT_COLUMNS = ["candidate_count", "unresolved_fec_candidate_count"]
METRIC_COLUMNS = ["pres_2020_dem_margin_pp", "pres_2024_dem_margin_pp", "cook_pvi_label", "cook_pvi_dem_lean_pp"]
STATUS_COLUMNS = ["pres_2020_status", "pres_2024_status", "cook_pvi_status"]
SOURCE_COLUMNS = ["pres_2020_source_id", "pres_2024_source_id", "cook_pvi_source_id", "cook_pvi_edition"]
GUIDE_CONTEXT_COLUMNS = STATEWIDE_GUIDE_COLUMNS + ["guide_name_check", "guide_status", "guide_source_id"]
RACE_COLUMNS = (IDENTITY_COLUMNS + COUNT_COLUMNS + METRIC_COLUMNS + STATUS_COLUMNS + SOURCE_COLUMNS
                + POLL_COLUMNS + GUIDE_CONTEXT_COLUMNS + ROSTER_COLUMNS)
APPENDED_COLUMNS = (["election_cycle"] + METRIC_COLUMNS + STATUS_COLUMNS + SOURCE_COLUMNS
                    + POLL_COLUMNS + GUIDE_CONTEXT_COLUMNS + ROSTER_CANDIDATE_COLUMNS)
ISSUE_COLUMNS = ["state", "office", "race_id", "metric", "source_id", "issue", "detail"]
UNRESOLVED_STATUSES = {"unmatched", "ambiguous", "reviewed_unmatched"}
MATCH_STATUSES = UNRESOLVED_STATUSES | {"automatic", "reviewed", "not_federal"}


def verify_saved(path, columns, expected, key_of, rebuild):
    """Return saved rows after checking they equal a fresh in-memory rebuild."""
    _, rows = read_records(path, columns)
    require_unique([dict(r, source_record=r.get("source_record", "")) for r in rows], key_of, path)
    if sorted(tuple(r[c] for c in columns) for r in rows) != sorted(tuple(r[c] for c in columns) for r in expected):
        raise ValueError(f"{path}: stale or inconsistent output; run {rebuild}")
    return rows


def build(candidate_path=DEFAULT_CANDIDATES, manifest_path=DEFAULT_MANIFEST,
          house_candidate_path=DEFAULT_HOUSE_CANDIDATES,
          state_history_path=RESULTS_DIR / "state-presidential-normalized.csv",
          state_pvi_path=RESULTS_DIR / "cook-state-pvi-normalized.csv", poll_paths=None,
          poll_averages_path=DEFAULT_POLL_AVERAGES, matchups_path=DEFAULT_MATCHUPS, guide_path=DEFAULT_GUIDE,
          output_dir=OUTPUT_DIR, require_complete=False, project_root=ROOT, roster_path=DEFAULT_ROSTER):
    sources, expected_history, expected_pvi = normalized_state_sources(manifest_path, project_root,
                                                                      house_candidate_path)
    history = verify_saved(state_history_path, STATE_PRESIDENTIAL_COLUMNS, expected_history,
                           lambda r: (r["state"], r["election_year"]), "normalize_district_history.py")
    pvi = verify_saved(state_pvi_path, STATE_PVI_COLUMNS, expected_pvi, lambda r: r["state"],
                       "normalize_district_history.py")
    expected_averages, _ = compute_poll_averages(poll_paths, candidate_path, matchups_path)
    averages = verify_saved(poll_averages_path, AVERAGE_COLUMNS, expected_averages, lambda r: r["race_id"],
                            "build_statewide_poll_averages.py")
    guide = load_statewide_guide(guide_path, candidate_path)
    candidate_columns, candidates = read_records(candidate_path)
    if not {"state", "office", "race_id", "name", "fec_match_status"} <= set(candidate_columns):
        raise ValueError(f"{candidate_path}: missing required candidate columns")
    if set(candidate_columns) & set(APPENDED_COLUMNS):
        raise ValueError(f"{candidate_path}: input already contains race context columns")
    groups = defaultdict(list)
    for row in candidates:
        if row["fec_match_status"] not in MATCH_STATUSES:
            raise ValueError(f"{candidate_path}: invalid candidate match status for {row['name']}")
        groups[(row["state"], row["office"], row["race_id"])].append(row)
    roster = load_roster(roster_path, {race_id: (office, rows) for (_, office, race_id), rows in groups.items()},
                         {"Senate", "Governor"})
    history_by_key = {(r["state"], r["election_year"]): r for r in history}
    pvi_by_state = {r["state"]: r for r in pvi}
    averages_by_race = {r["race_id"]: r for r in averages}
    pres_source = sources["presidential"]["source_id"]
    pvi_source = sources["cook_state_pvi"]["source_id"]
    races, enriched, issues = [], [], []

    def add_issue(key, metric, source_id, issue, detail):
        issues.append(dict(zip(ISSUE_COLUMNS, [*key, metric, source_id, issue, detail])))

    for key, rows in sorted(groups.items(), key=lambda item: item[0][2]):
        state, office, race_id = key
        context = dict(zip(IDENTITY_COLUMNS, [state, office, race_id, "2026"]))
        context.update(candidate_count=str(len(rows)), unresolved_fec_candidate_count=str(
            sum(row["fec_match_status"] in UNRESOLVED_STATUSES for row in rows)))
        for year in ["2020", "2024"]:
            metric = f"pres_{year}"
            record = history_by_key.get((state, year))
            value = record["dem_margin_pp"] if record else ""
            context[f"{metric}_dem_margin_pp"] = value
            context[f"{metric}_status"] = "available" if value != "" else "missing"
            context[f"{metric}_source_id"] = pres_source
            if value == "":
                add_issue(key, metric, pres_source, "missing_value" if record else "missing_state",
                          f"Districts without counts: {record['missing_districts']}" if record
                          else "No state presidential row")
        record = pvi_by_state.get(state)
        label = record["cook_pvi_label"] if record else ""
        context.update(cook_pvi_label=label, cook_pvi_dem_lean_pp=record["cook_pvi_dem_lean_pp"] if record else "",
                       cook_pvi_status="available" if label else "missing", cook_pvi_source_id=pvi_source,
                       cook_pvi_edition=record["pvi_edition"] if record else "")
        if not label:
            add_issue(key, "cook_pvi", pvi_source, "missing_value" if record else "missing_state",
                      "Published state PVI is blank" if record else "No Cook state row")
        context.update({column: averages_by_race[race_id][column] for column in POLL_COLUMNS})
        guide_row = guide.get(race_id)
        context.update({column: guide_row[column] if guide_row else "" for column in STATEWIDE_GUIDE_COLUMNS})
        context.update(guide_name_check=statewide_name_check(guide_row, rows) if guide_row else "",
                       guide_status="in_guide" if guide_row else "not_in_guide", guide_source_id=GUIDE_SOURCE_ID)
        context.update(race_values(roster[race_id]))
        races.append(context)
        for row in rows:
            enriched.append(dict(row, **{column: context[column] for column in APPENDED_COLUMNS
                                         if column != "roster_incumbent"},
                                 roster_incumbent=candidate_flag(roster[race_id], row)))
    issues.sort(key=lambda r: tuple(r[c] for c in ISSUE_COLUMNS))
    enriched.sort(key=lambda r: (r["race_id"], *(r[c] for c in candidate_columns)))
    if require_complete and issues:
        details = "; ".join(f"{r['race_id']} {r['metric']}: {r['detail']}" for r in issues[:10])
        raise ValueError(f"incomplete statewide context: {len(issues)} missing race metrics; {details}")
    publish_csvs(output_dir, [
        ("statewide-race-context.csv", RACE_COLUMNS, races),
        ("statewide-candidate-context.csv", candidate_columns + APPENDED_COLUMNS, enriched),
        ("statewide-context-issues.csv", ISSUE_COLUMNS, issues),
    ])
    return races, enriched, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--house-candidates", type=Path, default=DEFAULT_HOUSE_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--state-history", type=Path, default=RESULTS_DIR / "state-presidential-normalized.csv")
    parser.add_argument("--state-pvi", type=Path, default=RESULTS_DIR / "cook-state-pvi-normalized.csv")
    parser.add_argument("--senate-polls", type=Path, default=DEFAULT_POLLS["Senate"])
    parser.add_argument("--governor-polls", type=Path, default=DEFAULT_POLLS["Governor"])
    parser.add_argument("--poll-averages", type=Path, default=DEFAULT_POLL_AVERAGES)
    parser.add_argument("--matchups", type=Path, default=DEFAULT_MATCHUPS)
    parser.add_argument("--guide", type=Path, default=DEFAULT_GUIDE)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        races, candidates, issues = build(
            args.candidates, args.manifest, args.house_candidates, args.state_history, args.state_pvi,
            {"Senate": args.senate_polls, "Governor": args.governor_polls}, args.poll_averages, args.matchups,
            args.guide, args.output_dir, args.require_complete, roster_path=args.roster)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Statewide build failed: {exc}")
    print(f"Wrote {len(races)} races, {len(candidates)} candidates, {len(issues)} issues", file=sys.stderr)


if __name__ == "__main__":
    main()
