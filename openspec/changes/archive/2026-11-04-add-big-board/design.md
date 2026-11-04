# Design

## Context

See [proposal.md](proposal.md) for why. The state that shapes the approach:

- The baseline ([`election-baseline.json`](../../../2026/baseline/election-baseline.json), 506 races and 1,420 candidates) already carries every pre-election field the board shows. Its `ap_race_id` and `ap_candidate_id` columns are blank by design.
- The repository is Python 3.11 scripts run with `uv run`, standard-library `unittest` tests, deterministic outputs, and builds that fail closed without replacing outputs. New scripts follow the same pattern.
- There is no map geometry in the repository. Nine states vote on new lines ([`boundary-vintage.json`](../../../2026/results/boundary-vintage.json)); Missouri and Virginia redrew but use their old lines. The Census Bureau has not published 2026 congressional boundary files.
- The user built a district map for another project (a design canvas) from `cb_2024_us_cd119_20m.zip`: drop Puerto Rico, project with Alaska and Hawaii below the lower 48, simplify to about 12% of points, write SVG paths in a 960 × 600 frame, merge districts into state outlines, and record state bounding boxes and district center points. The result was about 111 KB. Loading the paths as a separate file failed on that canvas, so they were embedded in the page. None of that work is in this repository.
- A published Claude Artifact is a static page plus supporting files on claude.ai. It cannot run the ingestor and has no server of its own. Publishing a new version needs the Artifact tool from a Claude session.

### Endpoint test, November 3, 2026, 9:39am ET

`GET https://elections-api.bostonglobe.com/v2/elections/2026-11-03/` returned HTTP 200 in 0.17 s:

- About 104 KB of JSON, `cache-control: max-age=60`, `access-control-allow-origin: *`. Top level: `electionDate`, `lastUpdated`, `url`, `races`.
- 862 races, each with one state-level `reportingUnits` entry (no county detail; `level=county` returns HTTP 400). `statePostal=XX` filters; `officeID` is ignored. The whole country in one request is the right call.
- Tracked offices: 436 `H` (430 `General`, 6 Louisiana `Nonpartisan Election`, plus one `US` national popular-vote row with race ID `999999`), 35 `S` (Ohio and Florida are `Special General`, seat `3`), 36 `G`. Everything else (state legislature, measures, mayors) is ignored.
- At-large House seats are seat `1` with `censusDistrict` `00`. Joining on `(statePostal, officeID, seatNum)` matched all 506 baseline races with no duplicates. The baseline's at-large assumption holds.
- Race fields used: `raceID`, `raceType`, `seatNum`, `eevp`, `raceCallStatus` (all `Too Early to Call` so far), `tabulationStatus` (`Awaiting Poll Close`), `rankedChoice`, `winThreshold`, `incumbents`, `currentParty`. Reporting-unit fields: `pollClosingTime` (UTC), `precinctsReportingPct`, `eevp`, `candidates[]` with `candidateID`, `first`, `last`, `party` (`Dem`, `GOP`, `Ind`, `Lib`, and 30 others), `voteCount`, `incumbent`.
- Candidate fields differ from the baseline: AP lists write-in totals and some minor candidates the baseline lacks, and the baseline has a few AP does not (169 races differ in count or surname). Surname matching on AP's `last` field, which keeps compound names such as `Wasserman Schultz` whole, covers 1,372 of 1,420 baseline candidates; the rest are mostly name-format differences to resolve in matching rules.
- Not observable before polls close: how a call appears. AP's convention is `winner: "X"` on the candidate plus a call status; the ingestor reads both, and the first real calls (Kentucky and Indiana, after 7pm ET) confirm it.

## Goals / Non-Goals

**Goals:**

- A loop that survives a long night unattended except for the Claude publishing session: fetch, validate, publish, with the last good data always on the board.
- Rehearse the whole loop against generated data this afternoon, then switch to the live endpoint with one flag.
- A board that opens fast on a phone: one page with its static data embedded, plus one live results file.

