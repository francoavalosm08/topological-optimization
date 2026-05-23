"""Compare a pre-run and post-run Z88 project folder."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import diff_project_dirs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pre_dir")
    parser.add_argument("post_dir")
    parser.add_argument("--out", help="Optional JSON output path")
    args = parser.parse_args()

    diff = diff_project_dirs(Path(args.pre_dir), Path(args.post_dir))
    payload = json.dumps(diff, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
