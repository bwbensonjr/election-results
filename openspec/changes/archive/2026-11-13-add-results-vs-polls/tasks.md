# Tasks

## 1. Comparison dataset

- [x] 1.1 Write `scripts/build_results_vs_polls.py` (uv script, standard library only) with a `compare_race(base_row, result_race)` function that finds the two poll principals by `baseline_name`, computes result shares, result margin, difference, and status (`compared`, `no_polls`, `no_votes`, `principal_missing`) per design decisions 1, 2, and 7. Verify with unit tests in `tests/test_build_results_vs_polls.py` using a small fixture: AK-AL (independent principal, result margin -7.41), a D+2.50 poll with an R+1.00 result (difference -3.50), a `no_polls` race with a winner, a `no_votes` race, and a missing principal.
- [x] 1.2 Add the poll-list builder that unifies included rows from `house-poll-average-inputs.csv` and `statewide-poll-average-inputs.csv` into the design decision 6 schema and sort order. Verify with tests that excluded rows (`superseded`, `out_of_cycle`) are dropped and that each fixture race's poll count matches its average's `poll_count`; the build fails, naming the race, when a real count differs.
- [x] 1.3 Add the CLI: default results file `2026/results/ap-results.json`, `--results` override, atomic writes of `2026/results/results-vs-polls.csv` and `2026/results/results-vs-polls-polls.csv`, failure without replacing outputs when a baseline race is missing from the results, and a printed count per status. Verify with tests for the missing-race failure and by running the build twice against the snapshot and confirming byte-identical outputs with 506 comparison rows and 1,458 poll rows.
- [x] 1.4 Review the generated CSV (spot-check AK-AL, AK-SEN, one governor race, and one `no_polls` House race against the snapshot by hand) and commit both files. Document the dataset (purpose, columns, sign convention, statuses, rebuild command) in a new section of `docs/big-board.md` and add the build to the README rebuild order. Verify the documented command runs as written.

## 2. Board data

- [x] 2.1 Extend `scripts/build_bigboard_data.py` to read `results-vs-polls-polls.csv` and embed `polls` as compact per-race arrays sorted newest first (design decision 5), bumping nothing else in the schema except adding the key. Verify with an updated `tests/test_build_bigboard_data.py` that checks the key, the row shape, and the ordering for a fixture race, and by rerunning the build and noting the new page size (expected under 450 KB; measured 474 KB, accepted as well under the artifact limit).

## 3. Big Board metric and detail

- [x] 3.1 Add the Results vs. Polls button (`data-metric="rvp"`) between Polls and President, the difference function mirroring `compare_race`, a 2/5/10 bin function, and `fillFor` handling: solid for called, hatched lead patterns for uncalled, neutral `--nodata` for every other status. Verify in a local preview that AL-01 is grey, a called polled race is solid, and the button works in Governor, Senate, and House modes.
- [x] 3.2 Add the legend for the metric ("Results vs. polls", red-to-blue ramp, ticks `<2 · 2–5 · 5–10 · 10+ pts`, hatched uncalled sample, and grey labeled "No polling average or no votes"). Update the tooltip under this metric to show the signed difference. Verify in the preview in light and dark schemes.
- [x] 3.3 Add the detail block (design decision 8): result shares and margin for the principals, polling average with count, signed difference in party ink, partial-count note with expected vote for uncalled races, "No polling average" message for unpolled races, and the poll table newest first in a height-capped scroll region, followed by the existing candidates and facts. Verify in the preview that AK-SEN shows 21 polls with the latest end date at the top and that the layout has no horizontal scroll at 375 pixels.
- [x] 3.4 Check the page against the dataset: for AK-AL, AK-SEN, and three other `compared` races, confirm the page's difference equals `diff_pp` in `results-vs-polls.csv` built from the same results file. Verify by recording the five values in the task notes or commit message.
- [x] 3.5 Update `docs/big-board.md` (metrics list, color steps for Results vs. Polls, detail contents) and the big-board metrics bullet list at the top of the doc. Verify the doc matches the page.

## 4. Integration and publish

- [x] 4.1 Run the full test suite (`uv run --with requests --with beautifulsoup4 python -m unittest discover -s tests -v`) and verify that it passes.
- [x] 4.2 Republish the board to the URL in `bigboard/artifact.json` (root `bigboard`, fallback `data/results.json`, `capabilities` omitted), and verify that the published page shows the Results vs. Polls button, colors, and detail, and still receives live database results.

## Workflow follow-up

- Archive the change after review and sync the delta specs into `openspec/specs/`.
