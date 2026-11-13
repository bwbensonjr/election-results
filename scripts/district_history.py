"""District keys, source validation, and offline partisan-history normalization."""

import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import date
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "2026/results/source-manifest.json"
RESULTS_DIR = ROOT / "2026/results"
STATES = set("AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split())
PRESIDENTIAL_HEADERS = [
    ["District", "Incumbent", "Party", "2024", "", "", "", "", "", "", "2020", "", "", "", "", ""],
    ["", "", "", "Harris", "Trump", "Total", "Harris %", "Trump %", "Margin", "", "Biden", "Trump", "Total", "Biden %", "Trump %", "Margin"],
]
COOK_COLUMNS = ["Dist", "Incumbent", "Incumbent Party", "2025 PVI", "2026 PVI", "2026 Rank"]
PRESIDENTIAL_COLUMNS = [
    "state", "district", "district_id", "election_year", "dem_votes", "rep_votes",
    "total_votes", "dem_share_pct", "rep_share_pct", "dem_margin_pp",
    "source_incumbent_label", "source_party_label", "source_id", "source_record",
]
PVI_COLUMNS = [
    "state", "district", "district_id", "cook_pvi_label", "cook_pvi_dem_lean_pp",
    "source_incumbent_label", "source_party_label", "source_id", "source_record", "pvi_edition",
]
TOLERANCE = Decimal("0.011")
STATE_PVI_COLUMNS_SOURCE = ["State", "PVI"]
STATE_NAMES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "Washington, D.C.": "DC", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}
STATE_PRESIDENTIAL_COLUMNS = [
    "state", "election_year", "dem_votes", "rep_votes", "total_votes", "dem_share_pct",
    "rep_share_pct", "dem_margin_pp", "district_count", "status", "missing_districts",
    "source_id", "source_record",
]
STATE_PVI_COLUMNS = ["state", "cook_pvi_label", "cook_pvi_dem_lean_pp", "source_id", "source_record", "pvi_edition"]
# A district is flagged when its 2026 PVI and the PVI-like lean implied by its presidential
# margins differ by more than this many points; see docs/district-data.md.
BOUNDARY_REVIEW_THRESHOLD = Decimal("4")
BOUNDARY_REVIEW_COLUMNS = [
    "state", "district", "district_id", "cook_pvi_dem_lean_pp", "implied_dem_lean_pp", "difference_pp",
]
CROSSWALK_COLUMNS = ["state", "old_district_id", "county_fips", "new_district_id", "shared_pop", "old_district_pop",
                     "share"]
COUNTY_COLUMNS = ["state", "county_fips", "election_year", "dem_votes", "rep_votes", "total_votes", "pop_2020"]
INTERPOLATED_SOURCE_ID = "presidential-interpolated-cd119-to-2026"
# Year weights for the lean implied by presidential margins. Cook's PVI weights the most recent
# election 75 percent; the boundary review predates that refinement and keeps equal weights.
EQUAL_WEIGHTS = {"2020": Decimal("0.5"), "2024": Decimal("0.5")}
COOK_WEIGHTS = {"2020": Decimal("0.25"), "2024": Decimal("0.75")}
# Reallocated state totals must match the source district totals within this many votes.
CONSERVATION_TOLERANCE = Decimal("1")


def district_key(label):
    """Return (state, two-digit district, display ID), without map inference."""
    if not isinstance(label, str):
        raise ValueError(f"invalid district label {label!r}")
    match = re.fullmatch(r"([A-Z]{2})-(AL|[0-9]{1,2})", label.strip().upper())
    if not match or match[1] not in STATES:
        raise ValueError(f"invalid district label {label!r}")
    state, number = match.groups()
    number = "00" if number == "AL" else number.zfill(2)
    return state, number, f"{state}-{'AL' if number == '00' else number}"


