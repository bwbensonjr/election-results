# Design

## Context

The House pipeline runs `build_house_field.py` (Ballot Brief rows plus FEC matching), then `build_house_poll_averages.py`, then `build_house_district_context.py`, which reads the presidential and Cook sources through `district_history.py`. The statewide pipeline mirrors it with `build_statewide_field.py`, `build_statewide_poll_averages.py`, and `build_statewide_race_context.py`. Every build runs offline from committed inputs, writes sorted output, and refuses to replace exports when inputs are invalid or stale. Reviewed judgments already live in committed JSON registries with evidence, reviewer, and date (`candidate-identity-decisions.json`, `polls/statewide-principal-matchups.json`).

Facts found while scoping this change (November 2, 2026 snapshot):

- The FEC-derived `incumbent` value is blank for 325 House candidate rows (299 unmatched, 26 ambiguous), leaving 152 districts with no flagged incumbent. Governors are `not_federal`, so all 36 governor races lack incumbency.
- `cook-pvi-2026-source.csv` already records an incumbent and party for every district, captured November 2, 2026. The presidential source also has an incumbent label of unknown date.
- Comparing 2026 PVI with the presidential margins finds districts off by more than four points in CA, TX, FL, LA, TN, UT, AL, NC, and OH, consistent with mid-decade redistricting.
- The Ballot Brief AK-AL page lists "Bill Hill, James C. "Jim" McDermott" as one Libertarian row. Polls show Hill as an independent near 40% and McDermott near 5%.
- Statewide `context-issues` files are empty because there are no coverage gaps; that is correct behavior, not a defect.

## Goals / Non-Goals

**Goals:**
- Every race reaches election night with a correct incumbent, open-seat flag, principal matchup, and only current-boundary partisan context.
- Fixes stay reviewable: every judgment is a committed registry entry with evidence, and builds fail loudly when an entry goes stale.
- Existing exports stay backward compatible: new columns are appended, no column is removed, renamed, or reordered.

**Non-Goals:**
- Fetching AP data, mapping AP race or candidate IDs, or ingesting results.
- Acquiring presidential results on the 2026 lines.
- Changing FEC identity matching or the poll weighting method.

## Decisions

### Registries follow the existing reviewed-JSON pattern

Add four committed JSON files, each with `schema_version` and entries carrying `evidence` (list of URLs or file references), `reviewed_by`, and `reviewed_at`, like `statewide-principal-matchups.json`:

- `2026/results/boundary-vintage.json`: redrawn states and the plan in effect.
- `2026/roster/incumbent-roster.json`: 506 entries keyed by race key.
- `2026/candidates/house-ballot-corrections.json`: row replacements.
- `2026/polls/house-principal-matchups.json`: House principal entries.

Alternative considered: CSV registries. Rejected because evidence is a list and the project already validates JSON registries the same way.

### Boundary status is a separate field, not a new missing state

District history gains a per-district `pres_boundary_status` (`current` or `prior_boundaries`). The context build maps it into the existing `pres_2020_status` and `pres_2024_status` columns as `prior_boundaries` while keeping the values. No new columns are needed in the district exports.

Alternative considered: blanking the margins. Rejected because the user still wants the old-line values available for reference, and blanking would make complete-data validation fail for nine states.

The registry is seeded from the PVI consistency check, then each state is confirmed with an evidence URL for its enacted 2026 plan. The check stays in the build as a non-failing report (`2026/results/boundary-review.csv`) so a missed state is visible. The threshold is four points between PVI and a PVI-like value implied by the 2020 and 2024 margins against the national results, documented in `docs/district-data.md`.

### Roster seeded from saved sources, then reviewed

House entries are generated from the Cook 2026 table's incumbent columns, the most recent saved source, and compared with the presidential source's labels. Cook names the sitting member contesting each 2026 district, or `OPEN (Name)` for the departing member, which is the useful meaning of incumbent in redrawn states; the roster adopts that convention and gives Cook's open seats a reviewed `not_running` override. Disagreements and vacancies are listed in a review report and resolved by hand with evidence. Senate and governor entries are seeded from saved snapshots of the U.S. Senate member list and the National Governors Association list, captured to `2026/roster/sources/` with retrieval date and URL in the source manifest, then reviewed.

