# Tasks

## 1. Capture and identify source snapshots

- [x] 1.1 Capture all 435 rows of Cook's six-column paginated table through the available Browser tab into `cook-pvi-2026-source.csv`; verify unique district coverage and representative 2025/2026 differences and EVEN labels against rendered rows.
- [x] 1.2 Add `source-manifest.json` with source IDs, paths, hashes, URLs/dates when known, editions, and interpretive notes; verify recorded values against saved inputs and leave unknown presidential provenance explicit without boundary approvals.
- [x] 1.3 Start `docs/district-data.md` with source acquisition, pagination checks, editions, and the documented boundary limitation; verify every source claim is supported and no compatibility gate remains.

## 2. Normalize and validate partisan history

- [x] 2.1 Implement canonical district keys and reject malformed/duplicate source keys; verify offline tests for at-large, numbered districts, leading zeroes, invalid states, and duplicate normalized labels, and document the key format.
- [x] 2.2 Implement the presidential normalizer for the two header rows and 2020/2024 column groups; verify 435 districts and 870 year records, proper separator handling, integer counts, and distinct year fields on the committed fixture.
- [x] 2.3 Add Decimal validation and 0.011 percentage-point checks; verify negative/impossible counts, invalid shares/margins, blank versus zero, rounding, and unchanged outputs on failure, and document margin signs/units.
- [x] 2.4 Implement the six-column Cook adapter selecting `2026 PVI` and preserving published labels/provenance; verify D/R/EVEN/missing/invalid labels and a differing 2025 value cannot enter the published metric, and document label semantics.
- [x] 2.5 Validate source metadata/hashes and normalized-input freshness without boundary gating; verify stale snapshots, contradictory editions, and stale normalization fail visibly while unknown map vintage does not exclude valid values, and document refresh order.

## 3. Join district and candidate context

- [x] 3.1 Implement the district context export with counts, both margins, published PVI, available/missing statuses, and source IDs; verify multi-candidate, missing-value, and source-only fixtures preserve target district coverage.
- [x] 3.2 Implement candidate enrichment through a many-to-one join preserving every original value and row; verify blank identities, incumbent/finance/filing/poll values, historical incumbent differences, and unchanged candidate outputs.
- [x] 3.3 Add deterministic issues, staged publication, and `--require-complete`; verify missing values stay blank, invalid/strict failures preserve previous outputs, and shuffled inputs reproduce outputs, and document diagnostics and strict-mode behavior.
- [x] 3.4 Complete the district-data reference with all schemas, source links, offline commands, and examples of district versus candidate analytical grain; verify links and example results against generated data.

## 4. Build and integrate the current snapshot

- [x] 4.1 Generate normalized and joined exports from saved inputs; verify 435 district rows, 1,159 candidate rows, source samples including changed PVI editions, source metadata, and the strict-completeness outcome.
- [x] 4.2 Update README and the candidate pipeline reference to link the district workflow and accurately describe available fields and source limitations; verify the documented command sequence runs offline from the repository root.
- [x] 4.3 Run existing/new offline tests, normal/strict builds, and spec validation; verify deterministic shuffled inputs, unchanged raw presidential/candidate files, and join cardinality before marking implementation complete.
