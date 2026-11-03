# Spec Delta

## Purpose

Publish one pre-election baseline of every 2026 House, Senate, and governor race, keyed so an election-night results feed can join to it, and carrying only context that describes each race as it is contested in 2026.

## ADDED Requirements

### Requirement: One baseline row per race

The race baseline SHALL have exactly one row per House district in the House context and per race in the statewide race context: 506 rows for the current fields. Rows SHALL be sorted by state, then office (House, Senate, Governor), then district.

#### Scenario: Complete race coverage
- **WHEN** the House context has 435 districts and the statewide context has 71 races
- **THEN** the race baseline has 506 rows with unique race keys

### Requirement: Stable race keys and AP join fields

Each race row SHALL carry a race key equal to the existing district ID for House races (`VA-01`, `AK-AL`) and the existing race ID for statewide races (`GA-SEN`, `GA-GOV`). It SHALL also carry AP-style join fields: state postal code, office code `H`, `S`, or `G`, and seat number for House races. An AP race ID column SHALL exist and be blank until a results feed fills it.

#### Scenario: House race keys
- **WHEN** the baseline is built
- **THEN** VA-01 has state `VA`, office code `H`, seat number `1`, and a blank AP race ID

#### Scenario: Statewide race keys
- **WHEN** the baseline is built
- **THEN** GA-SEN has state `GA`, office code `S`, a blank seat number, and a blank AP race ID

### Requirement: Candidate baseline for result joins

A candidate baseline SHALL have one row per candidate in the House and statewide fields, carrying the race key, name, ballot party, FEC ID where resolved, roster incumbent flag, whether the candidate is a principal in the race's polling matchup, and a blank AP candidate ID column.

#### Scenario: Corrected Alaska candidates
- **WHEN** the House field has separate AK-AL rows for Bill Hill and Jim McDermott
- **THEN** the candidate baseline has a row for each under race key `AK-AL`, and Bill Hill is marked as a principal

### Requirement: Only current-boundary metrics

Race rows SHALL carry the 2024 presidential Democratic-minus-Republican margin only when its boundary status is `available`, and SHALL otherwise leave it blank with that status. Race rows SHALL NOT carry 2020 presidential margins. Cook PVI, the polling average and its matchup basis, roster incumbent and open-seat fields, and guide watch fields SHALL be copied unchanged from their sources.

#### Scenario: Redrawn district
- **WHEN** UT-01's presidential metrics have status `prior_boundaries`
- **THEN** UT-01's baseline row has a blank 2024 margin with status `prior_boundaries` and still carries its 2026 PVI

#### Scenario: Unchanged district
- **WHEN** MA-04's 2024 margin has status `available`
- **THEN** MA-04's baseline row carries that margin unchanged

### Requirement: Machine-readable and reproducible output

The baseline SHALL be published as CSV for both grains and as one JSON document containing both, with a schema version, build inputs' source IDs, and no build timestamp. Rebuilding from unchanged inputs SHALL produce byte-identical files. The build SHALL exit nonzero without replacing outputs if any source export is stale or a race key is missing or duplicated.

#### Scenario: Rebuild without changes
- **WHEN** the baseline is rebuilt from unchanged context exports
- **THEN** the CSV and JSON files are byte-identical to the previous build
