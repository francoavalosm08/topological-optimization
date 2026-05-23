"""Summarize a native or staged Z88Arion project directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import summarize_project_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Directory containing native Z88 project files")
    parser.add_argument("--out", help="Optional JSON output path")
    args = parser.parse_args()

    summary = summarize_project_files(Path(args.project_dir))
    payload = json.dumps(summary, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
