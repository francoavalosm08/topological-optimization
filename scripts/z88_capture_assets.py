"""Copy installed Z88 example projects into ignored local z88_assets/."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import DEFAULT_EXAMPLES, capture_examples, discover_installation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--asset-root", default="z88_assets")
    parser.add_argument(
        "--examples",
        nargs="*",
        default=list(DEFAULT_EXAMPLES),
        help="Example project folder names to copy",
    )
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args()

    installation = discover_installation(args.install_root)
    examples_root = installation.root / "docu" / "examples" / "project"
    captured = capture_examples(
        examples_root,
        asset_root=args.asset_root,
        example_names=tuple(args.examples),
        overwrite=not args.no_overwrite,
    )
    print(json.dumps({"asset_root": args.asset_root, "captured": captured}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
