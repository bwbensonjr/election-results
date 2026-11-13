# Election Results

Use pre-election data to prepare for watching election results.

The 2026 House candidate pipeline combines a ballot-source candidate list, FEC candidacy and financial records, and candidate appearances in general-election polls. Its primary output is [`house-general-field.csv`](2026/candidates/house-general-field.csv). The November 2, 2026 snapshot contains 1,160 candidate rows across 435 districts; unresolved identities are explicitly marked and their FEC-derived fields are blank.

Implemented:

- Candidate downloads from the FEC and The Ballot Brief.
- Pre-general (12G) filing flags and district review reports.
- Conservative candidate matching, evidence-backed reviewed decisions, and an [identity review queue](2026/candidates/candidate-match-review.csv).
- A combined candidate field with FEC incumbency, financial values, and a poll-presence flag.
- Seven [polling snapshots](2026/polls), described in the original project notes as NY Times data; polling acquisition is currently manual.
- A validated [election-night guide races CSV](2026/guide/election-night-guide-races.csv) of the 62 races (44 House, 14 Senate, 4 governor) named in the [November 3 guide](2026/guide/election-night-guide-november-3-2026.md), with watch slots, poll-close times, ratings, seat-ladder tiers, and the guide's signals.
- A weighted [House polling average](2026/polls/house-poll-averages.csv) of each district's Democratic and Republican nominees, with a question-level [input log](2026/polls/house-poll-average-inputs.csv) of every inclusion decision and weight.

The [district context dataset](2026/districts/house-district-context.csv) joins 2020 Biden/Trump and 2024 Harris/Trump source margins with published Cook 2026 PVI for all 435 districts, and appends the polling average and the election-night guide's House race columns where they exist. In the current snapshot, 111 districts have an average and the rest have blank polling columns with a status explaining why. A separate [candidate context dataset](2026/districts/house-candidate-context.csv) retains all candidate details and appends those metrics. See the [district-data reference](docs/district-data.md) for source editions, schemas, and analytical examples.

The same context is built for the 71 Senate and governor races on the November 3 ballot (35 Senate, including the Ohio and Florida specials, and 36 governor). The [statewide candidate field](2026/candidates/statewide-general-field.csv) has 260 candidates, with FEC identities for Senate candidates and an explicit `not_federal` status for governors. The [race context](2026/statewide/statewide-race-context.csv) and [candidate context](2026/statewide/statewide-candidate-context.csv) exports join state 2020 and 2024 presidential margins (summed from the district vote counts), Cook's latest (2025) state PVI, a weighted polling average of each race's principal matchup, and the guide's Senate and governor rows. In the current snapshot, 62 races have a polling average. See the [statewide reference](docs/statewide-data.md).

