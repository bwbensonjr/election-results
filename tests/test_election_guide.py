import csv
import re
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


def race(state, district, office="House", **values):
    row = {column: "" for column in guide.RACE_COLUMNS}
    row.update(slot_et="6:00", poll_close_et="18:00", state=state, office=office, district=district, card="Test")
    row.update(values)
    return row


def guide_row(**values):
    row = {column: "" for column in guide.GUIDE_COLUMNS}
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
        self.rows = [race("KY", "06", incumbent_party="R", open_seat="True", dem_candidate="Dembo",
                          rep_candidate="Alvarado", trump_2024_margin="15"),
                     race("VA", "01", slot_et="7:00", poll_close_et="19:00", ladder_tier="2018-style",
                          dem_candidate="Taylor", rep_candidate="Wittman"),
                     race("AK", "00", slot_et="12:00+", poll_close_et="24:00"),
                     race("AK", "", office="Senate", slot_et="12:00+", poll_close_et="24:00",
                          silver_avg_dem_margin="3.5")]

    def write(self, path, columns, rows):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def load(self, columns=guide.RACE_COLUMNS):
        self.write(self.csv, columns, [{c: r.get(c, "") for c in columns} for r in self.rows])
        return guide.load_guide(self.csv, self.markdown, self.candidates)


class ValidationTests(GuideFixture):
    def test_valid_guide_keeps_house_rows_only(self):
        loaded = self.load()
        self.assertEqual(sorted(k[2] for k in loaded), ["AK-AL", "KY-06", "VA-01"])
        va = loaded[("VA", "01", "VA-01")]
        self.assertEqual(list(va), guide.GUIDE_COLUMNS)
        self.assertEqual((va["guide_slot_et"], va["guide_ladder_tier"]), ("7:00", "2018-style"))

    def test_missing_column(self):
        with self.assertRaisesRegex(ValueError, "expected columns"):
            self.load([c for c in guide.RACE_COLUMNS if c != "notes"])

    def test_controlled_values(self):
        for column, value in [("office", "Mayor"), ("ladder_tier", "Wave"), ("slot_et", "6:30"),
                              ("slot_et", ""), ("poll_close_et", "7pm"), ("incumbent_party", "Dem"),
                              ("open_seat", "yes"), ("trump_2024_margin", "R+5")]:
            with self.subTest(column=column, value=value):
                original = self.rows[1][column]
                self.rows[1][column] = value
                with self.assertRaisesRegex(ValueError, re.escape(f"row 3: invalid {column} {value!r}")):
                    self.load()
                self.rows[1][column] = original

    def test_district_only_on_house_rows(self):
        self.rows[3]["district"] = "01"
        with self.assertRaisesRegex(ValueError, "row 5: district must be set for House races"):
            self.load()
        self.rows[3]["district"] = ""
        self.rows[1]["district"] = ""
        with self.assertRaisesRegex(ValueError, "row 3: district must be set for House races"):
            self.load()

    def test_canonical_unique_and_field_districts(self):
        self.rows[0]["district"] = "6"
        with self.assertRaisesRegex(ValueError, "district '6' must be canonical '06'"):
            self.load()
        self.rows[0]["district"] = "06"
        self.rows.append(race("KY", "06"))
        with self.assertRaisesRegex(ValueError, "duplicate district KY-06"):
            self.load()
        self.rows[-1] = race("PA", "18")
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
        self.assertEqual(guide.name_check(guide_row(guide_dem_candidate="Dembo", guide_rep_candidate="Alvarado"), ky),
                         "matched")
        self.assertEqual(guide.name_check(guide_row(guide_dem_candidate="McGrath", guide_rep_candidate="Alvarado"), ky),
                         "mismatch")
        self.assertEqual(guide.name_check(guide_row(guide_dem_candidate="Alvarado"), ky), "mismatch")
        self.assertEqual(guide.name_check(guide_row(), ky), "not_named")
        va = field[("VA", "01", "VA-01")]
        self.assertEqual(guide.name_check(guide_row(guide_rep_candidate="Wittman"), va), "matched")


