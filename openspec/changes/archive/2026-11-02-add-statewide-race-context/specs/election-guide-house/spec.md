# Spec Delta

## ADDED Requirements

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
