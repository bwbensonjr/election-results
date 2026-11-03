# Proposal

## Why

The election-night tracker will show and update every 2026 House, Senate, and governor race from an AP results feed starting November 3, but the race context it starts from has known errors: presidential margins on retired district lines in redrawn states, incumbency missing for a third of House districts and every governor race, a merged Alaska candidate row that hides the main challenger, and no race key an AP feed can join to. These need fixing before the feed is wired up, because the tracker cannot correct them on the night.

## What Changes

- Record which states use different congressional lines in 2026 than the presidential results source, in a reviewed registry with evidence. Presidential margins for districts in those states get a new `prior_boundaries` status instead of `available`. The values stay in the existing exports for reference but are no longer treated as describing the current district.
- Add a reviewed incumbent roster for all 435 House seats, all 35 Senate seats up in 2026, and all 36 governorships, recording the officeholder, party, and whether they are on the 2026 ballot. Race exports gain incumbent and open-seat columns derived from it. Existing FEC-derived candidate `incumbent` values are unchanged.
- Add reviewed corrections for House ballot-source rows that combine several candidates. Alaska's single "Bill Hill, James C. McDermott" Libertarian row becomes independent Bill Hill and Libertarian Jim McDermott.
- Let the House polling average use a reviewed principal matchup, as the statewide average already does. AK-AL's average becomes independent Bill Hill against Nick Begich instead of Democrat Eric Hafner (about 6%) against Begich.
- Add an election-night baseline export with one row per race (435 House, 71 statewide), each with a stable race key, AP-style state, office, and seat fields, candidates, incumbency, open-seat flag, 2024 presidential margin only where it is on current lines, Cook PVI, polling average, and guide fields. 2020 presidential margins are not carried into it.

## Capabilities

### New Capabilities
- `congressional-boundary-vintage`: the reviewed registry of states whose 2026 congressional lines differ from the presidential results source, and the boundary status it gives district presidential metrics.
- `incumbent-roster`: the reviewed roster of current House members, senators in seats up in 2026, and governors, with ballot status, and how race and candidate exports use it.
- `house-ballot-corrections`: reviewed corrections to House ballot-source candidate rows applied when the House field is built.
- `election-night-baseline`: the all-races export, its race keys and AP join fields, and which metrics it carries.

### Modified Capabilities
- `district-partisan-history`: source provenance requirement changes so district presidential metrics carry a boundary status from the vintage registry instead of always joining without boundary checks.
- `house-district-context`: presidential metric status gains `prior_boundaries`; complete-data validation treats it as present but not current; both exports append roster incumbent and open-seat columns.
- `house-poll-average`: nominee head-to-head matching accepts a reviewed principal matchup for a district, with matchup basis recorded in the output.
- `statewide-race-context`: both exports append roster incumbent and open-seat columns.

## Impact

- Scripts: `scripts/build_house_field.py` (ballot corrections), `scripts/district_history.py` and `scripts/build_house_district_context.py` (boundary status, roster columns), `scripts/build_house_poll_averages.py` (principal matchups), `scripts/build_statewide_race_context.py` (roster columns), and a new baseline export script.
- New reviewed inputs under `2026/`: boundary vintage registry, incumbent roster, House ballot corrections, House principal matchups.
- Rebuilt outputs: House field, House poll averages and input log, district and candidate context, statewide race and candidate context, plus the new baseline file. Column additions are appended after existing columns; no existing column is removed or reordered.
- Docs: `README.md`, `docs/district-data.md`, `docs/statewide-data.md`, `docs/candidate-pipeline.md`.
- Out of scope: the AP feed itself, race calls, results ingestion, and the tracker artifact, which follow in later changes. 2024 presidential results on the new lines are not acquired here.
