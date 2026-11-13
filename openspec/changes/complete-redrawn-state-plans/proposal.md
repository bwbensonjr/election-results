# Proposal

## Why

The Big Board still draws Alabama, Ohio, and Tennessee on their 2024 district lines and greys out their 31 House districts under the President metric. When the shapes were built on November 3, none of the three states had a usable 2026 boundary file. The Census Bureau has since published both:

- **TIGER/Line 2026 `cd120` shapefiles** for every state. They were built September 27 and posted November 9, 2026.
- **120th Congress block equivalency files** for all nine redrawn states. The national file was regenerated October 5, 2026. The state files are dated April 21 for Ohio, June 4 for Alabama, and June 10 for Tennessee, all after each plan's adoption.

A check on November 13 confirmed that the files describe the new maps:

- **The two sources agree.** The TIGER shapes and the 2026 block file put every populated block in the same district for 100% of Alabama's and Tennessee's population and 99.998% of Ohio's.
- **The lines differ from 2024.** Relative to the 2024 lines, 13.1% of Alabama's population changed districts, 12.5% of Ohio's, and 34.7% of Tennessee's.
- **They match Cook's 2026 PVI.** Cook rates AL-02 R+7, but Harris won it by 8 on the 2024 court-drawn lines. Cook rates TN-09 R+9, but Harris won it by 43 before Memphis was split.

## What Changes

- Add geometry overrides for Alabama, Ohio, and Tennessee from the TIGER/Line 2026 `cd120` shapefiles (field `CD120FP`), with hashes in `2026/geometry/sources.json`. All nine registry states will then be drawn on their 2026 lines, and no district will keep vintage `prior_boundaries`.
- Add the three states' 2020 block files to `presidential-crosswalk-sources.json`. The crosswalk build already covers every registry state that has an override, so Alabama, Ohio, and Tennessee get interpolated margins through the existing method: block-level, weighted by county vote rates.
- New check: add the Census 120th Congress block equivalency file to the crosswalk sources. For every crosswalk state, compare each block's point-in-polygon 2026 district with the Census assignment, report agreement by population, and fail when it falls below 99.9 percent. This guards against a wrong or outdated plan file, for the six existing state-supplied plans as well as the three new ones.
- Rebuild the geometry, crosswalk, county table, normalization, context, baseline, and board data. Update the docs and test expectations: 262 `available`, 173 `interpolated`, and 0 `prior_boundaries` districts. Republish the board to its existing link.

Out of scope:

- Replacing the six state-supplied plan files with TIGER `cd120`. The new check verifies them instead.
- Removing the `prior_boundaries` handling, which stays for any state added to the registry later without a plan file.
- Changing the interpolation method or the review threshold.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `presidential-margin-interpolation`: adds the check of plan assignments against the Census 2026 block equivalency file, and updates the crosswalk-scope example that named Tennessee as a state without shapes.
- `election-night-baseline`: the redrawn-district scenario that used TN-05 as a `prior_boundaries` example now uses a hypothetical state, since every current registry state is interpolated.

## Impact

- Data: `2026/geometry/sources.json`, `us-house-2026.json`, the crosswalk sources, crosswalk, report, and county table, `source-manifest.json` hashes, interpolated results and review, district and candidate context, baseline, and `bigboard/index.html` board data.
- Code: `scripts/build_presidential_crosswalk.py` (the assignment check).
- Tests: the geometry, crosswalk, context, baseline, and board-data tests whose expectations name AL, OH, and TN as prior-line states.
- Docs: `docs/big-board.md` ("Still on 2024 lines"), `docs/district-data.md`, `docs/election-baseline.md`, and `README.md`.
- Downloads: about 850 MB more of block files and 3 MB of TIGER shapes in the ignored cache. Committed outputs grow by a few hundred crosswalk and county rows.
