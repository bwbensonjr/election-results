# House district context

This workflow joins the supplied 2020/2024 presidential margins, Cook's published 2026 PVI, a weighted polling average of each district's Democratic and Republican nominees, and the House races from the election-night guide to the existing 2026 House candidate field, using normalized district IDs. It provides one export for district analysis and another for candidate details. Districts without eligible polling keep blank polling columns.

The Senate and governor races have a parallel workflow, documented in [statewide-data.md](statewide-data.md). It sums this file's district vote counts into state margins and adds Cook's state PVI.

## Sources and refresh

The user-supplied [`presidential-results-by-us-house-district-2020-2024.csv`](../2026/results/presidential-results-by-us-house-district-2020-2024.csv) has two header rows and 435 district rows. Its exact upstream URL, retrieval date, and map vintage are unknown. Both years' values are used as supplied; matching a district label does not establish that its electorate stayed the same across source editions. The pipeline does not interpolate votes or estimate PVI. The source describes the 2024 congressional map, so in states that redrew for 2026 its margins describe districts that no longer exist; see [Redrawn states](#redrawn-states).

[`cook-pvi-2026-source.csv`](../2026/results/cook-pvi-2026-source.csv) was captured on November 2, 2026 from the user's open [Cook 2026 district page](https://www.cookpolitical.com/cook-pvi/2026-partisan-voting-index/district-map-and-list), dated July 29, 2026. Its embedded [Datawrapper table](https://datawrapper.dwcdn.net/fejB0/2/) has six visible columns: `Dist`, `Incumbent`, `Incumbent Party`, `2025 PVI`, `2026 PVI`, `2026 Rank`. The normalizer imports **2026 PVI**. Presidential margins do not come from this table.

To refresh Cook data, use the integrated Browser on the linked page, open the table's show-more control, and capture all rendered rows. The initial table shows only 50 of 435; expanding "Show 385 more" displayed all rows in this capture. Preserve the six source columns and quoted CSV values. Ignore the empty layout cell, not an actual data column. Verify 435 unique district keys, coverage against the candidate field, a published EVEN value, and a changed-edition sample such as CA-13 (`2025 PVI=R+1`, `2026 PVI=D+2`). Do not infer unavailable values or capture just the first page.

[`source-manifest.json`](../2026/results/source-manifest.json) records source identifiers, repository-relative paths, hashes, source/embedded URLs, known publication and acquisition dates, editions, and notes. Unknown presidential metadata is null, not inferred from Git dates. After replacing either source snapshot, update its SHA-256 and actual provenance, normalize again, and rebuild. Its `reviewed_inputs.boundary_vintage` entry points to the reviewed registry of redrawn states described below. Offline builds do not need browser access, credentials, or new network requests once Python is available.

## Redrawn states

Nine states vote in 2026 on different congressional lines than the 2024 map the presidential source describes: Alabama, California, Florida, Louisiana, North Carolina, Ohio, Tennessee, Texas, and Utah. [`boundary-vintage.json`](../2026/results/boundary-vintage.json) lists them, each with its 2026 plan, enactment date, evidence, `reviewed_by`, and `reviewed_at`. A `not_listed` array records states that redrew but still use 2024 lines in November: Missouri, whose 2025 map is stayed pending Proposition A, and Virginia, whose 2026 map never took effect. Cook's 2026 PVI is already scored on each state's current lines.

