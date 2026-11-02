import csv
import math
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_field as candidates
import build_house_poll_averages as polls

ROOT = Path(__file__).resolve().parents[1]
POLL_COLUMNS = polls.REQUIRED_COLUMNS + ["ranked_choice_round"]
FIELD = [
    ("VT", "00", "Becca Balint", "DEM"), ("VT", "00", "Gerald Malloy", "REP"),
    ("PA", "07", "Susan Wild", "DEM"), ("PA", "07", "Ryan Mackenzie", "REP"),
    ("PA", "07", "Olivia Faulkner", "OTHER"),
    ("PA", "08", "Paige Cognetti", "DEM"), ("PA", "08", "Rob Bresnahan", "REP"),
    ("PA", "08", "Rachel Bresnahan", "OTHER"),
    ("CA", "34", "Jimmy Gomez", "DEM"), ("CA", "34", "David Kim", "DEM"),
    ("ME", "02", "Matthew G. Dunlap", "DEM"), ("ME", "02", "Paul R. LePage", "REP"),
    ("NY", "01", "Nick LaLota", "REP"), ("NY", "01", "John Avlon", "DEM"),
]


def answer(question, party, name, pct, poll=None, state="PA", seat="7", **fields):
    row = dict(poll_id=poll or f"poll-{question}", question_id=question, pollster="Pollster A", state=state,
               end_date="10/01/26", sample_size="600", population="lv", partisan="", cycle="2026",
               stage="general", seat_number=seat, party=party, candidate_name=name, pct=str(pct),
               ranked_choice_reallocated="FALSE", ranked_choice_round="")
    row.update(fields)
    return row


def head_to_head(question, dem, rep, poll=None, state="PA", seat="7", dem_name="Susan Wild",
                 rep_name="Ryan Mackenzie", **fields):
    return [answer(question, "DEM", dem_name, dem, poll, state, seat, **fields),
            answer(question, "REP", rep_name, rep, poll, state, seat, **fields),
            answer(question, "NONE", "Undecided", 100 - dem - rep, poll, state, seat, **fields)]


class PollFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.polls_path = self.root / "polls.csv"
        self.candidates_path = self.root / "candidates.csv"
        self.output = self.root / "out"
        rows = []
        for state, district, name, party in FIELD:
            row = {column: "" for column in candidates.FIELD_COLUMNS}
            row.update(state=state, district=district, name=name, party=party, fec_match_status="automatic")
            rows.append(row)
        self.write(self.candidates_path, candidates.FIELD_COLUMNS, rows)
        self.rows = []

    def write(self, path, columns, rows):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def compute(self, columns=POLL_COLUMNS):
        self.write(self.polls_path, columns, [{c: r[c] for c in columns} for r in self.rows])
        averages, records = polls.compute(self.polls_path, self.candidates_path)
        return {r["district_id"]: r for r in averages}, {r["question_id"]: r for r in records}

    def build(self):
        self.write(self.polls_path, POLL_COLUMNS, self.rows)
        return polls.build(self.polls_path, self.candidates_path, self.output)

    def output_bytes(self):
        return {p.name: p.read_bytes() for p in self.output.glob("*.csv")}


