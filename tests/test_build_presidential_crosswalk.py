# /// script
# requires-python = ">=3.11"
# dependencies = ["geopandas>=1.0", "numpy>=1.26", "pyogrio>=0.9", "pyproj>=3.6", "shapely>=2.0", "topojson>=1.9"]
# ///
"""Tests for the 119th Congress to 2026 crosswalk build. Run: uv run tests/test_build_presidential_crosswalk.py

Uses Utah's Census 119th Congress districts from 2026/geometry/cache (downloaded on first run) as fixture shapes.
"""

import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import geopandas as gpd
    import build_district_geometry as geometry
    import build_presidential_crosswalk as crosswalk
except ImportError as error:  # geopandas and friends come from the inline script metadata
    raise unittest.SkipTest(f"run with: uv run tests/test_build_presidential_crosswalk.py ({error})")


class CrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads(geometry.MANIFEST.read_text())
        base = geometry.read_base(geometry.fetch(manifest["base"], geometry.CACHE_DIR))
        cls.utah = base[base["state"] == "UT"].sort_values("race_key").reset_index(drop=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.blocks_dir = self.cache / "blocks"
        self.blocks_dir.mkdir(parents=True)
        self.out = self.root / "out"
        self.out.mkdir()

    def zip_shapefile(self, frame, name):
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        frame.to_file(folder / f"{name}.shp")
        archive = (self.blocks_dir if name.startswith("tl_") else self.cache) / f"{name}.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for f in sorted(folder.iterdir()):
                z.write(f, f.name)
        return archive

    def fixture_blocks(self, extra=()):
        """One block inside each Utah district, plus extra (lon, lat, pop, old CDFP) blocks."""
        rows = []
        for i, geom in enumerate(self.utah.geometry):
            point = geom.representative_point()
            rows.append((f"49{i:013d}", 100 * (i + 1), point.x, point.y, f"{i + 1:02d}"))
        for j, (lon, lat, pop, cd) in enumerate(extra):
            rows.append((f"49{90 + j:013d}", pop, lon, lat, cd))
        return rows

    def write_counties(self, rows, years=("2020", "2024")):
        entries = []
        for year in ("2020", "2024"):
            path = self.blocks_dir / f"county_{year}.csv"
            counties = sorted({r[0][:5] for r in rows}) if year in years else []
            lines = ["state_name,county_fips,county_name,votes_gop,votes_dem,total_votes,diff,per_gop,per_dem,per_point_diff"]
            lines += [f"Utah,{c},Fixture County,600,300,1000,300,0.6,0.3,0.3" for c in counties]
            lines.append("Nevada,32003,Clark County,1,2,3,1,0.3,0.6,0.3")
            path.write_text("\n".join(lines) + "\n")
            entries.append({"election_year": year, "url": f"https://example.test/{year}.csv", "file": path.name,
                            "retrieved": "2026-11-13", "sha256": geometry.sha256(path)})
        return entries

    def write_inputs(self, rows, plan_frame=None, registry=("UT",), bad_hash=False, county_years=("2020", "2024"),
                     census_2026=None):
        """census_2026 maps block GEOID to its 2026 CDFP; by default, the plan district containing (or nearest) it."""
        frame = gpd.GeoDataFrame({
            "GEOID20": [r[0] for r in rows], "POP20": [r[1] for r in rows],
            "INTPTLAT20": [f"{r[3]:+.7f}" for r in rows], "INTPTLON20": [f"{r[2]:+.7f}" for r in rows],
        }, geometry=gpd.points_from_xy([r[2] for r in rows], [r[3] for r in rows]), crs="EPSG:4269")
        blocks = self.zip_shapefile(frame, "tl_2020_49_tabblock20")
        bef = self.blocks_dir / "cd119.zip"
        with zipfile.ZipFile(bef, "w") as z:
            z.writestr("NationalCD119.txt", "GEOID,CDFP\n" + "".join(f"{r[0]},{r[4]}\n" for r in rows))
        if plan_frame is None:
            plan_frame = self.utah.copy()
            plan_frame["DISTRICT"] = [5 - int(k[-2:]) for k in plan_frame["race_key"]]
            plan_frame = plan_frame[["DISTRICT", "geometry"]]
        plan = self.zip_shapefile(plan_frame, "ut_plan")
        if census_2026 is None:
            census_2026 = {}
            for geoid, _, x, y, _ in rows:
                point = gpd.points_from_xy([x], [y])[0]
                inside = [d for d, g in zip(plan_frame["DISTRICT"], plan_frame.geometry) if g.contains(point)]
                nearest = min(zip(plan_frame["DISTRICT"], plan_frame.geometry), key=lambda dg: dg[1].distance(point))[0]
                census_2026[geoid] = f"{int(inside[0] if inside else nearest):02d}"
        bef_2026 = self.blocks_dir / "cd120.zip"
        with zipfile.ZipFile(bef_2026, "w") as z:
            z.writestr("NationalCD120.txt", "GEOID,STATEFP,COUNTYFP,TRACTCE,BLOCKCE,CDFP\n" + "".join(
                f"{g},{g[:2]},{g[2:5]},{g[5:11]},{g[11:]},{cd}\n" for g, cd in sorted(census_2026.items())))
        sources = {"schema_version": 1, "bef": {
            "url": "https://example.test/cd119.zip", "file": "cd119.zip", "member": "NationalCD119.txt",
            "retrieved": "2026-11-13", "sha256": geometry.sha256(bef)}, "bef_2026": {
            "url": "https://example.test/cd120.zip", "file": "cd120.zip", "member": "NationalCD120.txt",
            "retrieved": "2026-11-13", "sha256": geometry.sha256(bef_2026)}, "blocks": [{
            "state": "UT", "url": "https://example.test/ut.zip", "file": blocks.name, "retrieved": "2026-11-13",
            "sha256": "0" * 64 if bad_hash else geometry.sha256(blocks)}],
            "county_results": self.write_counties(rows, county_years)}
        (self.root / "sources.json").write_text(json.dumps(sources))
        (self.root / "geometry.json").write_text(json.dumps({"overrides": [{
            "id": "ut_test", "state": "UT", "file": plan.name, "url": "https://example.test/ut_plan.zip",
            "sha256": geometry.sha256(plan), "district_field": "DISTRICT"}]}))
        (self.root / "registry.json").write_text(json.dumps({"states": [{"state": s} for s in registry]}))

    def build(self):
        return crosswalk.build(self.root / "sources.json", self.root / "geometry.json", self.root / "registry.json",
                               self.cache, self.blocks_dir, self.out, log=lambda *_: None)

    def read(self, name):
        with open(self.out / name, newline="") as f:
            return list(csv.DictReader(f))

    def test_renumbered_plan_maps_each_old_district(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        rows = self.read(crosswalk.CROSSWALK)
        self.assertEqual([(r["old_district_id"], r["county_fips"], r["new_district_id"], r["shared_pop"], r["share"])
                          for r in rows], [
            ("UT-01", "49000", "UT-04", "100", "1.00000000"), ("UT-02", "49000", "UT-03", "200", "1.00000000"),
            ("UT-03", "49000", "UT-02", "300", "1.00000000"), ("UT-04", "49000", "UT-01", "400", "1.00000000")])
        self.assertEqual([(r["county_fips"], r["election_year"], r["dem_votes"], r["total_votes"], r["pop_2020"])
                          for r in self.read(crosswalk.COUNTIES)],
                         [("49000", "2020", "300", "1000", "1000"), ("49000", "2024", "300", "1000", "1000")])

    def test_census_2026_agreement_is_reported(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        self.assertEqual(self.read(crosswalk.REPORT)[0]["census_agreement_pct"], "100.0000")

    def test_plan_disagreeing_with_census_2026_fails_and_keeps_outputs(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        before = (self.out / crosswalk.CROSSWALK).read_bytes()
        # The Census file keeps the old numbering, so the renumbered fixture plan agrees for nobody.
        rows = self.fixture_blocks()
        self.write_inputs(rows, census_2026={r[0]: r[4] for r in rows})
        with self.assertRaisesRegex(geometry.BuildError, r"UT: the 2026 plan places only 0.00% of the population"):
            self.build()
        self.assertEqual((self.out / crosswalk.CROSSWALK).read_bytes(), before)

    def test_split_old_district_shares(self):
        # A second UT-01 block of 300 people sits inside old UT-02, which is new UT-03.
        inside_two = self.utah.geometry[1].representative_point()
        self.write_inputs(self.fixture_blocks([(inside_two.x, inside_two.y, 300, "01")]))
        self.build()
        ut01 = [r for r in self.read(crosswalk.CROSSWALK) if r["old_district_id"] == "UT-01"]
        self.assertEqual([(r["new_district_id"], r["shared_pop"], r["old_district_pop"], r["share"]) for r in ut01],
                         [("UT-03", "300", "400", "0.75000000"), ("UT-04", "100", "400", "0.25000000")])

    def test_unplaced_block_goes_to_nearest_and_is_reported(self):
        # One person just west of Utah, in Nevada; a tiny share of the fixture's population.
        bounds = self.utah.total_bounds
        rows = self.fixture_blocks()
        rows = [(g, p * 10000, x, y, cd) for g, p, x, y, cd in rows]
        self.write_inputs(rows + [(f"49{99:013d}", 1, bounds[0] - 0.05, (bounds[1] + bounds[3]) / 2, "02")])
        self.build()
        report = self.read(crosswalk.REPORT)[0]
        self.assertEqual((report["unplaced_blocks"], report["unplaced_population"]), ("1", "1"))

    def test_unplaced_population_over_limit_fails_and_keeps_outputs(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        before = (self.out / crosswalk.CROSSWALK).read_bytes()
        bounds = self.utah.total_bounds
        self.write_inputs(self.fixture_blocks([(bounds[0] - 0.05, (bounds[1] + bounds[3]) / 2, 500, "02")]))
        with self.assertRaisesRegex(geometry.BuildError, "outside every 2026 district"):
            self.build()
        self.assertEqual((self.out / crosswalk.CROSSWALK).read_bytes(), before)

    def test_county_without_results_fails_and_keeps_outputs(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        before = (self.out / crosswalk.COUNTIES).read_bytes()
        self.write_inputs(self.fixture_blocks(), county_years=("2020",))
        with self.assertRaisesRegex(geometry.BuildError, "county 49000 has no 2024 presidential results"):
            self.build()
        self.assertEqual((self.out / crosswalk.COUNTIES).read_bytes(), before)

    def test_new_district_without_blocks_fails(self):
        self.write_inputs(self.fixture_blocks()[:3])
        with self.assertRaisesRegex(geometry.BuildError, "UT-01"):
            self.build()

    def test_hash_mismatch_fails_and_keeps_outputs(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        before = (self.out / crosswalk.CROSSWALK).read_bytes()
        self.write_inputs(self.fixture_blocks(), bad_hash=True)
        with self.assertRaisesRegex(geometry.BuildError, "does not match manifest"):
            self.build()
        self.assertEqual((self.out / crosswalk.CROSSWALK).read_bytes(), before)

    def test_registry_state_without_plan_is_not_interpolated(self):
        self.write_inputs(self.fixture_blocks(), registry=("TN", "UT"))
        rows, _, _ = self.build()
        self.assertFalse(any(r["state"] == "TN" for r in rows))
        self.assertEqual([(r["state"], r["status"]) for r in self.read(crosswalk.REPORT)],
                         [("UT", "interpolated"), ("TN", "not_interpolated")])

    def test_rebuild_is_byte_identical(self):
        self.write_inputs(self.fixture_blocks())
        self.build()
        first = (self.out / crosswalk.CROSSWALK).read_bytes(), (self.out / crosswalk.REPORT).read_bytes()
        self.build()
        self.assertEqual(((self.out / crosswalk.CROSSWALK).read_bytes(), (self.out / crosswalk.REPORT).read_bytes()),
                         first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
