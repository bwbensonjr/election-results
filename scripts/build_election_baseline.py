# /// script
# requires-python = ">=3.11"
# ///
"""Publish the election-night baseline of every 2026 House, Senate, and governor race, offline.

Run from the repository root after the context builds: uv run scripts/build_election_baseline.py
See docs/election-baseline.md for the files, columns, and AP join fields.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import build_house_district_context as house_context
import build_statewide_race_context as statewide_context
from district_history import ROOT, publish_csvs, read_records

HOUSE_DIR = ROOT / "2026/districts"
STATEWIDE_DIR = ROOT / "2026/statewide"
OUTPUT_DIR = ROOT / "2026/baseline"
SCHEMA_VERSION = 1
ELECTION_DATE = "2026-11-03"
INPUTS = {
    "house_races": (HOUSE_DIR, "house-district-context.csv"),
    "house_candidates": (HOUSE_DIR, "house-candidate-context.csv"),
    "statewide_races": (STATEWIDE_DIR, "statewide-race-context.csv"),
    "statewide_candidates": (STATEWIDE_DIR, "statewide-candidate-context.csv"),
}
AP_OFFICE = {"House": "H", "Senate": "S", "Governor": "G"}
OFFICE_ORDER = {"House": 0, "Senate": 1, "Governor": 2}
GUIDE_COLUMNS = [
    "guide_status", "guide_slot_et", "guide_poll_close_et", "guide_card", "guide_rating", "guide_senate_path",
    "guide_ladder_tier", "guide_hell_yes", "guide_ffs", "guide_chill", "guide_notes",
]
RACE_COLUMNS = [
    "race_key", "state_postal", "office", "district", "ap_office_id", "ap_seat_num", "ap_race_id",
    "candidate_count", "roster_incumbent_name", "roster_incumbent_party", "roster_vacant", "roster_ballot_status",
    "open_seat", "pres_2024_dem_margin_pp", "pres_2024_status", "cook_pvi_label", "cook_pvi_dem_lean_pp",
    "cook_pvi_status", "poll_avg_dem_candidate", "poll_avg_rep_candidate", "poll_avg_matchup_basis",
    "poll_avg_dem_pct", "poll_avg_rep_pct", "poll_avg_dem_margin_pp", "poll_count", "poll_latest_end_date",
    "poll_avg_status",
] + GUIDE_COLUMNS
CANDIDATE_COLUMNS = [
    "race_key", "state_postal", "office", "name", "party", "party_raw", "fec_candidate_id", "roster_incumbent",
    "poll_principal", "source_correction", "ap_candidate_id",
]
# Copied unchanged from the context exports; everything else in RACE_COLUMNS is derived here.
COPIED = [c for c in RACE_COLUMNS if c not in {
    "race_key", "state_postal", "district", "ap_office_id", "ap_seat_num", "ap_race_id", "pres_2024_dem_margin_pp"}]


def verify_current(house_dir=HOUSE_DIR, statewide_dir=STATEWIDE_DIR):
    """Fail unless the saved context exports equal a fresh rebuild from their committed inputs."""
    with tempfile.TemporaryDirectory() as scratch:
        for name, (builder, saved, script) in {
            "house": (house_context.build, house_dir, "build_house_district_context.py"),
            "statewide": (statewide_context.build, statewide_dir, "build_statewide_race_context.py"),
        }.items():
            fresh = Path(scratch) / name
            builder(output_dir=fresh)
            for path in sorted(fresh.iterdir()):
                if not (saved / path.name).exists() or (saved / path.name).read_bytes() != path.read_bytes():
                    raise ValueError(f"{saved / path.name}: stale context export; run {script}")


def race_row(context, office):
    """Return one baseline race row from a House district or statewide race context row."""
    house = office == "House"
    key = context["district_id"] if house else context["race_id"]
    row = {column: context.get(column, "") for column in COPIED}
    # Interpolated margins are estimates on the 2026 lines; prior-boundary margins describe old lines.
    current = context["pres_2024_status"] in ("available", "interpolated")
    row.update(race_key=key, state_postal=context["state"], office=office,
               district=context["district"] if house else "", ap_office_id=AP_OFFICE[office],
               # AP numbers at-large seats 1; confirm against the AP feed before relying on it.
               ap_seat_num=str(int(context["district"]) or 1) if house else "", ap_race_id="",
               pres_2024_dem_margin_pp=context["pres_2024_dem_margin_pp"] if current else "")
    return row


def candidate_row(context, office, key, principals):
    return dict(race_key=key, state_postal=context["state"], office=office, name=context["name"],
                party=context["party"], party_raw=context["party_raw"], fec_candidate_id=context["fec_candidate_id"],
                roster_incumbent=context["roster_incumbent"], poll_principal=str(context["name"] in principals),
                source_correction=context.get("source_correction", ""), ap_candidate_id="")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compute(house_dir=HOUSE_DIR, statewide_dir=STATEWIDE_DIR):
    """Return (race rows, candidate rows, input hashes) from the saved context exports."""
    paths = {name: {"house": house_dir, "statewide": statewide_dir}[name.split("_")[0]] / file
             for name, (_, file) in INPUTS.items()}
    _, house_races = read_records(paths["house_races"])
    _, house_candidates = read_records(paths["house_candidates"])
    _, statewide_races = read_records(paths["statewide_races"])
    _, statewide_candidates = read_records(paths["statewide_candidates"])
    races = [race_row(r, "House") for r in house_races] + [race_row(r, r["office"]) for r in statewide_races]
    keys = [r["race_key"] for r in races]
    if len(set(keys)) != len(keys) or not all(keys):
        raise ValueError("race keys are missing or duplicated across the context exports")
    principals = {r["race_key"]: {r["poll_avg_dem_candidate"], r["poll_avg_rep_candidate"]} - {""} for r in races}
    candidates = []
    for rows, key_column, office_of in [(house_candidates, "district_id", lambda _: "House"),
                                        (statewide_candidates, "race_id", lambda r: r["office"])]:
        for r in rows:
            key = r[key_column]
            if key not in principals:
                raise ValueError(f"candidate {r['name']} has race key {key!r} with no race row")
            candidates.append(candidate_row(r, office_of(r), key, principals[key]))
    order = lambda r: (r["state_postal"], OFFICE_ORDER[r["office"]], r["race_key"])
    races.sort(key=order)
    candidates.sort(key=lambda r: (*order(r), r["party"], r["name"]))
    return races, candidates, {name: sha256(path) for name, path in paths.items()}


def write_json(path, document):
    """Write JSON atomically with stable formatting and no timestamps, so rebuilds are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(document, stream, ensure_ascii=False, indent=1)
        stream.write("\n")
    os.chmod(stream.name, 0o644)
    os.replace(stream.name, path)


def build(house_dir=HOUSE_DIR, statewide_dir=STATEWIDE_DIR, output_dir=OUTPUT_DIR, verify=verify_current):
    verify(house_dir, statewide_dir)
    races, candidates, inputs = compute(house_dir, statewide_dir)
    publish_csvs(output_dir, [
        ("race-baseline.csv", RACE_COLUMNS, races),
        ("candidate-baseline.csv", CANDIDATE_COLUMNS, candidates),
    ])
    write_json(Path(output_dir) / "election-baseline.json", dict(
        schema_version=SCHEMA_VERSION, election_date=ELECTION_DATE, input_sha256=inputs,
        race_columns=RACE_COLUMNS, candidate_columns=CANDIDATE_COLUMNS, races=races, candidates=candidates))
    return races, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    try:
        races, candidates = build(output_dir=args.output_dir)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Baseline build failed: {exc}")
    print(f"Wrote {len(races)} races and {len(candidates)} candidates", file=sys.stderr)


if __name__ == "__main__":
    main()
