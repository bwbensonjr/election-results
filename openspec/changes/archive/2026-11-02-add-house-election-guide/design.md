# Design

## Context

See `proposal.md` for motivation and `specs/` for the required behavior.

Observed in the committed guide (`2026/guide/election-night-guide-november-3-2026.md`, current as of November 1, 2026):

- **Districts.** The guide references 44 distinct House districts in `XX-n` form. All 44 exist in the candidate field. Mentions run from one to four per district; VA-1 has four, and KY-6, IN-5, VA-2, and ME-2 have three each.
- **Time sections.** The 6:00, 7:00, 7:30, 8:00, 9:00, "10 to 11", and "12:00+" ET sections carry House races, often with an explicit time. For example, IN-1 sits in the 6:00 section but is marked "· 7:00".
- **Signals.** These are bulleted **HELL YES**, **FFS**, and **CHILL** lines. Some apply to one district, and some pair several districts, such as "FL-14 Castor and FL-25 Moskowitz both hold".
- **Seat ladder.** The "How big is this thing?" table assigns district outcomes to four tiers: We'll take it, Solid, 2018-style, and Holy shit. Some cells cite Todd seat counts: KY-6 230+, VA-1 ~235, VA-5 ~250.
- **Candidates.** Candidates appear by surname with a party letter, for example `Alvarado (R) v Dembo (D)`, or as "NC-1 Davis (D)". Some districts name only one candidate, and lists such as "House battlegrounds at 9:00" name only the incumbent.
- **Ratings and margins.** Cook ratings and Trump 2024 margins appear in the prose, for example "Cook Lean D" and "Trump +15 in 2024".

`build_house_district_context.py` already appends the poll columns at the end of both exports, and it verifies the saved averages before it publishes. `build_house_field.poll_candidates` implements the surname-plus-first-initial match.

## Goals / Non-Goals

**Goals:**
- A faithful, reviewable transcription.
- Validation that catches drift between the CSV and the markdown.
- Join output that is easy to filter on election night.

**Non-Goals:**
- Natural-language parsing of the markdown.
- Rewriting or fact-checking the guide's claims.
- Reconciling guide ratings with Cook PVI.
- Statewide races.

## Decisions

### 1. Curated CSV checked against the markdown, not a parser

The guide is free-form prose with tables, bullets, and inline lists. A parser would be brittle and would still need hand-written rules for each pattern. Instead, implementation transcribes the guide once into `2026/guide/election-night-guide-house.csv`. Validation then enforces the mechanical invariant: the CSV's district IDs equal the district IDs found by the regex `\b([A-Z]{2})-(\d{1,2})\b` in the markdown, normalized with `district_history.district_key`. Edits that add or remove districts in the markdown are therefore caught. Wording edits to districts that are already listed are not caught; the docs state that limitation and the re-transcription step.

Alternative considered: storing the markdown's SHA-256 so that any guide edit fails the build. This was rejected for now because the guide is the user's working document. Failing on typo fixes would be noisy, and the district-set check targets the change that would break the join.

### 2. Guide CSV schema

Columns, in order:

| Column | Content |
| --- | --- |
| `district_id` | Canonical ID, e.g. `KY-06`, `AK-AL` |
| `guide_watch_time_et` | One of `6:00`, `7:00`, `7:30`, `8:00`, `9:00`, `10:00`, `11:00`, `12:00+`. This is the race's own marked time when the guide gives one (IN-1 `7:00`), otherwise its section's time. In the "10 to 11" section, Nevada and Montana use `10:00`; California and Washington use `11:00`, per the section's state list. |
| `guide_section` | Heading under which the district appears, e.g. `Virginia ladder`, `House battlegrounds at 9:00` |
| `guide_role` | `bellwether`, `wave_ladder`, `battleground`, `majority_check`, `hold_check`, `stretch`, `reach`, or `tsunami_tell` |
| `guide_dem_win_tier` | Blank, or the seat-ladder tier that lists a Democratic win or flip in this district: `We'll take it`, `Solid`, `2018-style`, or `Holy shit` |
| `guide_seat_signal` | Todd seat count tied to the district, verbatim (`230+`, `~235`, `~250`), else blank |
| `guide_dem_name`, `guide_rep_name` | Surnames or names exactly as the guide writes them, else blank |
| `guide_incumbent_note` | E.g. `open, R`, `Spartz, R` |
| `guide_rating_note` | Ratings and partisanship notes as cited, e.g. `Cook Lean D`, `Trump +15 in 2024; polls roughly tied` |
| `guide_hell_yes`, `guide_ffs`, `guide_chill` | The signal text that applies to this district. Several bullets are joined with ` | `. A bullet that pairs districts is copied to each of them. |
| `guide_note` | Other district-specific context, e.g. `Watch Hamilton County (Trump 52 to 46 in 2024)` |

