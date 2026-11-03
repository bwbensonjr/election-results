# /// script
# requires-python = ">=3.11"
# ///
"""Build the House field and review reports from committed inputs, offline.

Run from the repository root: uv run scripts/build_house_field.py
See docs/candidate-pipeline.md for schemas, decisions, and refresh instructions.
"""

import csv
import os
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from candidate_identity import (
    Resolution, load_decisions, name_parts, party_code, resolve,
)

DATA_DIR = Path("2026/candidates")
POLLS_PATH = Path("2026/polls/us-house-polls.csv")
POLLS_AFTER = date(2026, 9, 1)
FIELD_COLUMNS = [
    "state", "district", "name", "party", "party_raw", "fec_candidate_id",
    "fec_name", "incumbent", "filed_12g", "receipts", "cash_on_hand_end_period",
    "in_general_polls", "source_url", "fec_match_status", "fec_match_reason",
    "fec_alternate_ids",
]
REVIEW_COLUMNS = [
    "state", "district", "ballot_name", "ballot_party", "fec_match_status",
    "fec_match_reason", "fec_candidate_id", "fec_name", "fec_party", "incumbent",
    "filed_12g", "receipts", "cash_on_hand_end_period", "coverage_end_date",
    "decision_evidence",
]


def normalize_party(party):
    code = party_code(party)
    return code if code in {"DEM", "REP"} else ("OTHER" if party.strip() else "")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def poll_district(row):
    number = row["seat_number"].strip()
    return number.zfill(2) if number else None


def poll_end(row):
    return datetime.strptime(row["end_date"], "%m/%d/%y").date()


def poll_candidates(name, ballot):
    """Poll evidence can use a unique surname; it never selects FEC IDs."""
    given, surname = name_parts(name)
    hits = [b for b in ballot if surname and surname == name_parts(b["name"])[1]]
    if len(hits) > 1:
        stronger = [b for b in hits if given and name_parts(b["name"])[0]
                    and given[0] == name_parts(b["name"])[0][0]]
        if stronger:
            hits = stronger
    return sorted(hits, key=lambda b: (b["name"], b["party"]))


def resolve_rows(rows, records, decisions):
    """Resolve one race's ballot rows, keeping each accepted FEC ID with one identity."""
    resolutions = [(b, resolve(b, records, decisions)) for b in rows]
    owners = defaultdict(list)
    for index, (_, resolution) in enumerate(resolutions):
        for cid in resolution.member_ids:
            owners[cid].append(index)
    for cid, indices in owners.items():
        if len(indices) > 1:
            # A reviewed decision reserves its IDs; automatic competitors
            # remain unresolved instead of duplicating the accepted identity.
            for index in indices:
                b, result = resolutions[index]
                if result.status == "automatic":
                    resolutions[index] = (b, Resolution(
                        "ambiguous", f"FEC ID {cid} also fits another ballot identity; review required",
                        result.candidates))
    return resolutions


