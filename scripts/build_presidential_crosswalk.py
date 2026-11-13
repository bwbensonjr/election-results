# /// script
# requires-python = ">=3.11"
# dependencies = ["geopandas>=1.0", "numpy>=1.26", "pyogrio>=0.9", "pyproj>=3.6", "shapely>=2.0", "topojson>=1.9"]
# ///
"""Build the population-weighted crosswalk from 119th Congress districts to enacted 2026 districts.

Run from the repository root: uv run scripts/build_presidential_crosswalk.py
Each 2020 Census block is assigned to its 119th Congress district by the Census block equivalency
file, to its county, and to the 2026 district containing its internal point. County presidential results
for the same states are written beside the crosswalk to weight the split. See docs/district-data.md.
"""

import argparse
import csv
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pyogrio

from build_district_geometry import (
    MANIFEST as GEOMETRY_MANIFEST, REGISTRY, STATE_FIPS, BuildError, district_key, fetch as fetch_plan,
    read_override, sha256,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "2026/results"
SOURCES = RESULTS_DIR / "presidential-crosswalk-sources.json"
CACHE_DIR = ROOT / "2026/geometry/cache"
BLOCK_CACHE = CACHE_DIR / "blocks"
CROSSWALK = "presidential-crosswalk.csv"
REPORT = "presidential-crosswalk-report.csv"
COUNTIES = "presidential-county-results.csv"
CROSSWALK_COLUMNS = ["state", "old_district_id", "county_fips", "new_district_id", "shared_pop", "old_district_pop",
                     "share"]
COUNTY_COLUMNS = ["state", "county_fips", "election_year", "dem_votes", "rep_votes", "total_votes", "pop_2020"]
COUNTY_SOURCE_COLUMNS = ["state_name", "county_fips", "county_name", "votes_gop", "votes_dem", "total_votes"]
ELECTION_YEARS = ["2020", "2024"]
REPORT_COLUMNS = ["state", "status", "plan_id", "blocks", "population", "old_districts", "new_districts",
                  "unplaced_blocks", "unplaced_population", "unplaced_pct"]
FIPS_STATE = {v: k for k, v in STATE_FIPS.items()}
# A populated block whose internal point lies outside every 2026 district goes to the nearest one;
# the build fails if such blocks hold more than this share of a state's population.
MAX_UNPLACED_SHARE = 0.001
EQUAL_AREA = "EPSG:5070"


def fetch(entry, cache_dir):
    """Return a cached block source file, downloading it if needed, after a hash check."""
    path = Path(cache_dir) / entry["file"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "election-results-crosswalk"})
        with urllib.request.urlopen(request, timeout=300) as response, open(path, "wb") as f:
            while chunk := response.read(1 << 20):
                f.write(chunk)
    actual = sha256(path)
    if actual != entry["sha256"]:
        raise BuildError(f"{path.name}: SHA-256 {actual} does not match manifest {entry['sha256']}")
    return path


def load_sources(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("blocks"), list):
        raise BuildError(f"{path}: expected schema_version 1 and a blocks list")
    if sorted(e.get("election_year") for e in data.get("county_results") or []) != ELECTION_YEARS:
        raise BuildError(f"{path}: county_results needs one entry for each of {ELECTION_YEARS}")
    for entry in [data.get("bef"), *data["blocks"], *data["county_results"]]:
        if not isinstance(entry, dict) or not all(entry.get(k) for k in ("url", "file", "retrieved", "sha256")):
            raise BuildError(f"{path}: every source needs url, file, retrieved, and sha256")
    states = [e.get("state") for e in data["blocks"]]
    if len(states) != len(set(states)) or not set(states) <= set(FIPS_STATE):
        raise BuildError(f"{path}: block sources need unique, known state codes")
    return data


def read_bef(path, member, fips):
    """Return {block GEOID: 119th Congress district number} for the given state FIPS codes."""
    with zipfile.ZipFile(path) as archive, archive.open(member) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
        if [h.strip() for h in next(reader)] != ["GEOID", "CDFP"]:
            raise BuildError(f"{path.name}!{member}: expected GEOID,CDFP header")
        return {geoid: cd.strip() for geoid, cd in reader if geoid[:2] in fips}


