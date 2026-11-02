# House district context

This workflow joins the supplied 2020/2024 presidential margins, Cook's published 2026 PVI, and a weighted polling average of each district's Democratic and Republican nominees to the existing 2026 House candidate field, using normalized district IDs. It provides one export for district analysis and another for candidate details. Districts without eligible polling keep blank polling columns.

## Sources and refresh

The user-supplied [`presidential-results-by-us-house-district-2020-2024.csv`](../2026/results/presidential-results-by-us-house-district-2020-2024.csv) has two header rows and 435 district rows. Its exact upstream URL, retrieval date, and map vintage are unknown. Both years' values are used as supplied; matching a district label does not establish that its electorate stayed the same across source editions. This limits interpretation of historical shifts, but does not block the join or withhold valid margins. The pipeline does not interpolate votes or estimate PVI.

[`cook-pvi-2026-source.csv`](../2026/results/cook-pvi-2026-source.csv) was captured on November 2, 2026 from the user's open [Cook 2026 district page](https://www.cookpolitical.com/cook-pvi/2026-partisan-voting-index/district-map-and-list), dated July 29, 2026. Its embedded [Datawrapper table](https://datawrapper.dwcdn.net/fejB0/2/) has six visible columns: `Dist`, `Incumbent`, `Incumbent Party`, `2025 PVI`, `2026 PVI`, `2026 Rank`. The normalizer imports **2026 PVI**. Presidential margins do not come from this table.

To refresh Cook data, use the integrated Browser on the linked page, open the table's show-more control, and capture all rendered rows. The initial table shows only 50 of 435; expanding "Show 385 more" displayed all rows in this capture. Preserve the six source columns and quoted CSV values. Ignore the empty layout cell, not an actual data column. Verify 435 unique district keys, coverage against the candidate field, a published EVEN value, and a changed-edition sample such as CA-13 (`2025 PVI=R+1`, `2026 PVI=D+2`). Do not infer unavailable values or capture just the first page.

[`source-manifest.json`](../2026/results/source-manifest.json) records source identifiers, repository-relative paths, hashes, source/embedded URLs, known publication and acquisition dates, editions, and notes. Unknown presidential metadata is null, not inferred from Git dates. After replacing either source snapshot, update its SHA-256 and actual provenance, normalize again, and rebuild. There is no district-boundary approval registry. Offline builds do not need browser access, credentials, or new network requests once Python is available.

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

The first command refreshes derived candidate data from its committed inputs; it does not download new FEC/ballot/poll data. The remaining commands run entirely on saved inputs without an API key. Rebuild the polling averages after any change to the candidate field or the poll snapshot. Joiner options are `--candidates`, `--manifest`, `--history`, `--pvi`, `--polls`, `--poll-averages`, `--output-dir`, and `--require-complete`; paths can select alternate candidate, metadata, normalized, poll, and output files. Source paths inside the manifest remain relative to the repository root.

## Files and schemas