Every listed state has its enacted 2026 plan in the [district shape manifest](big-board.md#district-shapes), so presidential margins for all 173 of their districts are estimates on the 2026 lines, with status `interpolated` and source ID `presidential-interpolated-cd119-to-2026`. See [Interpolated margins on 2026 lines](#interpolated-margins-on-2026-lines). A state added to the registry before its plan is in the manifest would keep its source margins with status `prior_boundaries` instead. Treat those as describing the old district with the same number, not the current one, and use Cook PVI. `--require-complete` treats both statuses as present. An entry with an unknown or duplicate state, no evidence, or no review metadata fails normalization and the context build without replacing outputs.

Normalization also writes [`boundary-review.csv`](../2026/results/boundary-review.csv), a non-failing check for states the registry may be missing. For each district outside a listed state, it compares the published 2026 PVI lean with the lean implied by the presidential margins: each year's margin minus the national margin summed from the same source, averaged over 2020 and 2024 and halved to put it on Cook's scale. Districts where the two differ by more than four points are listed. With an empty registry, the check flags exactly the nine listed states; with the registry, the report is empty. A new row means a state may have redrawn: confirm with a source and add it, or explain it in `not_listed`.

## Interpolated margins on 2026 lines

The presidential source reports votes by 119th Congress district (the 2024 lines). For redrawn states with an enacted 2026 plan, `scripts/build_presidential_crosswalk.py` moves those votes onto the 2026 districts:

1. **Old lines.** Each 2020 Census block's 119th Congress district comes from the Census Bureau's 119th Congress block equivalency file (`cd119.zip`, `NationalCD119.txt`; its per-state files for AL, GA, LA, NY, and NC match the national file).
2. **New lines.** Each populated block (`POP20 > 0` in TIGER/Line 2020 `tabblock20`, read without geometry) goes to the 2026 district containing its internal point, using the same plan files the board draws. A block outside every district goes to the nearest one and is counted in the report. The build fails if such blocks hold more than 0.1 percent of a state's population. None do in the current build. As an independent check, the build compares each block's district with the Census Bureau's 120th Congress block equivalency file (`cd120.zip`, `NationalCD120.txt`, regenerated October 5, 2026). It reports the agreement by population as `census_agreement_pct`, and fails below 99.9 percent. In the current build, every state agrees for at least 99.997 percent of its population. That covers the six state-supplied plans and the TIGER/Line 2026 files used for Alabama, Ohio, and Tennessee.
3. **Crosswalk.** [`presidential-crosswalk.csv`](../2026/results/presidential-crosswalk.csv) has one row per old district, county, and new district, with their shared 2020 population and its share of the old district's population.
4. **County rates.** [`presidential-county-results.csv`](../2026/results/presidential-county-results.csv) has each county's 2020 and 2024 Democratic, Republican, and total votes and its 2020 population. The votes come from the [tonmcg county results](https://github.com/tonmcg/US_County_Level_Election_Results_08-24), which are compiled from media tallies. For these six states, their state totals agree with the district source within about 0.2 percent.
5. **Reallocation.** For each year, and for Democratic, Republican, and other votes (total minus both), a crosswalk row's weight is its shared population times its county's votes per resident. Each old district's source votes are split across its rows in proportion to those weights. A new district sums its rows, and its total is the sum of the three parts. Old district and state totals are kept exactly (checked within 1 vote), so the county file sets only relative rates. Votes are published to two decimals, and shares and margins use the source definitions.

Weighting by county rates matters where an old district mixed a city with rural areas. With population weights alone, new UT-01 (mostly Salt Lake City) came out at Trump +22.6. With county rates it is Harris +7.5. Cook's 2026 PVI is D+12, because Salt Lake County itself is split between districts.

`normalize_district_history.py` applies the committed crosswalk using only the standard library, with no network access. It writes [`presidential-results-interpolated.csv`](../2026/results/presidential-results-interpolated.csv), whose `source_record` lists each contributing old district and its population share, and [`presidential-interpolation-review.csv`](../2026/results/presidential-interpolation-review.csv). The review lists interpolated districts whose implied lean differs from Cook's 2026 PVI by more than four points. It weights the two elections the way Cook does: `(0.75 * (m2024 - n2024) + 0.25 * (m2020 - n2020)) / 2`, where `n` is the national margin summed from the source. That way a district that swung between 2020 and 2024 is not flagged for the swing alone. The [boundary review](#redrawn-states) keeps equal weights. The current review lists 14 of 173 districts. The largest gaps (FL-24, LA-06, FL-25, UT-01, TX-09) are in districts carved from one part of a large county, where county rates cannot see the difference. Of the 31 Alabama, Ohio, and Tennessee districts, only TN-08 is listed, at 5.9 points. The estimates follow those states' new lines: AL-02 moves from Harris +8 on its 2024 court-drawn lines to Trump +13 (Cook R+7), and TN-09, after the Memphis split, from Harris +43 to Trump +27 (Cook R+9). Treat interpolated margins as estimates and prefer Cook PVI where they disagree.

The crosswalk, county table, and their sources are hashed. [`presidential-crosswalk-sources.json`](../2026/results/presidential-crosswalk-sources.json) records each download, and `source-manifest.json` (`reviewed_inputs.presidential_crosswalk` and `presidential_county_results`) records the committed files. The context build recomputes the interpolation and fails if the saved file is stale. To rebuild the crosswalk after a plan or source change (this needs network access and downloads about 2 GB of block files into `2026/geometry/cache/blocks/`), run:

```sh
uv run scripts/build_presidential_crosswalk.py
uv run tests/test_build_presidential_crosswalk.py
```

Then update the two hashes in `source-manifest.json` and rerun normalization. [`presidential-crosswalk-report.csv`](../2026/results/presidential-crosswalk-report.csv) gives each state's block counts and unplaced population, and lists the registry states that were not interpolated.

## District identifiers

`AK-AL` and `AK-00` normalize to state `AK`, district `00`, district ID `AK-AL`; `AL-1` and `AL-01` become `AL`, `01`, `AL-01`. State codes are validated against the 50 states. Numbered seats are not silently converted to at-large. Preserve district strings and IDs as text when importing CSVs. Duplicate normalized source keys are errors even if their original spellings differ.

## Normalization and numeric definitions

Run `uv run scripts/normalize_district_history.py` from the repository root. It uses only Python 3.11+ standard-library modules and reads the manifest's saved inputs. `--manifest` and `--output-dir` select alternate metadata and normalization output paths. Source paths in the manifest are relative to the repository root.

The presidential parser validates both header rows explicitly. It strips comma thousands separators from integer vote counts and strips `%` from decimal values, retaining published precision. `dem_margin_pp` means Democratic minus Republican as percentage points of all reported votes: `100 * (D - R) / total`. It uses the source's published margin, rather than subtracting already rounded shares. Alaska's 2024 `-13.14%` becomes numeric `-13.14`. No missing margin is reconstructed.

Counts must be nonnegative integers, totals positive when supplied, and D+R cannot exceed the total. Shares must be between 0 and 100, margins between -100 and 100. Source shares and margins are compared with unrounded counts using a 0.011 percentage-point tolerance. Blank fields remain unknown; malformed nonblank values fail with source row/field details before output replacement. A published `0.00%` is a real zero.

Cook's published `2026 PVI` label is retained as `cook_pvi_label`. `D+4` maps to `cook_pvi_dem_lean_pp=4`, `R+3` to `-3`, and published `EVEN` to `0`. Blank labels stay blank, not EVEN. Numeric lean parses the published rounded label; it is not a recalculated or unrounded PVI. PVI describes relative two-party partisanship; a presidential margin is the difference between parties as a share of all reported votes. Their signs align but their magnitudes mean different things.

## Metadata, freshness, and rebuild order

The manifest uses `schema_version=1` and a `sources` object with `presidential` and `cook_pvi` entries. Each entry has `source_id`, `path`, `sha256`, `format`, `edition`, `election_years`, `source_url`, `retrieved_at`, `published_at`, and `notes`. Cook also records `embedded_table_url` and `acquisition_method`. Source IDs must be unique, dates must be ISO calendar dates or null, paths must stay inside the repository, and hashes must match file bytes. The formats are `presidential-two-header` and `cook-pvi-six-column`; election years are `[2020, 2024]` and Cook's edition must be `2026`.

The joiner rereads saved sources and compares the expected normalized records with the intermediate CSVs. In the same way, it recomputes the polling averages from the saved poll snapshot and candidate field, and it fails with an instruction to rerun `build_house_poll_averages.py` if the saved averages differ. Changing a source and its manifest hash without normalizing again fails visibly. Changing normalized values or duplicating normalized keys also fails. Source row references use stable district/year or district/edition keys so reordering source rows does not change outputs. Diagnostic errors additionally identify raw source row numbers where applicable.

Run from the repository root after source acquisition:

```sh
uv run scripts/build_house_field.py
uv run scripts/normalize_district_history.py
uv run scripts/build_house_poll_averages.py
uv run scripts/build_house_district_context.py
uv run scripts/build_house_district_context.py --require-complete
```

The first command refreshes derived candidate data from its committed inputs; it does not download new FEC/ballot/poll data. The remaining commands run entirely on saved inputs without an API key. Rebuild the polling averages after any change to the candidate field or the poll snapshot. Joiner options are `--candidates`, `--manifest`, `--history`, `--pvi`, `--interpolated`, `--polls`, `--poll-averages`, `--matchups`, `--roster`, `--guide`, `--guide-markdown`, `--output-dir`, and `--require-complete`; paths can select alternate candidate, metadata, normalized, poll, guide, and output files. The joiner validates the guide CSV against its markdown and the candidate field before it replaces any export. Source paths inside the manifest remain relative to the repository root.

## Files and schemas

| File | Grain and purpose |
| --- | --- |
| `2026/results/presidential-results-by-us-house-district-2020-2024.csv` | Original two-row-header presidential input; preserved |
| `2026/results/cook-pvi-2026-source.csv` | Captured six-column Cook table; both PVI editions preserved |
| `2026/results/source-manifest.json` | Source provenance, editions, and snapshot hashes |
| `2026/results/boundary-vintage.json` | Reviewed registry of states voting on 2026 lines that differ from the presidential source |
| `2026/roster/incumbent-roster.json` | Reviewed incumbent for every 2026 House, Senate, and governor race |
| `2026/roster/roster-review.csv` | Seed issues for review, with who resolved each |
| `2026/results/boundary-review.csv` | Districts outside listed states whose PVI and presidential margins disagree by more than four points |
| `2026/results/presidential-results-normalized.csv` | One row per source district and presidential election year |
| `2026/results/cook-pvi-normalized.csv` | One row per Cook district for published 2026 PVI |
| `2026/polls/house-poll-averages.csv` | One row per candidate-field district with its weighted nominee polling average or status |
| `2026/polls/house-poll-average-inputs.csv` | One row per poll question with its inclusion reason and weight factors |
| `2026/guide/election-night-guide-races.csv` | One row per race named in the election-night guide (House, Senate, governor); hand-made and validated |
| `2026/districts/house-district-context.csv` | One row per district represented in the candidate field |
| `2026/districts/house-candidate-context.csv` | One row per input candidate, with district metrics appended |
| `2026/districts/district-context-issues.csv` | One row per missing metric or source-only district/year |

The normalized presidential columns are:

| Column | Meaning |
| --- | --- |
| `state`, `district`, `district_id` | Canonical identifiers |
| `election_year` | `2020` or `2024` |
| `dem_votes`, `rep_votes`, `total_votes` | Integer reported vote counts; total includes other reported votes |
| `dem_share_pct`, `rep_share_pct`, `dem_margin_pp` | Published shares and D-minus-R margin in percentage points |
| `source_incumbent_label`, `source_party_label` | Original source context, not candidate identity decisions |
| `source_id` | Manifest identifier |
| `source_record` | Stable district/year reference in that input snapshot |

The normalized Cook columns are:

| Column | Meaning |
| --- | --- |
| `state`, `district`, `district_id` | Canonical identifiers |
| `cook_pvi_label`, `cook_pvi_dem_lean_pp` | Published 2026 label and parsed signed numeric lean |
| `source_incumbent_label`, `source_party_label` | Source incumbent and party labels |
| `source_id`, `source_record` | Manifest ID and stable district/edition reference |
| `pvi_edition` | `2026` |

The district context columns are:

| Column | Meaning |
| --- | --- |
| `state`, `district`, `district_id`, `election_cycle` | Canonical district identity and `2026` target election cycle |
| `candidate_count` | Number of ballot rows in the candidate input |
| `unresolved_fec_candidate_count` | Rows with unmatched, ambiguous, or reviewed-unmatched FEC identity |
| `pres_2020_dem_margin_pp`, `pres_2024_dem_margin_pp` | Source D-minus-R margins on all-vote denominator |
| `cook_pvi_label`, `cook_pvi_dem_lean_pp` | Published Cook label and signed lean |
| `pres_2020_status`, `pres_2024_status`, `cook_pvi_status` | `available` when the source value exists, otherwise `missing`; in [redrawn states](#redrawn-states), presidential statuses are `interpolated` (estimated on 2026 lines) or `prior_boundaries` |
| `pres_2020_source_id`, `pres_2024_source_id`, `cook_pvi_source_id` | Source attribution; configured source ID is retained even when the metric is missing |
| `poll_avg_dem_candidate` through `poll_avg_source_id` | The ten polling-average columns, copied from `house-poll-averages.csv` and described under [House polling averages](#house-polling-averages); blank unless `poll_avg_status` is `available` |
| `guide_slot_et` through `guide_notes` | Seventeen columns copied unchanged from the House rows of the [election-night guide](#election-night-guide) races CSV, each prefixed with `guide_`; blank for districts the guide does not name |
| `guide_name_check` | `matched`, `mismatch`, or `not_named` for guide districts; blank otherwise |
| `guide_status` | `in_guide` or `not_in_guide` |
| `guide_source_id` | `election-night-guide-2026-11-03` |
| `poll_avg_matchup_basis` | `dem_rep` or `reviewed`, copied from `house-poll-averages.csv`; added after the guide columns so earlier columns keep their positions |
| `roster_incumbent_name`, `roster_incumbent_party` | The [incumbent roster](#incumbent-roster)'s incumbent; blank when the seat is vacant |
| `roster_vacant` | `True` when the seat has no member |
| `roster_ballot_status` | `running` or `not_running`; blank when vacant |
| `open_seat` | `True` when the incumbent is not running or the seat is vacant |
| `roster_source_id` | `incumbent-roster-2026` |

Candidate context retains all original candidate columns and exact values, appending `district_id`, `election_cycle`, and the district context's metric, status, source-ID, and polling-average columns. The polling columns, the guide columns, `poll_avg_matchup_basis`, and then the roster columns come last in both exports, so earlier columns keep their positions. The candidate export adds `roster_incumbent`, `True` only on the row of a running roster incumbent. It does not append district candidate counts. Candidate columns and finance/filing/poll semantics are described in the [candidate pipeline reference](candidate-pipeline.md). In particular, a blank candidate FEC identity remains blank after this join. Source incumbent labels in the presidential and Cook files do not overwrite candidate records; current incumbency comes from the reviewed [incumbent roster](#incumbent-roster).

All generated CSVs are sorted deterministically with UTF-8 encoding and LF line endings. Candidate rows are sorted by canonical district ID and their original field values; duplicate input candidate rows remain duplicated. Repeated district metrics are deliberate in that detail export.

## Missing data and validation

Normal mode keeps every candidate-field district and every candidate row, using blank missing metrics and `missing` statuses. Zero margins and published EVEN are real values, not missing. Redrawn states change presidential status to `interpolated` or `prior_boundaries` but add no issue rows. `district-context-issues.csv` has `state`, `district`, `district_id`, `metric`, `source_id`, `issue`, `detail`. Metrics are `pres_2020`, `pres_2024`, or `cook_pvi`.

| Issue | Meaning |
| --- | --- |
| `missing_district` | No source row for a target district/year or target PVI district |
| `missing_value` | Source row exists but the published margin or PVI label is blank |
| `source_only_district` | Source key absent from the candidate field; reported rather than added to target coverage |

`--require-complete` requires all three metrics for every target district; source-only issues alone do not fail it. It does not require polling averages or guide coverage, and districts without polling or outside the guide add no issue rows; their polling and guide statuses explain the gap. A guide CSV that fails validation stops the build in either mode. Invalid schemas/values, duplicate normalized keys, stale snapshots/normalizations, or contradictory metadata fail in either mode. Validation and strict-completeness errors exit nonzero with actionable stderr diagnostics and preserve previous successful outputs. Files are staged before replacement; an operating-system interruption during replacement is not a multi-file transaction guarantee.

## Incumbent roster

[`incumbent-roster.json`](../2026/roster/incumbent-roster.json) names the incumbent for every 2026 House, Senate, and governor race: 506 entries, one per race key (`VA-01`, `GA-SEN`, `GA-GOV`). It replaces neither candidate identities nor the FEC-derived `incumbent` flag, which stays blank for 325 unresolved House rows and for every governor. The roster answers a simpler question from better sources.

**Who counts as the incumbent.** For House races the roster follows Cook's 2026 table: the sitting member contesting the district, or, where Cook marks the district `OPEN (Name)`, the departing member. In redrawn states this can differ from whoever held the district with the same number in 2024: CA-03's incumbent is Ami Bera, who now runs there. A seat with no member is `vacant` with blank name and party, keeping `previous_party` and `previous_holder`. Senate incumbents come from the [Senate member list](https://www.senate.gov/general/contact_information/senators_cfm.xml): the Class II senator, or the Class III appointee in Ohio and Florida, which hold special elections. Governors come from the [National Governors Association list](https://www.nga.org/governors/), with party from [Wikipedia's current-governors list](https://en.wikipedia.org/wiki/List_of_current_United_States_governors). All three are saved under `2026/roster/sources/` and hashed in the manifest's `roster_sources`.

Each entry has `race_key`, `office`, `name`, `party` (`D`, `R`, or `I`), `vacant`, `evidence`, `reviewed_by`, and `reviewed_at`. An optional `ballot_status_override` (`running` or `not_running`, with `override_rationale`, and `override_candidate` for `running`) settles cases the name rule cannot.

**Ballot status** is computed by each context build, not stored. A non-vacant incumbent is `running` when they match exactly one candidate in that race's field by the surname rule refined by first initial, or by override; otherwise `not_running`. Cook's `OPEN` districts carry a `not_running` override, because a different candidate can share the departing member's surname. Alaska's Senate race has a `running` override for Dan Sullivan, since Daniel J. Sullivan Jr. is also on the ballot. `open_seat` is true when the incumbent is not running or the seat is vacant.

**Seeding and review.** `uv run scripts/build_incumbent_roster.py --reseed` regenerates the roster from the saved sources; without `--reseed`, an existing roster is left alone and only [`roster-review.csv`](../2026/roster/roster-review.csv) is rewritten. The report lists seed entries that need a decision: disagreements between Cook and the presidential source, vacancies, open-seat names to complete, special elections, and incumbents not on their race's ballot. `resolved_by` shows the reviewer of the committed entry. In the November 2, 2026 snapshot all 61 report rows are resolved. Review corrected Cook's spellings of Pettersen (CO-07) and Haridopolos (FL-08), made Aisha Wahab CA-14's incumbent after her August special-election win, and made Debbie Wasserman Schultz FL-20's incumbent, since she is on its ballot while Cook lists the old seat as vacant. GA-13 and TX-23 remain vacant per the House Clerk. CA-40 is a member-versus-member race: the roster follows Cook in naming Young Kim, and Ken Calvert is also on the ballot. All 71 Senate and governor entries were reviewed; 409 House entries remain marked as seed-only because Cook's name matched exactly one ballot candidate, or Cook marked the seat open, with nothing for a reviewer to decide. Reviews were made by an automated source review, recorded in `reviewed_by`.

The context builds validate the roster before replacing exports: a missing, duplicate, or unknown race key, a wrong office, an invalid party, missing evidence or review metadata, or an override naming a candidate not in the race's field fails the build. In the snapshot, 360 House incumbents are running and 75 districts are open seats, two of them vacant.

## House polling averages

`uv run scripts/build_house_poll_averages.py` builds a weighted Democratic-versus-Republican polling average for each district from the saved [`us-house-polls.csv`](../2026/polls/us-house-polls.csv) snapshot and the candidate field. It uses only the Python standard library, runs offline, and has the options `--polls`, `--candidates`, `--output-dir`, and `--matchups`. Polling acquisition is still manual (see the [README](../README.md)), and no other poll file is read.

### Eligibility and matching

Answer rows are grouped by `question_id`. Each question gets the first reason in this list that applies. Included questions have a blank reason.

| Reason | Meaning |
| --- | --- |
| `out_of_cycle` | `cycle` is not `2026` |
| `not_general` | `stage` is a primary, runoff, or special election |
| `nationwide` | `state` is `US` (the national generic ballot) |
| `missing_seat` | No `seat_number` |
| `unknown_district` | The seat does not map to a candidate-field district |
| `no_dem_rep_field` | The district's field lacks exactly one `DEM` and one `REP` candidate |
| `not_head_to_head` | After dropping `NONE` answers, `Generic` names, and reallocated ranked-choice rows, the question lacks exactly one Democratic and one Republican answer (not checked for a reviewed matchup) |
| `non_nominee` | A Democratic or Republican answer matches no field candidate, or matches someone other than that party's nominee; for a reviewed matchup, the question lacks exactly one answer for each principal |
| `ambiguous_match` | A name matches more than one field candidate in the district |
| `superseded` | Another question from the same poll was chosen |

Seat `1` in an at-large state (one whose only field district is `00`) maps to `STATE-AL`. Other seats are zero-padded. Names are matched against every field candidate in the district with the same surname rule, refined by first initial, that sets `in_general_polls`. Party-label questions (`Generic Democrat` against `Generic Republican`) never count. Independent and third-party answers may appear in an eligible question, but their shares are not averaged.

### Reviewed principal matchups

By default a district's matchup is its single Democratic and single Republican nominee (basis `dem_rep`). [`house-principal-matchups.json`](../2026/polls/house-principal-matchups.json) can name a different pair, with the same shape as the [statewide matchups](statewide-data.md): `schema_version: 1` and a `matchups` array whose entries have `district_id`, `principal_candidate` (the non-Republican principal, as spelled in the field), optional `republican_candidate` (required when the field has several Republicans), `evidence`, `rationale`, `reviewed_by`, and `reviewed_at`. A reviewed district has basis `reviewed`. Its questions count when exactly one answer matches each principal by name; the poll's party code is not compared, because polls often code independents inconsistently. An entry for a district or candidate not in the field, a duplicate district, or missing evidence or review metadata fails the build without replacing outputs.

The November 3, 2026 snapshot has one entry. AK-AL's only Democrat, Eric Hafner, polls near 5%, while independent Bill Hill polls about 40% against Republican Nick Begich. With the entry, AK-AL averages 12 polls from 9 pollsters: Hill 40.62, Begich 45.96, margin -5.33. Without it, the average was Hafner against Begich at -39.95.

Each poll contributes at most one question. Likely voters are preferred over registered voters, and registered voters over adults. Ties go to the question naming the most field candidates, then to the lowest `question_id`. Ranked-choice questions use first-choice answers only. `pct`, `sample_size`, and `end_date` are parsed strictly only for questions that pass the head-to-head and matching checks. A malformed value there fails the build and names the question. Malformed values in out-of-scope questions do not.

### Weights

Each selected poll's weight is `recency × sample × pollster × partisan`. The constants are defined at the top of the script:

| Factor | Formula | Rationale |
| --- | --- | --- |
| recency | `0.5 ** (age_days / HALF_LIFE_DAYS)`, `HALF_LIFE_DAYS = 21`; `age_days` counts back from the district's latest selected poll | Newer polls count more. Anchoring to the district's latest poll rather than today keeps rebuilds stable over time; staleness shows in `poll_latest_end_date` |
| sample | `sqrt(min(n, SAMPLE_CAP) / SAMPLE_REFERENCE)`, `SAMPLE_CAP = 1500`, `SAMPLE_REFERENCE = 600`; a blank `n` uses `SAMPLE_DEFAULT = 600` and is flagged | Sampling error shrinks with the square root of `n`; the cap stops large online panels from dominating |
| pollster | `1 / sqrt(k)`, where `k` is that pollster's selected polls in the district | Stops one firm's repeated polls from swamping a district |
| partisan | `PARTISAN_FACTOR = 0.5` when `partisan` (sponsor party) is nonblank, otherwise `1` | Discounts campaign and party-committee polls without discarding them |

The snapshot has no pollster ratings (`numeric_grade` and `pollscore` are empty), so pollster quality is not weighted. There is no house-effect correction and no date cutoff.

### Outputs

[`house-poll-averages.csv`](../2026/polls/house-poll-averages.csv) has one row per candidate-field district:

| Column | Meaning |
| --- | --- |
| `state`, `district`, `district_id` | Canonical district identity |
| `poll_avg_dem_candidate`, `poll_avg_rep_candidate` | Principal names as spelled in the candidate field. The `dem` columns hold the non-Republican principal, who is an independent when the basis is `reviewed` |
| `poll_avg_dem_pct`, `poll_avg_rep_pct` | Weighted mean shares of all respondents, including undecided; not rescaled to two-party totals |
| `poll_avg_dem_margin_pp` | Weighted mean of each poll's non-Republican-principal-minus-Republican margin, in percentage points |
| `poll_count`, `poll_pollster_count` | Selected polls and distinct pollsters |
| `poll_latest_end_date` | ISO end date of the newest selected poll |
| `poll_avg_status` | `available`, `no_polls` (no 2026 general-election question for the district), `no_eligible_polls` (questions exist but none qualified), or `no_dem_rep_field` |
| `poll_avg_source_id` | `us-house-polls-2026` |
| `poll_avg_matchup_basis` | `dem_rep` or `reviewed`; appended last so earlier columns keep their positions |

All values except status and source ID are blank unless the status is `available`. A blank is never zero.

[`house-poll-average-inputs.csv`](../2026/polls/house-poll-average-inputs.csv) has one row for every question in the snapshot, with these columns: `poll_id`, `question_id`, `state`, `district`, `district_id`, `stage`, `pollster`, `end_date`, `population`, `sample_size`, `sample_size_imputed`, `partisan`, `dem_candidate`, `rep_candidate`, `dem_pct`, `rep_pct`, `dem_margin_pp`, `included`, `reason`, `age_days`, `recency_factor`, `sample_factor`, `pollster_factor`, `partisan_factor`, and `weight`. Shares and margins are filled for every question that matched both nominees, including superseded ones. Weight factors are filled only for included questions. Rows are sorted by `district_id`, `end_date`, `poll_id`, and `question_id`. The weighted mean of an included district's `dem_margin_pp`, using `weight`, reproduces its published margin to within rounding.

### Limitations

- **Sponsored polls.** 203 of the 302 selected polls in the current snapshot have a party sponsor. They are discounted, not removed or adjusted for house effects, so a district polled mostly by one side can lean toward that side.
- **Single polls.** 40 of the 111 averaged districts rest on one poll. Read `poll_count` and `poll_pollster_count` next to the margin.
- **Strong independents.** Without a reviewed matchup the margin measures only the Democrat against the Republican, which does not describe a race where an independent is the main contender. AK-AL has a reviewed entry; add one for any other such district, and check the input log and source poll when a margin looks lopsided.
- **Same-party contests.** Districts such as California's same-party runoffs get `no_dem_rep_field` even when polled.
- **Nominee matching.** Matching uses the candidate field's current names. If the field is wrong or out of date, nominee polls are logged as `non_nominee` rather than guessed.

## Election-night guide

[`election-night-guide-races.csv`](../2026/guide/election-night-guide-races.csv) is a hand-made CSV of the races in [`election-night-guide-november-3-2026.md`](../2026/guide/election-night-guide-november-3-2026.md) (current as of November 1, 2026). It has one row per race: 44 House districts, 14 Senate races, and 4 governor races. Only the House rows join to the district data. Validate the CSV after any edit with:

```sh
uv run scripts/election_guide.py
```

The validator uses only the standard library, writes nothing, and has the options `--guide`, `--markdown`, and `--candidates`.

### Schema

| Column | Content |
| --- | --- |
| `slot_et` | The guide's watch slot: `6:00`, `7:00`, `7:30`, `8:00`, `9:00`, `10 to 11`, or `12:00+` |
| `poll_close_et` | The race's own poll close in 24-hour ET, e.g. `19:00` for IN-1 inside the 6:00 slot; `24:00` is midnight |
| `state`, `office` | Postal code; `House`, `Senate`, or `Governor` |
| `district` | Two-digit district for House rows (`00` at large); blank for other offices |
| `card` | The guide card the race appears on, e.g. `Florida · the fast-count state` |
| `incumbent`, `incumbent_party` | Incumbent surname and `D`, `R`, or `I`, else blank |
| `open_seat` | `True`, `False`, or blank |
| `dem_candidate`, `rep_candidate`, `other_candidate` | Names as the guide writes them |
| `rating` | Rating text cited, e.g. `Cook Lean D` or `Luria favored` |
| `silver_avg_dem_margin` | Silver Bulletin polling margin cited for Senate races, else blank |
| `trump_2024_margin` | Trump's 2024 margin in points as the guide cites it, positive for Trump |
| `senate_path` | The race's place on the Senate path; blank for House rows |
| `ladder_tier` | `We'll take it`, `Solid`, `2018-style`, `Holy shit`, or blank |
| `hell_yes`, `ffs`, `chill` | The guide's signal text for the race |
| `notes` | Other race-specific context |

### Join to the House data

Each House row joins by `state` and `district` to the district context. Every column except `state`, `office`, `district`, and `senate_path` is appended with a `guide_` prefix (for example `guide_slot_et` and `guide_dem_candidate`), followed by `guide_name_check`, `guide_status`, and `guide_source_id`. Senate and governor rows are validated but not joined.

### Checks and their limits

`load_guide` checks:

- exact columns
- the allowed offices, states, slots, poll-close times, tiers, parties, and `open_seat` values, and that the two margin columns are numeric or blank
- that `district` is set on House rows and only on House rows, and is the canonical two-digit form
- unique House districts, each in the candidate field
- that the House districts are exactly the districts referenced in the markdown, as `XX-n`, normalized with at-large states mapped to `STATE-AL`

Adding or removing a district reference in the markdown therefore fails validation until the CSV matches. Rewording a race that is already listed is not detected, and Senate and governor rows are not compared with the markdown. After editing the guide, update the affected rows, then rerun the validator and the context build.

`guide_name_check` is computed at join time. Each nonblank `dem_candidate` and `rep_candidate` is matched against the district's same-party field candidates using the surname rule (refined by first initial) that `in_general_polls` uses. The result is `matched` when every name hits exactly once, `mismatch` otherwise, and `not_named` when the guide names nobody. In the current snapshot, 37 guide districts are `matched`, 7 are `not_named`, and none are `mismatch`.

## Examples and current snapshot

Use the district export for district counts, filtering to available values. Use the candidate export for individual candidate details. This example reads Alaska's metrics, lists its enriched candidates, and counts districts by published PVI party without multiplying counts by candidate count:

```sh
uv run python - <<'PY'
import csv
from collections import Counter
from pathlib import Path

base = Path("2026/districts")
with (base / "house-district-context.csv").open(newline="") as stream:
    districts = list(csv.DictReader(stream))
with (base / "house-candidate-context.csv").open(newline="") as stream:
    candidates = list(csv.DictReader(stream))

alaska = next(row for row in districts if row["district_id"] == "AK-AL")
print({key: alaska[key] for key in [
    "pres_2020_dem_margin_pp", "pres_2024_dem_margin_pp", "cook_pvi_label"
]})
print([row["name"] for row in candidates if row["district_id"] == "AK-AL"])
print(Counter(
    "EVEN" if row["cook_pvi_label"] == "EVEN" else row["cook_pvi_label"][0]
    for row in districts if row["cook_pvi_status"] == "available"
))
print(Counter(row["poll_avg_status"] for row in districts))
polled = [row for row in districts if row["poll_avg_status"] == "available"]
for row in sorted(polled, key=lambda r: abs(float(r["poll_avg_dem_margin_pp"])))[:3]:
    print(row["district_id"], row["poll_avg_dem_margin_pp"], row["poll_count"],
          row["cook_pvi_label"], row["pres_2024_dem_margin_pp"])
watch = [row for row in districts if row["guide_status"] == "in_guide"]
for row in sorted(watch, key=lambda r: (r["guide_poll_close_et"], r["district_id"]))[:4]:
    print(row["guide_poll_close_et"], row["district_id"], row["guide_ladder_tier"] or "no tier",
          row["poll_avg_dem_margin_pp"] or "no poll avg", row["cook_pvi_label"])
PY
```

In the November 2, 2026 snapshot, Alaska has source margins of -10.12 points (2020) and -13.14 points (2024), and published PVI R+6. CA-13 has D+2 in Cook's 2026 column; R+1 in its 2025 column is preserved only in the captured source. The 435 districts have 224 R-leaning labels, 204 D-leaning labels, and 7 EVEN labels. These are published PVI groups, not forecasts or predicted seat counts.

The polling statuses are 111 `available`, 297 `no_polls`, 25 `no_dem_rep_field`, and 2 `no_eligible_polls`. The input log has 1,699 questions; 312 were selected. ME-02 averages nine polls from five pollsters to an R+1.35 margin (Matthew G. Dunlap 48.32, Paul R. LePage 49.67), with the latest poll ending October 31, 2026. CA-13 has `no_polls`, so its polling columns are blank.

44 districts are `in_guide` and 391 are `not_in_guide`. Sorted by poll close and district ID, the example's first guide races close at 18:00 ET: IN-05 (Holy shit tier, poll average -2.41, R+8) and KY-06 (2018-style, 6.19, R+7). They are followed at 19:00 ET by FL-09 (no tier, 0.00, R+8) and FL-14 (Solid, 5.21, R+4).

The build produces 870 presidential year rows, 435 normalized PVI rows, 435 district context rows, and 1,160 candidate context rows. Every target metric has a value: PVI is `available` everywhere, and presidential margins are `available` for 262 districts and `interpolated` for the 173 in the nine redrawn states. No district has `prior_boundaries`. The issue report and the boundary review have only their headers, and `--require-complete` passes. Counts apply to these saved inputs; future refreshes can change candidate counts and source coverage. The existing 325 unresolved FEC identities remain unresolved in the enriched export.

Run all offline tests with:

```sh
uv run --with requests python -m unittest discover -s tests -v
```

The first `uv` invocation may acquire Python or the existing candidate tests' `requests` dependency. With the runtime/dependency cached, `uv run --offline --with requests python -m unittest discover -s tests -v` exercises both pipelines without API credentials or network calls.
