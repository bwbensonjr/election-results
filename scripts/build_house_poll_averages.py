# /// script
# requires-python = ">=3.11"
# ///
"""Build weighted House nominee polling averages from the saved poll snapshot, offline.

Run from the repository root: uv run scripts/build_house_poll_averages.py
See docs/district-data.md for eligibility, weights, schemas, and limitations.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from build_house_field import poll_candidates
from district_history import ROOT, district_key, publish_csvs, read_records

DEFAULT_POLLS = ROOT / "2026/polls/us-house-polls.csv"
DEFAULT_CANDIDATES = ROOT / "2026/candidates/house-general-field.csv"
DEFAULT_MATCHUPS = ROOT / "2026/polls/house-principal-matchups.json"
OUTPUT_DIR = ROOT / "2026/polls"
SOURCE_ID = "us-house-polls-2026"
CYCLE = "2026"
HALF_LIFE_DAYS = 21
SAMPLE_REFERENCE = 600
SAMPLE_CAP = 1500
SAMPLE_DEFAULT = 600
PARTISAN_FACTOR = 0.5
POPULATION_RANK = {"lv": 0, "rv": 1, "a": 2}
REQUIRED_COLUMNS = [
    "poll_id", "question_id", "pollster", "state", "end_date", "sample_size", "population",
    "partisan", "cycle", "stage", "seat_number", "party", "candidate_name", "pct",
    "ranked_choice_reallocated",
]
POLL_COLUMNS = [
    "poll_avg_dem_candidate", "poll_avg_rep_candidate", "poll_avg_dem_pct", "poll_avg_rep_pct",
    "poll_avg_dem_margin_pp", "poll_count", "poll_pollster_count", "poll_latest_end_date",
    "poll_avg_status", "poll_avg_source_id",
]
# Appended after POLL_COLUMNS so the context exports keep their earlier column positions.
MATCHUP_COLUMNS = ["poll_avg_matchup_basis"]
AVERAGE_COLUMNS = ["state", "district", "district_id"] + POLL_COLUMNS + MATCHUP_COLUMNS
INPUT_COLUMNS = [
    "poll_id", "question_id", "state", "district", "district_id", "stage", "pollster", "end_date",
    "population", "sample_size", "sample_size_imputed", "partisan", "dem_candidate", "rep_candidate",
    "dem_pct", "rep_pct", "dem_margin_pp", "included", "reason", "age_days", "recency_factor",
    "sample_factor", "pollster_factor", "partisan_factor", "weight",
]


def parse_date(value, location):
    try:
        return datetime.strptime(value.strip(), "%m/%d/%y").date()
    except ValueError:
        raise ValueError(f"{location}: invalid end_date {value!r}") from None


def parse_pct(value, location):
    try:
        number = Decimal(value.strip())
    except InvalidOperation:
        raise ValueError(f"{location}: invalid pct {value!r}") from None
    if not number.is_finite() or not 0 <= number <= 100:
        raise ValueError(f"{location}: pct out of range {value!r}")
    return float(number)


def parse_sample(value, location):
    if not value.strip():
        return None
    if not value.strip().isdigit() or int(value) <= 0:
        raise ValueError(f"{location}: invalid sample_size {value!r}")
    return int(value)


def fixed(value, places):
    return f"{round(value, places) + 0.0:.{places}f}"


def weighted(values, weights):
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def candidate_answers(question_id, rows):
    """Return a question's named-candidate answers: no NONE, Generic, or reallocated ranked-choice rows."""
    answers = [r for r in rows if r["party"] != "NONE" and not r["candidate_name"].startswith("Generic")
               and r["ranked_choice_reallocated"].strip().upper() != "TRUE"]
    names = [(r["party"], r["candidate_name"]) for r in answers]
    if len(names) != len(set(names)):
        raise ValueError(f"question {question_id}: duplicate candidate answers")
    return answers


