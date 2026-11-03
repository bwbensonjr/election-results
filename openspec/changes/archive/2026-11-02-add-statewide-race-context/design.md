# Design

## Context

See `proposal.md` for motivation and `specs/` for the required behavior. These facts were observed in the committed November 2, 2026 snapshot and live sources:

- The House pipeline runs in four stages: `build_house_field.py` (ballot plus FEC plus polls), `normalize_district_history.py`, `build_house_poll_averages.py`, and `build_house_district_context.py`. Each publishes through staged replacement, and the context build recomputes upstream outputs in memory to reject stale files.
- `2026/polls/us-senate-polls.csv` has 3,520 2026 general-stage answer rows (624 polls, 938 questions) in 29 states. `governor-polls.csv` has 3,191 general-stage rows (572 polls, 823 questions) in 34 states, plus 407 rows from 2025 general elections. `seat_number` is blank throughout; `seat_name` is blank except for 17 governor rows.
- A trial using the House rule (exactly one `DEM` and one `REP` after dropping `NONE` and `Generic`) finds 837 Senate questions in 29 states and 749 governor questions in 33 states. Of the rest, Alaska questions are mostly multi-Republican or ranked-choice. Montana, South Dakota, and Idaho have `IND` versus `REP` questions.
- Nebraska's Senate polls code independent Dan Osborn as `DEM`. The guide lists him as `Osborn (I)` in `other_candidate`.
- The Ballot Brief serves `/candidates/us-senate` and `/candidates/governor` with the same site layout as the House page.
- FEC Senate candidate records (`office=S`) use district `00`, so `candidate_identity.resolve` already scopes them to a state when given only Senate records.
- The committed district presidential file has vote counts for all 435 districts. Cook publishes a separate state PVI list.
- The guide races CSV has 14 Senate and 4 Governor rows, with Senate-specific `senate_path` values. Ohio and Florida Senate races are special elections.

## Goals / Non-Goals

**Goals:** statewide outputs that mirror the House files column for column where the concept carries over, so the same analysis works on both, and House outputs that stay byte-identical.

**Non-Goals:** merging House and statewide rows into one file, a general race-key abstraction across all offices, and state campaign-finance sources for governors.

## Decisions

### 1. Parallel statewide scripts over shared helpers

Add four statewide scripts that import the House modules' helpers: `candidate_identity`, `build_house_field.poll_candidates` and `publish_csvs`, the weight and selection functions from `build_house_poll_averages`, `district_history` validation, and `election_guide.name_check`. Where a House function hard-codes district keys, extract the race-agnostic core into a parameterized function and keep the House entry point's signature. The race key is `(state, office)`, written as race ID `STATE-SEN` or `STATE-GOV`.

Alternative considered: generalizing every House script to accept an `--office` flag and emit mixed files. This was rejected because House outputs are keyed and validated by district throughout, and threading an office dimension through them risks changing committed House outputs for no analytical gain.

### 2. Statewide candidate field

- `fetch_ballotbrief_statewide.py` writes `2026/candidates/ballotbrief-statewide-candidates.csv` with `state, office, name, party, source_url`. It follows the House fetcher's crawl delay and truncation handling.
- `fetch_fec_house_candidates.py` and `flag_general_candidates.py` gain `--office {H,S}` (default `H`) and office-specific default paths: `fec-senate-candidates.csv`, `fec-senate-candidates-flagged.csv`, and `fec-senate-general.csv`. House defaults are unchanged.
- `build_statewide_field.py` writes `statewide-general-field.csv` with the House field columns, with `district` replaced by `office` and `race_id`. It also writes `statewide-match-review.csv` and `statewide-field-discrepancies.csv`. Senate rows resolve against Senate FEC records only, using `senate-identity-decisions.json`, which has the House registry's schema plus `office`. Governor rows get `fec_match_status=not_federal`. Poll presence uses `poll_candidates` against the race's rows, with the office's snapshot and the House `POLLS_AFTER` window.

Alternative considered: adding Senate decisions to the House registry. This was rejected because the House loader rejects decisions for absent ballot rows, so a shared file would couple the two builds' validity.

### 3. State history from summed district counts

