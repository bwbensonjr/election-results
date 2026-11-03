# congressional-boundary-vintage Specification

## Purpose

Record which states elect their 2026 House members on different congressional lines than the presidential results source describes, so district metrics from older lines are never presented as describing the current district.

## Requirements

### Requirement: Reviewed boundary vintage registry

A committed registry SHALL list every state whose 2026 congressional lines differ from the lines of the presidential results source. Each entry SHALL name the state, the plan in effect for 2026, at least one evidence URL, a reviewer, and a review date. States not listed SHALL be treated as using the same lines as the source.

#### Scenario: Redrawn state listed
- **WHEN** Utah's 2026 congressional map differs from the map behind the presidential results source
- **THEN** the registry has a Utah entry naming the 2026 plan, evidence, reviewer, and date

#### Scenario: Unchanged state
- **WHEN** Massachusetts uses the same lines in 2026 as the presidential results source
- **THEN** Massachusetts has no registry entry and its district metrics are treated as current

### Requirement: Registry entries are validated

The build SHALL exit nonzero, naming the entry, when a registry entry has an unknown state code, a duplicate state, no evidence URL, or no reviewer or review date. It SHALL NOT replace previous outputs on such a failure.

#### Scenario: Entry without evidence
- **WHEN** a registry entry for Texas has an empty evidence list
- **THEN** the build exits nonzero naming the Texas entry and preserves the previous exports

### Requirement: Consistency check against published PVI

The build SHALL report, without failing, each unlisted state where a district's published 2026 PVI and its presidential margins disagree by more than a documented threshold, so reviewers can decide whether the state belongs in the registry.

#### Scenario: Unlisted state with large disagreement
- **WHEN** a state is not in the registry and one of its districts has a 2026 PVI of D+12 while its presidential margins imply about R+11
- **THEN** the build lists that district and state in a boundary review report and still completes