def mark_eligible(record, question_id, first, dem_answer, rep_answer, dem_name, rep_name, matched, key):
    """Parse an eligible question's values into its log record and attach private selection fields."""
    location = f"question {question_id}"
    dem_pct, rep_pct = parse_pct(dem_answer["pct"], location), parse_pct(rep_answer["pct"], location)
    end = parse_date(first["end_date"], location)
    sample = parse_sample(first["sample_size"], location)
    record.update(dem_candidate=dem_name, rep_candidate=rep_name,
                  dem_pct=fixed(dem_pct, 2), rep_pct=fixed(rep_pct, 2),
                  dem_margin_pp=fixed(dem_pct - rep_pct, 2), end_date=end.isoformat(),
                  sample_size_imputed=str(sample is None),
                  sample_size=str(sample if sample is not None else SAMPLE_DEFAULT))
    record["_eligible"] = dict(key=key, end=end, sample=sample or SAMPLE_DEFAULT, dem=dem_pct, rep=rep_pct,
                               rank=(POPULATION_RANK.get(first["population"], len(POPULATION_RANK)),
                                     -matched, question_id))


def select_questions(records, race_of):
    """Keep each poll's best-ranked eligible question per race and mark the others superseded."""
    by_poll = defaultdict(list)
    for record in records:
        if "_eligible" in record:
            by_poll[(record["poll_id"], race_of(record))].append(record)
    selected = defaultdict(list)
    for group in by_poll.values():
        group.sort(key=lambda r: r["_eligible"]["rank"])
        selected[group[0]["_eligible"]["key"]].append(group[0])
        for record in group[1:]:
            record["reason"] = "superseded"
    return selected


def summarize(selected):
    """Weigh one race's selected polls and return its average columns."""
    weights = weigh(selected)
    dem = [r["_eligible"]["dem"] for r in selected]
    rep = [r["_eligible"]["rep"] for r in selected]
    return dict(poll_avg_dem_pct=fixed(weighted(dem, weights), 2),
                poll_avg_rep_pct=fixed(weighted(rep, weights), 2),
                poll_avg_dem_margin_pp=fixed(weighted([d - r for d, r in zip(dem, rep)], weights), 2),
                poll_count=str(len(selected)),
                poll_pollster_count=str(len({r["pollster"] for r in selected})),
                poll_latest_end_date=max(r["_eligible"]["end"] for r in selected).isoformat(),
                poll_avg_status="available")


def poll_district(state, seat, at_large):
    """Map a poll seat to (state, district, district_id), or None when it is not a valid seat."""
    if not seat.isdigit():
        return None
    try:
        return district_key(f"{state}-{'AL' if state in at_large else seat}")
    except ValueError:
        return None


def load_matchups(path, field):
    """Validate reviewed House principal matchups and return {district key: (non-Republican row, Republican row)}."""
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("matchups"), list):
        raise ValueError(f"{path}: expected schema_version 1 and a matchups list")
    by_id = {key[2]: key for key in field}
    overrides = {}
    for index, entry in enumerate(data["matchups"], 1):
        label = f"{path} matchup {index}"
        try:
            if not isinstance(entry, dict):
                raise ValueError("must be an object")
            for name in ("district_id", "principal_candidate", "rationale", "reviewed_by", "reviewed_at"):
                if not isinstance(entry.get(name), str) or not entry[name].strip():
                    raise ValueError(f"missing or invalid {name}")
            label += f" ({entry['district_id']} {entry['principal_candidate']})"
            date.fromisoformat(entry["reviewed_at"])
            evidence = entry.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(e, str) and e for e in evidence):
                raise ValueError("missing evidence references")
            key = by_id.get(entry["district_id"])
            if key is None:
                raise ValueError("district is not in the House field")
            if key in overrides:
                raise ValueError("duplicate district")
            rows = field[key]
            principal = [r for r in rows if r["name"] == entry["principal_candidate"]]
            if len(principal) != 1:
                raise ValueError("principal candidate is not in the district's field")
            if principal[0]["party"] == "REP":
                raise ValueError("principal candidate must not be the Republican")
            republicans = [r for r in rows if r["party"] == "REP"]
            if "republican_candidate" in entry:
                republicans = [r for r in republicans if r["name"] == entry["republican_candidate"]]
                if len(republicans) != 1:
                    raise ValueError("republican_candidate is not a Republican in the district's field")
            elif len(republicans) != 1:
                raise ValueError("district has several Republicans; name republican_candidate")
            overrides[key] = (principal[0], republicans[0])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return overrides


