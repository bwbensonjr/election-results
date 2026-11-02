# Spec Delta

## ADDED Requirements

### Requirement: Election guide columns are joined by district

Both exports SHALL append, after all existing columns, the election-guide columns, the guide name check, `guide_status`, and a guide source ID. Guide values SHALL be copied unchanged from the guide CSV by district: once per district row, and repeated on each of that district's candidate rows. Districts the guide does not name SHALL have status `not_in_guide` and blank guide values.

#### Scenario: Guide district
- **WHEN** the guide CSV has a `KY-06` row
- **THEN** the KY-06 context row and each KY-06 candidate row carry its guide values with `guide_status` set to `in_guide`

#### Scenario: District outside the guide
- **WHEN** the guide does not name CA-13
- **THEN** CA-13's guide columns are blank and its `guide_status` is `not_in_guide`

#### Scenario: Existing columns unchanged
- **WHEN** the guide columns are added
- **THEN** every earlier column keeps its position and values, and the row counts are unchanged

### Requirement: Guide names are checked against the candidate field

Each guide district SHALL carry a `guide_name_check` comparing the guide's Democratic and Republican names with the field's candidates of those parties. The comparison SHALL use the surname rule that `in_general_polls` uses. The check SHALL be `matched` when every guide name matches, `mismatch` when any does not, and `not_named` when the guide names neither. A mismatch SHALL NOT change candidate or guide values.

#### Scenario: Guide names both nominees
- **WHEN** the guide gives `Alvarado (R) v Dembo (D)` for KY-06 and the field has Ralph Alvarado (REP) and Zach Dembo (DEM)
- **THEN** KY-06's `guide_name_check` is `matched`

#### Scenario: Guide name not in the field
- **WHEN** a guide Democratic name matches no Democratic candidate in that district's field
- **THEN** the check is `mismatch`, and the guide and candidate values stay as they were

### Requirement: Guide validation gates publication but not completeness

The context build SHALL validate the guide CSV against its markdown source and the candidate field before it replaces any export, and SHALL exit nonzero on a validation failure while preserving previous exports. Complete-data validation SHALL NOT require districts to appear in the guide, and districts without guide coverage SHALL NOT add issue rows.

#### Scenario: Guide out of step with markdown
- **WHEN** the markdown names a district that the guide CSV lacks
- **THEN** the context build exits nonzero with that district named, and previous exports are unchanged

#### Scenario: Strict build with partial guide coverage
- **WHEN** `--require-complete` runs, every district has both presidential margins and PVI, and only 44 districts are in the guide
- **THEN** the build succeeds and the issues report has no guide rows
