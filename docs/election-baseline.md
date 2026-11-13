# Election-night baseline

The baseline is one pre-election record of every race on the November 3, 2026 ballot that this project tracks: all 435 House districts, 35 Senate races, and 36 governor races. An election-night results feed joins to it by race key, and the tracker reads it for context. It carries only context that describes each race as it is contested in 2026.

## Build

Run from the repository root after the House and statewide context builds (see the [README](../README.md#build-district-data-for-viewing-and-analysis)):

```sh
uv run scripts/build_election_baseline.py
```

The build reads only the four context exports. It first rebuilds both context builds into a temporary folder and compares them byte for byte with the saved exports; any difference fails with the name of the script to rerun, and previous baseline files are kept. A missing or duplicated race key also fails. `--output-dir` writes elsewhere. Rebuilding from unchanged inputs produces byte-identical files: there is no build timestamp.

## Files

| File | Grain |
| --- | --- |
| [`2026/baseline/race-baseline.csv`](../2026/baseline/race-baseline.csv) | One row per race (506), sorted by state, then House, Senate, governor, then district |
| [`2026/baseline/candidate-baseline.csv`](../2026/baseline/candidate-baseline.csv) | One row per ballot candidate in the House and statewide fields (1,420) |
| [`2026/baseline/election-baseline.json`](../2026/baseline/election-baseline.json) | Both grains in one document, with `schema_version` (1), `election_date`, `input_sha256` for each context export, and the column lists |

JSON values are the same strings as the CSV cells, including `True`/`False` and blanks for unknown values.

## Race columns

| Column | Meaning |
| --- | --- |
| `race_key` | Stable key: the district ID for House races (`VA-01`, `AK-AL`), the race ID for statewide races (`GA-SEN`, `GA-GOV`) |
| `state_postal`, `office`, `district` | Two-letter state, `House`/`Senate`/`Governor`, and the two-digit district (`00` at-large; blank statewide) |
| `ap_office_id` | AP-style office code: `H`, `S`, or `G` |
| `ap_seat_num` | House seat number as an integer string, `1` for at-large districts; blank statewide. The at-large convention is an assumption to confirm against the AP feed |
| `ap_race_id` | Blank; the results-feed change fills it from AP |
| `candidate_count` | Ballot rows in the race |
| `roster_incumbent_name`, `roster_incumbent_party`, `roster_vacant`, `roster_ballot_status`, `open_seat` | From the [incumbent roster](district-data.md#incumbent-roster) |
| `pres_2024_dem_margin_pp`, `pres_2024_status` | 2024 presidential D-minus-R margin when its status is `available`, or `interpolated` (an estimate on the 2026 lines in six [redrawn states](district-data.md#redrawn-states)). Blank with status `prior_boundaries` in Alabama, Ohio, and Tennessee. Statewide races carry the state margin |
| `cook_pvi_label`, `cook_pvi_dem_lean_pp`, `cook_pvi_status` | Cook 2026 district PVI, or the 2025 state PVI for statewide races |
| `poll_avg_dem_candidate`, `poll_avg_rep_candidate`, `poll_avg_matchup_basis` | Polling principals and basis (`dem_rep` or `reviewed`); the `dem` side is the non-Republican principal, an independent where reviewed |
| `poll_avg_dem_pct`, `poll_avg_rep_pct`, `poll_avg_dem_margin_pp`, `poll_count`, `poll_latest_end_date`, `poll_avg_status` | The polling average, blank unless `available` |
| `guide_status`, `guide_slot_et`, `guide_poll_close_et`, `guide_card`, `guide_rating`, `guide_senate_path`, `guide_ladder_tier`, `guide_hell_yes`, `guide_ffs`, `guide_chill`, `guide_notes` | Election-night guide fields for the 62 guide races; `guide_senate_path` is blank for House races |

2020 presidential margins are deliberately left out: they describe older lines in redrawn states and are not needed on election night. The context exports still carry them.

## Candidate columns

| Column | Meaning |
| --- | --- |
| `race_key`, `state_postal`, `office` | The candidate's race |
| `name`, `party`, `party_raw` | Ballot name, `DEM`/`REP`/`OTHER`, and the ballot's party label |
| `fec_candidate_id` | Resolved FEC ID, blank when unresolved or for governors |
| `roster_incumbent` | `True` only for the running roster incumbent |
| `poll_principal` | `True` for the two polling principals where a polling average exists |
| `source_correction` | ID of the reviewed House ballot correction that produced the row, else blank |
| `ap_candidate_id` | Blank; the results-feed change fills it from AP |

## Joining AP results

AP results identify a race by state, office, and seat (plus AP's own race ID) and candidates by AP candidate ID. Match races on `state_postal`, `ap_office_id`, and, for House races, `ap_seat_num`; then record AP's race ID in `ap_race_id`. Match candidates within a race by name and party, then record `ap_candidate_id`. Keep `race_key` as the project's join key throughout.

Confirmed against the feed on November 3, 2026 (see [`election-endpoints.md`](../2026/results/election-endpoints.md)): AP numbers at-large House seats `1`, so the `ap_seat_num` convention holds and all 506 races join one to one. The Ohio and Florida special Senate elections are office `S`, seat `3`, race type `Special General`; each is the only Senate race in its state, so they join on state and office like any other. Louisiana's House races are race type `Nonpartisan Election` and are on a different calendar for 2026 (the general election is December 12), so November 3 results there are not final. The feed also carries a national House popular-vote row (state `US`, race ID `999999`) that is not a race. The baseline files stay unchanged: the results ingestor records AP race and candidate IDs in its own output (see [`big-board.md`](big-board.md)).
