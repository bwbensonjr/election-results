# /// script
# requires-python = ">=3.11"
# ///
"""Generate a simulated election night in the exact shape of the Globe/AP feed, marked as test data.

Run from the repository root:
    uv run scripts/mock_election_feed.py                          # write 54 ten-minute steps to 2026/live/mock/
    uv run scripts/mock_election_feed.py --play 60 --out 2026/live/mock/current.json
See docs/big-board.md for the model and a rehearsal recipe.
"""

import argparse
import copy
import gzip
import json
import math
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/globe-2026-11-03-pre.json.gz"
BASELINE = ROOT / "2026/baseline/election-baseline.json"
OUT_DIR = ROOT / "2026/live/mock"
START = "2026-11-03T23:00:00Z"
TRACKED = ("H", "S", "G")
VOTES_PER_DISTRICT = 320_000
CLOSE_RACE_KEY = "PA-07"


def parse_time(text):
    return datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def stamp(moment, millis=True):
    return moment.strftime("%Y-%m-%dT%H:%M:%S") + (".000Z" if millis else "Z")


def load_fixture(path=FIXTURE):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def load_baseline(path=BASELINE):
    document = json.loads(Path(path).read_text())
    by_ap_key = {(r["state_postal"], r["ap_office_id"], r["ap_seat_num"]): r for r in document["races"]}
    districts = {}
    for r in document["races"]:
        if r["office"] == "House":
            districts[r["state_postal"]] = districts.get(r["state_postal"], 0) + 1
    return by_ap_key, districts


def number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def expected_margin(baseline_race, environment):
    """Two-way Democratic-side margin in points: polling average, else PVI plus environment, else 2024 margin."""
    if baseline_race["poll_avg_status"] == "available":
        return number(baseline_race["poll_avg_dem_margin_pp"]) or 0.0
    pvi = number(baseline_race["cook_pvi_dem_lean_pp"])
    if pvi is not None:
        return 2 * pvi + environment
    pres = number(baseline_race["pres_2024_dem_margin_pp"])
    return pres if pres is not None else 0.0


def surname(name):
    parts = [p for p in name.replace('"', " ").replace(",", " ").split() if p.lower().rstrip(".") not in ("jr", "sr", "ii", "iii", "iv")]
    return parts[-1].lower() if parts else ""


def principal(candidates, name, prefer, exclude=None):
    """The ballot candidate matching a polling principal's surname, preferring the expected party."""
    last = surname(name) if name else ""
    matches = [c for c in candidates if last and c is not exclude and c["last"].lower().split()[-1] == last]
    return next((c for c in matches if c["party"] == prefer), matches[0] if matches else None)


