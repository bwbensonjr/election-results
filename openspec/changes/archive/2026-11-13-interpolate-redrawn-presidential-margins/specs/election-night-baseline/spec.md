# Spec Delta

## MODIFIED Requirements

### Requirement: Only current-boundary metrics

Race rows SHALL carry the 2024 presidential Democratic-minus-Republican margin only when its boundary status is `available` or `interpolated`, with that status, and SHALL otherwise leave it blank with its status. Race rows SHALL NOT carry 2020 presidential margins. Cook PVI, the polling average and its matchup basis, roster incumbent and open-seat fields, and guide watch fields SHALL be copied unchanged from their sources.

#### Scenario: Redrawn district
- **WHEN** TN-05's presidential metrics have status `prior_boundaries`
- **THEN** TN-05's baseline row has a blank 2024 margin with status `prior_boundaries` and still carries its 2026 PVI

#### Scenario: Redrawn district with an estimate
- **WHEN** UT-01's 2024 margin has status `interpolated`
- **THEN** UT-01's baseline row carries the interpolated margin with status `interpolated` and its 2026 PVI

#### Scenario: Unchanged district
- **WHEN** MA-04's 2024 margin has status `available`
- **THEN** MA-04's baseline row carries that margin unchanged
