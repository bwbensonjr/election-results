# incumbent-roster Specification

## Purpose

Provide one reviewed roster of who currently holds each office on the 2026 ballot, so every race can say who the incumbent is and whether the seat is open, independent of FEC identity matching.

## Requirements

### Requirement: Roster covers every 2026 race

The roster SHALL have exactly one entry per House district in the House field, per Senate race, and per governor race in the statewide field: 506 entries for the current fields. Each entry SHALL hold the race key, office, the incumbent's name and party (`D`, `R`, or `I`), or a vacancy marker, plus evidence, reviewer, and review date.

#### Scenario: Complete coverage
- **WHEN** the House field has 435 districts and the statewide field has 35 Senate and 36 governor races
- **THEN** the roster has 506 entries, one per race key

#### Scenario: Vacant seat
- **WHEN** a House seat has no member on the review date
- **THEN** its entry is marked vacant with blank name and party and carries evidence for the vacancy

### Requirement: House incumbent follows the 2026 district

A House entry SHALL name the sitting member contesting that district in 2026, or the departing member when the seat is open, so a redrawn district names the member running there rather than the 2024 holder of the district with the same number.

#### Scenario: Member running in a renumbered district
- **WHEN** Ami Bera, a sitting member, is on the 2026 CA-03 ballot after California's redraw
- **THEN** CA-03's roster incumbent is Ami Bera, even though the 2024 CA-03 holder was someone else

#### Scenario: Open seat
- **WHEN** the source marks a district open because its member is not seeking it
- **THEN** the entry names that departing member and records a reviewed `not_running` override

### Requirement: Ballot status per incumbent

Each non-vacant entry SHALL record whether the incumbent is a candidate in that race in 2026: `running` when they match exactly one candidate in the race's field by the surname rule refined by first initial, otherwise `not_running`. A reviewed override MAY set the status where name matching cannot decide.

#### Scenario: Incumbent on the ballot
- **WHEN** Jen Kiggans holds VA-02 and the VA-02 field includes Jen A. Kiggans
- **THEN** VA-02's roster status is `running`

#### Scenario: Retiring incumbent
- **WHEN** a district's incumbent matches no candidate in that district's field
- **THEN** the status is `not_running` and the race is an open seat

#### Scenario: Incumbent running for another office
- **WHEN** a House member is a Senate candidate and not a House candidate
- **THEN** their House district's status is `not_running`

### Requirement: Roster validation

The build SHALL exit nonzero without replacing exports when the roster is missing a race key, has a duplicate or unknown race key, an invalid party code, or an entry without evidence, reviewer, or date, or when a reviewed override names a candidate absent from that race's field.

#### Scenario: Missing district
- **WHEN** the roster has no entry for NY-17
- **THEN** the build exits nonzero naming NY-17

### Requirement: Roster does not rewrite candidate identity

Roster matches SHALL NOT change any candidate's FEC ID, match status, or FEC-derived `incumbent` value. Exports SHALL expose roster incumbency in separate columns, so FEC evidence and roster evidence stay distinguishable.

#### Scenario: Unmatched FEC identity
- **WHEN** Mike Lawler's NY-17 row has a blank FEC-derived `incumbent` value and the roster names him as the incumbent
- **THEN** his `incumbent` value stays blank and his roster incumbent column marks him as the incumbent
