# Tasks

## 1. Guide validator

- [x] 1.1 Create `scripts/election_guide.py` with `GUIDE_COLUMNS`, `ROLES`, `TIERS`, `WATCH_TIMES`, and `load_guide` checking columns, vocabularies, canonical unique district IDs, and field membership. Verify with fixture tests: a missing column, an unknown role, an invalid tier and watch time, a duplicate normalized ID, and a district absent from the field each fail and name the row, field, or district.
- [x] 1.2 Add the markdown district-set comparison using the `XX-n` regex and `district_key`, plus a validate-only CLI. Verify with tests: an added markdown district fails as missing from the CSV, a stray CSV row fails as absent from the guide, `AK-1`-style and zero-padded references normalize consistently, and the CLI exits nonzero with the district named.
- [x] 1.3 Implement `name_check` with `build_house_field.poll_candidates` against the field's DEM and REP rows. Verify with tests for `matched`, `mismatch` (an unknown Democratic surname), `not_named`, and a one-name row that matches.

## 2. Transcribe the guide

- [x] 2.1 Transcribe all 44 House districts from `2026/guide/election-night-guide-november-3-2026.md` into `2026/guide/election-night-guide-house.csv`, following the design's column, time, role-precedence, tier, and signal conventions. Verify that `uv run scripts/election_guide.py` passes, and that tests spot-check KY-06 (bellwether, `2018-style`, `230+`), VA-01 (wave_ladder, `2018-style`, `~235`), IN-01 (`7:00`), and FL-14/FL-25 (shared majority-check signals) against the guide wording.
- [x] 2.2 Add an "Election-night guide" section to `docs/district-data.md` covering the CSV schema, vocabularies and role precedence, transcription conventions, the district-set check and its limits, the name check, and the re-transcription step after guide edits. Verify that every documented column and value matches `election_guide.py`.

## 3. Join to district context

- [x] 3.1 Add `--guide` and `--guide-markdown` to `build_house_district_context.py`. Load and validate the guide before publishing, then append the guide columns plus `guide_name_check`, `guide_status`, and `guide_source_id` after the poll columns in both exports. Verify with context tests: a guide district and a non-guide district have the correct values and statuses, candidate rows repeat their district's guide values, earlier columns keep their positions, a markdown/CSV mismatch fails and preserves the outputs, and `--require-complete` passes with partial guide coverage and adds no issue rows.
- [x] 3.2 Update the context schema table, rebuild notes, and an analytical example (guide districts sorted by watch time with polling margin and PVI) in `docs/district-data.md`, and summarize the guide join in `README.md`. Verify that the example runs offline and its output matches the generated data.

## 4. Build and verify the current snapshot

- [x] 4.1 Rebuild the context exports from committed inputs. Verify 435 district rows and 1,159 candidate rows, 44 `in_guide` districts, the name-check counts (reviewing and documenting any `mismatch`), an unchanged issues report, and that only trailing columns changed versus HEAD.
- [x] 4.2 Run the full offline test suite, the normal and `--require-complete` builds, and `openspec validate add-house-election-guide --strict`. Verify that everything passes.

## Workflow follow-up

- Archive the change after review and confirm the `election-guide-house` and `house-district-context` main specs.
