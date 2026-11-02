# /// script
# requires-python = ">=3.11"
# ///
"""Join saved district margins and published PVI to the House field, offline."""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from district_history import (
    DEFAULT_MANIFEST, ROOT, RESULTS_DIR, PRESIDENTIAL_COLUMNS, PVI_COLUMNS,
    district_key, normalized_sources, publish_csvs, read_records, require_unique,
)

DEFAULT_CANDIDATES = ROOT / "2026/candidates/house-general-field.csv"
OUTPUT_DIR = ROOT / "2026/districts"
IDENTITY_COLUMNS = ["state", "district", "district_id", "election_cycle"]
COUNT_COLUMNS = ["candidate_count", "unresolved_fec_candidate_count"]
METRIC_COLUMNS = ["pres_2020_dem_margin_pp", "pres_2024_dem_margin_pp", "cook_pvi_label", "cook_pvi_dem_lean_pp"]
STATUS_COLUMNS = ["pres_2020_status", "pres_2024_status", "cook_pvi_status"]
SOURCE_COLUMNS = ["pres_2020_source_id", "pres_2024_source_id", "cook_pvi_source_id"]
DISTRICT_COLUMNS = IDENTITY_COLUMNS + COUNT_COLUMNS + METRIC_COLUMNS + STATUS_COLUMNS + SOURCE_COLUMNS
APPENDED_COLUMNS = ["district_id", "election_cycle"] + METRIC_COLUMNS + STATUS_COLUMNS + SOURCE_COLUMNS
ISSUE_COLUMNS = ["state", "district", "district_id", "metric", "source_id", "issue", "detail"]
UNRESOLVED_STATUSES = {"unmatched", "ambiguous", "reviewed_unmatched"}
MATCH_STATUSES = UNRESOLVED_STATUSES | {"automatic", "reviewed"}


def verify_normalized(path, columns, expected, key_of):
    _, rows = read_records(path, columns)
    require_unique(rows, key_of, path)
    actual_values = sorted(tuple(row[c] for c in columns) for row in rows)
    expected_values = sorted(tuple(row[c] for c in columns) for row in expected)
    if actual_values != expected_values:
        raise ValueError(f"{path}: stale or inconsistent normalization; run normalize_district_history.py")
    return rows


def build(candidate_path=DEFAULT_CANDIDATES, manifest_path=DEFAULT_MANIFEST,
          history_path=RESULTS_DIR / "presidential-results-normalized.csv",
          pvi_path=RESULTS_DIR / "cook-pvi-normalized.csv", output_dir=OUTPUT_DIR,
          require_complete=False, project_root=ROOT):
    sources, expected_history, expected_pvi = normalized_sources(manifest_path, project_root)
    history = verify_normalized(history_path, PRESIDENTIAL_COLUMNS, expected_history,
                                lambda r: (r["state"], r["district"], r["election_year"]))
    pvi = verify_normalized(pvi_path, PVI_COLUMNS, expected_pvi,
                           lambda r: (r["state"], r["district"]))
    candidate_columns, candidates = read_records(candidate_path)
    if not {"state", "district", "name", "fec_match_status"} <= set(candidate_columns):
        raise ValueError(f"{candidate_path}: missing required candidate columns")
    if set(candidate_columns) & set(APPENDED_COLUMNS):
        raise ValueError(f"{candidate_path}: input already contains district context columns")
    groups = defaultdict(list)
    for row in candidates:
        key = district_key(f"{row['state']}-{row['district']}")
        if row["fec_match_status"] not in MATCH_STATUSES:
            raise ValueError(f"{candidate_path}: invalid candidate match status for {row['name']}")
        groups[key].append(row)
    history_by_key = {(r["state"], r["district"], r["election_year"]): r for r in history}
    pvi_by_key = {(r["state"], r["district"]): r for r in pvi}
    districts, enriched, issues = [], [], []

    def add_issue(key, metric, source_id, issue, detail):
        issues.append(dict(zip(ISSUE_COLUMNS, [*key, metric, source_id, issue, detail])))

    for key, rows in sorted(groups.items()):
        state, district, district_id = key
        context = dict(zip(IDENTITY_COLUMNS, [state, district, district_id, "2026"]))
        context.update(candidate_count=str(len(rows)), unresolved_fec_candidate_count=str(
            sum(row["fec_match_status"] in UNRESOLVED_STATUSES for row in rows)))
        for year in ["2020", "2024"]:
            metric = f"pres_{year}"
            source_id = sources["presidential"]["source_id"]
            record = history_by_key.get((state, district, year))
            value = record["dem_margin_pp"] if record else ""
            context[f"{metric}_dem_margin_pp"] = value
            context[f"{metric}_status"] = "available" if value != "" else "missing"
            context[f"{metric}_source_id"] = source_id
            if value == "":
                add_issue(key, metric, source_id, "missing_value" if record else "missing_district",
                          "Published margin is blank" if record else "No presidential district/year row")
        source_id = sources["cook_pvi"]["source_id"]
        record = pvi_by_key.get((state, district))
        label = record["cook_pvi_label"] if record else ""
        context.update(cook_pvi_label=label, cook_pvi_dem_lean_pp=record["cook_pvi_dem_lean_pp"] if record else "",
                       cook_pvi_status="available" if label else "missing", cook_pvi_source_id=source_id)
        if not label:
            add_issue(key, "cook_pvi", source_id, "missing_value" if record else "missing_district",
                      "Published 2026 PVI is blank" if record else "No Cook district row")
        districts.append(context)
        for row in rows:
            enriched.append(dict(row, **{column: context[column] for column in APPENDED_COLUMNS}))
    target_keys = {(state, district) for state, district, _ in groups}
    for record in history:
        key = record["state"], record["district"]
        if key not in target_keys:
            add_issue((*key, record["district_id"]), f"pres_{record['election_year']}", record["source_id"],
                      "source_only_district", "Source district absent from candidate field")
    for record in pvi:
        key = record["state"], record["district"]
        if key not in target_keys:
            add_issue((*key, record["district_id"]), "cook_pvi", record["source_id"],
                      "source_only_district", "Source district absent from candidate field")
    issues.sort(key=lambda r: tuple(r[c] for c in ISSUE_COLUMNS))
    enriched.sort(key=lambda r: (r["district_id"], *(r[c] for c in candidate_columns)))
    missing = [row for row in issues if row["issue"] in {"missing_value", "missing_district"}]
    if require_complete and missing:
        details = "; ".join(f"{r['district_id']} {r['metric']}: {r['detail']}" for r in missing[:10])
        raise ValueError(f"incomplete district context: {len(missing)} missing target metrics; {details}")
    publish_csvs(output_dir, [
        ("house-district-context.csv", DISTRICT_COLUMNS, districts),
        ("house-candidate-context.csv", candidate_columns + APPENDED_COLUMNS, enriched),
        ("district-context-issues.csv", ISSUE_COLUMNS, issues),
    ])
    return districts, enriched, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--history", type=Path, default=RESULTS_DIR / "presidential-results-normalized.csv")
    parser.add_argument("--pvi", type=Path, default=RESULTS_DIR / "cook-pvi-normalized.csv")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        districts, candidates, issues = build(args.candidates, args.manifest, args.history,
                                             args.pvi, args.output_dir, args.require_complete)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"District build failed: {exc}")
    print(f"Wrote {len(districts)} districts, {len(candidates)} candidates, {len(issues)} issues", file=sys.stderr)


if __name__ == "__main__":
    main()
