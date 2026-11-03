# Spec Delta

## MODIFIED Requirements

### Requirement: Coverage and missing values are visible

Every presidential and PVI metric SHALL have status `available` or `missing` from source coverage and value presence, or, for presidential metrics in redrawn states, `prior_boundaries` with source values kept. Unavailable metrics SHALL remain blank. A deterministic issue report SHALL identify affected district, metric, source, and reason for missing presidential or PVI values and missing or source-only district keys. Unknown values SHALL NOT become zero, EVEN, or a fabricated result.

#### Scenario: Margins with undocumented map vintage
- **WHEN** a district in a state outside the boundary vintage registry has published PVI and valid presidential margins whose source map vintage is undocumented
- **THEN** all three metrics populate by district ID and have available status
- **AND** documentation records the source limitation without withholding the margins

#### Scenario: Margins from retired lines
- **WHEN** a district in a state listed in the boundary vintage registry has valid presidential margins
- **THEN** both margins keep their source values with status `prior_boundaries`, its PVI keeps status `available`, and no issue row is added

#### Scenario: Missing published value
- **WHEN** one district lacks a source PVI value
- **THEN** only its PVI is blank with missing status and an actionable issue row

## ADDED Requirements

### Requirement: Strict mode counts prior-boundary margins as present

Complete-data validation SHALL treat presidential metrics with status `prior_boundaries` as present, so redrawn states do not fail it.

#### Scenario: Strict build with redrawn states
- **WHEN** complete-data validation is requested and every district has both margins and PVI, some with status `prior_boundaries`
- **THEN** the build succeeds

### Requirement: Roster incumbency columns are joined by district

Both exports SHALL append, after all existing columns, the roster's incumbent name, incumbent party, vacancy marker, ballot status, and an open-seat flag, plus a roster source ID. The candidate export SHALL also append a roster incumbent flag that is true only on the candidate row matched to a `running` incumbent. Existing columns SHALL keep their positions and values.

#### Scenario: Incumbent running
- **WHEN** the roster names Mike Lawler as NY-17's `running` incumbent
- **THEN** NY-17's context row has open-seat false, and only Lawler's candidate row has the roster incumbent flag set

#### Scenario: Open seat
- **WHEN** a district's roster status is `not_running`
- **THEN** its context row has open-seat true and none of its candidate rows has the roster incumbent flag set
