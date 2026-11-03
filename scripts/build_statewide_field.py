# /// script
# requires-python = ">=3.11"
# ///
"""Build the 2026 Senate and governor field and review reports from committed inputs, offline.

Run from the repository root: uv run scripts/build_statewide_field.py
See docs/candidate-pipeline.md for schemas, decisions, and refresh instructions.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from build_house_field import (
    POLLS_AFTER, normalize_party, poll_candidates, poll_end, publish_csvs, read_csv, resolve_rows,
)
from candidate_identity import OFFICE_ID_PREFIXES, load_decisions
from district_history import STATES

DATA_DIR = Path("2026/candidates")
POLL_PATHS = {
    "Senate": Path("2026/polls/us-senate-polls.csv"),
    "Governor": Path("2026/polls/governor-polls.csv"),
}
OFFICE_CODES = {"Senate": "SEN", "Governor": "GOV"}
BALLOT_COLUMNS = ["state", "office", "name", "party", "source_url"]
FIELD_COLUMNS = [
    "state", "office", "race_id", "name", "party", "party_raw", "fec_candidate_id",
    "fec_name", "incumbent", "filed_12g", "receipts", "cash_on_hand_end_period",
    "in_general_polls", "source_url", "fec_match_status", "fec_match_reason",
    "fec_alternate_ids",
]
REVIEW_COLUMNS = [
    "state", "office", "race_id", "ballot_name", "ballot_party", "fec_match_status",
    "fec_match_reason", "fec_candidate_id", "fec_name", "fec_party", "incumbent",
    "filed_12g", "receipts", "cash_on_hand_end_period", "coverage_end_date",
    "decision_evidence",
]
DISCREPANCY_COLUMNS = ["state", "office", "race_id", "candidate", "issue"]
UNRESOLVED = {"unmatched", "ambiguous", "reviewed_unmatched"}


def race_id(state, office):
    return f"{state}-{OFFICE_CODES[office]}"


def load_ballot(path):
    """Read the statewide ballot list and group it by (state, office), validating one race each."""
    rows = read_csv(path)
    if rows and list(rows[0]) != BALLOT_COLUMNS:
        raise ValueError(f"{path}: expected columns {BALLOT_COLUMNS}, got {list(rows[0])}")
    races, seen = defaultdict(list), set()
    for line, row in enumerate(rows, 2):
        location = f"{path} row {line}"
        if row["office"] not in OFFICE_CODES:
            raise ValueError(f"{location}: invalid office {row['office']!r}")
        if row["state"] not in STATES:
            raise ValueError(f"{location}: invalid state {row['state']!r}")
        if not row["name"].strip():
            raise ValueError(f"{location}: blank candidate name")
        # The list holds one entry per state and office; a repeated candidate means two
        # contests were flattened together, so the race cannot be identified.
        key = (row["state"], row["office"], row["name"])
        if key in seen:
            raise ValueError(f"{location}: {row['state']} lists {row['name']} twice for {row['office']}; "
                             "two races in one state cannot be told apart")
        seen.add(key)
        races[(row["state"], row["office"])].append(dict(row, district="00"))
    return races


def poll_names(polls_path):
    """Return qualifying candidate names from an office's general-election polls, by state."""
    names = defaultdict(set)
    for poll in read_csv(polls_path):
        if (poll["cycle"] == "2026" and poll["stage"] == "general"
                and poll["party"] not in {"NONE", "ALL"}
                and not poll["candidate_name"].startswith("Generic")
                and poll_end(poll) >= POLLS_AFTER):
            names[poll["state"]].add(poll["candidate_name"])
    return names


