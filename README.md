# Election Results

Use pre-election data to prepare for watching election results.

The 2026 House candidate pipeline combines a ballot-source candidate list, FEC candidacy and financial records, and candidate appearances in general-election polls. Its primary output is [`house-general-field.csv`](2026/candidates/house-general-field.csv). The November 2, 2026 snapshot contains 1,159 candidate rows across 435 districts; unresolved identities are explicitly marked and their FEC-derived fields are blank.

Implemented:

- Candidate downloads from the FEC and The Ballot Brief.
- Pre-general (12G) filing flags and district review reports.
- Conservative candidate matching, evidence-backed reviewed decisions, and an [identity review queue](2026/candidates/candidate-match-review.csv).
- A combined candidate field with FEC incumbency, financial values, and a poll-presence flag.
- Seven [polling snapshots](2026/polls), described in the original project notes as NY Times data; polling acquisition is currently manual.
- A weighted [House polling average](2026/polls/house-poll-averages.csv) of each district's Democratic and Republican nominees, with a question-level [input log](2026/polls/house-poll-average-inputs.csv) of every inclusion decision and weight.

The [district context dataset](2026/districts/house-district-context.csv) joins 2020 Biden/Trump and 2024 Harris/Trump source margins with published Cook 2026 PVI for all 435 districts, and appends the polling average where one exists. In the current snapshot, 111 districts have an average and the rest have blank polling columns with a status explaining why. A separate [candidate context dataset](2026/districts/house-candidate-context.csv) retains all candidate details and appends those metrics. See the [district-data reference](docs/district-data.md) for source editions, schemas, and analytical examples.

Planned: a separate district incumbent roster and an election-night briefing or watchlist.

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

These commands read saved source snapshots and need no API key or live Cook access. District IDs normalize at-large seats to `STATE-AL` and district code `00`. Margins are Democratic minus Republican in percentage points. Cook PVI retains its published 2026 label and a numeric lean, positive for D and negative for R.

The join uses normalized district IDs without boundary approval checks. The supplied historical results' map vintage is undocumented; they are used as supplied, and the [source notes](docs/district-data.md) explain limits on historical comparisons. Missing metrics are reported rather than assigned zero or EVEN. The current strict build has all three metrics for every district. Polling averages are optional: strict mode does not require them, and unpolled districts keep blank polling columns rather than zeroes. See the [polling-average method](docs/district-data.md#house-polling-averages) for eligibility, weights, and limitations.

## Tests

```sh
uv run --with requests python -m unittest discover -s tests -v
```

Tests use fixtures and committed snapshots without API credentials or network calls. The first run may download `requests`; use `--offline` with `uv` after dependencies and Python are cached.
