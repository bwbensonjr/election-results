import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import flag_general_candidates as flag


def report(committee="C1", receipt="2026-10-22", number=1):
    return dict(committee_id=committee, committee_name=committee, receipt_date=receipt,
                file_number=number, beginning_image_number=str(number))


class CommitteeTests(unittest.TestCase):
    def test_shared_principal_committee_and_order(self):
        records = [dict(candidate_id=cid, principal_committees=[dict(committee_id="C1")])
                   for cid in ["H1", "H2", "OUTSIDE"]]
        for ordered in [records, records[::-1]]:
            with patch.object(flag, "fetch_all", return_value=ordered):
                links = flag.fetch_principal_committees(None)
            matched, unmatched = flag.attribute_reports(None, {"C1": report()}, links, {"H1", "H2"})
            self.assertEqual(set(matched), {"H1", "H2"})
            self.assertEqual(unmatched, [])

    def test_fallback_retains_all_ids_and_rows(self):
        data = {"results": [{"candidate_ids": ["H1", "OUTSIDE"]}, {"candidate_ids": ["H2"]}]}
        with patch.object(flag, "get_json", return_value=data):
            matched, _ = flag.attribute_reports(None, {"C1": report()}, {}, {"H1", "H2"})
        self.assertEqual(set(matched), {"H1", "H2"})

    def test_latest_and_tied_reports_across_committees(self):
        reports = {"C1": report(number=2), "C2": report("C2", number=10),
                   "C3": report("C3", receipt="2026-10-21", number=100)}
        links = {cid: {"H1"} for cid in reports}
        for items in [reports, dict(reversed(list(reports.items())))]:
            matched, _ = flag.attribute_reports(None, items, links, {"H1"})
            self.assertEqual(matched["H1"], reports["C2"])
        with patch.object(flag, "fetch_all", return_value=[report(number=2), report(number=10)]):
            self.assertEqual(flag.fetch_12g_reports(None)["C1"]["file_number"], 10)

    def test_unmatched_committee(self):
        with patch.object(flag, "get_json", return_value={"results": []}):
            matched, unmatched = flag.attribute_reports(None, {"C1": report()}, {}, {"H1"})
        self.assertEqual(matched, {})
        self.assertEqual(unmatched, ["C1"])


if __name__ == "__main__":
    unittest.main()
