# Design

## Context

- The polling averages are already in the baseline: each race row in `2026/baseline/election-baseline.json` carries `poll_avg_dem_candidate`, `poll_avg_rep_candidate`, their shares, `poll_avg_dem_margin_pp`, `poll_count`, and `poll_avg_status`. The "dem" principal is the reviewed non-Republican principal where one exists (AK-AL Bill Hill, AK-SEN Mary Peltola, ID-SEN Todd Achilles, and so on).
- The included poll questions live in two input logs with slightly different columns: `2026/polls/house-poll-average-inputs.csv` (keyed by `district_id`) and `2026/polls/statewide-poll-average-inputs.csv` (keyed by `race_id`, with `office`). Rows with `included == True` are the polls in each average: 309 House and 1,149 statewide.
- Results reach the board as `results.races[race_key]` with `candidates[]`, each with `baseline_name`, `votes`, and `pct` (share of total vote). The race-level `dem_margin_pp` is top Democrat minus top Republican, which is wrong for independent principals (AK-AL would read R+41 instead of R+7.4).
- A check against the current snapshot found every available average's two principals among both the baseline candidates and the result candidates by exact `baseline_name`.
- The board is a hand-written page whose static data is embedded by `scripts/build_bigboard_data.py`; live results arrive in the artifact database and the page redraws in place. Metric coloring is in `fillFor`, the legend in `legend`, and the detail in `card`.

## Goals / Non-Goals

**Goals:**
- One definition of the comparison, implemented in the Python build and mirrored in the page, so the CSV and the board agree for the same results.
- The board's comparison stays live as late counts arrive, with no change to the ingestor or the database records.

**Non-Goals:**
- Shipping the comparison through the live database or `results.json`.
- Showing excluded polls or poll weights in the detail.

## Decisions

### 1. Compute the difference in two places from one rule
The committed CSV is computed by `scripts/build_results_vs_polls.py` from a results file. The board computes the same difference in the page from its live results and the embedded baseline poll fields. The alternative, adding the comparison to the ingestor's output, would put poll data into every database write and couple the ingestor to the poll builds for a value that is one subtraction. The rule is small enough to mirror: find the two principals by `baseline_name`, take `pct` for each, subtract, subtract the poll margin, round to two decimals. A test fixture pins the expected values (AK-AL, AK-SEN, a `no_polls` race, a `no_votes` race), and implementation checks a handful of races in the running page against the CSV.

### 2. Margins on raw shares, matching the averages
Poll shares include undecideds and results do not, so the shares themselves are not comparable, but the margins are: both are principal-minus-Republican in points. This is the usual definition of polling error and needs no allocation model. Two-party normalization was considered and rejected because the averages are not two-party and the third-party share differs by race (Alaska, Maine, Nebraska).

### 3. Statuses decide coloring, not thresholds on reporting
The board colors any `compared` race, hatched until called, using the existing lead-pattern machinery. An expected-vote threshold (say 95%) was considered, but the Results metric already uses called versus uncalled to signal provisional numbers, and on November 13 only 14 races are uncalled. The detail shows the percent of expected vote so a partial-count difference is visible.

### 4. Color steps for polling error
Margin steps of 5/10/20 points would put almost every race in the first one or two steps. Polling misses mostly fall within 10 points, so the metric uses 2/5/10, with the same four blue and red ramps already validated for both themes. The pattern definitions are reused with a separate bin function.

### 5. Poll list embedded per race, compact
`build_bigboard_data.py` reads `results-vs-polls-polls.csv` and embeds `polls: {race_key: [[end_date, pollster, population, sample_size, partisan, dem_pct, rep_pct, margin], ...]}`, pre-sorted by end date descending and pollster ascending. About 1,450 rows at roughly 60 bytes each adds 80 to 100 KB to a page of about 330 KB, well under the artifact limit. Reading the input logs directly in the board build was considered, but going through the committed poll-list file keeps the board's data identical to the dataset and gives the board build one input per concern.

### 6. Unify the two input logs into one schema
The poll list file has columns `race_key, office, poll_id, question_id, pollster, end_date, population, sample_size, sample_size_imputed, partisan, dem_candidate, rep_candidate, dem_pct, rep_pct, dem_margin_pp, weight`. House rows take `race_key` from `district_id` and office `House`; statewide rows from `race_id` and `office`. Weight is kept in the file for analysis though the board does not show it. Rows are sorted by race key, then end date descending, then pollster, then question ID, so output is deterministic.

### 7. Comparison CSV columns
`race_key, state, office, district, poll_avg_status, poll_dem_candidate, poll_rep_candidate, poll_dem_pct, poll_rep_pct, poll_dem_margin_pp, poll_count, poll_latest_end_date, result_dem_pct, result_rep_pct, result_dem_margin_pp, diff_pp, called, winner_party_group, eevp, total_votes, status, results_fetched_at`. Result shares are filled for any race whose principals are known and present, so `no_polls` rows leave poll and result-principal fields blank, while `called`, `winner_party_group`, and `eevp` are always filled from the results. `results_fetched_at` records which results the row describes.

### 8. Detail layout
Under the new metric the card keeps its header and status pill, then shows a three-row comparison block (Result, Polls, Difference, with the difference as "D +3.2 vs. polls" or "R +3.2 vs. polls" in party ink), then the poll table (date, pollster, sample with population, D-side share, R share, margin) in a scrollable region capped in height, then the existing candidates table and facts. On phones the table keeps four columns (date, pollster, shares, margin) so it fits at 375 pixels.

## Risks / Trade-offs

- [Page and Python rules drift] → One fixture of expected values is used by the Python tests, and the task list includes a side-by-side check of the page against the CSV for several races, including AK-AL.
- [A principal's name changes in a later baseline rebuild] → The build reports `principal_missing` and prints the race key, so the mismatch is visible instead of silently comparing the wrong candidate.
- [Ranked-choice races compare first-round results with first-choice polls] → Consistent on both sides; the detail already notes ranked-choice races.
- [Partial counts can mislead early on election night] → Hatching and the expected-vote note in the detail; after November 13 this matters for few races.
- [Page size] → Poll rows are compact arrays and the growth is measured in the build output; the build already prints the page size.

## Migration Plan

Build the dataset, rebuild the board data, verify in a local preview, and republish the board to its existing URL with `capabilities` omitted so the database declaration is kept. Rollback is republishing the previous page; the dataset files are additive.
