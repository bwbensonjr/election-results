# /// script
# requires-python = ">=3.11"
# ///
"""Build the 2026 U.S. House general-election field from all sources.

Joins The Ballot Brief's certified candidate lists (who is on the ballot)
with FEC data (incumbency, money, 12G filing) and the general-election polls
(which candidates pollsters tested). Matching is by state, district, and
normalized last name.

Usage:
    uv run scripts/build_house_field.py

Inputs (in 2026/candidates unless noted):
    ballotbrief-house-candidates.csv  from fetch_ballotbrief_house.py
    fec-house-candidates-flagged.csv  from flag_general_candidates.py
    2026/polls/us-house-polls.csv
Outputs:
    house-general-field.csv  one row per ballot candidate with FEC/poll data
    field-discrepancies.csv  disagreements between the sources to check
"""

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path("2026/candidates")
POLLS_PATH = Path("2026/polls/us-house-polls.csv")
POLLS_AFTER = date(2026, 9, 1)

PARTY_MAP = {
    "republican": "REP",
    "r": "REP",
    "prefers republican party": "REP",
    "democratic": "DEM",
    "democrat": "DEM",
    "d": "DEM",
    "prefers democratic party": "DEM",
    "democratic-farmer-labor": "DEM",
    "dfl": "DEM",
}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "mr", "mrs", "ms", "dr"}

FIELD_COLUMNS = [
    "state",
    "district",
    "name",
    "party",
    "party_raw",
    "fec_candidate_id",
    "fec_name",
    "incumbent",
    "filed_12g",
    "receipts",
    "cash_on_hand_end_period",
    "in_general_polls",
    "source_url",
]


def normalize_party(party):
    return PARTY_MAP.get(party.strip().lower(), "OTHER" if party.strip() else "")


def fold(text):
    """Lowercase and strip accents and punctuation."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", " ", text.lower())


def last_name(name):
    """Return the last name token, handling "LAST, FIRST" and suffixes."""
    if "," in name:
        name = name.split(",")[0]
    tokens = [t for t in fold(name).split() if t not in SUFFIXES]
    return tokens[-1] if tokens else ""


def name_tokens(name):
    return {t for t in fold(name.replace(",", " ")).split() if t not in SUFFIXES}


def match(name, candidates, name_of):
    """Find the candidate in a district whose name matches, or None."""
    last = last_name(name)
    hits = [c for c in candidates if last and last in name_tokens(name_of(c))]
    if len(hits) > 1:
        # Disambiguate on first-name overlap too.
        tokens = name_tokens(name)
        best = [c for c in hits if len(tokens & name_tokens(name_of(c))) > 1]
        hits = best or hits
    return hits[0] if hits else None


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def poll_district(row):
    """Return the FEC-style district for a poll row, or None."""
    number = row["seat_number"].strip()
    if not number:
        return None
    return "00" if number == "0" else number.zfill(2)


def poll_end(row):
    """Parse a poll end_date like "9/21/26" into a date."""
    return datetime.strptime(row["end_date"], "%m/%d/%y").date()


def main():
    ballot = read_csv(DATA_DIR / "ballotbrief-house-candidates.csv")
    fec = read_csv(DATA_DIR / "fec-house-candidates-flagged.csv")
    polls = read_csv(POLLS_PATH)

    fec_by_district = defaultdict(list)
    for c in fec:
        fec_by_district[(c["state"], c["district"])].append(c)

    # Candidates named in 2026 general-election polls, by district.
    # Polls number at-large seats as 1; the other sources use 00.
    at_large = {
        s for s in {b["state"] for b in ballot}
        if {b["district"] for b in ballot if b["state"] == s} == {"00"}
    }
    poll_names = defaultdict(set)
    for p in polls:
        district = poll_district(p)
        if p["state"] in at_large:
            district = "00"
        # NONE/ALL rows are "Don't know", "Someone else", and similar.
        # Earlier general-election polls test hypothetical pre-primary
        # matchups, so only polls ending after the primaries count.
        if (
            p["cycle"] == "2026"
            and p["stage"] == "general"
            and district
            and p["party"] not in {"NONE", "ALL"}
            and not p["candidate_name"].startswith("Generic")
            and poll_end(p) >= POLLS_AFTER
        ):
            poll_names[(p["state"], district)].add(p["candidate_name"])

    field = []
    discrepancies = []
    ballot_by_district = defaultdict(list)
    for b in ballot:
        key = (b["state"], b["district"])
        ballot_by_district[key].append(b)
        f = match(b["name"], fec_by_district[key], lambda c: c["name"])
        in_polls = match(b["name"], list(poll_names[key]), lambda n: n) is not None
        party = normalize_party(b["party"])
        field.append(
            {
                "state": b["state"],
                "district": b["district"],
                "name": b["name"],
                "party": party,
                "party_raw": b["party"],
                "fec_candidate_id": f["candidate_id"] if f else "",
                "fec_name": f["name"] if f else "",
                "incumbent": f["incumbent_challenge"] == "I" if f else "",
                "filed_12g": f["filed_12g"] if f else "",
                "receipts": f["receipts"] if f else "",
                "cash_on_hand_end_period": f["cash_on_hand_end_period"] if f else "",
                "in_general_polls": in_polls,
                "source_url": b["source_url"],
            }
        )
        if party in {"DEM", "REP"} and not f:
            discrepancies.append(
                (key, b["name"], "major-party ballot candidate not found in FEC data")
            )

    # 12G filers who are not on the ballot list.
    for key, cands in fec_by_district.items():
        on_ballot = ballot_by_district.get(key, [])
        for c in cands:
            if c["filed_12g"] == "True" and not match(c["name"], on_ballot, lambda b: b["name"]):
                discrepancies.append((key, c["name"], "filed 12G but not on ballot list"))

    # Polled general-election candidates who are not on the ballot list.
    for key, names in poll_names.items():
        on_ballot = ballot_by_district.get(key, [])
        for n in sorted(names):
            if not match(n, on_ballot, lambda b: b["name"]):
                discrepancies.append((key, n, "in general polls but not on ballot list"))

    # Districts lacking either major party on the ballot.
    for key, cands in sorted(ballot_by_district.items()):
        parties = {normalize_party(c["party"]) for c in cands}
        if not {"DEM", "REP"} <= parties:
            missing = ", ".join(sorted({"DEM", "REP"} - parties))
            discrepancies.append((key, "", f"no {missing} candidate on ballot list"))

    field.sort(key=lambda r: (r["state"], r["district"], r["party"], r["name"]))
    with (DATA_DIR / "house-general-field.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_COLUMNS)
        writer.writeheader()
        writer.writerows(field)

    discrepancies.sort()
    with (DATA_DIR / "field-discrepancies.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["state", "district", "candidate", "issue"])
        for (state, district), name, issue in discrepancies:
            writer.writerow([state, district, name, issue])

    print(f"Wrote {len(field)} candidates to house-general-field.csv", file=sys.stderr)
    print(f"Wrote {len(discrepancies)} rows to field-discrepancies.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
