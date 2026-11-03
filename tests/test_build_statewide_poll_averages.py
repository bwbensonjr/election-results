import csv
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_field as house_field
import build_house_poll_averages as house_polls
import build_statewide_field as statewide_field
import build_statewide_poll_averages as polls

POLL_COLUMNS = polls.REQUIRED_COLUMNS + ["ranked_choice_round", "seat_number"]
FIELD = [
    ("GA", "Senate", "Jon Ossoff", "DEM"), ("GA", "Senate", "Mike Collins", "REP"),
    ("GA", "Governor", "Keisha Lance Bottoms", "DEM"), ("GA", "Governor", "Rick Jackson", "REP"),
    ("NE", "Senate", "Pete Ricketts", "REP"), ("NE", "Senate", "Dan Osborn", "OTHER"),
    ("AK", "Senate", "Mary Peltola", "DEM"), ("AK", "Senate", "Dan Sullivan", "REP"),
    ("AK", "Senate", "Daniel J. Sullivan Jr.", "REP"),
    ("WY", "Senate", "James Byrd", "DEM"), ("WY", "Senate", "Harriet Hageman", "REP"),
]
OSBORN = dict(race_id="NE-SEN", principal_candidate="Dan Osborn", evidence=["https://example.test"],
              rationale="No Democrat", reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")
SULLIVAN = dict(OSBORN, race_id="AK-SEN", principal_candidate="Mary Peltola", republican_candidate="Dan Sullivan")


def answer(question, party, name, pct, state="GA", poll=None, **fields):
    row = dict(poll_id=poll or f"poll-{question}", question_id=question, pollster="Pollster A", state=state,
               end_date="10/01/26", sample_size="600", population="lv", partisan="", cycle="2026",
               stage="general", seat_number="", party=party, candidate_name=name, pct=str(pct),
               ranked_choice_reallocated="FALSE", ranked_choice_round="")
    row.update(fields)
    return row


def matchup(question, dem, rep, state="GA", dem_name="Jon Ossoff", rep_name="Mike Collins", poll=None, **fields):
    return [answer(question, "DEM", dem_name, dem, state, poll, **fields),
            answer(question, "REP", rep_name, rep, state, poll, **fields),
            answer(question, "NONE", "Undecided", 100 - dem - rep, state, poll, **fields)]


def write_csv(path, columns, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class StatewidePollTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {"Senate": self.root / "senate.csv", "Governor": self.root / "governor.csv"}
        self.candidates = self.root / "field.csv"
        self.matchups = self.root / "matchups.json"
        self.output = self.root / "out"
        rows = []
        for state, office, name, party in FIELD:
            row = dict.fromkeys(statewide_field.FIELD_COLUMNS, "")
            row.update(state=state, office=office, race_id=statewide_field.race_id(state, office), name=name,
                       party=party, fec_match_status="automatic")
            rows.append(row)
        write_csv(self.candidates, statewide_field.FIELD_COLUMNS, rows)
        self.senate, self.governor = [], []
        self.save_matchups([OSBORN, SULLIVAN])

    def save_matchups(self, entries):
        self.matchups.write_text(json.dumps(dict(schema_version=1, matchups=entries)))

    def build(self):
        write_csv(self.paths["Senate"], POLL_COLUMNS, self.senate)
        write_csv(self.paths["Governor"], POLL_COLUMNS, self.governor)
        averages, records = polls.build(self.paths, self.candidates, self.matchups, self.output)
        return {r["race_id"]: r for r in averages}, {(r["office"], r["question_id"]): r for r in records}

    def output_bytes(self):
        return {p.name: p.read_bytes() for p in self.output.iterdir()}

    def test_cycle_stage_and_unknown_race(self):
        self.governor += matchup("q1", 50, 45, state="VA", dem_name="Abigail Spanberger", rep_name="Winsome Sears",
                                 cycle="2025")
        self.governor += matchup("q2", 50, 45, dem_name="Keisha Lance Bottoms", rep_name="Rick Jackson",
                                 stage="primary")
        self.senate += matchup("q3", 50, 45, state="CA", dem_name="Someone Else", rep_name="Other Person")
        averages, log = self.build()
        self.assertEqual(log[("Governor", "q1")]["reason"], "out_of_cycle")
        self.assertEqual(log[("Governor", "q2")]["reason"], "not_general")
        self.assertEqual(log[("Senate", "q3")]["reason"], "unknown_race")
        self.assertEqual(averages["GA-GOV"]["poll_avg_status"], "no_polls")
        self.assertEqual(averages["GA-GOV"]["poll_avg_dem_margin_pp"], "")

    def test_reviewed_independent_with_mismatched_poll_party(self):
        # Nebraska polls code Osborn as DEM; the ballot lists him as an independent.
        self.senate += matchup("q1", 46, 48, state="NE", dem_name="Dan Osborn", rep_name="Pete Ricketts")
        averages, log = self.build()
        nebraska = averages["NE-SEN"]
        self.assertEqual(log[("Senate", "q1")]["included"], "True")
        self.assertEqual((nebraska["poll_avg_dem_candidate"], nebraska["poll_avg_matchup_basis"]),
                         ("Dan Osborn", "reviewed"))
        self.assertEqual(nebraska["poll_avg_dem_margin_pp"], "-2.00")

    def test_without_reviewed_entry_races_lack_a_principal(self):
        self.save_matchups([])
        self.senate += matchup("q1", 46, 48, state="NE", dem_name="Dan Osborn", rep_name="Pete Ricketts")
        averages, log = self.build()
        self.assertEqual(log[("Senate", "q1")]["reason"], "no_principal_matchup")
        for race in ["NE-SEN", "AK-SEN"]:
            self.assertEqual(averages[race]["poll_avg_status"], "no_principal_matchup")

    def test_stale_or_invalid_entries_fail_and_preserve_outputs(self):
        self.senate += matchup("q1", 50, 45)
        self.build()
        before = self.output_bytes()
        for entries, message in [([dict(OSBORN, principal_candidate="Absent Person")], "not in the race's field"),
                                 ([dict(OSBORN, race_id="OH-SEN")], "not in the statewide field"),
                                 ([dict(SULLIVAN, republican_candidate="")], "republican_candidate"),
                                 ([dict(OSBORN, principal_candidate="Pete Ricketts")], "must not be the Republican"),
                                 ([OSBORN, OSBORN], "duplicate race")]:
            with self.subTest(message=message):
                self.save_matchups(entries)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
                self.assertEqual(self.output_bytes(), before)

    def test_non_principal_pairing_and_namesake(self):
        self.senate += matchup("q1", 44, 50, dem_name="Hypothetical Democrat", rep_name="Mike Collins")
        self.senate += [answer("q2", "DEM", "Mary Peltola", 47, "AK"), answer("q2", "REP", "Dan Sullivan", 45, "AK"),
                        answer("q2", "REP", "Dan J. Sullivan", 3, "AK"), answer("q2", "REP", "Gerald Heikes", 2, "AK")]
        _, log = self.build()
        self.assertEqual(log[("Senate", "q1")]["reason"], "non_principal")
        self.assertEqual(log[("Senate", "q2")]["included"], "True")
        self.assertEqual(log[("Senate", "q2")]["dem_margin_pp"], "2.00")

    def test_selection_and_weights_match_house_method(self):
        rows = matchup("q1", 50, 44, poll="p1", population="rv", sample_size="900", partisan="DEM") + \
            matchup("q2", 49, 45, poll="p1", population="lv", sample_size="900", partisan="DEM") + \
            matchup("q3", 47, 47, poll="p2", end_date="09/01/26", sample_size="")
        self.senate += rows
        averages, log = self.build()
        self.assertEqual(log[("Senate", "q1")]["reason"], "superseded")
        house_dir = self.root / "house"
        house_dir.mkdir()
        field = [dict(dict.fromkeys(house_field.FIELD_COLUMNS, ""), state="VT", district="00", name=name,
                      party=party, fec_match_status="automatic")
                 for name, party in [("Jon Ossoff", "DEM"), ("Mike Collins", "REP")]]
        write_csv(house_dir / "field.csv", house_field.FIELD_COLUMNS, field)
        write_csv(house_dir / "polls.csv", POLL_COLUMNS, [dict(r, state="VT", seat_number="1") for r in rows])
        house_averages, house_log = house_polls.compute(house_dir / "polls.csv", house_dir / "field.csv",
                                                          house_dir / "matchups.json")
        house_log = {r["question_id"]: r for r in house_log}
        for question in ["q2", "q3"]:
            for column in ["recency_factor", "sample_factor", "pollster_factor", "partisan_factor", "weight",
                           "sample_size_imputed"]:
                self.assertEqual(log[("Senate", question)][column], house_log[question][column], (question, column))
        self.assertEqual(averages["GA-SEN"]["poll_avg_dem_margin_pp"], house_averages[0]["poll_avg_dem_margin_pp"])

    def test_margin_recomputes_from_log(self):
        for index, (dem, rep, end) in enumerate([(50, 44, "10/20/26"), (47, 46, "10/01/26"), (45, 48, "09/10/26")]):
            self.senate += matchup(f"q{index}", dem, rep, end_date=end, pollster=f"Pollster {index % 2}")
        averages, log = self.build()
        included = [r for r in log.values() if r["race_id"] == "GA-SEN" and r["included"] == "True"]
        weights = [float(r["weight"]) for r in included]
        margin = sum(float(r["dem_margin_pp"]) * w for r, w in zip(included, weights)) / sum(weights)
        self.assertAlmostEqual(margin, float(averages["GA-SEN"]["poll_avg_dem_margin_pp"]), places=2)
        self.assertEqual(averages["GA-SEN"]["poll_count"], "3")

    def test_no_eligible_polls_and_shuffle(self):
        self.senate += matchup("q1", 50, 45, state="WY", dem_name="Someone Else", rep_name="Harriet Hageman")
        self.senate += matchup("q2", 50, 45) + matchup("q3", 48, 47, end_date="09/20/26")
        self.governor += matchup("q4", 49, 48, dem_name="Keisha Lance Bottoms", rep_name="Rick Jackson")
        averages, _ = self.build()
        self.assertEqual(averages["WY-SEN"]["poll_avg_status"], "no_eligible_polls")
        self.assertEqual(averages["WY-SEN"]["poll_count"], "")
        before = self.output_bytes()
        random.Random(3).shuffle(self.senate)
        self.build()
        self.assertEqual(self.output_bytes(), before)

    def test_malformed_share_fails(self):
        self.senate += matchup("q1", 50, 45)
        self.senate[0]["pct"] = "fifty"
        with self.assertRaisesRegex(ValueError, "question q1: invalid pct"):
            self.build()


if __name__ == "__main__":
    unittest.main()
