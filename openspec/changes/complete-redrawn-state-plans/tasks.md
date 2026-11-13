# Tasks

## 1. 2026 shapes for Alabama, Ohio, and Tennessee

- [x] 1.1 Add `overrides` entries for AL, OH, and TN in `2026/geometry/sources.json`, using the TIGER/Line 2026 `tl_2026_<fips>_cd120.zip` files (`district_field` `CD120FP`, URL, plan description, retrieval date, SHA-256). Rebuild `us-house-2026.json`. Verify that `prior_line_states` is empty, all 435 districts are `current` or `plan_2026`, and the output is under 400 KB.
- [x] 1.2 Update `tests/test_build_district_geometry.py` expectations: the committed manifest leaves no prior-line states, and OH-09 is `plan_2026`. Update the "Still on 2024 lines" paragraph in `docs/big-board.md`. Verify with `uv run tests/test_build_district_geometry.py`.

## 2. Crosswalk with the Census 2026 assignment check

- [x] 2.1 Add the AL, OH, and TN `tabblock20` entries and a `bef_2026` entry for `cd120.zip` (member `NationalCD120.txt`) to `presidential-crosswalk-sources.json`, with hashes. Verify that each cached file matches its hash.
- [x] 2.2 Make `read_bef` select `GEOID` and `CDFP` by name. Compute each state's agreement between point-in-polygon and Census 2026 districts by population, write it as `census_agreement_pct` in the report, and fail below 99.9 percent without replacing outputs. Verify with new fixture tests in `tests/test_build_presidential_crosswalk.py` (agreement passes, a renumbered plan fails) and the existing ones.
- [x] 2.3 Rebuild the crosswalk and county table for all nine states. Review the report: no unplaced population over the limit, and agreement of at least 99.9 percent everywhere. Verify that a second run is byte-identical.

## 3. Interpolated margins and context

- [x] 3.1 Update the crosswalk and county-table hashes in `source-manifest.json`, rerun normalization, and review `presidential-interpolation-review.csv` for the new states. Check AL-02 and TN-09 against their Cook PVI direction. Verify that the state presidential files and `boundary-review.csv` are unchanged.
- [x] 3.2 Rebuild the district context with `--require-complete`, and update the test expectations in `tests/test_house_district_context.py` to 262 `available`, 173 `interpolated`, and 0 `prior_boundaries`. Verify with the context tests.
- [x] 3.3 Update `docs/district-data.md` (redrawn states, interpolation section counts and largest gaps, the new check) and `README.md`. Verify that the stated counts match the outputs.

## 4. Baseline and Big Board

- [x] 4.1 Rebuild the baseline. Update `tests/test_build_election_baseline.py` (TN-05 now `interpolated`) and `docs/election-baseline.md`. Verify with the baseline tests.
- [x] 4.2 Rebuild the board data and update `tests/test_build_bigboard_data.py` (173 `interpolated`; TN-05 interpolated on a `plan_2026` shape) and the President text in `docs/big-board.md`. Verify with the board-data tests and a headless-Chrome check that AL, OH, and TN are colored under House/President.

## 5. Integration and publish

- [x] 5.1 Run the full test suite plus the two geospatial suites, and verify that all pass.
- [x] 5.2 Commit, then republish the board to the URL in `bigboard/artifact.json` (root `bigboard`, fallback `data/results.json`, `capabilities` omitted). Update `artifact.json`, and verify that the published page carries 173 interpolated districts.

## Workflow follow-up

- Archive the change after review and sync its delta specs.