**Non-Goals:**

- County-level results or maps (the feed has none).
- Historical playback inside the board. Raw snapshots allow replay from the command line only.
- Ranked-choice tabulation, runoff tracking, or projections. The board shows AP's counts and calls.
- State legislative races and ballot measures, although the feed carries them.

## Decisions

### Flat JSON files, not SQLite

The board's static data, the district shapes (about 111 KB) and a slim baseline of race and candidate context (about 300 KB), is embedded in `index.html`; the live results (about 480 KB) travel as five database records split from `results.json`, with `results.json` also published beside the page as a fallback. The ingestor writes `2026/live/results.json` atomically and gzips each raw response into `2026/live/raw/` (git-ignored, except fixtures).

Alternatives: a SQLite file shipped to the page would need sql.js and its WebAssembly download, and the page would still load it whole; a local SQLite store for the ingestor adds nothing the raw snapshots do not already provide, since every query the board needs is "latest state of each race". JSON is also diffable when reviewing a run. If cross-snapshot analysis is wanted after the election, the raw snapshots can be loaded into SQLite then.

### One national request per run, a single ingestor for live and mock

`scripts/ingest_results.py` takes `--source live|PATH` and `--every SECONDS`. It parses, selects `H`/`S`/`G` races, joins on `(state, office, seat)`, matches candidates by normalized surname plus party (AP `Dem` to `DEM`, `GOP` to `REP`, anything else to `OTHER`), and writes `results.json`. It writes a `status.json` beside it with `changed`, `generated_at`, `ap_last_updated`, and counts, which the publishing step reads. Join failures fail the run (see the ingest spec); candidate mismatches are logged in `results.json` under `unmatched_candidates` and in the run log.

Vote share is computed over all candidates in the race. Leader margin for coloring is the top two candidates' share difference, signed D-minus-R when the top two are a Democrat and a Republican; otherwise the leader's party and margin are used as-is.

### Delivery: the artifact database, with the published file as fallback

The ingestor runs every 120 seconds in a terminal. Each run that changes the results also writes five record files to `2026/live/db/`: `meta` (everything in `results.json` except `races`), `statewide` (Senate and governor races, about 78 KB), and `house-1` to `house-3` (House races split by state in alphabetical order into three groups of about 130 KB). Each record carries the run's `content_hash`, and each must be under 240 KiB, below the database's 256 KiB document limit; an oversized record fails the run and keeps the previous files.

A Claude session runs `/loop 5m`: each tick reads `status.json`, and if the content hash differs from the last one written, it writes the five records to the `live` collection in one `ArtifactData` batch from the files, pinned to the versions returned by its previous write. If a pinned write is refused, it lists the collection for the current versions and retries once. A batch is at most 1 MiB, so the five records fit in one call.

The page declares `db` with one rule, `{path: "live", read: "view", write: "owner"}`, so every signed-in organization member reads the results and only the owner, through the loop, writes them. It subscribes once to the `live` collection and redraws only when all five records carry the same `content_hash` as `meta`, so a viewer never sees a mix of two runs. A database write creates no new artifact version, so open boards update in place with no reload, and the zoom, selection, and scroll position are never lost. A viewer returning to the board may first get the records saved on an earlier visit, which draws the map at once.

If the database namespace is unavailable, or no complete set of records arrives within 10 seconds, the page fetches the published `data/results.json` and polls it every 60 seconds until the database delivers. The file is published with the page and republished only by hand, so it is a floor, not the live path.

View state (office, metric, zoom, and selection) is kept in the viewer's `localStorage`, so a reload after a page republish restores the same view. The page applies the saved zoom before its first draw and draws results only once they arrive, so a load shows no grey map and no zoom jump. The page also shows when the board was loaded, which makes a reload visible during testing.

Alternatives: republishing `data/results.json` (the first implementation) works, but every republish creates a new version and every open board reloads to it, redrawing grey and losing its zoom for a moment. One database record per race would need 506 writes per update across eleven batches. The page fetching the Globe API directly (it sends `Access-Control-Allow-Origin: *`) depends on the artifact's content security policy, which blocks other hosts.

