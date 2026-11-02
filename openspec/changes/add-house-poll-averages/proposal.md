# Proposal

## Why

The district context dataset describes each House seat's partisan history but not the current race. The repository already holds a 2026 House polling snapshot, about 6,300 answer rows. For each candidate, the only polling signal that reaches the district data is the `in_general_polls` flag. A transparent weighted polling average for each nominee matchup puts the current race next to the 2020 and 2024 margins and the Cook PVI for election-night viewing and analysis.

## What Changes

- Build a weighted polling average for each district from the saved `2026/polls/us-house-polls.csv`. Use only 2026 general-election questions that put the district's Democratic nominee against its Republican nominee from the candidate field. Exclude generic-ballot, primary, special-election, nationwide `US`, and hypothetical-matchup questions.
- Select one question per poll. Weight each poll by recency, sample size, the number of polls the same pollster has in that district, and whether a party sponsored it. All weighting constants are named and documented.
- Publish a district-level averages file plus a question-level input log. The log lists every considered question, whether it was included, why, and the parts of its weight, so any average can be traced back to its source rows.
- Append the average columns to `house-district-context.csv` and `house-candidate-context.csv`. These columns hold the Democratic and Republican candidates' averaged shares, the Democratic-minus-Republican margin, poll and pollster counts, the latest poll end date, a status, and a source ID. Districts with no eligible polling keep blank values and a status that says why. They are never zero-filled.
- Keep `--require-complete` limited to the presidential margins and Cook PVI. Missing polls are expected and do not fail a strict build.
- Document the method, the constants, the limitations, and the new rebuild order.

## Capabilities

### New Capabilities

- `house-poll-average`: Selecting eligible House general-election poll questions, matching them to nominees, weighting them, and publishing a district-level polling average with a traceable record of each input question.

### Modified Capabilities

- `house-district-context`: The exports gain the polling-average columns and the poll-specific status values. The strict completeness check explicitly excludes the polling average. Context builds also fail if the saved averages are stale for the current poll snapshot or candidate field.

## Impact

- New script `scripts/build_house_poll_averages.py` and tests. It uses only the standard library and runs offline with `uv`.
- New outputs `2026/polls/house-poll-averages.csv` and `2026/polls/house-poll-average-inputs.csv`.
- `scripts/build_house_district_context.py` reads the averages and appends columns, so both context CSVs gain columns at the end. Existing columns, their positions, values, and row counts do not change.
- Updated docs: `docs/district-data.md`, plus a new polling section and the rebuild order in `README.md`.
- No new network access, credentials, or dependencies. Polling acquisition remains manual.

Out of scope: forecasts or win probabilities, house-effect or partisan-lean adjustments, pollster quality ratings (the snapshot's `numeric_grade` and `pollscore` columns are empty), the national generic ballot, Senate or governor polling, matchups involving independent or third-party nominees, ranked-choice reallocation, and any change to candidate identity decisions or the `in_general_polls` flag.
