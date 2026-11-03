# /// script
# requires-python = ">=3.11"
# dependencies = ["geopandas>=1.0", "numpy>=1.26", "pyogrio>=0.9", "pyproj>=3.6", "shapely>=2.0", "topojson>=1.9"]
# ///
"""Tests for the district shape build. Run: uv run tests/test_build_district_geometry.py

Uses the Census base file from 2026/geometry/cache (downloaded on first run).
"""

import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import build_district_geometry as geometry
except ImportError as error:  # geopandas and friends come from the inline script metadata
    raise unittest.SkipTest(f"run with: uv run tests/test_build_district_geometry.py ({error})")

ROOT = Path(__file__).resolve().parents[1]


class DistrictGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(geometry.MANIFEST.read_text())
        geometry.fetch(cls.manifest["base"], geometry.CACHE_DIR)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        base_name = Path(self.manifest["base"]["url"]).name
        shutil.copy(geometry.CACHE_DIR / base_name, self.cache / base_name)

    def write_manifest(self, overrides=(), base=None):
        manifest = {**self.manifest, "base": base or self.manifest["base"], "overrides": list(overrides)}
        path = self.root / "sources.json"
        path.write_text(json.dumps(manifest))
        return path

    def build(self, manifest, output=None):
        return geometry.build(manifest_path=manifest, cache_dir=self.cache, output=output or self.root / "out.json")

    def utah_override(self):
        """A stand-in 2026 plan for Utah: its four Census districts renumbered in a DISTRICT field."""
        base = geometry.read_base(self.cache / Path(self.manifest["base"]["url"]).name)
        utah = base[base["state"] == "UT"].copy()
        utah["DISTRICT"] = [5 - int(k[-2:]) for k in utah["race_key"]]
        shp_dir = self.root / "ut_plan"
        shp_dir.mkdir()
        utah[["DISTRICT", "geometry"]].to_file(shp_dir / "ut_plan.shp")
        archive = self.cache / "ut_plan.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for f in sorted(shp_dir.iterdir()):
                z.write(f, f.name)
        return {"id": "ut_test", "state": "UT", "url": "https://example.test/ut_plan.zip", "plan": "test plan",
                "retrieved": "2026-11-03", "sha256": geometry.sha256(archive), "district_field": "DISTRICT"}

    def test_district_key_normalization(self):
        self.assertEqual(geometry.district_key("AK", "00"), "AK-AL")
        self.assertEqual(geometry.district_key("VT", "00"), "VT-AL")
        self.assertEqual(geometry.district_key("TX", "38"), "TX-38")
        self.assertEqual(geometry.district_key("UT", 3), "UT-03")
        with self.assertRaises(geometry.BuildError):
            geometry.district_key("TX", "X1")

    def test_committed_build_coverage_and_vintage(self):
        document, size = self.build(self.write_manifest())
        self.assertEqual(len(document["districts"]), 435)
        for key in ("AK-AL", "VT-AL", "TX-38"):
            self.assertIn(key, document["districts"])
        self.assertNotIn("PR", document["states"])
        self.assertIn("DC", document["states"])
        self.assertIn("DC", document["no_race"])
        self.assertEqual(len(document["states"]), 51)
        self.assertEqual(document["prior_line_states"], ["AL", "CA", "FL", "LA", "NC", "OH", "TN", "TX", "UT"])
        self.assertEqual(document["districts"]["TX-38"]["vintage"], "prior_boundaries")
        self.assertEqual(document["districts"]["MA-04"]["vintage"], "current")
        self.assertLessEqual(size, geometry.MAX_BYTES)

    def test_committed_manifest_with_enacted_plans(self):
        files = [geometry.CACHE_DIR / e["file"] for e in self.manifest["overrides"]]
        if not all(f.exists() for f in files):
            self.skipTest("enacted plan files are not in 2026/geometry/cache")
        document, size = geometry.build(cache_dir=geometry.CACHE_DIR, output=self.root / "committed.json")
        self.assertEqual(document["prior_line_states"], ["AL", "OH", "TN"])
        self.assertEqual(document["districts"]["TX-38"]["vintage"], "plan_2026")
        self.assertEqual(document["districts"]["OH-09"]["vintage"], "prior_boundaries")
        self.assertEqual(len(document["districts"]), 435)
        self.assertLessEqual(size, geometry.MAX_BYTES)

    def test_shapes_inside_frame(self):
        document, _ = self.build(self.write_manifest())
        width, height = document["frame"]
        for item in [*document["districts"].values(), *document["no_race"].values()]:
            x, y = item["center"]
            self.assertTrue(0 <= x <= width and 0 <= y <= height)
        for item in document["states"].values():
            x0, y0, x1, y1 = item["bbox"]
            self.assertTrue(0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height)

    def test_hash_mismatch_fails_and_keeps_output(self):
        output = self.root / "out.json"
        output.write_text("previous")
        bad = {**self.manifest["base"], "sha256": "0" * 64}
        with self.assertRaisesRegex(geometry.BuildError, "cb_2024_us_cd119_20m.zip"):
            self.build(self.write_manifest(base=bad), output)
        self.assertEqual(output.read_text(), "previous")

    def test_override_replaces_registry_state(self):
        document, _ = self.build(self.write_manifest([self.utah_override()]))
        self.assertNotIn("UT", document["prior_line_states"])
        self.assertEqual({document["districts"][f"UT-0{n}"]["vintage"] for n in range(1, 5)}, {"plan_2026"})
        self.assertEqual(document["districts"]["TX-38"]["vintage"], "prior_boundaries")

    def test_override_outside_registry_fails(self):
        entry = {**self.utah_override(), "state": "MA"}
        with self.assertRaisesRegex(geometry.BuildError, "MA override"):
            self.build(self.write_manifest([entry]))

    def test_size_limit(self):
        with self.assertRaisesRegex(geometry.BuildError, "over the"):
            geometry.build(manifest_path=self.write_manifest(), cache_dir=self.cache, output=self.root / "o.json",
                           max_bytes=1000)

    def test_rebuild_is_byte_identical(self):
        manifest = self.write_manifest()
        self.build(manifest, self.root / "a.json")
        self.build(manifest, self.root / "b.json")
        self.assertEqual((self.root / "a.json").read_bytes(), (self.root / "b.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
