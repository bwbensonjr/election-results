# /// script
# requires-python = ">=3.11"
# ///
"""Ingest election-night results from the Globe/AP feed and publish results.json for the Big Board.

Run from the repository root:
    uv run scripts/ingest_results.py                       # one live fetch
    uv run scripts/ingest_results.py --every 120           # live, every two minutes
    uv run scripts/ingest_results.py --source PATH         # a saved or mock response, or a folder of them
See docs/big-board.md for outputs, the results.json schema, and failure behavior.
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "2026/baseline/election-baseline.json"
OUTPUT_DIR = ROOT / "2026/live"
LIVE_URL = "https://elections-api.bostonglobe.com/v2/elections/2026-11-03/"
SCHEMA_VERSION = 1
TRACKED_OFFICES = ("H", "S", "G")
OFFICE_NAMES = {"H": "House", "S": "Senate", "G": "Governor"}
MIN_INTERVAL = 60
RECORD_LIMIT = 240 * 1024
HOUSE_PARTS = 3
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
RAW_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)")


class IngestError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def party_group(ap_party):
    return {"Dem": "DEM", "GOP": "REP"}.get(ap_party, "OTHER")


def name_tokens(name):
    """Lowercase ASCII word tokens with nicknames in quotes and generational suffixes removed."""
    name = re.sub(r'"[^"]*"', " ", name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z]+", name.lower().replace("'", ""))
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return tokens


def read_json_bytes(data):
    return json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)


# ---- sources -------------------------------------------------------------------------------------------


def fetch_live(url=LIVE_URL, timeout=30):
    request = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "election-results-ingest"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    return data


def save_raw(data, fetched_at, raw_dir):
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{fetched_at.strftime('%Y-%m-%dT%H%M%SZ')}.json.gz"
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as g:
        g.write(data)
    return path


def fetched_time_for(path):
    """A saved response's fetch time comes from its file name, so replays reproduce the original output."""
    match = RAW_NAME.search(path.name)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0)


def source_files(source):
    path = Path(source)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.name.endswith((".json", ".json.gz")))
        if not files:
            raise IngestError(f"{path}: no .json or .json.gz responses")
        return files
    return [path]


# ---- baseline join -------------------------------------------------------------------------------------


def load_baseline(path=BASELINE):
    document = json.loads(Path(path).read_text())
    races = {r["race_key"]: r for r in document["races"]}
    by_ap_key = {(r["state_postal"], r["ap_office_id"], r["ap_seat_num"]): r["race_key"] for r in document["races"]}
    candidates = {}
    for c in document["candidates"]:
        candidates.setdefault(c["race_key"], []).append(c)
    return races, by_ap_key, candidates


def ap_key(race):
    response = race["raceResponse"]
    office = response["officeID"]
    return race["statePostal"], office, str(response.get("seatNum", "")) if office == "H" else ""


def select_races(document):
    tracked, national = [], None
    for race in document.get("races", []):
        response = race.get("raceResponse", {})
        if response.get("officeID") not in TRACKED_OFFICES:
            continue
        if race.get("statePostal") == "US":
            national = race
        else:
            tracked.append(race)
    return tracked, national


def join_races(tracked, by_ap_key):
    matches, errors = {}, []
    for race in tracked:
        key = ap_key(race)
        race_key = by_ap_key.get(key)
        if race_key is None:
            errors.append(f"AP race {race['raceResponse'].get('raceID')} {'/'.join(key)} matches no baseline race")
        elif race_key in matches:
            errors.append(f"{race_key}: matched by more than one AP race")
        else:
            matches[race_key] = race
    missing = sorted(set(by_ap_key.values()) - set(matches))
    errors.extend(f"{key}: no AP race" for key in missing)
    if errors:
        raise IngestError("race join failed: " + "; ".join(errors))
    return matches


def match_candidates(ap_candidates, baseline_candidates):
    """Map AP candidate IDs to baseline candidates by surname and party; each baseline row is used once."""
    used, links = set(), {}
    for candidate in sorted(ap_candidates, key=lambda c: (c.get("ballotOrder", 0), c["candidateID"])):
        last = name_tokens(candidate.get("last", ""))
        if not last:
            continue
        group = party_group(candidate.get("party"))
        options = [i for i, b in enumerate(baseline_candidates)
                   if i not in used and b["party"] == group and name_tokens(b["name"])[-len(last):] == last]
        if len(options) > 1:
            first = name_tokens(candidate.get("first", ""))[:1]
            options = [i for i in options if first and name_tokens(baseline_candidates[i]["name"])[:1] == first]
        if len(options) == 1:
            used.add(options[0])
            links[candidate["candidateID"]] = baseline_candidates[options[0]]
    return links


# ---- normalization -------------------------------------------------------------------------------------


def display_name(candidate):
    first = candidate.get("nickname") or candidate.get("first") or ""
    return " ".join(p for p in (first, candidate.get("last", ""), candidate.get("suffix", "")) if p)


def share(votes, total):
    return None if not total else round(100 * votes / total, 2)


