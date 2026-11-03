# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Flag 2026 House or Senate candidates who filed an FEC pre-general (12G) report.

A 12G filing corroborates general-election participation; it does not
certify ballot eligibility. Preserve all committee links and select the
latest report by receipt date, then numeric report identifier on ties.

Usage:
    uv run scripts/flag_general_candidates.py [--office {H,S}]

Reads 2026/candidates/fec-<office>-candidates.csv (from
fetch_fec_house_candidates.py) and writes, in the same directory:
    fec-<office>-candidates-flagged.csv  every candidate plus 12G columns
    fec-<office>-general.csv             only candidates who filed a 12G
    review-districts.csv                 House districts without a clean D vs. R field
    review-senate-races.csv              the same review for Senate races
where <office> is house (default) or senate.
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import requests

from fetch_fec_house_candidates import (
    CYCLE, DATA_DIR, OFFICE_NAMES, candidates_path, fetch_all, get_json, load_api_key,
)

TOP_TWO_STATES = {"CA", "WA"}
DEM_PARTIES = {"DEM", "DFL"}

REVIEW_FILES = {"H": "review-districts.csv", "S": "review-senate-races.csv"}

FLAG_FIELDS = [
    "filed_12g",
    "pre_general_receipts",
    "pre_general_cash_on_hand",
    "pre_general_coverage_end",
]


def report_order(report):
    """Stable ordering within and across committees, including amended reports."""
    identifier = report.get("file_number") or report.get("beginning_image_number") or "0"
    return (report.get("receipt_date") or "", int(identifier),
            str(report.get("beginning_image_number") or ""),
            str(report.get("committee_id") or ""))


def output_paths(office):
    """Return (flagged, general, review) CSV paths for an office."""
    name = OFFICE_NAMES[office]
    return (DATA_DIR / f"fec-{name}-candidates-flagged.csv",
            DATA_DIR / f"fec-{name}-general.csv", DATA_DIR / REVIEW_FILES[office])


def fetch_12g_reports(session, office="H"):
    """Return the latest 12G report per committee of the office, keyed by committee_id."""
    reports = fetch_all(
        session,
        "/reports/house-senate/",
        {
            "cycle": CYCLE,
            "report_type": "12G",
            "committee_type": office,
            # Must be unique: offset paging on a tied key skips rows.
            "sort": "beginning_image_number",
        },
    )
    latest = {}
    for r in reports:
        cid = r["committee_id"]
        if cid not in latest or report_order(r) > report_order(latest[cid]):
            latest[cid] = r
    return latest


def fetch_principal_committees(session, office="H"):
    """Return every candidate ID linked to each principal committee."""
    candidates = fetch_all(
        session,
        "/candidates/search/",
        {"office": office, "election_year": CYCLE, "sort": "candidate_id"},
    )
    mapping = defaultdict(set)
    for c in candidates:
        for comm in c.get("principal_committees") or []:
            mapping[comm["committee_id"]].add(c["candidate_id"])
    return mapping


def attribute_reports(session, reports, committee_links, office_ids):
    """Attribute the latest report to all in-scope linked candidate IDs."""
    report_by_candidate = {}
    unmatched = []
    for cid, report in sorted(reports.items()):
        linked = set(committee_links.get(cid, set())) & office_ids
        if not linked:
            data = get_json(session, f"/committee/{cid}/", {})
            linked = {candidate_id for row in data["results"]
                      for candidate_id in (row.get("candidate_ids") or [])} & office_ids
        if not linked:
            unmatched.append(report.get("committee_name", cid))
        for candidate_id in sorted(linked):
            previous = report_by_candidate.get(candidate_id)
            if previous is None or report_order(report) > report_order(previous):
                report_by_candidate[candidate_id] = report
    return report_by_candidate, sorted(unmatched)


def review_reason(state, cands):
    """Return why a district's 12G filers need a manual check, or None."""
    dems = sum(1 for c in cands if c["party"] in DEM_PARTIES)
    reps = sum(1 for c in cands if c["party"] == "REP")
    if state == "LA":
        return "Louisiana primary/runoff calendar"
    if not cands:
        return "no 12G filers"
    if state in TOP_TWO_STATES:
        # Any two finalists are valid in a top-two state, including D vs. D.
        if len(cands) == 2:
            return None
        return f"top-two state with {len(cands)} 12G filers"
    if dems > 1 or reps > 1:
        return f"multiple same-party filers ({dems}D, {reps}R)"
    if dems == 0 or reps == 0:
        return f"one major party only ({dems}D, {reps}R)"
    return None


def write_csv(path, rows, fields):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Flag FEC candidates who filed a 12G report.")
    parser.add_argument("--office", choices=sorted(OFFICE_NAMES), default="H",
                        help="FEC office code: H for House (default) or S for Senate")
    args = parser.parse_args()
    in_path = candidates_path(args.office)
    if not in_path.exists():
        sys.exit(f"{in_path} not found; run fetch_fec_house_candidates.py first")
    with in_path.open(newline="") as f:
        candidates = list(csv.DictReader(f))
    base_fields = list(candidates[0].keys())

    api_key = load_api_key()
    if api_key == "DEMO_KEY":
        sys.exit("Set FEC_API_KEY in the environment or .env")
    session = requests.Session()
    session.params = {"api_key": api_key}

    print("Fetching 12G reports", file=sys.stderr)
    reports = fetch_12g_reports(session, args.office)
    print("Fetching principal committees", file=sys.stderr)
    committee_to_candidate = fetch_principal_committees(session, args.office)

    office_ids = {c["candidate_id"] for c in candidates}
    report_by_candidate, unmatched = attribute_reports(
        session, reports, committee_to_candidate, office_ids
    )
    if unmatched:
        print(
            f"{len(unmatched)} 12G committees not matched to a 2026 {OFFICE_NAMES[args.office].title()} "
            f"candidate: {', '.join(sorted(unmatched))}",
            file=sys.stderr,
        )

    by_district = defaultdict(list)
    for c in candidates:
        r = report_by_candidate.get(c["candidate_id"])
        c["filed_12g"] = r is not None
        c["pre_general_receipts"] = r["total_receipts_ytd"] if r else ""
        c["pre_general_cash_on_hand"] = r["cash_on_hand_end_period"] if r else ""
        c["pre_general_coverage_end"] = r["coverage_end_date"][:10] if r else ""
        # Skip records with no district code; they are not real seats.
        if not c["district"]:
            continue
        district = by_district[(c["state"], c["district"])]
        if r:
            district.append(c)

    fields = base_fields + FLAG_FIELDS
    general = [c for c in candidates if c["filed_12g"]]
    flagged_path, general_path, review_path = output_paths(args.office)
    write_csv(flagged_path, candidates, fields)
    write_csv(general_path, general, fields)

    review = []
    for (state, district), cands in sorted(by_district.items()):
        reason = review_reason(state, cands)
        if reason:
            review.append(
                {
                    "state": state,
                    "district": district,
                    "reason": reason,
                    "filers_12g": "; ".join(
                        f"{c['name']} ({c['party']})" for c in cands
                    ),
                }
            )
    write_csv(
        review_path,
        review,
        ["state", "district", "reason", "filers_12g"],
    )


if __name__ == "__main__":
    main()
