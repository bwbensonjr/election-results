# /// script
# requires-python = ">=3.11"
# ///
"""Build the GitHub Pages copy of the Big Board into _site/.

Run from the repository root: uv run scripts/build_pages_site.py
The page is bigboard/index.html wrapped in a full HTML document; its results file is the committed AP snapshot
(2026/results/ap-results.json), so the site shows the latest checked-in results. Outside an artifact the page has no
database and reads data/results.json directly.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "bigboard/index.html"
RESULTS = ROOT / "2026/results/ap-results.json"
OUT = ROOT / "_site"
HEAD = (
    "<!doctype html>\n"
    '<html lang="en">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
)


class BuildError(Exception):
    pass


def build(page=PAGE, results=RESULTS, out=OUT):
    text = page.read_text(encoding="utf-8")
    if "<!-- board-data:begin -->" not in text:
        raise BuildError(f"{page} has no board data; run scripts/build_bigboard_data.py first")
    data = json.loads(results.read_text(encoding="utf-8"))
    if data.get("test") is not False:
        raise BuildError(f"{results} is not live AP data (test is {data.get('test')!r})")
    if not data.get("races"):
        raise BuildError(f"{results} has no races")
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    (out / "index.html").write_text(HEAD + text, encoding="utf-8")
    (out / "data/results.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return data


def main():
    parser = argparse.ArgumentParser(description="Build the GitHub Pages copy of the Big Board into _site/.")
    parser.add_argument("--out", type=Path, default=OUT, help="output directory (replaced)")
    args = parser.parse_args()
    try:
        data = build(out=args.out)
    except (BuildError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.out}: {len(data['races'])} races, AP update {data.get('ap_last_updated')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