class RaceModel:
    """Final outcome and counting curve for one tracked race, fixed by the seed."""

    def __init__(self, race, baseline_race, districts, seed, environment, close_race):
        response = race["raceResponse"]
        unit = response["reportingUnits"][0]
        rng = random.Random(f"{seed}:{response['raceID']}")
        state_rng = random.Random(f"{seed}:{race['statePostal']}")
        self.close_time = parse_time(unit["pollClosingTime"])
        self.statewide = response["officeID"] != "H"
        self.majority_rule = bool(response.get("rankedChoice")) or response.get("raceType") == "Nonpartisan Election"
        # Counting speed and the early-vote shift are shared by a state's races.
        self.delay = state_rng.uniform(5, 25)
        self.midpoint = state_rng.uniform(55, 160)
        self.spread = state_rng.uniform(25, 45)
        self.final_eevp = state_rng.uniform(93, 99.5)
        self.shift = state_rng.gauss(0, 6)
        candidates = sorted(unit["candidates"], key=lambda c: c["ballotOrder"])
        dem = principal(candidates, baseline_race["poll_avg_dem_candidate"], prefer="Dem")
        dem = dem or next((c for c in candidates if c["party"] == "Dem"), None)
        rep = principal(candidates, baseline_race["poll_avg_rep_candidate"], prefer="GOP", exclude=dem)
        rep = rep or next((c for c in candidates if c["party"] == "GOP" and c is not dem), None)
        margin = expected_margin(baseline_race, environment) + rng.gauss(0, 3 if self.statewide else 4)
        if close_race:
            margin = 0.3 if margin >= 0 else -0.3
        self.margin = margin
        others = [c for c in candidates if c is not dem and c is not rep]
        write_ins = [c for c in others if "write-in" in (c["last"] + c.get("first", "")).lower()]
        named = [c for c in others if c not in write_ins]
        shares = {c["candidateID"]: rng.uniform(0.1, 0.4) for c in write_ins}
        if named:
            heavy = response.get("raceType") == "Nonpartisan Election" or response.get("rankedChoice")
            pool = rng.uniform(8, 25) if heavy else rng.uniform(1.5, 5)
            raw = {c["candidateID"]: rng.uniform(0.5, 1.5) for c in named}
            shares.update({k: pool * v / sum(raw.values()) for k, v in raw.items()})
        other_share = sum(shares.values())
        weights = {k: v / other_share for k, v in shares.items()} if shares else {}
        self.dem_id = dem["candidateID"] if dem else None
        self.rep_id = rep["candidateID"] if rep else None
        self.other_share = other_share if (dem or rep) else 100.0
        self.other_weights = weights
        size = districts.get(race["statePostal"], 1) if self.statewide else 1
        self.expected_votes = int(VOTES_PER_DISTRICT * size * rng.uniform(0.8, 1.2))

    def eevp(self, moment):
        minutes = (moment - self.close_time).total_seconds() / 60
        if minutes < self.delay:
            return 0.0
        fraction = 1 / (1 + math.exp(-(minutes - self.midpoint) / self.spread))
        start = 1 / (1 + math.exp(-(self.delay - self.midpoint) / self.spread))
        return round(self.final_eevp * (fraction - start) / (1 - start), 1)

    def shares(self, eevp):
        """Candidate shares in percent at a reporting level; early counts lean by the state's shift."""
        margin = self.margin + self.shift * (1 - eevp / 100)
        two_party = 100 - self.other_share
        shares = {}
        if self.dem_id and self.rep_id:
            shares[self.dem_id] = two_party * (0.5 + margin / 200)
            shares[self.rep_id] = two_party * (0.5 - margin / 200)
        elif self.dem_id or self.rep_id:
            shares[self.dem_id or self.rep_id] = two_party
        for cid, weight in self.other_weights.items():
            shares[cid] = self.other_share * weight
        return shares


def callable_leader(model, counts, eevp, minutes_since_close):
    """The candidate to call now, or None. Safe races are called at poll close; close ones stay open."""
    total = sum(counts.values())
    final = model.shares(100)
    final_leader = max(final, key=final.get)
    ordered = sorted(final.values(), reverse=True)
    final_margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0)
    if model.majority_rule and final[final_leader] <= 50:
        return None
    if final_margin < 1.0 or minutes_since_close < 0:
        return None
    if final_margin >= 20 and not model.majority_rule:
        return final_leader
    if eevp < 50 or not total:
        return None
    current_leader = max(counts, key=counts.get)
    current = sorted(counts.values(), reverse=True)
    current_margin = 100 * (current[0] - (current[1] if len(current) > 1 else 0)) / total
    if current_leader != final_leader or current_margin < max(1.0, 25 * (1 - eevp / 100)):
        return None
    if model.majority_rule and 100 * counts[current_leader] / total <= 50:
        return None
    return final_leader


