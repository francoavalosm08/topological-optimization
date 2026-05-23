"""Generate bundled/local sample STL assets for Z88 workflow smoke tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import generate_sample_assets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="samples", help="Output directory for generated STL samples")
    args = parser.parse_args()

    result = generate_sample_assets(args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
