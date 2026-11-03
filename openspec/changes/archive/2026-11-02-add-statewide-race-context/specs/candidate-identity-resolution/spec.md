# Spec Delta

## MODIFIED Requirements

### Requirement: Conservative automatic matching

The pipeline SHALL automatically match only one eligible FEC identity for the same office within the same state and, for House candidates, the same district, using compatible party and normalized given-name and surname evidence. Surname-only evidence SHALL require review. Multiple plausible identities SHALL remain ambiguous. Results SHALL be independent of input ordering.

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

#### Scenario: Senate candidate scoped to state and office
- **WHEN** a Senate ballot candidate shares a name with a House FEC record in the same state and with one Senate FEC record
- **THEN** only the Senate record is considered and the candidate matches it automatically

### Requirement: Reviewed identity decisions

The pipeline SHALL accept version-controlled decisions keyed by cycle, office, state, district, and ballot name, kept in a separate registry per office. House decisions without an office SHALL be treated as House. A decision SHALL specify a canonical FEC ID and any reviewed alternate IDs, or explicitly record no FEC match, with an evidence reference, rationale, reviewer, and review date. The canonical record SHALL supply incumbency and financial values without summing alternate records.

#### Scenario: Reviewed alternate IDs
- **WHEN** a valid decision identifies a canonical ID and alternate IDs for the same person
- **THEN** the output uses the canonical ID, exposes the reviewed alternates, and has a reviewed match status
- **AND** financial totals are not added across alternate IDs

#### Scenario: Explicitly unmatched candidate
- **WHEN** a reviewer records that no suitable FEC record exists with supporting evidence
- **THEN** the candidate remains in the field with a reviewed-unmatched status and blank FEC-derived values

#### Scenario: Existing House registry
- **WHEN** the House builder reads the committed House registry, whose entries have no office field
- **THEN** every decision applies to House candidates and the House outputs are unchanged

#### Scenario: Senate decision naming a House ID
- **WHEN** a Senate registry decision names an FEC ID whose record is a House candidacy
- **THEN** the statewide build rejects the decision before publishing outputs
