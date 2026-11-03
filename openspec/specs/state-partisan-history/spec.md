# state-partisan-history Specification

## Purpose

Provide statewide 2020 and 2024 presidential margins and Cook's latest published state PVI for Senate and governor analysis, with source provenance and explicit unknowns.

## Requirements

### Requirement: State presidential margins from district counts

The importer SHALL compute each state's 2020 and 2024 Democratic votes, Republican votes, and total votes by summing that state's normalized district vote counts. Shares and margins SHALL be recomputed from the summed counts as Democratic-minus-Republican percentage points of all reported votes. District-level rounded shares or margins SHALL NOT be averaged.

#### Scenario: Multi-district state
- **WHEN** a state has three districts with 2024 counts
- **THEN** its 2024 state margin equals (sum of Democratic votes minus sum of Republican votes) divided by the sum of total votes, times 100

#### Scenario: At-large state
- **WHEN** a state has a single `STATE-AL` district
- **THEN** its state counts and margin equal that district's counts and recomputed margin

### Requirement: Complete district coverage per state

A state SHALL receive presidential values for a year only when every district the candidate field lists for that state has valid counts for that year. Otherwise its values for that year SHALL be blank with missing status, and an issue SHALL name the state and the districts lacking counts.

#### Scenario: Missing district counts
- **WHEN** one of a state's districts has no 2020 counts
- **THEN** that state's 2020 values are blank with missing status rather than a partial sum

### Requirement: Published Cook state PVI

The importer SHALL ingest Cook's latest published state PVI, the 2025 edition, from a saved snapshot recorded in the source manifest with its edition, URLs, retrieval date, and checksum. It SHALL keep the label and a signed lean (D positive, R negative, zero only for EVEN). It SHALL NOT estimate state PVI from district PVI.

#### Scenario: Published state label
- **WHEN** the snapshot gives Georgia as `R+1`
- **THEN** the normalized row has label `R+1`, numeric lean `-1`, and edition `2025`

#### Scenario: No 2026 state edition
- **WHEN** Cook's 2026 update re-scores only redistricted House districts and publishes no state list
- **THEN** state PVI comes from the 2025 state edition, which uses the same 2020 and 2024 elections, and its edition is recorded on every row

#### Scenario: State missing from snapshot
- **WHEN** a state with a 2026 statewide race has no published PVI in the snapshot
- **THEN** its PVI is blank with missing status, not computed from its districts or assigned EVEN

### Requirement: Validated state source

The importer SHALL reject a state PVI snapshot whose checksum differs from the manifest, whose labels are malformed, or that has duplicate or unknown states, and SHALL exit nonzero before replacing normalized outputs. District normalization outputs SHALL be unchanged.

#### Scenario: Duplicate state row
- **WHEN** the snapshot lists Texas twice
- **THEN** normalization fails naming both source rows, and previous outputs are preserved

#### Scenario: District outputs unchanged
- **WHEN** state normalization runs on the committed snapshot
- **THEN** the normalized district presidential and PVI files are byte-identical to before
