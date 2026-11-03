# statewide-candidate-field Specification

## Purpose

Assemble the 2026 Senate and governor general-election field from a ballot source, FEC Senate records, pre-general filings, finance, and poll presence, with unknowns kept distinct from verified false values.

## Requirements

### Requirement: One race per state and office

The statewide field SHALL contain every ballot candidate for each November 3, 2026 Senate and governor general election in the ballot source. Each row SHALL carry state, office (`Senate` or `Governor`), a race ID of the form `STATE-SEN` or `STATE-GOV`, name, normalized party, raw party, and source URL. A state SHALL have at most one race per office.

#### Scenario: Special Senate election
- **WHEN** the ballot source lists Ohio's special Senate election and Ohio has no regular Senate race in 2026
- **THEN** its candidates appear under race ID `OH-SEN` with office `Senate`

#### Scenario: Two Senate races in one state
- **WHEN** the ballot source lists two Senate races for the same state
- **THEN** the build fails and names the state rather than merging or dropping either race

#### Scenario: State without a governor race
- **WHEN** a state has no 2026 governor election
- **THEN** the field has no `STATE-GOV` rows for that state

### Requirement: Senate FEC enrichment

Senate rows SHALL carry the FEC candidate ID, FEC name, incumbency, 12G filing flag, receipts, and cash on hand from the canonical FEC Senate record selected by identity resolution, plus match status, reason, and alternate IDs. Unresolved Senate rows SHALL keep these FEC-derived fields blank.

#### Scenario: Matched incumbent senator
- **WHEN** a Senate candidate resolves to one FEC Senate record coded as an incumbent
- **THEN** the row carries that record's ID, incumbency, filing flag, and financial values

#### Scenario: Ambiguous Senate candidate
- **WHEN** two FEC Senate records plausibly match a candidate and no reviewed decision applies
- **THEN** the FEC-derived fields are blank and the match status is `ambiguous`

### Requirement: Governor rows are not FEC candidates

Governor rows SHALL have FEC match status `not_federal`, blank FEC ID, incumbency, filing, and financial fields, and SHALL NOT appear in the identity review queue. Blank SHALL mean unknown, not false.

#### Scenario: Governor candidate
- **WHEN** the field includes a governor candidate
- **THEN** the row's match status is `not_federal` and its incumbency and `filed_12g` values are blank rather than `False`

### Requirement: Statewide poll presence

Each row SHALL carry an `in_general_polls` flag computed from that office's poll snapshot using the House flag's surname rule, poll window, and general-stage filter, within the same state. Poll presence SHALL NOT affect FEC identity selection.

#### Scenario: Candidate named in a governor poll
- **WHEN** a qualifying 2026 general-election governor poll in Georgia names a candidate whose surname matches one Georgia governor candidate
- **THEN** that candidate's `in_general_polls` is true and Georgia Senate candidates are unaffected

### Requirement: Review queue and discrepancy report

The build SHALL write a deterministic review queue of unmatched and ambiguous Senate candidates with their plausible FEC records, and a discrepancy report of 12G-filing FEC Senate candidates absent from the ballot and races without both a Democratic and a Republican candidate.

#### Scenario: Senate filer missing from ballot
- **WHEN** an FEC Senate candidate filed a 12G report and matches no ballot row or reviewed alternate ID
- **THEN** the discrepancy report lists that candidate with its state

### Requirement: Offline, validated statewide build

The field build SHALL run offline from committed inputs, produce output independent of input row order, and exit nonzero without replacing previous outputs on missing columns, malformed rows, invalid reviewed decisions, or duplicate races. It SHALL NOT change House inputs or outputs.

#### Scenario: Reordered inputs
- **WHEN** the ballot and FEC rows are shuffled without other changes
- **THEN** the field, review queue, and discrepancy report are byte-identical to the previous build

#### Scenario: House outputs untouched
- **WHEN** the statewide build runs
- **THEN** `house-general-field.csv` and the House review outputs are unchanged
