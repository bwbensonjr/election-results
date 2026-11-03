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

    def boundary_entry(self, state="AK", **updates):
        entry = dict(state=state, plan_2026="Fixture 2026 plan", evidence=["https://example.test/map"],
                     reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")
        entry.update(updates)
        return entry

    def save_boundary(self, *entries):
        (self.root / "boundary.json").write_text(json.dumps(dict(schema_version=1, states=list(entries))))
        data = json.loads(self.manifest.read_text())
        data["reviewed_inputs"] = {"boundary_vintage": dict(path="boundary.json", notes="Fixture registry")}
        self.manifest.write_text(json.dumps(data))


class BoundaryVintageTests(HistoryFixture):
    def review(self):
        with (self.normalized / "boundary-review.csv").open(newline="") as stream:
            return list(csv.DictReader(stream))

    def test_check_flags_unlisted_disagreement_and_still_publishes(self):
        # National margins sum to -10 (2024) and +20 (2020). AK implies (0 - 10) / 4 = -2.5
        # against a published D+4, a 6.5-point gap; AL implies 2.5 against EVEN.
        self.normalize()
        rows = self.review()
        self.assertEqual([(r["district_id"], r["implied_dem_lean_pp"], r["difference_pp"]) for r in rows],
                         [("AK-AL", "-2.5", "6.5")])
        self.assertTrue((self.normalized / "presidential-results-normalized.csv").exists())

    def test_listed_state_is_not_reported(self):
        self.save_boundary(self.boundary_entry())
        self.normalize()
        self.assertEqual(self.review(), [])
        self.assertEqual(set(history.load_boundary_vintage(self.manifest, self.root)), {"AK"})

    def test_manifest_without_registry_has_no_redrawn_states(self):
        self.assertEqual(history.load_boundary_vintage(self.manifest, self.root), {})

    def test_invalid_entries_fail_and_preserve_outputs(self):
        self.normalize()
        before = {p.name: p.read_bytes() for p in self.normalized.glob("*.csv")}
        for entries, message in [([self.boundary_entry(state="XX")], "unknown state"),
                                 ([self.boundary_entry(), self.boundary_entry()], "duplicate state"),
                                 ([self.boundary_entry(evidence=[])], "evidence"),
                                 ([self.boundary_entry(reviewed_by="")], "reviewed_by"),
                                 ([self.boundary_entry(reviewed_at="yesterday")], "Invalid isoformat")]:
            self.save_boundary(*entries)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.normalize()
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.normalized.glob("*.csv")})

    def test_committed_registry_explains_every_flagged_state(self):
        _, rows, pvi = history.normalized_sources()
        registry = history.load_boundary_vintage()
        flagged = {r["state"] for r in history.boundary_review(rows, pvi, {})}
        self.assertEqual(flagged, set(registry))
        self.assertEqual(history.boundary_review(rows, pvi, registry), [])


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

    def test_committed_state_snapshot(self):
        _, states, pvi = history.normalized_state_sources()
        self.assertEqual(len(states), 100)
        self.assertEqual({r["status"] for r in states}, {"available"})
        georgia = {r["election_year"]: r["dem_margin_pp"] for r in states if r["state"] == "GA"}
        self.assertEqual(georgia, {"2020": "0.24", "2024": "-2.19"})
        self.assertEqual(len(pvi), 51)
        self.assertEqual(next(r for r in pvi if r["state"] == "GA")["cook_pvi_dem_lean_pp"], "-1")
        self.assertEqual({r["pvi_edition"] for r in pvi}, {"2025"})

    def test_committed_snapshot(self):
        _, presidential, pvi = history.normalized_sources()
        self.assertEqual(len(presidential), 870)
        self.assertEqual(len(pvi), 435)
        self.assertEqual(next(r for r in presidential if r["district_id"] == "AK-AL" and r["election_year"] == "2024")["dem_margin_pp"], "-13.14")
        self.assertEqual(next(r for r in pvi if r["district_id"] == "CA-13")["cook_pvi_label"], "D+2")