def nominee_pairs(candidates, matchups_path=DEFAULT_MATCHUPS):
    """Return field rows by district and each district's principal pair with its basis.

    The pair is the single DEM/REP nominee pair (basis `dem_rep`) unless a reviewed
    entry names the principals (basis `reviewed`).
    """
    field = defaultdict(list)
    for row in candidates:
        field[district_key(f"{row['state']}-{row['district']}")].append(row)
    reviewed = load_matchups(matchups_path, field)
    pairs = {}
    for key, rows in field.items():
        if key in reviewed:
            dem_side, republican = reviewed[key]
            pairs[key] = {"DEM": dem_side, "REP": republican, "basis": "reviewed"}
            continue
        dems = [r for r in rows if r["party"] == "DEM"]
        reps = [r for r in rows if r["party"] == "REP"]
        if len(dems) == 1 and len(reps) == 1:
            pairs[key] = {"DEM": dems[0], "REP": reps[0], "basis": "dem_rep"}
    return field, pairs


def reviewed_answers(answers, rows, pair):
    """Match answers to reviewed principals by name only; the poll's party code is not compared."""
    sides = {"DEM": [], "REP": []}
    for answer in answers:
        hits = poll_candidates(answer["candidate_name"], rows)
        if len(hits) > 1 and any(h is pair["DEM"] or h is pair["REP"] for h in hits):
            return "ambiguous_match"
        for side in sides:
            if len(hits) == 1 and hits[0] is pair[side]:
                sides[side].append(answer)
    if any(len(found) != 1 for found in sides.values()):
        return "non_nominee"
    return sides["DEM"][0], sides["REP"][0]


def classify(question_id, rows, field, pairs, at_large):
    """Return one input-log record; eligible questions carry private selection fields."""
    first = rows[0]
    state, seat = first["state"].strip(), first["seat_number"].strip()
    key = poll_district(state, seat, at_large) if seat else None
    record: dict = {column: "" for column in INPUT_COLUMNS}
    record.update(poll_id=first["poll_id"], question_id=question_id, state=state,
                  stage=first["stage"], pollster=first["pollster"], population=first["population"],
                  sample_size=first["sample_size"], partisan=first["partisan"], included="False")
    if key and key in field:
        record.update(state=key[0], district=key[1], district_id=key[2])
    try:
        record["end_date"] = parse_date(first["end_date"], question_id).isoformat()
    except ValueError:
        pass

    def reason():
        if first["cycle"] != CYCLE:
            return "out_of_cycle"
        if first["stage"] != "general":
            return "not_general"
        if state == "US":
            return "nationwide"
        if not seat:
            return "missing_seat"
        if key not in field:
            return "unknown_district"
        if key not in pairs:
            return "no_dem_rep_field"
        answers = candidate_answers(question_id, rows)
        if pairs[key]["basis"] == "reviewed":
            found = reviewed_answers(answers, field[key], pairs[key])
            if isinstance(found, str):
                return found
            matched = sum(len(poll_candidates(a["candidate_name"], field[key])) == 1 for a in answers)
            mark_eligible(record, question_id, first, *found, pairs[key]["DEM"]["name"],
                          pairs[key]["REP"]["name"], matched, key)
            return ""
        dem = [r for r in answers if r["party"] == "DEM"]
        rep = [r for r in answers if r["party"] == "REP"]
        if len(dem) != 1 or len(rep) != 1:
            return "not_head_to_head"
        for answer in (dem[0], rep[0]):
            hits = poll_candidates(answer["candidate_name"], field[key])
            if len(hits) > 1:
                return "ambiguous_match"
            if not hits or hits[0] is not pairs[key][answer["party"]]:
                return "non_nominee"
        matched = sum(len(poll_candidates(a["candidate_name"], field[key])) == 1 for a in answers)
        mark_eligible(record, question_id, first, dem[0], rep[0], pairs[key]["DEM"]["name"],
                      pairs[key]["REP"]["name"], matched, key)
        return ""

    record["reason"] = reason()
    return record


