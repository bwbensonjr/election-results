# Spec Delta

## MODIFIED Requirements

### Requirement: Analytics fields have explicit semantics

Exports SHALL expose numeric 2020 and 2024 Democratic-minus-Republican margins in percentage points, the published Cook PVI label and signed lean, the district polling average with its nominee names, shares, Democratic-minus-Republican margin, poll and pollster counts, and latest poll end date, and per-metric source/status fields. District metrics SHALL exist once at district grain for district counts and aggregates. Candidate counts SHALL describe ballot rows and preserve unresolved identities in their totals.

#### Scenario: Safe district counting
- **WHEN** a district has several candidates
- **THEN** district-level counts use its single context row rather than repeated candidate-grain metrics
- **AND** the district candidate count includes every ballot row, including unresolved FEC identities

#### Scenario: Polling average joined by district
- **WHEN** the polling averages report an `available` margin for a district
- **THEN** that district's context row and each of its candidate rows carry the same polling columns and values as the averages row

### Requirement: Coverage and missing values are visible

Every presidential and PVI metric SHALL have an available or missing status based on source coverage and value presence. The polling average SHALL carry its own status from the polling build (`available`, `no_polls`, `no_eligible_polls`, or `no_dem_rep_field`). Unavailable metrics SHALL remain blank. A deterministic issue report SHALL identify affected district, metric, source, and reason for missing presidential or PVI values and missing or source-only district keys. Districts without polling SHALL NOT generate issue rows. Unknown values SHALL NOT become zero, EVEN, or a fabricated result.

#### Scenario: Margins with undocumented map vintage
- **WHEN** a district has published PVI and valid presidential margins whose source map vintage is undocumented
- **THEN** all three metrics populate by district ID and have available status
- **AND** documentation records the source limitation without withholding the margins

#### Scenario: Missing published value
- **WHEN** one district lacks a source PVI value
- **THEN** only its PVI is blank with missing status and an actionable issue row

#### Scenario: District without polling
- **WHEN** a district has no eligible nominee polls
- **THEN** its polling columns are blank with the polling build's non-available status
- **AND** no issue row is added for that district's polling

### Requirement: Reproducible and validated publication

The rebuild SHALL run offline from saved inputs and metadata and produce deterministic outputs independent of source row order. Invalid schemas, duplicate source keys, contradictory metadata, or polling averages that are stale for the current poll snapshot and candidate field SHALL exit nonzero before replacing successful exports. A complete-data validation mode SHALL reject missing presidential or PVI target metrics before replacing exports. It SHALL NOT require polling averages.

#### Scenario: Reordered inputs
- **WHEN** unchanged candidate and source rows are shuffled
- **THEN** rebuilding produces the same sorted output records and issue report

#### Scenario: Strict completeness check
- **WHEN** complete-data validation is requested and any target district lacks either presidential margin or published PVI
- **THEN** the command exits nonzero with actionable diagnostics and preserves the previous exports

#### Scenario: Strict build with unpolled districts
- **WHEN** complete-data validation is requested and every district has both margins and PVI, but most districts have no polling average
- **THEN** the build succeeds

#### Scenario: Stale polling averages
- **WHEN** the poll snapshot or candidate field changed after the averages were built
- **THEN** the context build exits nonzero with an instruction to rerun the polling build, and it preserves the previous exports