### Mock generator built on a captured real response

`scripts/mock_election_feed.py` loads a committed real pre-election response (`tests/fixtures/globe-2026-11-03-pre.json.gz`, captured this morning) and mutates only counts, reporting, call status, and winners. This keeps the shape identical to the live feed by construction. For each tracked race:

- Final Democratic two-party share centers on the polling average where `poll_avg_status` is `available`, else Cook PVI plus a national-environment setting (default D+2), with seeded normal error (4 points House, 3 statewide). Third-party shares come from a small fixed split.
- Counting starts at the race's real `pollClosingTime` and follows a seeded S-curve per state toward 95 to 100% of expected vote; early vote can lean toward one party and shift later, to exercise leads that flip. Counts never decrease.
- A race is called when expected vote is at least 50% and the projected margin exceeds a threshold that tightens with reporting. One race is forced to finish within half a point and stays uncalled. Alaska and Maine ranked-choice races without a majority stay uncalled; Louisiana's six House races are reported as nonpartisan and only called with a majority.
- Untracked races are carried through with counts zeroed so the response still holds 862 races.

`--steps N --step-minutes M` writes `step-001.json` onward; `--play SECONDS --out PATH` rewrites one file on a timer for a live rehearsal. Simulated clock time is written into `lastUpdated` so the board's freshness display can be tested.

### Geometry: the proven 20m pipeline, with enacted-plan overrides

`scripts/build_district_geometry.py` repeats the user's earlier pipeline in a committed, tested script:

