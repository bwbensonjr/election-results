# Tasks

## 1. Question selection and nominee matching

- [x] 1.1 Create `scripts/build_house_poll_averages.py` with the `uv` script header, check required columns, group answers by question, and map districts using the field's at-large states. Verify with offline fixture tests: a missing column fails, `VT` seat `1` maps to `VT-AL`, a numbered seat is zero-padded, and a seat absent from the field logs `unknown_district`.
- [x] 1.2 Implement the ordered exclusion rules (`out_of_cycle`, `not_general`, `nationwide`, `missing_seat`, `no_dem_rep_field`, `not_head_to_head`). Drop `NONE` and `Generic` answers and reallocated ranked-choice rows. Verify with fixture tests covering a `US` generic-ballot question, a primary, a party-label-only question, a D-vs-D district, and a ranked-choice question that keeps only first-round shares.
- [x] 1.3 Match DEM and REP answers to field nominees through `build_house_field.poll_candidates`. Verify with tests: a hypothetical non-nominee matchup logs `non_nominee`, an ambiguous surname logs `ambiguous_match`, and a third-party answer alongside both nominees is still eligible.
- [x] 1.4 Select one question per poll (`lv` > `rv` > `a`, then the most matched field candidates, then `question_id`) and log the others as `superseded`. Parse `pct`, `sample_size`, and `end_date` strictly for head-to-head candidates only. Verify with tests for the population preference and its tie-breaks, a malformed `pct` that fails and names the question, and a malformed out-of-scope primary that does not fail.

## 2. Weighting, outputs, and polling docs

- [x] 2.1 Implement the recency, sample, pollster, and partisan factors with the named constants from the design. Anchor recency to each district's latest included poll. Verify with tests: hand-computed weights for a three-poll fixture, a missing sample size imputed and flagged, a repeated pollster damped by `1/sqrt(k)`, and identical output when the build runs on different dates.
- [x] 2.2 Write `house-poll-averages.csv` (one row per field district, with the four status values and blank non-available values) and `house-poll-average-inputs.csv` (one row per snapshot question), sorted and published through staged replacement. Verify with tests: the weighted margin can be recomputed from the log, `no_polls` values are blank rather than zero, shuffled poll rows give byte-identical outputs, and a failed build leaves the previous outputs intact.
- [x] 2.3 Add a polling-average section to `docs/district-data.md` covering eligibility, matching, the selection order, the weight formulas and constant rationale, the output schemas, status values, and limitations (internal polls, single-poll districts, no quality ratings). Verify that every documented column, constant, and reason code matches the script.

## 3. Join to district context

- [x] 3.1 Add `--polls` to `build_house_district_context.py`. Recompute the averages in memory and fail on stale saved averages before publishing, then append the polling columns at the end of both context exports. Verify with existing and new context tests: polled and unpolled districts carry the correct values and statuses, candidate rows repeat their district's values, existing columns keep their positions and values, a stale averages file fails and preserves the outputs, and `--require-complete` passes when only polling is missing.
- [x] 3.2 Keep polling out of `district-context-issues.csv` and the strict check. Update the context schema table, the rebuild order, and analytical examples in `docs/district-data.md` and `README.md`. Verify that the issues report is unchanged for the committed snapshot and that the documented command sequence runs offline from the repository root.

## 4. Build and integrate the current snapshot

- [x] 4.1 Run the four-step rebuild on the committed inputs. Verify 435 averages rows, about 111 `available` districts (matching the design's trial count or explaining any difference), 1,680 input-log rows, 435 and 1,159 context rows, and a hand check of ME-02 and AK-AL against their logged inputs.
- [x] 4.2 Run the full offline test suite, the normal and `--require-complete` context builds, and `openspec validate add-house-poll-averages --strict`. Verify that everything passes and that `git diff` shows only the expected new outputs and appended columns.

## Workflow follow-up

- Archive the change after review, then confirm that the `house-poll-average` and updated `house-district-context` main specs are correct.
