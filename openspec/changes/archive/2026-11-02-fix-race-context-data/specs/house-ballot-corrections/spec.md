# Spec Delta

## Purpose

Fix House ballot-source rows that the source publishes incorrectly, such as several candidates in one row, through reviewed corrections applied at build time so the saved source stays unchanged.

## ADDED Requirements

### Requirement: Reviewed row corrections

A committed corrections file SHALL hold reviewed replacements for House ballot-source rows. Each correction SHALL identify one source row by district and exact source name, and give the replacement candidate rows with name and ballot party, plus evidence, reviewer, and review date. The saved ballot-source file SHALL NOT be edited.

#### Scenario: Merged Alaska row
- **WHEN** the ballot source has one AK-AL row named "Bill Hill, James C. "Jim" McDermott" with party Libertarian, and a correction replaces it with Bill Hill (independent) and James C. "Jim" McDermott (Libertarian)
- **THEN** the House field has two AK-AL rows for them in place of the merged row, and the source file is unchanged

### Requirement: Corrected rows go through normal matching

Replacement rows SHALL be processed like source rows: FEC matching, filing flags, finance, and poll presence apply to each. Each replacement row SHALL carry a marker that it came from a reviewed correction.

#### Scenario: Corrected candidate appears in polls
- **WHEN** corrected row Bill Hill is named in AK-AL general-election polls
- **THEN** his `in_general_polls` value is true and his row is marked as corrected

### Requirement: Stale corrections fail

The House field build SHALL exit nonzero without replacing outputs when a correction matches no source row or more than one, or lacks evidence, reviewer, or date.

#### Scenario: Source fixed upstream
- **WHEN** a refreshed ballot source no longer has the merged AK-AL row
- **THEN** the build exits nonzero naming the stale correction
