# statewide-race-context Specification

## Purpose

Expose race-grain and candidate-grain datasets that join statewide partisan history, polling averages, and the election-night guide to the 2026 Senate and governor field without hiding missing evidence.

## Requirements

### Requirement: One context row per statewide race

The race export SHALL contain exactly one row per race ID in the statewide field, carrying state, office, race ID, candidate counts, and the state's history metrics joined by state. A Senate and a governor race in the same state SHALL carry the same state metrics.

#### Scenario: State with both races
- **WHEN** Georgia has a Senate and a governor race
- **THEN** the race export has `GA-SEN` and `GA-GOV` rows with identical presidential margins and PVI

### Requirement: Candidate export preserves grain and identity

The candidate export SHALL preserve every statewide field row with its existing columns and values, appending its race's context through a many-to-one join on race ID. FEC match status, blank unresolved values, and `not_federal` governor values SHALL be preserved.

#### Scenario: Several candidates in one race
- **WHEN** a race has four candidate rows
- **THEN** the candidate export has four rows carrying that race's context values

### Requirement: Statewide analytics columns

Both exports SHALL expose numeric 2020 and 2024 state Democratic-minus-Republican margins, the published Cook state PVI label and signed lean, per-metric status and source fields, the polling average columns copied unchanged from the statewide averages, and the guide columns. New columns SHALL appear in a fixed, documented order.

#### Scenario: Polling values copied
- **WHEN** the statewide averages report an `available` margin for `TX-SEN`
- **THEN** the `TX-SEN` race row and each of its candidate rows carry the same polling columns and values

### Requirement: Guide rows joined by state and office

Both exports SHALL append the guide races CSV's Senate and Governor columns with a `guide_` prefix, a `guide_name_check`, `guide_status`, and guide source ID, joined by state and office. Races the guide does not name SHALL have status `not_in_guide` and blank guide values.

#### Scenario: Guide race
- **WHEN** the guide has a Kansas Senate row
- **THEN** `KS-SEN` carries its guide values with `guide_status` set to `in_guide`

#### Scenario: Race outside the guide
- **WHEN** the guide does not name the Colorado governor race
- **THEN** `CO-GOV` has blank guide columns and status `not_in_guide`

### Requirement: Guide names checked against the statewide field

Each guide race SHALL carry a `guide_name_check` comparing the guide's Democratic, Republican, and other candidate names with that race's field candidates, using the surname rule and ignoring a parenthesized party suffix. The check SHALL be `matched`, `mismatch`, or `not_named`. A mismatch SHALL NOT change field or guide values.

#### Scenario: Independent named in the other column
- **WHEN** the guide's Nebraska Senate row has Ricketts as Republican and `Osborn (I)` as other, and both are in the field
- **THEN** `NE-SEN`'s check is `matched`

#### Scenario: Guide name not in the field
- **WHEN** a guide name matches no candidate in that race's field
- **THEN** the check is `mismatch` and values are unchanged

### Requirement: Visible statewide gaps

Missing presidential or PVI values SHALL be blank with missing status and produce a deterministic issue row naming race, metric, source, and reason. Unknown values SHALL NOT become zero or EVEN. Polling and guide gaps SHALL use their own statuses and SHALL NOT produce issue rows.

#### Scenario: Missing state PVI
- **WHEN** a state has no published PVI
- **THEN** each of its races has blank PVI with missing status and one issue row per race

### Requirement: Reproducible and gated statewide publication

The context build SHALL run offline, produce identical sorted output for reordered inputs, and exit nonzero without replacing exports when inputs are invalid, the statewide averages or state history are stale, or guide validation fails. A complete-data mode SHALL require both margins and PVI for every race but SHALL NOT require polling or guide coverage.

#### Scenario: Stale statewide averages
- **WHEN** the poll snapshot changed after the statewide averages were built
- **THEN** the build exits nonzero with an instruction to rerun the polling build and preserves previous exports

#### Scenario: Strict build with unpolled races
- **WHEN** complete-data mode runs, every race has both margins and PVI, and some races have no polling
- **THEN** the build succeeds

### Requirement: Roster incumbency columns are joined by race

Both statewide exports SHALL append, after all existing columns, the roster's incumbent name, incumbent party, vacancy marker, ballot status, an open-seat flag, and a roster source ID, joined by race ID. The candidate export SHALL also append a roster incumbent flag that is true only on the candidate row matched to a `running` incumbent. Governor rows SHALL get roster incumbency even though they have no FEC incumbency.

#### Scenario: Governor running for reelection
- **WHEN** the roster names a governor as the `running` incumbent of a governor race
- **THEN** that race row has open-seat false and that governor's candidate row has the roster incumbent flag set, while its FEC fields stay `not_federal`

#### Scenario: Open Senate seat
- **WHEN** a Senate race's roster status is `not_running`
- **THEN** its race row has open-seat true and no candidate row has the roster incumbent flag set

#### Scenario: Existing columns unchanged
- **WHEN** the roster columns are added
- **THEN** every earlier column keeps its position and values, and the row counts are unchanged
