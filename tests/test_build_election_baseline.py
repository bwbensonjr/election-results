import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_election_baseline as baseline

ROOT = Path(__file__).resolve().parents[1]


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def output_bytes(self, directory):
        return {p.name: p.read_bytes() for p in directory.iterdir()}

    def test_committed_snapshot_rows_keys_and_metrics(self):
        races, candidates = baseline.build(output_dir=self.root / "out")
        self.assertEqual(len(races), 506)
        self.assertEqual(len({r["race_key"] for r in races}), 506)
        by_key = {r["race_key"]: r for r in races}
        self.assertEqual([by_key["VA-01"][c] for c in ["state_postal", "ap_office_id", "ap_seat_num", "ap_race_id"]],
                         ["VA", "H", "1", ""])
        self.assertEqual([by_key["GA-SEN"][c] for c in ["state_postal", "ap_office_id", "ap_seat_num", "ap_race_id"]],
                         ["GA", "S", "", ""])
        self.assertEqual((by_key["UT-01"]["pres_2024_dem_margin_pp"], by_key["UT-01"]["pres_2024_status"],
                          by_key["UT-01"]["cook_pvi_label"]), ("7.50", "interpolated", "D+12"))
        self.assertEqual((by_key["TN-05"]["pres_2024_dem_margin_pp"], by_key["TN-05"]["pres_2024_status"],
                          by_key["TN-05"]["cook_pvi_label"]), ("", "prior_boundaries", "R+10"))
        self.assertEqual((by_key["MA-04"]["pres_2024_dem_margin_pp"], by_key["MA-04"]["pres_2024_status"]),
                         ("19.72", "available"))
        self.assertNotIn("pres_2020_dem_margin_pp", baseline.RACE_COLUMNS)
        alaska = {c["name"]: c for c in candidates if c["race_key"] == "AK-AL"}
        self.assertEqual(alaska["Bill Hill"]["poll_principal"], "True")
        self.assertEqual(alaska["James C. \"Jim\" McDermott"]["source_correction"], "AK-AL-hill-mcdermott")
        self.assertEqual(alaska["Nick Begich"]["roster_incumbent"], "True")
        self.assertTrue(all(c["ap_candidate_id"] == "" for c in candidates))

    def test_rebuild_is_byte_identical_and_json_matches_csv(self):
        out = self.root / "out"
        baseline.build(output_dir=out)
        before = self.output_bytes(out)
        baseline.build(output_dir=out)
        self.assertEqual(before, self.output_bytes(out))
        document = json.loads((out / "election-baseline.json").read_text())
        with (out / "race-baseline.csv").open(newline="") as stream:
            self.assertEqual(document["races"], list(csv.DictReader(stream)))
        self.assertEqual(set(document["input_sha256"]), set(baseline.INPUTS))
        self.assertNotIn("built_at", document)

    def test_stale_context_export_fails_without_replacing_outputs(self):
        house, statewide, out = self.root / "house", self.root / "statewide", self.root / "out"
        shutil.copytree(baseline.HOUSE_DIR, house)
        shutil.copytree(baseline.STATEWIDE_DIR, statewide)
        baseline.build(house, statewide, out)
        before = self.output_bytes(out)
        path = house / "house-district-context.csv"
        path.write_text(path.read_text().replace("Nick Begich", "Someone Else", 1))
        with self.assertRaisesRegex(ValueError, "stale context export"):
            baseline.build(house, statewide, out)
        self.assertEqual(before, self.output_bytes(out))

    def test_duplicate_race_key_fails(self):
        house, statewide = self.root / "house", self.root / "statewide"
        shutil.copytree(baseline.HOUSE_DIR, house)
        shutil.copytree(baseline.STATEWIDE_DIR, statewide)
        path = statewide / "statewide-race-context.csv"
        lines = path.read_text().splitlines(keepends=True)
        path.write_text("".join(lines + [lines[1]]))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            baseline.build(house, statewide, self.root / "out", verify=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
