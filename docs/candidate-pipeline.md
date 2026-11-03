# Candidate pipeline

## Run and refresh

Run all commands from the repository root with Python 3.11+ and `uv`:

```sh
# Offline rebuild from committed inputs; no API credentials required.
uv run scripts/build_house_field.py

# Full source refresh (network and FEC_API_KEY required).
uv run scripts/fetch_fec_house_candidates.py --totals
uv run scripts/flag_general_candidates.py
uv run scripts/fetch_ballotbrief_house.py
uv run scripts/build_house_field.py

# Senate and governor source refresh (network and FEC_API_KEY required).
uv run scripts/fetch_fec_house_candidates.py --office S --totals
uv run scripts/flag_general_candidates.py --office S
uv run scripts/fetch_ballotbrief_statewide.py

# Offline test data; first run can download requests and beautifulsoup4.
uv run --with requests --with beautifulsoup4 python -m unittest discover -s tests -v
```

`--office` takes the FEC office code, `H` (the default) or `S`. With `S` the fetcher writes `fec-senate-candidates.csv`, and the flagger reads it and writes `fec-senate-candidates-flagged.csv`, `fec-senate-general.csv`, and `review-senate-races.csv`. Without `--office`, both scripts read and write exactly the House paths they always have.

`uv` reads Python/dependency requirements from each script's PEP 723 header. Fetching FEC records and flagging need `requests`; scraping also needs `beautifulsoup4`; the builder needs only the standard library. The scripts use repository-relative paths. Optional `--out` paths on the fetchers do not change downstream defaults; move outputs into the expected locations before continuing.

