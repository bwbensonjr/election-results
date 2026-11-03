# Tasks

## 1. Endpoint capture and findings

- [x] 1.1 Save a gzipped pre-election national response as `tests/fixtures/globe-2026-11-03-pre.json.gz` and add `2026/live/` (except `.gitkeep`) to `.gitignore`; verify the fixture loads with 862 races and `git status` shows no files under `2026/live/raw/`
- [x] 1.2 Record the endpoint test findings (payload, filters, cache header, office codes, at-large seat `1`, specials, Louisiana race type, national `US` row, candidate differences) in `2026/results/election-endpoints.md`, and replace the two "to settle" notes in `docs/election-baseline.md` with the confirmed answers; verify both pages render and their links resolve

## 2. Artifact data path check

- [x] 2.1 Publish a throwaway artifact whose page fetches a small supporting JSON file by relative path, republish only that file, and record whether an open view sees the new content, reloads, or fails; verify the outcome is noted in `design.md` Open Questions, and if the fetch fails switch tasks 6.5 and 7.1 to 7.2 to the inline-results fallback before continuing

## 3. District shapes

- [x] 3.1 Record `cb_2024_us_cd119_20m.zip` from `https://www2.census.gov/geo/tiger/GENZ2024/shp/` in `2026/geometry/sources.json` with plan, retrieval date, and SHA-256; verify the downloaded file matches the recorded hash
- [x] 3.2 Write `scripts/build_district_geometry.py`: hash-checked download into an ignored cache, drop Puerto Rico, keep D.C. with no race, normalize keys, Albers USA composite fitted to 960 × 600, topology-preserving simplification to about 12% of points, states merged from districts, vintage per district, and output `2026/geometry/us-house-2026.json` with paths, state bounding boxes, and district center points; verify 435 district keys equal the baseline House keys, all nine registry states are listed as `prior_boundaries`, and the file is under 400 KB
- [x] 3.3 Add enacted-plan overrides: a manifest `override` entry for a registry state replaces its districts and marks them `plan_2026`; verify with a test fixture override for one state
- [x] 3.4 Add `tests/test_build_district_geometry.py` covering a hash mismatch, key normalization (`AK-AL`, `VT-AL`, `TX-38`), Puerto Rico removal, the D.C. shape, a registry state with and without an override, the frame bounds, and byte-identical rebuilds; verify `uv run tests/test_build_district_geometry.py` passes
- [x] 3.5 Time-boxed to one hour: find state-published 2026 plan shapefiles for TX, CA, NC, OH, and UT first, then AL, FL, LA, and TN, adding each as an override with its hash; verify each added state renders its 2026 district count and is reported as `plan_2026`, and list the states still on prior lines
- [x] 3.6 Render the shapes once in a scratch page and check alignment of state and district borders, Alaska and Hawaii placement, and any overridden states against their plan maps; record the check, the build command, and the prior-line states in a new `docs/big-board.md` section

## 4. Results ingestion

- [x] 4.1 Write `scripts/ingest_results.py` with `--source live|PATH`, raw snapshot saving, race selection, the baseline race join, and fail-closed join errors; verify a run on the fixture writes `2026/live/results.json` with 506 races and a national House summary
- [x] 4.2 Add candidate matching by normalized surname and party, vote shares, leader margin, call status and winner parsing (candidate `winner` flag and call status, unknown status treated as uncalled), and the test flag; verify on the fixture that at least 1,370 baseline candidates link and unmatched AP candidates are listed
- [x] 4.3 Add atomic writes, `status.json` with a `changed` flag, `--every SECONDS` repeating mode with a JSONL run log, and failure handling that keeps the last good file; verify two runs on the same input report unchanged and a run against an unreachable URL leaves `results.json` untouched
- [x] 4.4 Add `tests/test_ingest_results.py` covering at-large and special-election joins, a missing race, an extra race, a write-in line, a called race, replay of saved snapshots, and the unchanged flag; verify `uv run python -m unittest tests.test_ingest_results` passes
- [x] 4.5 Document the ingestor (sources, outputs, schedule, failure behavior, `results.json` schema) in `docs/big-board.md` and the README; verify the documented commands run as written