def build(data_dir=DATA_DIR, poll_paths=None):
    poll_paths = poll_paths or POLL_PATHS
    races = load_ballot(data_dir / "ballotbrief-statewide-candidates.csv")
    # Senate records are statewide; some FEC rows carry a blank district instead of 00.
    fec = [dict(row, district="00") for row in read_csv(data_dir / "fec-senate-candidates-flagged.csv")
           if row["candidate_id"].startswith(OFFICE_ID_PREFIXES["Senate"])]
    senate_ballot = [b for (_, office), rows in races.items() if office == "Senate" for b in rows]
    decisions = load_decisions(data_dir / "senate-identity-decisions.json", senate_ballot, fec, "Senate")
    fec_by_state = defaultdict(list)
    for row in fec:
        fec_by_state[row["state"]].append(row)
    names = {office: poll_names(path) for office, path in poll_paths.items()}

    field, review, discrepancies = [], [], []
    accepted_ids, plausible_ids = set(), set()
    for (state, office), rows in sorted(races.items()):
        rid = race_id(state, office)
        polled, ambiguous_polls = set(), set()
        for name in sorted(names[office][state]):
            hits = poll_candidates(name, rows)
            if len(hits) == 1:
                polled.add(hits[0]["name"])
            elif len(hits) > 1:
                ambiguous_polls.update(b["name"] for b in hits)
                discrepancies.append((state, office, rid, name, "ambiguous poll-to-ballot association"))
            else:
                discrepancies.append((state, office, rid, name, "in general polls but not on ballot list"))
        if office == "Senate":
            resolutions = resolve_rows(rows, fec_by_state[state], decisions)
        else:
            resolutions = [(b, None) for b in rows]
        for b, result in resolutions:
            f = result.canonical if result else None
            party = normalize_party(b["party"])
            in_polls = True if b["name"] in polled else ("" if b["name"] in ambiguous_polls else False)
            row = dict(
                state=state, office=office, race_id=rid, name=b["name"], party=party, party_raw=b["party"],
                fec_candidate_id="", fec_name="", incumbent="", filed_12g="", receipts="",
                cash_on_hand_end_period="", in_general_polls=in_polls, source_url=b["source_url"],
                fec_match_status="not_federal", fec_match_reason="governor candidates do not file with the FEC",
                fec_alternate_ids="",
            )
            if result:
                accepted_ids.update(result.member_ids)
                plausible_ids.update(c["candidate_id"] for c in result.candidates)
                row.update(
                    fec_candidate_id=f["candidate_id"] if f else "", fec_name=f["name"] if f else "",
                    incumbent=f["incumbent_challenge"] == "I" if f else "", filed_12g=result.filed_12g,
                    receipts=f["receipts"] if f else "",
                    cash_on_hand_end_period=f["cash_on_hand_end_period"] if f else "",
                    fec_match_status=result.status, fec_match_reason=result.reason,
                    fec_alternate_ids=";".join(result.alternates),
                )
                if result.status in UNRESOLVED:
                    for candidate in result.candidates or [{}]:
                        review.append(dict(
                            state=state, office=office, race_id=rid, ballot_name=b["name"],
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
                    discrepancies.append((state, office, rid, b["name"],
                                          f"major-party FEC identity {result.status}"))
            field.append(row)
        parties = {normalize_party(b["party"]) for b in rows}
        if not {"DEM", "REP"} <= parties:
            missing = ", ".join(sorted({"DEM", "REP"} - parties))
            discrepancies.append((state, office, rid, "", f"no {missing} candidate on ballot list"))
    for row in fec:
        if row["filed_12g"] == "True" and row["candidate_id"] not in accepted_ids:
            issue = ("filed 12G with unresolved ballot identity" if row["candidate_id"] in plausible_ids
                     else "filed 12G but not on ballot list")
            discrepancies.append((row["state"], "Senate", race_id(row["state"], "Senate"), row["name"], issue))
    for office in poll_paths:
        for state in sorted(set(names[office]) - {s for s, o in races if o == office}):
            for name in sorted(names[office][state]):
                discrepancies.append((state, office, race_id(state, office) if state in STATES else "",
                                      name, "in general polls but no race on ballot list"))
    field.sort(key=lambda r: (r["race_id"], r["party"], r["name"]))
    review.sort(key=lambda r: (r["race_id"], r["ballot_name"], r["fec_candidate_id"]))
    discrepancy_rows = [dict(zip(DISCREPANCY_COLUMNS, row)) for row in sorted(discrepancies)]
    publish_csvs(data_dir, [
        ("statewide-general-field.csv", FIELD_COLUMNS, field),
        ("statewide-field-discrepancies.csv", DISCREPANCY_COLUMNS, discrepancy_rows),
        ("statewide-match-review.csv", REVIEW_COLUMNS, review),
    ])
    return field, review, discrepancy_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    try:
        field, review, discrepancies = build(args.data_dir)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Build failed: {exc}")
    races = len({r["race_id"] for r in field})
    print(f"Wrote {len(field)} candidates in {races} races, {len(review)} review rows, "
          f"{len(discrepancies)} discrepancies", file=sys.stderr)


if __name__ == "__main__":
    main()