class SelectionTests(PollFixture):
    def test_missing_column_fails(self):
        self.rows = head_to_head("q1", 48, 45)
        with self.assertRaisesRegex(ValueError, "missing required columns.*partisan"):
            self.compute([c for c in POLL_COLUMNS if c != "partisan"])

    def test_district_mapping(self):
        self.rows = (head_to_head("vt", 55, 30, state="VT", seat="1", dem_name="Becca Balint", rep_name="Gerald Malloy")
                     + head_to_head("pa", 48, 45, seat="7") + head_to_head("bad", 48, 45, seat="99"))
        averages, records = self.compute()
        self.assertEqual(records["vt"]["district_id"], "VT-AL")
        self.assertEqual(records["vt"]["district"], "00")
        self.assertEqual(records["vt"]["reason"], "")
        self.assertEqual(records["pa"]["district"], "07")
        self.assertEqual(records["bad"]["reason"], "unknown_district")
        self.assertEqual(averages["VT-AL"]["poll_avg_status"], "available")

    def test_exclusion_rules(self):
        self.rows = (
            [answer("us", "DEM", "Generic Democrat", 48, state="US", seat=""),
             answer("us", "REP", "Generic Republican", 45, state="US", seat="")]
            + head_to_head("primary", 48, 45, stage="primary")
            + head_to_head("old", 48, 45, cycle="2024")
            + head_to_head("noseat", 48, 45, seat="")
            + [answer("label", "DEM", "Generic Democrat", 48), answer("label", "REP", "Generic Republican", 45)]
            + head_to_head("dd", 40, 35, state="CA", seat="34", dem_name="Jimmy Gomez", rep_name="Someone")
            + [answer("rcv", "DEM", "Susan Wild", 44, ranked_choice_round="1"),
               answer("rcv", "REP", "Ryan Mackenzie", 41, ranked_choice_round="1"),
               answer("rcv", "IND", "Olivia Faulkner", 15, ranked_choice_round="1"),
               answer("rcv", "DEM", "Susan Wild", 52, ranked_choice_round="2", ranked_choice_reallocated="TRUE"),
               answer("rcv", "REP", "Ryan Mackenzie", 48, ranked_choice_round="2", ranked_choice_reallocated="TRUE")])
        averages, records = self.compute()
        reasons = {q: r["reason"] for q, r in records.items()}
        self.assertEqual(reasons, dict(us="nationwide", primary="not_general", old="out_of_cycle",
                                       noseat="missing_seat", label="not_head_to_head",
                                       dd="no_dem_rep_field", rcv=""))
        self.assertEqual((records["rcv"]["dem_pct"], records["rcv"]["rep_pct"]), ("44.00", "41.00"))
        self.assertEqual(averages["PA-07"]["poll_avg_dem_margin_pp"], "3.00")
        self.assertEqual(averages["CA-34"]["poll_avg_status"], "no_dem_rep_field")

    def test_nominee_matching(self):
        self.rows = (head_to_head("hypo", 47, 44, dem_name="Janelle Stelson")
                     + head_to_head("ambig", 47, 44, seat="8", dem_name="Paige Cognetti", rep_name="R. Bresnahan")
                     + head_to_head("third", 46, 43) + [answer("third", "IND", "Olivia Faulkner", 6)])
        averages, records = self.compute()
        self.assertEqual(records["hypo"]["reason"], "non_nominee")
        self.assertEqual(records["ambig"]["reason"], "ambiguous_match")
        self.assertEqual(records["third"]["reason"], "")
        self.assertEqual(records["third"]["dem_candidate"], "Susan Wild")
        self.assertEqual(averages["PA-08"]["poll_avg_status"], "no_eligible_polls")
        self.assertEqual(averages["PA-07"]["poll_count"], "1")

    def test_one_question_per_poll(self):
        self.rows = (head_to_head("q-rv", 49, 44, poll="p1", population="rv")
                     + head_to_head("q-lv", 47, 46, poll="p1")
                     + head_to_head("q-b", 47, 45, poll="p2")
                     + head_to_head("q-c", 46, 45, poll="p2") + [answer("q-c", "IND", "Olivia Faulkner", 5, "p2")]
                     + head_to_head("q-e", 45, 45, poll="p3") + head_to_head("q-d", 44, 44, poll="p3"))
        _, records = self.compute()
        self.assertEqual(records["q-rv"]["reason"], "superseded")
        self.assertEqual(records["q-lv"]["included"], "True")
        self.assertEqual(records["q-b"]["reason"], "superseded")
        self.assertEqual(records["q-c"]["included"], "True")
        self.assertEqual(records["q-d"]["included"], "True")
        self.assertEqual(records["q-e"]["reason"], "superseded")

    def test_strict_parsing_only_for_candidates(self):
        self.rows = head_to_head("ok", 48, 45) + head_to_head("primary", 48, 45, stage="primary")
        self.rows[-2]["pct"] = "n/a"
        averages, _ = self.compute()
        self.assertEqual(averages["PA-07"]["poll_avg_status"], "available")
        self.rows[0]["pct"] = "forty"
        with self.assertRaisesRegex(ValueError, "question ok: invalid pct 'forty'"):
            self.compute()
        self.rows[0]["pct"] = "48"
        for row in self.rows[:3]:
            row["end_date"] = "2026-10-01"
        with self.assertRaisesRegex(ValueError, "question ok: invalid end_date"):
            self.compute()