1. Read `2026/geometry/sources.json` (URL, plan, retrieved date, SHA-256 per file), download into an ignored cache, and verify hashes. The base entry is `cb_2024_us_cd119_20m.zip` from `https://www2.census.gov/geo/tiger/GENZ2024/shp/`.
2. Drop Puerto Rico; keep D.C.'s delegate seat as a shape with no race. Normalize Census `STATEFP`/`CD119FP` to the baseline's `ST-NN` / `ST-AL` keys and check them against the 435 House race keys.
3. For each registry state with an `override` entry in the manifest (a state-published 2026 plan shapefile), reproject it to the base file's CRS and replace that state's districts; mark them `plan_2026`. Registry states without one keep 119th Congress districts marked `prior_boundaries`, and the build lists them. All other districts are `current`.
4. Project with an Albers USA composite (lower 48 conic, Alaska and Hawaii scaled and translated below), fit to 960 × 600.
5. Simplify topology-preserving, so neighbors keep shared edges (a 1 px tolerance, which keeps more detail than the prototype's 12% so urban districts survive zooming). Enacted-plan files are full resolution, so they go through the same step.
6. Merge each state's simplified districts into its outline, so borders coincide exactly.
7. Write `2026/geometry/us-house-2026.json`: frame size, `states` (path, bounding box), `districts` (path, center point, state, vintage), `prior_line_states`, and source hashes. Coordinates are rounded to 0.1 px and keys sorted for byte-identical rebuilds.

Dependencies (`geopandas`, `shapely`, `pyproj`, `topojson` for topology-preserving simplification) are declared as inline `uv` script metadata, like the other scripts.

Sourcing enacted plans is optional work with a clear payoff: each state found turns its districts from `prior_boundaries` to `plan_2026` with no other change. Texas, California, North Carolina, Ohio, and Utah publish plan shapefiles on their legislature or court sites; Alabama, Florida, Louisiana, and Tennessee are the most recent and least likely to be easy to find.

Alternatives: the 500k file is more detailed than a national map needs and much larger; TopoJSON projected in the browser would add topojson-client and d3-geo for no visible gain; failing the build on a missing plan was rejected because the Census Bureau has not published 2026 files and the board must ship tonight.

### Page structure

`bigboard/index.html` is a single page, written to the artifact-design contract (tokens on `:root`, dark mode, 16 px gutter), with d3 (selection and zoom only) from an approved CDN at a pinned version. The shapes are already projected, so the page draws the SVG paths as given in a 960 × 600 `viewBox`. Zoom uses `d3-zoom`; zooming to a state uses its recorded bounding box, and district labels use the recorded center points. Uncalled leads use an SVG hatch pattern over a lighter shade; calls use the solid shade. Districts marked `prior_boundaries` get a dashed outline and a legend entry. Margin bins and colors follow the `dataviz` skill palette with a legend. Detail opens in a side panel on desktop and a bottom sheet on phones. Times are shown in Eastern time.

`scripts/build_bigboard_data.py` takes the slim baseline (only the columns the board uses) and the shape file and writes them into a marked data block in `bigboard/index.html`, so the page source stays hand-edited while its data stays generated. It is deterministic like the other builds.

## Risks / Trade-offs

- [Enacted 2026 plans cannot be found for some redrawn states] → Those states draw on 2024 lines, flagged on the map and in the detail view, matching how the data already treats their presidential margins. Plan sourcing is time-boxed and can continue after the board ships; each state found needs only a rebuild and republish.
- [A published artifact cannot fetch its own supporting file, as the canvas could not] → Tested first with a throwaway artifact; fetching works, so the published file serves as the database fallback.
- [The Globe API changes shape or goes down tonight] → The ingestor fails closed and keeps the last good file; the board shows its staleness warning. Raw snapshots show exactly what changed. The AP developer API is the documented fallback but needs a key we do not have.
- [The Claude session stops or waits on a permission prompt for each database write] → The ingestor keeps running independently, so restarting the loop catches up in one batch. Pre-approve `ArtifactData` writes in the session, confirm the loop runs unattended in the rehearsal, and keep the Mac awake for the night.
- [The database's realtime connection drops] → The store falls back to refreshing about every 30 seconds with the same callbacks; the staleness warning covers longer gaps.
- [A pinned batch is refused because a record changed since the last write] → The loop lists the `live` collection for current versions and retries once; only the owner can write, so this happens only after a restart.
- [Call representation differs from the AP convention] → The ingestor treats an unrecognized call status as uncalled and logs it, so the board never shows a false call; fix the parser after the first real calls around 7pm ET and replay raw snapshots.
- [The page needs fixing during the night] → Republishing the page reloads open boards once; view state survives in `localStorage`. Results keep flowing through the database.
- [Candidate surname matching mislinks] → Matching is within one race and requires party agreement; unmatched candidates still display with AP's name, so a miss loses only the baseline link, not votes.
- [Mock data is mistaken for real results] → The mock sets `test: true` on every race, as AP does for test data, the ingestor carries it into `results.json`, and the board shows a prominent "TEST DATA" banner whenever it is set.

## Migration Plan

1. This afternoon: confirm supporting-file fetches work in a published artifact, build shapes and board data, publish the board against generated data, and rehearse with the mock in play mode and the Claude loop.
2. Before 6pm ET: switch the ingestor to `--source live`, write the records once and republish the fallback file, confirm the test banner disappears and races show `Awaiting Poll Close`.
3. After the first calls: confirm call parsing against raw snapshots and correct it if needed.
4. Rollback at any point: stop the ingestor and loop; the database keeps the last written results. If the database path fails, return to republishing `data/results.json`, which the page still reads as its fallback.

## Open Questions

- Whether a tool republish reloads already open views. Checked November 3: a probe artifact republished with only `data/probe.json` changed served the new file, and in the rehearsal an open board showed three successive republishes of `data/results.json` with its mode and metric kept. The runtime contract says every open view reloads to a new version, so those updates were most likely fast reloads restored from `localStorage`; the `hot` snapshot hook the first implementation used is not part of the contract. This is why live results moved to the database. Links cannot carry `#key=value` state, so view state stays in `localStorage`, not the URL hash.
- Whether AP's `eevp` stays populated for every state through the night; the board falls back to precincts reporting when it is missing.