def read_county_results(path, fips):
    """Return {county FIPS: (dem, rep, total)} for counties in the given state FIPS codes."""
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not set(COUNTY_SOURCE_COLUMNS) <= set(reader.fieldnames or []):
            raise BuildError(f"{Path(path).name}: expected columns {COUNTY_SOURCE_COLUMNS}")
        results = {}
        for line, row in enumerate(reader, 2):
            county = row["county_fips"].strip().zfill(5)
            if county[:2] not in fips:
                continue
            try:
                dem, rep, total = (int(row[c]) for c in ["votes_dem", "votes_gop", "total_votes"])
            except ValueError as error:
                raise BuildError(f"{Path(path).name} row {line}: invalid vote count") from error
            if county in results or min(dem, rep) < 0 or dem + rep > total or total <= 0:
                raise BuildError(f"{Path(path).name} row {line}: duplicate county or impossible votes for {county}")
            results[county] = (dem, rep, total)
    return results


def county_rows(state, blocks, results):
    """Return county table rows for every populated county, failing if a year lacks its results."""
    population = blocks.assign(county=blocks["GEOID20"].str[:5]).groupby("county")["POP20"].sum()
    rows = []
    for county, pop in sorted(population.items()):
        for year in ELECTION_YEARS:
            if county not in results[year]:
                raise BuildError(f"{state}: county {county} has no {year} presidential results")
            dem, rep, total = results[year][county]
            rows.append(dict(zip(COUNTY_COLUMNS, [state, county, year, str(dem), str(rep), str(total), str(int(pop))])))
    return rows


def read_blocks(path):
    """Return populated blocks with their internal points; geometry is not read."""
    frame = pyogrio.read_dataframe(path, read_geometry=False,
                                   columns=["GEOID20", "POP20", "INTPTLAT20", "INTPTLON20"])
    frame["POP20"] = frame["POP20"].astype(int)
    frame = frame[frame["POP20"] > 0].copy()
    points = gpd.points_from_xy(frame["INTPTLON20"].astype(float), frame["INTPTLAT20"].astype(float))
    return gpd.GeoDataFrame(frame[["GEOID20", "POP20"]], geometry=points, crs="EPSG:4269")


def place_blocks(blocks, plan):
    """Assign each block to the 2026 district containing its internal point, else the nearest one."""
    plan = plan[["race_key", "geometry"]]
    joined = gpd.sjoin(blocks, plan, how="left", predicate="intersects")
    # A point on a shared edge matches two districts; keep the first by race key, deterministically.
    joined = joined.sort_values(["GEOID20", "race_key"]).drop_duplicates("GEOID20")
    unplaced = joined["race_key"].isna()
    if unplaced.any():
        lost = joined[unplaced].drop(columns=["race_key", "index_right"]).to_crs(EQUAL_AREA)
        nearest = gpd.sjoin_nearest(lost, plan.to_crs(EQUAL_AREA), how="left")
        nearest = nearest.sort_values(["GEOID20", "race_key"]).drop_duplicates("GEOID20")
        joined.loc[unplaced, "race_key"] = joined.loc[unplaced, "GEOID20"].map(
            dict(zip(nearest["GEOID20"], nearest["race_key"])))
    return dict(zip(joined["GEOID20"], joined["race_key"])), set(joined.loc[unplaced, "GEOID20"])


def crosswalk_state(state, blocks, bef, plan):
    new_of, unplaced = place_blocks(blocks, plan)
    shared = defaultdict(int)
    old_pop = defaultdict(int)
    new_districts = set()
    for geoid, pop in zip(blocks["GEOID20"], blocks["POP20"]):
        if geoid not in bef:
            raise BuildError(f"{state}: populated block {geoid} is not in the 119th Congress block file")
        if not bef[geoid].isdigit():
            raise BuildError(f"{state}: populated block {geoid} has no 119th Congress district ({bef[geoid]!r})")
        old = district_key(state, bef[geoid])
        shared[(old, geoid[:5], new_of[geoid])] += int(pop)
        old_pop[old] += int(pop)
        new_districts.add(new_of[geoid])
    missing = sorted(set(plan["race_key"]) - new_districts)
    if missing:
        raise BuildError(f"{state}: 2026 districts with no populated blocks: {', '.join(missing)}")
    population = int(blocks["POP20"].sum())
    unplaced_pop = int(blocks.loc[blocks["GEOID20"].isin(unplaced), "POP20"].sum())
    if unplaced_pop > MAX_UNPLACED_SHARE * population:
        raise BuildError(f"{state}: {unplaced_pop} people in blocks outside every 2026 district "
                         f"exceeds {MAX_UNPLACED_SHARE:.1%} of {population}")
    rows = [dict(zip(CROSSWALK_COLUMNS, [state, old, county, new, str(pop), str(old_pop[old]),
                                         f"{pop / old_pop[old]:.8f}"]))
            for (old, county, new), pop in sorted(shared.items())]
    report = dict(state=state, status="interpolated", blocks=str(len(blocks)), population=str(population),
                  old_districts=str(len(old_pop)), new_districts=str(len(set(plan["race_key"]))),
                  unplaced_blocks=str(len(unplaced)), unplaced_population=str(unplaced_pop),
                  unplaced_pct=f"{100 * unplaced_pop / population:.4f}")
    return rows, report


