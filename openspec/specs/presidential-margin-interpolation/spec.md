# presidential-margin-interpolation Specification

## Purpose

Estimate 2020 and 2024 presidential results on the 2026 congressional lines of redrawn states by reallocating source votes from the 119th Congress districts to the enacted 2026 districts, weighted by shared 2020 Census population and county-level presidential vote rates.

## Requirements

### Requirement: Block-level prior-line sources

The 119th Congress district lines SHALL be taken from Census block assignment data at block resolution, and block population and location from 2020 Census blocks. Each source file SHALL be recorded in a committed manifest with URL, retrieval date, and SHA-256; a hash mismatch SHALL fail the build without replacing outputs.

#### Scenario: Changed block file
- **WHEN** a cached block assignment file's hash differs from the manifest
- **THEN** the crosswalk build fails naming the file and keeps the previous crosswalk

### Requirement: County presidential results

The 2020 and 2024 county-level presidential Democratic, Republican, and total votes for each crosswalk state SHALL come from a snapshot recorded in the source manifest with URL, retrieval date, and SHA-256, and SHALL be committed with each county's 2020 Census population summed from its blocks. Every county with populated blocks in a crosswalk state SHALL have results for both years, or the build SHALL fail naming the county.

#### Scenario: County missing from the results snapshot
- **WHEN** a populated Texas county has no 2024 row in the county results snapshot
- **THEN** the crosswalk build fails naming the county and keeps the previous outputs

### Requirement: Crosswalk scope

A crosswalk SHALL be built for exactly the boundary-vintage registry states whose district geometry has an enacted 2026 plan. Registry states without one SHALL get no crosswalk and SHALL be listed in the build report.

#### Scenario: State without 2026 shapes
- **WHEN** a state is added to the registry before the geometry manifest has its 2026 plan
- **THEN** the crosswalk has no rows for that state and the build report lists it as not interpolated

### Requirement: Population-weighted crosswalk

Each block SHALL be assigned to its 119th Congress district, its county, and the 2026 district containing its internal point. The committed crosswalk SHALL have one row per state, old district, county, and new district with nonzero shared population, giving that population and its share of the old district's population; shares from each old district SHALL sum to 1.

#### Scenario: Old district split across new districts
- **WHEN** old TX-28 lies in one county, with 60 percent of its 2020 population in new TX-28 and 40 percent in new TX-34
- **THEN** the crosswalk has rows (TX-28, that county, TX-28, share 0.6) and (TX-28, that county, TX-34, share 0.4)

#### Scenario: Every new district covered
- **WHEN** the crosswalk is built for a state
- **THEN** every 2026 district of that state appears as a new district in at least one row, or the build fails naming it

### Requirement: Unplaced blocks are bounded

A populated block whose internal point lies in no 2026 district SHALL be assigned to the nearest 2026 district and counted in the build report. The build SHALL fail if unplaced population exceeds 0.1 percent of a state's population.

#### Scenario: Coastal block outside the plan shapes
- **WHEN** a populated Florida block's internal point lies just offshore of every 2026 district
- **THEN** it is assigned to the nearest district and the report counts it and its population

### Requirement: Vote reallocation

For each year and for Democratic, Republican, and other votes (total minus both), each crosswalk row SHALL be weighted by its shared population times its county's votes per 2020 resident, and each old district's votes SHALL be split among its rows by those weights. A new district's votes SHALL sum its rows, its total SHALL sum the three parts, and shares and margins SHALL use the source definitions.

#### Scenario: County rates shift votes within an old district
- **WHEN** old UT-01 has 100 residents in county A, all in new UT-01, with 0.3 Democratic votes per resident, and 100 residents in county B, all in new UT-02, with 0.1 Democratic votes per resident
- **THEN** new UT-01 receives 75 percent of old UT-01's Democratic votes and new UT-02 receives 25 percent

#### Scenario: Margin from reallocated votes
- **WHEN** a new district receives 100,000 Democratic, 120,000 Republican, and 225,000 total reallocated 2024 votes
- **THEN** its 2024 margin is -8.89 percentage points

### Requirement: State totals conserved

For each interpolated state and year, the reallocated Democratic, Republican, and total votes SHALL equal the sum of that state's source district votes within 1 vote; otherwise the build SHALL fail naming the state and year.

#### Scenario: Conservation check
- **WHEN** Utah's interpolated 2024 votes are summed
- **THEN** they match Utah's source district totals within 1 vote for each party and the total

### Requirement: PVI review report

The build SHALL write a non-failing report listing each interpolated district whose implied lean differs from its published Cook 2026 PVI by more than the boundary review threshold. The implied lean SHALL weight each year's margin relative to the national margin as Cook does, 75 percent 2024 and 25 percent 2020, halved to Cook's scale.

#### Scenario: Swing between elections
- **WHEN** an interpolated district's margins are 10 points above the national margin in 2020 and 2 points above it in 2024
- **THEN** its implied lean is D+2.0, not the D+3.0 an equal weighting would give

#### Scenario: Large disagreement
- **WHEN** an interpolated district's implied lean is R+2 and its Cook 2026 PVI is D+5
- **THEN** the district is listed in the report and the build still completes

### Requirement: Offline rebuild from the committed crosswalk

Building district context SHALL require only the committed crosswalk, county results, and presidential source, with no network access or geospatial dependencies. Rebuilding from unchanged inputs SHALL produce byte-identical outputs.

#### Scenario: Offline rebuild
- **WHEN** normalization runs without network access and without geospatial libraries installed
- **THEN** the interpolated margins are produced from the committed crosswalk unchanged

### Requirement: Plan assignments checked against Census 2026 blocks

For every crosswalk state, the build SHALL compare each populated block's point-in-polygon 2026 district with its district in the Census 120th Congress block equivalency file, recorded in the source manifest with URL, retrieval date, and SHA-256. The report SHALL give each state's agreement by population, and the build SHALL fail, keeping outputs, below 99.9 percent.

#### Scenario: Plan file matches the Census assignment
- **WHEN** the Tennessee plan shapes place 100 percent of Tennessee's population in the same districts as the Census 120th Congress file
- **THEN** the report records 100 percent agreement for Tennessee and the build continues

#### Scenario: Outdated plan file
- **WHEN** a state's plan shapes agree with the Census 120th Congress file for only 87 percent of its population
- **THEN** the build fails naming the state and its agreement, and keeps the previous crosswalk
