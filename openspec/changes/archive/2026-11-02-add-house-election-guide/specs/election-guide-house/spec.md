# Spec Delta

## Purpose

Keep the House portion of the election-night guide as a validated, district-grain CSV that stays consistent with its markdown source, so the guide's watch list and signals can join to district data.

## ADDED Requirements

### Requirement: One guide row per named House district

The guide CSV SHALL contain exactly one row for each House district the guide markdown names. A district named in several places SHALL have its information combined into that one row. District IDs SHALL use the repository's canonical form (for example `VA-01`, `AK-AL`) and SHALL be unique.

#### Scenario: District named in several sections
- **WHEN** the guide names VA-1 in the seat ladder table and again in the 7:00 ET Virginia ladder
- **THEN** the CSV has a single `VA-01` row that carries both its ladder tier and its 7:00 ET signals

#### Scenario: Duplicate district row
- **WHEN** the CSV contains two rows that normalize to the same district ID
- **THEN** validation fails and names the duplicate district

### Requirement: Guide coverage matches the markdown source

Validation SHALL compare the CSV's district IDs with every House district reference (`XX-n`) in the guide markdown, after normalization. Any district present in only one of the two SHALL fail validation, and the error SHALL name it.

#### Scenario: Guide edit adds a district
- **WHEN** the guide markdown gains a mention of `MI-07` and the CSV has no `MI-07` row
- **THEN** validation fails with `MI-07` reported as missing from the CSV

#### Scenario: Stray CSV row
- **WHEN** the CSV has a `TX-34` row that the markdown never mentions
- **THEN** validation fails with `TX-34` reported as absent from the guide

### Requirement: Controlled guide fields

The guide CSV SHALL have a fixed column set. Watch time SHALL be one of the guide's Eastern-time headings. Role SHALL come from a documented vocabulary. Democratic-win tier SHALL be blank or one of the guide's four seat-ladder tiers. Free-text fields SHALL hold the guide's own wording without inferred facts, and fields the guide does not address SHALL be blank.

#### Scenario: Unknown role value
- **WHEN** a row's role is `swing` and the vocabulary does not include it
- **THEN** validation fails and names the row and field

#### Scenario: District without a tier
- **WHEN** the guide never places a district on the seat ladder
- **THEN** its Democratic-win tier is blank rather than guessed

### Requirement: Every guide district exists in the candidate field

Each guide district ID SHALL match a district in the 2026 candidate field. A guide district that is absent from the field SHALL fail validation, not be silently dropped.

#### Scenario: Unknown district
- **WHEN** a guide row names `PA-18` and the field has no such district
- **THEN** validation fails and names `PA-18`
