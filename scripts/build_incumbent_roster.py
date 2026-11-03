# /// script
# requires-python = ">=3.11"
# ///
"""Seed the 2026 incumbent roster from saved sources and write its review report, offline.

Run from the repository root: uv run scripts/build_incumbent_roster.py
The committed roster is reviewed after seeding. Once it exists, a run only rewrites the review
report, marking each row resolved when the committed entry has a reviewer other than the seed;
--reseed replaces the roster. See docs/district-data.md for the roster's meaning and review steps.
"""

import argparse
import csv
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from candidate_identity import name_parts
from district_history import ROOT, STATE_NAMES, district_key, publish_csvs, read_records

ROSTER_DIR = ROOT / "2026/roster"
DEFAULT_ROSTER = ROSTER_DIR / "incumbent-roster.json"
SEED_REVIEWER = "seed (scripts/build_incumbent_roster.py)"
REVIEW_COLUMNS = ["race_key", "office", "issue", "roster_name", "detail", "resolved_by"]
COOK_URL = "https://www.cookpolitical.com/cook-pvi/2026-partisan-voting-index/district-map-and-list"
SENATE_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
NGA_URL = "https://www.nga.org/governors/"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_current_United_States_governors"


def default_paths(root=ROOT):
    return dict(
        house_field=root / "2026/candidates/house-general-field.csv",
        statewide_field=root / "2026/candidates/statewide-general-field.csv",
        cook=root / "2026/results/cook-pvi-2026-source.csv",
        presidential=root / "2026/results/presidential-results-by-us-house-district-2020-2024.csv",
        senators=root / "2026/roster/sources/senators.xml",
        nga=root / "2026/roster/sources/nga-governors.html",
        wikipedia=root / "2026/roster/sources/wikipedia-current-governors.wikitext",
    )


def surname(name):
    return name_parts(name)[1]


def presidential_holders(path):
    """Return {district_id: (name, party)} from the presidential source's incumbent labels."""
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream))[2:]
    return {district_key(r[0])[2]: (r[1].strip(), r[2].strip("() ")) for r in rows}


def senators(path):
    """Return {state: [(name, party, class)]} from the Senate's member XML."""
    by_state = {}
    for member in ET.parse(path).getroot().iter("member"):
        text = {field: member.findtext(field, default="").strip()
                for field in ["first_name", "last_name", "state", "party", "class"]}
        by_state.setdefault(text["state"], []).append(
            (f"{text['first_name']} {text['last_name']}", text["party"], text["class"]))
    return by_state


def nga_governors(path):
    """Return {state: name} from the saved NGA current-governors page."""
    text = Path(path).read_text(encoding="utf-8")
    found = re.findall(r'<small class="state">([^<]+)</small>\s*Gov\.\s+([^<]+?)\s*</div>', text)
    return {STATE_NAMES[html.unescape(s).strip()]: html.unescape(n).strip()
            for s, n in found if html.unescape(s).strip() in STATE_NAMES}


def wikipedia_governors(path):
    """Return {state: (name, party)} from the saved wikitext of the current-governors list."""
    text = Path(path).read_text(encoding="utf-8")
    result = {}
    for block in re.split(r"\n\|-[^\n]*\n", text):
        state = re.match(r"\|\[\[Governor of ([^|\]]+)\|", block)
        name = re.search(r"\{\{sortname\|([^|}]+)\|([^|}]+)", block)
        # Minnesota's Democratic-Farmer-Labor Party is the Democratic Party's state affiliate.
        party = re.search(r"\{\{party color\|(?:Minnesota )?(Republican|Democratic|Independent)", block)
        if state and name and party and state[1] in STATE_NAMES:
            result[STATE_NAMES[state[1]]] = (f"{name[1]} {name[2]}", party[1][0])
    return result


