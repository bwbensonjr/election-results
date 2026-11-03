# /// script
# requires-python = ">=3.11"
# ///
"""Build weighted Senate and governor polling averages from the saved poll snapshots, offline.

Run from the repository root: uv run scripts/build_statewide_poll_averages.py
Selection and weights are the House method's; see docs/statewide-data.md for the differences.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from build_house_field import poll_candidates
from candidate_identity import name_parts
from build_house_poll_averages import (
    CYCLE, INPUT_COLUMNS as HOUSE_INPUT_COLUMNS, REQUIRED_COLUMNS as HOUSE_REQUIRED_COLUMNS,
    candidate_answers, mark_eligible, parse_date, select_questions, summarize,
)
from district_history import ROOT, publish_csvs, read_records

DEFAULT_POLLS = {
    "Senate": ROOT / "2026/polls/us-senate-polls.csv",
    "Governor": ROOT / "2026/polls/governor-polls.csv",
}
DEFAULT_CANDIDATES = ROOT / "2026/candidates/statewide-general-field.csv"
DEFAULT_MATCHUPS = ROOT / "2026/polls/statewide-principal-matchups.json"
OUTPUT_DIR = ROOT / "2026/polls"
SOURCE_IDS = {"Senate": "us-senate-polls-2026", "Governor": "governor-polls-2026"}
REQUIRED_COLUMNS = [c for c in HOUSE_REQUIRED_COLUMNS if c != "seat_number"]
POLL_COLUMNS = [
    "poll_avg_dem_candidate", "poll_avg_rep_candidate", "poll_avg_matchup_basis", "poll_avg_dem_pct",
    "poll_avg_rep_pct", "poll_avg_dem_margin_pp", "poll_count", "poll_pollster_count", "poll_latest_end_date",
    "poll_avg_status", "poll_avg_source_id",
]
AVERAGE_COLUMNS = ["state", "office", "race_id"] + POLL_COLUMNS
INPUT_COLUMNS = ["office", "race_id"] + [c for c in HOUSE_INPUT_COLUMNS if c not in ("district", "district_id")]


def load_field(candidate_path):
    """Return the statewide field's rows grouped by race ID, with each race's (state, office)."""
    _, candidates = read_records(candidate_path)
    field, races = defaultdict(list), {}
    for row in candidates:
        field[row["race_id"]].append(row)
        races[row["race_id"]] = (row["state"], row["office"])
    return field, races


def load_matchups(path, field):
    """Validate reviewed principal matchups and return (non-Republican row, Republican row) by race ID.

    An entry names the non-Republican principal and, when the race has several
    Republicans (Alaska's top-four ballot), the Republican principal as well.
    """
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("matchups"), list):
        raise ValueError(f"{path}: expected schema_version 1 and a matchups list")
    overrides = {}
    for index, entry in enumerate(data["matchups"], 1):
        label = f"{path} matchup {index}"
        try:
            if not isinstance(entry, dict):
                raise ValueError("must be an object")
            for key in ("race_id", "principal_candidate", "rationale", "reviewed_by", "reviewed_at"):
                if not isinstance(entry.get(key), str) or not entry[key].strip():
                    raise ValueError(f"missing or invalid {key}")
            label += f" ({entry['race_id']} {entry['principal_candidate']})"
            date.fromisoformat(entry["reviewed_at"])
            evidence = entry.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(e, str) and e for e in evidence):
                raise ValueError("missing evidence references")
            rows = field.get(entry["race_id"])
            if rows is None:
                raise ValueError("race is not in the statewide field")
            if entry["race_id"] in overrides:
                raise ValueError("duplicate race")
            principal = [r for r in rows if r["name"] == entry["principal_candidate"]]
            if len(principal) != 1:
                raise ValueError("principal candidate is not in the race's field")
            if principal[0]["party"] == "REP":
                raise ValueError("principal candidate must not be the Republican")
            republicans = [r for r in rows if r["party"] == "REP"]
            if "republican_candidate" in entry:
                republicans = [r for r in republicans if r["name"] == entry["republican_candidate"]]
                if len(republicans) != 1:
                    raise ValueError("republican_candidate is not a Republican in the race's field")
            elif len(republicans) != 1:
                raise ValueError("race has several Republicans; name republican_candidate")
            overrides[entry["race_id"]] = (principal[0], republicans[0])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return overrides


def principal_matchups(field, overrides):
    """Return {race_id: (dem-side row, Republican row, basis)} for races with a principal matchup."""
    matchups = {}
    for race_id, rows in field.items():
        if race_id in overrides:
            matchups[race_id] = (*overrides[race_id], "reviewed")
            continue
        reps = [r for r in rows if r["party"] == "REP"]
        dems = [r for r in rows if r["party"] == "DEM"]
        if len(dems) == 1 and len(reps) == 1:
            matchups[race_id] = (dems[0], reps[0], "dem_rep")
    return matchups


def classify(office, question_id, rows, field, races, matchups):
    """Return one input-log record; eligible questions carry private selection fields."""
    first = rows[0]
    state = first["state"].strip()
    race_id = next((rid for rid, key in races.items() if key == (state, office)), "")
    record = {column: "" for column in INPUT_COLUMNS}
    record.update(office=office, race_id=race_id, poll_id=first["poll_id"], question_id=question_id, state=state,
                  stage=first["stage"], pollster=first["pollster"], population=first["population"],
                  sample_size=first["sample_size"], partisan=first["partisan"], included="False")
    try:
        record["end_date"] = parse_date(first["end_date"], question_id).isoformat()
    except ValueError:
        pass

    def reason():
        if first["cycle"] != CYCLE:
            return "out_of_cycle"
        if first["stage"] != "general":
            return "not_general"
        if not race_id:
            return "unknown_race"
        if race_id not in matchups:
            return "no_principal_matchup"
        dem_side, republican, _ = matchups[race_id]
        answers = candidate_answers(question_id, rows)
        if not answers:
            return "not_head_to_head"
        hits = [(answer, poll_candidates(answer["candidate_name"], field[race_id])) for answer in answers]
        # The poll's party code is not compared with the ballot: Osborn is DEM in Nebraska polls.
        sides = {id(dem_side): [], id(republican): []}
        for answer, matched in hits:
            if len(matched) > 1 and any(id(m) in sides for m in matched):
                return "ambiguous_match"
            if len(matched) == 1 and id(matched[0]) in sides:
                sides[id(matched[0])].append(answer)
        for principal in (dem_side, republican):
            found = sides[id(principal)]
            if len(found) > 1:
                # A namesake ("Dan J. Sullivan" beside "Dan Sullivan") can share the first given
                # name; keep only an answer whose full given name matches the ballot exactly.
                exact = [a for a in found if name_parts(a["candidate_name"])[0] == name_parts(principal["name"])[0]]
                if len(exact) != 1:
                    return "ambiguous_match"
                sides[id(principal)] = exact
        if not all(sides.values()):
            return "non_principal"
        matched_count = sum(len(matched) == 1 for _, matched in hits)
        mark_eligible(record, question_id, first, sides[id(dem_side)][0], sides[id(republican)][0],
                      dem_side["name"], republican["name"], matched_count, race_id)
        return ""

    record["reason"] = reason()
    return record


def compute(poll_paths=None, candidate_path=DEFAULT_CANDIDATES, matchups_path=DEFAULT_MATCHUPS):
    """Return (race averages, question input log) without writing files."""
    poll_paths = poll_paths or DEFAULT_POLLS
    field, races = load_field(candidate_path)
    matchups = principal_matchups(field, load_matchups(matchups_path, field))
    records, general = [], set()
    for office, path in sorted(poll_paths.items()):
        columns, polls = read_records(path)
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        questions = defaultdict(list)
        for row in polls:
            questions[row["question_id"]].append(row)
        for qid, rows in questions.items():
            record = classify(office, qid, sorted(rows, key=lambda r: tuple(r[c] for c in columns)),
                              field, races, matchups)
            records.append(record)
            if record["race_id"] and rows[0]["stage"] == "general" and rows[0]["cycle"] == CYCLE:
                general.add(record["race_id"])
    selected = select_questions(records, lambda r: r["race_id"])
    averages = []
    for race_id in sorted(field):
        state, office = races[race_id]
        row = dict.fromkeys(AVERAGE_COLUMNS, "")
        row.update(state=state, office=office, race_id=race_id, poll_avg_source_id=SOURCE_IDS[office])
        polls_in = selected.get(race_id, [])
        if race_id not in matchups:
            row["poll_avg_status"] = "no_principal_matchup"
        elif polls_in:
            dem_side, republican, basis = matchups[race_id]
            row.update(summarize(polls_in), poll_avg_dem_candidate=dem_side["name"],
                       poll_avg_rep_candidate=republican["name"], poll_avg_matchup_basis=basis)
        else:
            row["poll_avg_status"] = "no_eligible_polls" if race_id in general else "no_polls"
        averages.append(row)
    for record in records:
        record.pop("_eligible", None)
    records.sort(key=lambda r: (r["office"], r["race_id"], r["end_date"], r["poll_id"], r["question_id"]))
    return averages, records


def build(poll_paths=None, candidate_path=DEFAULT_CANDIDATES, matchups_path=DEFAULT_MATCHUPS,
          output_dir=OUTPUT_DIR):
    averages, records = compute(poll_paths, candidate_path, matchups_path)
    publish_csvs(output_dir, [
        ("statewide-poll-averages.csv", AVERAGE_COLUMNS, averages),
        ("statewide-poll-average-inputs.csv", INPUT_COLUMNS, records),
    ])
    return averages, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--senate-polls", type=Path, default=DEFAULT_POLLS["Senate"])
    parser.add_argument("--governor-polls", type=Path, default=DEFAULT_POLLS["Governor"])
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--matchups", type=Path, default=DEFAULT_MATCHUPS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    try:
        averages, records = build({"Senate": args.senate_polls, "Governor": args.governor_polls},
                                  args.candidates, args.matchups, args.output_dir)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Statewide poll average build failed: {exc}")
    available = sum(r["poll_avg_status"] == "available" for r in averages)
    print(f"Wrote {len(averages)} races ({available} with averages), {len(records)} questions", file=sys.stderr)


if __name__ == "__main__":
    main()
