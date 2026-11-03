# Tasks

## 1. House ballot corrections

- [x] 1.1 Add `2026/candidates/house-ballot-corrections.json` with the reviewed AK-AL entry splitting the merged row into Bill Hill (independent) and James C. "Jim" McDermott (Libertarian), with Ballot Brief and poll evidence; verify the file parses and names exactly one source row.
- [x] 1.2 Apply corrections in `scripts/build_house_field.py` before district grouping, appending a `source_correction` column and failing on stale, duplicate-matching, or unevidenced entries; verify with new tests in `tests/test_build_house_field.py` for a split row, a stale entry, and unchanged uncorrected rows.
- [x] 1.3 Rebuild the House field and verify AK-AL has separate Hill and McDermott rows, Hill has `in_general_polls` true, and every other district's rows are unchanged apart from the new column.
- [x] 1.4 Document the corrections file and column in `docs/candidate-pipeline.md` and verify the documented rebuild command runs as written.

## 2. House principal matchups

- [x] 2.1 Add `2026/polls/house-principal-matchups.json` with a reviewed AK-AL entry naming Bill Hill and Nick Begich; verify it validates against the House field.
- [x] 2.2 Extend `scripts/build_house_poll_averages.py` to use reviewed principals, skip party-code checks for them, append `poll_avg_matchup_basis`, and fail on entries for unknown districts or absent candidates; verify with tests in `tests/test_build_house_poll_averages.py` covering the reviewed independent principal, a stale entry, and an unchanged nominee-basis district.
- [x] 2.3 Rebuild the House averages and verify AK-AL's average is Hill against Begich with basis `reviewed`, and every other district's values are byte-identical apart from the new column.
- [x] 2.4 Document principal entries and the non-Republican-principal meaning of `poll_avg_dem_*` in `docs/district-data.md`; verify the AK-AL example in the docs matches the rebuilt output.

## 3. Boundary vintage

- [x] 3.1 Add the PVI consistency check to `scripts/district_history.py` writing `2026/results/boundary-review.csv` with the documented four-point threshold; verify a test fixture with one mismatched district appears in the report and the build still succeeds.
- [x] 3.2 Create `2026/results/boundary-vintage.json` listing each state with a different 2026 congressional plan, confirmed against an evidence URL for its enacted plan and against a published list of 2025-2026 redistricting, not only the check; verify every state flagged by the check is either listed or explained in the entry notes.
- [x] 3.3 Add registry loading and validation, a per-district boundary status, and `prior_boundaries` presidential statuses in `scripts/district_history.py` and `scripts/build_house_district_context.py`; verify with tests in `tests/test_district_history.py` and `tests/test_house_district_context.py` for a listed state, an unlisted state, an invalid entry, and `--require-complete` succeeding with `prior_boundaries` values.
- [x] 3.4 Document the registry, statuses, and review report in `docs/district-data.md` and record the registry in `2026/results/source-manifest.json`; verify the manifest validates in the context build.

## 4. Incumbent roster

- [x] 4.1 Capture saved snapshots of the U.S. Senate member list and the National Governors Association governor list to `2026/roster/sources/` and record URL, retrieval date, and SHA-256 in the source manifest; verify the files exist and the manifest hashes match.
- [x] 4.2 Write `scripts/build_incumbent_roster.py` to seed `2026/roster/incumbent-roster.json` (506 entries) from the Cook 2026 table and the statewide snapshots and write a review report of disagreements with the presidential source and vacancies; verify a test seeds the expected entry count from fixtures and reports a disagreement.
- [x] 4.3 Review the seeded roster: resolve every report row and all 71 statewide entries with evidence, and confirm known cases (Kiggans VA-02, Lawler NY-17, Keating MA-09, Begich AK-AL); verify the report has no unresolved rows and the docs state how many entries remain seed-only.
- [x] 4.4 Add roster validation, computed ballot status with reviewed overrides, and appended roster columns to `scripts/build_house_district_context.py`; verify with tests for a running incumbent, an open seat, an incumbent running for another office, a missing district, and unchanged FEC `incumbent` values.
- [x] 4.5 Add the same roster columns to `scripts/build_statewide_race_context.py`, including governors; verify with tests in `tests/test_statewide_race_context.py` for a running governor, an open Senate seat, and unchanged earlier columns.
- [x] 4.6 Document the roster, its sources, and the new columns in `docs/district-data.md`, `docs/statewide-data.md`, and `README.md` (replacing the "planned incumbent roster" note); verify the README build commands run as written.

## 5. Election-night baseline

- [x] 5.1 Write `scripts/build_election_baseline.py` producing `2026/baseline/race-baseline.csv`, `candidate-baseline.csv`, and `election-baseline.json` from the context exports and roster, with race keys, AP join fields, blank AP ID columns, current-boundary 2024 margins only, no 2020 margins, and stale-input checks; verify with a new `tests/test_build_election_baseline.py` covering row counts, key uniqueness, a redrawn district, an unchanged district, the AK-AL candidates, and byte-identical rebuilds.
- [x] 5.2 Document the baseline files, columns, and AP join fields in a new `docs/election-baseline.md` linked from `README.md`; verify the documented build command runs as written.

## 6. Integration

- [x] 6.1 Rebuild everything in the design's build order with `--require-complete` where supported and verify all builds exit zero, `uv run pytest` passes, and the baseline has 506 race rows.
- [x] 6.2 Spot-check the baseline against the known problems: AK-AL principal Hill with basis `reviewed`; incumbents for Kiggans, Lawler, Keating, and Begich; a governor incumbent; UT-01 with a blank 2024 margin and status `prior_boundaries`; MA-04 with its 2024 margin; and verify each in the output files.

## Workflow follow-up

- Archive the change after review, then sync specs.
- Start the AP results feed change, which fills `ap_race_id` and `ap_candidate_id` and settles AP seat numbering.