| File | Grain and purpose |
| --- | --- |
| `2026/results/presidential-results-by-us-house-district-2020-2024.csv` | Original two-row-header presidential input; preserved |
| `2026/results/cook-pvi-2026-source.csv` | Captured six-column Cook table; both PVI editions preserved |
| `2026/results/source-manifest.json` | Source provenance, editions, and snapshot hashes |
| `2026/results/presidential-results-normalized.csv` | One row per source district and presidential election year |
| `2026/results/cook-pvi-normalized.csv` | One row per Cook district for published 2026 PVI |
| `2026/polls/house-poll-averages.csv` | One row per candidate-field district with its weighted nominee polling average or status |
| `2026/polls/house-poll-average-inputs.csv` | One row per poll question with its inclusion reason and weight factors |
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
| `pres_2020_status`, `pres_2024_status`, `cook_pvi_status` | `available` when the source value exists, otherwise `missing` |
| `pres_2020_source_id`, `pres_2024_source_id`, `cook_pvi_source_id` | Source attribution; configured source ID is retained even when the metric is missing |
| `poll_avg_dem_candidate` through `poll_avg_source_id` | The ten polling-average columns, copied from `house-poll-averages.csv` and described under [House polling averages](#house-polling-averages); blank unless `poll_avg_status` is `available` |

Candidate context retains all original candidate columns and exact values, appending `district_id`, `election_cycle`, and the district context's metric, status, source-ID, and polling-average columns. The polling columns come last in both exports, so earlier columns keep their positions. It does not append district candidate counts. Candidate columns and finance/filing/poll semantics are described in the [candidate pipeline reference](candidate-pipeline.md). In particular, a blank candidate FEC identity remains blank after this join. Different source incumbent names do not overwrite candidate records or establish a verified current-incumbent roster.

All generated CSVs are sorted deterministically with UTF-8 encoding and LF line endings. Candidate rows are sorted by canonical district ID and their original field values; duplicate input candidate rows remain duplicated. Repeated district metrics are deliberate in that detail export.

## Missing data and validation

Normal mode keeps every candidate-field district and every candidate row, using blank missing metrics and `missing` statuses. Zero margins and published EVEN are real values, not missing. Unknown boundary vintage does not affect availability. `district-context-issues.csv` has `state`, `district`, `district_id`, `metric`, `source_id`, `issue`, `detail`. Metrics are `pres_2020`, `pres_2024`, or `cook_pvi`.

| Issue | Meaning |
| --- | --- |
| `missing_district` | No source row for a target district/year or target PVI district |
| `missing_value` | Source row exists but the published margin or PVI label is blank |
| `source_only_district` | Source key absent from the candidate field; reported rather than added to target coverage |

`--require-complete` requires all three metrics for every target district; source-only issues alone do not fail it. It does not require polling averages, and districts without polling add no issue rows; their polling status explains the gap. Invalid schemas/values, duplicate normalized keys, stale snapshots/normalizations, or contradictory metadata fail in either mode. Validation and strict-completeness errors exit nonzero with actionable stderr diagnostics and preserve previous successful outputs. Files are staged before replacement; an operating-system interruption during replacement is not a multi-file transaction guarantee.

## House polling averages

`uv run scripts/build_house_poll_averages.py` builds a weighted Democratic-versus-Republican polling average for each district from the saved [`us-house-polls.csv`](../2026/polls/us-house-polls.csv) snapshot and the candidate field. It uses only the Python standard library, runs offline, and has the options `--polls`, `--candidates`, and `--output-dir`. Polling acquisition is still manual (see the [README](../README.md)), and no other poll file is read.

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
| `not_head_to_head` | After dropping `NONE` answers, `Generic` names, and reallocated ranked-choice rows, the question lacks exactly one Democratic and one Republican answer |
| `non_nominee` | A Democratic or Republican answer matches no field candidate, or matches someone other than that party's nominee |
| `ambiguous_match` | A name matches more than one field candidate in the district |
| `superseded` | Another question from the same poll was chosen |

Seat `1` in an at-large state (one whose only field district is `00`) maps to `STATE-AL`. Other seats are zero-padded. Names are matched against every field candidate in the district with the same surname rule, refined by first initial, that sets `in_general_polls`. Party-label questions (`Generic Democrat` against `Generic Republican`) never count. Independent and third-party answers may appear in an eligible question, but their shares are not averaged.

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
| `poll_avg_dem_candidate`, `poll_avg_rep_candidate` | Nominee names as spelled in the candidate field |
| `poll_avg_dem_pct`, `poll_avg_rep_pct` | Weighted mean shares of all respondents, including undecided; not rescaled to two-party totals |
| `poll_avg_dem_margin_pp` | Weighted mean of each poll's D-minus-R margin, in percentage points |
| `poll_count`, `poll_pollster_count` | Selected polls and distinct pollsters |
| `poll_latest_end_date` | ISO end date of the newest selected poll |
| `poll_avg_status` | `available`, `no_polls` (no 2026 general-election question for the district), `no_eligible_polls` (questions exist but none qualified), or `no_dem_rep_field` |
| `poll_avg_source_id` | `us-house-polls-2026` |

All values except status and source ID are blank unless the status is `available`. A blank is never zero.

[`house-poll-average-inputs.csv`](../2026/polls/house-poll-average-inputs.csv) has one row for every question in the snapshot, with these columns: `poll_id`, `question_id`, `state`, `district`, `district_id`, `stage`, `pollster`, `end_date`, `population`, `sample_size`, `sample_size_imputed`, `partisan`, `dem_candidate`, `rep_candidate`, `dem_pct`, `rep_pct`, `dem_margin_pp`, `included`, `reason`, `age_days`, `recency_factor`, `sample_factor`, `pollster_factor`, `partisan_factor`, and `weight`. Shares and margins are filled for every question that matched both nominees, including superseded ones. Weight factors are filled only for included questions. Rows are sorted by `district_id`, `end_date`, `poll_id`, and `question_id`. The weighted mean of an included district's `dem_margin_pp`, using `weight`, reproduces its published margin to within rounding.

### Limitations

- **Sponsored polls.** 198 of the 296 selected polls in the current snapshot have a party sponsor. They are discounted, not removed or adjusted for house effects, so a district polled mostly by one side can lean toward that side.
- **Single polls.** 40 of the 111 averaged districts rest on one poll. Read `poll_count` and `poll_pollster_count` next to the margin.
- **Strong independents.** The margin measures only the Democrat against the Republican. Where an independent is a main contender, it does not describe the race. In AK-AL, independent Bill Hill polls far ahead of Democrat Eric Hafner, so the -39.63 D-minus-R margin says little about how close the seat is. Check the input log and the source poll for those districts.
- **Same-party contests.** Districts such as California's same-party runoffs get `no_dem_rep_field` even when polled.
- **Nominee matching.** Matching uses the candidate field's current names. If the field is wrong or out of date, nominee polls are logged as `non_nominee` rather than guessed.

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
PY
```

In the November 2, 2026 snapshot, Alaska has source margins of -10.12 points (2020) and -13.14 points (2024), and published PVI R+6. CA-13 has D+2 in Cook's 2026 column; R+1 in its 2025 column is preserved only in the captured source. The 435 districts have 224 R-leaning labels, 204 D-leaning labels, and 7 EVEN labels. These are published PVI groups, not forecasts or predicted seat counts.

The polling statuses are 111 `available`, 297 `no_polls`, 25 `no_dem_rep_field`, and 2 `no_eligible_polls`. The input log has 1,680 questions; 296 were selected. ME-02 averages eight polls from five pollsters to a D+3.31 margin (Matthew G. Dunlap 50.01, Paul R. LePage 46.70), with the latest poll ending October 14, 2026. CA-13 has `no_polls`, so its polling columns are blank.

The build produces 870 presidential year rows, 435 normalized PVI rows, 435 district context rows, and 1,159 candidate context rows. All target metrics are available, the issue report has only its header, and `--require-complete` passes. Counts apply to these saved inputs; future refreshes can change candidate counts and source coverage. The existing 325 unresolved FEC identities remain unresolved in the enriched export.

Run all offline tests with:

```sh
uv run --with requests python -m unittest discover -s tests -v
```

The first `uv` invocation may acquire Python or the existing candidate tests' `requests` dependency. With the runtime/dependency cached, `uv run --offline --with requests python -m unittest discover -s tests -v` exercises both pipelines without API credentials or network calls.
