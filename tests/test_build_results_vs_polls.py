import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_results_vs_polls as rvp


def base(key, office="House", status="available", dem="Dee Dem", rep="Rob Rep", dem_pct="45.00",
         rep_pct="42.50", margin="2.50", count="2"):
    available = status == "available"
    return {
        "race_key": key, "state_postal": key[:2], "office": office, "district": "01" if office == "House" else "",
        "poll_avg_status": status, "poll_avg_dem_candidate": dem if available else "",
        "poll_avg_rep_candidate": rep if available else "", "poll_avg_dem_pct": dem_pct if available else "",
        "poll_avg_rep_pct": rep_pct if available else "", "poll_avg_dem_margin_pp": margin if available else "",
        "poll_count": count if available else "", "poll_latest_end_date": "2026-11-01" if available else "",
    }


def cand(name, party_group, votes):
    return {"name": name, "baseline_name": name, "party_group": party_group, "votes": votes}


def race(candidates, called=False, winner=None, eevp=90):
    total = sum(c["votes"] for c in candidates)
    return {"called": called, "winner": winner, "eevp": eevp, "total_votes": total, "candidates": candidates}


def input_row(key, included, question, end_date, pollster="P", statewide=False):
    row = {"poll_id": question, "question_id": question, "pollster": pollster, "end_date": end_date,
           "population": "lv", "sample_size": "600", "sample_size_imputed": "False", "partisan": "",
           "dem_candidate": "Dee Dem", "rep_candidate": "Rob Rep", "dem_pct": "45", "rep_pct": "42",
           "dem_margin_pp": "3", "weight": "1", "included": included, "reason": ""}
    if statewide:
        row.update(office="Senate", race_id=key)
    else:
        row.update(district_id=key)
    return row


class CompareRaceTests(unittest.TestCase):
    def test_independent_principal_uses_poll_pair(self):
        b = base("AK-AL", dem="Bill Hill", rep="Nick Begich", dem_pct="40.62", rep_pct="45.96", margin="-5.33")
        r = race([cand("Nick Begich", "REP", 123241), cand("Bill Hill", "OTHER", 104460),
                  cand("Eric Hafner", "DEM", 19032), cand("Other", "OTHER", 6726)])
        row = rvp.compare_race(b, r)
        self.assertEqual(row["status"], "compared")
        self.assertEqual(row["result_dem_margin_pp"], "-7.41")
        self.assertEqual(row["diff_pp"], "-2.08")

    def test_republican_overperformance_is_negative(self):
        row = rvp.compare_race(base("XX-01"), race([cand("Dee Dem", "DEM", 4950), cand("Rob Rep", "REP", 5050)]))
        self.assertEqual(row["result_dem_margin_pp"], "-1.00")
        self.assertEqual(row["diff_pp"], "-3.50")

    def test_democratic_overperformance_is_positive(self):
        b = base("AL-GOV", office="Governor", margin="-8.17")
        row = rvp.compare_race(b, race([cand("Dee Dem", "DEM", 4800), cand("Rob Rep", "REP", 5200)]))
        self.assertEqual(row["diff_pp"], "4.17")

    def test_no_polls_keeps_call_but_no_comparison(self):
        r = race([cand("Rob Rep", "REP", 100)], called=True, winner={"party_group": "REP"}, eevp=99)
        row = rvp.compare_race(base("AL-01", status="no_polls"), r)
        self.assertEqual((row["status"], row["called"], row["winner_party_group"], row["eevp"]),
                         ("no_polls", "True", "REP", "99"))
        for column in ("poll_dem_margin_pp", "result_dem_pct", "result_dem_margin_pp", "diff_pp"):
            self.assertEqual(row[column], "")

    def test_no_votes(self):
        row = rvp.compare_race(base("XX-02"), race([cand("Dee Dem", "DEM", 0), cand("Rob Rep", "REP", 0)]))
        self.assertEqual((row["status"], row["diff_pp"]), ("no_votes", ""))

    def test_principal_missing(self):
        row = rvp.compare_race(base("XX-03"), race([cand("Dee Dem", "DEM", 10), cand("Other Rep", "REP", 9)]))
        self.assertEqual((row["status"], row["diff_pp"]), ("principal_missing", ""))


class PollListTests(unittest.TestCase):
    def test_only_included_newest_first(self):
        house = [input_row("XX-01", "True", "q1", "2026-10-01"), input_row("XX-01", "True", "q2", "2026-10-20"),
                 input_row("XX-01", "False", "q3", "2026-10-25")]
        statewide = [input_row("XX-SEN", "True", "s1", "2026-09-01", statewide=True),
                     input_row("XX-SEN", "False", "s2", "2025-01-01", statewide=True)]
        polls = rvp.poll_list(house, statewide)
        self.assertEqual([(p["race_key"], p["question_id"]) for p in polls],
                         [("XX-01", "q2"), ("XX-01", "q1"), ("XX-SEN", "s1")])
        self.assertEqual([p["office"] for p in polls], ["House", "House", "Senate"])

    def test_count_mismatch_fails(self):
        rows = [{"race_key": "XX-01", "poll_count": "2"}]
        with self.assertRaisesRegex(rvp.BuildError, "XX-01"):
            rvp.check_counts(rows, [{"race_key": "XX-01"}])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def test_missing_race_fails_without_writing(self):
        results = json.loads(rvp.RESULTS.read_text())
        del results["races"]["GA-SEN"]
        path = self.dir / "results.json"
        path.write_text(json.dumps(results))
        with self.assertRaisesRegex(rvp.BuildError, "GA-SEN"):
            rvp.build(path, output_dir=self.dir / "out")
        self.assertFalse((self.dir / "out").exists())

    def test_snapshot_build_is_complete_and_identical(self):
        out1, out2 = self.dir / "a", self.dir / "b"
        rvp.build(output_dir=out1)
        rvp.build(output_dir=out2)
        for name in (rvp.COMPARISON_FILE, rvp.POLLS_FILE):
            self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes())
        with open(out1 / rvp.COMPARISON_FILE) as f:
            rows = {r["race_key"]: r for r in csv.DictReader(f)}
        self.assertEqual(len(rows), 506)
        self.assertEqual(rows["AK-AL"]["result_dem_margin_pp"], "-7.41")
        with open(out1 / rvp.POLLS_FILE) as f:
            polls = list(csv.DictReader(f))
        self.assertEqual(sum(p["race_key"] == "AK-SEN" for p in polls), int(rows["AK-SEN"]["poll_count"]))


if __name__ == "__main__":
    unittest.main()
