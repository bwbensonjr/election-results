# Spec Delta

## Purpose

Fetch election-night results for every tracked 2026 House, Senate, and governor race from the AP-backed Globe elections API, join them to the election-night baseline, and publish one normalized results file the Big Board reads, with raw responses kept for audit and replay.

## ADDED Requirements

### Requirement: Fetch from a live or recorded source

The ingestor SHALL read one national response per run, either from the live Globe endpoint for November 3, 2026 or from a local response file or directory, through the same parsing and validation path. A run SHALL make at most one request to the live endpoint.

#### Scenario: Live fetch
- **WHEN** the ingestor runs with no source option
- **THEN** it requests the national endpoint for 2026-11-03 once and processes the response

#### Scenario: Recorded or mock response
- **WHEN** the ingestor runs with a path to a saved or generated response
- **THEN** it processes that file exactly as it would a live response and makes no network request

### Requirement: Keep every raw response

Each successfully fetched response SHALL be saved unchanged under a name that includes the fetch time in UTC, before parsing. Saved responses SHALL be usable later as recorded input.

#### Scenario: Replay a night
- **WHEN** the ingestor is run in order over the saved raw responses of a night
- **THEN** it produces the same results file each run produced at the time

### Requirement: Select tracked races

The ingestor SHALL keep only races with office code `H`, `S`, or `G` from a state, and SHALL set aside the national House popular-vote row (state `US`) as a separate national summary. All other offices, ballot measures, and state legislative races SHALL be ignored.

#### Scenario: Mixed national response
- **WHEN** the response holds 862 races including state legislative seats, ballot measures, and a `US` House row
- **THEN** the results file has one entry per tracked race and a national House popular-vote summary, and nothing else

### Requirement: Join races to the baseline

Each tracked AP race SHALL be matched to exactly one baseline race on state, office code, and, for House, seat number, where an at-large seat is number `1`. The AP race ID SHALL be recorded with the match. Specials and Louisiana's nonpartisan House races SHALL match like any other race and carry their AP race type.

#### Scenario: At-large district
- **WHEN** AP reports Alaska office `H` seat `1`
- **THEN** it joins to race key `AK-AL`

#### Scenario: Ohio special Senate election
- **WHEN** AP reports Ohio office `S` with race type `Special General`
- **THEN** it joins to race key `OH-SEN` and the results entry carries race type `Special General`

### Requirement: Fail closed on join errors

A run SHALL exit nonzero without replacing the current results file when any baseline race has no AP match, two AP races match one baseline race, or an AP race of a tracked office matches no baseline race. The error SHALL name each race.

#### Scenario: Missing race
- **WHEN** a response lacks the Georgia governor race
- **THEN** the run fails naming `GA-GOV` and the previous results file is left in place

### Requirement: Join candidates within a race

Each AP candidate SHALL be matched to at most one baseline candidate in the same race by surname and party, and the AP candidate ID recorded. AP candidates with no baseline match, including write-in totals, SHALL still be reported with their votes and marked unmatched. Unmatched candidates SHALL NOT fail a run.

#### Scenario: Write-in line
- **WHEN** AP lists a `Total Write-ins` candidate in AK-AL
- **THEN** the results entry includes it with its votes and no baseline candidate link

### Requirement: Normalized results file

The results file SHALL be one JSON document with a schema version, the AP response time, the fetch time, and one entry per baseline race keyed by race key. Each entry SHALL carry the AP race ID and race type, poll close time, reporting percentages (precincts and expected vote), call status, winner if called, and candidates with votes, vote share, party, and incumbent flag.

#### Scenario: Race before poll close
- **WHEN** a race reports tabulation status `Awaiting Poll Close` and zero votes
- **THEN** its entry has zero reporting, null vote shares, no winner, and call status `Too Early to Call`

#### Scenario: Test data carried through
- **WHEN** any race in the response has AP's test flag set
- **THEN** the results file marks the whole run as test data

#### Scenario: Called race
- **WHEN** AP marks a candidate as the winner of a race
- **THEN** the entry names that candidate and party as winner and records the call status

### Requirement: Atomic and change-aware publishing

The results file SHALL be replaced atomically. A run whose results content is unchanged from the current file, apart from fetch time, SHALL report "unchanged" so the publishing step can skip a republish.

#### Scenario: No new votes
- **WHEN** two consecutive runs fetch responses with identical race data
- **THEN** the second run reports unchanged and the file's race content is identical

### Requirement: Scheduled operation

The ingestor SHALL support a repeating mode that runs every configurable interval of at least 60 seconds, logs each run's outcome, and keeps running after a failed fetch or validation, leaving the last good results file in place.

#### Scenario: Transient network failure
- **WHEN** one fetch in a repeating run times out
- **THEN** the failure is logged, the last good results file is unchanged, and the next interval runs normally