Summing district vote counts gives exact state totals when the districts partition the state, which they do. It avoids a new, unverified statewide source. Margins are recomputed from sums with the House rounding rule. Cook published no 2026 state PVI: its 2026 update re-scored only the House districts in the ten states that redrew. The latest state edition is 2025 (published March 6, 2025), computed from the same 2020 and 2024 elections, and redistricting does not change state scores. Cook's state list is subscriber-only, so the snapshot `2026/results/cook-state-pvi-2025-source.csv` is transcribed from the state table on Wikipedia's Cook PVI article, which cites that Cook page. Its manifest entry `cook_state_pvi` records the Wikipedia revision, the upstream Cook URL, and edition `2025`. The source is optional in the manifest, so the district normalization is unchanged. `district_history.normalize` gains a state step that writes `state-presidential-normalized.csv` and `cook-state-pvi-normalized.csv` and leaves its district outputs unchanged.

Alternative considered: deriving state PVI from district PVI. This was rejected because Cook publishes state PVI, and the existing spec forbids estimating PVI.

### 4. Principal matchup with reviewed overrides

The House average requires a D-versus-R nominee pair. Statewide races include serious independents. `2026/polls/statewide-principal-matchups.json` lists reviewed overrides keyed by race ID, naming the non-Republican principal candidate with evidence, reviewer, and date. An entry also names the Republican principal when a race has several Republicans (Alaska's top-four ballot). Data review produced five entries: AK-SEN (Peltola vs. Dan Sullivan), ID-SEN (Achilles), MT-SEN (Bodnar, who polls well ahead of the Democrat), NE-SEN (Osborn), and SD-SEN (Bengs). AK-GOV has no entry, because three Republicans split the first round. When two answers match one principal, only the answer with an exact given name counts, which separates a namesake ("Dan J. Sullivan") from the incumbent. Answers match by name to the principal candidates, ignoring the poll's party code, because the snapshot's coding (Osborn as `DEM`) differs from the ballot. Output columns keep the House names (`poll_avg_dem_candidate`, `poll_avg_dem_margin_pp`) so analyses carry over, and add `poll_avg_matchup_basis` (`dem_rep` or `reviewed`) to show when the "dem" side is an independent.

Alternatives considered: renaming the columns to `principal_*`, which breaks parity with the House files, and skipping races without a Democrat, which drops the guide's Nebraska wildcard race.

Exclusion reasons follow the House order, with `unknown_race` replacing `missing_seat`/`unknown_district` and `no_principal_matchup` replacing `no_dem_rep_field`. Selection and weights call the House functions and constants directly.

### 5. Context exports and guide join

`build_statewide_race_context.py` writes `2026/statewide/statewide-race-context.csv` (race grain), `statewide-candidate-context.csv`, and `statewide-context-issues.csv`. Column groups follow the House context in the same order: identifiers and counts, presidential 2020 and 2024, Cook PVI, polling, then guide. It recomputes the state history and statewide averages in memory and fails if the saved files differ. `election_guide.py` gains statewide validation behind a `--statewide-field` option, which the context build calls. Guide name check reuses the House surname comparison and adds `other_candidate` with a trailing `(X)` party suffix stripped.

## Risks / Trade-offs

- [The Ballot Brief is AI-assisted and secondary] → keep its URL on every row, report races without a D-versus-R pair, and cross-check against the guide names and 12G filers in the discrepancy report.
- [The state PVI is a secondary transcription of a 2025 edition] → the manifest names the Wikipedia revision and the Cook page it cites, every row carries edition `2025`, and the docs state why no 2026 state edition is used. A later Cook state edition replaces the snapshot and its manifest entry.
- [Governor rows have no incumbency or finance] → `not_federal` status makes the gap explicit, and the docs say no state-finance source is used.
- [Reviewed matchups are judgment calls] → keep them few, evidence-backed, and visible in `poll_avg_matchup_basis`. The build fails if one goes stale.
- [Refactoring House helpers could shift House outputs] → treat a byte-identical House rebuild and the existing tests as a gate on every task that touches House modules.
- [Alaska and Maine use ranked choice, and Georgia and Louisiana can go to runoffs] → first-round shares only, and the docs state that averages do not model final-round or runoff outcomes.

## Migration Plan

Additive. Run the House rebuild first and confirm no diff, then run the statewide sequence: fetch (network), `build_statewide_field.py`, `normalize_district_history.py`, `build_statewide_poll_averages.py`, `build_statewide_race_context.py`. To roll back, delete the new scripts and outputs; House files are untouched.
