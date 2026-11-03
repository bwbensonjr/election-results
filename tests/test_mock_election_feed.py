import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_results as ingest
import mock_election_feed as mock

FIXTURE = mock.load_fixture()
BASELINE = mock.load_baseline()
NIGHT = list(mock.generate(54, 10, seed=7, fixture=FIXTURE, baseline=BASELINE))


def shape(value):
    """Keys and value types, ignoring list lengths, for comparing documents."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items() if k not in ("winner",)}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else type(value).__name__


def tracked(document):
    for race in document["races"]:
        response = race["raceResponse"]
        if response["officeID"] in mock.TRACKED and race["statePostal"] != "US":
            yield race


def race_by(document, state, office, seat=None):
    for race in document["races"]:
        response = race["raceResponse"]
        if race["statePostal"] == state and response["officeID"] == office and (seat is None or response.get("seatNum") == seat):
            return race
    raise LookupError((state, office, seat))


class MockFeedTests(unittest.TestCase):
    def test_same_shape_and_races_as_fixture(self):
        _, _, last = NIGHT[-1]
        self.assertEqual(len(last["races"]), len(FIXTURE["races"]))
        self.assertEqual([r["raceResponse"]["raceID"] for r in last["races"]],
                         [r["raceResponse"]["raceID"] for r in FIXTURE["races"]])
        self.assertEqual(shape({k: v for k, v in last.items() if k != "races"}),
                         shape({k: v for k, v in FIXTURE.items() if k != "races"}))
        for before, after in zip(FIXTURE["races"], last["races"]):
            self.assertEqual(shape(before), shape(after), before["raceResponse"]["raceID"])

    def test_every_step_ingests(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = ingest.load_baseline()
            for _, moment, document in NIGHT:
                status = ingest.run_once(json.dumps(document).encode(), moment, Path(temp), baseline, "mock")
                self.assertEqual(status["races"], 506)
                self.assertTrue(status["test"])

    def test_every_race_marked_test(self):
        for _, _, document in NIGHT[:1] + NIGHT[-1:]:
            self.assertTrue(all(r["test"] and r["raceResponse"]["test"] for r in document["races"]))

    def test_no_votes_before_poll_close(self):
        for _, moment, document in NIGHT:
            for race in tracked(document):
                unit = race["raceResponse"]["reportingUnits"][0]
                if moment < mock.parse_time(unit["pollClosingTime"]):
                    self.assertEqual(sum(c["voteCount"] for c in unit["candidates"]), 0)
                    self.assertEqual(race["raceResponse"]["tabulationStatus"], "Awaiting Poll Close")
                    self.assertFalse(any(c.get("winner") for c in unit["candidates"]))

    def test_seven_thirty_step(self):
        step = next(d for _, m, d in NIGHT if mock.stamp(m) == "2026-11-04T00:30:00.000Z")
        def votes(race):
            return sum(c["voteCount"] for c in race["raceResponse"]["reportingUnits"][0]["candidates"])
        self.assertGreater(votes(race_by(step, "GA", "S")), 0)  # Georgia closes at 7pm ET
        self.assertEqual(votes(race_by(step, "PA", "H", "7")), 0)  # Pennsylvania closes at 8pm ET

    def test_counts_never_decrease(self):
        previous = {}
        for _, _, document in NIGHT:
            for race in tracked(document):
                unit = race["raceResponse"]["reportingUnits"][0]
                for c in unit["candidates"]:
                    key = (race["raceResponse"]["raceID"], c["candidateID"])
                    self.assertGreaterEqual(c["voteCount"], previous.get(key, 0))
                    previous[key] = c["voteCount"]
                key = (race["raceResponse"]["raceID"], "eevp")
                self.assertGreaterEqual(unit["eevp"], previous.get(key, 0))
                previous[key] = unit["eevp"]

    def test_seeded_reproducibility(self):
        first = [json.dumps(d) for _, _, d in mock.generate(6, 30, seed=11, fixture=FIXTURE, baseline=BASELINE)]
        second = [json.dumps(d) for _, _, d in mock.generate(6, 30, seed=11, fixture=FIXTURE, baseline=BASELINE)]
        other = [json.dumps(d) for _, _, d in mock.generate(6, 30, seed=12, fixture=FIXTURE, baseline=BASELINE)]
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_final_step_calls_and_edge_cases(self):
        _, _, last = NIGHT[-1]
        races = list(tracked(last))
        called = [r for r in races if any(c.get("winner") == "X" for c in r["raceResponse"]["reportingUnits"][0]["candidates"])]
        self.assertGreater(len(called), 0.8 * len(races))
        close = race_by(last, "PA", "H", "7")
        self.assertFalse(any(c.get("winner") for c in close["raceResponse"]["reportingUnits"][0]["candidates"]))
        self.assertGreaterEqual(close["raceResponse"]["reportingUnits"][0]["eevp"], 90)
        for race in races:
            response = race["raceResponse"]
            if response.get("rankedChoice") or response.get("raceType") == "Nonpartisan Election":
                candidates = response["reportingUnits"][0]["candidates"]
                total = sum(c["voteCount"] for c in candidates)
                for c in candidates:
                    if c.get("winner") == "X":
                        self.assertGreater(c["voteCount"], total / 2, race["statePostal"])

    def test_one_winner_at_most(self):
        _, _, last = NIGHT[-1]
        for race in tracked(last):
            winners = [c for c in race["raceResponse"]["reportingUnits"][0]["candidates"] if c.get("winner")]
            self.assertLessEqual(len(winners), 1)


if __name__ == "__main__":
    unittest.main()
