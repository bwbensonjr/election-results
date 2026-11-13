import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_bigboard_data as board

PAGE = """<title>T</title>
<p>before</p>
<!-- board-data:begin -->
<script type="application/json" id="board-data">{}</script>
<!-- board-data:end -->
<script>const after = "</script>";</script>
"""


class BoardDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.page = Path(self.temp.name) / "index.html"
        self.page.write_text(PAGE)

    def embedded(self):
        text = self.page.read_text()
        payload = re.search(r'id="board-data">(.*?)</script>', text, re.S).group(1)
        return text, json.loads(payload)

    def test_embeds_races_shapes_and_candidates(self):
        board.build(self.page)
        _, data = self.embedded()
        self.assertEqual(len(data["races"]), 506)
        self.assertEqual(len(data["geometry"]["districts"]), 435)
        races = {r[0]: dict(zip(data["race_columns"], r)) for r in data["races"]}
        self.assertEqual(races["GA-SEN"]["office"], "Senate")
        self.assertIn("AK-AL", data["candidates"])
        self.assertEqual(data["state_names"]["PA"], "Pennsylvania")

    def test_interpolated_margins_reach_the_page(self):
        board.build(self.page)
        _, data = self.embedded()
        races = {r[0]: dict(zip(data["race_columns"], r)) for r in data["races"]}
        statuses = {}
        for race in races.values():
            if race["office"] == "House":
                statuses[race["pres_2024_status"]] = statuses.get(race["pres_2024_status"], 0) + 1
        self.assertEqual(statuses, {"available": 262, "interpolated": 173})
        self.assertEqual((races["UT-01"]["pres_2024_status"], races["UT-01"]["pres_2024_dem_margin_pp"]),
                         ("interpolated", "7.50"))
        self.assertEqual((races["TN-05"]["pres_2024_status"], races["TN-05"]["pres_2024_dem_margin_pp"]),
                         ("interpolated", "-27.50"))
        districts = data["geometry"]["districts"]
        self.assertTrue(all(districts[k]["vintage"] == "plan_2026" for k, r in races.items()
                            if r["pres_2024_status"] == "interpolated"))

    def test_poll_lists_newest_first(self):
        board.build(self.page)
        _, data = self.embedded()
        self.assertEqual(data["poll_columns"][:2], ["end_date", "pollster"])
        races = {r[0]: dict(zip(data["race_columns"], r)) for r in data["races"]}
        polls = data["polls"]["AK-SEN"]
        self.assertEqual(len(polls), int(races["AK-SEN"]["poll_count"]))
        self.assertTrue(all(len(p) == len(data["poll_columns"]) for p in polls))
        dates = [p[0] for p in polls]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(dates[0], "2026-11-01")
        self.assertNotIn("AL-01", data["polls"])
        self.assertEqual(sum(len(v) for v in data["polls"].values()), 1458)

    def test_rest_of_page_untouched_and_rebuild_identical(self):
        board.build(self.page)
        first, _ = self.embedded()
        self.assertTrue(first.startswith("<title>T</title>\n<p>before</p>\n"))
        self.assertTrue(first.endswith('<script>const after = "</script>";</script>\n'))
        board.build(self.page)
        self.assertEqual(self.page.read_text(), first)

    def test_markers_required(self):
        self.page.write_text("<p>no markers</p>")
        with self.assertRaises(board.BuildError):
            board.build(self.page)


if __name__ == "__main__":
    unittest.main()