def read_table(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def read_records(path, expected_columns=None):
    table = read_table(path)
    if not table or len(set(table[0])) != len(table[0]) or not all(table[0]):
        raise ValueError(f"{path}: missing, blank, or duplicate CSV headers")
    columns = table[0]
    if expected_columns is not None and columns != expected_columns:
        raise ValueError(f"{path}: expected columns {expected_columns}, got {columns}")
    rows = []
    for line, row in enumerate(table[1:], 2):
        if len(row) != len(columns):
            raise ValueError(f"{path} row {line}: expected {len(columns)} cells, got {len(row)}")
        rows.append(dict(zip(columns, row)))
    return columns, rows


def require_unique(rows, key_of, source):
    seen = {}
    for row in rows:
        key = key_of(row)
        reference = row["source_record"]
        if key in seen:
            raise ValueError(f"{source}: duplicate normalized key {key}: {seen[key]} and {reference}")
        seen[key] = reference


def load_sources(manifest_path=DEFAULT_MANIFEST, project_root=ROOT):
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("manifest: schema_version must be 1")
    sources = data.get("sources")
    if not isinstance(sources, dict) or set(sources) - {"cook_state_pvi"} != {"presidential", "cook_pvi"}:
        raise ValueError("manifest: sources must contain presidential and cook_pvi, and may add cook_state_pvi")
    result, ids = {}, set()
    for kind, entry in sources.items():
        if not isinstance(entry, dict):
            raise ValueError(f"manifest {kind}: source must be an object")
        for field in ["source_id", "path", "sha256", "edition", "format", "notes"]:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"manifest {kind}: missing or invalid {field}")
        if entry["source_id"] in ids:
            raise ValueError("manifest: source IDs must be unique")
        ids.add(entry["source_id"])
        if entry.get("election_years") != [2020, 2024]:
            raise ValueError(f"manifest {kind}: election_years must be [2020, 2024]")
        expected_format, expected_edition = {
            "presidential": ("presidential-two-header", None),
            "cook_pvi": ("cook-pvi-six-column", "2026"),
            # Cook's 2026 update re-scored districts only; 2025 is the latest state edition.
            "cook_state_pvi": ("cook-state-pvi-two-column", "2025"),
        }[kind]
        if entry["format"] != expected_format or expected_edition not in (None, entry["edition"]):
            raise ValueError(f"manifest {kind}: contradictory format or edition")
        for field in ["retrieved_at", "published_at"]:
            value = entry.get(field)
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError(f"manifest {kind}: invalid {field}")
                try:
                    if date.fromisoformat(value).isoformat() != value:
                        raise ValueError()
                except ValueError as exc:
                    raise ValueError(f"manifest {kind}: invalid {field}") from exc
        url = entry.get("source_url")
        if url is not None and (not isinstance(url, str) or not url.startswith(("https://", "http://"))):
            raise ValueError(f"manifest {kind}: invalid source_url")
        relative = Path(entry["path"])
        path = (Path(project_root) / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(Path(project_root).resolve()):
            raise ValueError(f"manifest {kind}: path must remain inside project root")
        if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise ValueError(f"manifest {kind}: invalid SHA-256")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"manifest {kind}: stale SHA-256 for {entry['path']}; update snapshot metadata")
        result[kind] = dict(entry, resolved_path=path)
    return result


def load_boundary_vintage(manifest_path=DEFAULT_MANIFEST, project_root=ROOT):
    """Return {state: entry} for states voting on different lines than the presidential source.

    The registry path comes from the manifest's `reviewed_inputs`; a manifest without one has no
    redrawn states.
    """
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entry = (data.get("reviewed_inputs") or {}).get("boundary_vintage")
    if entry is None:
        return {}
    relative = Path(entry.get("path", ""))
    path = (Path(project_root) / relative).resolve()
    if not entry.get("path") or relative.is_absolute() or not path.is_relative_to(Path(project_root).resolve()):
        raise ValueError("manifest boundary_vintage: path must remain inside project root")
    registry = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or not isinstance(registry.get("states"), list):
        raise ValueError(f"{relative}: expected schema_version 1 and a states list")
    states = {}
    for index, item in enumerate(registry["states"], 1):
        label = f"{relative} state {index}"
        try:
            if not isinstance(item, dict):
                raise ValueError("must be an object")
            state = item.get("state")
            label += f" ({state})"
            if state not in STATES:
                raise ValueError("unknown state code")
            if state in states:
                raise ValueError("duplicate state")
            for field in ["plan_2026", "reviewed_by", "reviewed_at"]:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError(f"missing or invalid {field}")
            date.fromisoformat(item["reviewed_at"])
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(e, str) and e for e in evidence):
                raise ValueError("missing evidence references")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
        states[state] = item
    return states


