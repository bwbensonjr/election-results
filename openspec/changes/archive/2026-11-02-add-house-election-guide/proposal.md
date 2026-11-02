# Proposal

## Why

`2026/guide/election-night-guide-november-3-2026.md` is a written viewing guide for election night. It names 44 House districts with a watch time, a role in the night (bellwether, wave-ladder rung, battleground, tsunami tell, and so on), the candidates by surname, cited Cook ratings, and signals for good and bad nights. All of this is narrative markdown, so none of it can be filtered or sorted next to the district data the repository already builds: partisan history, Cook PVI, and the polling average. A structured CSV joined by district puts the guide's watch list and its signals in the same row as the numbers.

## What Changes

- Add a curated CSV, `2026/guide/election-night-guide-house.csv`, transcribed from the guide markdown, with one row for each House district the guide names. Columns:
  - watch time (Eastern)
  - guide section
  - a role from a controlled vocabulary
  - the wave-ladder tier that a Democratic win in the district signals
  - Chuck Todd's seat-count signal, where given
  - the Democratic and Republican names as the guide gives them
  - incumbent and rating notes
  - the guide's **HELL YES**, **FFS**, and **CHILL** signal text
  - a free-form note
- Validate the CSV offline:
  - exact columns, controlled vocabularies, and district IDs that are well-formed, unique, and present in the candidate field
  - the set of district IDs must equal the set of House district IDs that appear in the guide markdown, so a guide edit that adds or drops a district fails the build until the CSV is updated
- Append the guide columns, a `guide_status` (`in_guide` / `not_in_guide`), and a guide-to-field name check (`matched` / `mismatch` / `not_named`) to the end of both district context exports. Districts the guide doesn't mention keep blank guide columns.
- Keep the guide optional for strict builds: `--require-complete` does not require guide coverage.
- Document the transcription conventions, schema, vocabularies, and the re-transcription step after guide edits.

## Capabilities

### New Capabilities

- `election-guide-house`: The curated, validated House portion of the election-night guide as a district-grain CSV, kept consistent with its markdown source.

### Modified Capabilities

- `house-district-context`: The exports gain the election-guide columns, the guide status, and the name check. Guide validation failures block publication, and strict completeness does not depend on the guide. These are added requirements; existing requirement text is unchanged.

## Impact

- New `2026/guide/election-night-guide-house.csv`, transcribed once during implementation from the committed markdown.
- New `scripts/election_guide.py`, a standard-library validator and loader with a small CLI, plus its tests.
- `scripts/build_house_district_context.py` gains a `--guide` option, and both context CSVs gain trailing columns. Existing columns, their positions, values, and row counts do not change.
- Updated docs: `docs/district-data.md` and `README.md`.
- No new network access, credentials, or dependencies.

Out of scope:
- The guide's Senate and governor races, the House-wide seat ladder as a separate table, and poll-closing times for districts the guide doesn't name.
- Parsing the free-form markdown automatically.
- Any change to candidate identities, polling averages, or the guide markdown itself.
