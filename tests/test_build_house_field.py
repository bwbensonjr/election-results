import csv
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_field as builder
from test_candidate_identity import ballot, decision, fec

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows, columns=None):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.polls = self.data / "polls.csv"
        write_csv(self.polls, [], ["cycle", "stage", "state", "seat_number", "party",
                                   "candidate_name", "end_date"])

    def inputs(self, ballots=None, records=None, decisions=None):
        write_csv(self.data / "ballotbrief-house-candidates.csv", ballots or [ballot()])
        write_csv(self.data / "fec-house-candidates-flagged.csv", records or [fec()])
        (self.data / "candidate-identity-decisions.json").write_text(json.dumps(
            dict(schema_version=1, decisions=decisions or [])))

    def output_bytes(self):
        return {name: (self.data / name).read_bytes() for name in
                ["house-general-field.csv", "field-discrepancies.csv", "candidate-match-review.csv"]}

    def test_invalid_registry_preserves_outputs(self):
        self.inputs()
        builder.build(self.data, self.polls)
        before = self.output_bytes()
        self.inputs(decisions=[decision(canonical_fec_id="MISSING")])
        with self.assertRaisesRegex(ValueError, "nonexistent"):
            builder.build(self.data, self.polls)
        self.assertEqual(self.output_bytes(), before)

    def test_invalid_registry_cli_exits_nonzero_without_overwriting(self):
        self.inputs()
        builder.build(self.data, self.polls)
        project = self.data / "project"
        destination = project / "2026/candidates"
        destination.mkdir(parents=True)
        (project / "2026/polls").mkdir()
        (project / "2026/polls/us-house-polls.csv").write_bytes(self.polls.read_bytes())
        for source in self.data.glob("*.csv"):
            (destination / source.name).write_bytes(source.read_bytes())
        (destination / "candidate-identity-decisions.json").write_text(json.dumps(
            dict(schema_version=1, decisions=[decision(canonical_fec_id="MISSING")])))
        before = {p.name: p.read_bytes() for p in destination.glob("*.csv")}
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_house_field.py")],
                                cwd=project, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nonexistent FEC ID", result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in destination.glob("*.csv")})

    def test_ambiguous_and_missing_rows_with_dates(self):
        self.inputs(ballots=[ballot(), ballot("Jane Jones")], records=[fec(), fec("H2")])
        field, review, _ = builder.build(self.data, self.polls)
        self.assertEqual(len(field), 2)
        self.assertEqual(len(review), 3)
        for row in field:
            for key in ["fec_candidate_id", "incumbent", "filed_12g", "receipts"]:
                self.assertEqual(row[key], "")
        self.assertEqual(review[0]["coverage_end_date"], "2026-10-14")
        self.assertEqual(review[-1]["fec_candidate_id"], "")
        before = self.output_bytes()
        builder.build(self.data, self.polls)
        self.assertEqual(self.output_bytes(), before)

    def test_reviewed_alias_is_present_and_not_double_counted(self):
        alternate = fec("H2")
        alternate["filed_12g"] = "True"
        self.inputs(records=[fec(), alternate], decisions=[decision(alternate_fec_ids=["H2"])])
        field, review, issues = builder.build(self.data, self.polls)
        self.assertEqual(field[0]["fec_candidate_id"], "H1")
        self.assertTrue(field[0]["filed_12g"])
        self.assertEqual(field[0]["receipts"], "100")
        self.assertEqual(review, [])
        self.assertFalse(any("12G" in r["issue"] for r in issues))

    def test_poll_presence_does_not_choose_fec(self):
        self.inputs(records=[fec(), fec("H2")])
        write_csv(self.polls, [dict(cycle="2026", stage="general", state="NY", seat_number="1",
                                    party="DEM", candidate_name="Alice Smith", end_date="10/30/26")])
        field, _, _ = builder.build(self.data, self.polls)
        self.assertTrue(field[0]["in_general_polls"])
        self.assertEqual(field[0]["fec_match_status"], "ambiguous")

    def test_id_cannot_be_automatically_assigned_to_two_ballot_rows(self):
        self.inputs(ballots=[ballot(), ballot("Alice Smith Jr.")])
        field, _, _ = builder.build(self.data, self.polls)
        self.assertTrue(all(row["fec_match_status"] == "ambiguous" for row in field))
        self.assertTrue(all(row["fec_candidate_id"] == "" for row in field))

    def test_ambiguous_poll_association(self):
        self.inputs(ballots=[ballot(), ballot("Bob Smith")])
        write_csv(self.polls, [dict(cycle="2026", stage="general", state="NY", seat_number="1",
                                    party="DEM", candidate_name="Unknown Smith", end_date="10/30/26")])
        field, _, issues = builder.build(self.data, self.polls)
        self.assertTrue(all(r["in_general_polls"] == "" for r in field))
        self.assertTrue(any(r["issue"] == "ambiguous poll-to-ballot association" for r in issues))

    def test_reviewed_unmatched_keeps_row_and_evidence(self):
        self.inputs(decisions=[decision(decision="unmatched", canonical_fec_id="")])
        field, review, _ = builder.build(self.data, self.polls)
        self.assertEqual(field[0]["fec_match_status"], "reviewed_unmatched")
        self.assertEqual(field[0]["incumbent"], "")
        self.assertEqual(review[0]["decision_evidence"], "https://example.test/evidence")

    def corrections(self, *entries):
        (self.data / builder.CORRECTIONS_FILE).write_text(json.dumps(
            dict(schema_version=1, corrections=list(entries))))

    def merged_correction(self, **updates):
        row = dict(id="NY-01-split", state="NY", district="01", source_name="Bob Lee, Cy Moe",
                   replacements=[dict(name="Bob Lee", party="Independent"),
                                 dict(name="Cy Moe", party="Libertarian")],
                   evidence=["https://example.test/ballot"], reviewed_by="Fixture reviewer",
                   reviewed_at="2026-11-02")
        row.update(updates)
        return row

    def test_correction_splits_merged_row(self):
        self.inputs(ballots=[ballot(), ballot("Bob Lee, Cy Moe", "Libertarian")])
        self.corrections(self.merged_correction())
        write_csv(self.polls, [dict(cycle="2026", stage="general", state="NY", seat_number="1",
                                    party="IND", candidate_name="Bob Lee", end_date="10/30/26")])
        field, _, _ = builder.build(self.data, self.polls)
        by_name = {r["name"]: r for r in field}
        self.assertEqual(set(by_name), {"Alice Smith", "Bob Lee", "Cy Moe"})
        self.assertEqual(by_name["Bob Lee"]["party"], "OTHER")
        self.assertEqual(by_name["Bob Lee"]["party_raw"], "Independent")
        self.assertTrue(by_name["Bob Lee"]["in_general_polls"])
        self.assertEqual(by_name["Cy Moe"]["source_correction"], "NY-01-split")
        self.assertEqual(by_name["Alice Smith"]["source_correction"], "")
        self.assertEqual(by_name["Alice Smith"]["fec_candidate_id"], "H1")

    def test_stale_or_unevidenced_correction_preserves_outputs(self):
        self.inputs(ballots=[ballot(), ballot("Bob Lee, Cy Moe", "Libertarian")])
        builder.build(self.data, self.polls)
        before = self.output_bytes()
        for entry, message in [(self.merged_correction(source_name="Nobody"), "stale correction"),
                               (self.merged_correction(evidence=[]), "needs evidence")]:
            self.corrections(entry)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                builder.build(self.data, self.polls)
            self.assertEqual(self.output_bytes(), before)

    def test_current_snapshot_coverage_and_shuffled_rebuild(self):
        source = ROOT / "2026/candidates"
        for name in ["ballotbrief-house-candidates.csv", "fec-house-candidates-flagged.csv",
                     "candidate-identity-decisions.json", builder.CORRECTIONS_FILE]:
            (self.data / name).write_bytes((source / name).read_bytes())
        polls = ROOT / "2026/polls/us-house-polls.csv"
        field, _, _ = builder.build(self.data, polls)
        self.assertEqual(len(field), 1160)
        alaska = {r["name"]: r for r in field if r["state"] == "AK"}
        self.assertEqual(alaska["Bill Hill"]["party_raw"], "Independent")
        self.assertTrue(alaska["Bill Hill"]["in_general_polls"])
        self.assertEqual(len({(r["state"], r["district"]) for r in field}), 435)
        before = self.output_bytes()
        records = builder.read_csv(self.data / "fec-house-candidates-flagged.csv")
        random.Random(2026).shuffle(records)
        write_csv(self.data / "fec-house-candidates-flagged.csv", records)
        builder.build(self.data, polls)
        self.assertEqual(self.output_bytes(), before)


if __name__ == "__main__":
    unittest.main()
