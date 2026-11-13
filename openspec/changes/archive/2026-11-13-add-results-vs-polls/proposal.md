# Proposal

## Why

The project has a weighted polling average for 173 of the 506 races (111 House, 62 Senate and governor) and, since November 13, nearly complete AP results (492 races called). The obvious post-election question is where the polls missed and by how much, but today the only way to answer it is to flip between the Polls and Results metrics and compare numbers by eye. A per-race comparison dataset, and a Big Board view built on it, answers it directly and keeps answering it as late counts change the margins.

## What Changes

- New build `scripts/build_results_vs_polls.py` writes two committed files under `2026/results/`:
  - `results-vs-polls.csv`: one row for every baseline race in all three offices (Governor, Senate, House; 506 rows). Each row has the polling average (principals, shares, margin, poll count), the result for the same two principals (shares and margin, read from the results file by baseline candidate name), the difference (result margin minus poll margin), call status, percent of expected vote, and a comparison status.
  - `results-vs-polls-polls.csv`: every poll question included in a race's average, from both the House and statewide input logs, in one set of columns.
- The difference is signed like every other margin in the project: positive means the Democratic principal (or the reviewed non-Republican principal, such as AK-AL's Bill Hill) did better than the polls, negative means the Republican did better. Margins compare the two principals' shares of the total vote, not the top Democrat and top Republican, so races whose poll principal is an independent are compared correctly.
- Races without an available polling average get status `no_polls` and no difference, whatever their result. Races with polls but no votes get `no_votes`.
- The Big Board gets a new **Results vs. Polls** metric button beside Results, Polls, President, PVI, and Incumbent, for all three office modes. The map colors each race by its difference, computed live from the same results the board already receives: blue for Democratic over-performance, red for Republican, darker for larger misses, in steps suited to polling error. Races without polling are drawn in a neutral grey, with no result coloring; uncalled races use the board's existing hatched style.
- The race detail under this metric shows the result for the two principals, the polling average, the difference, and the list of polls in the average, newest first.
- The board's embedded data adds the included polls for each race with an average.

Out of scope:

- Changing how the polling averages are computed or which polls they include.
- Comparing against polls excluded from the average, or against the generic ballot.
- Two-party normalization or undecided allocation. The comparison is on raw margins, the same basis as the averages.
- Historical comparisons (2024 or earlier polling error).

## Capabilities

### New Capabilities
- `results-vs-polls`: the per-race comparison of results to the polling average for Governor, Senate, and House, the principal-matching and sign rules, the comparison statuses, and the combined list of included polls.

### Modified Capabilities
- `big-board`: the color metrics requirement adds Results vs. Polls, with its color scale and neutral treatment of races without polling, and a new requirement covers the race detail under that metric (result, average, difference, and polls newest first).

## Impact

- New script `scripts/build_results_vs_polls.py` (standard library only, offline) and `tests/test_build_results_vs_polls.py`. Inputs: `2026/baseline/election-baseline.json`, `2026/polls/house-poll-average-inputs.csv`, `2026/polls/statewide-poll-average-inputs.csv`, and a results file (default the checked-in snapshot `2026/results/ap-results.json`; `--results` to point at `2026/live/results.json`).
- `scripts/build_bigboard_data.py` embeds the per-race poll lists; `bigboard/index.html` adds the metric, legend, coloring, and detail. The embedded data grows by roughly 80 to 100 KB (about 1,450 included polls).
- Docs: `docs/big-board.md` (metric and detail) and a short section on the comparison dataset. The board is republished to its existing URL.
- No change to the results ingestor, the live database records, or the poll average builds.