def weigh(selected):
    """Set weight factors on one district's selected records and return their weights."""
    latest = max(r["_eligible"]["end"] for r in selected)
    pollster_counts = defaultdict(int)
    for record in selected:
        pollster_counts[record["pollster"]] += 1
    weights = []
    for record in selected:
        poll = record["_eligible"]
        age = (latest - poll["end"]).days
        recency = 0.5 ** (age / HALF_LIFE_DAYS)
        sample = math.sqrt(min(poll["sample"], SAMPLE_CAP) / SAMPLE_REFERENCE)
        pollster = 1 / math.sqrt(pollster_counts[record["pollster"]])
        partisan = PARTISAN_FACTOR if record["partisan"].strip() else 1.0
        weight = recency * sample * pollster * partisan
        record.update(included="True", age_days=str(age), recency_factor=fixed(recency, 6),
                      sample_factor=fixed(sample, 6), pollster_factor=fixed(pollster, 6),
                      partisan_factor=fixed(partisan, 6), weight=fixed(weight, 6))
        weights.append(weight)
    return weights


def compute(polls_path=DEFAULT_POLLS, candidate_path=DEFAULT_CANDIDATES, matchups_path=DEFAULT_MATCHUPS):
    """Return (district averages, question input log) without writing files."""
    columns, polls = read_records(polls_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise ValueError(f"{polls_path}: missing required columns {missing}")
    _, candidates = read_records(candidate_path)
    field, pairs = nominee_pairs(candidates, matchups_path)
    at_large = {state for state in {k[0] for k in field}
                if {k[1] for k in field if k[0] == state} == {"00"}}
    questions = defaultdict(list)
    for row in polls:
        questions[row["question_id"]].append(row)
    records = [classify(qid, sorted(rows, key=lambda r: tuple(r[c] for c in columns)), field, pairs, at_large)
               for qid, rows in questions.items()]
    selected = select_questions(records, lambda r: r["district_id"])
    general = {(r["state"], r["district"]) for r in records
               if r["district_id"] and r["stage"] == "general"
               and questions[r["question_id"]][0]["cycle"] == CYCLE}
    averages = []
    for key in sorted(field):
        state, district, district_id = key
        row = dict.fromkeys(AVERAGE_COLUMNS, "")
        row.update(state=state, district=district, district_id=district_id)
        row["poll_avg_source_id"] = SOURCE_ID
        polls_in = selected.get(key, [])
        if key not in pairs:
            row["poll_avg_status"] = "no_dem_rep_field"
        elif polls_in:
            row.update(summarize(polls_in), poll_avg_dem_candidate=pairs[key]["DEM"]["name"],
                       poll_avg_rep_candidate=pairs[key]["REP"]["name"],
                       poll_avg_matchup_basis=pairs[key]["basis"])
        else:
            row["poll_avg_status"] = "no_eligible_polls" if (state, district) in general else "no_polls"
        averages.append(row)
    for record in records:
        record.pop("_eligible", None)
    records.sort(key=lambda r: (r["district_id"], r["end_date"], r["poll_id"], r["question_id"]))
    return averages, records


def build(polls_path=DEFAULT_POLLS, candidate_path=DEFAULT_CANDIDATES, output_dir=OUTPUT_DIR,
          matchups_path=DEFAULT_MATCHUPS):
    averages, records = compute(polls_path, candidate_path, matchups_path)
    publish_csvs(output_dir, [
        ("house-poll-averages.csv", AVERAGE_COLUMNS, averages),
        ("house-poll-average-inputs.csv", INPUT_COLUMNS, records),
    ])
    return averages, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polls", type=Path, default=DEFAULT_POLLS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--matchups", type=Path, default=DEFAULT_MATCHUPS)
    args = parser.parse_args()
    try:
        averages, records = build(args.polls, args.candidates, args.output_dir, args.matchups)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Poll average build failed: {exc}")
    available = sum(r["poll_avg_status"] == "available" for r in averages)
    print(f"Wrote {len(averages)} districts ({available} with averages), {len(records)} questions",
          file=sys.stderr)


if __name__ == "__main__":
    main()
