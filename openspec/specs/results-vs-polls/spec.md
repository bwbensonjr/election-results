# results-vs-polls Specification

## Purpose

Compare each 2026 Governor, Senate, and House result with that race's pre-election polling average, so the size and direction of every polling miss can be read per race and shown on the Big Board.

## Requirements

### Requirement: One comparison row per race

The comparison dataset SHALL contain exactly one row for every race in the election-night baseline, in all three offices, keyed by race key. Each row SHALL carry the office, state, polling average principals, their poll shares and margin, poll count and latest poll end date, the result shares and margin for the same principals, the difference, whether the race is called, percent of expected vote, and a comparison status.

#### Scenario: Full coverage
- **WHEN** the dataset is built from a baseline of 435 House, 35 Senate, and 36 governor races
- **THEN** it has 506 rows, one per race key, including races with no polls

#### Scenario: Results file missing a baseline race
- **WHEN** the results file has no entry for a baseline race key
- **THEN** the build fails naming the race and leaves the previous dataset in place

### Requirement: Result margin uses the poll principals

The result margin SHALL be the vote share of the polling average's Democratic-side principal minus the vote share of its Republican principal, each as a percent of the race's total vote, found among the race's result candidates by baseline candidate name. It SHALL NOT use the race's top-Democrat-minus-top-Republican margin. Shares and margins SHALL be rounded to two decimals.

#### Scenario: Independent principal
- **WHEN** AK-AL's average pairs independent Bill Hill with Republican Nick Begich, and the result has Begich 48.62%, Hill 41.21%, and Democrat Eric Hafner 7.51%
- **THEN** the result margin is -7.41 (Hill minus Begich), not Hafner minus Begich

#### Scenario: Principal absent from results
- **WHEN** a race has an available average but one principal has no result candidate with that baseline name
- **THEN** the row has status `principal_missing`, no result margin, and no difference

### Requirement: Signed difference

The difference SHALL be the result margin minus the polling average margin, in percentage points rounded to two decimals. A positive difference SHALL mean the Democratic-side principal did better than the polls; a negative difference SHALL mean the Republican did better.

#### Scenario: Republican over-performance
- **WHEN** a race's polling average margin is D+2.50 and its result margin is R+1.00
- **THEN** the difference is -3.50

#### Scenario: Democratic over-performance
- **WHEN** a race's polling average margin is R+8.17 and its result margin is R+4.00
- **THEN** the difference is 4.17

### Requirement: Comparison status

Each row SHALL have exactly one status: `compared` when the race has an available polling average and votes for both principals, `no_polls` when the race's polling average status is anything other than `available`, `no_votes` when it has an average but no votes are reported, and `principal_missing` as above. Only `compared` rows SHALL carry a difference.

#### Scenario: Race without polling
- **WHEN** AL-01 has polling average status `no_polls` and a called result
- **THEN** its row has status `no_polls`, its call status, winner party, and expected vote are filled, and its poll fields, principal result shares, and difference are blank

#### Scenario: Polled race before votes
- **WHEN** a race has an available average and zero total votes
- **THEN** its row has status `no_votes` and no difference

### Requirement: Included poll list

A second file SHALL list every poll question included in any race's polling average, from both the House and statewide input logs, with race key, office, pollster, end date, population, sample size, partisan sponsor, the two principals' shares, and the margin. It SHALL list only questions marked included, and each race's count SHALL equal the poll count in its comparison row.

#### Scenario: Poll counts agree
- **WHEN** AK-SEN's average reports 21 polls
- **THEN** the poll list has exactly 21 rows for AK-SEN

#### Scenario: Excluded questions left out
- **WHEN** a statewide question is logged as `superseded` or `out_of_cycle`
- **THEN** it does not appear in the poll list

### Requirement: Reproducible offline build

The build SHALL run from committed inputs without network access, SHALL default to the checked-in results snapshot, SHALL accept another results file as an argument, and SHALL write byte-identical outputs when run twice on the same inputs. It SHALL report the counts of each status.

#### Scenario: Rebuild from the snapshot
- **WHEN** the build is run twice against `2026/results/ap-results.json`
- **THEN** both runs write identical files and print the number of `compared`, `no_polls`, `no_votes`, and `principal_missing` races
