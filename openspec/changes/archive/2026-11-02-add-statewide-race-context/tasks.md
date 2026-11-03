# Tasks

## 1. Source acquisition

- [x] 1.1 Add `--office {H,S}` to `fetch_fec_house_candidates.py` and `flag_general_candidates.py` with office-specific default paths, keeping House defaults. Verify that existing tests pass, new fixture tests cover Senate paths and the `office=S` request parameters, and a House run with no flags writes the same paths as before.
- [x] 1.2 Create `scripts/fetch_ballotbrief_statewide.py` for `/candidates/us-senate` and `/candidates/governor`, with the House fetcher's crawl delay and truncated-race handling. Verify with offline HTML fixture tests for list parsing, a truncated race, and party parsing.
- [x] 1.3 Fetch and commit `ballotbrief-statewide-candidates.csv` and the FEC Senate candidate, flagged, and general files (network and `FEC_API_KEY`). Verify the expected race counts (about 35 Senate including the OH and FL specials, about 36 governor), and record any difference with its cause.
- [x] 1.4 Document the statewide sources, fetch commands, and the Ballot Brief caveat in `docs/candidate-pipeline.md`. Verify that the documented commands match the scripts' arguments.

## 2. Statewide candidate field

- [x] 2.1 Extend `candidate_identity` decision loading to accept an `office` field (absent means House) and to reject decisions whose IDs are not that office's records. Verify that a House rebuild is byte-identical, and that new tests cover a Senate decision, a Senate decision naming a House ID, and Senate matching that ignores same-name House records.
- [x] 2.2 Create `scripts/build_statewide_field.py`, which writes `statewide-general-field.csv`, `statewide-match-review.csv`, and `statewide-field-discrepancies.csv`. Senate rows resolve against Senate FEC records and `senate-identity-decisions.json`, governor rows get `not_federal`, and poll presence uses each office's snapshot. Verify with fixture tests for a duplicate race failure, `not_federal` blanks, office-scoped poll presence, a 12G filer missing from the ballot, and shuffled-input determinism.
- [x] 2.3 Run the build on committed inputs, review unmatched and ambiguous Senate candidates, and add evidence-backed decisions to `senate-identity-decisions.json`. Verify that the review queue is empty or that each remaining row is explained in the snapshot review section of `docs/candidate-pipeline.md`.
- [x] 2.4 Document the statewide field schema, match statuses, and review procedure in `docs/candidate-pipeline.md`. Verify that each documented column matches the output header.

## 3. State partisan history

- [x] 3.1 Capture Cook's latest (2025) state PVI list, transcribed from Wikipedia's Cook PVI article because Cook's list is subscriber-only, to `2026/results/cook-state-pvi-2025-source.csv`. Add a `cook_state_pvi` manifest entry with its URLs, edition, retrieval date, acquisition method, and checksum. Verify that the snapshot covers every state with a 2026 statewide race, or list the gaps.
- [x] 3.2 Add state aggregation and state PVI normalization to `district_history.py`, writing `state-presidential-normalized.csv` and `cook-state-pvi-normalized.csv`. Verify with tests covering a multi-district sum, an at-large state, a state missing one district's counts, label parsing, a duplicate state, and a checksum mismatch. Also verify that the district normalized outputs are byte-identical.
- [x] 3.3 Document the state history sources, the summing rule, and its limits in a new `docs/statewide-data.md`, linked from `docs/district-data.md`. Verify the documented column definitions against the output headers.

## 4. Statewide polling average

- [x] 4.1 Extract race-agnostic selection and weighting from `build_house_poll_averages.py` without changing its outputs. Verify that a House rebuild is byte-identical and that existing tests pass.
- [x] 4.2 Create `scripts/build_statewide_poll_averages.py` and `2026/polls/statewide-principal-matchups.json` (Nebraska Senate: Osborn). The build writes `statewide-poll-averages.csv` and `statewide-poll-average-inputs.csv`. Verify with tests for an off-cycle governor question, an unknown race, a reviewed matchup with a mismatched poll party code, a stale matchup entry failing, a non-principal pairing, equal weights for a shared House and statewide fixture, recomputing a margin from the log, and shuffled-input determinism.
- [x] 4.3 Run on the snapshots and review excluded questions in MT, SD, ID, and AK for any further principal matchups. Verify that roughly 29 Senate and 33 governor races are `available`, close to the design trial, and explain any difference.
- [x] 4.4 Document the statewide method differences (principal matchups, matchup basis, reason codes) in `docs/statewide-data.md`. Verify that documented codes match the script.

## 5. Guide validation and context exports

- [x] 5.1 Add statewide validation to `election_guide.py` (one row per state and office, race exists in the statewide field) behind `--statewide-field`. Verify with tests for a duplicate Senate row and an unknown governor race, that House validation tests still pass, and that the committed 18 rows validate.
- [x] 5.2 Create `scripts/build_statewide_race_context.py`, which writes `2026/statewide/statewide-race-context.csv`, `statewide-candidate-context.csv`, and `statewide-context-issues.csv` with stale-input checks and `--require-complete`. Verify with tests for state metrics shared by `GA-SEN` and `GA-GOV`, candidate grain preserved, polling and guide values copied, `NE-SEN` name check `matched` with `Osborn (I)`, a missing PVI issue row, stale averages failing with previous exports preserved, and a strict build passing with unpolled races.
- [x] 5.3 Document the context schemas, rebuild order, and analytical examples in `docs/statewide-data.md` and `README.md`. Verify that the documented command sequence runs offline from the repository root.

## 6. Integration

- [x] 6.1 Run the full House rebuild and confirm that `git diff` shows no House output changes. Then run the statewide sequence with `--require-complete`. Verify the row counts (statewide races, candidates, input-log questions equal to the snapshots' question counts) and hand-check `KS-SEN` and `NE-SEN` against their logged inputs.
- [x] 6.2 Run the full offline test suite and `openspec validate add-statewide-race-context --strict`. Verify that both pass.

## Workflow follow-up

- Archive the change after review, then confirm that the four new main specs and the updated `candidate-identity-resolution` and `election-guide-house` specs are correct.
