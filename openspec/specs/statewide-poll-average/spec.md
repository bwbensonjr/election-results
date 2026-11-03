# statewide-poll-average Specification

## Purpose

Turn the saved 2026 Senate and governor polling snapshots into a traceable, weighted two-candidate polling average for each statewide race, with every included and excluded poll question explained.

## Requirements

### Requirement: Eligible statewide poll questions

The average SHALL consider only 2026-cycle, general-stage questions from the Senate snapshot for Senate races and the governor snapshot for governor races, assigned by state to a race in the statewide field. Other cycles, primary or runoff stages, and states without that race SHALL be excluded with a recorded reason. `Generic` and party `NONE` answers SHALL NOT count as candidates.

#### Scenario: Off-cycle governor poll
- **WHEN** the governor snapshot has a 2025 general-election question for Virginia
- **THEN** it contributes to no average and the input log records it as out of cycle

#### Scenario: State without the race
- **WHEN** a Senate question names a state that has no 2026 Senate race in the field
- **THEN** it is excluded with an unknown-race reason

### Requirement: Principal matchup per race

Each race SHALL have one principal matchup: its single Democratic and Republican candidates, unless a reviewed entry names the non-Republican principal, and the Republican principal where there are several, with evidence, reviewer, and date. A race with neither SHALL have status `no_principal_matchup`. Entries for absent races or candidates SHALL fail the build.

#### Scenario: Independent principal opponent
- **WHEN** Nebraska's Senate field has no Democrat and a reviewed entry names independent Dan Osborn as the principal opponent of the Republican nominee
- **THEN** Nebraska's matchup is Osborn against the Republican nominee, and the output marks the matchup basis as reviewed

#### Scenario: Several Republicans on a top-four ballot
- **WHEN** Alaska's Senate field has three Republicans and a reviewed entry names Mary Peltola and Dan Sullivan
- **THEN** Alaska's matchup is Peltola against Sullivan; without the entry its status is `no_principal_matchup`

#### Scenario: Stale reviewed entry
- **WHEN** a reviewed entry names a candidate absent from that race's field
- **THEN** the build exits nonzero naming the entry and preserves previous outputs

### Requirement: Principal candidate matching

A question SHALL count only if exactly one answer matches each principal candidate uniquely among the race's field rows, using the surname rule refined by first initial. The poll's party code for an answer SHALL NOT be required to equal the ballot party. Other named answers MAY appear. Unmatched, ambiguous, or non-principal questions SHALL be excluded with a reason.

#### Scenario: Poll party code differs from ballot
- **WHEN** a Nebraska poll codes Osborn as `DEM` and the ballot lists him as an independent principal candidate
- **THEN** the answer still matches Osborn and the question can count

#### Scenario: Namesake answers
- **WHEN** a question names both "Dan Sullivan" and "Dan J. Sullivan", and both match principal Dan Sullivan by the surname rule
- **THEN** only the answer whose full given name equals the ballot name counts for Sullivan, and the question can count

#### Scenario: Hypothetical non-nominee pairing
- **WHEN** a question pairs the Republican nominee with a Democrat not in the field
- **THEN** it is excluded as a non-principal matchup

### Requirement: Selection and weights match the House method

Each poll SHALL contribute at most one question, selected and weighted with the House polling average's population preference, tie-breaks, first-round-only ranked-choice rule, recency anchor, sample, pollster, and partisan factors, and their documented constants. Weights SHALL NOT depend on the build date.

#### Scenario: Same constants as the House build
- **WHEN** a fixture poll with identical inputs is run through the House and statewide builds
- **THEN** its four weight factors and final weight are equal

### Requirement: Race average values and status

The averages output SHALL have one row per statewide race with the principal candidate names, matchup basis, weighted shares, weighted principal-minus-Republican margin in percentage points, poll and pollster counts, latest end date, status, and source ID. Status SHALL be `available`, `no_polls`, `no_eligible_polls`, or `no_principal_matchup`; values SHALL be blank unless `available`.

#### Scenario: Race with eligible polls
- **WHEN** a race has four selected principal-matchup polls
- **THEN** its status is `available` and its margin is the weighted mean of the four margins

#### Scenario: Unpolled race
- **WHEN** a race has principal candidates but no general-election questions
- **THEN** its status is `no_polls` and its values are blank, not zero

### Requirement: Traceable statewide input log

The build SHALL publish a question-level log with one row per question in both snapshots, holding office, race ID, poll and question IDs, pollster, end date, population, matched principal shares and margin, included flag, reason, each weight factor, and the final weight.

#### Scenario: Recomputing a race average
- **WHEN** an analyst takes one race's included log rows
- **THEN** the weighted mean of their margins with logged weights reproduces the published margin within rounding

### Requirement: Reproducible offline statewide polling build

The build SHALL run offline from the saved snapshots, statewide field, and reviewed matchups, produce identical sorted output for reordered inputs, and fail without replacing previous outputs on missing columns or malformed dates, shares, or sample sizes in considered candidate rows. House polling outputs SHALL be unchanged.

#### Scenario: Shuffled poll rows
- **WHEN** the snapshot rows are reordered
- **THEN** both statewide outputs are byte-identical to the previous build
