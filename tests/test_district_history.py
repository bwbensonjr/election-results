import copy
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import district_history as history

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)


class HistoryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        self.pres = self.root / "pres.csv"
        self.cook = self.root / "cook.csv"
        self.normalized = self.root / "normalized"
        self.pres_rows = copy.deepcopy(history.PRESIDENTIAL_HEADERS) + [
            ["AK-AL", "Source incumbent", "(R)", "400", "600", "1,000", "40.00%", "60.00%", "-20.00%", "",
             "600", "400", "1,000", "60.00%", "40.00%", "20.00%"],
            ["AL-01", "Other incumbent", "(D)", "500", "500", "1,000", "50.00%", "50.00%", "0.00%", "",
             "600", "400", "1,000", "60.00%", "40.00%", "20.00%"],
        ]
        self.cook_rows = [history.COOK_COLUMNS.copy(),
                          ["AK-AL", "Source incumbent", "R", "R+3", "D+4", "200"],
                          ["AL-01", "Other incumbent", "D", "R+2", "EVEN", "205"]]
        self.sources = {
            "presidential": dict(source_id="test-pres", path="pres.csv", edition="user-supplied", format="presidential-two-header",
                                 election_years=[2020, 2024], notes="Boundary vintage unknown", source_url=None, retrieved_at=None, published_at=None),
            "cook_pvi": dict(source_id="test-cook", path="cook.csv", edition="2026", format="cook-pvi-six-column",
                             election_years=[2020, 2024], notes="Published 2026 PVI", source_url="https://example.test", retrieved_at="2026-11-02", published_at=None),
        }
        self.save_sources()

    def save_sources(self):
        write_csv(self.pres, self.pres_rows)
        write_csv(self.cook, self.cook_rows)
        for source in self.sources.values():
            source["sha256"] = hashlib.sha256((self.root / source["path"]).read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(dict(schema_version=1, sources=self.sources)))

    def normalize(self):
        return history.normalize(self.manifest, self.normalized, self.root)


