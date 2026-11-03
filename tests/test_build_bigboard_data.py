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
