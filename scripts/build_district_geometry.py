# /// script
# requires-python = ">=3.11"
# dependencies = ["geopandas>=1.0", "numpy>=1.26", "pyogrio>=0.9", "pyproj>=3.6", "shapely>=2.0", "topojson>=1.9"]
# ///
"""Build draw-ready House district and state shapes for the Big Board.

Run from the repository root: uv run scripts/build_district_geometry.py
See docs/big-board.md for sources, the projection, and boundary vintages.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import geopandas as gpd
import shapely
import topojson
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon
import numpy as np
from shapely.ops import polylabel, unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_DIR = ROOT / "2026/geometry"
MANIFEST = GEOMETRY_DIR / "sources.json"
CACHE_DIR = GEOMETRY_DIR / "cache"
OUTPUT = GEOMETRY_DIR / "us-house-2026.json"
REGISTRY = ROOT / "2026/results/boundary-vintage.json"
BASELINE = ROOT / "2026/baseline/race-baseline.csv"
SCHEMA_VERSION = 1
WIDTH, HEIGHT = 960, 600
MAX_BYTES = 400_000
# Simplification tolerance in output pixels; tuned to keep about 12% of points.
SIMPLIFY_PX = 1.0
EXCLUDED_STATEFP = {"60", "66", "69", "72", "78"}

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}

# Albers USA composite: (proj string, target box x0, y0, x1, y1). Lower 48 fills the frame;
# Alaska and Hawaii are fitted into boxes below it, as in d3.geoAlbersUsa.
REGIONS = {
    "lower48": ("+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96 +datum=NAD83", (10, 10, 950, 560)),
    "AK": ("+proj=aea +lat_1=55 +lat_2=65 +lat_0=50 +lon_0=-154 +datum=NAD83", (40, 440, 250, 590)),
    "HI": ("+proj=aea +lat_1=8 +lat_2=18 +lat_0=13 +lon_0=-157 +datum=NAD83", (255, 500, 375, 580)),
}


class BuildError(Exception):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(entry, cache_dir):
    """Return the cached source file for a manifest entry, downloading it if needed, after a hash check."""
    path = cache_dir / entry.get("file", Path(entry["url"].split("?")[0]).name)
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(entry["url"], timeout=60) as response, open(path, "wb") as f:
            f.write(response.read())
    actual = sha256(path)
    if actual != entry["sha256"]:
        raise BuildError(f"{path.name}: SHA-256 {actual} does not match manifest {entry['sha256']}")
    return path


def district_key(state, number):
    number = str(number).strip()
    if number in ("00", "0", "AL", "98"):
        return f"{state}-AL"
    if not number.isdigit():
        raise BuildError(f"{state}: unrecognized district number {number!r}")
    return f"{state}-{int(number):02d}"


def read_base(path):
    frame = gpd.read_file(f"zip://{path}")
    frame = frame[~frame["STATEFP"].isin(EXCLUDED_STATEFP)].copy()
    unknown = sorted(set(frame["STATEFP"]) - set(STATE_FIPS))
    if unknown:
        raise BuildError(f"base file has unknown state FIPS codes {unknown}")
    frame["state"] = frame["STATEFP"].map(STATE_FIPS)
    frame["race_key"] = [None if s == "DC" else district_key(s, n) for s, n in zip(frame["state"], frame["CD119FP"])]
    frame["vintage"] = "current"
    return frame[["state", "race_key", "vintage", "geometry"]].to_crs("EPSG:4269")


def read_override(entry, path):
    state = entry["state"]
    field = entry["district_field"]
    layer = f"!{entry['layer_path']}" if entry.get("layer_path") else ""
    frame = gpd.read_file(f"zip://{path}{layer}" if path.suffix == ".zip" else path)
    if field not in frame.columns:
        raise BuildError(f"{state} override: no district field {field!r} in {sorted(frame.columns)}")
    frame = frame.to_crs("EPSG:4269")
    frame = frame.dissolve(by=field, as_index=False)
    frame["state"] = state
    frame["race_key"] = [district_key(state, n) for n in frame[field]]
    frame["vintage"] = "plan_2026"
    return frame[["state", "race_key", "vintage", "geometry"]]


def apply_overrides(base, overrides, registry_states, cache_dir):
    frames = [base]
    for entry in overrides:
        state = entry["state"]
        if state not in registry_states:
            raise BuildError(f"{state} override: state is not in the boundary vintage registry")
        outline = unary_union(list(frames[0][frames[0]["state"] == state].geometry))
        frames[0] = frames[0][frames[0]["state"] != state]
        override = read_override(entry, fetch(entry, cache_dir))
        # Clip to the Census shoreline and state border so coasts and neighbors line up with the base file.
        override["geometry"] = [shapely.make_valid(g).intersection(outline) for g in override.geometry]
        frames.append(override)
    frame = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs="EPSG:4269")
    overridden = {e["state"] for e in overrides}
    prior = sorted(registry_states - overridden)
    frame.loc[frame["state"].isin(prior), "vintage"] = "prior_boundaries"
    return frame, prior


def region_of(state):
    return state if state in ("AK", "HI") else "lower48"


def project(frame):
    """Project each region with its own Albers and fit it into its box in the output frame."""
    projected = []
    for region, (proj, box) in REGIONS.items():
        part = frame[frame["state"].map(region_of) == region]
        transformer = Transformer.from_crs("EPSG:4269", proj, always_xy=True)
        to_xy = lambda a: np.column_stack(transformer.transform(a[:, 0], a[:, 1]))
        geoms = [shapely.transform(g, to_xy) for g in part.geometry]
        minx, miny, maxx, maxy = unary_union(geoms).bounds
        x0, y0, x1, y1 = box
        scale = min((x1 - x0) / (maxx - minx), (y1 - y0) / (maxy - miny))
        ox = x0 + ((x1 - x0) - (maxx - minx) * scale) / 2
        oy = y0 + ((y1 - y0) - (maxy - miny) * scale) / 2
        fit = lambda a: np.column_stack((ox + (a[:, 0] - minx) * scale, oy + (maxy - a[:, 1]) * scale))
        part = part.copy()
        part["geometry"] = [shapely.transform(g, fit) for g in geoms]
        projected.append(part)
    return gpd.GeoDataFrame(gpd.pd.concat(projected, ignore_index=True), crs=None)


def simplify(frame):
    """Topology-preserving simplification, so neighboring districts keep identical shared edges."""
    frame = frame.sort_values(["state", "race_key"], na_position="last").reset_index(drop=True)
    topo = topojson.Topology(frame, prequantize=False, toposimplify=SIMPLIFY_PX, topology=True)
    simplified = topo.to_gdf()
    simplified = simplified.set_index(frame.index)
    frame = frame.copy()
    frame["geometry"] = [shapely.make_valid(g) if not g.is_valid else g for g in simplified.geometry]
    return frame


def polygons(geom):
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for part in getattr(geom, "geoms", []) for g in polygons(part)]


def fmt(value):
    text = f"{value:.1f}"
    return "0.0" if text == "-0.0" else text


def ring_path(coords):
    points = []
    for x, y in coords[:-1]:
        point = f"{fmt(x)},{fmt(y)}"
        if not points or points[-1] != point:
            points.append(point)
    return "M" + "L".join(points) + "Z" if len(points) >= 3 else ""


def svg_path(geom):
    parts = []
    for poly in polygons(geom):
        for ring in [poly.exterior, *poly.interiors]:
            parts.append(ring_path(list(ring.coords)))
    return "".join(p for p in parts if p)


def point_count(geom):
    return sum(len(r.coords) for p in polygons(geom) for r in [p.exterior, *p.interiors])


def center(geom):
    largest = max(polygons(geom), key=lambda p: p.area)
    point = polylabel(largest, tolerance=0.5)
    return [float(fmt(point.x)), float(fmt(point.y))]


def bbox(geom):
    minx, miny, maxx, maxy = geom.bounds
    return [float(fmt(minx)), float(fmt(miny)), float(fmt(maxx)), float(fmt(maxy))]


def house_keys(path):
    with open(path, newline="") as f:
        return {r["race_key"] for r in csv.DictReader(f) if r["office"] == "House"}


def build_document(frame, prior, manifest, before_points):
    districts, states = {}, {}
    for row in frame.itertuples():
        if not isinstance(row.race_key, str):
            continue
        districts[row.race_key] = {
            "state": row.state,
            "vintage": row.vintage,
            "center": center(row.geometry),
            "path": svg_path(row.geometry),
        }
    for state, part in frame.groupby("state"):
        outline = unary_union(list(part.geometry))
        states[state] = {"bbox": bbox(outline), "path": svg_path(outline)}
    dc = frame[frame["state"] == "DC"]
    sources = [manifest["base"], *manifest.get("overrides", [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "frame": [WIDTH, HEIGHT],
        "simplify_px": SIMPLIFY_PX,
        "points_before": before_points,
        "points_after": sum(point_count(g) for g in frame.geometry),
        "prior_line_states": prior,
        "sources": [{"id": s["id"], "sha256": s["sha256"]} for s in sources],
        "states": dict(sorted(states.items())),
        "districts": dict(sorted(districts.items())),
        "no_race": {"DC": {"center": center(dc.geometry.iloc[0]), "path": svg_path(dc.geometry.iloc[0])}} if len(dc) else {},
    }


def validate(document, expected_keys):
    keys = set(document["districts"])
    missing, extra = sorted(expected_keys - keys), sorted(keys - expected_keys)
    if missing or extra:
        raise BuildError(f"district keys differ from baseline: missing {missing}, extra {extra}")
    for key, item in [*document["districts"].items(), *document["states"].items()]:
        if not item["path"]:
            raise BuildError(f"{key}: empty shape after simplification")
    for group in ("states", "districts", "no_race"):
        for key, item in document[group].items():
            coords = [float(v) for seg in item["path"].replace("M", " ").replace("L", " ").replace("Z", " ").split()
                      for v in seg.split(",")]
            xs, ys = coords[0::2], coords[1::2]
            if min(xs) < 0 or min(ys) < 0 or max(xs) > WIDTH or max(ys) > HEIGHT:
                raise BuildError(f"{key}: shape falls outside the {WIDTH}x{HEIGHT} frame")


def build(manifest_path=MANIFEST, registry_path=REGISTRY, baseline_path=BASELINE, cache_dir=CACHE_DIR,
          output=OUTPUT, max_bytes=MAX_BYTES):
    manifest = json.loads(Path(manifest_path).read_text())
    registry_states = {e["state"] for e in json.loads(Path(registry_path).read_text())["states"]}
    base = read_base(fetch(manifest["base"], Path(cache_dir)))
    frame, prior = apply_overrides(base, manifest.get("overrides", []), registry_states, Path(cache_dir))
    projected = project(frame)
    before = sum(point_count(g) for g in projected.geometry)
    document = build_document(simplify(projected), prior, manifest, before)
    validate(document, house_keys(baseline_path))
    text = json.dumps(document, separators=(",", ":"), sort_keys=False) + "\n"
    size = len(text.encode())
    if size > max_bytes:
        raise BuildError(f"output is {size} bytes, over the {max_bytes}-byte limit")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=output.parent, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, output)
    return document, size


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build draw-ready House district and state shapes for the Big Board.")
    parser.add_argument("--manifest", default=MANIFEST, help="source manifest (default: %(default)s)")
    parser.add_argument("--registry", default=REGISTRY, help="boundary vintage registry")
    parser.add_argument("--baseline", default=BASELINE, help="race baseline CSV")
    parser.add_argument("--cache-dir", default=CACHE_DIR, help="download cache directory")
    parser.add_argument("--output", default=OUTPUT, help="output JSON (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        document, size = build(manifest_path=args.manifest, registry_path=args.registry, baseline_path=args.baseline,
                               cache_dir=args.cache_dir, output=args.output)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output}: {len(document['districts'])} districts, {len(document['states'])} states, "
          f"{size:,} bytes, {document['points_after']:,} points")
    if document["prior_line_states"]:
        print("On 119th Congress lines (prior_boundaries): " + ", ".join(document["prior_line_states"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
