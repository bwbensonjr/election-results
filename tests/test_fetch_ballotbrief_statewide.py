import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_ballotbrief_statewide as fetch

ROW = ('<li><a href="/state/{slug}">{label}</a><span>{names}</span>'
       '<a href="/state/{slug}">{count} &rarr;</a></li>')
LIST_PAGE = "<ul>" + "".join([
    ROW.format(slug="georgia", label="Georgia", names="Jon Ossoff (D), Mike Collins (R)", count=2),
    ROW.format(slug="alabama", label="Alabama", names="Tommy Tuberville (R), Doug Jones (D) (+1 more contests)",
               count=2),
    ROW.format(slug="florida", label="Florida",
               names="Byron Donalds (R), David Jolly (D), Smith, Jr. (NPA) and 2 more", count=5),
    ROW.format(slug="idaho", label="Idaho", names="Brad Little (R), Pro-Life (Constitution)", count=2),
]) + '</ul><nav><a href="/state/florida">Florida</a></nav>'
STATE_PAGE = """
<div class="bl-group" id="statewide">
  <details class="bl-row" id="race-governor" data-office="Governor"><summary><span class="bl-title">Governor</span></summary>
    <div class="bl-body">
      <div class="bl-cand"><div class="bl-name">Byron Donalds</div><div class="bl-party">Republican</div></div>
      <div class="bl-cand"><div class="bl-name">David Jolly</div><div class="bl-party">Democrat</div></div>
      <div class="bl-cand"><div class="bl-name">Smith, Jr.</div><div class="bl-party">No party affiliation</div></div>
      <div class="bl-cand"><div class="bl-name">Dean Abrams</div><div class="bl-party">No party affiliation</div></div>
      <div class="bl-cand"><div class="bl-name">Write In</div></div>
    </div></details>
  <details class="bl-row" id="race-u-s-senate" data-office="U.S. Senate"><summary><span class="bl-title">U.S. Senate</span></summary>
    <div class="bl-body">
      <div class="bl-cand"><div class="bl-name">Ashley Moody</div><div class="bl-party">Republican</div></div>
    </div></details>
</div>
"""


class ParseTests(unittest.TestCase):
    def test_list_page_races_and_parties(self):
        races = fetch.parse_list_page(LIST_PAGE)
        self.assertEqual([r[0] for r in races], ["GA", "AL", "FL", "ID"])
        self.assertEqual(races[0], ("GA", "/state/georgia", [("Jon Ossoff", "D"), ("Mike Collins", "R")], False))
        self.assertEqual(races[3][2], [("Brad Little", "R"), ("Pro-Life", "Constitution")])

    def test_more_contests_note_is_not_a_party(self):
        _, _, candidates, truncated = fetch.parse_list_page(LIST_PAGE)[1]
        self.assertEqual(candidates, [("Tommy Tuberville", "R"), ("Doug Jones", "D")])
        self.assertFalse(truncated)

    def test_truncated_race_reads_state_contest(self):
        state, href, candidates, truncated = fetch.parse_list_page(LIST_PAGE)[2]
        self.assertTrue(truncated)
        self.assertEqual(candidates[2], ("Smith, Jr.", "NPA"))
        full = fetch.parse_state_page(STATE_PAGE, fetch.OFFICES["Governor"][1])
        self.assertEqual([name for name, _ in full],
                         ["Byron Donalds", "David Jolly", "Smith, Jr.", "Dean Abrams", "Write In"])
        self.assertEqual(full[3], ("Dean Abrams", "No party affiliation"))
        self.assertEqual(full[4], ("Write In", ""))
        self.assertEqual(fetch.parse_state_page(STATE_PAGE, fetch.OFFICES["Senate"][1]),
                         [("Ashley Moody", "Republican")])

    def test_missing_contest_and_unknown_state(self):
        self.assertEqual(fetch.parse_state_page("<div></div>", "race-governor"), [])
        with self.assertRaises(ValueError):
            fetch.parse_list_page(ROW.format(slug="guam", label="Guam", names="A B (D)", count=1))


if __name__ == "__main__":
    unittest.main()
