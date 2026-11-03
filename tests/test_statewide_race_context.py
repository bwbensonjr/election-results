import copy
import csv
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_statewide_field as statewide_field
import build_statewide_poll_averages as polls
import build_statewide_race_context as context
import district_history as history
import election_guide as guide

ROOT = Path(__file__).resolve().parents[1]
POLL_COLUMNS = polls.REQUIRED_COLUMNS + ["ranked_choice_round", "seat_number"]
FIELD = [
    ("GA", "Senate", "Jon Ossoff", "DEM", "automatic"), ("GA", "Senate", "Mike Collins", "REP", "automatic"),
    ("GA", "Senate", "Minor Person", "OTHER", "unmatched"),
    ("GA", "Governor", "Keisha Lance Bottoms", "DEM", "not_federal"),
    ("GA", "Governor", "Rick Jackson", "REP", "not_federal"),
    ("NE", "Senate", "Pete Ricketts", "REP", "automatic"), ("NE", "Senate", "Dan Osborn", "OTHER", "automatic"),
    ("AK", "Senate", "Mary Peltola", "DEM", "reviewed"), ("AK", "Senate", "Dan Sullivan", "REP", "reviewed"),
]
DISTRICTS = [["AK-AL", "400", "600", "1,000"], ["GA-01", "500", "500", "1,000"], ["GA-02", "100", "300", "500"],
             ["NE-01", "300", "600", "1,000"]]


def write_csv(path, rows, columns=None):
    with path.open("w", newline="", encoding="utf-8") as stream:
        if columns:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        else:
            csv.writer(stream, lineterminator="\n").writerows(rows)


def answer(question, party, name, pct, state="GA", **fields):
    row = dict(poll_id=f"poll-{question}", question_id=question, pollster="Pollster A", state=state,
               end_date="10/01/26", sample_size="600", population="lv", partisan="", cycle="2026", stage="general",
               seat_number="", party=party, candidate_name=name, pct=str(pct), ranked_choice_reallocated="FALSE",
               ranked_choice_round="")
    row.update(fields)
    return row


def guide_race(state, office, **values):
    row = dict.fromkeys(guide.RACE_COLUMNS, "")
    row.update(slot_et="7:00", poll_close_et="19:00", state=state, office=office, card="Test")
    row.update(values)
    return row


class ContextFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = self.root / "results"
        self.output = self.root / "statewide"
        self.paths = {"Senate": self.root / "senate.csv", "Governor": self.root / "governor.csv"}
        self.field_rows = copy.deepcopy(FIELD)
        self.state_pvi = [["State", "PVI"], ["Alaska", "R+6"], ["Georgia", "R+1"], ["Nebraska", "R+10"]]
        self.senate = [answer("q1", "DEM", "Jon Ossoff", 50), answer("q1", "REP", "Mike Collins", 44),
                       answer("q2", "DEM", "Dan Osborn", 46, "NE"), answer("q2", "REP", "Pete Ricketts", 48, "NE")]
        self.guide_rows = [guide_race("GA", "Senate", dem_candidate="Ossoff", rep_candidate="Mike Collins",
                                      senate_path="Hold"),
                           guide_race("NE", "Senate", slot_et="9:00", poll_close_et="21:00", rep_candidate="Ricketts",
                                      other_candidate="Osborn (I)", senate_path="Wildcard")]
        self.save_all()

    def save_all(self, rebuild=True):
        pres = copy.deepcopy(history.PRESIDENTIAL_HEADERS)
        for label, dem, rep, total in DISTRICTS:
            share = lambda v: f"{100 * int(v) / int(total.replace(',', '')):.2f}%"
            margin = f"{100 * (int(dem) - int(rep)) / int(total.replace(',', '')):.2f}%"
            pres.append([label, "Incumbent", "(R)", dem, rep, total, share(dem), share(rep), margin, "",
                         dem, rep, total, share(dem), share(rep), margin])
        write_csv(self.root / "pres.csv", pres)
        write_csv(self.root / "cook.csv", [history.COOK_COLUMNS] + [[d[0], "X", "R", "R+1", "R+1", "1"] for d in DISTRICTS])
        write_csv(self.root / "state.csv", self.state_pvi)
        sources = {
            "presidential": dict(source_id="test-pres", path="pres.csv", edition="test", format="presidential-two-header",
                                 election_years=[2020, 2024], notes="Fixture"),
            "cook_pvi": dict(source_id="test-cook", path="cook.csv", edition="2026", format="cook-pvi-six-column",
                             election_years=[2020, 2024], notes="Fixture"),
            "cook_state_pvi": dict(source_id="test-state-pvi", path="state.csv", edition="2025",
                                   format="cook-state-pvi-two-column", election_years=[2020, 2024], notes="Fixture"),
        }
        for source in sources.values():
            source["sha256"] = hashlib.sha256((self.root / source["path"]).read_bytes()).hexdigest()
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(dict(schema_version=1, sources=sources)))
        self.house = self.root / "house.csv"
        write_csv(self.house, [dict(state=d[0][:2], district=history.district_key(d[0])[1], name="x") for d in DISTRICTS],
                  ["state", "district", "name"])
        self.field = self.root / "field.csv"
        rows = []
        for state, office, name, party, status in self.field_rows:
            row = dict.fromkeys(statewide_field.FIELD_COLUMNS, "")
            row.update(state=state, office=office, race_id=statewide_field.race_id(state, office), name=name,
                       party=party, fec_match_status=status)
            rows.append(row)
        write_csv(self.field, rows, statewide_field.FIELD_COLUMNS)
        write_csv(self.paths["Senate"], self.senate, POLL_COLUMNS)
        write_csv(self.paths["Governor"], [], POLL_COLUMNS)
        self.matchups = self.root / "matchups.json"
        self.matchups.write_text(json.dumps(dict(schema_version=1, matchups=[dict(
            race_id="NE-SEN", principal_candidate="Dan Osborn", evidence=["fixture"], rationale="No Democrat",
            reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")])))
        self.guide = self.root / "guide.csv"
        write_csv(self.guide, self.guide_rows, guide.RACE_COLUMNS)
        if rebuild:
            history.normalize(self.manifest, self.results, self.root, self.house)
            polls.build(self.paths, self.field, self.matchups, self.root)

    def build(self, strict=False):
        return context.build(self.field, self.manifest, self.house, self.results / "state-presidential-normalized.csv",
                             self.results / "cook-state-pvi-normalized.csv", self.paths,
                             self.root / "statewide-poll-averages.csv", self.matchups, self.guide, self.output,
                             strict, self.root)

    def output_bytes(self):
        return {p.name: p.read_bytes() for p in self.output.iterdir()}


class StatewideContextTests(ContextFixture):
    def test_state_metrics_shared_and_grain_preserved(self):
        races, candidates, issues = self.build()
        by_race = {r["race_id"]: r for r in races}
        self.assertEqual(list(by_race), ["AK-SEN", "GA-GOV", "GA-SEN", "NE-SEN"])
        georgia = [{c: by_race[r][c] for c in context.METRIC_COLUMNS + context.STATUS_COLUMNS} for r in ["GA-SEN", "GA-GOV"]]
        self.assertEqual(georgia[0], georgia[1])
        # (500 + 100 - 500 - 300) / 1,500 votes.
        self.assertEqual(by_race["GA-SEN"]["pres_2024_dem_margin_pp"], "-13.33")
        self.assertEqual((by_race["GA-SEN"]["cook_pvi_label"], by_race["GA-SEN"]["cook_pvi_edition"]), ("R+1", "2025"))
        self.assertEqual((by_race["GA-SEN"]["candidate_count"], by_race["GA-SEN"]["unresolved_fec_candidate_count"]),
                         ("3", "1"))
        self.assertEqual(by_race["GA-GOV"]["unresolved_fec_candidate_count"], "0")
        self.assertEqual(len(candidates), len(FIELD))
        minor = next(r for r in candidates if r["name"] == "Minor Person")
        self.assertEqual((minor["fec_match_status"], minor["pres_2024_dem_margin_pp"]), ("unmatched", "-13.33"))
        self.assertEqual(list(minor)[:len(statewide_field.FIELD_COLUMNS)], statewide_field.FIELD_COLUMNS)
        self.assertEqual(issues, [])

    def test_polling_and_guide_values_copied(self):
        races, candidates, _ = self.build()
        by_race = {r["race_id"]: r for r in races}
        with (self.root / "statewide-poll-averages.csv").open(newline="") as stream:
            averages = {r["race_id"]: r for r in csv.DictReader(stream)}
        for row in [by_race["GA-SEN"]] + [r for r in candidates if r["race_id"] == "GA-SEN"]:
            self.assertEqual({c: row[c] for c in polls.POLL_COLUMNS},
                             {c: averages["GA-SEN"][c] for c in polls.POLL_COLUMNS})
        self.assertEqual(by_race["GA-SEN"]["poll_avg_dem_margin_pp"], "6.00")
        self.assertEqual((by_race["GA-SEN"]["guide_status"], by_race["GA-SEN"]["guide_senate_path"]), ("in_guide", "Hold"))
        self.assertEqual((by_race["NE-SEN"]["guide_name_check"], by_race["NE-SEN"]["poll_avg_matchup_basis"]),
                         ("matched", "reviewed"))
        self.assertEqual((by_race["GA-GOV"]["guide_status"], by_race["GA-GOV"]["guide_card"]), ("not_in_guide", ""))
        self.assertEqual(by_race["GA-GOV"]["poll_avg_status"], "no_polls")

    def test_missing_state_pvi_issue_and_strict_failure(self):
        self.state_pvi = [row for row in self.state_pvi if row[0] != "Georgia"]
        self.save_all()
        races, _, issues = self.build()
        georgia = [r for r in races if r["state"] == "GA"]
        self.assertEqual({(r["cook_pvi_label"], r["cook_pvi_status"]) for r in georgia}, {("", "missing")})
        self.assertEqual([(i["race_id"], i["metric"], i["issue"]) for i in issues],
                         [("GA-GOV", "cook_pvi", "missing_state"), ("GA-SEN", "cook_pvi", "missing_state")])
        before = self.output_bytes()
        with self.assertRaisesRegex(ValueError, "incomplete statewide context: 2 missing"):
            self.build(strict=True)
        self.assertEqual(self.output_bytes(), before)

    def test_strict_build_passes_with_unpolled_and_unguided_races(self):
        races, _, issues = self.build(strict=True)
        self.assertEqual(issues, [])
        self.assertIn("no_polls", {r["poll_avg_status"] for r in races})
        self.assertIn("not_in_guide", {r["guide_status"] for r in races})

    def test_stale_inputs_fail_and_preserve_exports(self):
        self.build()
        before = self.output_bytes()
        self.senate.append(answer("q3", "DEM", "Jon Ossoff", 40))
        self.senate.append(answer("q3", "REP", "Mike Collins", 52))
        self.save_all(rebuild=False)
        with self.assertRaisesRegex(ValueError, "run build_statewide_poll_averages.py"):
            self.build()
        self.assertEqual(self.output_bytes(), before)
        self.save_all()
        (self.results / "cook-state-pvi-normalized.csv").write_text(
            (self.results / "cook-state-pvi-normalized.csv").read_text().replace("R+10,-10", "R+9,-9"))
        with self.assertRaisesRegex(ValueError, "run normalize_district_history.py"):
            self.build()

    def test_guide_validation_gates_publication(self):
        self.build()
        before = self.output_bytes()
        self.guide_rows.append(guide_race("KY", "Governor"))
        self.save_all()
        with self.assertRaisesRegex(ValueError, "KY-GOV is not in the statewide field"):
            self.build()
        self.assertEqual(self.output_bytes(), before)

    def test_reordered_inputs_are_deterministic(self):
        self.build()
        before = self.output_bytes()
        rng = random.Random(5)
        for rows in (self.field_rows, self.senate, self.guide_rows):
            rng.shuffle(rows)
        self.save_all()
        self.build()
        self.assertEqual(self.output_bytes(), before)

    def test_committed_snapshot_cardinality(self):
        with (ROOT / "2026/statewide/statewide-race-context.csv").open(newline="") as stream:
            races = list(csv.DictReader(stream))
        with (ROOT / "2026/statewide/statewide-candidate-context.csv").open(newline="") as stream:
            candidates = list(csv.DictReader(stream))
        self.assertEqual(len(races), 71)
        self.assertEqual(len({r["race_id"] for r in races}), 71)
        self.assertEqual(len(candidates), 260)
        self.assertEqual(sum(r["guide_status"] == "in_guide" for r in races), 18)
        self.assertEqual({r["cook_pvi_status"] for r in races} | {r["pres_2024_status"] for r in races}, {"available"})


if __name__ == "__main__":
    unittest.main()
