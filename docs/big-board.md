# Big Board Application 

Basic specification of a Big Board application artifact to follow results on election night.

# Functionality

- The primary view of the Big Board application is a U.S. map with modes for office
  - For 2026 the offices are Governor, Senate, and House
- The map has boundaries for the different offices and allows for
  zooming and selecting to see details for the identified race.
- The metric that drives the color of the districts on the map can
  configured and by default will use shades of blue and red, or grey
  for unknown/missing
  - Metrics for 2026
    - Party of incumbent
    - Harris/Trump margin (the President button)
    - Cook PVI
    - Polling average
    - Election night results
- When a district is selected it should show the full details for the
  district and the current election night results if any.
  - Details for 2026
    - Incumbent
    - Winner, if called 
    - Election night results (votes/vote percent, percent reporting)
    - Harris/Trump Margin
    - PVI 

# Design Factors 

- Should the UI be driven off of flat files or a SQLite database?
- Most of the data is locked before election night, but the results
  data will be updated every several minutes (probably 5 or 10
  minutes) based on a script that makes a web URL requests to
  the established AP API endpoint.
- The ingestor has not been written for 2026, but the endpoint we are
  planning on using is described in
  [`election-endpoints.md`](../2026/results/election-endpoints.md).

# Implementation

The board has four parts, each a script run from the repository root with `uv run`:

| Part | Script | Output |
| --- | --- | --- |
| District shapes | `scripts/build_district_geometry.py` | `2026/geometry/us-house-2026.json` |
| Results ingestion | `scripts/ingest_results.py` | `2026/live/results.json`, `status.json`, `runs.jsonl`, `raw/` |
| Mock election night | `scripts/mock_election_feed.py` | numbered responses in the AP feed's shape |
| Board page data | `scripts/build_bigboard_data.py` | the embedded data block in `bigboard/index.html` |

The board uses flat JSON files, not SQLite. The page embeds its static data (district shapes and a slim baseline) and gets live results as five records in the artifact's database, which a Claude session writes when they change; `data/results.json` is published beside the page as a fallback. Everything under `2026/live/` is ignored by git; a [checked-in snapshot](#checked-in-snapshot) of the results is kept in `2026/results/`.

## Results ingestion

```sh
uv run scripts/ingest_results.py                  # one live fetch
uv run scripts/ingest_results.py --every 120      # live, every two minutes, until stopped
uv run scripts/ingest_results.py --source PATH    # a saved or mock response (.json or .json.gz), or a folder of them in name order
```

Each run makes one request to the national endpoint (see [`election-endpoints.md`](../2026/results/election-endpoints.md)) and saves the response unchanged, gzipped, as `2026/live/raw/<UTC time>.json.gz` before parsing it. Running the ingestor over the `raw/` folder replays a night: a saved file's fetch time comes from its name, so replays reproduce the original output byte for byte.

A run keeps only House, Senate, and governor races, sets aside the national House popular-vote row (state `US`), and joins every race to the [baseline](election-baseline.md) on state, office code, and seat. It fails, leaving the previous `results.json` in place and naming each race, when a baseline race has no AP race, an AP race of a tracked office matches no baseline race, or two AP races match one baseline race. Candidates are linked to the baseline by surname and party (AP `Dem` to `DEM`, `GOP` to `REP`, anything else to `OTHER`), using first names only to break ties. AP candidates without a link, such as write-in totals, are kept with their votes and listed under `unmatched_candidates`. A link is never required.

