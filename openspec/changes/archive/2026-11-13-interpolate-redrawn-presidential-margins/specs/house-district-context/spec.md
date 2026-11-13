# Spec Delta

## MODIFIED Requirements

### Requirement: Coverage and missing values are visible

Every presidential and PVI metric SHALL have status `available` or `missing` from source coverage and value presence, or, for presidential metrics in redrawn states, `interpolated` with values estimated on the 2026 lines and the interpolation source ID where the state has a crosswalk, and `prior_boundaries` with source values kept where it does not. Unavailable metrics SHALL remain blank. A deterministic issue report SHALL identify affected district, metric, source, and reason for missing presidential or PVI values and missing or source-only district keys. Unknown values SHALL NOT become zero, EVEN, or a fabricated result.

#### Scenario: Margins with undocumented map vintage
- **WHEN** a district in a state outside the boundary vintage registry has published PVI and valid presidential margins whose source map vintage is undocumented
- **THEN** all three metrics populate by district ID and have available status
- **AND** documentation records the source limitation without withholding the margins

#### Scenario: Margins from retired lines
- **WHEN** a district in a state listed in the boundary vintage registry and without a crosswalk has valid presidential margins
- **THEN** both margins keep their source values with status `prior_boundaries`, its PVI keeps status `available`, and no issue row is added

#### Scenario: Margins estimated on new lines
- **WHEN** a district in a registry state with a crosswalk has interpolated margins
- **THEN** both margins carry the interpolated values with status `interpolated` and the interpolation source ID, its PVI keeps status `available`, and no issue row is added

#### Scenario: Missing published value
- **WHEN** one district lacks a source PVI value
- **THEN** only its PVI is blank with missing status and an actionable issue row

### Requirement: Strict mode counts prior-boundary margins as present

Complete-data validation SHALL treat presidential metrics with status `prior_boundaries` or `interpolated` as present, so redrawn states do not fail it.

#### Scenario: Strict build with redrawn states
- **WHEN** complete-data validation is requested and every district has both margins and PVI, some with status `prior_boundaries` and some with status `interpolated`
- **THEN** the build succeeds