def reviewed_file(manifest_path, key, project_root):
    """Return the path of a hashed reviewed input named in the manifest, or None when absent."""
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entry = (data.get("reviewed_inputs") or {}).get(key)
    if entry is None:
        return None
    relative = Path(entry.get("path", ""))
    path = (Path(project_root) / relative).resolve()
    if not entry.get("path") or relative.is_absolute() or not path.is_relative_to(Path(project_root).resolve()):
        raise ValueError(f"manifest {key}: path must remain inside project root")
    if not re.fullmatch(r"[a-f0-9]{64}", str(entry.get("sha256", ""))):
        raise ValueError(f"manifest {key}: invalid SHA-256")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(f"manifest {key}: stale SHA-256 for {entry['path']}; "
                         "update the manifest after rebuilding the crosswalk")
    return path


def load_crosswalk(manifest_path=DEFAULT_MANIFEST, project_root=ROOT):
    """Return validated (crosswalk rows, county results), or ([], {}) when the manifest names no crosswalk.

    Both files are built by scripts/build_presidential_crosswalk.py; their paths and SHA-256 come
    from the manifest's `reviewed_inputs.presidential_crosswalk` and `presidential_county_results`.
    County results are keyed by (county FIPS, year).
    """
    path = reviewed_file(manifest_path, "presidential_crosswalk", project_root)
    if path is None:
        return [], {}
    county_path = reviewed_file(manifest_path, "presidential_county_results", project_root)
    if county_path is None:
        raise ValueError("manifest: presidential_crosswalk requires presidential_county_results")
    counties = {}
    for line, row in enumerate(read_records(county_path, COUNTY_COLUMNS)[1], 2):
        location = f"{county_path.name} row {line}"
        values = [row[c] for c in ["dem_votes", "rep_votes", "total_votes", "pop_2020"]]
        if (not all(v.isdigit() for v in values) or int(values[2]) <= 0 or int(values[3]) <= 0
                or int(values[0]) + int(values[1]) > int(values[2])):
            raise ValueError(f"{location}: votes and population must be integers, with positive total and population, "
                             "and party votes within the total")
        key = (row["county_fips"], row["election_year"])
        if key in counties or row["election_year"] not in ("2020", "2024"):
            raise ValueError(f"{location}: duplicate or unexpected county year {key}")
        counties[key] = dict(zip(["dem_votes", "rep_votes", "total_votes", "pop_2020"], map(int, values)))
    _, rows = read_records(path, CROSSWALK_COLUMNS)
    registry = load_boundary_vintage(manifest_path, project_root)
    shared_by_old, old_pop = defaultdict(int), {}
    seen = set()
    for line, row in enumerate(rows, 2):
        location = f"{path.name} row {line}"
        old_state, _, old_id = district_key(row["old_district_id"])
        new_state, _, new_id = district_key(row["new_district_id"])
        if not row["state"] == old_state == new_state:
            raise ValueError(f"{location}: state does not match both district IDs")
        if row["state"] not in registry:
            raise ValueError(f"{location}: {row['state']} is not in the boundary vintage registry")
        if any((row["county_fips"], year) not in counties for year in ["2020", "2024"]):
            raise ValueError(f"{location}: county {row['county_fips']} has no results for both years")
        if (old_id, row["county_fips"], new_id) in seen:
            raise ValueError(f"{location}: duplicate row {old_id}, {row['county_fips']}, {new_id}")
        seen.add((old_id, row["county_fips"], new_id))
        if not (row["shared_pop"].isdigit() and row["old_district_pop"].isdigit()) or int(row["shared_pop"]) <= 0:
            raise ValueError(f"{location}: populations must be positive integers")
        if old_pop.setdefault(old_id, int(row["old_district_pop"])) != int(row["old_district_pop"]):
            raise ValueError(f"{location}: inconsistent population for {old_id}")
        shared_by_old[old_id] += int(row["shared_pop"])
    for old_id, total in shared_by_old.items():
        if total != old_pop[old_id]:
            raise ValueError(f"{path.name}: shared populations for {old_id} sum to {total}, not {old_pop[old_id]}")
    return rows, counties


