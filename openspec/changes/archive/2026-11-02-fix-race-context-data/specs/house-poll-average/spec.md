# Spec Delta

## MODIFIED Requirements

### Requirement: Nominee head-to-head matching

A question SHALL count only if exactly one answer matches each of the district's two principals, uniquely among its candidate-field rows, by the surname rule refined by first initial. Principals SHALL be the single Democratic and Republican nominees unless a reviewed entry names them; a reviewed principal's poll party code need not match the ballot. Other named candidates MAY appear. Unmatched, ambiguous, or non-principal matchups SHALL be excluded with a reason.

#### Scenario: Hypothetical pre-primary matchup
- **WHEN** a district has a question pairing the Republican nominee with a Democrat who is not in the candidate field
- **THEN** that question is excluded as a non-nominee matchup
- **AND** a different question in the same district that pairs both nominees remains eligible

#### Scenario: Party-label question
- **WHEN** a poll asks a question whose answers are only `Democrat` and `Republican`
- **THEN** that question is excluded because it does not name the nominees

#### Scenario: Ambiguous surname
- **WHEN** a poll's Republican surname matches the Republican nominee and another field candidate in the same district, and the first initial does not decide between them
- **THEN** the question is excluded as an ambiguous match and does not choose either candidate

#### Scenario: Reviewed independent principal
- **WHEN** a reviewed entry names independent Bill Hill and Republican Nick Begich as AK-AL's principals, and a question has answers for Hill, Begich, Democrat Eric Hafner, and others
- **THEN** the question counts with Hill's share as the non-Republican principal share and Begich's as the Republican share

### Requirement: District average values and status

The averages output SHALL have one row per candidate-field district. Each row SHALL hold the weighted mean principal shares and the weighted mean non-Republican-principal-minus-Republican margin, in percentage points of all respondents. It SHALL also hold the principal names, the matchup basis (`dem_rep` or `reviewed`), the selected poll count, the distinct pollster count, the latest poll end date, a status, and a source ID. Values SHALL be blank unless the status is `available`.

#### Scenario: District with eligible polls
- **WHEN** a district has three selected nominee polls
- **THEN** its status is `available`, its poll count is 3, and its margin equals the weighted mean of the three D-minus-R margins

#### Scenario: District without polling
- **WHEN** a district has a Democratic and a Republican nominee but no 2026 general-election questions
- **THEN** its status is `no_polls` and every average value is blank, not zero

#### Scenario: Polls exist but none qualify
- **WHEN** every question for a district is excluded
- **THEN** its status is `no_eligible_polls` and its values are blank

#### Scenario: No two-party nominee pair
- **WHEN** a district's field lacks exactly one Democratic and one Republican candidate and has no reviewed principal entry
- **THEN** its status is `no_dem_rep_field` and its values are blank, regardless of polling

#### Scenario: Reviewed matchup basis
- **WHEN** AK-AL's average uses a reviewed principal entry
- **THEN** its matchup basis is `reviewed` and its principal names are Bill Hill and Nick Begich

## ADDED Requirements

### Requirement: Reviewed House principal entries are validated

Each reviewed House principal entry SHALL name a district, a non-Republican and a Republican principal, evidence, reviewer, and date. The build SHALL exit nonzero without replacing outputs when an entry names an unknown district or a candidate absent from that district's field.

#### Scenario: Stale entry
- **WHEN** a reviewed entry names a candidate no longer in AK-AL's field
- **THEN** the build exits nonzero naming the entry and preserves previous outputs
