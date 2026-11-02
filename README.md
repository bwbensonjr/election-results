# Election Results

Use pre-election data to prepare for watching election results.

The 2026 House candidate pipeline combines a ballot-source candidate list, FEC candidacy and financial records, and candidate appearances in general-election polls. Its primary output is [`house-general-field.csv`](2026/candidates/house-general-field.csv). The November 2, 2026 snapshot contains 1,159 candidate rows across 435 districts; unresolved identities are explicitly marked and their FEC-derived fields are blank.

Implemented:

- Candidate downloads from the FEC and The Ballot Brief.
- Pre-general (12G) filing flags and district review reports.
- Conservative candidate matching, evidence-backed reviewed decisions, and an [identity review queue](2026/candidates/candidate-match-review.csv).
- A combined candidate field with FEC incumbency, financial values, and a poll-presence flag.
- Seven [polling snapshots](2026/polls), described in the original project notes as NY Times data; polling acquisition is currently manual.

Planned: district-level 2024 Harris/Trump and 2020 Biden/Trump results, PVI, a separate district incumbent roster, and an election-night briefing or watchlist.

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

## Tests

```sh
uv run --with requests python -m unittest discover -s tests -v
```

Tests use fixtures and committed snapshots without API credentials or network calls. The first run may download `requests`; use `--offline` with `uv` after dependencies and Python are cached.