def generate(steps, step_minutes, seed=2026, environment=2.0, start=START, fixture=None, baseline=None):
    """Yield (moment, response) for each step of a simulated night."""
    fixture = fixture or load_fixture()
    by_ap_key, districts = baseline or load_baseline()
    models, called, counts = {}, {}, {}
    for race in fixture["races"]:
        response = race["raceResponse"]
        if response.get("officeID") in TRACKED and race["statePostal"] != "US":
            seat = str(response.get("seatNum", "")) if response["officeID"] == "H" else ""
            baseline_race = by_ap_key[(race["statePostal"], response["officeID"], seat)]
            models[response["raceID"]] = RaceModel(race, baseline_race, districts, seed, environment,
                                                   baseline_race["race_key"] == CLOSE_RACE_KEY)
    begin = parse_time(start)
    for step in range(steps):
        moment = begin + timedelta(minutes=step * step_minutes)
        document = copy.deepcopy(fixture)
        document["lastUpdated"] = stamp(moment)
        national = {}
        national_race = None
        for race in document["races"]:
            race["test"] = True
            race["lastUpdated"] = stamp(moment)
            response = race["raceResponse"]
            response["test"] = True
            unit = response["reportingUnits"][0]
            unit["lastUpdated"] = stamp(moment)
            model = models.get(response["raceID"])
            if race["statePostal"] == "US":
                national_race = race
                continue
            if model is None:
                continue
            eevp = model.eevp(moment)
            shares = model.shares(eevp) if eevp else {}
            previous = counts.get(response["raceID"], {})
            current = {}
            for c in unit["candidates"]:
                votes = int(model.expected_votes * eevp / 100 * shares.get(c["candidateID"], 0) / 100)
                c["voteCount"] = max(votes, previous.get(c["candidateID"], 0))
                current[c["candidateID"]] = c["voteCount"]
                if response["officeID"] == "H":
                    group = {"Dem": "Dem", "GOP": "GOP"}.get(c["party"], "Oth")
                    national[group] = national.get(group, 0) + c["voteCount"]
            counts[response["raceID"]] = current
            minutes = (moment - model.close_time).total_seconds() / 60
            reported = min(1.0, eevp / 100 * 1.04)
            unit["eevp"] = response["eevp"] = eevp
            unit["precinctsReporting"] = int(unit["precinctsTotal"] * reported)
            unit["precinctsReportingPct"] = round(100 * reported, 1)
            if response["raceID"] not in called:
                leader = callable_leader(model, current, eevp, minutes)
                if leader:
                    called[response["raceID"]] = leader
            winner = called.get(response["raceID"])
            for c in unit["candidates"]:
                c.pop("winner", None)
                if c["candidateID"] == winner:
                    c["winner"] = "X"
            if minutes < 0:
                response["tabulationStatus"] = "Awaiting Poll Close"
                response["raceCallStatus"] = "Too Early to Call"
            else:
                response["tabulationStatus"] = "Active Tabulation" if eevp < model.final_eevp else "Tabulation Paused"
                response["raceCallStatus"] = "Called" if winner else (
                    "Too Close to Call" if eevp >= 90 else "Too Early to Call")
        if national_race:
            unit = national_race["raceResponse"]["reportingUnits"][0]
            for c in unit["candidates"]:
                c["voteCount"] = national.get(c["party"], 0)
        yield step + 1, moment, document


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def step_name(step, moment):
    return f"step-{step:03d}-{moment.strftime('%Y-%m-%dT%H%M%SZ')}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a simulated election night in the Globe/AP feed's shape.")
    parser.add_argument("--steps", type=int, default=54, help="number of steps (default: %(default)s)")
    parser.add_argument("--step-minutes", type=int, default=10, help="simulated minutes per step (default: %(default)s)")
    parser.add_argument("--start", default=START, help="simulated time of step 1, UTC (default: %(default)s, 6pm ET)")
    parser.add_argument("--seed", type=int, default=2026, help="random seed (default: %(default)s)")
    parser.add_argument("--environment", type=float, default=2.0,
                        help="national Democratic margin added to PVI where no polling average exists (default: %(default)s)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR, help="folder for step files (default: %(default)s)")
    parser.add_argument("--play", type=float, metavar="SECONDS", help="rewrite --out with the next step every SECONDS")
    parser.add_argument("--out", type=Path, help="file to rewrite in --play mode")
    args = parser.parse_args(argv)
    if args.play is not None and args.out is None:
        parser.error("--play needs --out")
    steps = generate(args.steps, args.step_minutes, args.seed, args.environment, args.start)
    for step, moment, document in steps:
        text = json.dumps(document, separators=(",", ":")) + "\n"
        if args.play is not None:
            write_atomic(args.out, text)
            print(f"step {step}/{args.steps}: {stamp(moment, millis=False)} written to {args.out}", flush=True)
            if step < args.steps:
                time.sleep(args.play)
        else:
            write_atomic(args.out_dir / step_name(step, moment), text)
    if args.play is None:
        print(f"Wrote {args.steps} steps to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
