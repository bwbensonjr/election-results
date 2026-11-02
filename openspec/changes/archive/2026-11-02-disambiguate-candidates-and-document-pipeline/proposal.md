# Proposal

## Why

The combined House candidate field covers 435 districts, but matching silently selects the first FEC record when several fit: the current snapshot has 18 ambiguous ballot candidates, including conflicting incumbency and pre-general filing flags. The README also omits the implemented pipeline, making its outputs and limitations difficult to reproduce or evaluate.

## What Changes

- Replace first-match selection with conservative, deterministic identity resolution that leaves ambiguous candidates unresolved and reports all plausible FEC records.
- Add a version-controlled review process for explicit candidate mappings, alternate FEC IDs belonging to the same person, and intentionally unmatched ballot candidates, with evidence and validation.
- Preserve committee-to-candidate relationships when flagging 12G reports so multiple candidate IDs do not silently overwrite one another.
- Expose match status and review evidence alongside existing discrepancy reports; regenerate derived candidate files after reviewing the current ambiguities.
- Document prerequisites, execution order, sources, file schemas, refresh procedures, disambiguation steps, and known limitations in the README and a pipeline reference.

## Capabilities

### New Capabilities

- `candidate-identity-resolution`: Deterministic ballot-to-FEC matching, explicit reviewed mappings, ambiguity reporting, and consistent handling of alternate IDs and committee links.

### Modified Capabilities

None. There are no existing main specifications. Pipeline documentation is part of the delivery work and does not introduce a separate runtime capability.

## Impact

Changes affect `scripts/build_house_field.py`, `scripts/flag_general_candidates.py`, supporting identity-resolution code and tests, reviewed mapping data under `2026/candidates/`, derived candidate CSVs, `README.md`, and a new `docs/candidate-pipeline.md`. Existing output columns remain, with additive match-status fields; ambiguous matches will intentionally have blank FEC-derived values until resolved. No new external service is required.

Presidential results, PVI, a district incumbent roster, polling aggregation, scraper hardening, and an election-night interface are outside this change. This proposal plans implementation; it does not modify the pipeline itself.
