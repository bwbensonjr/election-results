# Tasks

## 1. Block sources and crosswalk build

- [x] 1.1 Confirm the Census 119th Congress block assignment file URLs and the TIGER/Line 2020 `tabblock20` URLs for CA, FL, LA, NC, TX, and UT, and write `2026/results/presidential-crosswalk-sources.json` (URL, retrieval date, SHA-256 per file). Verify that every file downloads into `2026/geometry/cache/blocks/` and matches its hash.
- [x] 1.2 Write `scripts/build_presidential_crosswalk.py` (uv script). It verifies hashes, reads block attributes without geometry, joins blocks to their 119th Congress districts, places block internal points in the 2026 plan shapes using the geometry manifest's `district_field` and `layer_path`, sends unplaced points to the nearest district, and writes the crosswalk and report CSVs. Verify by running it and checking that each old district's shares sum to 1 and every 2026 district appears.
- [x] 1.3 Add the failure cases: a hash mismatch, unplaced population over 0.1%, a 2026 district missing from the crosswalk, and a registry state without shapes listed as not interpolated. Each must fail without replacing outputs. Verify with `tests/test_build_presidential_crosswalk.py`, using tiny fixture blocks and shapes.
- [x] 1.4 Run the build for real, review `presidential-crosswalk-report.csv` (unplaced counts; AL, OH, and TN listed as not interpolated), and commit the crosswalk files. Verify that a second run produces byte-identical output.
- [x] 1.5 Add the 2020 and 2024 county presidential results to `presidential-crosswalk-sources.json` with hashes. Key the crosswalk by old district, county, and new district, and write `presidential-county-results.csv` with each county's 2020 block population. Fail, keeping outputs, when a populated county lacks a result for either year. Verify with new fixture tests and a real rebuild that is byte-identical on a second run.

## 2. Standard-library interpolation in normalization

- [x] 2.1 Add `interpolate_presidential` to `scripts/district_history.py`, using Decimal reallocation and recomputing shares and margins with the source definitions. Verify with unit tests in `tests/test_district_history.py`, including the spec example of -8.89 points.
- [x] 2.2 Add the conservation check (state totals within 1 vote for each year), failing with the state and year named. Verify with a test that perturbs a crosswalk share.
- [x] 2.3 Have `normalize_district_history.py` write `presidential-results-interpolated.csv` and `presidential-interpolation-review.csv`, the latter reusing the boundary-review lean and threshold, and record the crosswalk hash in `source-manifest.json`. Verify that it runs offline without geopandas and that the state presidential files are unchanged.
- [x] 2.4 Weight reallocation by county vote rates (design decision 6) and record the county table's hash in `source-manifest.json`. Verify with the spec's 75/25 county example and the conservation test in `tests/test_district_history.py`, and by rerunning normalization and checking that UT-01 moves to a Democratic margin.
- [x] 2.5 Compute the interpolation review's implied lean with Cook's 75/25 year weights, keeping the boundary review unchanged. Verify with the spec's swing example and an unchanged committed `boundary-review.csv`.

## 3. District context statuses

- [x] 3.1 Update `build_house_district_context.py` so crosswalk states get the interpolated values, status `interpolated`, and the interpolation source ID. Registry states without a crosswalk stay `prior_boundaries`, and strict mode counts `interpolated` as present. Extend the recompute-and-compare check to the interpolated CSV. Verify with updated `tests/test_house_district_context.py` and `uv run scripts/build_house_district_context.py --require-complete` (142 `interpolated` and 31 `prior_boundaries` districts).
- [x] 3.2 Update `docs/district-data.md` (Redrawn states and a new interpolation method section with its limitations) and the README rebuild order. Verify that the documented commands run as written.

## 4. Baseline and Big Board

- [x] 4.1 Update `build_election_baseline.py` to carry the 2024 margin when the status is `available` or `interpolated`. Verify with `tests/test_build_election_baseline.py` (UT-01 interpolated, TN-05 blank) and a rebuilt baseline.
- [x] 4.2 Update `bigboard/index.html` to color `interpolated` margins under President and to label them "est. on 2026 lines" in the race detail, then rerun `scripts/build_bigboard_data.py`. Verify with `tests/test_build_bigboard_data.py`, and check in the running page that the TX, CA, FL, NC, LA, and UT districts are colored while AL, OH, and TN stay grey.
- [x] 4.3 Update `docs/big-board.md` (President metric and detail wording). Verify that the doc matches the page's behavior.

## 5. Integration and publish

- [x] 5.1 Run the full test suite (`uv run --with requests --with beautifulsoup4 python -m unittest discover -s tests -v`) and verify that it passes.
- [x] 5.2 Republish the board to the URL in `bigboard/artifact.json` (root `bigboard`, fallback `data/results.json`, `capabilities` omitted), and verify that the published page shows the redrawn districts colored under President.

## Workflow follow-up

- Archive the change after review and sync the delta specs into `openspec/specs/`.