def normalize_race(race_key, race, baseline_candidates):
    response = race["raceResponse"]
    unit = response["reportingUnits"][0]
    ap_candidates = unit.get("candidates", [])
    links = match_candidates(ap_candidates, baseline_candidates)
    total = sum(c.get("voteCount", 0) for c in ap_candidates)
    candidates = []
    for c in sorted(ap_candidates, key=lambda c: (-c.get("voteCount", 0), c.get("ballotOrder", 0), c["candidateID"])):
        link = links.get(c["candidateID"])
        candidates.append({
            "ap_candidate_id": c["candidateID"],
            "name": display_name(c),
            "party": c.get("party", ""),
            "party_group": party_group(c.get("party")),
            "votes": c.get("voteCount", 0),
            "pct": share(c.get("voteCount", 0), total),
            "incumbent": bool(c.get("incumbent")),
            "winner": c.get("winner") == "X",
            "baseline_name": link["name"] if link else None,
        })
    winners = [c for c in candidates if c["winner"]]
    leader = candidates[0] if total and candidates else None
    runner_up = candidates[1] if total and len(candidates) > 1 else None
    top = {}
    for c in candidates:
        top.setdefault(c["party_group"], c)
    dem_margin = None
    if total and "DEM" in top and "REP" in top:
        dem_margin = round(top["DEM"]["pct"] - top["REP"]["pct"], 2)
    return {
        "race_key": race_key,
        "state_postal": race["statePostal"],
        "office": OFFICE_NAMES[response["officeID"]],
        "ap_race_id": response["raceID"],
        "race_type": response.get("raceType", ""),
        "poll_close": unit.get("pollClosingTime", "")[:19] + "Z" if unit.get("pollClosingTime") else None,
        "tabulation_status": response.get("tabulationStatus"),
        "call_status": response.get("raceCallStatus"),
        "called": len(winners) == 1,
        "winner": ({"name": winners[0]["name"], "party_group": winners[0]["party_group"],
                    "ap_candidate_id": winners[0]["ap_candidate_id"]} if len(winners) == 1 else None),
        "eevp": unit.get("eevp", response.get("eevp")),
        "precincts_pct": unit.get("precinctsReportingPct"),
        "total_votes": total,
        "leader_party_group": leader["party_group"] if leader and leader["votes"] else None,
        "leader_margin_pp": (round(leader["pct"] - runner_up["pct"], 2) if leader and runner_up else
                             (100.0 if leader else None)),
        "dem_margin_pp": dem_margin,
        "ranked_choice": bool(response.get("rankedChoice")),
        "test": bool(race.get("test") or response.get("test")),
        "candidates": candidates,
    }


def normalize_national(race):
    if race is None:
        return None
    unit = race["raceResponse"]["reportingUnits"][0]
    total = sum(c.get("voteCount", 0) for c in unit.get("candidates", []))
    return {
        "house_popular_vote": {party_group(c.get("party")): {"votes": c.get("voteCount", 0),
                                                             "pct": share(c.get("voteCount", 0), total)}
                               for c in unit.get("candidates", [])},
        "precincts_pct": unit.get("precinctsReportingPct"),
    }


def summarize(races):
    summary = {}
    for office in OFFICE_NAMES.values():
        rows = [r for r in races.values() if r["office"] == office]
        called = {"DEM": 0, "REP": 0, "OTHER": 0}
        for r in rows:
            if r["winner"]:
                called[r["winner"]["party_group"]] += 1
        summary[office] = {"races": len(rows), "called": called,
                           "reporting": sum(1 for r in rows if r["total_votes"])}
    return summary


def build_results(document, baseline, fetched_at):
    _, by_ap_key, candidates = baseline
    tracked, national = select_races(document)
    matches = join_races(tracked, by_ap_key)
    races = {key: normalize_race(key, matches[key], candidates.get(key, []))
             for key in sorted(matches)}
    unmatched = [{"race_key": r["race_key"], "ap_candidate_id": c["ap_candidate_id"], "name": c["name"],
                  "party": c["party"]} for r in races.values() for c in r["candidates"] if c["baseline_name"] is None]
    content = {"national": normalize_national(national), "summary": summarize(races), "races": races}
    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "election_date": document.get("electionDate"),
        "ap_last_updated": document.get("lastUpdated"),
        "fetched_at": iso(fetched_at),
        "content_hash": content_hash,
        "test": any(r["test"] for r in races.values()),
        **content,
        "unmatched_candidates": unmatched,
    }


# ---- publishing ----------------------------------------------------------------------------------------


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def previous_hash(results_path):
    try:
        return json.loads(results_path.read_text()).get("content_hash")
    except (OSError, ValueError):
        return None


