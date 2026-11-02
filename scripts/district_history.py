"""District keys, source validation, and offline partisan-history normalization."""

import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
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
    if not isinstance(sources, dict) or set(sources) != {"presidential", "cook_pvi"}:
        raise ValueError("manifest: sources must contain presidential and cook_pvi")
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
        expected_format = "presidential-two-header" if kind == "presidential" else "cook-pvi-six-column"
        if entry["format"] != expected_format or (kind == "cook_pvi" and entry["edition"] != "2026"):
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


def normalize(manifest_path=DEFAULT_MANIFEST, output_dir=RESULTS_DIR, project_root=ROOT):
    _, history, pvi = normalized_sources(manifest_path, project_root)
    publish_csvs(output_dir, [
        ("presidential-results-normalized.csv", PRESIDENTIAL_COLUMNS, history),
        ("cook-pvi-normalized.csv", PVI_COLUMNS, pvi),
    ])
    return history, pvi