def seed(paths):
    """Return (roster entries, review rows) built from the saved sources."""
    _, house = read_records(paths["house_field"])
    _, statewide = read_records(paths["statewide_field"])
    _, cook = read_records(paths["cook"])
    cook = {district_key(r["Dist"])[2]: r for r in cook}
    pres = presidential_holders(paths["presidential"])
    field = {}
    for row in house:
        field.setdefault(district_key(f"{row['state']}-{row['district']}")[2], []).append(row)
    races = {}
    for row in statewide:
        races.setdefault(row["race_id"], (row["state"], row["office"]))
        field.setdefault(row["race_id"], []).append(row)
    entries, review = [], []

    def flag(key, office, issue, name, detail):
        review.append(dict(race_key=key, office=office, issue=issue, roster_name=name, detail=detail))

    for key in sorted(k for k in field if k not in races):
        row = cook.get(key)
        if row is None:
            raise ValueError(f"{paths['cook']}: no Cook row for {key}")
        label, party = row["Incumbent"].strip(), row["Incumbent Party"].strip()
        entry: dict = dict(race_key=key, office="House", name=label, party=party, vacant=False,
                     evidence=[f"{COOK_URL} ({key}: {label}, {party})"], reviewed_by=SEED_REVIEWER,
                     reviewed_at="2026-11-02")
        held = pres.get(key, ("", ""))
        opened = re.fullmatch(r"OPEN \((.+)\)", label)
        if opened:
            departing = opened[1]
            entry["name"] = held[0] if held[0] and surname(held[0]) == surname(departing) else departing
            entry["ballot_status_override"] = "not_running"
            entry["override_rationale"] = f"Cook marks {key} OPEN; {departing} is not seeking this seat."
            if entry["name"] == departing:
                flag(key, "House", "open_seat_name", departing, "Full name not in presidential source; complete it")
        elif label.upper().startswith("VACANT"):
            former = re.fullmatch(r"VACANT \((.+)\)", label)
            entry.update(name="", party="", vacant=True, previous_party=party,
                         previous_holder=former[1] if former else "")
            flag(key, "House", "vacant", label, "Confirm vacancy with evidence")
        else:
            if held[0] and surname(held[0]) != surname(label):
                flag(key, "House", "cook_vs_presidential", label, f"Presidential source names {held[0]} ({held[1]})")
            matches = [r for r in field[key] if surname(r["name"]) == surname(label)]
            if len(matches) != 1:
                flag(key, "House", "incumbent_not_in_field", label,
                     f"{len(matches)} field candidates share the surname; check spelling or retirement")
        entries.append(entry)

    members = senators(paths["senators"])
    nga, wiki = nga_governors(paths["nga"]), wikipedia_governors(paths["wikipedia"])
    for key in sorted(races):
        state, office = races[key]
        entry: dict = dict(race_key=key, office=office, vacant=False, reviewed_by=SEED_REVIEWER,
                           reviewed_at="2026-11-02")
        if office == "Senate":
            seats = members.get(state, [])
            # Class II seats are up in 2026; a state without one holds a special for Class III.
            chosen = [s for s in seats if s[2] == "Class II"] or [s for s in seats if s[2] == "Class III"]
            if len(chosen) != 1:
                raise ValueError(f"{key}: expected one senator for the 2026 seat, found {len(chosen)}")
            name, party, seat_class = chosen[0]
            entry.update(name=name, party=party, evidence=[f"{SENATE_URL} ({state} {seat_class}: {name}, {party})"])
            if seat_class != "Class II":
                flag(key, office, "special_election", name, f"No Class II senator; seeded the {seat_class} holder")
        else:
            if state not in nga or state not in wiki:
                raise ValueError(f"{key}: governor missing from saved NGA or Wikipedia source")
            name, party = wiki[state]
            entry.update(name=nga[state], party=party,
                         evidence=[f"{NGA_URL} ({state}: Gov. {nga[state]})", f"{WIKI_URL} ({state}: {name}, {party})"])
            if surname(name) != surname(nga[state]):
                flag(key, office, "governor_sources_disagree", nga[state], f"Wikipedia names {name}")
        matches = [r for r in field[key] if surname(r["name"]) == surname(entry["name"])]
        if not matches:
            flag(key, office, "incumbent_not_in_field", entry["name"], "Not on the 2026 ballot for this race; confirm retirement")
        entries.append(entry)
    review.sort(key=lambda r: (r["race_key"], r["issue"]))
    return entries, review


def write_roster(path, entries):
    data = dict(schema_version=1, cycle=2026,
                description=("One entry per 2026 House, Senate, and governor race. House incumbents follow Cook's "
                             "2026 convention: the sitting member contesting the district, or the departing "
                             "member when Cook marks it OPEN."),
                entries=entries)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--review", type=Path, default=ROSTER_DIR / "roster-review.csv")
    parser.add_argument("--reseed", action="store_true", help="replace an existing, reviewed roster")
    args = parser.parse_args()
    try:
        entries, review = seed(default_paths())
        reviewed = {}
        if args.roster.exists() and not args.reseed:
            committed = json.loads(args.roster.read_text(encoding="utf-8"))["entries"]
            reviewed = {e["race_key"]: e["reviewed_by"] for e in committed if e["reviewed_by"] != SEED_REVIEWER}
        for row in review:
            row["resolved_by"] = reviewed.get(row["race_key"], "")
        publish_csvs(args.review.parent, [(args.review.name, REVIEW_COLUMNS, review)])
        if args.reseed or not args.roster.exists():
            write_roster(args.roster, entries)
            print(f"Seeded {len(entries)} roster entries", file=sys.stderr)
    except (ValueError, KeyError, OSError, ET.ParseError) as exc:
        sys.exit(f"Roster seed failed: {exc}")
    unresolved = sum(not row["resolved_by"] for row in review)
    print(f"Wrote {len(review)} review rows, {unresolved} unresolved", file=sys.stderr)


if __name__ == "__main__":
    main()