class CommittedGuideTests(unittest.TestCase):
    def setUp(self):
        self.guide = {k[2]: row for k, row in guide.load_guide().items()}

    def test_coverage(self):
        self.assertEqual(len(self.guide), 44)

    def test_spot_checks_against_races_csv(self):
        ky = self.guide["KY-06"]
        self.assertEqual((ky["guide_slot_et"], ky["guide_poll_close_et"], ky["guide_ladder_tier"],
                          ky["guide_open_seat"], ky["guide_trump_2024_margin"]),
                         ("6:00", "18:00", "2018-style", "True", "15"))
        self.assertEqual((ky["guide_dem_candidate"], ky["guide_rep_candidate"]), ("Dembo", "Alvarado"))
        self.assertIn("96%+", ky["guide_hell_yes"])
        va = self.guide["VA-01"]
        self.assertEqual((va["guide_ladder_tier"], va["guide_rating"]), ("2018-style", "Cook Toss-up"))
        self.assertIn("~13 in 2024", va["guide_chill"])
        self.assertEqual((self.guide["IN-01"]["guide_slot_et"], self.guide["IN-01"]["guide_poll_close_et"]),
                         ("6:00", "19:00"))
        self.assertEqual(self.guide["VA-02"]["guide_ladder_tier"], "We'll take it")
        for district in ["FL-14", "FL-25"]:
            self.assertIn("near-certain House majority", self.guide[district]["guide_hell_yes"])
        self.assertEqual(self.guide["CA-22"]["guide_poll_close_et"], "23:00")
        self.assertEqual(self.guide["MT-01"]["guide_slot_et"], "10 to 11")



class StatewideGuideTests(GuideFixture):
    def setUp(self):
        super().setUp()
        import build_statewide_field as statewide
        self.statewide = self.root / "statewide.csv"
        rows = []
        for state, office, name, party in [("AK", "Senate", "Mary Peltola", "DEM"), ("AK", "Senate", "Dan Sullivan", "REP"),
                                           ("NE", "Senate", "Pete Ricketts", "REP"), ("NE", "Senate", "Dan Osborn", "OTHER"),
                                           ("GA", "Governor", "Rick Jackson", "REP")]:
            row = {column: "" for column in statewide.FIELD_COLUMNS}
            row.update(state=state, office=office, race_id=statewide.race_id(state, office), name=name, party=party)
            rows.append(row)
        self.write(self.statewide, statewide.FIELD_COLUMNS, rows)

    def load_statewide(self):
        self.write(self.csv, guide.RACE_COLUMNS, self.rows)
        return guide.load_statewide_guide(self.csv, self.statewide)

    def test_statewide_rows_join_by_race_id(self):
        self.rows.append(race("NE", "", office="Senate", slot_et="9:00", poll_close_et="21:00",
                              rep_candidate="Ricketts", other_candidate="Osborn (I)", senate_path="Wildcard"))
        loaded = self.load_statewide()
        self.assertEqual(set(loaded), {"AK-SEN", "NE-SEN"})
        self.assertEqual(loaded["NE-SEN"]["guide_senate_path"], "Wildcard")
        self.assertEqual(loaded["AK-SEN"]["guide_silver_avg_dem_margin"], "3.5")
        # House validation is unchanged by the statewide rows.
        self.assertEqual(set(self.load()), {("KY", "06", "KY-06"), ("VA", "01", "VA-01"), ("AK", "00", "AK-AL")})

    def test_duplicate_senate_row(self):
        self.rows.append(race("AK", "", office="Senate", slot_et="12:00+", poll_close_et="24:00"))
        with self.assertRaisesRegex(ValueError, "duplicate Senate row for AK"):
            self.load_statewide()

    def test_unknown_governor_race(self):
        self.rows.append(race("KY", "", office="Governor", slot_et="6:00", poll_close_et="18:00"))
        with self.assertRaisesRegex(ValueError, "KY Governor race KY-GOV is not in the statewide field"):
            self.load_statewide()

    def test_statewide_name_check(self):
        field = [dict(name="Pete Ricketts", party="REP"), dict(name="Dan Osborn", party="OTHER")]
        row = {column: "" for column in guide.STATEWIDE_GUIDE_COLUMNS}
        self.assertEqual(guide.statewide_name_check(dict(row, guide_rep_candidate="Ricketts",
                                                         guide_other_candidate="Osborn (I)"), field), "matched")
        self.assertEqual(guide.statewide_name_check(dict(row, guide_dem_candidate="Osborn"), field), "mismatch")
        self.assertEqual(guide.statewide_name_check(row, field), "not_named")

    def test_committed_statewide_rows_validate(self):
        loaded = guide.load_statewide_guide()
        self.assertEqual(len(loaded), 18)
        self.assertEqual(sum(r.endswith("-SEN") for r in loaded), 14)


if __name__ == "__main__":
    unittest.main()
