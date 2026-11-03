import copy
import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_results as ingest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/globe-2026-11-03-pre.json.gz"
BASELINE = ingest.load_baseline()


def fixture():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))


def find(document, state, office, seat=None):
    for race in document["races"]:
        response = race["raceResponse"]
        if race["statePostal"] == state and response["officeID"] == office and (seat is None or response.get("seatNum") == seat):
            return race
    raise LookupError((state, office, seat))


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "live"
        self.moment = datetime(2026, 11, 4, 1, 15, tzinfo=timezone.utc)

    def run_document(self, document, moment=None):
        data = json.dumps(document).encode()
        return ingest.run_once(data, moment or self.moment, self.out, BASELINE, "test")

    def results(self):
        return json.loads((self.out / "results.json").read_text())

    def test_fixture_joins_every_race(self):
        status = self.run_document(fixture())
        results = self.results()
        self.assertEqual(status["races"], 506)
        self.assertEqual(len(results["races"]), 506)
        self.assertIn("DEM", results["national"]["house_popular_vote"])
        self.assertFalse(results["test"])
        linked = sum(1 for r in results["races"].values() for c in r["candidates"] if c["baseline_name"])
        self.assertGreaterEqual(linked, 1370)

    def test_at_large_and_special_joins(self):
        document = fixture()
        self.run_document(document)
        races = self.results()["races"]
        self.assertEqual(races["AK-AL"]["ap_race_id"], find(document, "AK", "H", "1")["raceResponse"]["raceID"])
        self.assertEqual(races["OH-SEN"]["race_type"], "Special General")
        self.assertEqual(races["FL-SEN"]["race_type"], "Special General")
        self.assertEqual(races["LA-02"]["race_type"], "Nonpartisan Election")

    def test_before_poll_close(self):
        self.run_document(fixture())
        race = self.results()["races"]["GA-SEN"]
        self.assertEqual(race["total_votes"], 0)
        self.assertIsNone(race["winner"])
        self.assertEqual(race["call_status"], "Too Early to Call")
        self.assertTrue(all(c["pct"] is None for c in race["candidates"]))

    def test_missing_race_fails_and_keeps_results(self):
        self.run_document(fixture())
        before = (self.out / "results.json").read_bytes()
        document = fixture()
        document["races"].remove(find(document, "GA", "G"))
        with self.assertRaisesRegex(ingest.IngestError, "GA-GOV: no AP race"):
            self.run_document(document)
        self.assertEqual((self.out / "results.json").read_bytes(), before)

    def test_extra_and_duplicate_races_fail(self):
        document = fixture()
        extra = copy.deepcopy(find(document, "TX", "H", "1"))
        extra["raceResponse"]["seatNum"] = "99"
        document["races"].append(extra)
        with self.assertRaisesRegex(ingest.IngestError, "TX/H/99 matches no baseline race"):
            self.run_document(document)
        document = fixture()
        document["races"].append(copy.deepcopy(find(document, "GA", "S")))
        with self.assertRaisesRegex(ingest.IngestError, "GA-SEN: matched by more than one AP race"):
            self.run_document(document)

    def test_write_in_line_is_kept_unmatched(self):
        self.run_document(fixture())
        results = self.results()
        write_in = [c for c in results["races"]["AK-AL"]["candidates"] if c["name"] == "Total Write-ins"]
        self.assertEqual(len(write_in), 1)
        self.assertIsNone(write_in[0]["baseline_name"])
        self.assertIn("Total Write-ins", [u["name"] for u in results["unmatched_candidates"]])

    def test_called_race_and_shares(self):
        document = fixture()
        race = find(document, "GA", "S")
        response = race["raceResponse"]
        candidates = response["reportingUnits"][0]["candidates"]
        dem = next(c for c in candidates if c["party"] == "Dem")
        rep = next(c for c in candidates if c["party"] == "GOP")
        dem["voteCount"], rep["voteCount"] = 600, 400
        dem["winner"] = "X"
        response["raceCallStatus"] = "Called"
        response["reportingUnits"][0]["eevp"] = 95
        self.run_document(document)
        result = self.results()["races"]["GA-SEN"]
        self.assertTrue(result["called"])
        self.assertEqual(result["winner"]["party_group"], "DEM")
        self.assertEqual(result["dem_margin_pp"], 20.0)
        self.assertEqual(result["leader_party_group"], "DEM")
        self.assertEqual(result["candidates"][0]["pct"], 60.0)
        self.assertEqual(self.results()["summary"]["Senate"]["called"]["DEM"], 1)

    def test_unknown_call_status_is_uncalled(self):
        document = fixture()
        find(document, "GA", "S")["raceResponse"]["raceCallStatus"] = "Something New"
        self.run_document(document)
        self.assertFalse(self.results()["races"]["GA-SEN"]["called"])

    def test_test_flag_carried(self):
        document = fixture()
        find(document, "GA", "S")["test"] = True
        self.run_document(document)
        self.assertTrue(self.results()["test"])

    def test_unchanged_flag(self):
        self.assertTrue(self.run_document(fixture())["changed"])
        later = datetime(2026, 11, 4, 1, 17, tzinfo=timezone.utc)
        self.assertFalse(self.run_document(fixture(), later)["changed"])
        self.assertEqual(self.results()["fetched_at"], "2026-11-04T01:17:00Z")

    def test_replay_of_saved_snapshots(self):
        raw = self.root / "raw"
        first, second = fixture(), fixture()
        find(second, "GA", "S")["raceResponse"]["reportingUnits"][0]["candidates"][0]["voteCount"] = 1234
        outputs = []
        for moment, document in ((self.moment, first), (datetime(2026, 11, 4, 1, 17, tzinfo=timezone.utc), second)):
            data = json.dumps(document).encode()
            ingest.save_raw(data, moment, raw)
            ingest.run_once(data, moment, self.out, BASELINE, "test")
            outputs.append((self.out / "results.json").read_bytes())
        replay = self.root / "replay"
        ingest.ingest(str(raw), replay, BASELINE)
        self.assertEqual((replay / "results.json").read_bytes(), outputs[-1])
        ingest.ingest(str(sorted(raw.iterdir())[0]), replay, BASELINE)
        self.assertEqual((replay / "results.json").read_bytes(), outputs[0])

    def test_failed_fetch_keeps_results(self):
        self.run_document(fixture())
        before = (self.out / "results.json").read_bytes()
        with mock.patch.object(ingest, "fetch_live", side_effect=OSError("timed out")):
            with self.assertRaisesRegex(ingest.IngestError, "fetch failed"):
                ingest.ingest("live", self.out, BASELINE)
        self.assertEqual((self.out / "results.json").read_bytes(), before)

    def records(self):
        return {p.stem: json.loads(p.read_text()) for p in (self.out / "db").glob("*.json")}

    def test_database_records_split_and_hash(self):
        self.run_document(fixture())
        records, results = self.records(), self.results()
        self.assertEqual(sorted(records), ["house-1", "house-2", "house-3", "meta", "statewide"])
        self.assertEqual(records["meta"]["records"], ["statewide", "house-1", "house-2", "house-3"])
        self.assertNotIn("races", records["meta"])
        self.assertEqual(records["meta"]["content_hash"], results["content_hash"])
        keys = []
        for name in records["meta"]["records"]:
            self.assertEqual(records[name]["content_hash"], results["content_hash"])
            keys.extend(records[name]["races"])
        self.assertEqual(sorted(keys), sorted(results["races"]))
        self.assertEqual(len(keys), 506)
        house_states = [{r["state_postal"] for r in records[f"house-{n}"]["races"].values()} for n in (1, 2, 3)]
        self.assertFalse(house_states[0] & house_states[1] or house_states[1] & house_states[2])
        for path in (self.out / "db").glob("*.json"):
            self.assertLess(path.stat().st_size, ingest.RECORD_LIMIT)

    def test_race_records_follow_changes_meta_every_run(self):
        self.run_document(fixture())
        before = (self.out / "db/statewide.json").stat().st_mtime_ns
        later = datetime(2026, 11, 4, 1, 17, tzinfo=timezone.utc)
        self.run_document(fixture(), later)
        self.assertEqual((self.out / "db/statewide.json").stat().st_mtime_ns, before)
        self.assertEqual(self.records()["meta"]["fetched_at"], self.results()["fetched_at"])

    def test_oversized_record_fails_and_keeps_files(self):
        self.run_document(fixture())
        before = {p.name: p.read_bytes() for p in [self.out / "results.json", *(self.out / "db").glob("*.json")]}
        document = fixture()
        find(document, "GA", "S")["raceResponse"]["reportingUnits"][0]["candidates"][0]["voteCount"] = 1234
        with mock.patch.object(ingest, "RECORD_LIMIT", 100_000):
            with self.assertRaisesRegex(ingest.IngestError, "database record house-1"):
                self.run_document(document)
        after = {p.name: p.read_bytes() for p in [self.out / "results.json", *(self.out / "db").glob("*.json")]}
        self.assertEqual(after, before)

    def test_interval_minimum(self):
        with self.assertRaises(SystemExit):
            ingest.main(["--every", "30", "--output-dir", str(self.out)])


if __name__ == "__main__":
    unittest.main()
