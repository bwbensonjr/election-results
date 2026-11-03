# Proposal

## Why

The repository prepares only the House for election night: a resolved candidate field, presidential margins and Cook PVI, a weighted polling average, and the guide's watch-list columns, all joined at district grain. The November 3, 2026 ballot also carries the Senate and governor races that decide Senate control and that the guide watches in 18 of its 62 rows. The Senate and governor poll snapshots are already committed (about 3,500 and 3,200 general-election answer rows), but nothing uses them. This change produces the same context for every statewide race.

## What Changes

- Download the Senate and governor general-election candidates from The Ballot Brief (`/candidates/us-senate` and `/candidates/governor`) and the 2026 Senate candidates from the FEC (`office=S`), with pre-general (12G) flags and financial totals.
- Build one statewide candidate field covering every Senate and governor race on the November 3 ballot, including the Ohio and Florida special Senate elections. Senate candidates resolve to FEC identities through the existing conservative matcher and a separate reviewed-decision registry. Governor candidates are not federal candidates, so their FEC-derived fields stay blank with an explicit `not_federal` status instead of a false value.
- Add statewide partisan history: 2020 and 2024 presidential margins by state, computed from the committed district vote counts, and Cook's state PVI from a new saved snapshot recorded in the source manifest. Cook's 2026 update re-scored only House districts, so the latest state edition is 2025. It uses the same 2020 and 2024 elections, and the snapshot is Wikipedia's transcription of it because Cook's state list is subscriber-only.
- Build a weighted polling average for each statewide race from the saved Senate and governor snapshots. It uses the House method's eligibility rules, one-question-per-poll selection, weights, and input log. A small reviewed matchup file covers races where the principal opponent of the Republican is an independent (for example Nebraska's Osborn) rather than a Democrat.
- Publish a race-grain context export and a candidate-grain context export that join the field, the state history, the polling average, and the guide's Senate and governor rows, with the same status columns and missing-value rules as the House exports.
- Validate the guide's Senate and governor rows against the statewide field: at most one row per state and office, each naming a race in the field, with a name check on the guide's candidates.
- Document the sources, schemas, method differences, and rebuild order.

## Capabilities

### New Capabilities

- `statewide-candidate-field`: Assembling the Senate and governor general-election field from the ballot source, FEC Senate records, 12G flags, finance, and poll presence, with one race per state and office.
- `state-partisan-history`: Statewide 2020 and 2024 presidential margins aggregated from district vote counts, and Cook's latest published (2025) state PVI, with provenance and explicit unknowns.
- `statewide-poll-average`: Selecting, matching, and weighting Senate and governor general-election poll questions into a traceable race-level average, including reviewed non-Democratic principal matchups.
- `statewide-race-context`: Race-grain and candidate-grain exports that join the field, state history, polling average, and guide rows offline and reproducibly.

### Modified Capabilities

- `candidate-identity-resolution`: Matching and reviewed decisions become scoped by office, so Senate candidates resolve within their state and office using a separate registry. House behavior and decisions are unchanged.
- `election-guide-house`: Senate and governor guide rows gain validation against the statewide field (uniqueness per state and office, and existence of the race) before they are joined.

## Impact

- New scripts: `fetch_ballotbrief_statewide.py`, `build_statewide_field.py`, `build_statewide_poll_averages.py`, and `build_statewide_race_context.py`. The FEC fetch and 12G flag scripts gain an `--office` option, keeping House as the default. `district_history.py` gains state aggregation and a Cook state-PVI format.
- New data under `2026/candidates/` (statewide ballot, FEC Senate, flagged, field, review queue, decision registry), `2026/results/` (Cook state snapshot and normalized state history), `2026/polls/` (statewide averages and input log), and a new `2026/statewide/` directory for the two context exports and an issue report.
- Shared helpers (name matching, `poll_candidates`, weight functions, staged publishing) are reused, not copied. The House outputs must not change; the House rebuild and tests are a regression gate.
- Refreshing sources needs network access and `FEC_API_KEY`; the rebuild stays offline. No new dependencies.
- Updated docs: `README.md`, `docs/candidate-pipeline.md`, `docs/district-data.md`, or a new statewide section.

Out of scope: state-level campaign finance for governors, forecasts or win probabilities, ranked-choice reallocation (Alaska, Maine), Georgia or Louisiana runoff modeling, other statewide executive offices, comparing guide Senate and governor rows with the guide markdown, and any change to House candidate identities or House outputs.