class DistrictHistoryTests(HistoryFixture):
    def test_keys(self):
        self.assertEqual(history.district_key("AK-AL"), ("AK", "00", "AK-AL"))
        self.assertEqual(history.district_key("AK-00"), ("AK", "00", "AK-AL"))
        self.assertEqual(history.district_key("AL-1"), ("AL", "01", "AL-01"))
        self.assertEqual(history.district_key("AK-1")[1], "01")
        for value in ["XX-01", "DC-AL", "AL", "AL--1", "AL-100", "AL-X", "AL-1.0"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                history.district_key(value)

    def test_two_header_groups_counts_and_precision(self):
        rows, _ = self.normalize()
        self.assertEqual(len(rows), 4)
        alaska = {r["election_year"]: r for r in rows if r["state"] == "AK"}
        self.assertEqual(alaska["2024"]["dem_votes"], "400")
        self.assertEqual(alaska["2024"]["total_votes"], "1000")
        self.assertEqual(alaska["2024"]["dem_margin_pp"], "-20.00")
        self.assertEqual(alaska["2020"]["dem_margin_pp"], "20.00")
        self.assertEqual(alaska["2024"]["source_incumbent_label"], "Source incumbent")
        self.assertEqual(alaska["2024"]["source_id"], "test-pres")

    def test_bom_and_header_whitespace(self):
        self.pres.write_text("\ufeff" + self.pres.read_text().replace("District,", " District ,", 1))
        self.sources["presidential"]["sha256"] = hashlib.sha256(self.pres.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(dict(schema_version=1, sources=self.sources)))
        self.assertEqual(len(self.normalize()[0]), 4)

    def test_duplicate_keys_show_source_rows(self):
        self.pres_rows.append(["AK-00", *self.pres_rows[2][1:]])
        self.save_sources()
        with self.assertRaisesRegex(ValueError, "duplicate normalized key.*rows 3 and 5"):
            self.normalize()
        self.pres_rows.pop()
        self.cook_rows.append(["AK-00", *self.cook_rows[1][1:]])
        self.save_sources()
        with self.assertRaisesRegex(ValueError, "duplicate normalized key"):
            self.normalize()

    def test_invalid_values_and_disagreement(self):
        original = copy.deepcopy(self.pres_rows)
        for index, value in [(3, "-1"), (3, "NaN"), (3, "1,00"), (5, "0"), (5, "900"),
                             (6, "101%"), (6, "39%"), (8, "-101%"), (8, "NaN"), (8, "-10%")]:
            self.pres_rows = copy.deepcopy(original)
            self.pres_rows[2][index] = value
            self.save_sources()
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                self.normalize()

    def test_missing_not_zero_and_rounding_tolerance(self):
        self.pres_rows[2][8] = ""
        self.save_sources()
        rows, _ = self.normalize()
        margins = {(r["district_id"], r["election_year"]): r["dem_margin_pp"] for r in rows}
        self.assertEqual(margins["AK-AL", "2024"], "")
        self.assertEqual(margins["AL-01", "2024"], "0.00")
        self.pres_rows[2][8] = "-20.01%"
        self.save_sources()
        self.assertEqual(len(self.normalize()[0]), 4)

    def test_published_2026_pvi_instead_of_2025(self):
        _, rows = self.normalize()
        self.assertEqual(rows[0]["cook_pvi_label"], "D+4")
        self.assertEqual(rows[0]["cook_pvi_dem_lean_pp"], "4")
        self.assertEqual(rows[1]["cook_pvi_label"], "EVEN")
        self.assertEqual(rows[1]["cook_pvi_dem_lean_pp"], "0")
        self.assertEqual(history.pvi_lean("R+3", "test"), "-3")
        self.assertEqual(history.pvi_lean("", "test"), "")
        for label in ["D+0", "R+0", "0", "D+1.5", "D+51", "unknown"]:
            with self.subTest(label=label), self.assertRaises(ValueError):
                history.pvi_lean(label, "test")
        self.cook_rows[1][4] = ""
        self.save_sources()
        self.assertEqual(self.normalize()[1][0]["cook_pvi_label"], "")

    def test_schema_and_separator_validation(self):
        original = copy.deepcopy(self.pres_rows)
        for change in ["header", "separator", "width"]:
            self.pres_rows = copy.deepcopy(original)
            if change == "header":
                self.pres_rows[1][3] = "Wrong"
            elif change == "separator":
                self.pres_rows[2][9] = "Unexpected"
            else:
                self.pres_rows[2].pop()
            self.save_sources()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.normalize()
        self.pres_rows = original
        self.cook_rows[0][4] = "Wrong PVI"
        self.save_sources()
        with self.assertRaisesRegex(ValueError, "expected columns"):
            self.normalize()

    def test_source_validation_and_safe_failure(self):
        self.normalize()
        before = {p.name: p.read_bytes() for p in self.normalized.iterdir()}
        self.pres.write_text(self.pres.read_text() + "changed")
        with self.assertRaisesRegex(ValueError, "stale SHA-256"):
            self.normalize()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.normalized.iterdir()})
        self.sources["cook_pvi"]["edition"] = "2025"
        self.save_sources()
        with self.assertRaisesRegex(ValueError, "contradictory"):
            self.normalize()
        self.sources["cook_pvi"]["edition"] = "2026"
        self.sources["cook_pvi"]["path"] = "../outside.csv"
        self.save_sources_for_invalid_path()
        with self.assertRaisesRegex(ValueError, "inside project"):
            self.normalize()

    def save_sources_for_invalid_path(self):
        self.manifest.write_text(json.dumps(dict(schema_version=1, sources=self.sources)))

    def test_committed_snapshot(self):
        _, presidential, pvi = history.normalized_sources()
        self.assertEqual(len(presidential), 870)
        self.assertEqual(len(pvi), 435)
        self.assertEqual(next(r for r in presidential if r["district_id"] == "AK-AL" and r["election_year"] == "2024")["dem_margin_pp"], "-13.14")
        self.assertEqual(next(r for r in pvi if r["district_id"] == "CA-13")["cook_pvi_label"], "D+2")


if __name__ == "__main__":
    unittest.main()
