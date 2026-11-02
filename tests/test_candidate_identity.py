import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from candidate_identity import load_decisions, resolve


def ballot(name="Alice Smith", party="Democratic"):
    return dict(state="NY", district="01", name=name, party=party, source_url="https://example.test/ballot")


def fec(cid="H1", name="SMITH, ALICE", party="DEM", **extra):
    return dict(state="NY", district="01", candidate_id=cid, name=name, party=party,
                incumbent_challenge="I", receipts="100", cash_on_hand_end_period="20",
                filed_12g="False", coverage_end_date="2026-10-14", **extra)


def decision(**updates):
    row = dict(cycle=2026, state="NY", district="01", ballot_name="Alice Smith",
               decision="match", canonical_fec_id="H1", alternate_fec_ids=[],
               evidence=["https://example.test/evidence"], rationale="Fixture evidence",
               reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")
    row.update(updates)
    return row


class IdentityTests(unittest.TestCase):
    def test_unique_normalized_names_and_party(self):
        for b, f in [(ballot(), fec()),
                     (ballot("Alice Smith Jr.", "DFL"), fec(name="SMITH JR., ALICE", party="DFL")),
                     (ballot("Jose Garcia", "Republican"), fec(name="GARCÍA, JOSÉ", party="REP")),
                     (ballot("Alice Smith, III"), fec(name="SMITH, ALICE III")),
                     (ballot("Alice Van Smith"), fec(name="VAN SMITH, ALICE")),
                     (ballot("Alice Greene-Smith"), fec(name="GREENE-SMITH, ALICE"))]:
            with self.subTest(b=b):
                self.assertEqual(resolve(b, [f]).status, "automatic")

    def test_weak_names_and_party_conflict(self):
        for name, party in [("Bob Smith", "Democratic"), ("A. Smith", "Democratic"),
                            ("Alice Smith", "Republican"), ("Alice Smith", "Unrecognized")]:
            result = resolve(ballot(name, party), [fec()])
            self.assertEqual(result.status, "unmatched")
            self.assertIsNone(result.canonical)
        self.assertEqual(resolve(ballot("Alice Smith"), [fec(name="SMITH, A")]).status, "unmatched")
        self.assertEqual(resolve(ballot("Alice Smith"), [fec(name="JONES, ALICE")]).candidates, [])

    def test_competing_identity_and_order(self):
        records = [fec(), fec("H2", "SMITH, ALICIA")]
        a, b = resolve(ballot(), records), resolve(ballot(), records[::-1])
        self.assertEqual(a, b)
        self.assertEqual(a.status, "ambiguous")
        self.assertIsNone(a.canonical)

    def test_district_boundary(self):
        record = fec()
        record["district"] = "02"
        self.assertEqual(resolve(ballot(), [record]).candidates, [])

    def load(self, entries, ballots=None, records=None):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "decisions.json"
            path.write_text(json.dumps(dict(schema_version=1, decisions=entries)))
            return load_decisions(path, ballots or [ballot()], records or [fec()])

    def test_valid_review_and_explicit_unmatched(self):
        entries = self.load([decision()])
        self.assertEqual(resolve(ballot(), [fec()], entries).status, "reviewed")
        entries = self.load([decision(decision="unmatched", canonical_fec_id="")])
        result = resolve(ballot(), [fec()], entries)
        self.assertEqual(result.status, "reviewed_unmatched")
        self.assertEqual(result.filed_12g, "")

    def test_invalid_decisions(self):
        cases = [[decision(), decision()], [decision(canonical_fec_id="MISSING")],
                 [decision(ballot_name="Absent Person")], [decision(state="CA")],
                 [decision(reviewed_by="")], [decision(reviewed_at="yesterday")],
                 [decision(evidence=[])], [decision(alternate_fec_ids=["H1"])],
                 [decision(cycle=2024)], [decision(decision="unknown")],
                 [decision(decision="unmatched")], [decision(alternate_fec_ids="H2")]]
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.load(entries)
        other = fec()
        other["district"] = "02"
        with self.assertRaisesRegex(ValueError, "state/district"):
            self.load([decision()], records=[other])
        with self.assertRaisesRegex(ValueError, "reused"):
            self.load([decision(), decision(ballot_name="Alicia Smith")],
                      ballots=[ballot(), ballot("Alicia Smith")])

    def test_alternate_filing_and_canonical_finance(self):
        canonical = fec()
        alternate = fec("H2", "SMITH, ALICE J")
        alternate.update(incumbent_challenge="C", filed_12g="True", receipts="100")
        entries = self.load([decision(alternate_fec_ids=["H2"])], records=[canonical, alternate])
        result = resolve(ballot(), [alternate, canonical], entries)
        self.assertEqual(result.canonical["incumbent_challenge"], "I")
        self.assertEqual(result.canonical["receipts"], "100")
        self.assertTrue(result.filed_12g)
        self.assertEqual(result.member_ids, {"H1", "H2"})


if __name__ == "__main__":
    unittest.main()