def publish_csvs(data_dir, outputs):
    """Stage every CSV before replacement; validation happens before this call."""
    staged = []
    try:
        for name, columns, rows in outputs:
            with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8",
                                             dir=data_dir, delete=False) as stream:
                staged.append((Path(stream.name), data_dir / name))
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def build(data_dir=DATA_DIR, polls_path=POLLS_PATH):
    ballot = read_csv(data_dir / "ballotbrief-house-candidates.csv")
    fec = read_csv(data_dir / "fec-house-candidates-flagged.csv")
    polls = read_csv(polls_path)
    decisions = load_decisions(data_dir / "candidate-identity-decisions.json", ballot, fec)
    ballot_by_district = defaultdict(list)
    fec_by_district = defaultdict(list)
    for row in ballot:
        ballot_by_district[(row["state"], row["district"])].append(row)
    for row in fec:
        fec_by_district[(row["state"], row["district"])].append(row)
    at_large = {state for state in {b["state"] for b in ballot}
                if {b["district"] for b in ballot if b["state"] == state} == {"00"}}
    poll_names = defaultdict(set)
    for poll in polls:
        district = "00" if poll["state"] in at_large else poll_district(poll)
        if (poll["cycle"] == "2026" and poll["stage"] == "general" and district
                and poll["party"] not in {"NONE", "ALL"}
                and not poll["candidate_name"].startswith("Generic")
                and poll_end(poll) >= POLLS_AFTER):
            poll_names[(poll["state"], district)].add(poll["candidate_name"])

    field, review, discrepancies = [], [], []
    accepted_ids = set()
    plausible_ids = set()
    for key, rows in sorted(ballot_by_district.items()):
        polled, ambiguous_polls = set(), set()
        for name in sorted(poll_names[key]):
            hits = poll_candidates(name, rows)
            if len(hits) == 1:
                polled.add(hits[0]["name"])
            elif len(hits) > 1:
                ambiguous_polls.update(b["name"] for b in hits)
                discrepancies.append((*key, name, "ambiguous poll-to-ballot association"))
            else:
                discrepancies.append((*key, name, "in general polls but not on ballot list"))
        for b, result in resolve_rows(rows, fec_by_district[key], decisions):
            f = result.canonical
            accepted_ids.update(result.member_ids)
            plausible_ids.update(c["candidate_id"] for c in result.candidates)
            in_polls = True if b["name"] in polled else ("" if b["name"] in ambiguous_polls else False)
            party = normalize_party(b["party"])
            field.append(dict(
                state=b["state"], district=b["district"], name=b["name"], party=party,
                party_raw=b["party"], fec_candidate_id=f["candidate_id"] if f else "",
                fec_name=f["name"] if f else "",
                incumbent=f["incumbent_challenge"] == "I" if f else "",
                filed_12g=result.filed_12g, receipts=f["receipts"] if f else "",
                cash_on_hand_end_period=f["cash_on_hand_end_period"] if f else "",
                in_general_polls=in_polls, source_url=b["source_url"],
                fec_match_status=result.status, fec_match_reason=result.reason,
                fec_alternate_ids=";".join(result.alternates),
            ))
            if result.status in {"unmatched", "ambiguous", "reviewed_unmatched"}:
                for candidate in result.candidates or [{}]:
                    review.append(dict(
                        state=b["state"], district=b["district"], ballot_name=b["name"],
                        ballot_party=b["party"], fec_match_status=result.status,
                        fec_match_reason=result.reason,
                        fec_candidate_id=candidate.get("candidate_id", ""),
                        fec_name=candidate.get("name", ""), fec_party=candidate.get("party", ""),
                        incumbent=(candidate["incumbent_challenge"] == "I") if candidate else "",
                        filed_12g=candidate.get("filed_12g", ""),
                        receipts=candidate.get("receipts", ""),
                        cash_on_hand_end_period=candidate.get("cash_on_hand_end_period", ""),
                        coverage_end_date=candidate.get("coverage_end_date", ""),
                        decision_evidence=";".join(result.evidence),
                    ))
            if not f and party in {"DEM", "REP"}:
                discrepancies.append((*key, b["name"], f"major-party FEC identity {result.status}"))
        parties = {normalize_party(b["party"]) for b in rows}
        if not {"DEM", "REP"} <= parties:
            missing = ", ".join(sorted({"DEM", "REP"} - parties))
            discrepancies.append((*key, "", f"no {missing} candidate on ballot list"))
    for row in fec:
        if row["filed_12g"] == "True" and row["candidate_id"] not in accepted_ids:
            issue = ("filed 12G with unresolved ballot identity" if row["candidate_id"] in plausible_ids
                     else "filed 12G but not on ballot list")
            discrepancies.append((row["state"], row["district"], row["name"], issue))
    for key in sorted(set(poll_names) - set(ballot_by_district)):
        for name in sorted(poll_names[key]):
            discrepancies.append((*key, name, "in general polls but not on ballot list"))
    field.sort(key=lambda r: (r["state"], r["district"], r["party"], r["name"]))
    review.sort(key=lambda r: (r["state"], r["district"], r["ballot_name"], r["fec_candidate_id"]))
    discrepancy_columns = ["state", "district", "candidate", "issue"]
    discrepancy_rows = [dict(zip(discrepancy_columns, row)) for row in sorted(discrepancies)]
    publish_csvs(data_dir, [
        ("house-general-field.csv", FIELD_COLUMNS, field),
        ("field-discrepancies.csv", discrepancy_columns, discrepancy_rows),
        ("candidate-match-review.csv", REVIEW_COLUMNS, review),
    ])
    return field, review, discrepancy_rows


def main():
    try:
        field, review, discrepancies = build(DATA_DIR, POLLS_PATH)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Build failed: {exc}")
    print(f"Wrote {len(field)} candidates, {len(review)} review rows, "
          f"{len(discrepancies)} discrepancies", file=sys.stderr)


if __name__ == "__main__":
    main()
