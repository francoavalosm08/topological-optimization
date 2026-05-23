"""Record a manually completed Z88Arion project as a local post-run fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import record_post_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_name", help="Matching pre fixture name, e.g. 2_Querlenker_OC")
    parser.add_argument("--source", required=True, help="Completed manual post-run project folder")
    parser.add_argument("--asset-root", default="z88_assets")
    parser.add_argument("--optimized-stl", help="Optional exported optimized STL to copy into post fixture")
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args()

    result = record_post_run(
        args.fixture_name,
        Path(args.source).resolve(),
        asset_root=args.asset_root,
        optimized_stl=Path(args.optimized_stl).resolve() if args.optimized_stl else None,
        overwrite=not args.no_overwrite,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
