# candidate-identity-resolution Specification

## Purpose

Resolve ballot candidates to FEC identities reproducibly while exposing uncertainty and preserving evidence for human-reviewed decisions.

## Requirements

### Requirement: Conservative automatic matching

The pipeline SHALL automatically match only one eligible FEC identity within the same state and district using compatible party and normalized given-name and surname evidence. Surname-only evidence SHALL require review. Multiple plausible identities SHALL remain ambiguous. Results SHALL be independent of input ordering.

#### Scenario: Unique compatible identity
- **WHEN** exactly one record has compatible party, given name, and surname after normalization
- **THEN** the candidate receives that FEC ID and an automatic match status

#### Scenario: Multiple plausible IDs
- **WHEN** two FEC records plausibly match a ballot candidate and no reviewed mapping applies
- **THEN** the candidate remains ambiguous and neither record is selected
- **AND** reversing the FEC input order produces the same outcome

#### Scenario: Weak or conflicting evidence
- **WHEN** only a surname overlaps or the apparent match has a conflicting party
- **THEN** the pipeline requires review rather than automatically attaching that record

### Requirement: Reviewed identity decisions

The pipeline SHALL accept version-controlled decisions keyed by cycle, state, district, and ballot name. A decision SHALL specify a canonical FEC ID and any reviewed alternate IDs, or explicitly record no FEC match. Each decision SHALL include an evidence reference, rationale, reviewer, and review date. The canonical record SHALL supply incumbency and financial values without summing alternate records.

#### Scenario: Reviewed alternate IDs
- **WHEN** a valid decision identifies a canonical ID and alternate IDs for the same person
- **THEN** the output uses the canonical ID, exposes the reviewed alternates, and has a reviewed match status
- **AND** financial totals are not added across alternate IDs

#### Scenario: Explicitly unmatched candidate
- **WHEN** a reviewer records that no suitable FEC record exists with supporting evidence
- **THEN** the candidate remains in the field with a reviewed-unmatched status and blank FEC-derived values

### Requirement: Invalid decisions fail visibly

The pipeline SHALL reject duplicate decision keys, nonexistent IDs, IDs reused across different ballot identities, decisions for absent ballot rows, missing review metadata, and state or district conflicts. Rejection SHALL exit nonzero before replacing derived output files and identify the offending decision.

#### Scenario: Stale decision after a refresh
- **WHEN** a decision references an ID or ballot row absent from the refreshed inputs
- **THEN** the run fails with an actionable validation error and preserves previous outputs

#### Scenario: Conflicting decisions
- **WHEN** two different ballot candidates claim the same canonical or alternate FEC ID
- **THEN** the pipeline rejects the decisions before publishing outputs

### Requirement: Visible match status and review queue

The combined field SHALL retain all ballot rows and existing columns and add match status, reason, and alternate-ID fields. Unresolved rows SHALL leave FEC-derived values blank. A deterministic review report SHALL list unmatched and ambiguous cases with their plausible records, identifying fields, incumbency, filing flags, financial coverage dates, and conflict reasons.

#### Scenario: Unresolved identity
- **WHEN** a candidate has no accepted match
- **THEN** its identity and source URL remain in the field with an unmatched or ambiguous status
- **AND** a review report describes the candidate and any plausible FEC records
- **AND** missing incumbency and filing values are blank rather than false

#### Scenario: Reviewed alias in discrepancy checks
- **WHEN** a 12G-filing FEC ID is a reviewed alternate for a ballot candidate
- **THEN** it is recognized as belonging to that ballot identity and is not reported as absent from the ballot

### Requirement: Committee relationships preserve multiple identities

The 12G flagging process SHALL retain every candidate link for a committee rather than overwrite links. A qualifying report SHALL flag every linked candidate ID present in the input dataset. Multiple qualifying reports for one candidate SHALL resolve by latest receipt date with a deterministic report-identifier tie-breaker.

#### Scenario: Shared committee
- **WHEN** two candidate IDs in the input are linked to a committee with a qualifying 12G report
- **THEN** both candidate records receive the filing flag regardless of API ordering

#### Scenario: Multiple reports
- **WHEN** multiple linked committees have qualifying reports for a candidate
- **THEN** the latest report supplies pre-general values and ties resolve consistently

### Requirement: Reviewed filing evidence across alternate IDs

For a reviewed identity with alternate IDs, the final filed_12g value SHALL reflect whether any member ID filed a qualifying report. Incumbency and finance values SHALL still come from the canonical record. The output reason SHALL identify the canonical selection and alternate-ID evidence.

#### Scenario: Filing appears on an alternate ID
- **WHEN** the canonical record has no 12G flag but a reviewed alternate does
- **THEN** the combined candidate has filed_12g set to true and retains canonical incumbency and finance values
- **AND** the decision is traceable through the reviewed mapping and output explanation

### Requirement: Poll evidence does not resolve FEC identity

The pipeline SHALL keep poll-name matching separate from FEC identity selection. A poll appearance SHALL NOT select a canonical FEC record or resolve multiple FEC IDs. Poll-name ambiguities SHALL be reported instead of resolved by input order.

#### Scenario: Poll presence with ambiguous FEC identity
- **WHEN** a ballot candidate appears in a qualifying poll but has multiple plausible FEC IDs
- **THEN** the poll-presence flag can be true while the FEC match remains ambiguous
