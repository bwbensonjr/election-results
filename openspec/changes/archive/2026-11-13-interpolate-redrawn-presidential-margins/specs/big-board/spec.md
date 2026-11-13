# Spec Delta

## MODIFIED Requirements

### Requirement: Color metrics

The map SHALL be colored by one selectable metric: election-night results, polling average margin, 2024 Harris/Trump margin (labeled President), Cook PVI lean, or incumbent party. Democratic values SHALL use blue shades, Republican values red shades, scaled by margin, and missing or unknown values grey. Under the President metric, margins with status `available` or `interpolated` SHALL be colored the same way.

#### Scenario: Margin unavailable
- **WHEN** the metric is 2024 margin and a district's margin status is `prior_boundaries`
- **THEN** the district is grey and its detail says the margin describes prior lines

#### Scenario: Interpolated margin
- **WHEN** the metric is 2024 margin and a Texas district drawn on its 2026 shape has an interpolated margin of Trump +24
- **THEN** the district is drawn in the strongest red step, like a district with an available margin of the same size

#### Scenario: PVI metric
- **WHEN** the metric is PVI and a race's Cook PVI is R+12
- **THEN** the race is drawn in the strongest red step, with PVI steps set at half the margin steps since PVI is about half a two-party margin

#### Scenario: Results metric before votes
- **WHEN** the metric is results and a race has no votes
- **THEN** the race is grey

### Requirement: Race detail

The detail view for a selected race SHALL show the incumbent and whether the seat is open, the winner if called, each candidate's votes and vote share, percent of expected vote and precincts reporting, the 2024 Harris/Trump margin with its boundary status, Cook PVI, and the polling average where available. An interpolated 2024 margin SHALL be labeled as an estimate on the 2026 lines.

#### Scenario: Open seat with results
- **WHEN** the viewer selects an open-seat race with partial results
- **THEN** the detail shows the departing incumbent, the open-seat flag, candidates with votes and percentages, and reporting levels

#### Scenario: Interpolated margin in detail
- **WHEN** the viewer selects a North Carolina district whose 2024 margin is interpolated
- **THEN** the detail shows the margin with a note that it is estimated from 2024 results reallocated to the 2026 lines