def split_records(results):
    """The database records for the board: meta, statewide, and the House in state groups."""
    races = results["races"]
    meta = {k: v for k, v in results.items() if k != "races"}
    meta["records"] = ["statewide"] + [f"house-{n}" for n in range(1, HOUSE_PARTS + 1)]
    records = {"meta": meta, "statewide": {k: r for k, r in races.items() if r["office"] != "House"}}
    house = sorted(k for k, r in races.items() if r["office"] == "House")
    states = sorted({races[k]["state_postal"] for k in house})
    groups, done = [[] for _ in range(HOUSE_PARTS)], 0
    for state in states:
        keys = [k for k in house if races[k]["state_postal"] == state]
        part = min(done * HOUSE_PARTS // len(house), HOUSE_PARTS - 1)
        groups[part].extend(keys)
        done += len(keys)
    for n, keys in enumerate(groups, 1):
        records[f"house-{n}"] = {k: races[k] for k in keys}
    out = {}
    for name, body in records.items():
        record = body if name == "meta" else {"content_hash": results["content_hash"], "races": body}
        text = json.dumps(record, separators=(",", ":"))
        if len(text.encode()) >= RECORD_LIMIT:
            raise IngestError(f"database record {name} is {len(text.encode())} bytes, over {RECORD_LIMIT}")
        out[name] = text + "\n"
    return out


def write_records(records, db_dir):
    for name, text in records.items():
        write_atomic(db_dir / f"{name}.json", text)


def log_run(output_dir, entry):
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "runs.jsonl", "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def run_once(data, fetched_at, output_dir, baseline, source):
    """Validate and publish one response. Raises IngestError without touching results.json on failure."""
    try:
        document = read_json_bytes(data)
    except (ValueError, OSError) as error:
        raise IngestError(f"response is not JSON: {error}")
    if not isinstance(document, dict) or not isinstance(document.get("races"), list):
        raise IngestError("response has no races list")
    try:
        results = build_results(document, baseline, fetched_at)
    except (KeyError, IndexError, TypeError) as error:
        raise IngestError(f"unexpected response shape: {error!r}")
    results_path = output_dir / "results.json"
    db_dir = output_dir / "db"
    changed = results["content_hash"] != previous_hash(results_path)
    records = split_records(results)
    write_atomic(results_path, json.dumps(results, separators=(",", ":")) + "\n")
    if changed or not all((db_dir / f"{name}.json").exists() for name in records):
        write_records(records, db_dir)
    else:
        write_records({"meta": records["meta"]}, db_dir)  # keeps fetched_at current for the freshness line
    status = {
        "ok": True,
        "changed": changed,
        "content_hash": results["content_hash"],
        "fetched_at": results["fetched_at"],
        "ap_last_updated": results["ap_last_updated"],
        "test": results["test"],
        "source": source,
        "races": len(results["races"]),
        "reporting": {o: s["reporting"] for o, s in results["summary"].items()},
        "called": {o: s["called"] for o, s in results["summary"].items()},
        "unmatched_candidates": len(results["unmatched_candidates"]),
    }
    write_atomic(output_dir / "status.json", json.dumps(status, indent=1) + "\n")
    return status


def ingest(source, output_dir, baseline):
    """One run: a live fetch, or each file of a saved source in order. Returns the last status."""
    output_dir = Path(output_dir)
    if source == "live":
        fetched_at = utc_now()
        try:
            data = fetch_live()
        except OSError as error:
            raise IngestError(f"fetch failed: {error}")
        save_raw(data, fetched_at, output_dir / "raw")
        return run_once(data, fetched_at, output_dir, baseline, "live")
    status = None
    for path in source_files(source):
        status = run_once(path.read_bytes(), fetched_time_for(path), output_dir, baseline, str(path))
    return status


def report(status):
    called = ", ".join(f"{o} D{c['DEM']} R{c['REP']}" + (f" O{c['OTHER']}" if c["OTHER"] else "")
                       for o, c in status["called"].items())
    return (f"{status['fetched_at']} {'changed' if status['changed'] else 'unchanged'}"
            f"{' TEST' if status['test'] else ''}: AP {status['ap_last_updated']}; called {called}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest Globe/AP election results into results.json.")
    parser.add_argument("--source", default="live", help="'live' (default), or a saved response file or folder")
    parser.add_argument("--every", type=int, help=f"repeat every N seconds (at least {MIN_INTERVAL})")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, type=Path, help="default: %(default)s")
    parser.add_argument("--baseline", default=BASELINE, type=Path, help="default: %(default)s")
    args = parser.parse_args(argv)
    if args.every is not None and args.every < MIN_INTERVAL:
        parser.error(f"--every must be at least {MIN_INTERVAL} seconds")
    baseline = load_baseline(args.baseline)
    while True:
        started = time.monotonic()
        try:
            status = ingest(args.source, args.output_dir, baseline)
            print(report(status), flush=True)
            log_run(args.output_dir, {"at": iso(utc_now()), **status})
            code = 0
        except IngestError as error:
            print(f"{iso(utc_now())} error: {error}", file=sys.stderr, flush=True)
            log_run(args.output_dir, {"at": iso(utc_now()), "ok": False, "error": str(error)})
            code = 1
        if args.every is None:
            return code
        time.sleep(max(0, args.every - (time.monotonic() - started)))


if __name__ == "__main__":
    sys.exit(main())
