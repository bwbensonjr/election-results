import collections
import csv
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_house_district_context as context
import build_house_field as candidates
import district_history as history
from test_district_history import HistoryFixture, ROOT, write_csv


class ContextTests(HistoryFixture):
    def setUp(self):
        super().setUp()
        self.candidate_path = self.root / "candidates.csv"
        self.output = self.root / "context"
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
        self.save_candidates()
        self.normalize()

    def save_candidates(self):
        write_csv(self.candidate_path, [candidates.FIELD_COLUMNS] +
                  [[row[c] for c in candidates.FIELD_COLUMNS] for row in self.candidate_rows])

    def build(self, strict=False):
        return context.build(self.candidate_path, self.manifest,
                             self.normalized / "presidential-results-normalized.csv",
                             self.normalized / "cook-pvi-normalized.csv", self.output, strict, self.root)

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
        original = collections.Counter(tuple(r[c] for c in candidates.FIELD_COLUMNS) for r in self.candidate_rows)
        actual = collections.Counter(tuple(r[c] for c in candidates.FIELD_COLUMNS) for r in enriched)
        self.assertEqual(original, actual)
        self.assertNotIn("candidate_count", enriched[0])
        self.assertEqual(next(r for r in enriched if r["name"] == "Candidate B")["fec_candidate_id"], "")

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
        self.build()
        before = self.output_bytes()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_house_district_context.py"),
                                 "--candidates", str(self.candidate_path), "--output-dir", str(self.output),
                                 "--require-complete"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AL-99", result.stderr)
        self.assertIn("missing target metrics", result.stderr)
        self.assertEqual(before, self.output_bytes())

    def test_current_snapshot_cardinality_and_candidate_preservation(self):
        districts, enriched, issues = context.build(output_dir=self.output, require_complete=True)
        self.assertEqual(len(districts), 435)
        self.assertEqual(len({r["district_id"] for r in districts}), 435)
        self.assertEqual(len(enriched), 1159)
        self.assertEqual(issues, [])
        columns, original = history.read_records(context.DEFAULT_CANDIDATES)
        self.assertEqual(collections.Counter(tuple(r[c] for c in columns) for r in original),
                         collections.Counter(tuple(r[c] for c in columns) for r in enriched))
        ca13 = next(r for r in districts if r["district_id"] == "CA-13")
        self.assertEqual(ca13["cook_pvi_label"], "D+2")
        self.assertTrue(all(r["pres_2020_status"] == r["pres_2024_status"] == r["cook_pvi_status"] == "available" for r in districts))


if __name__ == "__main__":
    import unittest
    unittest.main()
