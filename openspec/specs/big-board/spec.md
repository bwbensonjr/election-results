# big-board Specification

## Purpose

Give a published, shareable election-night view of every 2026 House, Senate, and governor race on a U.S. map, colored by a chosen metric, with full detail and live results for any selected race.

## Requirements

### Requirement: Office modes

The board SHALL offer Governor, Senate, and House modes. Governor and Senate modes SHALL draw states, House mode SHALL draw districts, and states or districts with no race in the selected office SHALL be drawn as not on the ballot, distinct from missing data.

#### Scenario: Senate mode
- **WHEN** the viewer selects Senate
- **THEN** the 35 states with a Senate race are colored by the current metric and the other states are shown as not on the ballot

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

### Requirement: Results coloring distinguishes calls

Under the results metric, a called race SHALL be colored solid by the winner's party and an uncalled race with votes SHALL be colored by the leader's party in a visibly lighter or hatched style. A winner outside the two parties SHALL use a distinct third color.

#### Scenario: Leading but not called
- **WHEN** a Republican leads an uncalled race at 40% expected vote
- **THEN** the race is shown as a Republican lead, not a Republican win

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

### Requirement: Prior-line districts are marked

In House mode, districts whose shapes have boundary vintage `prior_boundaries` SHALL be visibly marked on the map and labeled in their detail as drawn on 2024 lines, so an outdated shape is never presented as the current district.

#### Scenario: State without an enacted plan
- **WHEN** Louisiana's districts are built on prior lines and the viewer selects LA-02
- **THEN** Louisiana's districts carry the prior-lines marking and LA-02's detail says its shape shows 2024 lines

### Requirement: Zoom and selection

The viewer SHALL be able to zoom and pan the map, zoom to a state, and select a race by clicking or tapping its shape or by searching for a race key, state, or candidate name. The selection SHALL be kept when the data updates.

#### Scenario: Select a district
- **WHEN** the viewer clicks PA-07 in House mode
- **THEN** PA-07 is highlighted and its details open

### Requirement: Race detail

The detail view for a selected race SHALL show the incumbent and whether the seat is open, the winner if called, each candidate's votes and vote share, percent of expected vote and precincts reporting, the 2024 Harris/Trump margin with its boundary status, Cook PVI, and the polling average where available. An interpolated 2024 margin SHALL be labeled as an estimate on the 2026 lines.

#### Scenario: Open seat with results
- **WHEN** the viewer selects an open-seat race with partial results
- **THEN** the detail shows the departing incumbent, the open-seat flag, candidates with votes and percentages, and reporting levels

#### Scenario: Interpolated margin in detail
- **WHEN** the viewer selects a North Carolina district whose 2024 margin is interpolated
- **THEN** the detail shows the margin with a note that it is estimated from 2024 results reallocated to the 2026 lines

### Requirement: Freshness and summary

The board SHALL show when results were last updated by AP and when they were last published, warn when published data is more than 15 minutes old during the night, and summarize called seats by party for each office.

#### Scenario: Stale data
- **WHEN** the newest published results are 20 minutes old
- **THEN** the board shows a visible staleness warning with the time

### Requirement: Test data is labeled

When the published results come from races AP marks as test data, the board SHALL show a prominent test-data banner on every view.

#### Scenario: Rehearsal with generated results
- **WHEN** the published results were ingested from the mock feed
- **THEN** the board shows a test-data banner above the map

### Requirement: Picks up new results without losing context

The board SHALL read live results from the artifact's database and show new results as soon as they are written, without the page reloading, keeping the selected office, metric, zoom, and selected race. It SHALL draw results only from a complete set of records that share one content hash, never a mix of two runs. The board SHALL show when it was loaded, so a reload can be seen.

#### Scenario: Update while a race is selected
- **WHEN** new results are written while the viewer has GA-SEN selected under the results metric and the map zoomed to Georgia
- **THEN** the board shows the new GA-SEN numbers with the same mode, metric, zoom, and selection

#### Scenario: No reload on update
- **WHEN** three successive result updates are written to the database
- **THEN** the board shows each one and its loaded time does not change

#### Scenario: Partial update
- **WHEN** the board has received some records of a new run but not all of them
- **THEN** it keeps showing the previous complete results until the set is complete

### Requirement: Fallback to the published results file

When the database is unavailable to the viewer, or no complete set of records arrives within 10 seconds of loading, the board SHALL read the published results file and check it every 60 seconds, and SHALL switch to the database when it delivers.

#### Scenario: Database unavailable
- **WHEN** the board cannot reach the database
- **THEN** it shows the results from the published file with their publish time

### Requirement: No flash on load

When the board loads, it SHALL apply the viewer's saved zoom before drawing the map, and SHALL NOT draw an empty results map before results arrive when the results metric is selected.

#### Scenario: Reload while zoomed
- **WHEN** the board reloads while the viewer's saved view is zoomed to Pennsylvania under the results metric
- **THEN** the first map drawn is zoomed to Pennsylvania and shows results, with no full-country or grey frame first

### Requirement: Works on phone and desktop, light and dark

The board SHALL be usable at phone width without horizontal scrolling, with the detail view below or over the map, and SHALL render correctly in light and dark color schemes with readable contrast.

#### Scenario: Phone width
- **WHEN** the board is opened at 375 pixels wide
- **THEN** the map, mode and metric controls, and detail view are usable without horizontal scrolling
