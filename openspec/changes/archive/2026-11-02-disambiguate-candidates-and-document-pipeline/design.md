# Design

## Context

See `proposal.md` for motivation. The current scripts use PEP 723 dependency metadata and run through `uv`; the final merge uses only the standard library. There are no existing main specs or automated tests. `build_house_field.py` uses the same first-match helper for FEC records, poll names, and discrepancy checks. `flag_general_candidates.py` maps each committee to only one candidate ID, so later API records overwrite earlier links.

The existing snapshot contains 18 ambiguous ballot identities under the current matching heuristic. Examples include Rob Menendez (NJ-08), Bob Onder (MO-03), Mark Harris (NC-08), and Mitch Clemmons (CA-41). These are review targets, not verified canonical mappings. Alternate records disagree on incumbency and filing flags. The new conservative matcher may expose additional cases beyond those 18.

## Goals / Non-Goals

**Goals:** Make identity decisions inspectable, repeatable, and safe across refreshed CSV inputs; preserve candidate coverage and the lightweight script workflow; document both an offline rebuild and network-dependent refresh.

**Non-Goals:** Automatic fuzzy matching, name-based global person deduplication, summing campaign finances across FEC IDs, or asserting that every discrepancy is a data error. Scope exclusions in the proposal also apply.

## Decisions

### 1. Separate candidate discovery from accepted identity resolution

Add a small standard-library identity module used by the builder. Parse FEC comma-separated names explicitly, normalize accents/punctuation/suffixes, and preserve given-name and surname roles. Normalize known party equivalents, including DFL. Restrict automatic matching to a unique state/district/party-compatible record with matching full given name and surname. Initials, nicknames, compound-name uncertainty, unknown party codes, or surname-only evidence go to review. Retain broader plausible candidates for the report, even when none qualifies automatically. Sort candidates by ID and never resolve a tie by ordering.

An explicit reviewed mapping takes precedence. No plausible records yields `unmatched`; one weak plausible record also stays `unmatched` with a review reason; multiple plausible identities yield `ambiguous`. A unique eligible record is accepted only when no competing plausible identity remains. Keep poll-name resolution separate; report ambiguous poll associations and do not let them choose FEC IDs.

Alternative: score fuzzy matches and select the highest score. Rejected because an apparently confident score can conceal incorrect identity and requires tuning without a trusted reference set.

### 2. Store reviewed decisions in a small JSON registry

Use `2026/candidates/candidate-identity-decisions.json` with a schema version and a list of decisions. Each decision includes `cycle`, `state`, `district`, exact source `ballot_name`, `decision` (`match` or `unmatched`), `canonical_fec_id`, `alternate_fec_ids`, `evidence` (source references), `rationale`, `reviewed_by`, and ISO `reviewed_at`. Unmatched decisions have no IDs. Normalize district formatting consistently but do not silently rewrite ballot names to find stale decisions.

Validate the entire registry against the inputs before writing outputs: reject duplicate keys, reused IDs, nonexistent records, scope conflicts, malformed decisions, and missing review metadata. A party discrepancy can be resolved explicitly with evidence and rationale; it cannot become an automatic match. Do not infer a reviewer or fabricate evidence. A source name or district change requires renewed review rather than carrying a decision forward silently.

The canonical record supplies incumbency and financial values. Reviewed alternate IDs represent the same ballot identity for discrepancy checks and 12G evidence. `filed_12g` is true if any reviewed member ID has the flag. Do not merge finances or choose each favorable field from a different record. Conflicting incumbency is resolved by the documented canonical selection, not by an automatic OR operation.

Alternative: hard-code exceptions in Python or edit generated CSVs. Rejected because neither provides a clean, durable review trail. JSON avoids adding a parser dependency and handles alternate-ID lists directly.

### 3. Fix committee link cardinality at the source

Represent committee links as sets of candidate IDs and preserve all links returned by both candidate search and committee fallback. Limit flag assignment to IDs present in the candidate input. Select the latest qualifying report across all linked committees per candidate using receipt date, then report identifier for ties. Explain the deterministic tie policy in the pipeline reference. Do not infer that unrelated people sharing a committee are the same person; alternate-ID grouping still requires review.

Alternative: patch filing flags only in the final builder. Rejected because it leaves `fec-house-general.csv` and `review-districts.csv` dependent on overwritten links.

### 4. Publish explicit status and a stable review report

Keep existing field columns and append `fec_match_status`, `fec_match_reason`, and `fec_alternate_ids` (semicolon-separated, sorted). Status values are `automatic`, `reviewed`, `reviewed_unmatched`, `unmatched`, and `ambiguous`. Unresolved or reviewed-unmatched rows have blank FEC-derived values, preserving the distinction between unknown and false.

