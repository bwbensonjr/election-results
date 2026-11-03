# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Download 2026 U.S. Senate and governor general-election candidates from The Ballot Brief.

The Ballot Brief is a secondary source for November candidates. Its list
pages truncate races with many candidates ("and 2 more"), so those races
are read from the state page's contest instead. robots.txt asks for a 0.5s
crawl delay.

Usage:
    uv run scripts/fetch_ballotbrief_statewide.py [--out PATH]
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://theballotbrief.com"
CRAWL_DELAY = 0.5
# Office -> (list page, element ID of the contest on a state page)
OFFICES = {
    "Senate": ("/candidates/us-senate", "race-u-s-senate"),
    "Governor": ("/candidates/governor", "race-governor"),
}
STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new-hampshire": "NH",
    "new-jersey": "NJ", "new-mexico": "NM", "new-york": "NY", "north-carolina": "NC",
    "north-dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode-island": "RI", "south-carolina": "SC", "south-dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west-virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_RE = re.compile(r"^/state/([a-z-]+)$")
CANDIDATE_RE = re.compile(r"^(.*) \(([^()]*)\)$")
MORE_RE = re.compile(r"\s+and \d+ more$")
# Some rows end with a note that the state hub lists other contests.
CONTESTS_RE = re.compile(r"\s*\(\+\d+ more contests?\)$")
COLUMNS = ["state", "office", "name", "party", "source_url"]


def parse_list_page(html):
    """Return (state, href, candidates, truncated) for each race on an office list page."""
    soup = BeautifulSoup(html, "html.parser")
    races = []
    for item in soup.find_all("li"):
        link = item.find("a", href=STATE_RE)
        names_span = item.find("span")
        if link is None or names_span is None:
            continue
        slug = STATE_RE.match(link["href"])[1]
        if slug not in STATE_CODES:
            raise ValueError(f"unknown state slug {slug!r}")
        text = CONTESTS_RE.sub("", names_span.get_text(" ", strip=True))
        truncated = bool(MORE_RE.search(text))
        text = MORE_RE.sub("", text)
        candidates = []
        # Split on ", " only after a closing paren so names with commas survive.
        for entry in re.split(r"(?<=\)), ", text):
            m = CANDIDATE_RE.match(entry.strip())
            if m:
                candidates.append((m.group(1).strip(), m.group(2).strip()))
        races.append((STATE_CODES[slug], link["href"], candidates, truncated))
    return races


def parse_state_page(html, contest_id):
    """Return (name, party) for every candidate card in one contest on a state page."""
    soup = BeautifulSoup(html, "html.parser")
    contest = soup.find("details", id=contest_id)
    if contest is None:
        return []
    candidates = []
    for card in contest.find_all(class_="bl-cand"):
        name = card.find(class_="bl-name")
        party = card.find(class_="bl-party")
        if name:
            candidates.append(
                (name.get_text(strip=True), party.get_text(strip=True) if party else "")
            )
    return candidates


def main():
    parser = argparse.ArgumentParser(
        description="Download 2026 U.S. Senate and governor candidates from The Ballot Brief."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("2026/candidates/ballotbrief-statewide-candidates.csv"),
        help="Output CSV path",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "election-results research script"

    rows = []
    for office, (list_path, contest_id) in OFFICES.items():
        resp = session.get(BASE_URL + list_path, timeout=60)
        resp.raise_for_status()
        races = parse_list_page(resp.text)
        print(f"Found {len(races)} {office} races", file=sys.stderr)
        for state, href, candidates, truncated in races:
            if truncated:
                time.sleep(CRAWL_DELAY)
                print(f"  fetching {href} ({office})", file=sys.stderr)
                r = session.get(BASE_URL + href, timeout=60)
                r.raise_for_status()
                full = parse_state_page(r.text, contest_id)
                if len(full) > len(candidates):
                    candidates = full
                else:
                    print(f"  warning: {href} gave no more candidates", file=sys.stderr)
            for name, party in candidates:
                rows.append(
                    {
                        "state": state,
                        "office": office,
                        "name": name,
                        "party": party,
                        "source_url": BASE_URL + href,
                    }
                )
        time.sleep(CRAWL_DELAY)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} candidates to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
