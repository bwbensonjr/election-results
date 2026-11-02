# Tasks

## 1. Identity resolution and reviewed decisions

- [x] 1.1 Implement conservative candidate discovery and unique-match resolution in a standard-library helper, with offline tests for normalized names, party equivalents, surname-only evidence, nicknames, competing identities, and shuffled input order; verify tests run through `uv` without API credentials.
- [x] 1.2 Add the versioned JSON decision registry and validation for match/unmatched decisions, review metadata, stale keys, nonexistent IDs, duplicate keys, reused IDs, and district conflicts; verify valid decisions pass and each invalid case fails before output replacement.
- [x] 1.3 Implement canonical-record fields and reviewed alternate-ID membership, with any-member 12G evidence and no financial summation; verify fixtures with conflicting incumbency, duplicate financial totals, and a filing flag only on an alternate record.
- [x] 1.4 Start `docs/candidate-pipeline.md` with the identity statuses, registry schema, validation rules, and reviewer workflow; verify every documented field and status agrees with the implementation and sample decisions.

## 2. Committee and report attribution

- [x] 2.1 Replace one-to-one committee mappings with complete candidate-ID sets in search and fallback paths, restricting flags to input candidates; verify mocked responses link a shared committee to both IDs and remain stable under reordered API results.
- [x] 2.2 Select the latest qualifying report across all linked committees per candidate, with a deterministic report-identifier tie-breaker; verify offline tests cover multiple committees, tied dates, and unmatched committees.
- [x] 2.3 Update the flagging script's explanation and pipeline reference to describe committee attribution, filing limitations, and report-selection policy; verify the documented behavior matches tested outputs without treating a 12G flag as ballot certification.

## 3. Builder outputs and review evidence

- [x] 3.1 Integrate reviewed and automatic resolution into `build_house_field.py`, preserving ballot rows and existing columns while appending match status/reason/alternate IDs; verify unresolved values stay blank and malformed decisions leave existing output files unchanged.
- [x] 3.2 Generate deterministic `candidate-match-review.csv` with plausible records, conflict reasons, financial dates, and review evidence; verify ambiguous and no-candidate fixtures produce actionable rows and repeat builds are identical.
- [x] 3.3 Use resolved identities and reviewed aliases in FEC discrepancy checks, separate poll-name matching from FEC selection, and report ambiguous poll associations; verify alternate IDs are not falsely absent and poll presence cannot resolve an ambiguous FEC identity.
- [x] 3.4 Extend the pipeline reference with all generated columns, blank/boolean semantics, review report layout, and discrepancy meanings; verify the documented headers against generated fixture outputs.

## 4. Review the current snapshot

- [x] 4.1 Generate the review queue from committed inputs and record a disposition for each of the 18 baseline ambiguous candidates, prioritizing Menendez, Onder, Harris, and Clemmons; verify each resolution has actual evidence/reviewer metadata and each remaining ambiguity has an explicit explanation in the pipeline reference's dated review summary.
- [x] 4.2 Review the three baseline major-party unmatched candidates and any additional major-party cases exposed by conservative matching; verify each is resolved with evidence, explicitly reviewed-unmatched, or visibly retained in the unresolved queue without a guessed ID.
- [x] 4.3 Regenerate the final field, review report, and discrepancies from the registry; refresh flagged/general/review-district snapshots when FEC access is available, or record the precise unrefreshed files and reason; verify unchanged ballot inputs retain 1,159 rows and 435 districts and inspect every changed incumbent/filing assignment.

## 5. Document the existing end-to-end pipeline

- [x] 5.1 Update `README.md` with implemented versus planned features, primary output, Python 3.11+/`uv` prerequisites, API-key setup, ordered commands including `--totals`, and a link to the pipeline reference; verify command paths and local links resolve.
- [x] 5.2 Complete `docs/candidate-pipeline.md` with all four scripts, seven existing candidate CSVs, the new registry/report, relevant polling inputs, sources, schemas, financial units and dates, refresh/review procedures, and snapshot provenance; verify descriptions against actual script inputs/outputs and explicitly mark unknown retrieval details.
- [x] 5.3 Document the fixed poll cutoff and presence-only flag, manual poll acquisition, election-rule exceptions, limitations of FEC filing evidence, unresolved review dispositions, and missing presidential results/PVI/incumbent roster; verify the documentation makes no unsupported completeness or freshness claims.

## 6. Integration verification

- [x] 6.1 Run the complete offline test suite and the documented offline builder from the repository root with no API key; verify all spec scenarios, row preservation, and reproducibility under reordered FEC inputs.
- [x] 6.2 Review generated CSV diffs, registry evidence, and the dated review summary together; verify every changed identity is explained, no finance totals are doubled, no unresolved field is represented as a verified false value, and full-refresh limitations are stated accurately.
