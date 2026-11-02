import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_field as candidates
import election_guide as guide

ROOT = Path(__file__).resolve().parents[1]
FIELD = [("KY", "06", "Ralph Alvarado", "REP"), ("KY", "06", "Zach Dembo", "DEM"),
         ("VA", "01", "Robert J. \"Rob\" Wittman", "REP"), ("VA", "01", "Shannon L. Taylor", "DEM"),
         ("AK", "00", "Nick Begich", "REP"), ("AK", "00", "Eric Hafner", "DEM"),
         ("IN", "01", "Frank J. Mrvan", "DEM"), ("IN", "01", "Barb Regnitz", "REP")]
MARKDOWN = """### KY-6 · Lexington (open, R)
Alvarado (R) v Dembo (D). **MEDIUM · VA-01** Wittman (R) v Taylor (D).
Alaska at-large AK-1 is mentioned too. Not a district: ZZ-9.
"""


def guide_row(district_id, **values):
    row = {column: "" for column in guide.GUIDE_COLUMNS}
    row.update(district_id=district_id, guide_watch_time_et="6:00", guide_section="Test", guide_role="battleground")
    row.update(values)
    return row


class GuideFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidates = self.root / "candidates.csv"
        self.markdown = self.root / "guide.md"
        self.csv = self.root / "guide.csv"
        rows = []
        for state, district, name, party in FIELD:
            row = {column: "" for column in candidates.FIELD_COLUMNS}
            row.update(state=state, district=district, name=name, party=party, fec_match_status="automatic")
            rows.append(row)
        self.write(self.candidates, candidates.FIELD_COLUMNS, rows)
        self.markdown.write_text(MARKDOWN, encoding="utf-8")
        self.rows = [guide_row("KY-06", guide_role="bellwether", guide_dem_name="Dembo", guide_rep_name="Alvarado"),
                     guide_row("VA-01", guide_watch_time_et="7:00", guide_role="wave_ladder",
                               guide_dem_win_tier="2018-style", guide_seat_signal="~235"),
                     guide_row("AK-AL", guide_watch_time_et="12:00+")]

    def write(self, path, columns, rows):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def load(self, columns=guide.GUIDE_COLUMNS):
        self.write(self.csv, columns, [{c: r.get(c, "") for c in columns} for r in self.rows])
        return guide.load_guide(self.csv, self.markdown, self.candidates)


class ValidationTests(GuideFixture):
    def test_valid_guide_and_at_large_normalization(self):
        loaded = self.load()
        self.assertEqual(sorted(k[2] for k in loaded), ["AK-AL", "KY-06", "VA-01"])
        self.assertEqual(loaded[("VA", "01", "VA-01")]["guide_seat_signal"], "~235")

    def test_missing_column(self):
        with self.assertRaisesRegex(ValueError, "expected columns"):
            self.load([c for c in guide.GUIDE_COLUMNS if c != "guide_note"])

    def test_controlled_values(self):
        for column, value in [("guide_role", "swing"), ("guide_dem_win_tier", "Wave"),
                              ("guide_watch_time_et", "6:30"), ("guide_watch_time_et", "")]:
            with self.subTest(column=column, value=value):
                original = self.rows[1][column]
                self.rows[1][column] = value
                with self.assertRaisesRegex(ValueError, f"row 3: invalid {column} {value!r}"):
                    self.load()
                self.rows[1][column] = original

    def test_canonical_unique_and_field_districts(self):
        self.rows[0]["district_id"] = "KY-6"
        with self.assertRaisesRegex(ValueError, "must be canonical 'KY-06'"):
            self.load()
        self.rows[0]["district_id"] = "KY-06"
        self.rows.append(guide_row("KY-06"))
        with self.assertRaisesRegex(ValueError, "duplicate district KY-06"):
            self.load()
        self.rows[-1] = guide_row("PA-18")
        with self.assertRaisesRegex(ValueError, "district PA-18 is not in the candidate field"):
            self.load()

    def test_markdown_district_set(self):
        self.markdown.write_text(MARKDOWN + "Also watch IN-1.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing from the CSV: IN-01"):
            self.load()
        self.markdown.write_text(MARKDOWN.replace("AK-1", "Alaska"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "absent from the guide: AK-AL"):
            self.load()

    def test_cli_reports_district(self):
        self.load()
        self.markdown.write_text(MARKDOWN + "IN-1\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/election_guide.py"), "--guide", str(self.csv),
                                 "--markdown", str(self.markdown), "--candidates", str(self.candidates)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Guide validation failed", result.stderr)
        self.assertIn("IN-01", result.stderr)


class NameCheckTests(GuideFixture):
    def test_name_check_outcomes(self):
        field = guide.field_districts(self.candidates)
        ky = field[("KY", "06", "KY-06")]
        self.assertEqual(guide.name_check(guide_row("KY-06", guide_dem_name="Dembo", guide_rep_name="Alvarado"), ky),
                         "matched")
        self.assertEqual(guide.name_check(guide_row("KY-06", guide_dem_name="McGrath", guide_rep_name="Alvarado"), ky),
                         "mismatch")
        self.assertEqual(guide.name_check(guide_row("KY-06", guide_dem_name="Alvarado"), ky), "mismatch")
        self.assertEqual(guide.name_check(guide_row("KY-06"), ky), "not_named")
        va = field[("VA", "01", "VA-01")]
        self.assertEqual(guide.name_check(guide_row("VA-01", guide_rep_name="Wittman"), va), "matched")


class CommittedGuideTests(unittest.TestCase):
    def setUp(self):
        self.guide = {k[2]: row for k, row in guide.load_guide().items()}

    def test_coverage(self):
        self.assertEqual(len(self.guide), 44)

    def test_spot_checks_against_guide_wording(self):
        ky = self.guide["KY-06"]
        self.assertEqual((ky["guide_watch_time_et"], ky["guide_role"], ky["guide_dem_win_tier"], ky["guide_seat_signal"]),
                         ("6:00", "bellwether", "2018-style", "230+"))
        self.assertEqual((ky["guide_dem_name"], ky["guide_rep_name"]), ("Dembo", "Alvarado"))
        self.assertIn("Trump +15 in 2024", ky["guide_rating_note"])
        self.assertIn("96%+", ky["guide_hell_yes"])
        va = self.guide["VA-01"]
        self.assertEqual((va["guide_role"], va["guide_dem_win_tier"], va["guide_seat_signal"]),
                         ("wave_ladder", "2018-style", "~235"))
        self.assertIn("~13 in 2024", va["guide_chill"])
        self.assertEqual(self.guide["IN-01"]["guide_watch_time_et"], "7:00")
        self.assertEqual(self.guide["VA-05"]["guide_dem_win_tier"], "Holy shit")
        for district in ["FL-14", "FL-25"]:
            row = self.guide[district]
            self.assertEqual(row["guide_role"], "majority_check")
            self.assertIn("near-certain House majority", row["guide_hell_yes"])
            self.assertIn("1 in 3", row["guide_ffs"])
        self.assertEqual(self.guide["CA-22"]["guide_watch_time_et"], "11:00")
        self.assertEqual(self.guide["MT-01"]["guide_watch_time_et"], "10:00")


if __name__ == "__main__":
    unittest.main()