def write_csv(path, columns, rows):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.chmod(tmp, 0o644)
        return tmp
    except BaseException:
        os.unlink(tmp)
        raise


def build(sources_path=SOURCES, geometry_manifest=GEOMETRY_MANIFEST, registry_path=REGISTRY,
          cache_dir=CACHE_DIR, block_cache=BLOCK_CACHE, output_dir=RESULTS_DIR, log=print):
    sources = load_sources(sources_path)
    plans = {e["state"]: e for e in json.loads(Path(geometry_manifest).read_text(encoding="utf-8"))["overrides"]}
    registry = {e["state"] for e in json.loads(Path(registry_path).read_text(encoding="utf-8"))["states"]}
    states = sorted(registry & set(plans))
    blocks_by_state = {e["state"]: e for e in sources["blocks"]}
    absent = [s for s in states if s not in blocks_by_state]
    if absent:
        raise BuildError(f"{sources_path}: no block source for {', '.join(absent)}")
    fips = {FIPS_STATE[s] for s in states}
    bef = read_bef(fetch(sources["bef"], block_cache), sources["bef"]["member"], fips)
    results = {e["election_year"]: read_county_results(fetch(e, block_cache), fips) for e in sources["county_results"]}
    rows, report, counties = [], [], []
    for state in states:
        log(f"{state}: reading blocks and placing them in the 2026 plan")
        blocks = read_blocks(fetch(blocks_by_state[state], block_cache))
        plan = read_override(plans[state], fetch_plan(plans[state], Path(cache_dir)))
        state_rows, state_report = crosswalk_state(state, blocks, bef, plan)
        counties += county_rows(state, blocks, results)
        rows += state_rows
        report.append(dict(state_report, plan_id=plans[state]["id"]))
        log(f"{state}: {state_report['blocks']} blocks, {state_report['unplaced_blocks']} unplaced "
            f"({state_report['unplaced_pct']}% of population), {len(state_rows)} crosswalk rows")
    for state in sorted(registry - set(plans)):
        report.append(dict.fromkeys(REPORT_COLUMNS, "") | {"state": state, "status": "not_interpolated"})
        log(f"{state}: no enacted 2026 plan in the geometry manifest; not interpolated")
    output_dir = Path(output_dir)
    staged = [(write_csv(output_dir / CROSSWALK, CROSSWALK_COLUMNS, rows), output_dir / CROSSWALK)]
    try:
        staged.append((write_csv(output_dir / REPORT, REPORT_COLUMNS, report), output_dir / REPORT))
        staged.append((write_csv(output_dir / COUNTIES, COUNTY_COLUMNS, counties), output_dir / COUNTIES))
        for tmp, destination in staged:
            os.replace(tmp, destination)
    finally:
        for tmp, _ in staged:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return rows, report, counties


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the 119th Congress to 2026 district crosswalk and county table.")
    parser.add_argument("--sources", default=SOURCES, help="block source manifest (default: %(default)s)")
    parser.add_argument("--geometry-manifest", default=GEOMETRY_MANIFEST, help="district shape manifest")
    parser.add_argument("--registry", default=REGISTRY, help="boundary vintage registry")
    parser.add_argument("--cache-dir", default=CACHE_DIR, help="plan download cache directory")
    parser.add_argument("--block-cache", default=BLOCK_CACHE, help="block download cache directory")
    parser.add_argument("--output-dir", default=RESULTS_DIR, help="directory for the crosswalk, county table, and report")
    args = parser.parse_args(argv)
    try:
        build(args.sources, args.geometry_manifest, args.registry, args.cache_dir, args.block_cache, args.output_dir)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
