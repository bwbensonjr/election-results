# /// script
# requires-python = ">=3.11"
# ///
"""Normalize saved presidential results and published Cook 2026 PVI, offline."""

import argparse
import sys
from pathlib import Path

from district_history import DEFAULT_MANIFEST, RESULTS_DIR, normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    try:
        history, pvi = normalize(args.manifest, args.output_dir)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(f"Normalization failed: {exc}")
    print(f"Wrote {len(history)} presidential year rows and {len(pvi)} Cook PVI rows", file=sys.stderr)


if __name__ == "__main__":
    main()
