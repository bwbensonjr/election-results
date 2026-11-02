# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Download 2026 U.S. House general-election candidates from The Ballot Brief.

The Ballot Brief is a secondary source for November candidates. Its list
page truncates races with many candidates ("and 2 more"), so those districts
are fetched individually. robots.txt asks for a 0.5s crawl delay.

Usage:
    uv run scripts/fetch_ballotbrief_house.py [--out PATH]
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
LIST_PATH = "/candidates/us-house"
CRAWL_DELAY = 0.5
DISTRICT_RE = re.compile(r"^/district/([a-z]{2})-(al|\d+)$")
CANDIDATE_RE = re.compile(r"^(.*) \(([^()]*)\)$")
MORE_RE = re.compile(r"\s+and \d+ more$")


def district_code(slug_district):
    """Convert a Ballot Brief district slug ("al", "4") to FEC style ("00", "04")."""
    return "00" if slug_district == "al" else slug_district.zfill(2)


def parse_list_page(html):
    """Return (state, district, href, candidates, truncated) for each House race."""
    soup = BeautifulSoup(html, "html.parser")
    races = []
    for link in soup.find_all("a", href=DISTRICT_RE):
        if not link.get_text().startswith("U.S. House"):
            continue
        state, dist = DISTRICT_RE.match(link["href"]).groups()
        names_span = link.find_next_sibling("span")
        text = names_span.get_text(" ", strip=True) if names_span else ""
        truncated = bool(MORE_RE.search(text))
        text = MORE_RE.sub("", text)
        candidates = []
        # Split on ", " only after a closing paren so names with commas survive.
        for item in re.split(r"(?<=\)), ", text):
            m = CANDIDATE_RE.match(item.strip())
            if m:
                candidates.append((m.group(1).strip(), m.group(2).strip()))
        races.append((state.upper(), district_code(dist), link["href"], candidates, truncated))
    return races


def parse_district_page(html):
    """Return (name, party) for every candidate card on a district page."""
    soup = BeautifulSoup(html, "html.parser")
    group = soup.find(class_="bl-district-cands")
    if group is None:
        return []
    candidates = []
    for card in group.find_all(class_="bl-cand"):
        name = card.find(class_="bl-name")
        party = card.find(class_="bl-party")
        if name:
            candidates.append(
                (name.get_text(strip=True), party.get_text(strip=True) if party else "")
            )
    return candidates


def main():
    parser = argparse.ArgumentParser(
        description="Download 2026 U.S. House candidates from The Ballot Brief."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("2026/candidates/ballotbrief-house-candidates.csv"),
        help="Output CSV path",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "election-results research script"

    resp = session.get(BASE_URL + LIST_PATH, timeout=60)
    resp.raise_for_status()
    races = parse_list_page(resp.text)
    print(f"Found {len(races)} House races", file=sys.stderr)

    rows = []
    for state, district, href, candidates, truncated in races:
        if truncated:
            time.sleep(CRAWL_DELAY)
            print(f"  fetching {href}", file=sys.stderr)
            r = session.get(BASE_URL + href, timeout=60)
            r.raise_for_status()
            full = parse_district_page(r.text)
            if len(full) > len(candidates):
                candidates = full
            else:
                print(f"  warning: {href} gave no more candidates", file=sys.stderr)
        for name, party in candidates:
            rows.append(
                {
                    "state": state,
                    "district": district,
                    "name": name,
                    "party": party,
                    "source_url": BASE_URL + href,
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["state", "district", "name", "party", "source_url"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} candidates to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
