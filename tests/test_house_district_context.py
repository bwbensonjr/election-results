import collections
import csv
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_district_context as context
import build_house_field as candidates
import build_house_poll_averages as polls
import election_guide as guide
import district_history as history
from test_district_history import HistoryFixture, ROOT, county_results, crosswalk_row, write_csv


class ContextTests(HistoryFixture):
    def setUp(self):
        super().setUp()
        self.candidate_path = self.root / "candidates.csv"
        self.output = self.root / "context"
        self.polls_path = self.root / "polls.csv"
        self.poll_output = self.root / "polls"
        self.poll_rows = []
        self.guide_path = self.root / "guide.csv"
        self.guide_markdown = self.root / "guide.md"
        self.guide_markdown.write_text("### AK-1 · Alaska at-large\nCandidate B (R) v Candidate A (D).\n")
        race = {column: "" for column in guide.RACE_COLUMNS}
        race.update(slot_et="12:00+", poll_close_et="24:00", state="AK", office="House", district="00",
                    card="Alaska", dem_candidate="Candidate A", chill="Counts slowly.")
        senate = dict(race, office="Senate", district="", dem_candidate="", chill="")
        self.guide_rows = [race, senate]
        self.save_guide()
        self.candidate_rows = []
        for state, district, name, status in [("AK", "00", "Candidate A", "reviewed"),
                                               ("AK", "00", "Candidate B", "unmatched"),
                                               ("AL", "01", "Candidate C", "automatic")]:
            row = {column: "" for column in candidates.FIELD_COLUMNS}
            row.update(state=state, district=district, name=name, party="DEM", party_raw="Democratic",
                       fec_match_status=status, incumbent="False", filed_12g="True", receipts="123.45",
                       cash_on_hand_end_period="12.00", in_general_polls="False", source_url="https://example.test/ballot")
            if status != "unmatched":
                row["fec_candidate_id"] = name
            self.candidate_rows.append(row)
        self.roster = self.root / "roster.json"
        self.save_roster(self.roster_entry("AK-AL", "Candidate A", "D"), self.roster_entry("AL-01", "Old Member", "R"))
        self.save_candidates()
        self.normalize()

    def roster_entry(self, key, name, party, **extra):
        entry = dict(race_key=key, office="House", name=name, party=party, vacant=False,
                     evidence=["https://example.test/roster"], reviewed_by="Fixture reviewer", reviewed_at="2026-11-02")
        entry.update(extra)
        return entry

    def save_roster(self, *entries):
        self.roster.write_text(json.dumps(dict(schema_version=1, entries=list(entries))))

    def save_candidates(self):
        write_csv(self.candidate_path, [candidates.FIELD_COLUMNS] +
                  [[row[c] for c in candidates.FIELD_COLUMNS] for row in self.candidate_rows])
        self.save_polls()

    def save_guide(self):
        write_csv(self.guide_path, [guide.RACE_COLUMNS] +
                  [[row[c] for c in guide.RACE_COLUMNS] for row in self.guide_rows])

    def save_polls(self, rebuild=True):
        write_csv(self.polls_path, [polls.REQUIRED_COLUMNS] +
                  [[row.get(c, "") for c in polls.REQUIRED_COLUMNS] for row in self.poll_rows])
        if rebuild:
            polls.build(self.polls_path, self.candidate_path, self.poll_output, self.root / "matchups.json")

    def build(self, strict=False):
        return context.build(self.candidate_path, self.manifest,
                             self.normalized / "presidential-results-normalized.csv",
                             self.normalized / "cook-pvi-normalized.csv", self.output, strict, self.root,
                             self.polls_path, self.poll_output / "house-poll-averages.csv",
                             self.guide_path, self.guide_markdown, self.root / "matchups.json", self.roster,
                             self.normalized / "presidential-results-interpolated.csv")

    def output_bytes(self):
        return {p.name: p.read_bytes() for p in self.output.glob("*.csv")}

    def test_grain_values_and_unknown_vintage_not_gated(self):
        districts, enriched, issues = self.build(strict=True)
        self.assertEqual(len(districts), 2)
        self.assertEqual(len(enriched), 3)
        self.assertEqual(districts[0]["candidate_count"], "2")
        self.assertEqual(districts[0]["unresolved_fec_candidate_count"], "1")
        self.assertEqual(districts[0]["pres_2024_dem_margin_pp"], "-20.00")
        self.assertEqual(districts[0]["pres_2020_dem_margin_pp"], "20.00")
        self.assertEqual(districts[0]["cook_pvi_label"], "D+4")
        self.assertEqual(districts[1]["cook_pvi_dem_lean_pp"], "0")
        self.assertTrue(all(row["pres_2024_status"] == "available" for row in districts))
        self.assertEqual(issues, [])
        self.assertTrue(all(row["poll_avg_status"] == "no_dem_rep_field" for row in districts))
        self.assertTrue(all(row["poll_avg_dem_margin_pp"] == "" for row in enriched))
        original = collections.Counter(tuple(r[c] for c in candidates.FIELD_COLUMNS) for r in self.candidate_rows)
        actual = collections.Counter(tuple(r[c] for c in candidates.FIELD_COLUMNS) for r in enriched)
        self.assertEqual(original, actual)
        self.assertNotIn("candidate_count", enriched[0])
        self.assertEqual(next(r for r in enriched if r["name"] == "Candidate B")["fec_candidate_id"], "")

    def test_redrawn_state_keeps_margins_with_prior_boundaries_status(self):
        self.save_boundary(self.boundary_entry("AK"))
        self.normalize()
        districts, enriched, issues = self.build(strict=True)
        ak, al = districts
        self.assertEqual((ak["pres_2020_status"], ak["pres_2024_status"], ak["cook_pvi_status"]),
                         ("prior_boundaries", "prior_boundaries", "available"))
        self.assertEqual((ak["pres_2024_dem_margin_pp"], ak["pres_2020_dem_margin_pp"]), ("-20.00", "20.00"))
        self.assertEqual((al["pres_2020_status"], al["pres_2024_status"]), ("available", "available"))
        self.assertEqual(issues, [])
        self.assertTrue(all(r["pres_2024_status"] == "prior_boundaries" for r in enriched if r["state"] == "AK"))

    def test_crosswalk_state_gets_interpolated_margins(self):
        self.save_boundary(self.boundary_entry("AK"), self.boundary_entry("AL"))
        self.save_crosswalk([crosswalk_row("AL-01", "01097", "AL-01", 10, 10, "1.00000000")],
                            county_results(("01097", 5, 5, 10, 10)))
        self.normalize()
        districts, enriched, issues = self.build(strict=True)
        ak, al = districts
        self.assertEqual((ak["pres_2020_status"], ak["pres_2024_status"]), ("prior_boundaries", "prior_boundaries"))
        self.assertEqual(ak["pres_2024_source_id"], "test-pres")
        self.assertEqual((al["pres_2020_status"], al["pres_2024_status"], al["cook_pvi_status"]),
                         ("interpolated", "interpolated", "available"))
        self.assertEqual((al["pres_2020_dem_margin_pp"], al["pres_2024_dem_margin_pp"]), ("20.00", "0.00"))
        self.assertEqual(al["pres_2024_source_id"], history.INTERPOLATED_SOURCE_ID)
        self.assertEqual(issues, [])
        self.assertTrue(all(r["pres_2024_status"] == "interpolated" for r in enriched if r["state"] == "AL"))

    def test_stale_interpolation_fails(self):
        self.save_boundary(self.boundary_entry("AL"))
        self.save_crosswalk([crosswalk_row("AL-01", "01097", "AL-01", 10, 10, "1.00000000")],
                            county_results(("01097", 5, 5, 10, 10)))
        self.normalize()
        path = self.normalized / "presidential-results-interpolated.csv"
        path.write_text(path.read_text().replace(",20.00,", ",21.00,"))
        with self.assertRaisesRegex(ValueError, "stale or inconsistent normalization"):
            self.build()

    def test_invalid_boundary_registry_preserves_exports(self):
        self.build()
        before = self.output_bytes()
        self.save_boundary(self.boundary_entry("AK", evidence=[]))
        with self.assertRaisesRegex(ValueError, "evidence"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_roster_running_incumbent_and_open_seat(self):
        districts, enriched, _ = self.build(strict=True)
        ak, al = districts
        self.assertEqual([ak[c] for c in ["roster_incumbent_name", "roster_incumbent_party", "roster_vacant",
                                          "roster_ballot_status", "open_seat"]],
                         ["Candidate A", "D", "False", "running", "False"])
        # AL-01's incumbent is not on its ballot, as when a member runs for another office.
        self.assertEqual((al["roster_ballot_status"], al["open_seat"]), ("not_running", "True"))
        self.assertEqual({r["name"] for r in enriched if r["roster_incumbent"] == "True"}, {"Candidate A"})
        self.assertTrue(all(r["incumbent"] == "False" for r in enriched))
        self.assertEqual(context.DISTRICT_COLUMNS[-len(context.ROSTER_COLUMNS):], context.ROSTER_COLUMNS)

    def test_vacant_seat_and_not_running_override(self):
        self.save_roster(self.roster_entry("AK-AL", "Candidate A", "D", ballot_status_override="not_running",
                                           override_rationale="Fixture: a different Candidate A"),
                         self.roster_entry("AL-01", "", "", vacant=True))
        districts, enriched, _ = self.build()
        ak, al = districts
        self.assertEqual((ak["roster_ballot_status"], ak["open_seat"]), ("not_running", "True"))
        self.assertEqual((al["roster_vacant"], al["roster_ballot_status"], al["open_seat"]), ("True", "", "True"))
        self.assertFalse(any(r["roster_incumbent"] == "True" for r in enriched))

    def test_missing_roster_district_preserves_exports(self):
        self.build()
        before = self.output_bytes()
        self.save_roster(self.roster_entry("AK-AL", "Candidate A", "D"))
        with self.assertRaisesRegex(ValueError, "AL-01"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_missing_value_row_and_source_only_coverage(self):
        self.pres_rows[2][8] = ""
        self.cook_rows.pop()
        extra = self.pres_rows[3].copy()
        extra[0] = "IA-01"
        self.pres_rows.append(extra)
        self.cook_rows.append(["IA-01", "Historical name", "R", "R+1", "R+2", "230"])
        self.save_sources()
        self.normalize()
        districts, enriched, issues = self.build()
        self.assertEqual(len(districts), 2)
        self.assertEqual(len(enriched), 3)
        self.assertEqual(districts[0]["pres_2024_dem_margin_pp"], "")
        self.assertEqual(districts[0]["pres_2024_status"], "missing")
        self.assertEqual(districts[1]["cook_pvi_label"], "")
        self.assertEqual(districts[1]["cook_pvi_status"], "missing")
        self.assertEqual(sum(r["issue"] == "source_only_district" for r in issues), 3)
        self.assertEqual(sum(r["issue"] == "missing_value" for r in issues), 1)
        self.assertEqual(sum(r["issue"] == "missing_district" for r in issues), 1)
        before = self.output_bytes()
        with self.assertRaisesRegex(ValueError, "2 missing target metrics"):
            self.build(strict=True)
        self.assertEqual(self.output_bytes(), before)

    def test_missing_presidential_district(self):
        self.pres_rows.pop()
        self.save_sources()
        self.normalize()
        districts, _, issues = self.build()
        self.assertEqual(districts[1]["pres_2020_status"], "missing")
        self.assertEqual(districts[1]["pres_2024_status"], "missing")
        self.assertEqual(len(issues), 2)

    def test_stale_normalization_and_hash_preserve_exports(self):
        self.build()
        before = self.output_bytes()
        self.cook_rows[1][4] = "R+2"
        self.save_sources()
        with self.assertRaisesRegex(ValueError, "stale or inconsistent normalization"):
            self.build()
        self.assertEqual(before, self.output_bytes())
        self.normalize()
        self.cook.write_text(self.cook.read_text() + "changed")
        with self.assertRaisesRegex(ValueError, "stale SHA-256"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_duplicate_normalized_input_preserves_exports(self):
        self.build()
        before = self.output_bytes()
        path = self.normalized / "cook-pvi-normalized.csv"
        rows = history.read_table(path)
        rows.append(rows[1])
        write_csv(path, rows)
        with self.assertRaisesRegex(ValueError, "duplicate normalized key"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_reordered_sources_and_candidates_are_deterministic(self):
        self.build()
        before = self.output_bytes()
        normalized_before = {p.name: p.read_bytes() for p in self.normalized.glob("*.csv")}
        self.pres_rows = self.pres_rows[:2] + self.pres_rows[2:][::-1]
        self.cook_rows = self.cook_rows[:1] + self.cook_rows[1:][::-1]
        self.candidate_rows.reverse()
        self.save_sources()
        self.save_candidates()
        self.normalize()
        self.build()
        self.assertEqual(before, self.output_bytes())
        self.assertEqual(normalized_before, {p.name: p.read_bytes() for p in self.normalized.glob("*.csv")})

    def test_cli_strict_failure_keeps_prior_exports(self):
        self.candidate_rows[0].update(state="AL", district="99")
        self.save_candidates()
        self.save_roster(self.roster_entry("AK-AL", "Candidate A", "D"), self.roster_entry("AL-01", "Old Member", "R"),
                         self.roster_entry("AL-99", "Candidate A", "D"))
        self.build()
        before = self.output_bytes()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_house_district_context.py"),
                                 "--candidates", str(self.candidate_path), "--output-dir", str(self.output),
                                 "--polls", str(self.polls_path),
                                 "--poll-averages", str(self.poll_output / "house-poll-averages.csv"),
                                 "--guide", str(self.guide_path), "--guide-markdown", str(self.guide_markdown),
                                 "--matchups", str(self.root / "matchups.json"), "--roster", str(self.roster),
                                 "--require-complete"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AL-99", result.stderr)
        self.assertIn("missing target metrics", result.stderr)
        self.assertEqual(before, self.output_bytes())

    def poll_answers(self, question, dem, rep, end_date="10/01/26"):
        base = dict(poll_id=f"poll-{question}", question_id=question, pollster="Pollster", state="AK",
                    end_date=end_date, sample_size="600", population="lv", partisan="", cycle="2026",
                    stage="general", seat_number="1", ranked_choice_reallocated="FALSE")
        return [dict(base, party="DEM", candidate_name="Candidate A", pct=str(dem)),
                dict(base, party="REP", candidate_name="Candidate B", pct=str(rep))]

    def test_polling_columns_join_and_stale_averages_fail(self):
        self.candidate_rows[1]["party"] = "REP"
        self.poll_rows = self.poll_answers("q1", 48, 44) + self.poll_answers("q2", 46, 46, "09/10/26")
        self.save_candidates()
        districts, enriched, issues = self.build(strict=True)
        self.assertEqual(issues, [])
        with (self.output / "house-district-context.csv").open(newline="") as stream:
            header = next(csv.reader(stream))
        self.assertEqual(header[:16], [
            "state", "district", "district_id", "election_cycle", "candidate_count",
            "unresolved_fec_candidate_count", "pres_2020_dem_margin_pp", "pres_2024_dem_margin_pp",
            "cook_pvi_label", "cook_pvi_dem_lean_pp", "pres_2020_status", "pres_2024_status",
            "cook_pvi_status", "pres_2020_source_id", "pres_2024_source_id", "cook_pvi_source_id"])
        self.assertEqual(header[16:16 + len(polls.POLL_COLUMNS)], polls.POLL_COLUMNS)
        guide_end = 16 + len(polls.POLL_COLUMNS) + len(context.GUIDE_CONTEXT_COLUMNS)
        self.assertEqual(header[16 + len(polls.POLL_COLUMNS):guide_end], context.GUIDE_CONTEXT_COLUMNS)
        self.assertEqual(header[guide_end:guide_end + 1], polls.MATCHUP_COLUMNS)
        ak, al = districts
        self.assertEqual((ak["poll_avg_status"], ak["poll_count"], ak["poll_avg_dem_candidate"]),
                         ("available", "2", "Candidate A"))
        self.assertEqual(al["poll_avg_status"], "no_dem_rep_field")
        self.assertEqual(al["poll_avg_dem_margin_pp"], "")
        ak_rows = [r for r in enriched if r["district_id"] == "AK-AL"]
        self.assertEqual(len(ak_rows), 2)
        self.assertTrue(all(r[c] == ak[c] for r in ak_rows for c in polls.POLL_COLUMNS + polls.MATCHUP_COLUMNS))
        self.assertEqual((ak["poll_avg_matchup_basis"], al["poll_avg_matchup_basis"]), ("dem_rep", ""))
        self.assertEqual(ak_rows[0]["party_raw"], "Democratic")
        before = self.output_bytes()
        self.poll_rows[0]["pct"] = "50"
        self.save_polls(rebuild=False)
        with self.assertRaisesRegex(ValueError, "stale polling averages"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_guide_columns_join_and_mismatch_fails(self):
        districts, enriched, issues = self.build(strict=True)
        self.assertEqual(issues, [])
        ak, al = districts
        self.assertEqual((ak["guide_status"], ak["guide_card"], ak["guide_chill"], ak["guide_name_check"]),
                         ("in_guide", "Alaska", "Counts slowly.", "matched"))
        self.assertEqual(ak["guide_source_id"], guide.SOURCE_ID)
        self.assertEqual(al["guide_status"], "not_in_guide")
        self.assertTrue(all(al[c] == "" for c in guide.GUIDE_COLUMNS + ["guide_name_check"]))
        ak_rows = [r for r in enriched if r["district_id"] == "AK-AL"]
        self.assertTrue(all(r[c] == ak[c] for r in ak_rows for c in context.GUIDE_CONTEXT_COLUMNS))
        self.guide_rows[0]["dem_candidate"] = "Someone Else"
        self.save_guide()
        districts, _, _ = self.build()
        self.assertEqual(districts[0]["guide_name_check"], "mismatch")
        self.assertEqual(districts[0]["guide_dem_candidate"], "Someone Else")
        before = self.output_bytes()
        self.guide_markdown.write_text("AK-1 and AL-1 tonight.\n")
        with self.assertRaisesRegex(ValueError, "missing from the CSV: AL-01"):
            self.build()
        self.assertEqual(before, self.output_bytes())

    def test_current_snapshot_cardinality_and_candidate_preservation(self):
        districts, enriched, issues = context.build(output_dir=self.output, require_complete=True)
        self.assertEqual(len(districts), 435)
        self.assertEqual(len({r["district_id"] for r in districts}), 435)
        self.assertEqual(len(enriched), 1160)
        self.assertEqual(issues, [])
        columns, original = history.read_records(context.DEFAULT_CANDIDATES)
        self.assertEqual(collections.Counter(tuple(r[c] for c in columns) for r in original),
                         collections.Counter(tuple(r[c] for c in columns) for r in enriched))
        ca13 = next(r for r in districts if r["district_id"] == "CA-13")
        self.assertEqual(ca13["cook_pvi_label"], "D+2")
        prior, interpolated = {"AL", "OH", "TN"}, {"CA", "FL", "LA", "NC", "TX", "UT"}
        self.assertTrue(all(r["cook_pvi_status"] == "available" for r in districts))
        self.assertTrue(all(r["pres_2020_status"] == r["pres_2024_status"] == (
            "prior_boundaries" if r["state"] in prior else "interpolated" if r["state"] in interpolated else "available")
            for r in districts))
        self.assertEqual(collections.Counter(r["pres_2024_status"] for r in districts),
                         {"available": 262, "interpolated": 142, "prior_boundaries": 31})
        statuses = collections.Counter(r["poll_avg_status"] for r in districts)
        self.assertEqual(statuses["available"], 111)
        me02 = next(r for r in districts if r["district_id"] == "ME-02")
        self.assertEqual(me02["poll_avg_dem_margin_pp"], "-1.35")
        akal = next(r for r in districts if r["district_id"] == "AK-AL")
        self.assertEqual((akal["poll_avg_dem_candidate"], akal["poll_avg_matchup_basis"]), ("Bill Hill", "reviewed"))
        guide_statuses = collections.Counter(r["guide_status"] for r in districts)
        self.assertEqual(guide_statuses, {"in_guide": 44, "not_in_guide": 391})
        self.assertEqual((me02["guide_slot_et"], me02["guide_rep_candidate"]), ("8:00", "LePage"))
        self.assertNotIn("mismatch", {r["guide_name_check"] for r in districts})


if __name__ == "__main__":
    import unittest
    unittest.main()