class WeightTests(PollFixture):
    def test_hand_computed_weights(self):
        self.rows = (head_to_head("a", 50, 40, end_date="10/21/26", sample_size="2400", pollster="A")
                     + head_to_head("b", 44, 46, end_date="09/30/26", sample_size="", pollster="B", partisan="REP")
                     + head_to_head("c", 46, 45, end_date="10/21/26", sample_size="150", pollster="A"))
        averages, records = self.compute()
        a = math.sqrt(1500 / 600) / math.sqrt(2)
        b = 0.5 * 1 * 1 * 0.5
        c = math.sqrt(150 / 600) / math.sqrt(2)
        self.assertEqual(records["a"]["weight"], f"{a:.6f}")
        self.assertEqual(records["b"]["weight"], f"{b:.6f}")
        self.assertEqual(records["b"]["age_days"], "21")
        self.assertEqual(records["b"]["sample_size_imputed"], "True")
        self.assertEqual(records["b"]["sample_size"], "600")
        self.assertEqual(records["a"]["pollster_factor"], f"{1 / math.sqrt(2):.6f}")
        margin = (10 * a - 2 * b + 1 * c) / (a + b + c)
        self.assertEqual(averages["PA-07"]["poll_avg_dem_margin_pp"], f"{margin:.2f}")
        self.assertEqual(averages["PA-07"]["poll_pollster_count"], "2")
        self.assertEqual(averages["PA-07"]["poll_latest_end_date"], "2026-10-21")

    def test_weights_do_not_depend_on_calendar(self):
        self.rows = (head_to_head("a", 50, 40, end_date="10/21/26")
                     + head_to_head("b", 44, 46, end_date="08/30/26", pollster="B"))
        averages, records = self.compute()
        for row in self.rows:
            row["end_date"] = (datetime.strptime(row["end_date"], "%m/%d/%y") + timedelta(days=9)).strftime("%m/%d/%y")
        shifted_averages, shifted = self.compute()
        self.assertEqual(averages["PA-07"]["poll_avg_dem_margin_pp"], shifted_averages["PA-07"]["poll_avg_dem_margin_pp"])
        self.assertEqual([records[q]["weight"] for q in "ab"], [shifted[q]["weight"] for q in "ab"])

    def test_log_reproduces_average_and_unpolled_is_blank(self):
        self.rows = [row for i, (d, r) in enumerate([(50, 41), (47, 47), (45, 49), (52, 40)])
                     for row in head_to_head(f"q{i}", d, r, pollster=f"P{i % 2}", end_date=f"10/{10 + 3 * i}/26")]
        averages, records = self.compute()
        included = [r for r in records.values() if r["included"] == "True"]
        weights = [float(r["weight"]) for r in included]
        margin = sum(w * float(r["dem_margin_pp"]) for w, r in zip(weights, included)) / sum(weights)
        self.assertAlmostEqual(margin, float(averages["PA-07"]["poll_avg_dem_margin_pp"]), delta=0.006)
        ny = averages["NY-01"]
        self.assertEqual(ny["poll_avg_status"], "no_polls")
        self.assertTrue(all(ny[c] == "" for c in polls.POLL_COLUMNS if c not in {"poll_avg_status", "poll_avg_source_id"}))
        self.assertEqual(ny["poll_avg_source_id"], polls.SOURCE_ID)

    def test_shuffled_rows_are_byte_identical_and_failures_preserve_outputs(self):
        self.rows = (head_to_head("a", 50, 40, poll="p1") + head_to_head("b", 49, 41, poll="p1", population="rv")
                     + head_to_head("c", 44, 46, end_date="09/30/26") + head_to_head("us", 40, 40, state="US", seat=""))
        self.build()
        before = self.output_bytes()
        random.Random(4).shuffle(self.rows)
        self.build()
        self.assertEqual(before, self.output_bytes())
        self.rows.append(answer("a", "DEM", "Susan Wild", 51, "p1"))
        with self.assertRaisesRegex(ValueError, "question a: duplicate candidate answers"):
            self.build()
        self.assertEqual(before, self.output_bytes())
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_house_poll_averages.py"),
                                 "--polls", str(self.polls_path), "--candidates", str(self.candidates_path),
                                 "--output-dir", str(self.output)], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Poll average build failed", result.stderr)
        self.assertEqual(before, self.output_bytes())

    def test_current_snapshot(self):
        averages, records = polls.compute()
        self.assertEqual(len(averages), 435)
        self.assertEqual(len(records), 1680)
        statuses = [r["poll_avg_status"] for r in averages]
        self.assertEqual(statuses.count("available"), 111)
        me = next(r for r in averages if r["district_id"] == "ME-02")
        self.assertEqual((me["poll_avg_dem_candidate"], me["poll_avg_rep_candidate"]),
                         ("Matthew G. Dunlap", "Paul R. LePage"))


if __name__ == "__main__":
    unittest.main()
