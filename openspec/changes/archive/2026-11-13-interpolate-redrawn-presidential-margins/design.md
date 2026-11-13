# Design

## Context

- The presidential source (`presidential-results-by-us-house-district-2020-2024.csv`) gives Democratic, Republican, and total votes for each district on the 2024 (119th Congress) lines. `scripts/district_history.py` normalizes it using the standard library only. `load_boundary_vintage` marks the nine registry states as `prior_boundaries`, and `aggregate_states` sums district votes into the state presidential files.
- `scripts/build_district_geometry.py` (geopandas) already downloads and hashes the enacted 2026 plans for CA, FL, LA, NC, TX, and UT into `2026/geometry/cache/`, under the entries in `2026/geometry/sources.json` `overrides`. The only 119th Congress lines it has are the 1:20M cartographic file, which is too generalized to split blocks between districts accurately.
- Status flows from `build_house_district_context.py` (the `pres_*_status` columns) to `build_election_baseline.py`, which blanks the margin unless the status is `available`, then to `build_bigboard_data.py` and `bigboard/index.html`, which color only `available`.
- The project rule: a rebuild from committed inputs needs no network or API key. The heavy geospatial step therefore has to produce a small committed artifact.

## Goals / Non-Goals

**Goals:**
- A reproducible, hashed, block-level estimate for the 142 districts in the six states that have 2026 shapes.
- Normalization and context builds stay standard-library only and offline.

**Non-Goals:**
- Precinct-level or vote-weighted reaggregation, and turnout modelling.
- Changing the 2026 shapes or the geometry build.
- Interpolating Ohio. It has a 2026 block assignment file, but the board draws Ohio on its 2024 shapes, so an estimate would describe a shape the board does not show.

## Decisions

### 1. Old lines from Census 119th Congress block assignment files
Use the Census Bureau's 119th Congress block assignment files (BAF) for each crosswalk state. These give each 2020 block's 119th Congress district exactly. The alternative, the full-resolution TIGER `cd119` shapefile with block point-in-polygon, works too but adds a second geometric approximation. Implementation needs to confirm the exact BAF URL on the Census block-assignment-files page and record it in the manifest. If a state's file cannot be found, fall back to the full-resolution TIGER/Line `tl_2024_<fips>_cd119` shapefile and record that choice in the manifest entry.

### 2. Block population and location from TIGER/Line `tabblock20`, read without geometry
`tl_2020_<fips>_tabblock20.zip` carries `GEOID20`, `POP20`, `INTPTLAT20`, and `INTPTLON20` in its attribute table. Reading only the attributes with pyogrio (`read_geometry=False`) avoids loading millions of polygons. Total population (`POP20`) is the weight. Voting-age population would fit better, but it needs a separate PL 94-171 download, and the difference rarely moves a district's margin by more than a few tenths of a point. That is noted as a limitation. Blocks with zero population are dropped.

### 3. New lines by point-in-polygon on the board's own 2026 plan files
Place each block's internal point in the 2026 plan shapefile from the existing geometry cache and manifest entry, using `district_field` and `layer_path`, reprojected to EPSG:4269 to match the block points. Using the same plan files the board draws keeps the estimate consistent with the shape the viewer sees. Several states publish their own BAFs, but each uses a different format, and none are in the manifest today. Points outside every polygon (coastal or water slivers) go to the nearest district, and the build reports them. The build fails above 0.1% of a state's population.

### 4. New script, committed crosswalk, standard-library apply
`scripts/build_presidential_crosswalk.py` (a uv script with geopandas and pyogrio) reads `2026/results/boundary-vintage.json` and `2026/geometry/sources.json`, downloads and verifies the block files into `2026/geometry/cache/blocks/` (ignored), and writes:
- `2026/results/presidential-crosswalk-sources.json`: manifest of BAF and `tabblock20` files with URL, retrieval date, and SHA-256. The geometry plan hashes are referenced, not duplicated.
- `2026/results/presidential-crosswalk.csv`: `state, old_district_id, county_fips, new_district_id, shared_pop, old_district_pop, share` with share at 8 decimals, sorted, so output is byte-stable. The county is the first five digits of the block GEOID.
- `2026/results/presidential-county-results.csv`: `state, county_fips, election_year, dem_votes, rep_votes, total_votes, pop_2020` for every county with populated blocks in a crosswalk state (see decision 6).
- `2026/results/presidential-crosswalk-report.csv`: per-state block counts, unplaced blocks and population, and states not interpolated.

`district_history.py` gains an `interpolate_presidential(history, crosswalk, county_results)` function using the standard library and `Decimal`. `normalize_district_history.py` writes `presidential-results-interpolated.csv` (same columns as the normalized file, `source_id = presidential-interpolated-cd119-to-2026`, `source_record` naming the contributing old districts) and `presidential-interpolation-review.csv` (the PVI comparison). It reuses `BOUNDARY_REVIEW_THRESHOLD`, with Cook's year weights (decision 7). Reallocated votes are kept as decimals rounded to 2 places in the CSV, and margins are computed from unrounded sums.

