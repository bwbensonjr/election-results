# Senate and governor context

This workflow gives each 2026 Senate and governor race the same context the [House district workflow](district-data.md) gives each district: 2020 and 2024 presidential margins, Cook PVI, a weighted polling average of the race's principal matchup, and the election-night guide's columns. It joins them to the [statewide candidate field](candidate-pipeline.md#senate-and-governor-field). A race is a state and an office, identified as `STATE-SEN` or `STATE-GOV`; there are 35 Senate and 36 governor races.

## State partisan history

### Presidential margins

State margins are computed, not imported. For each state and year, the normalizer sums the Democratic, Republican, and total votes of the state's districts in the [district presidential file](../2026/results/presidential-results-by-us-house-district-2020-2024.csv). It then recomputes shares and the margin from the sums:

- `dem_share_pct = 100 * D / total`
- `dem_margin_pp = 100 * (D - R) / total`

Values are rounded half up to two decimals. Averaging district margins would weight small and large districts equally, so the sums are used instead. Districts partition their state, so the sums are statewide totals whatever map the district file describes. Spot checks against certified results agree to within 0.03 points, for example Georgia `0.24` (2020) and `-2.19` (2024), and Pennsylvania `1.19` and `-1.71`.

A state gets a value for a year only when every one of its districts in the House candidate field has all three counts. Otherwise the state row's `status` is `missing`, its values are blank, and `missing_districts` lists the district codes. A partial sum is never published. In the committed snapshot all 50 states are `available` for both years.

### Cook state PVI

Cook's 2026 PVI update re-scored only the House districts in the ten states that redrew their maps for 2026; Cook published no 2026 state list. The latest state edition is therefore the **2025 Cook PVI State Map and List** (published March 6, 2025). It is computed from the same 2020 and 2024 presidential elections, and state scores do not change with redistricting.

Cook's state list is subscriber-only. [`cook-state-pvi-2025-source.csv`](../2026/results/cook-state-pvi-2025-source.csv) was transcribed on November 2, 2026 from the "By state" table of [Wikipedia's Cook Partisan Voting Index article](https://en.wikipedia.org/w/index.php?title=Cook_Partisan_Voting_Index&oldid=1374239063) (revision 1374239063), which cites that Cook page. It keeps two columns, `State` and `PVI`, for the 50 states and Washington, D.C. This is a secondary transcription; replace it with a Cook copy, and update its manifest entry, if one becomes available. If Cook publishes a later state edition, capture it and change the manifest's edition along with the snapshot.

The normalizer maps state names to postal codes (`Washington, D.C.` is `DC`) and parses labels exactly as it does for districts: `D+4` is `4`, `R+3` is `-3`, and `EVEN` is `0`. Unknown state names, duplicate states, and malformed labels fail. It never estimates state PVI from district PVI.

### Manifest and normalization

The manifest's optional `cook_state_pvi` source has format `cook-state-pvi-two-column` and edition `2025`, and adds `upstream_url` (the Cook page) and `acquisition_method` to the usual fields. When it is present, `uv run scripts/normalize_district_history.py` also writes the two state files below. `--candidates` selects the House field whose districts define each state's district set, and `--districts-only` skips the state files. All sources are validated before any file is replaced, so a bad state snapshot also leaves the district outputs untouched. The district outputs themselves are unchanged by the state step.

`2026/results/state-presidential-normalized.csv` has one row per state and election year:

| Column | Meaning |
| --- | --- |
| `state`, `election_year` | Postal code and `2020` or `2024` |
| `dem_votes`, `rep_votes`, `total_votes` | Summed district counts; blank when `missing` |
| `dem_share_pct`, `rep_share_pct`, `dem_margin_pp` | Recomputed from the sums, in percent and percentage points |
| `district_count` | Districts the House field lists for the state |
| `status`, `missing_districts` | `available` or `missing`, and the districts lacking counts |
| `source_id`, `source_record` | District source ID and a stable `State=..;year=..;summed districts` key |

`2026/results/cook-state-pvi-normalized.csv` has one row per state (and DC): `state`, `cook_pvi_label`, `cook_pvi_dem_lean_pp`, `source_id`, `source_record`, and `pvi_edition` (`2025`).

## Statewide polling averages

`uv run scripts/build_statewide_poll_averages.py` averages each race's principal matchup from the saved Senate (`us-senate-polls.csv`) and governor (`governor-polls.csv`) snapshots. It uses the [House method](district-data.md#house-polling-averages) and calls the same code for one question per poll (likely voters, then registered voters, then adults; then the most matched candidates; then the lowest question ID), first-round non-reallocated ranked-choice answers, and the recency, sample, pollster, and partisan weights with their constants. A statewide poll and a House poll with the same inputs get identical weights. Options are `--senate-polls`, `--governor-polls`, `--candidates`, `--matchups`, and `--output-dir`.

### What differs from the House

- **Races, not seats.** Polls carry no seat number. A question belongs to the race for its snapshot's office in its state.
- **Principal matchup.** By default a race's matchup is its single Democrat against its single Republican. Some races need a reviewed entry in [`statewide-principal-matchups.json`](../2026/polls/statewide-principal-matchups.json): one where an independent, not a Democrat, is the Republican's principal opponent, or one with several Republicans on the ballot. Each entry names `principal_candidate` (non-Republican) and, for a race with several Republicans, `republican_candidate`, with `evidence`, `rationale`, `reviewed_by`, and `reviewed_at`. An entry whose race or candidate is not in the field fails the build. The committed entries:

  | Race | Matchup | Why |
  | --- | --- | --- |
  | `AK-SEN` | Peltola vs. Dan Sullivan | Top-four ballot with three Republicans; the other two poll under 3% |
  | `ID-SEN` | Achilles (I) vs. Risch | No Democrat on the ballot |
  | `MT-SEN` | Bodnar (I) vs. Alme | Bodnar polls about 31% to Democrat Bankhead's 17% |
  | `NE-SEN` | Osborn (I) vs. Ricketts | No Democrat on the ballot |
  | `SD-SEN` | Bengs (I) vs. Rounds | No Democrat on the ballot |

  `AK-GOV` has no entry. Three Republicans split the first round (Wilson about 21%, Bronson 12%, Taylor 7%), so no principal Republican is established, and a first-round margin against any one of them would overstate the Democrat's position.
- **Matching ignores the poll's party code.** Answers match principal candidates by the shared surname rule only, because the snapshot's coding can differ from the ballot (Nebraska polls code Osborn as `DEM`). Other named answers may appear. If two answers match the same principal, only an answer whose full given name equals the ballot name counts. This separates "Dan J. Sullivan", the namesake, from incumbent "Dan Sullivan".
- **Column names.** The House columns keep their names so the same analysis works on both: `poll_avg_dem_*` is the principal non-Republican side, and the margin is that candidate minus the Republican. The new `poll_avg_matchup_basis` column is `dem_rep` or `reviewed`, so an independent principal is never mistaken for a Democrat.

Reasons are applied in this order: `out_of_cycle`, `not_general`, `unknown_race`, `no_principal_matchup`, `not_head_to_head` (no named candidates), `ambiguous_match`, `non_principal` (the question does not name both principals), then `superseded`. The governor snapshot's 2025 Virginia and New Jersey questions are `out_of_cycle`.

### Outputs

`2026/polls/statewide-poll-averages.csv` has one row per race: `state`, `office`, `race_id`, then `poll_avg_dem_candidate`, `poll_avg_rep_candidate`, `poll_avg_matchup_basis`, `poll_avg_dem_pct`, `poll_avg_rep_pct`, `poll_avg_dem_margin_pp`, `poll_count`, `poll_pollster_count`, `poll_latest_end_date`, `poll_avg_status`, and `poll_avg_source_id` (`us-senate-polls-2026` or `governor-polls-2026`). Status is `available`, `no_polls`, `no_eligible_polls`, or `no_principal_matchup`. Every value except status and source is blank unless the status is `available`.

`2026/polls/statewide-poll-average-inputs.csv` logs every question in both snapshots: `office` and `race_id`, then the House log's columns without `district` and `district_id`. As with the House, the weighted mean of one race's included margins, using the logged weights, reproduces its published margin.

In the November 3, 2026 snapshot, 62 of 71 races have an average: 29 Senate and 33 governor. Five Senate races have no polls (DE, NJ, OR, WV, WY), and Virginia's only Senate question is a 2025 Warner vs. Youngkin hypothetical (`no_eligible_polls`). Hawaii and Wyoming have no governor polls, and Alaska's governor race has no principal matchup.

### Limitations

The House limitations apply: there are no pollster quality ratings, partisan polls are discounted rather than dropped, and races with one or two polls carry their full error. Ranked-choice (Alaska, Maine) and runoff (Georgia, Louisiana) outcomes are not modeled; the average describes first-round shares. Reviewed matchups are judgments recorded with their evidence, and the `reviewed` basis marks them in every output.

## Election-night guide rows

The [guide races CSV](../2026/guide/election-night-guide-races.csv) has 14 Senate and 4 governor rows. `uv run scripts/election_guide.py --statewide-field 2026/candidates/statewide-general-field.csv` validates them along with the House rows. Each state may appear at most once per office, and each row must name a race in the statewide field. Senate and governor rows are not compared with the guide markdown; only House district references are.

`guide_name_check` compares the guide's Democratic and Republican names with that party's candidates in the race, and `other_candidate` with everyone else. It drops a trailing party note such as `(I)` and uses the poll surname rule. In the committed snapshot 17 races are `matched`. `AK-SEN` is `mismatch` because the guide's "Sullivan" fits both Republican Sullivans on Alaska's ballot. A mismatch changes no values.

## Context exports

Run the statewide sequence from the repository root after the House sequence:

```sh
uv run scripts/build_statewide_field.py
uv run scripts/normalize_district_history.py
uv run scripts/build_statewide_poll_averages.py
uv run scripts/build_statewide_race_context.py
uv run scripts/build_statewide_race_context.py --require-complete
```

All five run offline from saved inputs. `normalize_district_history.py` also rewrites the House district outputs, unchanged. The context build recomputes the state history and the statewide averages in memory and fails if the saved files differ, naming the script to rerun. It validates the guide rows before replacing any export. `--require-complete` fails when any race lacks a presidential margin or PVI; it never requires polling or guide coverage. It also validates the Senate and governor entries of the [incumbent roster](district-data.md#incumbent-roster). Options are `--candidates`, `--house-candidates`, `--manifest`, `--state-history`, `--state-pvi`, `--senate-polls`, `--governor-polls`, `--poll-averages`, `--matchups`, `--guide`, `--roster`, `--output-dir`, and `--require-complete`.

| File | Grain and purpose |
| --- | --- |
| `2026/statewide/statewide-race-context.csv` | One row per race (71) |
| `2026/statewide/statewide-candidate-context.csv` | One row per statewide field candidate (260), with its race's context appended |
| `2026/statewide/statewide-context-issues.csv` | One row per race and missing presidential or PVI metric; empty in the committed snapshot |

The race export's columns, in order:

| Columns | Meaning |
| --- | --- |
| `state`, `office`, `race_id`, `election_cycle` | Race identity and `2026` |
| `candidate_count`, `unresolved_fec_candidate_count` | Ballot rows, and Senate rows with `unmatched`, `ambiguous`, or `reviewed_unmatched` identity (governor `not_federal` rows are not unresolved) |
| `pres_2020_dem_margin_pp`, `pres_2024_dem_margin_pp` | The state's summed presidential margins |
| `cook_pvi_label`, `cook_pvi_dem_lean_pp` | Cook state PVI label and signed lean |
| `pres_2020_status`, `pres_2024_status`, `cook_pvi_status` | `available` or `missing` |
| `pres_2020_source_id`, `pres_2024_source_id`, `cook_pvi_source_id`, `cook_pvi_edition` | Sources, with the PVI edition (`2025`) |
| `poll_avg_*`, `poll_count`, `poll_pollster_count`, `poll_latest_end_date` | Copied unchanged from `statewide-poll-averages.csv` |
| `guide_slot_et` through `guide_notes` | The guide row's columns, `guide_`-prefixed, including `guide_senate_path` |
| `guide_name_check`, `guide_status`, `guide_source_id` | Name check, `in_guide` or `not_in_guide`, and the guide's source ID |
| `roster_incumbent_name`, `roster_incumbent_party`, `roster_vacant`, `roster_ballot_status`, `open_seat`, `roster_source_id` | The [incumbent roster](district-data.md#incumbent-roster)'s incumbent, whether they are on this race's ballot, and whether the seat is open. Governors get incumbency here even though their FEC fields are `not_federal` |

The candidate export keeps every field column in its original order and appends the race export's columns from `election_cycle` on, plus `roster_incumbent`, `True` only on the running incumbent's row. In the snapshot, 22 Senate and 17 governor incumbents are running; 13 Senate and 19 governor races are open seats. A Senate and a governor race in the same state carry the same presidential and PVI values. Missing values stay blank with `missing` status and an issue row; they never become zero or EVEN. Polling and guide gaps use their own statuses and add no issue rows.

### Examples

Count each race once from the race export, not the candidate export. Filter by `office` to compare like races, and check `poll_avg_matchup_basis` before reading `poll_avg_dem_*` as a Democrat:

```python
import csv

with open("2026/statewide/statewide-race-context.csv", newline="") as stream:
    races = list(csv.DictReader(stream))
senate = [r for r in races if r["office"] == "Senate" and r["poll_avg_status"] == "available"]
for r in sorted(senate, key=lambda r: abs(float(r["poll_avg_dem_margin_pp"]))):
    overperformance = float(r["poll_avg_dem_margin_pp"]) - float(r["pres_2024_dem_margin_pp"])
    print(r["race_id"], r["poll_avg_matchup_basis"], r["poll_avg_dem_margin_pp"], f"{overperformance:+.1f}")
```

In the November 3, 2026 snapshot, the six closest Senate averages are Louisiana (-0.43), Iowa (+0.47), South Carolina (-1.63), Nebraska (Osborn vs. Ricketts, -1.82), Alaska (+2.50), and Texas (+3.22). Each runs 13 to 22 points ahead of its state's 2024 presidential margin. These are first-round polling averages, not forecasts, and several rest on few polls; check `poll_count`.
