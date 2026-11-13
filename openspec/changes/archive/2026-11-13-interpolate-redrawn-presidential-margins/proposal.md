# Proposal

## Why

Nine states vote in 2026 on new congressional lines, so their 173 districts carry presidential status `prior_boundaries`, and the Big Board greys them out under House mode with the President metric. Six of those states (California, Florida, Louisiana, North Carolina, Texas, and Utah, 142 districts) are already drawn on their enacted 2026 shapes. Those include most of the seats that decide the House, and that is where a 2024 baseline matters most. We have the 2024 results by old district and the new district shapes, so we can estimate each new district's 2024 margin by moving votes from the old lines to the new ones.

## What Changes

- Get the 119th Congress (2024-election) district lines at census-block resolution for the redrawn states. The source is the Census Bureau's 119th Congress block assignment files, plus 2020 Census block populations and internal points from TIGER/Line `tabblock20`. Record each file in a hashed manifest, following the district-geometry pattern. The 1:20M cartographic file the board draws is too coarse for this.
- Assign each block to its new 2026 district by placing the block's internal point in the enacted plan shapes already listed in `2026/geometry/sources.json`. Commit a crosswalk giving the population each old district, county, and new district share, so later builds need no network access or geospatial libraries.
- Get 2020 and 2024 county-level presidential results (a hashed snapshot) and commit them, with 2020 Census county populations, for the crosswalk states.
- Move 2020 and 2024 presidential Democratic, Republican, and total votes from old districts to new districts. Within each old district, weight each piece's population by its county's votes per resident for that party and year, then scale so the old district's source totals are kept exactly. Then recompute shares and margins on the new lines. A first run that weighted by population alone put UT-01 at Trump +22.6 against a Cook PVI of D+12, because each old Utah district mixed part of Salt Lake County with Republican areas. County rates capture that difference.
- Add a presidential status `interpolated`. Districts in redrawn states that have a crosswalk get estimated margins with that status, plus a distinct source ID. Redrawn states with no 2026 shapes (Alabama, Ohio, and Tennessee) stay `prior_boundaries`.
- Check each state's estimates: vote totals must be conserved, and a non-failing review report compares each estimated lean with the district's published Cook 2026 PVI. The report weights the two elections the way Cook does (75 percent 2024, 25 percent 2020), so a district that swung between them is not flagged just for the swing.
- The election-night baseline carries the 2024 margin when its status is `interpolated`. The Big Board colors those districts under the President metric and labels the margin in the race detail as an estimate on the 2026 lines.

Out of scope:

- Precinct-level reaggregation. This change assumes each county's votes are spread evenly by population within the part of the county inside each old district.
- Changing the lean weighting of the existing boundary review.
- Ohio. It has a 2026 block assignment file but no 2026 shapes; adding it is a later change.
- Statewide races, which are unaffected by redistricting.

## Capabilities

### New Capabilities
- `presidential-margin-interpolation`: block sources for the old lines, county results, the old-to-new crosswalk, county-weighted vote reallocation, the conservation check, and the PVI review report for districts in redrawn states.

### Modified Capabilities
- `district-partisan-history`: the boundary status requirement adds `interpolated` for registry states that have a crosswalk.
- `house-district-context`: coverage statuses add `interpolated`, with estimated values and source ID, and strict mode counts `interpolated` as present.
- `election-night-baseline`: race rows carry the 2024 margin when its status is `available` or `interpolated`.
- `big-board`: the President metric colors `interpolated` districts, and the race detail marks the margin as estimated on 2026 lines.

## Impact

- New script `scripts/build_presidential_crosswalk.py`. It needs network access and geopandas, and caches block downloads under ignored `2026/geometry/cache/`. It comes with a source manifest, a committed crosswalk CSV, and a committed county results CSV under `2026/results/`.
- `scripts/district_history.py` and `scripts/normalize_district_history.py` apply the crosswalk using the standard library only. `scripts/build_house_district_context.py`, `scripts/build_election_baseline.py`, `scripts/build_bigboard_data.py`, and `bigboard/index.html` handle the new status.
- Regenerated outputs: `house-district-context.csv`, `house-candidate-context.csv`, the baseline, and the board data. The board gets republished to its existing artifact URL.
- Docs: `docs/district-data.md` (redrawn states and the method) and `docs/big-board.md`. New and updated tests in `tests/`.
- Downstream consumers that filter on `pres_*_status == "available"` will still exclude estimated values until they opt in to `interpolated`.