With `--every`, a failed fetch or validation is logged and the next interval runs normally. The interval must be at least 60 seconds (the endpoint's cache time).

### Outputs

`results.json` is replaced atomically on each successful run:

| Field | Meaning |
| --- | --- |
| `schema_version`, `election_date` | `1`, `2026-11-03` |
| `ap_last_updated`, `fetched_at` | AP's response time and the fetch time (UTC) |
| `content_hash` | SHA-256 of `national`, `summary`, and `races`; unchanged when no results changed |
| `test` | `true` when any race is AP test data, as mock responses are |
| `national.house_popular_vote` | `DEM`/`REP`/`OTHER` votes and percent from the `US` row |
| `summary.<office>` | Race count, called seats by party group, and races with votes |
| `races.<race_key>` | One entry per baseline race (below) |
| `unmatched_candidates` | AP candidates with no baseline link |

Each race entry carries `ap_race_id`, `race_type` (`General`, `Special General`, `Nonpartisan Election`), `poll_close` (UTC), `tabulation_status`, `call_status` (AP's text), `called` and `winner` (from AP's candidate `winner: "X"` flag; any other call status is treated as uncalled), `eevp` (percent of expected vote), `precincts_pct`, `total_votes`, `leader_party_group` and `leader_margin_pp`, `dem_margin_pp` (top Democrat minus top Republican, when both ran), `ranked_choice`, `test`, and `candidates`, sorted by votes, each with `ap_candidate_id`, `name`, AP `party`, `party_group`, `votes`, `pct` (null before any votes), `incumbent`, `winner`, and `baseline_name`.

`db/` holds the same results as five database records for the board: `meta.json` (every field above except `races`, plus the list of race records), `statewide.json` (Senate and governor races), and `house-1.json` to `house-3.json` (House races grouped by state alphabetically). Race records carry `content_hash` and `races`. They are rewritten when results change; `meta.json` is rewritten on every run so its `fetched_at` stays current. A record of 240 KiB or more fails the run (the database limit is 256 KiB; a fully counted mock night peaks near 150 KB).

`status.json` summarizes the last successful run for the publishing step: `changed` (whether `content_hash` differs from the previous file), times, the test flag, and counts. `runs.jsonl` logs every run, including failures.

### Checked-in snapshot

[`2026/results/ap-results.json`](../2026/results/ap-results.json) is a committed copy of `results.json`, indented so each update diffs race by race. It is updated by hand after a live run whose results are worth keeping, never from mock data (check that `test` is `false`):

```sh
uv run python -m json.tool --indent 1 --no-ensure-ascii 2026/live/results.json 2026/results/ap-results.json
```

Its `fetched_at` and `ap_last_updated` say how current it is; counting continues for days after the election, so it is not final until states certify their results.

Tests: `uv run python -m unittest tests.test_ingest_results`.

## District shapes

```sh
uv run scripts/build_district_geometry.py
uv run tests/test_build_district_geometry.py
```

The build reads [`2026/geometry/sources.json`](../2026/geometry/sources.json), downloads each file into `2026/geometry/cache/` (ignored by git) if it is not already there, and fails if a file's SHA-256 differs from the manifest. It writes [`2026/geometry/us-house-2026.json`](../2026/geometry/us-house-2026.json) (about 184 KB), the same steps as an earlier canvas prototype, as a tested script:

1. Start from the Census 119th Congress cartographic boundary file at 1:20 million (`cb_2024_us_cd119_20m.zip`). Drop Puerto Rico. Keep D.C.'s delegate seat as a shape with no race. Normalize district numbers to the baseline's race keys (`00` is `ST-AL`).
2. Replace each redrawn state that has an `overrides` entry with its enacted 2026 plan, clipped to the Census state outline so coasts and borders match, and mark those districts `plan_2026`. Other states in the [boundary vintage registry](district-data.md#redrawn-states) keep their 119th Congress districts, marked `prior_boundaries`; all remaining districts are `current`.
3. Project with an Albers USA composite (separate conic projections for the lower 48, Alaska, and Hawaii, the latter two placed below) fitted to a 960 × 600 frame.
4. Simplify with shared borders preserved (1 px tolerance in the output frame), then merge each state's districts into its outline so state and district borders coincide.
5. Write SVG paths (0.1 px precision), each state's bounding box, each district's center point (for labels), its vintage, and the list of prior-line states. The build fails if any of the 435 baseline House keys is missing or extra, a shape falls outside the frame, or the file exceeds 400 KB. Rebuilds are byte-identical.

The 1 px tolerance keeps more detail than the prototype's 12% setting so that small urban districts stay recognizable when zoomed to a state; the file is still well under the size limit.

Enacted 2026 plans, found November 3, 2026 (see the manifest for URLs and hashes):

| State | Plan | Source |
| --- | --- | --- |
| CA | AB 604, put in effect by Proposition 50 | Senate Elections and Constitutional Amendments Committee |
| FL | EOGPCRP2026 (HB 1-D, Chapter 2026-229) | Florida Senate |
| LA | Act 2, 2026 Regular Session (SB 121) | Louisiana Legislature |
| NC | Session Law 2025-95 (S249) | North Carolina General Assembly |
| TX | PLANC2333 | Texas Legislative Council |
| UT | Court-adopted Map 1 (Map 1A) | Utah Geospatial Resource Center |

**Still on 2024 lines:** Alabama, Ohio, and Tennessee (31 districts). No official 2026 shapefile was published for them: Alabama and Tennessee offer only PDF maps, and Ohio's commission published a block assignment file, which would need joining to 2020 Census blocks. The board marks these districts with a dashed outline and says so in their detail. To add a state later, put its zip in the cache, add an `overrides` entry (`file`, `url`, `plan`, `sha256`, `district_field`, and `layer_path` when the shapefile is in a subfolder), rebuild, and rerun `scripts/build_bigboard_data.py`.

Utah's portal regenerates its zip on every download, so a fresh download will not match the recorded hash; keep the cached copy or re-verify and update the hash.

Checked by rendering: state and district borders coincide, Alaska and Hawaii sit below the lower 48, Texas shows its 38-district 2025 plan, and the remaining prior-line states are the three listed above.

## Mock election night

```sh
uv run scripts/mock_election_feed.py                      # 54 ten-minute steps from 6pm ET into 2026/live/mock/
uv run scripts/mock_election_feed.py --play 60 --out 2026/live/mock/current.json
uv run python -m unittest tests.test_mock_election_feed
```

The generator starts from the real pre-election response saved in `tests/fixtures/` and changes only counts, reporting, call status, and winners, so its output has exactly the live feed's shape and all 862 races. Every race is marked `test: true`, which the ingestor carries into `results.json` and the board shows as a test-data banner.

For each House, Senate, and governor race, the final margin between the two polling principals is centered on the polling average where one exists, otherwise on twice the Cook PVI lean plus `--environment` (default D+2), with seeded random error (4 points House, 3 statewide). Other named candidates share a few points (more in Louisiana's open primaries and ranked-choice races); write-ins get a fraction of a point. Counting starts 5 to 25 minutes after each race's real poll-closing time and follows a per-state S-curve to 93 to 99.5% of the expected vote; early counts lean by a per-state shift that fades as counting finishes, so some leads flip. Vote counts never decrease.

Races with a final margin of 20 points or more are called at poll close. Others are called once at least half the expected vote is in, the current leader is the final leader, and the lead exceeds a threshold that tightens with reporting. Ranked-choice races (Alaska, Maine) and Louisiana's nonpartisan House races are called only for a candidate over 50%. PA-07 is forced to finish within half a point and is never called. `--seed` and `--environment` change the night; the same settings write identical files.

### Rehearsal

Run each in its own terminal from the repository root:

```sh
uv run scripts/mock_election_feed.py --play 60 --out 2026/live/mock/current.json
```

```sh
uv run scripts/ingest_results.py --source 2026/live/mock/current.json --every 60
```

The ingestor picks up each new step within a minute. Publish as described in the runbook below; the board shows the test-data banner throughout.

## The board page

```sh
uv run scripts/build_bigboard_data.py       # after any baseline or shape rebuild
uv run python -m unittest tests.test_build_bigboard_data
```

[`bigboard/index.html`](../bigboard/index.html) is a hand-written page; the build script replaces only the block between the `board-data` markers with the slim baseline (the race columns the board shows, plus candidate names) and the district shapes, about 330 KB in all. The page loads d3 from cdnjs for zoom and draws the pre-projected paths. Live results come from the artifact's database: the page subscribes once to the `live` collection and redraws only when all five records share one `content_hash`. A database write makes no new artifact version, so open boards update in place with no reload. If the database is unavailable or silent for 10 seconds, the page reads the published `data/results.json` instead and checks it every 60 seconds. The footer says when the board was loaded and which source it is using. Mode, metric, zoom, and selection are kept in `localStorage`; on load the page applies the saved zoom before drawing and holds the map until results arrive, so a reload shows no grey map or zoom jump.

The database is declared at publish with one access rule, `{path: "live", read: "view", write: "owner"}`: everyone the board is shared with reads the results, and only the owner writes them.

Metrics: **Results**, **Polls** (polling average margin), **President** (2024 Harris–Trump margin. In the six redrawn states drawn on 2026 shapes, it is an estimate on the new lines, colored like any other margin and labeled "est. on 2026 lines" in the race detail with a note on the method; see [interpolated margins](district-data.md#interpolated-margins-on-2026-lines). Alabama, Ohio, and Tennessee, still drawn on 2024 lines, are grey), **PVI** (Cook PVI lean), and **Incumbent** (party). Colors: Democratic blue and Republican red in four margin steps (under 5, 5 to 10, 10 to 20, and 20 or more points; PVI uses half those steps, since a PVI lean is about half a two-party margin), validated as ordinal ramps in both themes; violet for any other party; mid grey for no data; a pale fill for states or districts with no race. Under the results metric a called race is solid and an uncalled lead is hatched. Districts drawn on 2024 lines have a dashed outline. A test-data banner appears whenever results come from the mock, and a warning appears during the night when published results are more than 15 minutes old.

The published board: <https://claude.ai/artifact/PYJrwsZ2CfhnGuu8SV6FnN> (shared with the organization from its Share menu; sharing carries across versions). [`bigboard/artifact.json`](../bigboard/artifact.json) records the link and publish settings, so any Claude session can republish to the same link.

## Election-night runbook

Times are Eastern. Keep the Mac awake and plugged in for the night.

1. **Ingest** (terminal 1, from the repository root). Stop any mock first.

   ```sh
   uv run scripts/ingest_results.py --every 120
   ```

   Each run prints one line: `changed` or `unchanged`, AP's update time, and called seats. Errors print and the loop continues with the last good `2026/live/results.json`.

2. **Write results to the database** (this Claude Code session). Start a loop:

   ```
   /loop 2m Big Board database tick. Read <repo>/2026/live/status.json and <repo>/2026/live/db-written.json. If status.ok is true and status.content_hash differs from db-written.content_hash, call ArtifactData action batch on https://claude.ai/artifact/PYJrwsZ2CfhnGuu8SV6FnN with five set writes to collection live for doc ids meta, statewide, house-1, house-2, house-3, each with file_path <repo>/2026/live/db/<doc id>.json and if_version from db-written.versions. Otherwise, if db-written.written_at is more than 10 minutes old, set only meta the same way. If a write is refused for a version mismatch, list collection live for the current versions and retry once. After a successful write, overwrite db-written.json with the status content_hash, written_at as UTC now, and the versions the write returned. Do nothing else and report one line.
   ```

   Replace `<repo>` with the absolute repository path. `2026/live/db-written.json` records the last hash written and each record's version; if it is missing, list the `live` collection with ArtifactData and recreate it from the versions shown. The 10-minute `meta` write keeps the board's freshness line current when no new votes arrive. Approve ArtifactData writes for the session before leaving it unattended, or the loop stops at a permission prompt.

   The published fallback file is updated only by republishing the page (step 5).

3. **Watch** `2026/live/runs.jsonl` for repeated errors. A join failure names the races involved; compare with the newest file in `2026/live/raw/`.

4. **After the first calls** (Kentucky and Indiana, after 7pm): confirm that called races show a winner. If they do not, AP's call format differs from the `winner: "X"` flag the ingestor expects: fix the parser, then replay the night so far with `uv run scripts/ingest_results.py --source 2026/live/raw` and let the loop write the records.

5. **Republish the page** only for a page fix or to refresh the fallback file: the Artifact tool with `file_path` `bigboard/index.html`, `url` from [`bigboard/artifact.json`](../bigboard/artifact.json), `root` `bigboard`, and `files` `{"data/results.json": {"from": "<repo>/2026/live/results.json"}}`. Omit `capabilities` so the database declaration is kept. Open boards reload once and restore their view.

**Restart:** rerun step 1 or 2; the ingestor needs no state, and the loop writes on its next tick.

**Rollback:** stop both; the database keeps the last written results. If the database path fails, go back to republishing the page with the current `results.json` every few minutes (step 5); the page reads the file whenever the database is silent.

**Rehearsal:** the same steps with the mock instead of the live feed (see [Mock election night](#mock-election-night)): `--play 60 --out 2026/live/mock/current.json` in one terminal and `uv run scripts/ingest_results.py --source 2026/live/mock/current.json --every 60` in the other. The board shows the test-data banner until a live run replaces the results.