The alternative was computing the interpolation inside the geospatial script and committing only margins. That was rejected because the arithmetic would then be unverifiable offline, and the context build's recompute-and-compare check could not cover it.

### 5. Status `interpolated` and a crosswalk check in the registry loader
`load_boundary_vintage` stays as it is. The context build sets status `interpolated` for registry states present in the crosswalk and `prior_boundaries` for the rest. The context joiner already recomputes normalized outputs from sources and compares them. It extends that check to the interpolated CSV and the crosswalk's hash, recorded in `source-manifest.json`, so a stale crosswalk or interpolation fails visibly. State aggregation (`aggregate_states`) keeps summing source rows. State totals do not depend on district lines, and the conservation check confirms that.

### 6. County vote rates refine the split within each old district
Population weighting alone assumes every resident of an old district votes alike. The first full run put new UT-01 (mostly Salt Lake City) at Trump +22.6 against a Cook PVI of D+12, and showed 10-point gaps in LA-02, LA-06, FL-24, FL-25, and TX-30. The refinement is a two-level dasymetric split. For year y and column k (Democratic, Republican, and other votes, meaning total minus both), each crosswalk row (old d, county c, new n) gets weight `shared_pop * V[c,y,k] / P[c]`, where V is the county's votes and P its 2020 population summed from blocks. Old district d's source votes are split across its rows in proportion to those weights, and new district n sums its rows. Because each old district's weights are normalized, old district and state totals are conserved exactly, and the county results set only the relative rates, never the totals. Splitting other votes rather than totals, and summing the three parts into the new total, guarantees that party votes never exceed a new district's total. Splitting totals separately allowed that in a fixture test.

The county source is the tonmcg `US_County_Level_Election_Results_08-24` 2020 and 2024 files on GitHub, which are compiled from news-media tallies. For the six states, their state totals agree with the district source within about 0.2 percent (NC 2020 total votes is the largest gap), which is ample for rates. The crosswalk build downloads and hashes both files (recorded in `presidential-crosswalk-sources.json`), checks that every populated county in a crosswalk state has both years, and writes the committed county table. That table's SHA-256 is recorded with the crosswalk's in `source-manifest.json`, so normalization stays offline.

Alternatives: precinct results (VEST or the Redistricting Data Hub) would be better, but they come in a different format per state and some 2024 files are incomplete. County rates fix the largest errors, which come from urban/rural splits, with one uniform national source. The rows' county key leaves room to swap in precinct-derived rates later.

### 7. Cook-weighted lean in the interpolation review
Cook's PVI averages the last two presidential elections, weighting the most recent 75 percent and the earlier one 25 percent. The interpolation review computes the implied lean the same way, `(0.75 * (m2024 - n2024) + 0.25 * (m2020 - n2020)) / 2`, so districts that swung between 2020 and 2024 (for example, Hispanic-majority districts in Texas, Florida, and California) are not flagged just for the swing. The existing boundary review keeps its equal weighting. It only detects missing registry states, its committed output is empty, and changing it is out of scope.

### 8. Board treatment
Baseline and board data carry the margin when the status is `available` or `interpolated`. The page colors both the same way, so solid fills stay comparable. The detail line reads, for example, "Trump +12.4 (est. on 2026 lines)", with a note in the detail notes. No hatching: hatching already means an uncalled lead under Results.

## Risks / Trade-offs

- [Within-county uniformity: a new district built from one side of a large county (Salt Lake, Harris, Miami-Dade) still inherits that county's average within each old district] → County rates remove the urban/rural error, but not the within-county one. The PVI review flags large remaining gaps. Docs and the board label the values as estimates. A precinct-level upgrade can replace the rates later without changing statuses.
- [County source is media-compiled, not certified] → It sets only relative rates, never totals. The build checks that every county is covered, and docs record the agreement with the district source.
- [2020 Census population vs. 2024 electorate: growth areas such as TX and FL suburbs are underweighted] → Accepted and documented. The review report surfaces the worst cases.
- [Large downloads: TX and CA block files are each about 100 MB or more] → Cached under the ignored cache directory, hashed, and downloaded once. Only the crosswalk is committed.
- [Mismatched plan CRS or district numbering, such as LA's `DISTRICT_I`] → Reuse the geometry build's per-plan settings. The every-new-district-covered check fails on a numbering mismatch.
- [Consumers filtering on `available`] → Statuses are additive. Docs call out the new value.

## Migration Plan

1. Build the crosswalk and county table with network access, review the report and PVI comparison, and commit the crosswalk files.
2. Rerun normalization, context, baseline, and board-data builds. Run the tests.
3. Republish the board to the URL in `bigboard/artifact.json`, omitting `capabilities`.

Rollback: revert the commit. Without a crosswalk, every registry state falls back to `prior_boundaries`.

## Open Questions

- Whether Cook's PVI comparison threshold (4 points) suits estimated values, or needs its own threshold after the first run shows how much the estimates and PVI differ. Changing it affects only the report, not any status.
