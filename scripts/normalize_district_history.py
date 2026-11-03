# /// script
# requires-python = ">=3.11"
# ///
"""Normalize saved presidential results, published Cook PVI, and statewide history, offline.

State outputs (summed presidential margins and Cook state PVI) are written when the
manifest has a cook_state_pvi source; --districts-only skips them.
"""

import argparse
import json
import sys
from pathlib import Path

from district_history import DEFAULT_MANIFEST, RESULTS_DIR, ROOT, normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--candidates", type=Path, default=ROOT / "2026/candidates/house-general-field.csv",
                        help="House field whose districts define each state's district set")
    parser.add_argument("--districts-only", action="store_true")
    args = parser.parse_args()
    try:
        has_states = "cook_state_pvi" in json.loads(args.manifest.read_text()).get("sources", {})
        candidates = args.candidates if has_states and not args.districts_only else None
        history, pvi = normalize(args.manifest, args.output_dir, candidate_path=candidates)
    except (ValueError, KeyError, OSError, AttributeError) as exc:
        sys.exit(f"Normalization failed: {exc}")
    states = " and state history" if candidates else ""
    print(f"Wrote {len(history)} presidential year rows and {len(pvi)} Cook PVI rows{states}", file=sys.stderr)


if __name__ == "__main__":
    main()
