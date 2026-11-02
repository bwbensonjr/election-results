# Design

## Context

See `proposal.md` for motivation and `specs/` for the required behavior.

These facts were observed in the committed November 2, 2026 snapshot:

- `2026/polls/us-house-polls.csv` has 6,321 answer rows, 1,298 polls, and 1,680 questions. It has one row per answer, keyed by `poll_id` and `question_id`, with `state`, `seat_number`, `stage`, `cycle`, `population` (`lv`/`rv`/`a`), `sample_size`, `partisan` (the sponsor's party), `party`, `candidate_name`, `pct`, `ranked_choice_round`, and `ranked_choice_reallocated`. Dates use the `m/d/yy` format.
- 3,233 of the 4,662 general-stage rows belong to the nationwide generic ballot (`state=US`, no seat). The other 1,429 rows cover 119 districts.
- `numeric_grade`, `pollscore`, `transparency_score`, `hypothetical`, and `source` are empty in every row. No pollster-quality signal is available.
- At-large seats use `seat_number=1`, for example AK, SD, and VT. `build_house_field.py` already maps these to district `00`, using the field's set of at-large states.
- A trial of the matching rule below found 311 eligible questions in 111 districts. Of those districts, 40 have a single poll, and the most-polled district (AK) has 32 questions. Questions were dropped for not being a single D-versus-R pair (105) and for naming a non-nominee or an ambiguous candidate (55).
- 410 of 435 field districts have exactly one Democratic and one Republican candidate.
- `build_house_district_context.py` already recomputes the normalized history in memory and compares it with the saved files to detect stale outputs. It also publishes all CSVs through a staged replacement.

## Goals / Non-Goals

**Goals:** a simple average that can be audited and reproduced by hand from its input log. It must stay stable when the build date changes, and missing polling must be easy to tell apart from a tied race.

**Non-Goals:** statistical modeling (house effects, trend lines, uncertainty intervals), adjusting polls with national generic-ballot movement, and a cutoff date that would drop old polls. Exponential decay already sets how much old polls count.

## Decisions

### 1. A standalone polling build that the context join verifies

Add `scripts/build_house_poll_averages.py`. It is a standard-library module with a CLI that has `--polls`, `--candidates`, and `--output-dir` options. It writes `2026/polls/house-poll-averages.csv` (district grain) and `2026/polls/house-poll-average-inputs.csv` (question grain), and it uses the same staged publish pattern as the other builds. `build_house_district_context.py` gets a `--polls` option. It imports the module, recomputes the averages in memory, and compares the result with the saved averages file before it appends columns. This is the same freshness check that the normalized history uses.

Alternative considered: computing averages inside the context builder. This was rejected because the input log is useful by itself, and because the existing scripts keep each source stage separate. A further alternative was to add the polls to `source-manifest.json`. This was rejected because that manifest's schema is fixed to the presidential and PVI formats, and recomputing the averages already detects a stale snapshot.

### 2. Selecting questions and matching nominees

Group answer rows by `question_id`. For each question, the reason is the first rule it fails, in this order:

`out_of_cycle` → `not_general` → `nationwide` → `missing_seat` → `unknown_district` → `no_dem_rep_field` → `not_head_to_head` → `non_nominee` / `ambiguous_match` → `superseded`

Included questions have a blank reason.

- **District key.** Map the poll's state and seat to the field: at-large states become `00`, and other seats are zero-padded. Validate the result against the field's district set.
- **Candidate answers.** Drop answers with party `NONE` or a `Generic` candidate name. For ranked-choice questions, keep only rows where `ranked_choice_reallocated` is not `TRUE`.
- **Head-to-head check.** The remaining answers must include exactly one `DEM` and one `REP`. Use `build_house_field.poll_candidates` to match each against all of the district's field rows. More than one hit is `ambiguous_match`. A single hit that is not that party's nominee, or no hit, is `non_nominee`. The rule is shared so that the averages and `in_general_polls` cannot disagree about who a poll names.
- **One question per poll.** Within a poll, rank eligible questions by population (`lv` < `rv` < `a`), then by the number of answers that match field candidates (descending), then by `question_id`. The losers get the reason `superseded`.

### 3. Weights

`weight = recency × sample × pollster × partisan`, using named module constants:

| Factor | Formula | Constant(s) |
| --- | --- | --- |
| recency | `0.5 ** (age_days / HALF_LIFE_DAYS)`, where `age_days` = district's latest included end date − this poll's end date | `HALF_LIFE_DAYS = 21` |
| sample | `sqrt(min(n, SAMPLE_CAP) / SAMPLE_REFERENCE)`; a blank `n` uses `SAMPLE_DEFAULT` and is flagged | `SAMPLE_REFERENCE = 600`, `SAMPLE_CAP = 1500`, `SAMPLE_DEFAULT = 600` |
| pollster | `1 / sqrt(k)`, where `k` = that pollster's selected polls in the district | none |
| partisan | `PARTISAN_FACTOR` if `partisan` is nonblank, else 1 | `PARTISAN_FACTOR = 0.5` |

Recency is anchored to each district's latest poll, not to today or election day. Only relative weights within a district affect the mean, so the anchor removes any dependence on the build date without changing the result. Staleness is reported through `poll_latest_end_date` instead.

The 21-day half-life is shorter than the life of a typical race but longer than the gap between polls in thinly polled districts. The square root on sample size reflects how sampling error shrinks. The cap stops very large online panels from dominating. Without pollster ratings, the pollster factor and the partisan discount are the only defenses against one firm or one campaign's internal polls flooding a district.

Alternatives considered: a hard date window, which throws data away in districts with few polls; house-effect correction, which needs more polls per pollster than most districts have; and excluding partisan polls entirely. Party-sponsored polls make up about a third of answer rows, so excluding them would empty many districts.

### 4. Average values and output schema

Weighted means of `dem_pct`, `rep_pct`, and the per-poll `dem_pct − rep_pct` margin are rounded to 2 decimals. Shares are computed over all respondents and are not rescaled to two-party totals. This matches the presidential `dem_margin_pp` definition, and undecided voters remain visible. Dates are written in ISO format.

`house-poll-averages.csv` columns:

`state, district, district_id, poll_avg_dem_candidate, poll_avg_rep_candidate, poll_avg_dem_pct, poll_avg_rep_pct, poll_avg_dem_margin_pp, poll_count, poll_pollster_count, poll_latest_end_date, poll_avg_status, poll_avg_source_id`

Every column after `district_id` is appended to the end of both context exports, so every existing column keeps its position. `poll_avg_source_id = us-house-polls-2026`. Nominee names come from the candidate field, not from the poll's spelling. On non-available rows the names are blank as well.

`house-poll-average-inputs.csv` columns:

`poll_id, question_id, state, district, district_id, stage, pollster, end_date, population, sample_size, sample_size_imputed, partisan, dem_candidate, rep_candidate, dem_pct, rep_pct, dem_margin_pp, included, reason, age_days, recency_factor, sample_factor, pollster_factor, partisan_factor, weight`

Rows are sorted by `district_id`, `end_date`, `poll_id`, and `question_id`. Factors and weights are rounded to 6 decimals. A row with no district or no match leaves the irrelevant fields blank.

### 5. Validation

Required snapshot columns are checked before any processing. Only questions that reach the head-to-head step have their `pct`, `sample_size`, and `end_date` parsed strictly. Malformed data in out-of-scope primaries therefore cannot block the build, but malformed data in a candidate question fails with its `question_id` and field. Duplicate `(question_id, candidate answer)` rows are an error.

## Risks / Trade-offs

- **Internal polls bias the margin toward their sponsor.** → The partisan factor halves their weight, and the input log shows their share of each average. House-effect correction is deferred.
- **One poll can be the whole average in 40 districts.** → `poll_count` and `poll_pollster_count` appear beside the margin, and the docs warn against reading single-poll averages as precise.
- **Surname matching could pick the wrong nominee.** → Ambiguous matches are excluded and logged. The rule is the same reviewed logic that already drives `in_general_polls`.
- **The tuning constants are judgment calls.** → They are named constants, documented with their rationale, and every factor is logged. Retuning changes values but not the schema or the specs.
- **Consumers that require an exact column set see new trailing columns.** → Documented in the proposal and the docs. Existing columns, their positions, values, and row counts are unchanged.

## Migration Plan

The new rebuild order is:

1. `build_house_field.py`
2. `normalize_district_history.py`
3. `build_house_poll_averages.py`
4. `build_house_district_context.py [--require-complete]`

Commit the regenerated averages, input log, and context CSVs together. To roll back, revert the commit. No other data depends on the new columns.

## Open Questions

- Should the constants be tuned after the election by comparing averages with the results? This would only change values, not the method or the schema.
