# Spec Delta

## MODIFIED Requirements

### Requirement: Boundary status from the vintage registry

Presidential metrics for districts in a state listed in the boundary vintage registry SHALL carry boundary status `interpolated` when the state has a presidential crosswalk, and `prior_boundaries` otherwise; all others SHALL carry `current`. Source values on the old lines SHALL be kept in the normalized source records either way, and interpolated values SHALL be recorded separately with their own source ID.

#### Scenario: State redrawn for 2026
- **WHEN** a district's state is listed in the boundary vintage registry and has no presidential crosswalk
- **THEN** its presidential margins keep their source values and carry boundary status `prior_boundaries`

#### Scenario: Redrawn state with a crosswalk
- **WHEN** Texas is listed in the registry and has a presidential crosswalk
- **THEN** each Texas 2026 district has interpolated 2020 and 2024 margins with boundary status `interpolated`, and the source records for the old Texas districts are unchanged
