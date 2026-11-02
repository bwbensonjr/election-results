# Spec Delta

## Purpose

Provide presidential source margins and published Cook PVI for House district analysis while retaining source evidence and documented source limitations.

## ADDED Requirements

### Requirement: Canonical district identifiers

The importer SHALL normalize district labels to a two-letter state, two-digit district, and stable district ID. At-large labels SHALL map to district `00` and ID `STATE-AL`; numbered IDs SHALL use `STATE-NN`. It SHALL reject malformed labels and duplicate normalized keys within a source edition rather than select an arbitrary row.

#### Scenario: At-large and numbered records
- **WHEN** a source contains `AK-AL` and `AL-01`
- **THEN** normalized keys are `(AK, 00)` and `(AL, 01)` with IDs `AK-AL` and `AL-01`
- **AND** numbered district 1 is not silently treated as an at-large seat

#### Scenario: Duplicate after normalization
- **WHEN** two rows in one source edition normalize to the same state and district
- **THEN** ingestion fails with both source row references and does not replace successful normalized outputs

### Requirement: Presidential result normalization

The importer SHALL read the supplied two-row CSV header without losing repeated year-specific columns. It SHALL retain source vote counts, shares, margins, incumbent labels, and party labels with their election year. Margins SHALL be signed Democratic-minus-Republican percentage points using all reported votes as denominator. Published source values SHALL retain their precision.

#### Scenario: Two-row source header
- **WHEN** the supplied file has separate 2024 and 2020 column groups, repeated Trump and Margin headings, and an empty separator column
- **THEN** Harris/Trump 2024 and Biden/Trump 2020 values remain distinct and the second header row is not counted as a district

#### Scenario: Margin direction and rounding
- **WHEN** the source has 2024 margin `-13.14%` for Alaska
- **THEN** its normalized source margin is numeric `-13.14` percentage points
- **AND** validation compares it to the vote-count-derived margin with a documented rounding tolerance rather than subtracting already rounded shares

### Requirement: Published Cook PVI

The importer SHALL ingest Cook's published 2026 PVI from a saved snapshot of the selected district page or its user-accessible export. It SHALL retain the published label and expose a signed numeric lean: positive for D, negative for R, and zero only for published EVEN. It SHALL NOT estimate PVI, substitute an older edition, or interpolate districts.

#### Scenario: Published labels
- **WHEN** source labels are `D+4`, `R+3`, and `EVEN`
- **THEN** normalized labels remain those values and numeric lean values are `4`, `-3`, and `0`
- **AND** numeric lean describes published PVI rather than a presidential vote margin

#### Scenario: Missing or inaccessible source
- **WHEN** the Cook snapshot or a district's published PVI is unavailable
- **THEN** the absence is reported and its PVI remains blank rather than calculated, assigned EVEN, or filled from a 2025 publication

### Requirement: Source provenance without boundary gating

Each normalized metric SHALL identify its source snapshot, edition, election year where applicable, and retrieval date when known. Valid values SHALL join by normalized district ID without per-district boundary approvals. Documentation SHALL state that source editions may describe different maps and that the pipeline does not interpolate them.

#### Scenario: Unknown source vintage
- **WHEN** the supplied CSV has no independently verified boundary vintage
- **THEN** its valid margins still populate district context
- **AND** source metadata records that limitation without treating the margin as missing

#### Scenario: Cook table has two PVI editions
- **WHEN** the saved table includes both 2025 PVI and 2026 PVI
- **THEN** the published PVI output uses 2026 PVI and retains the table edition and source reference

### Requirement: Validated values and explicit unknowns

The importer SHALL validate counts, percentages, margins, and PVI labels, reject malformed or impossible values, and distinguish blank values from numeric zero. It SHALL report missing districts and fields. Source values that disagree beyond the documented rounding tolerance SHALL fail validation before replacing normalized outputs.

#### Scenario: Invalid source value
- **WHEN** a row has a negative vote count, a nonpositive total, a share outside 0 to 100, or an unrecognized PVI label
- **THEN** validation fails with the source row and field identified

#### Scenario: Missing metric and true zero
- **WHEN** one district has a missing margin and another has a published margin of `0.00%`
- **THEN** the former remains blank and is reported, while the latter remains numeric zero