Add `candidate-match-review.csv`, sorted by state, district, ballot name, and proposed FEC ID. Use one row per plausible record, or a single blank-record row when none exists. Include ballot identity, match status/reason, FEC ID/name/party, incumbency, 12G flag, receipts, cash on hand, financial coverage end, and any applicable decision evidence. Keep existing discrepancy reports, but use resolved identities and reviewed alternates for FEC-to-ballot membership checks. Ambiguous membership remains explicit rather than being treated as a confirmed match. Expected one-party races remain review information.

Validate inputs and decisions before publishing any output. Build in memory or stage files in the destination directory before replacement. Unresolved identities are valid reported results and do not themselves cause a nonzero exit; invalid decisions do.

Alternative: fail every run on an ambiguous candidate. Rejected because a usable full ballot list should still be available with explicit unknowns.

### 5. Make the human review loop concrete

1. Rebuild the report from checked-in inputs without credentials.
2. Inspect each ambiguity and major-party unmatched row, comparing FEC candidate/committee records, official ballot or candidate sources, and available filing evidence.
3. Record a canonical ID, reviewed alternate IDs, or a reviewed-unmatched decision with sources and rationale. If evidence is insufficient, leave the case unresolved and record the reason in the documented review summary.
4. Validate the registry and rebuild; review status changes and incumbent/filing changes explicitly.
5. Commit decisions with regenerated outputs so the result is reproducible. Revalidate on every subsequent refresh.

Completion does not require inventing a mapping for every candidate. Every one of the 18 baseline ambiguous cases must receive a documented disposition: reviewed resolution, reviewed-unmatched decision, or a clearly explained remaining ambiguity.

### 6. Document the pipeline where users enter the project

Update `README.md` with implemented versus planned features, the primary output, prerequisites, execution order, and a link to `docs/candidate-pipeline.md`. The reference covers all four scripts and seven candidate CSVs, the new decision registry and review report, relevant polling inputs, schemas, boolean/blank semantics, financial units and coverage dates, sources, and credentials without secrets.

Show these commands from the repository root:

```sh
uv run scripts/fetch_fec_house_candidates.py --totals
uv run scripts/flag_general_candidates.py
uv run scripts/fetch_ballotbrief_house.py
uv run scripts/build_house_field.py
```

Explain that the builder alone runs offline against committed inputs; a full refresh needs network access and a real `FEC_API_KEY` for flagging. `--totals` is required for the documented financial merge. Poll CSVs currently have no refresh script; document their manual acquisition and available provenance without inventing an export URL or retrieval timestamp. Distinguish report coverage dates from retrieval dates. Identify Ballot Brief as the implemented ballot source and Ballotpedia as an additional reference.

Document the September 1, 2026 poll cutoff as a fixed heuristic, the meaning of `in_general_polls`, filing flags as corroborating evidence rather than ballot certification, incomplete minor-party FEC coverage, jurisdiction-specific election rules, and the absence of presidential results/PVI and a separate district incumbent roster. Present snapshot counts as dated observations, not permanent invariants.

Alternative: keep instructions in script docstrings alone. Rejected because the scripts do not explain the end-to-end workflow or review responsibilities.

## Risks / Trade-offs

- Conservative matching creates more blank fields and manual work. Mitigation: make the review queue actionable, prioritize major-party candidates, and retain all ballot rows.
- Reviewed mappings can become stale. Mitigation: validate keys and IDs on every build and fail before replacing outputs.
- Source records can remain contradictory. Mitigation: require evidence, keep unresolved outcomes visible, and avoid fabricated canonical choices.
- Alternate IDs can duplicate financial totals. Mitigation: read finances from the canonical record only and expose alternate IDs.
- Schema additions and changed values affect downstream readers. Mitigation: retain existing columns, document additions and unknown values, and review regenerated diffs.
- Existing polling provenance is incomplete. Mitigation: document what is known and explicitly identify unknown retrieval details.

## Migration Plan

Implement and test resolution and committee handling with offline fixtures first. Generate the new review report, review baseline ambiguities, and regenerate the builder outputs from checked-in inputs. Refresh FEC-derived files when credentials and network access are available; otherwise explicitly record that committee-related snapshots await refresh rather than implying they were updated. Preserve 435-district/1,159-row ballot coverage for the unchanged snapshot; refreshes may legitimately change counts.

Validate deterministic outputs under shuffled FEC inputs, registry failures without overwritten outputs, and the documented offline command. Review all changed identity/incumbency/filing values and unresolved dispositions. Reverting the implementation, decision registry, documentation, and generated files together restores the previous behavior; raw input snapshots remain available in Git.
