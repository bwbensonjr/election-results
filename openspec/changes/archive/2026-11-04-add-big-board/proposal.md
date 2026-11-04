# Proposal

## Why

The project has a complete pre-election baseline of all 506 House, Senate, and governor races, but nothing that shows live results against it. Polls close starting at 6pm Eastern on November 3, 2026, and the planned [Big Board](../../../docs/big-board.md) needs a results feed, a way to get that feed into a published Claude Artifact every few minutes, and a way to rehearse the whole loop before real votes arrive.

## What Changes

- Add an ingestion script that fetches the Boston Globe elections API (AP data), validates and joins every House, Senate, and governor race to the baseline by `race_key`, and writes one normalized `results.json` for the board. It keeps each raw response so a night can be replayed.
- Settle the data format for the board: flat JSON files, not SQLite. The artifact page reads static JSON directly; the ingestor keeps raw snapshots on disk for audit and replay.
- Add a mock election-night generator that writes responses in the exact Globe/AP shape for the real 2026 races and candidates, advancing through a simulated night (poll closings, rising reporting, race calls, a recount-close race, and a special case for Louisiana and ranked-choice races). The ingestor reads it through the same code path as the live API.
- Add a district shape build, following a pipeline already proven in another project: the Census 1:20m 119th Congress file, with state outlines merged from districts, projected into a 960 × 600 frame with Alaska and Hawaii below the lower 48, simplified, and written as SVG paths keyed by `race_key` (about 111 KB). The Census Bureau has not published 2026 boundaries, so each of the nine redrawn states uses its enacted 2026 plan when a shapefile is found, and is otherwise drawn on 2024 lines and marked as such on the board.
- Add the Big Board as a published Claude Artifact: a U.S. map with Governor, Senate, and House modes, zoom and selection, a configurable color metric (live results, polling average, 2024 Harris/Trump margin, Cook PVI, incumbent party), and a detail panel for the selected race.
- Add an update loop: the ingestor runs on a schedule and a Claude session writes changed results into the artifact's database, so open boards update in place without reloading. The published `results.json` stays as a fallback the page reads when the database is unavailable.
- Record findings from testing the endpoint on November 3 in [`election-endpoints.md`](../../../2026/results/election-endpoints.md) and the baseline reference: AP numbers at-large House seats `1` (the baseline assumption holds), the Ohio and Florida specials are office `S` with race type `Special General`, Louisiana House races are `Nonpartisan Election`, and the feed includes a national House popular-vote row (`statePostal` `US`, race ID `999999`).

## Capabilities

### New Capabilities

- `election-results-ingest`: Fetching the AP results feed, validating it, joining races and candidates to the baseline, and publishing a normalized results file with raw snapshots.
- `mock-election-feed`: A generator of realistic, AP-shaped election-night responses over a simulated timeline, for testing ingestion and the board before polls close.
- `congressional-district-geometry`: Draw-ready shapes for the 2026 House districts and for states, keyed to baseline race keys, with each district's boundary vintage recorded.
- `big-board`: The published election-night map artifact, its modes, color metrics, race detail, and how it picks up new results.

### Modified Capabilities

None. The `election-night-baseline` already says its AP race and candidate ID columns stay blank until a results feed fills them; the ingestor records those IDs in its own output and leaves the baseline files unchanged.

## Impact

- New scripts: `scripts/ingest_results.py`, `scripts/mock_election_feed.py`, `scripts/build_district_geometry.py`, with tests under `tests/`.
- New data: `2026/geometry/` (SVG path JSON and a source manifest), `2026/live/` (current `results.json`, raw snapshots, and an ingestion log; raw snapshots ignored by git except a few fixtures).
- New artifact source under `bigboard/` (HTML page plus published data files), published with the Artifact tool.
- The artifact's database holds the live results as five records in a `live` collection, readable by everyone who can open the board and writable only by its owner.
- External dependencies: the Globe API at `elections-api.bostonglobe.com` (no key, 60-second cache), the Census `cb_2024_us_cd119_20m.zip` file (about 404 KB) and any state-published 2026 plan shapefiles fetched once at build time, and `d3` (zoom and selection only) loaded from an approved CDN in the page.
- Docs: `docs/big-board.md`, `docs/election-baseline.md`, `2026/results/election-endpoints.md`, and the README.