def interpolate_presidential(history, crosswalk, counties):
    """Reallocate source votes from old districts to new ones, weighted by county vote rates.

    For each year and for Democratic, Republican, and other votes (total minus both), each
    crosswalk row (old district, county, new district) is weighted by shared_pop * county votes /
    county 2020 population. Each old district's source votes are split across its rows in
    proportion to those weights, so old district and state totals are kept exactly, and a new
    district's total is the sum of its three parts. Votes are published to two decimals; shares and margins are computed
    from the unrounded sums, with the source definitions. A new district any of whose old
    districts lacks a count is left blank for that year.
    """
    columns = ["dem_votes", "rep_votes", "total_votes"]
    parts = ["dem_votes", "rep_votes", "other_votes"]

    def split(values):
        return dict(dem_votes=Decimal(values["dem_votes"]), rep_votes=Decimal(values["rep_votes"]),
                    other_votes=Decimal(values["total_votes"]) - Decimal(values["dem_votes"])
                    - Decimal(values["rep_votes"]))

    source = {(r["district_id"], r["election_year"]): r for r in history}
    by_old = defaultdict(list)
    for row in crosswalk:
        by_old[row["old_district_id"]].append(row)
    votes = defaultdict(lambda: dict.fromkeys(parts, Decimal(0)))
    blank = set()
    for old_id, pieces in by_old.items():
        for year in ["2020", "2024"]:
            old = source.get((old_id, year))
            if old is None or "" in (old[c] for c in columns):
                blank.update((p["new_district_id"], year) for p in pieces)
                continue
            old_parts = split(old)
            for column in parts:
                weights = [int(p["shared_pop"]) * split(counties[(p["county_fips"], year)])[column]
                           / counties[(p["county_fips"], year)]["pop_2020"] for p in pieces]
                total_weight = sum(weights, Decimal(0))
                for piece, weight in zip(pieces, weights):
                    share = weight / total_weight if total_weight else Decimal(int(piece["shared_pop"])) / int(
                        piece["old_district_pop"])
                    votes[(piece["new_district_id"], year)][column] += old_parts[column] * share
    population_share = defaultdict(lambda: defaultdict(Decimal))
    for row in crosswalk:
        population_share[row["new_district_id"]][row["old_district_id"]] += (
            Decimal(int(row["shared_pop"])) / int(row["old_district_pop"]))
    rows = []
    for new_id in sorted(population_share, key=lambda k: district_key(k)[:2]):
        state, district, district_id = district_key(new_id)
        record = ",".join(f"{old}:{share.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)}"
                          for old, share in sorted(population_share[new_id].items()))
        for year in ["2020", "2024"]:
            row = dict.fromkeys(PRESIDENTIAL_COLUMNS, "")
            row.update(state=state, district=district, district_id=district_id, election_year=year,
                       source_id=INTERPOLATED_SOURCE_ID, source_record=f"District={district_id};year={year};from={record}")
            if (new_id, year) not in blank:
                dem, rep, other = (votes[(new_id, year)][c] for c in parts)
                total = dem + rep + other
                row.update({c: format(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
                            for c, v in zip(columns, [dem, rep, total])})
                row.update(dem_share_pct=percent(dem, total), rep_share_pct=percent(rep, total),
                           dem_margin_pp=percent(dem - rep, total))
            rows.append(row)
    check_conservation(history, rows)
    return rows


def check_conservation(history, interpolated):
    """Fail unless each interpolated state's published votes sum to its source district totals.

    A state and year with any blank count, on either side, has no complete total to compare.
    """
    columns = ["dem_votes", "rep_votes", "total_votes"]
    states = {row["state"] for row in interpolated}
    sums = defaultdict(lambda: defaultdict(Decimal))
    incomplete = set()
    for label, rows in [("source", history), ("interpolated", interpolated)]:
        for row in rows:
            if row["state"] not in states:
                continue
            if "" in (row[c] for c in columns):
                incomplete.add((row["state"], row["election_year"]))
                continue
            for c in columns:
                sums[(row["state"], row["election_year"], c)][label] += Decimal(row[c])
    for (state, year, column), totals in sorted(sums.items()):
        if (state, year) in incomplete:
            continue
        if abs(totals["source"] - totals["interpolated"]) > CONSERVATION_TOLERANCE:
            raise ValueError(f"interpolation for {state} {year}: {column} sums to {totals['interpolated']}, "
                             f"not the source total {totals['source']}")


def national_margins(history):
    """Return {year: national Democratic margin} summed from the source district rows."""
    totals = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    for row in history:
        if "" not in (row["dem_votes"], row["rep_votes"], row["total_votes"]):
            for i, column in enumerate(["dem_votes", "rep_votes", "total_votes"]):
                totals[row["election_year"]][i] += Decimal(row[column])
    return {year: 100 * (dem - rep) / total for year, (dem, rep, total) in totals.items() if total}


def boundary_review(history, pvi, registry):
    """Return districts outside the registry whose PVI and presidential margins disagree.

    Each margin is compared with the national margin summed from the same source, and the two
    differences are averaged and halved to put them on Cook's lean scale.
    """
    return lean_review(history, national_margins(history), pvi, lambda state: state not in registry, EQUAL_WEIGHTS)


def interpolation_review(interpolated, history, pvi):
    """Return interpolated districts whose PVI and estimated margins disagree.

    The implied lean weights the years as Cook's PVI does, so a district that swung between
    2020 and 2024 is not flagged for the swing alone.
    """
    states = {row["state"] for row in interpolated}
    return lean_review(interpolated, national_margins(history), pvi, lambda state: state in states, COOK_WEIGHTS)


def lean_review(history, national, pvi, include, weights):
    """Return PVI rows whose lean differs from the implied lean, sum(weight * (margin - national)) / 2."""
    by_year = defaultdict(dict)
    for row in history:
        by_year[row["election_year"]][(row["state"], row["district"])] = row
    rows = []
    for record in pvi:
        key = (record["state"], record["district"])
        margins = [by_year[year].get(key, {}).get("dem_margin_pp", "") for year in ["2020", "2024"]]
        if not include(record["state"]) or record["cook_pvi_dem_lean_pp"] == "" or "" in margins:
            continue
        implied = sum(weights[y] * (Decimal(m) - national[y]) for m, y in zip(margins, ["2020", "2024"])) / 2
        difference = abs(implied - Decimal(record["cook_pvi_dem_lean_pp"]))
        if difference > BOUNDARY_REVIEW_THRESHOLD:
            rows.append(dict(zip(BOUNDARY_REVIEW_COLUMNS, [
                record["state"], record["district"], record["district_id"], record["cook_pvi_dem_lean_pp"],
                format(implied.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f"),
                format(difference.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")])))
    return sorted(rows, key=lambda r: (r["state"], r["district"]))


def numeric(value, kind, location):
    value = value.strip()
    if not value:
        return ""
    if kind == "count":
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", value):
            raise ValueError(f"{location}: invalid nonnegative integer {value!r}")
        return str(int(value.replace(",", "")))
    if not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?%?", value):
        raise ValueError(f"{location}: invalid decimal percentage {value!r}")
    try:
        number = Decimal(value.removesuffix("%"))
    except InvalidOperation as exc:
        raise ValueError(f"{location}: invalid percentage") from exc
    lower = -100 if kind == "margin" else 0
    if not lower <= number <= 100:
        raise ValueError(f"{location}: percentage outside {lower} to 100")
    return format(number, "f")


def normalize_presidential(source):
    path = source["resolved_path"]
    table = read_table(path)
    headers = [[cell.strip() for cell in row] for row in table[:2]]
    if headers != PRESIDENTIAL_HEADERS:
        raise ValueError(f"{path}: unexpected two-row presidential header")
    rows = []
    seen = {}
    for line, raw in enumerate(table[2:], 3):
        location = f"{path} row {line}"
        if len(raw) != 16 or raw[9].strip():
            raise ValueError(f"{location}: expected 16 columns and an empty separator")
        raw = [value.strip() for value in raw]
        state, district, district_id = district_key(raw[0])
        if district_id in seen:
            raise ValueError(f"{location}: duplicate normalized key {district_id}, rows {seen[district_id]} and {line}")
        seen[district_id] = line
        for year, start in [(2024, 3), (2020, 10)]:
            values = [numeric(raw[start + offset], kind, f"{location} {year} {field}")
                      for offset, (field, kind) in enumerate([
                          ("dem_votes", "count"), ("rep_votes", "count"), ("total_votes", "count"),
                          ("dem_share_pct", "share"), ("rep_share_pct", "share"), ("dem_margin_pp", "margin")])]
            dem, rep, total, dem_share, rep_share, margin = [Decimal(v) if v != "" else None for v in values]
            if total is not None:
                if total <= 0 or sum(v or 0 for v in [dem, rep]) > total:
                    raise ValueError(f"{location} {year}: impossible vote total")
                for votes, share, field in [(dem, dem_share, "dem_share_pct"), (rep, rep_share, "rep_share_pct")]:
                    if votes is not None and share is not None and abs(100 * votes / total - share) > TOLERANCE:
                        raise ValueError(f"{location} {year}: {field} disagrees with vote counts")
                if dem is not None and rep is not None and margin is not None:
                    if abs(100 * (dem - rep) / total - margin) > TOLERANCE:
                        raise ValueError(f"{location} {year}: margin disagrees with vote counts")
            row = dict(zip(PRESIDENTIAL_COLUMNS[:10], [state, district, district_id, str(year), *values]))
            row.update(source_incumbent_label=raw[1], source_party_label=raw[2],
                       source_id=source["source_id"], source_record=f"District={district_id};year={year}")
            rows.append(row)
    return sorted(rows, key=lambda r: (r["state"], r["district"], r["election_year"]))


def pvi_lean(label, location):
    if label == "":
        return ""
    if label == "EVEN":
        return "0"
    match = re.fullmatch(r"([DR])\+([1-9][0-9]?)", label)
    if not match or int(match[2]) > 50:
        raise ValueError(f"{location}: invalid published PVI label {label!r}")
    return str(int(match[2]) * (1 if match[1] == "D" else -1))


def normalize_cook(source):
    _, records = read_records(source["resolved_path"], COOK_COLUMNS)
    rows, seen = [], {}
    for line, raw in enumerate(records, 2):
        location = f"{source['resolved_path']} row {line}"
        state, district, district_id = district_key(raw["Dist"])
        if district_id in seen:
            raise ValueError(f"{location}: duplicate normalized key {district_id}, rows {seen[district_id]} and {line}")
        seen[district_id] = line
        label = raw["2026 PVI"].strip()
        lean = pvi_lean(label, location)
        rows.append(dict(zip(PVI_COLUMNS, [state, district, district_id, label, lean,
                    raw["Incumbent"].strip(), raw["Incumbent Party"].strip(), source["source_id"],
                    f"Dist={district_id};edition=2026", source["edition"]])))
    return sorted(rows, key=lambda r: (r["state"], r["district"]))


def normalize_state_pvi(source):
    """Return published state PVI rows from the two-column state snapshot, keyed by postal code."""
    _, records = read_records(source["resolved_path"], STATE_PVI_COLUMNS_SOURCE)
    rows, seen = [], {}
    for line, raw in enumerate(records, 2):
        location = f"{source['resolved_path']} row {line}"
        name = raw["State"].strip()
        if name not in STATE_NAMES:
            raise ValueError(f"{location}: unknown state {name!r}")
        state = STATE_NAMES[name]
        if state in seen:
            raise ValueError(f"{location}: duplicate state {state}, rows {seen[state]} and {line}")
        seen[state] = line
        label = raw["PVI"].strip()
        rows.append(dict(zip(STATE_PVI_COLUMNS, [state, label, pvi_lean(label, location), source["source_id"],
                                                 f"State={name};edition={source['edition']}", source["edition"]])))
    return sorted(rows, key=lambda r: r["state"])


def percent(part, total):
    return format((100 * part / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def aggregate_states(history, expected_districts):
    """Sum district vote counts into state rows, only where every expected district has counts."""
    by_state = defaultdict(dict)
    for row in history:
        by_state[(row["state"], row["election_year"])][row["district"]] = row
    rows = []
    for state in sorted(expected_districts):
        districts = sorted(expected_districts[state])
        for year in ["2020", "2024"]:
            found = by_state.get((state, year), {})
            missing = [d for d in districts if d not in found
                       or "" in (found[d]["dem_votes"], found[d]["rep_votes"], found[d]["total_votes"])]
            row = dict.fromkeys(STATE_PRESIDENTIAL_COLUMNS, "")
            row.update(state=state, election_year=year, district_count=str(len(districts)),
                       missing_districts=";".join(missing), status="missing" if missing else "available",
                       source_record=f"State={state};year={year};summed districts")
            source_ids = {found[d]["source_id"] for d in districts if d in found}
            row["source_id"] = ";".join(sorted(source_ids))
            if not missing:
                dem, rep, total = (sum(Decimal(found[d][c]) for d in districts)
                                   for c in ["dem_votes", "rep_votes", "total_votes"])
                row.update(dem_votes=str(dem), rep_votes=str(rep), total_votes=str(total),
                           dem_share_pct=percent(dem, total), rep_share_pct=percent(rep, total),
                           dem_margin_pp=percent(dem - rep, total))
            rows.append(row)
    return rows


def expected_state_districts(candidate_path):
    """Return each state's districts from the House candidate field, the target district universe."""
    _, candidates = read_records(candidate_path)
    districts = defaultdict(set)
    for row in candidates:
        state, district, _ = district_key(f"{row['state']}-{row['district']}")
        districts[state].add(district)
    return districts


def normalized_state_sources(manifest_path=DEFAULT_MANIFEST, project_root=ROOT,
                             candidate_path=ROOT / "2026/candidates/house-general-field.csv"):
    """Return (sources, state presidential rows, state PVI rows) without writing files."""
    sources, history, _ = normalized_sources(manifest_path, project_root)
    if "cook_state_pvi" not in sources:
        raise ValueError("manifest: cook_state_pvi source is required for state normalization")
    states = aggregate_states(history, expected_state_districts(candidate_path))
    return sources, states, normalize_state_pvi(sources["cook_state_pvi"])


def normalized_sources(manifest_path=DEFAULT_MANIFEST, project_root=ROOT):
    sources = load_sources(manifest_path, project_root)
    return sources, normalize_presidential(sources["presidential"]), normalize_cook(sources["cook_pvi"])


def publish_csvs(directory, outputs):
    """All parsing and validation must complete before publication is invoked."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for name, columns, rows in outputs:
            with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8",
                                             dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, directory / name))
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            temporary.chmod(0o644)
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def normalize(manifest_path=DEFAULT_MANIFEST, output_dir=RESULTS_DIR, project_root=ROOT, candidate_path=None):
    """Publish district outputs, plus state outputs when a candidate field is given.

    Every source is validated before any file is replaced, so a bad state
    snapshot also leaves the district outputs untouched.
    """
    sources, history, pvi = normalized_sources(manifest_path, project_root)
    review = boundary_review(history, pvi, load_boundary_vintage(manifest_path, project_root))
    outputs = [
        ("presidential-results-normalized.csv", PRESIDENTIAL_COLUMNS, history),
        ("cook-pvi-normalized.csv", PVI_COLUMNS, pvi),
        ("boundary-review.csv", BOUNDARY_REVIEW_COLUMNS, review),
    ]
    crosswalk, counties = load_crosswalk(manifest_path, project_root)
    if crosswalk:
        interpolated = interpolate_presidential(history, crosswalk, counties)
        outputs += [
            ("presidential-results-interpolated.csv", PRESIDENTIAL_COLUMNS, interpolated),
            ("presidential-interpolation-review.csv", BOUNDARY_REVIEW_COLUMNS,
             interpolation_review(interpolated, history, pvi)),
        ]
    if candidate_path is not None:
        _, states, state_pvi = normalized_state_sources(manifest_path, project_root, candidate_path)
        outputs += [
            ("state-presidential-normalized.csv", STATE_PRESIDENTIAL_COLUMNS, states),
            ("cook-state-pvi-normalized.csv", STATE_PVI_COLUMNS, state_pvi),
        ]
    publish_csvs(output_dir, outputs)
    return history, pvi
