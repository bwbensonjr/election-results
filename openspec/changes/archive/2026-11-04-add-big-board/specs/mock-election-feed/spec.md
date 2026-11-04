# Spec Delta

## Purpose

Generate realistic election-night responses in the exact shape of the Globe/AP feed for the real 2026 races and candidates, so ingestion, publishing, and the Big Board can be tested end to end before and between real updates.

## ADDED Requirements

### Requirement: Same shape as the live feed

Generated responses SHALL use the field names, nesting, value types, and race identifiers of a real pre-election response captured on November 3, 2026, including the non-tracked races and the national House row, so the ingestor cannot tell them apart from live data.

#### Scenario: Ingest a generated response
- **WHEN** the ingestor reads a generated response
- **THEN** it validates and joins all 506 races without error

### Requirement: Simulated timeline

The generator SHALL produce a numbered sequence of responses for a simulated night at a configurable step interval. Races SHALL report zero votes before their real poll close time and rise toward full reporting afterwards, never decreasing in votes or reporting from one step to the next.

#### Scenario: Before and after poll close
- **WHEN** a step is at 7:30pm Eastern
- **THEN** races whose polls close at 7pm show votes and races closing at 8pm still show zero votes and `Awaiting Poll Close`

#### Scenario: Monotonic counts
- **WHEN** consecutive steps are compared
- **THEN** no race's vote counts or reporting percentage decreases

### Requirement: Plausible and reproducible outcomes

Outcomes SHALL be drawn around each race's polling average where one exists, otherwise its Cook PVI, with random error controlled by a seed. The same seed and settings SHALL produce byte-identical responses.

#### Scenario: Seeded rerun
- **WHEN** the generator is run twice with the same seed
- **THEN** both runs write identical files

### Requirement: Race calls and edge cases

Races SHALL be called once a leader is safely ahead at sufficient reporting, and close races SHALL stay uncalled. Every generated night SHALL include at least one race that stays uncalled at full reporting, Louisiana House races as nonpartisan races that are not called with a majority winner, and ranked-choice races (Alaska, Maine) that stay uncalled below a majority.

#### Scenario: Final step
- **WHEN** the last step is generated
- **THEN** most races are called, at least one stays too close to call, and Alaska races without a majority are not called

### Requirement: Marked as test data

Every generated race SHALL carry AP's test flag set to true, so generated results can never be presented as real.

#### Scenario: Test flag
- **WHEN** any generated response is inspected
- **THEN** every race has `test` set to true

### Requirement: Serve or write responses

The generator SHALL write each step as a file the ingestor can read, and SHALL offer a mode that writes the current step to a single path on a timer so the scheduled ingestor can be exercised as on election night.

#### Scenario: Rehearsal
- **WHEN** the generator advances a step every minute into one file and the ingestor runs on that file every minute
- **THEN** the results file and board update with each step
