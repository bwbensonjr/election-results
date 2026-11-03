# election-guide-house Specification

## Purpose

Keep the election-night guide's races as a validated CSV that stays consistent with its markdown source, so the guide's House races and signals can join to district data.

## Requirements

### Requirement: One guide row per named race

The races CSV SHALL contain one row per race the guide covers, with an office of `House`, `Senate`, or `Governor`. House rows SHALL carry a canonical two-digit district (`00` at large), and other offices SHALL leave the district blank. Each House district SHALL appear at most once.

#### Scenario: Duplicate House district
- **WHEN** the CSV contains two House rows for KY-06
- **THEN** validation fails and names the duplicate district

#### Scenario: District on a Senate row
- **WHEN** a Senate row has a district value
- **THEN** validation fails and names the row

### Requirement: Guide coverage matches the markdown source

Validation SHALL compare the CSV's House districts with every House district reference (`XX-n`) in the guide markdown, after normalization. Any district present in only one of the two SHALL fail validation, and the error SHALL name it. Senate and governor rows are not compared with the markdown.

#### Scenario: Guide edit adds a district
- **WHEN** the guide markdown gains a mention of `MI-07` and the CSV has no `MI-07` House row
- **THEN** validation fails with `MI-07` reported as missing from the CSV

#### Scenario: Stray CSV row
- **WHEN** the CSV has a `TX-34` House row that the markdown never mentions
- **THEN** validation fails with `TX-34` reported as absent from the guide

### Requirement: Controlled guide fields

The races CSV SHALL have a fixed column set. The watch slot SHALL be one of the guide's slots, and the poll close SHALL be a 24-hour Eastern time. Ladder tier SHALL be blank or one of the guide's four seat-ladder tiers. Incumbent party, open seat, and the two margin columns SHALL be blank or a documented value. Fields the guide does not address SHALL be blank.

#### Scenario: Unknown ladder tier
- **WHEN** a row's ladder tier is `Wave`
- **THEN** validation fails and names the row and field

#### Scenario: Race without a tier
- **WHEN** the guide never places a race on the seat ladder
- **THEN** its ladder tier is blank rather than guessed

### Requirement: Every guide House district exists in the candidate field

Each House row's district SHALL match a district in the 2026 candidate field. A guide district that is absent from the field SHALL fail validation, not be silently dropped.

#### Scenario: Unknown district
- **WHEN** a House row names `PA-18` and the field has no such district
- **THEN** validation fails and names `PA-18`

### Requirement: One guide row per statewide race

Each state SHALL appear at most once among Senate rows and at most once among Governor rows of the races CSV. A duplicate SHALL fail validation and name the state and office.

#### Scenario: Duplicate Senate row
- **WHEN** the CSV contains two Senate rows for Georgia
- **THEN** validation fails naming Georgia and Senate

### Requirement: Every guide statewide race exists in the statewide field

Each Senate and Governor row SHALL name a state whose race of that office exists in the 2026 statewide candidate field. A row without a matching race SHALL fail validation rather than be dropped. House validation SHALL be unchanged.

#### Scenario: Unknown governor race
- **WHEN** the CSV has a Governor row for Kentucky and the statewide field has no `KY-GOV` race
- **THEN** validation fails and names Kentucky and Governor

#### Scenario: Committed guide rows
- **WHEN** validation runs on the committed 14 Senate and 4 Governor rows
- **THEN** each maps to a field race, or the failure names the row to correct
