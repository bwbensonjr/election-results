# Spec Delta

## MODIFIED Requirements

### Requirement: Color metrics

The map SHALL be colored by one selectable metric: election-night results, polling average margin, results versus polls (labeled Results vs. Polls), 2024 Harris/Trump margin (labeled President), Cook PVI lean, or incumbent party. Democratic values SHALL use blue shades, Republican values red shades, scaled by margin, and missing or unknown values grey. Under the President metric, margins with status `available` or `interpolated` SHALL be colored the same way.

#### Scenario: Margin unavailable
- **WHEN** the metric is 2024 margin and a district's margin status is `prior_boundaries`
- **THEN** the district is grey and its detail says the margin describes prior lines

#### Scenario: Interpolated margin
- **WHEN** the metric is 2024 margin and a Texas district drawn on its 2026 shape has an interpolated margin of Trump +24
- **THEN** the district is drawn in the strongest red step, like a district with an available margin of the same size

#### Scenario: PVI metric
- **WHEN** the metric is PVI and a race's Cook PVI is R+12
- **THEN** the race is drawn in the strongest red step, with PVI steps set at half the margin steps since PVI is about half a two-party margin

#### Scenario: Results metric before votes
- **WHEN** the metric is results and a race has no votes
- **THEN** the race is grey

#### Scenario: Results vs. Polls button
- **WHEN** the viewer looks at the metric controls in any office mode
- **THEN** a Results vs. Polls button appears beside Results, Polls, President, PVI, and Incumbent

## ADDED Requirements

### Requirement: Results vs. Polls coloring

Under the Results vs. Polls metric, each race with polls and votes SHALL be colored by its difference (result margin minus polling average margin for the poll principals, as defined by the results-vs-polls capability), computed from the board's current results: blue when the Democratic side beat its polls, red when the Republican did, in four steps of under 2, 2 to 5, 5 to 10, and 10 or more points. A called race SHALL be solid and an uncalled race hatched.

#### Scenario: Large Republican over-performance
- **WHEN** a called Senate race polled at D+2.5 and the result is R+6.0
- **THEN** the state is drawn solid in the third red step (5 to 10 points), for a difference of 8.5 points toward the Republican

#### Scenario: Uncalled race
- **WHEN** an uncalled House race with partial votes shows Democratic over-performance of 3 points
- **THEN** the district is hatched in the second blue step

#### Scenario: Updates with new results
- **WHEN** new results change a race's margin while the Results vs. Polls metric is selected
- **THEN** the race's color and difference update without a reload

### Requirement: Races without polling are neutral

Under the Results vs. Polls metric, a race without an available polling average SHALL be drawn in the board's neutral no-data grey, without any result coloring, and a polled race with no votes or a missing principal SHALL also be grey. The legend SHALL label the grey as no polling average or no votes yet.

#### Scenario: Unpolled district with a winner
- **WHEN** AL-01 has no polling average and a called Republican winner
- **THEN** AL-01 is grey under Results vs. Polls, not red

### Requirement: Results vs. Polls race detail

When a race is selected under the Results vs. Polls metric, the detail SHALL show the result shares and margin for the two poll principals, the polling average shares and margin with its poll count, the signed difference labeled by which side over-performed, and the polls in the average with pollster, end date, population, sample size, shares, and margin, sorted by end date with the most recent first. The rest of the race detail SHALL remain available.

#### Scenario: Selected polled race
- **WHEN** the viewer selects AK-SEN under Results vs. Polls
- **THEN** the detail shows Peltola's and Sullivan's result shares and margin, their polling average of 48.0% to 45.5% (D+2.5, 21 polls), the difference, and 21 polls with the poll ending latest at the top

#### Scenario: Selected race without polling
- **WHEN** the viewer selects a race with no polling average under Results vs. Polls
- **THEN** the detail says the race has no polling average and lists no polls, and still shows the result

#### Scenario: Partial count
- **WHEN** the selected race is uncalled
- **THEN** the detail notes that the difference uses a partial count and shows the percent of expected vote
