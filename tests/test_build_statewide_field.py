import csv
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_statewide_field as builder

ROOT = Path(__file__).resolve().parents[1]
POLL_COLUMNS = ["cycle", "stage", "state", "seat_number", "party", "candidate_name", "end_date"]


def write_csv(path, rows, columns):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def ballot(state, office, name, party):
    return dict(state=state, office=office, name=name, party=party,
                source_url=f"https://example.test/state/{state.lower()}")


def senate(cid, name, party, state="GA", district="00", filed="False", incumbent="C"):
    return dict(candidate_id=cid, name=name, party=party, state=state, district=district,
                incumbent_challenge=incumbent, receipts="1000", cash_on_hand_end_period="50",
                filed_12g=filed, coverage_end_date="2026-10-14")


def poll(state, party, name, end="10/15/26", stage="general", cycle="2026"):
    return dict(cycle=cycle, stage=stage, state=state, seat_number="", party=party,
                candidate_name=name, end_date=end)


BALLOT = [
    ballot("GA", "Senate", "Jon Ossoff", "D"), ballot("GA", "Senate", "Mike Collins", "R"),
    ballot("GA", "Governor", "Keisha Lance Bottoms", "D"), ballot("GA", "Governor", "Rick Jackson", "R"),
    ballot("NE", "Senate", "Pete Ricketts", "R"), ballot("NE", "Senate", "Dan Osborn", "Independent"),
    ballot("AK", "Senate", "Dan Sullivan", "R"), ballot("AK", "Senate", "Daniel J. Sullivan Jr.", "R"),
    ballot("AK", "Senate", "Mary Peltola", "D"),
]
FEC = [
    senate("S6GA00001", "OSSOFF, JON", "DEM", incumbent="I"),
    senate("S6GA00002", "COLLINS, MIKE", "REP", filed="True"),
    # A House record with the same name must never be considered for a Senate race.
    dict(senate("H6GA10001", "COLLINS, MIKE", "REP", district="10")),
    senate("S6NE00001", "RICKETTS, PETE", "REP", state="NE", district=""),
    senate("S6NE00002", "OSBORN, DAN", "IND", state="NE"),
    senate("S6AK00001", "SULLIVAN, DAN", "REP", state="AK", incumbent="I"),
    senate("S6AK00002", "SULLIVAN, DANIEL J", "REP", state="AK"),
    senate("S6AK00003", "PELTOLA, MARY", "DEM", state="AK"),
    senate("S6OH00001", "FILER, ALEX", "DEM", state="OH", filed="True"),
]
SENATE_POLLS = [
    poll("GA", "DEM", "Jon Ossoff"), poll("GA", "REP", "Mike Collins"), poll("GA", "NONE", "Undecided"),
    poll("NE", "DEM", "Dan Osborn"), poll("NE", "REP", "Pete Ricketts"),
    poll("AK", "REP", "Dan Sullivan"), poll("AK", "REP", "Dan J. Sullivan"),
    poll("AK", "DEM", "Mary Peltola", end="06/01/26"),
]
GOVERNOR_POLLS = [
    poll("GA", "REP", "Rick Jackson"), poll("VA", "DEM", "Abigail Spanberger", cycle="2025"),
    poll("GA", "DEM", "Keisha Lance Bottoms", stage="primary"),
]


class StatewideFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.poll_paths = {"Senate": self.data / "senate-polls.csv", "Governor": self.data / "governor-polls.csv"}

    def inputs(self, ballots=BALLOT, records=FEC, decisions=(), senate_polls=SENATE_POLLS):
        write_csv(self.data / "ballotbrief-statewide-candidates.csv", ballots, builder.BALLOT_COLUMNS)
        write_csv(self.data / "fec-senate-candidates-flagged.csv", records, list(records[0]))
        write_csv(self.poll_paths["Senate"], senate_polls, POLL_COLUMNS)
        write_csv(self.poll_paths["Governor"], GOVERNOR_POLLS, POLL_COLUMNS)
        (self.data / "senate-identity-decisions.json").write_text(json.dumps(
            dict(schema_version=1, decisions=list(decisions))))

    def build(self):
        field, review, discrepancies = builder.build(self.data, self.poll_paths)
        return {(r["race_id"], r["name"]): r for r in field}, review, discrepancies

    def output_bytes(self):
        return {name: (self.data / name).read_bytes() for name in
                ["statewide-general-field.csv", "statewide-field-discrepancies.csv", "statewide-match-review.csv"]}

    def test_races_ids_and_senate_matching_within_office(self):
        self.inputs()
        field, _, _ = self.build()
        self.assertEqual({r["race_id"] for r in field.values()}, {"GA-SEN", "GA-GOV", "NE-SEN", "AK-SEN"})
        collins = field[("GA-SEN", "Mike Collins")]
        self.assertEqual((collins["fec_candidate_id"], collins["fec_match_status"]), ("S6GA00002", "automatic"))
        self.assertTrue(collins["filed_12g"])
        self.assertTrue(field[("GA-SEN", "Jon Ossoff")]["incumbent"])
        # The blank-district FEC record is still treated as statewide.
        self.assertEqual(field[("NE-SEN", "Pete Ricketts")]["fec_candidate_id"], "S6NE00001")
        self.assertEqual(field[("NE-SEN", "Dan Osborn")]["party"], "OTHER")

    def test_governor_rows_are_not_federal_with_blank_values(self):
        self.inputs()
        field, review, _ = self.build()
        jackson = field[("GA-GOV", "Rick Jackson")]
        self.assertEqual(jackson["fec_match_status"], "not_federal")
        for column in ["fec_candidate_id", "incumbent", "filed_12g", "receipts", "cash_on_hand_end_period"]:
            self.assertEqual(jackson[column], "", column)
        self.assertNotIn("GA-GOV", {r["race_id"] for r in review})

    def test_poll_presence_is_scoped_to_office_and_window(self):
        self.inputs()
        field, _, discrepancies = self.build()
        self.assertTrue(field[("GA-SEN", "Mike Collins")]["in_general_polls"])
        self.assertTrue(field[("GA-GOV", "Rick Jackson")]["in_general_polls"])
        # Primary-stage and pre-window polls do not count; Senate polls do not mark governor rows.
        self.assertFalse(field[("GA-GOV", "Keisha Lance Bottoms")]["in_general_polls"])
        self.assertFalse(field[("AK-SEN", "Mary Peltola")]["in_general_polls"])
        self.assertNotIn(("VA", "Governor"), {(d["state"], d["office"]) for d in discrepancies})

    def test_namesakes_split_by_first_given_name(self):
        self.inputs()
        field, review, _ = self.build()
        # The shared poll rule prefers the exact first given name, so "Dan" is not "Daniel".
        self.assertTrue(field[("AK-SEN", "Dan Sullivan")]["in_general_polls"])
        self.assertFalse(field[("AK-SEN", "Daniel J. Sullivan Jr.")]["in_general_polls"])
        self.assertEqual(field[("AK-SEN", "Dan Sullivan")]["fec_match_status"], "ambiguous")
        self.assertIn("Dan Sullivan", {r["ballot_name"] for r in review})

    def test_reviewed_senate_decision(self):
        entry = dict(cycle=2026, office="Senate", state="AK", ballot_name="Dan Sullivan", decision="match",
                     canonical_fec_id="S6AK00001", alternate_fec_ids=[], evidence=["https://example.test"],
                     rationale="Incumbent", reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")
        self.inputs(decisions=[entry])
        field, _, _ = self.build()
        self.assertEqual(field[("AK-SEN", "Dan Sullivan")]["fec_match_status"], "reviewed")
        self.assertTrue(field[("AK-SEN", "Dan Sullivan")]["incumbent"])

    def test_12g_filer_missing_from_ballot(self):
        self.inputs()
        _, _, discrepancies = self.build()
        self.assertIn(dict(state="OH", office="Senate", race_id="OH-SEN", candidate="FILER, ALEX",
                           issue="filed 12G but not on ballot list"), discrepancies)
        self.assertIn(dict(state="NE", office="Senate", race_id="NE-SEN", candidate="",
                           issue="no DEM candidate on ballot list"), discrepancies)

    def test_duplicate_race_fails_and_preserves_outputs(self):
        self.inputs()
        self.build()
        before = self.output_bytes()
        self.inputs(ballots=BALLOT + [ballot("GA", "Senate", "Jon Ossoff", "D")])
        with self.assertRaisesRegex(ValueError, "GA lists Jon Ossoff twice for Senate"):
            builder.build(self.data, self.poll_paths)
        self.assertEqual(self.output_bytes(), before)

    def test_invalid_office_fails(self):
        self.inputs(ballots=BALLOT + [ballot("GA", "Mayor", "Someone", "D")])
        with self.assertRaisesRegex(ValueError, "invalid office"):
            builder.build(self.data, self.poll_paths)

    def test_shuffled_inputs_are_byte_identical(self):
        self.inputs()
        self.build()
        before = self.output_bytes()
        rng = random.Random(7)
        ballots, records, polls = list(BALLOT), list(FEC), list(SENATE_POLLS)
        for rows in (ballots, records, polls):
            rng.shuffle(rows)
        self.inputs(ballots, records, senate_polls=polls)
        self.build()
        self.assertEqual(self.output_bytes(), before)

    def test_committed_snapshot_coverage(self):
        with (ROOT / "2026/candidates/statewide-general-field.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        races = {r["race_id"] for r in rows}
        self.assertEqual(sum(r.endswith("-SEN") for r in races), 35)
        self.assertEqual(sum(r.endswith("-GOV") for r in races), 36)
        self.assertEqual({r["fec_match_status"] for r in rows if r["office"] == "Governor"}, {"not_federal"})


if __name__ == "__main__":
    unittest.main()