## 5. Mock election-night feed

- [x] 5.1 Write `scripts/mock_election_feed.py` that loads the fixture and the baseline and writes `--steps`/`--step-minutes` responses with poll-close gating, monotonic S-curve counting, seeded outcomes around poll averages or PVI, calls, a forced too-close race, ranked-choice and Louisiana handling, and `test: true`; verify the ingestor accepts every step of a 40-step night
- [x] 5.2 Add `--play SECONDS --out PATH` to rewrite one file on a timer; verify the ingestor in `--every 60` mode picks up each new step
- [x] 5.3 Add `tests/test_mock_election_feed.py` covering shape equality with the fixture, zero votes before poll close, monotonic counts, seeded reproducibility, and final-step calls and edge cases; verify `uv run python -m unittest tests.test_mock_election_feed` passes
- [x] 5.4 Document mock usage and a rehearsal recipe in `docs/big-board.md`; verify the recipe runs as written

## 6. Big Board page

- [x] 6.1 Write `scripts/build_bigboard_data.py` that writes the slim baseline (only columns the board uses) and the district shapes into a marked data block in `bigboard/index.html`; verify byte-identical rebuilds, that hand-written page code outside the block is untouched, and a test in `tests/test_build_bigboard_data.py`
- [x] 6.2 Load the artifact-design and dataviz skills, then build `bigboard/index.html`: office modes, drawing the embedded pre-projected paths in a 960 × 600 `viewBox`, not-on-ballot styling, dashed prior-line districts, and the four color metrics with a legend; verify in the browser pane that each mode and metric renders against mock results
- [x] 6.3 Add zoom and pan, zoom to a state by its recorded bounding box, district labels at recorded center points when zoomed, search by race key, state, or candidate, and the race detail panel (bottom sheet on phones); verify selecting PA-07, GA-SEN, an open seat, and a prior-line district shows every detail field, including the 2024-lines note
- [x] 6.4 Add results coloring (solid calls, hatched leads, third-party color), called-seat summaries, AP and publish times, the 15-minute staleness warning, and the test-data banner; verify with mock steps before, during, and after calls
- [x] 6.5 Add 60-second polling of `data/results.json`, re-render on a new `generated_at`, and view state for mode, metric, zoom, and selection kept through the viewer `hot` snapshot and `localStorage`; verify a reload and a data change both keep the view
- [x] 6.6 Check phone width (375 px), light and dark schemes, and keyboard selection in the browser pane; verify no horizontal scroll and readable contrast

## 7. Publishing loop and rehearsal

- [x] 7.1 Publish the board with the Artifact tool, with mock `results.json` as its one supporting file; verify the published page draws the map from embedded data, loads the results, and shows the test banner
- [x] 7.2 Run a rehearsal: mock in play mode, ingestor every 60 seconds, and a Claude `/loop` that republishes `data/results.json` only when `status.json` says it changed; verify at least three republishes show up on an open board without a manual reload, or that a reload restores the view
- [x] 7.3 Write the election-night runbook (terminals, commands, keep-awake, loop prompt, restart and rollback) in `docs/big-board.md`; verify it matches the commands used in the rehearsal

## 8. Live cutover (before 6pm ET)

- [ ] 8.1 Stop the mock, run the ingestor with `--source live --every 120`, and republish; verify the test banner is gone and races show `Awaiting Poll Close`
- [ ] 8.2 After the first calls in Kentucky and Indiana, compare the parsed winners with the raw snapshots and fix call parsing if needed; verify by replaying the saved snapshots through the ingestor

## Workflow follow-up

- After election night, sync specs and archive the change once results are final enough to review.