The fetcher reads `FEC_API_KEY` from the environment, then a root `.env` file with a plain `FEC_API_KEY=...` assignment. The simple loader is not a complete dotenv parser. The fetcher can fall back to a severely rate-limited demo key; the flagger requires a real key. API keys are available through [api.data.gov](https://api.data.gov/signup/). Keep `.env` local and ignored.

Sources are [OpenFEC](https://api.open.fec.gov/developers/) for registrations, candidate classifications, financial totals, and reports, and [The Ballot Brief](https://theballotbrief.com/candidates/us-house) for ballot candidate coverage. Ballot Brief uses AI-assisted research and warns of possible errors; it is not an official certification source. Its district links are retained in `source_url`. [Ballotpedia](https://ballotpedia.org/List_of_congressional_candidates_in_the_2026_elections) is an additional reference, not a scraper input.

Senate and governor candidates come from Ballot Brief's [Senate](https://theballotbrief.com/candidates/us-senate) and [governor](https://theballotbrief.com/candidates/governor) list pages, with the same AI-assisted-research caveat. Each list row links to a state page (`/state/<name>`), which is kept as `source_url`. A row that ends in "and N more" is replaced by the candidates of that office's contest (`details#race-u-s-senate` or `details#race-governor`) on the state page. A trailing "(+N more contests)" note on a list row refers to other contests on the state page and is dropped. The Ohio and Florida Senate races in 2026 are special elections; the list shows each as that state's only Senate race. Governors are not federal candidates, so OpenFEC has no governor records; the pipeline uses no state campaign-finance source.

The seven polling CSVs in `2026/polls/` are attributed to the NY Times in the original README. They include House, Senate, governor, president, presidential approval, presidential approval averages, and other polls. No download script, exact export URL, or retrieval timestamp is recorded. Acquire refreshed exports manually, preserve their schemas, and record the actual source/retrieval date when refreshing. This pipeline reads only `us-house-polls.csv`; the other six files are retained for separate analysis. Candidate rows and answer choices can repeat per poll; a CSV row is not necessarily one poll.

## Script and artifact inventory

| Script | Inputs | Outputs |
| --- | --- | --- |
| `fetch_fec_house_candidates.py --totals` | FEC candidates and candidate-totals API endpoints for the 2026 House cycle | `fec-house-candidates.csv` |
| `flag_general_candidates.py` | Raw candidate CSV, House 12G report endpoint, candidate search, committee fallback endpoint | `fec-house-candidates-flagged.csv`, `fec-house-general.csv`, `review-districts.csv` |
| `fetch_ballotbrief_house.py` | House list and truncated district pages from Ballot Brief | `ballotbrief-house-candidates.csv` |
| `build_house_field.py` | Ballot CSV, flagged FEC CSV, reviewed registry, House polls | `house-general-field.csv`, `field-discrepancies.csv`, `candidate-match-review.csv` |
| `fetch_fec_house_candidates.py --office S --totals` | The same FEC endpoints for 2026 Senate candidates | `fec-senate-candidates.csv` |
| `flag_general_candidates.py --office S` | Raw Senate CSV, Senate 12G reports, candidate search, committee fallback | `fec-senate-candidates-flagged.csv`, `fec-senate-general.csv`, `review-senate-races.csv` |
| `fetch_ballotbrief_statewide.py` | Senate and governor list pages and truncated state pages from Ballot Brief | `ballotbrief-statewide-candidates.csv` |

All candidate paths are under `2026/candidates/`. The first seven CSVs above existed before identity resolution was added. `candidate-match-review.csv` is new. `candidate-identity-decisions.json` is maintained review input, not downloaded or regenerated by the fetchers. Keep it when refreshing source CSVs.

The FEC fetcher paginates and retries rate limits/server errors. The scraper follows truncated list entries to district pages with a 0.5-second delay. These mechanisms do not validate source completeness. Inspect counts and diffs before relying on a refresh; in particular, the scraper can still publish a partial parse. The field's coverage follows the ballot CSV, whereas FEC lists can include territorial, blank, or otherwise out-of-scope district records.

## Identity resolution

The ballot list defines candidate coverage. FEC matches are restricted to the same state and district. Automatic acceptance requires a unique compatible party, full given name, and surname after accent, punctuation, and suffix normalization. DFL and Democratic are equivalent. Initials, nicknames, conflicting/unknown parties, uncertain compound names, and multiple plausible IDs require review. Input ordering cannot choose an identity.

The final field appends `fec_match_status`, `fec_match_reason`, and `fec_alternate_ids` (sorted, semicolon-separated) to the existing columns:

| Status | Meaning |
| --- | --- |
| `automatic` | Unique strong name and compatible party evidence |
| `reviewed` | Explicit mapping accepted from the registry |
| `reviewed_unmatched` | Reviewer explicitly found no suitable FEC match |
| `unmatched` | No acceptable automatic match; review remains open |
| `ambiguous` | Multiple plausible records; review remains open |

Unresolved and reviewed-unmatched rows retain their ballot information and have blank FEC-derived fields. Blank means unknown, not false. Poll presence does not resolve FEC identity.

## Reviewed decisions

`2026/candidates/candidate-identity-decisions.json` contains `schema_version: 1` and a `decisions` array. Each decision has:

| Field | Meaning |
| --- | --- |
| `cycle` | Integer 2026 |
| `state`, `district`, `ballot_name` | Exact ballot identity; numeric districts normalize to two digits |
| `decision` | `match` or `unmatched` |
| `canonical_fec_id` | Existing ID for a match; empty string for unmatched |
| `alternate_fec_ids` | List of other reviewed IDs for this person; empty for unmatched |
| `evidence` | Nonempty list of source references supporting the decision |
| `rationale` | Why this mapping or unmatched decision is justified |
| `reviewed_by` | Actual reviewer identity, including an automated reviewer if applicable |
| `reviewed_at` | ISO calendar date, for example `2026-11-02` |

The canonical FEC record supplies incumbency and financial values. Financial totals are never summed across alternate IDs. The filing flag is true if any reviewed member ID has a qualifying 12G report. The output reason identifies the canonical and alternate IDs; the registry retains the review evidence.

The builder validates the full registry before replacing outputs. Duplicate keys, IDs reused across identities, nonexistent IDs, absent ballot rows, state/district conflicts, invalid dates, missing metadata, and malformed decisions fail with a nonzero exit. A source name change requires renewed review. A party discrepancy needs explicit evidence and rationale; it cannot match automatically.

## Review workflow

1. Run the offline builder and inspect `candidate-match-review.csv`, starting with major-party unmatched and ambiguous rows.
2. Compare candidate and committee records with the ballot source and official candidate/filing evidence. A shared name, committee, or equal financial totals alone does not establish canonical identity.
3. Record a canonical ID and verified alternate IDs, or an explicitly unmatched decision, with evidence and the actual reviewer. Do not edit generated CSVs or invent reviewer metadata. If evidence is insufficient, retain the unresolved case and explain it in the dated review summary.
4. Rebuild and inspect identity, incumbency, and filing changes together. Commit reviewed decisions and derived outputs together when committing the work.
5. Repeat after every input refresh; stale registry entries fail visibly.

## Committee attribution

The flagging script retains every principal-committee candidate link and assigns a qualifying report to every linked candidate ID present in the input. If search supplies no in-scope link, the committee endpoint's candidate IDs are used, retaining all returned rows and IDs. A shared committee does not establish that different IDs belong to the same person; identity grouping requires review.

Reports are selected by latest `receipt_date`, then highest numeric `file_number` (falling back to `beginning_image_number`), then image number and committee ID for deterministic ties. This ordering applies within and across committees. Unmatched committees are reported to stderr. A 12G flag corroborates participation; it does not certify a ballot candidate. Missing filings and duplicate IDs can affect the filing-based review list.

## Builder output schemas

`house-general-field.csv` has one row per ballot-list row. The original columns are retained in order; identity columns are appended. State is a two-letter code; district is a string with two digits, with `00` for at-large seats. Preserve leading zeroes when importing CSVs.

| Column | Meaning |
| --- | --- |
| `state`, `district` | Ballot jurisdiction and district |
| `name` | Ballot source's candidate name |
| `party` | `DEM`, `REP`, `OTHER`, or blank; only the two major parties are grouped here |
| `party_raw` | Original ballot party label |
| `fec_candidate_id`, `fec_name` | Accepted canonical record's ID and name |
| `incumbent` | Whether the canonical FEC record has incumbent code `I` |
| `filed_12g` | Whether any accepted member ID has a 12G flag |
| `receipts`, `cash_on_hand_end_period` | Canonical record's cycle totals in nominal U.S. dollars |
| `in_general_polls` | Appears in a qualifying poll; does not measure support or establish identity |
| `source_url` | Ballot source's district URL |
| `fec_match_status`, `fec_match_reason`, `fec_alternate_ids` | Resolution status, explanation, and reviewed alternate IDs |

CSV booleans are `True`/`False`. Blank FEC fields mean unresolved/unavailable; zero money and `False` are actual source values. A blank poll flag means an ambiguous poll association without other confirmed poll evidence. The final field does not carry financial coverage dates: consult the accepted FEC ID in the flagged input or the review report before comparing finances.

`candidate-match-review.csv` lists unresolved and reviewed-unmatched candidates. Each plausible FEC record gets a row; a candidate with no plausible records gets one row with blank FEC fields. It is sorted by state, district, ballot name, and proposed FEC ID.

| Column | Meaning |
| --- | --- |
| `state`, `district`, `ballot_name`, `ballot_party` | Identity needing review |
| `fec_match_status`, `fec_match_reason` | Why acceptance was withheld |
| `fec_candidate_id`, `fec_name`, `fec_party` | Proposed FEC record, not an accepted match |
| `incumbent`, `filed_12g`, `receipts`, `cash_on_hand_end_period` | Proposed record's source values |
| `coverage_end_date` | Proposed financial record's reporting cutoff |
| `decision_evidence` | Semicolon-separated references for an applicable reviewed-unmatched decision |

`field-discrepancies.csv` has `state`, `district`, `candidate`, and `issue`. Issues distinguish major-party unresolved identities, 12G filers with plausible but unresolved ballot identities, 12G filers absent from the ballot list, poll names absent from the list, ambiguous poll associations, and districts without one major party. Accepted alternate IDs count as on-ballot. A missing major party can be expected in an uncontested race or a jurisdiction with different election rules; it is a review item, not automatic proof of missing data.

## Source and intermediate schemas

`ballotbrief-house-candidates.csv` has `state`, `district`, `name`, `party`, and `source_url`. These are the scraper's source labels, not independently verified certifications. The combined field preserves every row.

`fec-house-candidates.csv` contains FEC registrations, including primary losers and inactive records. With the documented `--totals` invocation its columns are:

| Column | Meaning |
| --- | --- |
| `candidate_id`, `name` | FEC identifier and source name, usually surname first |
| `party`, `party_full` | FEC party code and description; source errors can occur |
| `state`, `district`, `district_number` | Reported jurisdiction, string district, and numeric district |
| `incumbent_challenge`, `incumbent_challenge_full` | FEC classification code and description; `I` denotes incumbent |
| `candidate_status` | FEC source status code, preserved without interpretation |
| `candidate_inactive`, `has_raised_funds` | Source boolean flags; neither establishes ballot eligibility |
| `first_file_date`, `last_file_date` | Source filing dates, not local retrieval dates |
| `receipts`, `disbursements` | Cycle-to-date U.S. dollar totals from the candidate totals endpoint |
| `cash_on_hand_end_period` | U.S. dollars held at the report's period end |
| `coverage_end_date` | Financial report's coverage cutoff, not download date |

Without `--totals`, the last four financial columns are absent, and the documented builder cannot use that file as its financial input. There are no financial estimates or currency conversions. Identical totals on two IDs are not additive. A missing source total can be blank even when identity is resolved.

`fec-house-candidates-flagged.csv` preserves those columns and appends:

| Column | Meaning |
| --- | --- |
| `filed_12g` | A qualifying report was attributed to the candidate record |
| `pre_general_receipts` | Selected 12G report's year-to-date receipts in U.S. dollars; a different scope from cycle totals |
| `pre_general_cash_on_hand` | Selected 12G report's ending cash in U.S. dollars |
| `pre_general_coverage_end` | Selected 12G report's coverage-end calendar date |

`fec-house-general.csv` has the identical flagged schema, restricted to 12G-filing records. It is a filing-based intermediate list, not the ballot authority or a deduplicated person list. The final builder reads the full flagged file so a missing filing does not remove a ballot candidate.

`review-districts.csv` has `state`, `district`, `reason`, and `filers_12g` (semicolon-separated candidate names with party codes). It flags missing or multiple major-party filers, districts without filings, top-two exceptions, and the script's Louisiana calendar exception. The check operates on candidate IDs, so duplicate person records can still produce multiple-filer warnings. It is a heuristic review aid, not an authoritative election-calendar model.

The registry schema and three builder output schemas are described above. `True`/`False` are CSV strings; blank source values and unresolved fields must not be coerced to false. Preserve district codes and IDs as text.

## Poll interpretation and known limits

The builder uses `cycle`, `stage`, `state`, `seat_number`, `party`, `candidate_name`, and `end_date` from `us-house-polls.csv`. Other export fields, including poll IDs, samples, percentages, population, question IDs, dates, and source URLs, are retained in the source file but are not aggregated by the builder.

A qualifying appearance has cycle `2026`, stage `general`, a district, a candidate party other than `NONE`/`ALL`, a name not starting with `Generic`, and an end date on or after **September 1, 2026**. Dates are parsed as month/day/two-digit-year. At-large poll seats are mapped to `00` for states represented only by that district in the ballot input. The cutoff is a fixed heuristic, not proof that every primary had finished or that a matchup was final. Polls can contain hypothetical matchups; the current filter does not examine the export's hypothetical flag or select ranked-choice rounds.

`in_general_polls` means at least one qualifying poll name maps uniquely to that ballot candidate. Unique surname matching is permitted for poll presence, with given-name disambiguation when needed. This rule is separate from the stricter FEC identity process. Ambiguous associations appear in the discrepancy report, and a candidate with only ambiguous evidence has a blank presence flag. `False` means no qualifying matched appearance in these inputs, not zero support, no campaign, or no polling elsewhere. No poll averages, vote margins, weights, or predictions are calculated.

Jurisdiction-specific rules can produce same-party finalists, more than two candidates, uncontested races, ranked-choice contests, or election-calendar exceptions. The existing review script special-cases California/Washington top-two fields and Louisiana; those heuristics do not fully model every state's law. Verify rules and current ballot status with the relevant election authority when adjudicating a discrepancy. The dataset targets the 435 voting House districts; territorial FEC filings can appear in discrepancies without being missing voting seats.

The separate [district-data workflow](district-data.md) now joins the supplied district-level 2020/2024 presidential margins and published Cook 2026 PVI to this candidate field through canonical district IDs. It produces district and candidate context exports without changing this pipeline's outputs or identity decisions. The project does not yet include a separate district incumbent roster (including incumbents who are not running) or an election-night watchlist. Candidate-level FEC incumbent flags are not a substitute for that roster. The combined field omits financial coverage dates, which remain available in the flagged source and review report. Snapshot age, source accuracy, incomplete FEC coverage, unresolved identity, and manual polling refresh all constrain interpretation.

## Snapshot review: November 2, 2026

Review performed by Codex (automated source review). This is a disposition of the committed snapshot, not certification of ballot completeness. The primary evidence for unresolved rows is the committed ballot and flagged FEC CSVs; candidate IDs below identify exact source rows.

The rebuilt field contains 1,159 candidates in 435 districts: 831 automatic matches, 3 reviewed matches, 299 unmatched, and 26 ambiguous. The review report contains 351 rows for 325 candidates. Counts describe this snapshot only.

### The 18 baseline ambiguous candidates

Three canonical selections were reviewed against both FEC profiles and the ballot source's district pages. The other 15 cases remain unresolved. No alternate IDs have been asserted: shared names, committees, and totals alone do not prove person-level equivalence.

| District | Ballot candidate | Baseline FEC IDs | Disposition and reason |
| --- | --- | --- | --- |
| CA-41 | Mitch Clemmons | `H2CA38260`, `H6CA41380` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |
| IL-09 | John Elleson | `H8IL09208`, `H8IL09224` | Unresolved: person-level equivalence and canonical selection not established. |
| IN-02 | William Eric Henry | `H4IN02200`, `H6IN02205` | Unresolved: person-level equivalence and canonical selection not established. |
| KY-04 | Jeremy Todd | `H6KY04205`, `H6KY04213` | Unresolved: 12G flags differ, financial totals differ; person-level equivalence and canonical selection not established. |
| LA-05 | Antonio Wilson | `H6LA05325`, `H6LA05333` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |
| MI-10 | Mike Saliba | `H0MI09206`, `H6MI10383` | Unresolved: person-level equivalence and canonical selection not established. |
| MO-01 | Paul Berry III | `H2MO02219`, `H6MO01261` | Unresolved: person-level equivalence and canonical selection not established. |
| MO-03 | Bob Onder | `H4MO03221`, `H8MO09146` | Reviewed canonical `H4MO03221`: current FEC profile identifies the incumbent; competing record is labeled challenger. Competing ID not grouped. |
| MS-04 | Carl Boyanton | `H0MS04161`, `H6MS04259` | Unresolved: 12G flags differ, financial totals differ; person-level equivalence and canonical selection not established. |
| NC-04 | Mahesh 'Max' Ganorkar | `H2NC06106`, `H4NC02150` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |
| NC-08 | Mark Harris | `H4NC08066`, `H6NC09200` | Reviewed canonical `H4NC08066`: current FEC profile identifies the incumbent; competing record is labeled challenger. Competing ID not grouped. |
| NJ-06 | Hillary Herzig | `H6NJ06278`, `H6NJ06286` | Unresolved: 12G flags differ, financial totals differ; person-level equivalence and canonical selection not established. |
| NJ-08 | Rob Menendez | `H2NJ08232`, `H2NJ13075` | Reviewed canonical `H2NJ08232`: current FEC profile identifies the incumbent; competing record is labeled challenger. Competing ID not grouped. |
| NV-03 | Marty O'Donnell | `H4NV03225`, `H6NV03204` | Unresolved: financial totals differ; person-level equivalence and canonical selection not established. |
| OH-01 | Nathan Weise | `H6OH01229`, `H6OH01237` | Unresolved: person-level equivalence and canonical selection not established. |
| SC-02 | Zyon Khalifa | `H6SC02159`, `H6SC02167` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |
| UT-02 | Carlton E. Bowen | `H6UT02259`, `H6UT02549` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |
| UT-03 | Michael R. Stoddard | `H2UT03355`, `H6UT03224` | Unresolved: 12G flags differ; person-level equivalence and canonical selection not established. |

Canonical evidence (accessed November 2, 2026):

- Rob Menendez: [canonical FEC profile](https://www.fec.gov/data/candidate/H2NJ08232/), [competing profile](https://www.fec.gov/data/candidate/H2NJ13075/), [ballot-source district page](https://theballotbrief.com/district/nj-8). The canonical profile identifies an incumbent with a 2026 statement; the competing profile shows a challenger with a 2005 statement.

- Bob Onder: [canonical FEC profile](https://www.fec.gov/data/candidate/H4MO03221/), [competing profile](https://www.fec.gov/data/candidate/H8MO09146/), [ballot-source district page](https://theballotbrief.com/district/mo-3). The canonical profile identifies the incumbent; the competing record is labeled challenger.

- Mark Harris: [canonical FEC profile](https://www.fec.gov/data/candidate/H4NC08066/), [competing profile](https://www.fec.gov/data/candidate/H6NC09200/), [ballot-source district page](https://theballotbrief.com/district/nc-8). The canonical profile identifies the incumbent; the competing record is labeled challenger.

- Mitch Clemmons remains unresolved after reviewing [one FEC profile](https://www.fec.gov/data/candidate/H2CA38260/), [the competing profile](https://www.fec.gov/data/candidate/H6CA41380/), and [the ballot-source district page](https://theballotbrief.com/district/ca-41). Both profiles describe the same district and a similarly named campaign, but this review did not establish which ID to designate canonical or whether to group them.

The canonical choices are explicit review judgments, not a general rule to prefer incumbent records. Menendez and Onder now retain incumbent values from their reviewed canonical records, while their 12G flags remain false in the committed input. Harris's canonical record also lacks a 12G flag. The competing records' filing evidence has not been transferred because alternate identity equivalence remains unverified. These false values describe the accepted record, not proof that the person did not file.

### Major-party unmatched candidates

The three baseline cases remain open after inspecting the source rows and same-district FEC records:

| District | Candidate | Disposition |
| --- | --- | --- |
| LA-03 | Caleb "With a C" Walker | No plausible same-district FEC record; retain unmatched pending official identity evidence. |
| LA-03 | "Kate" Cotten | No plausible same-district FEC record; retain unmatched pending official identity evidence. |
| MD-04 | George E. McDermott | No plausible same-district FEC record; retain unmatched pending official identity evidence. |

All 147 currently unresolved major-party identities remain individually visible in `candidate-match-review.csv`, with proposed IDs and explanations. No missing mapping has been guessed. The additional cases fall into these inspected evidence categories:

| Reason | Candidates | Disposition |
| --- | --- | --- |
| multiple plausible FEC IDs; review required | 18 | Retain ambiguous; distinguish people or verify alternate IDs before selecting a canonical record. |
| no plausible FEC record in district | 3 | Retain unmatched; source record or district association needs verification. |
| unknown or conflicting party; review required | 2 | Retain unmatched; validate source party code and person identity (MA-08 Burke: 08; MD-05 Chaffee: REO). |
| weak given-name or surname evidence; review required | 124 | Retain unmatched; nickname, initial, compound-name, suffix, or malformed-name evidence needs person-level confirmation. |

### Regeneration and refresh status

Rebuilt `house-general-field.csv`, `candidate-match-review.csv`, and `field-discrepancies.csv` from the committed inputs and registry. There is no local `.env` or `FEC_API_KEY` available in this session. `fec-house-candidates.csv`, `fec-house-candidates-flagged.csv`, `fec-house-general.csv`, and `review-districts.csv` were not refreshed; the latter three still predate the committee-attribution fix. `ballotbrief-house-candidates.csv` and all poll snapshots were also preserved. Public-page review did not constitute an API refresh. Raw snapshots lack recorded retrieval timestamps.

Compared with the previous combined field, changed fields were inspected by identity and match reason:

| Change | Rows |
| --- | --- |
| fec_candidate_id to blank | 264 |
| fec_candidate_id to populated value | 2 |
| filed_12g to blank | 264 |
| filed_12g to populated value | 2 |
| incumbent to blank | 264 |
| incumbent to populated value | 2 |

All populated canonical-ID changes are backed by registry decisions; remaining removed assignments are explained by the per-row match reason. No financial totals were summed. Lower known-incumbent or filing counts reflect withheld matches, not newly verified changes in officeholding or participation.

## Senate and governor field

`build_statewide_field.py` builds the 2026 Senate and governor general-election field offline from `ballotbrief-statewide-candidates.csv`, `fec-senate-candidates-flagged.csv`, `senate-identity-decisions.json`, `2026/polls/us-senate-polls.csv`, and `2026/polls/governor-polls.csv`:

```sh
uv run scripts/build_statewide_field.py
```

It writes three files to `2026/candidates/`: `statewide-general-field.csv`, `statewide-match-review.csv`, and `statewide-field-discrepancies.csv`. It never reads or writes House files. A race is a state and an office, identified as `STATE-SEN` or `STATE-GOV`. The Ballot Brief list has one entry per state and office, so a candidate listed twice for one state and office fails the build: it would mean two contests had been flattened together and could not be told apart. Ohio's and Florida's 2026 Senate races are special elections, and each is that state's only Senate race.

### Statewide schemas

`ballotbrief-statewide-candidates.csv` has `state`, `office` (`Senate` or `Governor`), `name`, `party`, and `source_url` (the Ballot Brief state page). Party labels are abbreviations from the list pages (`D`, `R`, `L`, `NPA`, `I`) or the state page's full names for races read from there.

`statewide-general-field.csv` has the House field's columns in the same order, with `district` replaced by `office` and `race_id`:

| Column | Meaning |
| --- | --- |
| `state`, `office`, `race_id` | Race identity, for example `GA`, `Senate`, `GA-SEN` |
| `name`, `party`, `party_raw` | Ballot name, `DEM`/`REP`/`OTHER`, and the original label |
| `fec_candidate_id` through `cash_on_hand_end_period` | Canonical FEC Senate record's values, as in the House field |
| `in_general_polls` | Appears in a qualifying general-election poll for that office and state |
| `source_url`, `fec_match_status`, `fec_match_reason`, `fec_alternate_ids` | As in the House field |

Governor candidates are not federal candidates and are not in OpenFEC. Their `fec_match_status` is `not_federal`, and their FEC ID, incumbency, `filed_12g`, receipts, and cash on hand are blank. Blank means unknown: it does not mean a governor is not an incumbent or did not raise money. No state campaign-finance source is used, and governor rows never enter the review queue.

Senate rows resolve only against FEC records whose IDs begin with `S`, matched within the state. Some FEC Senate records have a blank district instead of `00`; all are treated as statewide. `statewide-match-review.csv` uses the House review columns with `office` and `race_id` in place of `district`. `statewide-field-discrepancies.csv` has `state`, `office`, `race_id`, `candidate`, and `issue`, with the House issue types plus `in general polls but no race on ballot list` for poll names in a state without that race.

Poll presence uses the House rule and window (cycle 2026, stage `general`, end date on or after September 1, 2026, no `NONE`, `ALL`, or `Generic` answers). The Senate snapshot marks only Senate rows, and the governor snapshot marks only governor rows. The governor snapshot's 2025 Virginia and New Jersey rows are a different cycle and are ignored.

### Senate decisions

`senate-identity-decisions.json` has the House registry's schema plus `"office": "Senate"` on every entry. `district` may be omitted and means `00`. Each registry serves one office: the House builder rejects an entry with a non-House office, and the statewide builder rejects one without `"office": "Senate"`. A Senate decision that names an `H` FEC ID fails as "not a Senate candidacy". All other validation, the review workflow, and the rule that alternates never sum finances are the same as for the House.

### Snapshot review: November 2, 2026

The statewide field has 260 candidates in 71 races (35 Senate, 36 governor): 124 Senate and 136 governor rows. Senate identities are 71 automatic, 45 reviewed, and 8 unmatched. Review performed by Claude Code (automated source review) against the committed FEC Senate file, the FEC candidate profiles, and Ballot Brief state pages. Most automatic misses were legal-name or nickname differences (Thomas/Tom Cotton, Margaret/Peggy Flanagan, Felix Barry Moore, Garland Andy Barr, Ashley Hinson Arenholz), and minor-party labels the matcher does not recognize. Notable judgments:

- Alaska has two Republican Sullivans on the ballot: incumbent Dan Sullivan (`S4AK00214`) and Daniel J. Sullivan Jr. (`S6AK00326`). Both filed 12G reports; each ballot row has its own record.
- South Carolina's Darline Graham maps to `S6SC04437`, not Lindsey Graham's `S0SC00149`. Mississippi's Cindy Hyde-Smith and Texas's Ted Brown also had a second record that shared only a name fragment.
- Florida's Neil J. Gillespie maps to `S6FL00863`, which FEC spells GILESPIE.
- Colorado's Bob Chew has two records with identical totals. `S6CO00549` is canonical because its party code is Forward Party. The other record (`S6CO00556`) is not asserted as an alternate, so it appears in the discrepancies as an unresolved 12G filer.
- Idaho's Jim Risch has FEC party code `UNK`, and New Hampshire's Edmond Laplante has `RNC` against the ballot's Constitution label. Both are unique exact-name records and are treated as source coding gaps.

The 8 unresolved candidates have no FEC Senate record under any spelling: Blake Huber and Christopher Baum (CO), Curtis Stinnett and Sevier White (OK), Mark Hackett (SC), and Andrew Gerena, James William Macon III, and Jeremy Dean Hearn (TN). All are minor-party or independent candidates, who may not have reached the FEC registration threshold.

Remaining discrepancies are expected. 12G filers absent from the ballot are primary losers who filed before their primaries were settled (for example John Cornyn in Texas and Daniel Cameron in Kentucky). Some poll names are absent from the ballot because they come from hypothetical or primary-season general-election questions. Idaho, Nebraska, and South Dakota have no Democratic Senate candidate, and Nebraska's principal opponent is independent Dan Osborn.
