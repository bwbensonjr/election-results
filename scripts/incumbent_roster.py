"""Load and validate the reviewed 2026 incumbent roster and compute each race's ballot status."""

import json
from datetime import date
from pathlib import Path

from build_house_field import poll_candidates
from district_history import ROOT

DEFAULT_ROSTER = ROOT / "2026/roster/incumbent-roster.json"
SOURCE_ID = "incumbent-roster-2026"
PARTIES = {"D", "R", "I"}
OFFICES = {"House", "Senate", "Governor"}
RACE_COLUMNS = [
    "roster_incumbent_name", "roster_incumbent_party", "roster_vacant", "roster_ballot_status",
    "open_seat", "roster_source_id",
]
CANDIDATE_COLUMNS = RACE_COLUMNS + ["roster_incumbent"]


def require_text(entry, field):
    if not isinstance(entry.get(field), str) or not entry[field].strip():
        raise ValueError(f"missing or invalid {field}")


def ballot_status(entry, rows):
    """Return (status, matched field row or None) for one validated roster entry."""
    if entry.get("vacant"):
        return "", None
    override = entry.get("ballot_status_override")
    if override == "not_running":
        return "not_running", None
    if override == "running":
        matches = [r for r in rows if r["name"] == entry["override_candidate"]]
        if len(matches) != 1:
            raise ValueError(f"override_candidate {entry['override_candidate']!r} is not in the race's field")
        return "running", matches[0]
    matches = poll_candidates(entry["name"], rows)
    return ("running", matches[0]) if len(matches) == 1 else ("not_running", None)


def load_roster(path, races, offices=OFFICES):
    """Validate the roster's entries for `offices` against {race_key: (office, field rows)}.

    Returns {race_key: incumbency}. Entries for other offices are left to their own builds.

    Each incumbency has name, party, vacant, status (`running`, `not_running`, or blank when
    vacant), open_seat, and candidate (the matched field row's name, or "").
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError(f"{path}: expected schema_version 1 and an entries list")
    result = {}
    for index, entry in enumerate(data["entries"], 1):
        label = f"{path} entry {index}"
        try:
            if not isinstance(entry, dict):
                raise ValueError("must be an object")
            key = entry.get("race_key")
            label += f" ({key})"
            if entry.get("office") not in OFFICES:
                raise ValueError(f"office must be one of {sorted(OFFICES)}")
            if entry["office"] not in offices:
                continue
            if key not in races:
                raise ValueError("unknown race key")
            if key in result:
                raise ValueError("duplicate race key")
            office, rows = races[key]
            if entry.get("office") != office:
                raise ValueError(f"office must be {office}")
            for field in ["reviewed_by", "reviewed_at"]:
                require_text(entry, field)
            date.fromisoformat(entry["reviewed_at"])
            evidence = entry.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(e, str) and e for e in evidence):
                raise ValueError("missing evidence references")
            if entry.get("vacant") is True:
                if entry.get("name") or entry.get("party") or "ballot_status_override" in entry:
                    raise ValueError("a vacant entry has blank name and party and no override")
            elif entry.get("vacant") is False:
                require_text(entry, "name")
                if entry.get("party") not in PARTIES:
                    raise ValueError(f"party must be one of {sorted(PARTIES)}")
            else:
                raise ValueError("vacant must be true or false")
            override = entry.get("ballot_status_override")
            if override not in (None, "running", "not_running"):
                raise ValueError("ballot_status_override must be running or not_running")
            if override:
                require_text(entry, "override_rationale")
            if override == "running":
                require_text(entry, "override_candidate")
            status, candidate = ballot_status(entry, rows)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
        result[key] = dict(name=entry.get("name", ""), party=entry.get("party", ""), vacant=entry["vacant"],
                           status=status, open_seat=status != "running",
                           candidate=candidate["name"] if candidate else "")
    missing = sorted(set(races) - set(result))
    if missing:
        raise ValueError(f"{path}: no roster entry for {len(missing)} races, e.g. {', '.join(missing[:5])}")
    return result


def race_values(incumbency):
    """Return the race-grain roster columns for one incumbency."""
    return dict(roster_incumbent_name=incumbency["name"], roster_incumbent_party=incumbency["party"],
                roster_vacant=str(incumbency["vacant"]), roster_ballot_status=incumbency["status"],
                open_seat=str(incumbency["open_seat"]), roster_source_id=SOURCE_ID)


def candidate_flag(incumbency, row):
    """Return the candidate-grain roster flag: true only on the matched, running incumbent's row."""
    return str(incumbency["status"] == "running" and row["name"] == incumbency["candidate"])
