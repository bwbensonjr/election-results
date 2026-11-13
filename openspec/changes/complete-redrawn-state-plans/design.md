# Design

## Context

- `scripts/build_district_geometry.py` replaces a registry state's 119th Congress districts with any plan listed under `overrides` in `2026/geometry/sources.json`. It clips each plan to the Census state outline, so water areas and coastlines match the base file. Alabama, Ohio, and Tennessee have no override, so they are drawn with vintage `prior_boundaries`. The board shows their districts dashed and grey under President.
- `scripts/build_presidential_crosswalk.py` builds a crosswalk for `registry ∩ overrides`, so it picks up a new override with no code change. It needs only that state's `tabblock20` entry in `presidential-crosswalk-sources.json`.
- The current outputs are 262 `available`, 142 `interpolated`, and 31 `prior_boundaries` districts. `us-house-2026.json` is 184 KB, against a 400 KB limit.

## Goals / Non-Goals

**Goals:**
- Use official 2026 lines for all nine redrawn states, with no ad hoc digitizing.
- Independently verify every plan file, including the six existing ones, against the Census Bureau's own 2026 block assignment.

**Non-Goals:**
- A single source for all nine states (see decision 1).
- Changes to the board page code. It already handles `plan_2026` and `interpolated`.

## Decisions

### 1. TIGER/Line 2026 `cd120` for the three missing states
For Alabama, Ohio, and Tennessee, use `https://www2.census.gov/geo/tiger/TIGER2026/CD/tl_2026_<fips>_cd120.zip` with `district_field: CD120FP`. These files are full resolution and their district numbers match the race keys.

Alternatives:
- **Ohio Secretary of State shapefile.** It is official, but only for Ohio, and it would add a second file layout.
- **Alabama's legal-description PDF.** It would have to be parsed into blocks.
- **Tennessee.** No shapefile turned up on the General Assembly site.

TIGER is one uniform, official source, and the November 13 check showed its shapes agree with the Census 2026 block file for 99.998–100 percent of each state's population. The six existing overrides keep their state-supplied files. Switching them is unnecessary churn, and decision 2 verifies them.

### 2. Point-in-polygon stays; the Census 2026 block file becomes a check
The crosswalk keeps placing block internal points in the override shapes. That way the estimate and the drawn shape always describe the same plan. The Census 120th Congress block equivalency file is used as an independent check, not as the assignment:

- **Source.** `cd120.zip`, member `NationalCD120.txt`, with columns `GEOID,STATEFP,COUNTYFP,TRACTCE,BLOCKCE,CDFP`. Its national file was regenerated on October 5, 2026, after every state file.
- **Comparison.** The build reads `CDFP` for the crosswalk states only and computes, per state, the share of population whose point-in-polygon district equals the Census district.
- **Report.** The result goes in a new `census_agreement_pct` column of the crosswalk report.
- **Threshold.** Below 99.9 percent, the build fails naming the state. Small disagreements can come from internal points that lie near a boundary on a different block vintage, and the Ohio check shows those amount to thousandths of a percent. A wrong plan moves 10 percent or more.

`read_bef` today expects exactly `GEOID,CDFP`. It will select those two columns by name, so both file layouts work.

The alternative was assigning 2026 districts from the block file. That would be exact for the crosswalk, but it could silently disagree with the drawn shapes. The check catches the same problem without that risk.

### 3. Rebuild order
1. Geometry.
2. Crosswalk and county table.
3. Update the `source-manifest.json` hashes.
4. Normalization.
5. Context.
6. Baseline.
7. Board data.
8. Republish.

The county table gains the 67 Alabama, 88 Ohio, and 95 Tennessee counties from the county files already hashed. The geometry size must stay under 400 KB. With the same simplification tolerance, three full-resolution states should add tens of kilobytes.

## Risks / Trade-offs

- [A state-supplied plan file disagrees with the Census assignment above the threshold, for example because of a different block vintage] → The build fails and names the state. Implementation pauses to investigate rather than lowering the threshold silently.
- [TIGER 2026 lags a late plan change (Alabama's plan was restored on June 2)] → The shapefiles were built on September 27, after the last plan change, and the check against the October 5 national block file confirms each state.
- [Interpolation quality in the new states: Tennessee's Memphis split puts parts of Shelby County in three districts] → The existing PVI review report covers them. Docs list the largest gaps after the rebuild.
- [Large downloads, about 850 MB more] → Cached in the ignored folder and hashed.

## Migration Plan

Rebuild in the order above with network access for the first run, run the full test suite, commit, and republish the board to its existing URL with `capabilities` omitted. Rollback: revert the commit and republish, and the three states return to `prior_boundaries`.
