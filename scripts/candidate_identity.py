"""Conservative, auditable ballot-to-FEC identity resolution (no network I/O)."""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

CYCLE = 2026
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "mr", "mrs", "ms", "dr"}
PARTIES = {
    "rep": "REP", "r": "REP", "republican": "REP",
    "prefers republican party": "REP",
    "dem": "DEM", "d": "DEM", "democrat": "DEM", "democratic": "DEM",
    "prefers democratic party": "DEM", "democratic farmer labor": "DEM", "dfl": "DEM",
    "lib": "LIB", "libertarian": "LIB", "grn": "GRN", "green": "GRN",
    "ind": "IND", "independent": "IND", "unaffiliated": "IND",
    "con": "CON", "constitution": "CON", "iap": "IAP", "independent american": "IAP",
}


def fold(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z ]", " ", value.lower()).split())


def party_code(value):
    return PARTIES.get(fold(value), "")


def name_parts(value):
    """Return given-name and surname token tuples, preserving comma roles."""
    def tokens(text):
        return tuple(t for t in fold(text).split() if t not in SUFFIXES)
    if "," in value:
        surname, given = value.split(",", 1)
        if not tokens(given):
            return name_parts(surname)
        return tokens(given), tokens(surname)
    parts = tokens(value)
    return parts[:-1], parts[-1:]


def district(value):
    return value.zfill(2) if value.isdigit() else value


def ballot_key(row):
    return (CYCLE, row["state"], district(row["district"]), row["name"])


def scope(row):
    return row["state"], district(row["district"])


@dataclass
class Resolution:
    status: str
    reason: str
    candidates: list
    canonical: dict | None = None
    alternates: tuple = ()
    evidence: tuple = ()

    @property
    def member_ids(self):
        if not self.canonical:
            return set()
        return {self.canonical["candidate_id"], *self.alternates}

    @property
    def filed_12g(self):
        if not self.canonical:
            return ""
        return any(c.get("filed_12g") in (True, "True")
                   for c in self.candidates if c["candidate_id"] in self.member_ids)


def discover(ballot, records):
    """Retain broad surname evidence for review; never accept weak evidence."""
    _, surname = name_parts(ballot["name"])
    result = []
    for record in records:
        if scope(record) != scope(ballot):
            continue
        other_given, other_surname = name_parts(record["name"])
        # Include inverted/malformed FEC names and compound surname fragments
        # as review suggestions, without treating them as confirmed matches.
        if surname and set(surname) & set(other_given + other_surname):
            result.append(record)
    return sorted(result, key=lambda c: c["candidate_id"])


def resolve(ballot, records, decisions=None):
    candidates = discover(ballot, records)
    decision = (decisions or {}).get(ballot_key(ballot))
    if decision:
        evidence = tuple(decision["evidence"])
        if decision["decision"] == "unmatched":
            return Resolution("reviewed_unmatched", decision["rationale"], candidates,
                              evidence=evidence)
        by_id = {r["candidate_id"]: r for r in records}
        canonical = by_id[decision["canonical_fec_id"]]
        alternates = tuple(sorted(decision["alternate_fec_ids"]))
        members = {canonical["candidate_id"], *alternates}
        candidates = sorted({r["candidate_id"]: r for r in
                             candidates + [by_id[cid] for cid in members]}.values(),
                            key=lambda c: c["candidate_id"])
        reason = (f"canonical {canonical['candidate_id']}; alternates "
                  f"{';'.join(alternates) or 'none'}; {decision['rationale']}")
        return Resolution("reviewed", reason, candidates, canonical, alternates, evidence)
    if len(candidates) > 1:
        return Resolution("ambiguous", "multiple plausible FEC IDs; review required", candidates)
    if not candidates:
        return Resolution("unmatched", "no plausible FEC record in district", [])
    candidate = candidates[0]
    given, surname = name_parts(ballot["name"])
    fec_given, fec_surname = name_parts(candidate["name"])
    # A compound FEC surname can establish the same explicit trailing words
    # on a ballot name without guessing where the surname starts.
    full_ballot = given + surname
    if fec_surname and full_ballot[-len(fec_surname):] == fec_surname:
        given, surname = full_ballot[:-len(fec_surname)], fec_surname
    compatible = party_code(ballot["party"])
    if not compatible or compatible != party_code(candidate["party"]):
        return Resolution("unmatched", "unknown or conflicting party; review required", candidates)
    if (not given or not fec_given or len(given[0]) < 2 or given[0] != fec_given[0]
            or surname != fec_surname):
        return Resolution("unmatched", "weak given-name or surname evidence; review required", candidates)
    return Resolution("automatic", "unique full given-name, surname, and party match",
                      candidates, candidate)


def load_decisions(path, ballot, records):
    """Validate all decisions before any output can be published."""
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("identity registry: schema_version must be 1")
    if not isinstance(data.get("decisions"), list):
        raise ValueError("identity registry: decisions must be a list")
    by_id = {r["candidate_id"]: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("FEC input: duplicate candidate IDs")
    ballot_keys = {ballot_key(b) for b in ballot}
    decisions, claimed = {}, set()
    for index, entry in enumerate(data["decisions"]):
        label = f"identity decision {index + 1}"
        try:
            if not isinstance(entry, dict):
                raise ValueError("must be an object")
            for key in ("state", "district", "ballot_name", "decision", "rationale", "reviewed_by", "reviewed_at"):
                if not isinstance(entry.get(key), str) or not entry[key].strip():
                    raise ValueError(f"missing or invalid {key}")
            label += f" ({entry['state']}-{entry['district']} {entry['ballot_name']})"
            if type(entry.get("cycle")) is not int or entry["cycle"] != CYCLE:
                raise ValueError("wrong cycle")
            date.fromisoformat(entry["reviewed_at"])
            evidence = entry.get("evidence")
            if not isinstance(evidence, list) or not evidence or any(
                not isinstance(e, str) or not e.strip() for e in evidence
            ):
                raise ValueError("missing evidence references")
            key = (entry["cycle"], entry["state"], district(entry["district"]), entry["ballot_name"])
            if key not in ballot_keys:
                raise ValueError("absent ballot row or state/district conflict")
            if key in decisions:
                raise ValueError("duplicate decision key")
            alternates = entry.get("alternate_fec_ids")
            if not isinstance(alternates, list) or any(not isinstance(cid, str) or not cid for cid in alternates):
                raise ValueError("alternate_fec_ids must be a list of IDs")
            canonical = entry.get("canonical_fec_id")
            if entry["decision"] == "unmatched":
                if canonical != "" or alternates:
                    raise ValueError("unmatched decision must have no IDs")
                ids = []
            elif entry["decision"] == "match":
                if not isinstance(canonical, str) or not canonical:
                    raise ValueError("missing canonical_fec_id")
                ids = [canonical, *alternates]
            else:
                raise ValueError("decision must be match or unmatched")
            if len(set(ids)) != len(ids) or set(ids) & claimed:
                raise ValueError("duplicate or reused FEC ID")
            for cid in ids:
                if cid not in by_id:
                    raise ValueError(f"nonexistent FEC ID {cid}")
                if scope(by_id[cid]) != key[1:3]:
                    raise ValueError(f"state/district conflict for {cid}")
            claimed.update(ids)
            decisions[key] = entry
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return decisions
