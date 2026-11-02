# house-poll-average Specification

## Purpose

Turn the saved 2026 U.S. House polling snapshot into a traceable, weighted Democratic-versus-Republican polling average for each district's nominee matchup, with every included and excluded poll question explained.

## Requirements

### Requirement: Eligible poll questions

The average SHALL consider only 2026-cycle, general-stage U.S. House questions that name a valid state and a district seat. Questions labeled with state `US`, questions for primary, runoff, or special stages, and questions with no seat number SHALL be excluded, and the reason SHALL be recorded. Answers for `Generic` candidates or party `NONE` SHALL NOT count as candidates.

#### Scenario: Generic ballot and primary rows
- **WHEN** the snapshot contains a nationwide `US` generic-ballot question and a district primary question
- **THEN** neither contributes to any district average
- **AND** the input log records each question with its exclusion reason

#### Scenario: At-large seat numbering
- **WHEN** a poll for Vermont, an at-large state in the candidate field, uses seat number `1`
- **THEN** the question is assigned to district `00` with district ID `VT-AL`

### Requirement: Nominee head-to-head matching

A question SHALL count only if it contains exactly one Democratic and one Republican named candidate who each match uniquely, among all of that district's candidate-field rows, to its single Democratic and single Republican nominee. The match SHALL use the existing surname rule, refined by first initial. Other named candidates MAY appear in the question. Unmatched, ambiguous, or non-nominee matchups SHALL be excluded with a reason.

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

### Requirement: One question per poll

Each poll SHALL contribute at most one eligible question. Selection SHALL prefer likely voters, then registered voters, then adults. Among questions with the same population, it SHALL prefer the question naming the most field candidates, then the lowest question ID. In ranked-choice questions, only first-choice, non-reallocated answers SHALL be used. Questions that are not selected SHALL be logged as superseded.

#### Scenario: Poll reports two populations
- **WHEN** one poll reports the same nominee matchup among registered and likely voters
- **THEN** only the likely-voter question contributes, and the registered-voter question is logged as superseded

#### Scenario: Ranked-choice rounds
- **WHEN** a question has first-round and reallocated final-round answers
- **THEN** only the first-round, non-reallocated shares contribute

### Requirement: Documented poll weights

Each selected poll's weight SHALL be the product of four named, documented factors. Recency decays exponentially with the number of days before the district's latest included poll end date. Sample size uses a capped square root, with a documented default when the size is missing. The pollster factor shrinks repeated polls by one pollster in a district. The partisan factor lowers the weight of party-sponsored polls. Weights SHALL NOT depend on the build date.

#### Scenario: Repeated pollster
- **WHEN** one pollster has four selected polls in a district and another pollster has one
- **THEN** each of the four polls receives the pollster factor for a count of four, so that pollster's combined weight is less than four times a comparable single poll

#### Scenario: Missing sample size
- **WHEN** a selected poll has a blank sample size
- **THEN** it uses the documented default size, and the input log marks the sample size as imputed

#### Scenario: Rebuilding on a later date
- **WHEN** the same snapshot is rebuilt a week later
- **THEN** every weight and average is unchanged

### Requirement: District average values and status

The averages output SHALL have one row per candidate-field district. Each row SHALL hold the weighted mean Democratic and Republican shares and the weighted mean Democratic-minus-Republican margin, in percentage points of all respondents. It SHALL also hold the nominee names, the selected poll count, the distinct pollster count, the latest poll end date, a status, and a source ID. Values SHALL be blank unless the status is `available`.

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
- **WHEN** a district's field lacks exactly one Democratic and one Republican candidate
- **THEN** its status is `no_dem_rep_field` and its values are blank, regardless of polling

### Requirement: Traceable input log

The build SHALL publish a question-level log with one row for every question in the poll snapshot. Each row SHALL hold poll and question IDs, the district, the pollster, the end date, the population, the matched nominee shares and margin, an included flag, the exclusion or supersession reason, each weight factor, and the final weight.

#### Scenario: Recomputing an average from the log
- **WHEN** an analyst takes the included rows for one district from the log
- **THEN** the weighted mean of their margins, using the logged final weights, reproduces the district's published margin within rounding

### Requirement: Reproducible offline polling build

The averaging build SHALL run offline from the saved poll snapshot and candidate field. It SHALL produce the same rows in the same sorted order however the input rows are ordered. It SHALL fail without replacing previous outputs on missing required columns, unparseable dates, or nonnumeric shares or sample sizes in candidate rows.

#### Scenario: Shuffled poll rows
- **WHEN** the poll snapshot's rows are reordered without other changes
- **THEN** both outputs are identical to the previous build

#### Scenario: Malformed share
- **WHEN** a considered question has a nonnumeric `pct` value
- **THEN** the build exits nonzero and names the question and field, and the previous outputs are preserved
