# Spec Delta

## MODIFIED Requirements

### Requirement: Source provenance without boundary gating

Each normalized metric SHALL identify its source snapshot, edition, election year where applicable, and retrieval date when known. Valid values SHALL join by normalized district ID without per-district boundary approvals. Documentation SHALL state that source editions may describe different maps and that the pipeline does not interpolate them.

#### Scenario: Unknown source vintage
- **WHEN** the supplied CSV has no independently verified boundary vintage and the district's state is not in the boundary vintage registry
- **THEN** its valid margins still populate district context with boundary status `current`
- **AND** source metadata records that limitation without treating the margin as missing

#### Scenario: Cook table has two PVI editions
- **WHEN** the saved table includes both 2025 PVI and 2026 PVI
- **THEN** the published PVI output uses 2026 PVI and retains the table edition and source reference

## ADDED Requirements

### Requirement: Boundary status from the vintage registry

Presidential metrics for districts in a state listed in the boundary vintage registry SHALL carry boundary status `prior_boundaries`; all others SHALL carry `current`. Source values SHALL be kept either way.

#### Scenario: State redrawn for 2026
- **WHEN** a district's state is listed in the boundary vintage registry
- **THEN** its presidential margins keep their source values and carry boundary status `prior_boundaries`
