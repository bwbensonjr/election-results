# Proposal

## Why

The repository now has presidential results for 435 House districts, but its two-row CSV header and district-label conventions need normalization for a dependable join to the 2026 candidate field. Viewing and analytics need a consistent district dataset with 2020/2024 source margins and Cook's published 2026 PVI, with source definitions and limitations visible.

## What Changes

- Normalize the supplied presidential results into typed records with canonical district keys, explicit Democratic-minus-Republican margins in percentage points, and source provenance.
- Import published 2026 Cook PVI from the user-selected [district map and list](https://www.cookpolitical.com/cook-pvi/2026-partisan-voting-index/district-map-and-list), preserving its published label and a signed numeric representation. Do not estimate PVI or interpolate across maps.
- Join the supplied presidential margins and published Cook 2026 PVI by normalized district ID. Document source editions and boundary limitations without per-district approvals or withholding otherwise valid values.
- Produce one context row per 2026 House district and a separate candidate-grain enriched export, retaining existing candidate match statuses, finance, and poll-presence information without multiplying rows.
- Report missing districts, invalid values and source coverage differences. Preserve unknown metrics as blanks rather than zeroes or `EVEN`.
- Document input acquisition, schemas, signs, units, provenance, validation, and offline rebuild commands for future viewers and analytical consumers.

## Capabilities

### New Capabilities

- `district-partisan-history`: Source-preserving normalization of presidential margins and published Cook PVI, with validated district keys and source provenance.
- `house-district-context`: District-grain and candidate-grain joins of partisan history to the existing 2026 House field, with explicit coverage and data-quality status.

### Modified Capabilities

None. The existing `candidate-identity-resolution` contract remains authoritative; district enrichment does not resolve candidate identities or replace their source values.

## Impact

Adds normalization/join scripts and tests, source metadata and a Cook snapshot under `2026/results/`, derived CSVs under `2026/districts/`, and district-data documentation linked from `README.md` and the candidate pipeline reference. Existing candidate outputs and the user-added results file remain intact. The new rebuild runs offline from saved inputs; Cook acquisition uses the available integrated Browser tab to save its paginated table.

This change prepares data for viewing and analytics. It does not build a user interface, database, forecasts, poll averages, a new incumbent identity resolver, or a geographic interpolation system. Browser inspection confirmed a 435-row Datawrapper table with Dist, Incumbent, Incumbent Party, 2025 PVI, 2026 PVI, and 2026 Rank columns. Import the 2026 PVI column, not 2025 PVI; the table does not supply presidential margins.
