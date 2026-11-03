# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Download 2026 U.S. House or Senate candidates from the FEC API to CSV.

Usage:
    FEC_API_KEY=... uv run scripts/fetch_fec_house_candidates.py [--office {H,S}] [--totals] [--out PATH]

Get a free key at https://api.data.gov/signup/. Without one, DEMO_KEY is
used, which has a very low hourly rate limit.

The FEC list includes everyone who filed a statement of candidacy, not just
candidates on the general election ballot. Use the has_raised_funds,
candidate_inactive, and (with --totals) receipts columns to filter.
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests

API_BASE = "https://api.open.fec.gov/v1"
PER_PAGE = 100
CYCLE = 2026
DATA_DIR = Path("2026/candidates")
OFFICE_NAMES = {"H": "house", "S": "senate"}

CANDIDATE_FIELDS = [
    "candidate_id",
    "name",
    "party",
    "party_full",
    "state",
    "district",
    "district_number",
    "incumbent_challenge",
    "incumbent_challenge_full",
    "candidate_status",
    "candidate_inactive",
    "has_raised_funds",
    "first_file_date",
    "last_file_date",
]

TOTALS_FIELDS = [
    "receipts",
    "disbursements",
    "cash_on_hand_end_period",
    "coverage_end_date",
]


def candidates_path(office):
    """Default raw candidate CSV for an office; House keeps its original path."""
    return DATA_DIR / f"fec-{OFFICE_NAMES[office]}-candidates.csv"


def load_api_key():
    """Return FEC_API_KEY from the environment or a .env file, else DEMO_KEY."""
    if key := os.environ.get("FEC_API_KEY"):
        return key
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "FEC_API_KEY" and value.strip():
                return value.strip().strip("\"'")
    return "DEMO_KEY"


def get_json(session, path, params, max_retries=6):
    """GET an API path, retrying with backoff on rate limits and server errors."""
    delay = 5
    for _ in range(max_retries):
        resp = session.get(f"{API_BASE}{path}", params=params, timeout=60)
        retry_after = int(resp.headers.get("retry-after", "0") or 0)
        if resp.status_code == 429 and retry_after > 300:
            sys.exit(
                f"Rate limit exhausted (retry after {retry_after // 60} min). "
                "Set FEC_API_KEY to a key from https://api.data.gov/signup/"
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            print(f"  HTTP {resp.status_code}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Giving up on {path} after {max_retries} attempts")


def fetch_all(session, path, params):
    """Fetch every page of a paginated FEC endpoint."""
    results = []
    page = 1
    while True:
        data = get_json(session, path, {**params, "page": page, "per_page": PER_PAGE})
        results.extend(data["results"])
        pages = data["pagination"]["pages"]
        print(f"  {path} page {page}/{pages}", file=sys.stderr)
        if page >= pages:
            return results
        page += 1


def main():
    parser = argparse.ArgumentParser(
        description="Download 2026 U.S. House or Senate candidates from the FEC API to CSV."
    )
    parser.add_argument(
        "--office",
        choices=sorted(OFFICE_NAMES),
        default="H",
        help="FEC office code: H for House (default) or S for Senate",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output CSV path (default: 2026/candidates/fec-<office>-candidates.csv)",
    )
    parser.add_argument(
        "--totals",
        action="store_true",
        help="Also fetch 2026 cycle financial totals (receipts, cash on hand)",
    )
    args = parser.parse_args()
    out = args.out or candidates_path(args.office)

    api_key = load_api_key()
    if api_key == "DEMO_KEY":
        print("FEC_API_KEY not set; using DEMO_KEY (low rate limit)", file=sys.stderr)

    session = requests.Session()
    session.params = {"api_key": api_key}

    print("Fetching candidates", file=sys.stderr)
    candidates = fetch_all(
        session,
        "/candidates/",
        {"office": args.office, "election_year": CYCLE, "sort": "candidate_id"},
    )

    fields = list(CANDIDATE_FIELDS)
    if args.totals:
        print("Fetching candidate totals", file=sys.stderr)
        totals = fetch_all(
            session,
            "/candidates/totals/",
            {"office": args.office, "election_year": CYCLE, "cycle": CYCLE, "sort": "candidate_id"},
        )
        by_id = {t["candidate_id"]: t for t in totals}
        for c in candidates:
            t = by_id.get(c["candidate_id"], {})
            for f in TOTALS_FIELDS:
                c[f] = t.get(f)
        fields += TOTALS_FIELDS

    candidates.sort(key=lambda c: (c["state"], c["district"] or "", c["name"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)

    print(f"Wrote {len(candidates)} candidates to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