A small `scripts/build_incumbent_roster.py` writes the seeded roster and review report. After review, the committed JSON is the source of truth and the context builds only read and validate it.

Ballot status is computed at context-build time, not stored, by matching the incumbent name to the race's field with the same surname rule refined by first initial used elsewhere. A reviewed `ballot_status_override` handles name forms the rule cannot match (for example, a nickname that differs from the ballot name).

Alternative considered: deriving incumbency from FEC alone after more identity review. Rejected because governors are not federal candidates and 325 House rows remain unresolved; the roster answers a simpler question with better sources.

### House principal matchups reuse the statewide rule

`build_house_poll_averages.py` reads `house-principal-matchups.json`. A reviewed entry replaces the default single-D/single-R nominee pair for that district, and party-code checking is skipped for the reviewed principals, as the statewide build already does. Existing columns `poll_avg_dem_candidate` and `poll_avg_dem_pct` keep their names and hold the non-Republican principal; a new appended `poll_avg_matchup_basis` column says `dem_rep` or `reviewed`, the values the statewide average already uses. Documentation states the column semantics.

Alternative considered: renaming the columns to `principal_*`. Rejected as a breaking change for no gain before tomorrow.

### Ballot corrections applied before matching

`build_house_field.py` applies corrections immediately after reading the Ballot Brief CSV, before district grouping, FEC matching, and poll presence. Replacement rows get `source_correction` = the correction ID; uncorrected rows leave it blank. The column is appended to the House field and carried through to the context exports.

### Baseline export is a separate final step

`scripts/build_election_baseline.py` reads only the finished House and statewide context exports and the roster, never raw sources, and writes:

- `2026/baseline/race-baseline.csv`: one row per race.
- `2026/baseline/candidate-baseline.csv`: one row per candidate.
- `2026/baseline/election-baseline.json`: both grains plus `schema_version` and input source IDs.

Race keys reuse existing IDs (`VA-01`, `AK-AL`, `GA-SEN`), so no lookup table is needed. AP join fields are `state_postal`, `ap_office_id` (`H`, `S`, `G`), `ap_seat_num` (district number as an integer string; `1` for at-large districts, to be confirmed against AP data tomorrow), and blank `ap_race_id` and `ap_candidate_id` columns for the feed change to fill. Staleness is checked by recording the SHA-256 of each input export in the JSON and comparing input modification order, as the other builds do.

### Build order

`build_house_field` → `build_house_poll_averages` → `build_statewide_poll_averages` → `build_house_district_context` → `build_statewide_race_context` → `build_election_baseline`. The roster build runs only when reseeding.

## Risks / Trade-offs

- [Roster review takes longer than the time before polls close] → Seed from Cook (captured today) so most House entries need no edits; review the report's disagreements, vacancies, and all 71 statewide entries first; the build can run with entries marked `reviewed_by` as the seed source until a person confirms them, and the docs list how many entries are unconfirmed.
- [The PVI check misses a redrawn state whose new lines happen to resemble the old ones] → Confirm the registry against a published list of 2025–2026 mid-decade redistricting, not only the check.
- [AP numbers at-large seats differently than assumed] → `ap_seat_num` is only a join aid; the feed change confirms and adjusts it without touching race keys.
- [Reusing `poll_avg_dem_*` names for an independent principal confuses readers] → The basis column and docs make the meaning explicit, and the baseline exposes the principal's party.

## Migration Plan

Rebuild all exports in the build order above and commit inputs and outputs together. Rollback is reverting the commit; no external system depends on these files yet.

## Open Questions

- AP's seat numbering for at-large districts and its office ID for the Ohio and Florida special Senate elections. Settle when the AP feed is tested; neither affects race keys.
