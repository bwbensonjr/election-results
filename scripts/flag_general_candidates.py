# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Flag 2026 House candidates who filed an FEC pre-general (12G) report.

Only campaigns participating in the general election file the 12G report,
so it separates November candidates from primary losers.

Usage:
    uv run scripts/flag_general_candidates.py

Reads 2026/candidates/fec-house-candidates.csv (from
fetch_fec_house_candidates.py) and writes, in the same directory:
    fec-house-candidates-flagged.csv  every candidate plus 12G columns
    fec-house-general.csv             only candidates who filed a 12G
    review-districts.csv              districts without a clean D vs. R field
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

import requests

from fetch_fec_house_candidates import CYCLE, fetch_all, get_json, load_api_key

DATA_DIR = Path("2026/candidates")
TOP_TWO_STATES = {"CA", "WA"}
DEM_PARTIES = {"DEM", "DFL"}

FLAG_FIELDS = [
    "filed_12g",
    "pre_general_receipts",
    "pre_general_cash_on_hand",
    "pre_general_coverage_end",
]


def fetch_12g_reports(session):
    """Return the latest 12G report per House committee, keyed by committee_id."""
    reports = fetch_all(
        session,
        "/reports/house-senate/",
        {
            "cycle": CYCLE,
            "report_type": "12G",
            "committee_type": "H",
            # Must be unique: offset paging on a tied key skips rows.
            "sort": "beginning_image_number",
        },
    )
    latest = {}
    for r in reports:
        cid = r["committee_id"]
        if cid not in latest or r["receipt_date"] > latest[cid]["receipt_date"]:
            latest[cid] = r
    return latest


def fetch_principal_committees(session):
    """Return a map of committee_id to candidate_id for House candidates."""
    candidates = fetch_all(
        session,
        "/candidates/search/",
        {"office": "H", "election_year": CYCLE, "sort": "candidate_id"},
    )
    mapping = {}
    for c in candidates:
        for comm in c.get("principal_committees") or []:
            mapping[comm["committee_id"]] = c["candidate_id"]
    return mapping


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
    in_path = DATA_DIR / "fec-house-candidates.csv"
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
    reports = fetch_12g_reports(session)
    print("Fetching principal committees", file=sys.stderr)
    committee_to_candidate = fetch_principal_committees(session)

    house_ids = {c["candidate_id"] for c in candidates}
    report_by_candidate = {}
    unmatched = []
    for cid, r in reports.items():
        cand_id = committee_to_candidate.get(cid)
        if not cand_id:
            # Committee may be linked to a candidate record from another
            # cycle; ask the committee endpoint directly.
            data = get_json(session, f"/committee/{cid}/", {})
            linked = data["results"][0].get("candidate_ids") or [] if data["results"] else []
            cand_id = next((x for x in linked if x in house_ids), None)
        if cand_id:
            report_by_candidate[cand_id] = r
        else:
            unmatched.append(r["committee_name"])
    if unmatched:
        print(
            f"{len(unmatched)} 12G committees not matched to a 2026 House "
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
    write_csv(DATA_DIR / "fec-house-candidates-flagged.csv", candidates, fields)
    write_csv(DATA_DIR / "fec-house-general.csv", general, fields)

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
        DATA_DIR / "review-districts.csv",
        review,
        ["state", "district", "reason", "filers_12g"],
    )


if __name__ == "__main__":
    main()