The role vocabulary follows the guide's own framing. Each district gets the most specific role the guide gives it, in this precedence order:

`bellwether` > `wave_ladder` > `majority_check` > `battleground` > `stretch` > `reach` > `tsunami_tell` > `hold_check`

Examples:
- `bellwether`: KY-6.
- `wave_ladder`: VA-1, VA-2, and VA-5.
- `majority_check`: seats the guide ties to majority odds, such as FL-14, FL-25, NC-1, NC-11, and OH-7.
- `tsunami_tell`: SC-1, SC-2, NC-9, and OH-15.

The ladder tier and seat signal carry the remaining structure. Values are stored as UTF-8 with LF endings and plain ASCII punctuation. Bold markers are dropped, and the guide's words are otherwise kept as written.

### 3. Validator module and CLI

`scripts/election_guide.py` holds the guide logic:

- Constants: `GUIDE_COLUMNS`, `ROLES`, `TIERS`, and `WATCH_TIMES`.
- `load_guide(guide_csv, guide_md, candidate_path)` reads and validates the guide, then returns rows keyed by district.
- `name_check(row, field_rows)` compares guide names with the field.
- A `main()` validates without writing anything, so the guide can be checked right after editing it with `uv run scripts/election_guide.py`.

Validation order: exact columns, then per-row vocabulary, then unique IDs, then field membership, then the markdown district-set comparison. Each failure raises `ValueError` naming the row and field, or the districts involved.

### 4. Name check

`guide_dem_name` is matched against the district's `DEM` field rows, and `guide_rep_name` against its `REP` rows, using `poll_candidates`. Each name must produce exactly one hit. Blank names are skipped. The result is:

- `not_named` if both names are blank
- `matched` if every given name hits once
- `mismatch` otherwise

The check is computed at join time from the current candidate field, so a field refresh updates it without editing the guide CSV.

### 5. Join

`build_house_district_context.py` gains `--guide` and `--guide-markdown` paths, defaulting to the committed files. It loads the guide before publishing. Its added columns are:

`GUIDE_COLUMNS[1:] + ["guide_name_check", "guide_status", "guide_source_id"]`

They are appended after the poll columns in both exports. `guide_source_id` is `election-night-guide-2026-11-03` on every row. All other added values are blank for `not_in_guide` districts, which add no issue rows and play no part in `--require-complete`.

## Risks / Trade-offs

- **Transcription errors or omissions in free text.** → The district-set check guarantees coverage. Tests spot-check representative rows (KY-06, VA-01, IN-01, FL-14) against the guide wording. The CSV is committed for review.
- **Wording edits to the guide go undetected.** → The docs say to re-transcribe after editing a listed district, and the name check catches candidate changes.
- **Multi-district bullets are duplicated across rows.** → This is intentional: each district row stands alone. The docs note the duplication.
- **Role precedence flattens districts with several roles.** → The tier, seat signal, and signal text keep the remaining detail.

## Migration Plan

The new rebuild order:

1. `build_house_field.py`
2. `normalize_district_history.py`
3. `build_house_poll_averages.py`
4. `build_house_district_context.py`, which now also reads the guide

Commit the guide CSV with the regenerated context exports. Rolling back means reverting the commit.