A reviewed [incumbent roster](docs/district-data.md#incumbent-roster) names the incumbent for every House, Senate, and governor race on the 2026 ballot and whether each seat is open. In six of the nine states that redrew for 2026, presidential margins are estimated on the new lines from a block- and county-level crosswalk, with status `interpolated`. The other three keep their old-line margins with status `prior_boundaries` (see [redrawn states](docs/district-data.md#redrawn-states)).

An election-night [Big Board](docs/big-board.md) maps every House, Senate, and governor race and follows live results: `scripts/ingest_results.py` reads the AP-backed Globe elections feed into `2026/live/results.json` (`uv run scripts/ingest_results.py --every 120`), `scripts/mock_election_feed.py` generates a simulated night for rehearsal, and the board is a published Claude Artifact built from `bigboard/`.

## Rebuild from committed inputs

Install Python 3.11+ and `uv`, then run from the repository root:

```sh
uv run scripts/build_house_field.py
```

This builder needs no API key or network access once Python is available. It validates the [reviewed identity registry](2026/candidates/candidate-identity-decisions.json) and writes the combined field, identity review queue, and [discrepancy report](2026/candidates/field-discrepancies.csv). Unknown identity is distinct from a verified false value.

## Refresh source data

For FEC access, obtain a key through [api.data.gov](https://api.data.gov/signup/) and set `FEC_API_KEY` in your environment or a local, ignored `.env` file containing `FEC_API_KEY=your_key`. Do not commit the key. Network access is required; `uv` installs the scripts' declared dependencies.

```sh
uv run scripts/fetch_fec_house_candidates.py --totals
uv run scripts/flag_general_candidates.py
uv run scripts/fetch_ballotbrief_house.py
uv run scripts/build_house_field.py
uv run scripts/fetch_fec_house_candidates.py --office S --totals
uv run scripts/flag_general_candidates.py --office S
uv run scripts/fetch_ballotbrief_statewide.py
uv run scripts/build_statewide_field.py
```

Use `--totals` to include the financial columns required by the builder. Refresh polling CSVs separately before rebuilding; there is no poll-download script. Review unmatched identities, ambiguous records, stale registry decisions, and output changes after every refresh.

The implemented ballot source is [The Ballot Brief](https://theballotbrief.com/candidates/us-house), a secondary source that warns its AI-assisted information can contain errors. Verify important ballot details with official sources. [Ballotpedia](https://ballotpedia.org/List_of_congressional_candidates_in_the_2026_elections) is an additional reference, not an input to these scripts. FEC registration, incumbency codes, filing flags, and a poll appearance do not certify the general-election ballot.

See the [pipeline reference](docs/candidate-pipeline.md) for file schemas, identity-review procedures, sources, limitations, dated review dispositions, and refresh status.

## Build district data for viewing and analysis

After rebuilding the candidate field, run:

```sh
uv run scripts/normalize_district_history.py
uv run scripts/build_house_poll_averages.py
uv run scripts/build_house_district_context.py --require-complete
```

Then build the Senate and governor data:

```sh
uv run scripts/build_statewide_field.py
uv run scripts/build_statewide_poll_averages.py
uv run scripts/build_statewide_race_context.py --require-complete
```

Finally, publish the election-night baseline of all 506 races, keyed for an AP results feed (see the [baseline reference](docs/election-baseline.md)):

```sh
uv run scripts/build_election_baseline.py
```

`normalize_district_history.py` also writes the state presidential and Cook state PVI files the statewide context needs. These commands read saved source snapshots and need no API key or live Cook access. District IDs normalize at-large seats to `STATE-AL` and district code `00`. Margins are Democratic minus Republican in percentage points. Cook PVI retains its published 2026 label and a numeric lean, positive for D and negative for R.

The join uses normalized district IDs. The supplied presidential results describe the 2024 map; in the nine states listed in the reviewed [boundary registry](docs/district-data.md#redrawn-states), margins are reallocated to the 2026 lines with the committed crosswalk (status `interpolated`) where an enacted plan is available, and otherwise get status `prior_boundaries`. Cook PVI is the measure on current lines. Rebuilding the crosswalk needs network access (`uv run scripts/build_presidential_crosswalk.py`; see [interpolated margins](docs/district-data.md#interpolated-margins-on-2026-lines)); normalization only reads the committed copy. Missing metrics are reported rather than assigned zero or EVEN. The current strict build has all three metrics for every district. Polling averages are optional: strict mode does not require them, and unpolled districts keep blank polling columns rather than zeroes. See the [polling-average method](docs/district-data.md#house-polling-averages) for eligibility, weights, and limitations. The context build also validates the guide CSV against the guide markdown; after editing the guide, update the affected rows and run `uv run scripts/election_guide.py` (see the [guide conventions](docs/district-data.md#election-night-guide)).

## Tests

```sh
uv run --with requests --with beautifulsoup4 python -m unittest discover -s tests -v
```

Tests use fixtures and committed snapshots without API credentials or network calls. The first run may download `requests` and `beautifulsoup4`; use `--offline` with `uv` after dependencies and Python are cached.
