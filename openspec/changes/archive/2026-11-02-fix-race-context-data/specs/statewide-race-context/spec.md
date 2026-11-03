# Spec Delta

## ADDED Requirements

### Requirement: Roster incumbency columns are joined by race

Both statewide exports SHALL append, after all existing columns, the roster's incumbent name, incumbent party, vacancy marker, ballot status, an open-seat flag, and a roster source ID, joined by race ID. The candidate export SHALL also append a roster incumbent flag that is true only on the candidate row matched to a `running` incumbent. Governor rows SHALL get roster incumbency even though they have no FEC incumbency.

#### Scenario: Governor running for reelection
- **WHEN** the roster names a governor as the `running` incumbent of a governor race
- **THEN** that race row has open-seat false and that governor's candidate row has the roster incumbent flag set, while its FEC fields stay `not_federal`

#### Scenario: Open Senate seat
- **WHEN** a Senate race's roster status is `not_running`
- **THEN** its race row has open-seat true and no candidate row has the roster incumbent flag set

#### Scenario: Existing columns unchanged
- **WHEN** the roster columns are added
- **THEN** every earlier column keeps its position and values, and the row counts are unchanged
