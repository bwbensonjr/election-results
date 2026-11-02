# house-district-context Specification

## Purpose

Expose district and candidate datasets that join source partisan history to the 2026 House field without hiding missing evidence or changing candidate identity decisions.

## Requirements

### Requirement: One context row per target district

The context export SHALL contain exactly one row for each distinct district in the 2026 candidate field. It SHALL join unique normalized metrics by state and district without boundary approval checks. Source-only districts SHALL be reported rather than silently added to the target universe or used to drop existing districts.

#### Scenario: Current district coverage
- **WHEN** the committed candidate field has 435 distinct districts
- **THEN** the context export has 435 uniquely keyed rows even if some metrics are missing
- **AND** an extra historical district produces a source-only coverage issue

### Requirement: Candidate enrichment preserves grain and identity

The candidate export SHALL preserve every input candidate row and its existing columns and values, appending district context through a many-to-one district join. It SHALL preserve unresolved FEC matches, incumbency, filing flags, finance, and poll-presence values. Historical incumbent names SHALL NOT identify candidates or overwrite candidate records.

#### Scenario: Several candidates share a district
- **WHEN** a district has three candidate rows and one context row
- **THEN** the enriched export still has three candidate rows carrying the same district metrics
- **AND** an unresolved FEC ID remains blank with its existing match status

#### Scenario: Historical incumbent differs
- **WHEN** the results source names an incumbent who differs from the current candidate field
- **THEN** that label remains source metadata and does not replace the candidate-level incumbent flag or assert a current incumbent roster

### Requirement: Analytics fields have explicit semantics

Exports SHALL expose numeric 2020 and 2024 Democratic-minus-Republican margins in percentage points, the published Cook PVI label and signed lean, and per-metric source/status fields. District metrics SHALL exist once at district grain for district counts and aggregates. Candidate counts SHALL describe ballot rows and preserve unresolved identities in their totals.

#### Scenario: Safe district counting
- **WHEN** a district has several candidates
- **THEN** district-level counts use its single context row rather than repeated candidate-grain metrics
- **AND** the district candidate count includes every ballot row, including unresolved FEC identities

### Requirement: Polling average columns are joined by district

Both exports SHALL append the district polling average after all other columns: its nominee names, shares, Democratic-minus-Republican margin, poll and pollster counts, latest poll end date, status, and source ID. Values SHALL be copied unchanged from the polling averages by district, once per district row and repeated on each of that district's candidate rows.

#### Scenario: Polling average joined by district
- **WHEN** the polling averages report an `available` margin for a district
- **THEN** that district's context row and each of its candidate rows carry the same polling columns and values as the averages row

### Requirement: Coverage and missing values are visible

Every presidential and PVI metric SHALL have an available or missing status based on source coverage and value presence. Unavailable metrics SHALL remain blank. A deterministic issue report SHALL identify affected district, metric, source, and reason for missing presidential or PVI values and missing or source-only district keys. Unknown values SHALL NOT become zero, EVEN, or a fabricated result.

#### Scenario: Margins with undocumented map vintage
- **WHEN** a district has published PVI and valid presidential margins whose source map vintage is undocumented
- **THEN** all three metrics populate by district ID and have available status
- **AND** documentation records the source limitation without withholding the margins

#### Scenario: Missing published value
- **WHEN** one district lacks a source PVI value
- **THEN** only its PVI is blank with missing status and an actionable issue row

### Requirement: Polling gaps are explicit without issue rows

The polling average SHALL carry its own status from the polling build: `available`, `no_polls`, `no_eligible_polls`, or `no_dem_rep_field`. Polling values SHALL be blank unless the status is `available`, never zero. Districts without polling SHALL NOT generate issue report rows.

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

### Requirement: Election guide columns are joined by district

Both exports SHALL append, after all existing columns, the guide races CSV's House columns with a `guide_` prefix, the guide name check, `guide_status`, and a guide source ID. Guide values SHALL be copied unchanged from the House rows by district: once per district row, and repeated on each of that district's candidate rows. Districts the guide does not name SHALL have status `not_in_guide` and blank guide values.

#### Scenario: Guide district
- **WHEN** the guide races CSV has a KY-06 House row
- **THEN** the KY-06 context row and each KY-06 candidate row carry its guide values with `guide_status` set to `in_guide`

#### Scenario: District outside the guide
- **WHEN** the guide does not name CA-13
- **THEN** CA-13's guide columns are blank and its `guide_status` is `not_in_guide`

#### Scenario: Existing columns unchanged
- **WHEN** the guide columns are added
- **THEN** every earlier column keeps its position and values, and the row counts are unchanged

### Requirement: Guide names are checked against the candidate field

Each guide district SHALL carry a `guide_name_check` comparing the guide's Democratic and Republican candidate names with the field's candidates of those parties. The comparison SHALL use the surname rule that `in_general_polls` uses. The check SHALL be `matched` when every guide name matches, `mismatch` when any does not, and `not_named` when the guide names neither. A mismatch SHALL NOT change candidate or guide values.

#### Scenario: Guide names both nominees
- **WHEN** the guide gives Dembo as the Democratic and Alvarado as the Republican candidate for KY-06, and the field has Zach Dembo (DEM) and Ralph Alvarado (REP)
- **THEN** KY-06's `guide_name_check` is `matched`

#### Scenario: Guide name not in the field
- **WHEN** a guide Democratic name matches no Democratic candidate in that district's field
- **THEN** the check is `mismatch`, and the guide and candidate values stay as they were

### Requirement: Guide validation gates publication but not completeness

The context build SHALL validate the guide races CSV against its markdown source and the candidate field before it replaces any export, and SHALL exit nonzero on a validation failure while preserving previous exports. Complete-data validation SHALL NOT require districts to appear in the guide, and districts without guide coverage SHALL NOT add issue rows.

#### Scenario: Guide out of step with markdown
- **WHEN** the markdown names a district that the guide CSV has no House row for
- **THEN** the context build exits nonzero with that district named, and previous exports are unchanged

#### Scenario: Strict build with partial guide coverage
- **WHEN** `--require-complete` runs, every district has both presidential margins and PVI, and only 44 districts are in the guide
- **THEN** the build succeeds and the issues report has no guide rows
