import copy
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_incumbent_roster as roster
import district_history as history
import incumbent_roster

ROOT = Path(__file__).resolve().parents[1]
SENATORS = """<?xml version="1.0" encoding="UTF-8"?><contact_information>
<member><last_name>Ossoff</last_name><first_name>Jon</first_name><party>D</party><state>GA</state><class>Class II</class></member>
<member><last_name>Warnock</last_name><first_name>Raphael</first_name><party>D</party><state>GA</state><class>Class III</class></member>
<member><last_name>Husted</last_name><first_name>Jon</first_name><party>R</party><state>OH</state><class>Class III</class></member>
<member><last_name>Moreno</last_name><first_name>Bernie</first_name><party>R</party><state>OH</state><class>Class I</class></member>
</contact_information>"""
NGA = """<div class="current-governors__item__link">
  <small class="state">Georgia</small>
  Gov. Brian Kemp                </div>"""
WIKI = """{|
|-
|[[Governor of Georgia|Georgia]] ([[List of governors of Georgia|list]])
! scope="row" | {{sortname|Brian|Kemp}}
| style="background-color:{{party color|Republican Party (United States)}};" |
|-
|}"""


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = roster.default_paths(root)
        for path in self.paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(self.paths["house_field"], [["state", "district", "name", "party"],
                                              ["GA", "01", "Buddy Carter", "REP"], ["GA", "02", "Sanford Bishop", "DEM"],
                                              ["GA", "03", "New Person", "REP"], ["GA", "04", "Hank Johnson", "DEM"]])
        write_csv(self.paths["statewide_field"], [["state", "office", "race_id", "name", "party"],
                                                  ["GA", "Senate", "GA-SEN", "Jon Ossoff", "DEM"],
                                                  ["GA", "Governor", "GA-GOV", "Keisha Lance Bottoms", "DEM"],
                                                  ["OH", "Senate", "OH-SEN", "Jon Husted", "REP"]])
        write_csv(self.paths["cook"], [history.COOK_COLUMNS,
                                       ["GA-01", "Buddy Carter", "R", "R+9", "R+9", "1"],
                                       ["GA-02", "Sanford Bishop", "D", "D+1", "D+1", "2"],
                                       ["GA-03", "OPEN (Jack)", "R", "R+18", "R+18", "3"],
                                       ["GA-04", "VACANT (Johnson)", "D", "D+27", "D+27", "4"]])
        presidential = copy.deepcopy(history.PRESIDENTIAL_HEADERS)
        for district, name in [("GA-01", "Buddy Carter"), ("GA-02", "Someone Else"), ("GA-03", "Brian Jack"),
                               ("GA-04", "Hank Johnson")]:
            presidential.append([district, name, "(R)"] + [""] * 13)
        write_csv(self.paths["presidential"], presidential)
        self.paths["senators"].write_text(SENATORS)
        self.paths["nga"].write_text(NGA)
        self.paths["wikipedia"].write_text(WIKI)

    def test_seed_entries_and_review_report(self):
        entries, review = roster.seed(self.paths)
        by_key = {e["race_key"]: e for e in entries}
        self.assertEqual(sorted(by_key), ["GA-01", "GA-02", "GA-03", "GA-04", "GA-GOV", "GA-SEN", "OH-SEN"])
        self.assertEqual((by_key["GA-03"]["name"], by_key["GA-03"]["ballot_status_override"]), ("Brian Jack", "not_running"))
        self.assertEqual((by_key["GA-04"]["vacant"], by_key["GA-04"]["previous_party"]), (True, "D"))
        self.assertEqual((by_key["GA-SEN"]["name"], by_key["OH-SEN"]["name"]), ("Jon Ossoff", "Jon Husted"))
        self.assertEqual((by_key["GA-GOV"]["name"], by_key["GA-GOV"]["party"]), ("Brian Kemp", "R"))
        issues = {(r["race_key"], r["issue"]) for r in review}
        self.assertEqual(issues, {("GA-02", "cook_vs_presidential"), ("GA-04", "vacant"),
                                  ("GA-GOV", "incumbent_not_in_field"), ("OH-SEN", "special_election")})

    def test_seeded_roster_validates_against_its_fields(self):
        entries, _ = roster.seed(self.paths)
        path = Path(self.temp.name) / "roster.json"
        roster.write_roster(path, entries)
        races = {}
        _, rows = history.read_records(self.paths["house_field"])
        for row in rows:
            races.setdefault(history.district_key(f"{row['state']}-{row['district']}")[2], ("House", []))[1].append(row)
        loaded = incumbent_roster.load_roster(path, races, {"House"})
        self.assertEqual({k: v["status"] for k, v in loaded.items()},
                         {"GA-01": "running", "GA-02": "running", "GA-03": "not_running", "GA-04": ""})


class CommittedRosterTests(unittest.TestCase):
    def test_committed_roster_covers_every_race(self):
        data = json.loads((ROOT / "2026/roster/incumbent-roster.json").read_text())
        offices = [e["office"] for e in data["entries"]]
        self.assertEqual((offices.count("House"), offices.count("Senate"), offices.count("Governor")), (435, 35, 36))
        by_key = {e["race_key"]: e for e in data["entries"]}
        for key, name in [("VA-02", "Jen Kiggans"), ("NY-17", "Mike Lawler"), ("MA-09", "Bill Keating"),
                          ("AK-AL", "Nick Begich")]:
            self.assertEqual(by_key[key]["name"], name)

    def test_roster_source_snapshots_match_manifest(self):
        manifest = json.loads((ROOT / "2026/results/source-manifest.json").read_text())
        for name, source in manifest["roster_sources"].items():
            with self.subTest(source=name):
                digest = hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, source["sha256"])


if __name__ == "__main__":
    unittest.main()
