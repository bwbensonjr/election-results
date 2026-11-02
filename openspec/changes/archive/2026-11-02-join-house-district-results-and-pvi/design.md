# Design

## Context

See `proposal.md` for motivation. Existing Python 3.11+ scripts run with `uv`; the candidate field has 1,159 rows across 435 districts. Its state/district keys use `00` for at-large. The supplied presidential CSV has two header rows, 16 columns, 435 district rows, and no PVI column. Columns 3-8 contain 2024 votes/shares/margin; column 9 is blank; columns 10-15 contain 2020 values. All district keys match the candidate field after normalization.

The user approved joining the supplied margins and published Cook PVI directly by district ID, without boundary compatibility approvals. Source-map differences are a documented interpretive limitation, not a reason to suppress valid metrics. No PVI estimation or geographic interpolation is requested.

The integrated Browser can read [Cook's 2026 district page](https://www.cookpolitical.com/cook-pvi/2026-partisan-voting-index/district-map-and-list). It embeds a 435-row Datawrapper table, displaying 50 rows at a time, with `Dist`, `Incumbent`, `Incumbent Party`, `2025 PVI`, `2026 PVI`, and `2026 Rank`. The page is dated July 29, 2026. Examples verified in the displayed table include FL-04 R+5 in both editions and CA-13 changing from R+1 (2025) to D+2 (2026). The table supplies PVI, not presidential margins. A separate web fetch's HTTP 403 does not prevent access through the user's open tab.

## Goals / Non-Goals

**Goals:** Stable district identifiers, source-preserving numeric metrics, reproducible offline builds, district and candidate exports with explicit grain and missingness, and traceable acquisition.

**Non-Goals:** Boundary approval registries, map matching, precinct allocation, PVI estimation, candidate identity changes, poll aggregation, a database, or a viewing interface. Source incumbent labels do not replace candidate flags or create a verified incumbent roster.

## Decisions

### 1. Capture the rendered Cook table once, rebuild offline

Through the Browser plugin, read the table's rendered rows and paginate until all 435 unique districts are captured. Save `2026/results/cook-pvi-2026-source.csv` with its six original column headings and values. Verify pagination coverage, uniqueness, and sample 2025/2026 differences. Never treat the first 50 rows as the complete snapshot. Record the page URL, embedded table URL/version, publication date, actual retrieval date, and acquisition method in `2026/results/source-manifest.json`.

Use a saved six-column table as the adapter contract. This avoids coupling offline code to website scripts, browser authentication, or live network availability. Future refresh instructions describe the same browser pagination/export procedure. No browser package becomes an offline build dependency.

Alternative: live scraping during every build. Rejected because saved data is reproducible and the integrated browser already supplies access.

### 2. Validate district keys and source metadata, without boundary gates

A shared helper normalizes `AK-AL` or `AK-00` to state `AK`, district `00`, district ID `AK-AL`; `AL-1` becomes `AL,01,AL-01`. Validate state codes and district syntax; do not infer that a poll seat numbered 1 means at-large in arbitrary source data. Reject duplicate normalized keys within a source edition, even when the source strings differ.

The manifest has a schema version and configured source entries for presidential results and Cook PVI. Each records a source ID, repository-relative path, SHA-256 hash, edition, source URL and retrieval/publication dates when known, and notes describing units and source limitations. Record unknown provenance as null; the user-added file's exact upstream URL and map vintage are not yet known. Do not substitute the Git commit date for retrieval time. Reject stale hashes or contradictory editions. Hashes identify input snapshots; there is no compatibility registry, map approval state, or missing-value penalty for undocumented boundaries.

Alternative: checking compatibility for every district/year. Removed at the user's direction. A normalized-key join is the intended behavior; documentation explains that presidential shifts may reflect different source maps.

### 3. Normalize both years and the correct PVI edition

Add `scripts/district_history.py` for shared parsing, validation, metadata, and CSV publication. Add `scripts/normalize_district_history.py` as a standard-library CLI with optional `--manifest` and `--output-dir` paths for testability.

Use `csv.reader` to validate the presidential CSV's two expected header rows, separator, and 16-column rows, tolerating a BOM and surrounding whitespace. Use `Decimal`, strip comma count separators and percent signs, and preserve published decimal precision. Validate nonnegative integer counts, positive totals, `D + R <= total`, shares in 0-100, and margins in -100 to 100. Where fields are present, cross-check shares and margin against unrounded vote counts within 0.011 percentage points. Blank metrics remain unknown; malformed nonblank values fail with a source row/field. Do not reconstruct a missing published margin from other columns.

Write `2026/results/presidential-results-normalized.csv` with one row per district/year:

- `state,district,district_id,election_year`
- `dem_votes,rep_votes,total_votes,dem_share_pct,rep_share_pct,dem_margin_pp`
- `source_incumbent_label,source_party_label,source_id,source_record`

The margin is Democratic minus Republican as percentage points of all reported votes. Alaska's published `-13.14%` becomes numeric `-13.14`, not `-0.1314`. Source incumbent and party labels stay metadata.

Read Cook columns by their actual headings. `2026 PVI` is authoritative for this change. Parse `D+n` as positive lean, `R+n` as negative lean, and published `EVEN` as zero. Missing labels remain blank; invalid labels fail. This numeric value parses a published rounded label; it is not a calculated or unrounded PVI and not a presidential vote margin.

Write `2026/results/cook-pvi-normalized.csv`:

- `state,district,district_id,cook_pvi_label,cook_pvi_dem_lean_pp`
- `source_incumbent_label,source_party_label,source_id,source_record,pvi_edition`

Alternative: plain DictReader on the presidential first header, subtracting rounded shares, or using 2025 PVI. Rejected because they lose column groups, change source precision, or choose the wrong edition.

### 4. Publish district and candidate exports through validated joins

Add `scripts/build_house_district_context.py` with optional candidate, manifest, history, PVI, and output paths. The candidate field defines the district universe. Require unique normalized district/year and PVI keys, verify each normalized row's source ID/edition, and ensure normalized files reflect the current saved inputs rather than allowing a stale normalization to be labeled fresh. Recompute the expected normalized records in memory from the manifest and compare their values/order-independent keys before joining.

`2026/districts/house-district-context.csv` contains one row per target district:

- `state,district,district_id,election_cycle`
- `candidate_count,unresolved_fec_candidate_count` (unmatched, ambiguous, and reviewed-unmatched count as unresolved)
- `pres_2020_dem_margin_pp,pres_2024_dem_margin_pp,cook_pvi_label,cook_pvi_dem_lean_pp`
- `pres_2020_status,pres_2024_status,cook_pvi_status` with only `available` and `missing`
- `pres_2020_source_id,pres_2024_source_id,cook_pvi_source_id`

`2026/districts/house-candidate-context.csv` preserves original candidate columns and exact values and appends district ID, election cycle, metrics, statuses, and source IDs through a many-to-one join. Do not repeat district candidate counts there. Preserve blank identities, incumbent/filing flags, finance, and poll-presence values. Current snapshot assertions are 435 district rows and 1,159 candidate rows, not hard-coded constraints on every future input.

Alternative: enriching only the existing candidate file. Rejected because district-level aggregates would be easy to multiply by candidate count, and new source availability should not affect the established candidate pipeline.

### 5. Publish missingness explicitly and invalid data safely

Produce `2026/districts/district-context-issues.csv` with `state,district,district_id,metric,source_id,issue,detail`. Report missing district/year/PVI rows, missing metric values, and source-only district keys. Source incumbent disagreements remain available in normalized source records, without triggering candidate changes. There are no boundary-status issues.

Normal mode publishes valid partial data with blank missing fields and missing statuses. `--require-complete` requires both presidential margins and published PVI for every candidate-field district; failures print actionable diagnostics and leave previous exports intact. Malformed schemas, duplicate keys, impossible values, stale hashes/normalization, and contradictory metadata fail before publication. Stage all CSVs before replacement. Sort outputs and issues deterministically, including candidate rows by their original field values to avoid input-order dependence while retaining duplicate rows.

Alternative: inner joins or filling absent PVI with EVEN. Rejected because they conceal missing districts or fabricate observations.

### 6. Document source definitions and analytical grain

Add `docs/district-data.md` with capture steps, schemas, signs/units, editions, missingness, refresh instructions, offline commands, and small examples for district lookup, candidate-detail joins, and district counts by PVI. State that the supplied margins are joined as supplied, their map vintage is not independently verified, and the pipeline does not interpolate them. This is an interpretive limitation, not a validation gate. Link the workflow from README and the candidate pipeline reference.

Commands from the repository root:

```sh
uv run scripts/build_house_field.py
uv run scripts/normalize_district_history.py
uv run scripts/build_house_district_context.py
uv run scripts/build_house_district_context.py --require-complete
```

## Risks / Trade-offs

- Paginated capture can omit or repeat rows. Mitigation: verify all 435 unique keys, source coverage, and samples across both PVI editions before accepting the snapshot.
- Source maps may differ. Mitigation: record editions/unknown provenance and explain limits on cross-year interpretation without excluding supplied metrics.
- PVI and margin have different definitions. Mitigation: distinct columns, preserved labels, and documented denominators/signs.
- Enriched candidate rows repeat district metrics. Mitigation: a separate district export for district counts and aggregation examples.
- Stale inputs or intermediate files can produce misleading results. Mitigation: hashes, normalization comparison, validation before replacement, and an offline refresh sequence.

## Migration Plan

Capture Cook's table from the available browser tab, record provenance, normalize both sources, and build the two context exports and issue report. Verify full coverage, sample PVI edition selection, preserved candidate values, deterministic shuffled-input results, safe failures, and the actual strict-mode outcome. Update documentation and run existing/new offline tests. All files are additive; rollback removes the new scripts, metadata, normalized/context exports, and docs without changing raw presidential data or candidate identity decisions.
