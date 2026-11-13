# Spec Delta

## ADDED Requirements

### Requirement: Plan assignments checked against Census 2026 blocks

For every crosswalk state, the build SHALL compare each populated block's point-in-polygon 2026 district with its district in the Census 120th Congress block equivalency file, recorded in the source manifest with URL, retrieval date, and SHA-256. The report SHALL give each state's agreement by population, and the build SHALL fail, keeping outputs, below 99.9 percent.

#### Scenario: Plan file matches the Census assignment
- **WHEN** the Tennessee plan shapes place 100 percent of Tennessee's population in the same districts as the Census 120th Congress file
- **THEN** the report records 100 percent agreement for Tennessee and the build continues

#### Scenario: Outdated plan file
- **WHEN** a state's plan shapes agree with the Census 120th Congress file for only 87 percent of its population
- **THEN** the build fails naming the state and its agreement, and keeps the previous crosswalk

## MODIFIED Requirements

### Requirement: Crosswalk scope

A crosswalk SHALL be built for exactly the boundary-vintage registry states whose district geometry has an enacted 2026 plan. Registry states without one SHALL get no crosswalk and SHALL be listed in the build report.

#### Scenario: State without 2026 shapes
- **WHEN** a state is added to the registry before the geometry manifest has its 2026 plan
- **THEN** the crosswalk has no rows for that state and the build report lists it as not interpolated