class StateHistoryTests(HistoryFixture):
    def setUp(self):
        super().setUp()
        self.pres_rows.append(["AL-02", "Third incumbent", "(R)", "100", "300", "500", "20.00%", "60.00%", "-40.00%", "",
                               "200", "200", "500", "40.00%", "40.00%", "0.00%"])
        self.state_rows = [["State", "PVI"], ["Alaska", "R+6"], ["Alabama", "R+15"], ["Michigan", "EVEN"],
                           ["Washington, D.C.", "D+44"]]
        self.sources["cook_state_pvi"] = dict(
            source_id="test-state-pvi", path="state.csv", edition="2025", format="cook-state-pvi-two-column",
            election_years=[2020, 2024], notes="Latest state edition", source_url="https://example.test",
            retrieved_at="2026-11-02", published_at="2025-03-06")
        self.candidates = self.root / "field.csv"
        self.field_districts = [("AK", "00"), ("AL", "01"), ("AL", "02")]
        self.save_all()

    def save_all(self):
        write_csv(self.root / "state.csv", self.state_rows)
        write_csv(self.candidates, [["state", "district", "name"]] + [[s, d, f"{s}{d}"] for s, d in self.field_districts])
        self.save_sources()

    def normalize(self):
        return history.normalize(self.manifest, self.normalized, self.root, self.candidates)

    def read(self, name):
        with (self.normalized / name).open(newline="") as stream:
            return list(csv.DictReader(stream))

    def test_multi_district_sum_and_at_large(self):
        self.normalize()
        rows = {(r["state"], r["election_year"]): r for r in self.read("state-presidential-normalized.csv")}
        alabama = rows[("AL", "2024")]
        # (500 + 100) - (500 + 300) over 1,000 + 500 votes, not an average of the district margins.
        self.assertEqual((alabama["dem_votes"], alabama["rep_votes"], alabama["total_votes"]), ("600", "800", "1500"))
        self.assertEqual(alabama["dem_margin_pp"], "-13.33")
        self.assertEqual((alabama["district_count"], alabama["status"]), ("2", "available"))
        self.assertEqual(rows[("AK", "2024")]["dem_margin_pp"], "-20.00")
        self.assertEqual(rows[("AK", "2020")]["dem_share_pct"], "60.00")

    def test_missing_district_counts_leave_state_blank(self):
        self.pres_rows[-1][10:13] = ["", "", ""]
        self.save_all()
        self.normalize()
        rows = {(r["state"], r["election_year"]): r for r in self.read("state-presidential-normalized.csv")}
        self.assertEqual((rows[("AL", "2020")]["status"], rows[("AL", "2020")]["dem_margin_pp"]), ("missing", ""))
        self.assertEqual(rows[("AL", "2020")]["missing_districts"], "02")
        self.assertEqual(rows[("AL", "2024")]["status"], "available")
        self.field_districts.append(("AL", "03"))
        self.save_all()
        self.normalize()
        rows = {(r["state"], r["election_year"]): r for r in self.read("state-presidential-normalized.csv")}
        self.assertEqual(rows[("AL", "2024")]["missing_districts"], "03")

    def test_state_pvi_labels(self):
        self.normalize()
        rows = {r["state"]: r for r in self.read("cook-state-pvi-normalized.csv")}
        self.assertEqual((rows["AK"]["cook_pvi_label"], rows["AK"]["cook_pvi_dem_lean_pp"]), ("R+6", "-6"))
        self.assertEqual(rows["MI"]["cook_pvi_dem_lean_pp"], "0")
        self.assertEqual(rows["DC"]["cook_pvi_dem_lean_pp"], "44")
        self.assertEqual(rows["AL"]["pvi_edition"], "2025")

    def test_invalid_state_sources_preserve_all_outputs(self):
        self.normalize()
        before = {p.name: p.read_bytes() for p in self.normalized.iterdir()}
        for rows, message in [(self.state_rows + [["Alaska", "R+5"]], "duplicate state AK"),
                              (self.state_rows + [["Guam", "R+1"]], "unknown state"),
                              (self.state_rows + [["Ohio", "R5"]], "invalid published PVI")]:
            with self.subTest(message=message):
                write_csv(self.root / "state.csv", rows)
                self.save_sources()
                with self.assertRaisesRegex(ValueError, message):
                    self.normalize()
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.normalized.iterdir()})
        self.save_all()
        write_csv(self.root / "state.csv", self.state_rows + [["Ohio", "R+5"]])
        with self.assertRaisesRegex(ValueError, "stale SHA-256"):
            self.normalize()
        self.sources["cook_state_pvi"]["edition"] = "2026"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "contradictory"):
            self.normalize()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.normalized.iterdir()})

    def test_district_outputs_unchanged_by_state_step(self):
        history.normalize(self.manifest, self.normalized, self.root)
        district_only = {p.name: p.read_bytes() for p in self.normalized.iterdir()}
        self.normalize()
        both = {p.name: p.read_bytes() for p in self.normalized.iterdir()}
        self.assertEqual(set(both) - set(district_only),
                         {"state-presidential-normalized.csv", "cook-state-pvi-normalized.csv"})
        self.assertEqual({k: both[k] for k in district_only}, district_only)


if __name__ == "__main__":
    unittest.main()
