# Election Endpoints 

Links to consider for getting November 3, 2026 election results as the come in.

Base Globe link: https://elections-api.bostonglobe.com/v2/elections/2026-11-03/
Example state query: https://elections-api.bostonglobe.com/v2/elections/2026-11-03/?statePostal=KY

AP documentation: https://developer.ap.org/ap-elections-api/

## Endpoint test, November 3, 2026

Tested at 9:39am and 10:00am ET, before any polls closed. A pre-election response is saved as [`tests/fixtures/globe-2026-11-03-pre.json.gz`](../../tests/fixtures/globe-2026-11-03-pre.json.gz).

- `GET https://elections-api.bostonglobe.com/v2/elections/2026-11-03/` returns HTTP 200 in under 0.2 s: about 100 KB compressed, about 1 MB of JSON. Headers: `cache-control: max-age=60`, `access-control-allow-origin: *`. No key is needed.
- Top level: `electionDate`, `lastUpdated`, `responseType`, `apiVersion`, `url`, `races`. Each race has `statePostal`, `test`, `lastUpdated`, and `raceResponse`.
- `?statePostal=XX` filters by state. `officeID` is ignored, and `level=county` returns HTTP 400: there is one state-level reporting unit per race and no county detail. One national request per update is the simplest option.
- 862 races. Tracked offices: 436 `H` (430 `General`; Louisiana's six as `Nonpartisan Election`; one `US` national popular-vote row, race ID `999999`, with Democrat/Republican/Other totals), 35 `S` (Ohio and Florida as `Special General`, seat `3`, `raceTypeID` `W`), and 36 `G`. The rest are state legislative seats, ballot measures, and local offices.
- At-large House seats are seat `1` with `censusDistrict` `00`. Joining on state, office, and seat matches all 506 baseline races one to one.
- Race fields: `raceID`, `raceType`, `seatNum`, `eevp` (expected vote percent), `raceCallStatus` (`Too Early to Call` before polls close), `tabulationStatus` (`Awaiting Poll Close`), `rankedChoice`, `winThreshold`, `incumbents`, `currentParty`, `keyRace`. Reporting-unit fields: `pollClosingTime` (UTC), `precinctsReporting`, `precinctsTotal`, `precinctsReportingPct`, `eevp`, and `candidates`, each with `candidateID`, `first`, `last`, `party` (`Dem`, `GOP`, `Ind`, `Lib`, and about 30 others), `voteCount`, `ballotOrder`, and `incumbent`.
- Candidate lists differ from the baseline: AP includes write-in totals (`Total Write-ins`) and some minor candidates the baseline lacks, and the baseline has a few that AP does not list. AP's `last` keeps compound surnames whole (`Wasserman Schultz`, `Huckabee Sanders`).
- Not observable before polls close: how a race call is represented. AP's convention is `winner: "X"` on the winning candidate plus a call status.

The ingestor and mock feed that use this endpoint are described in [`docs/big-board.md`](../../docs/big-board.md).
