"""Stage an existing native Z88Arion project folder into the bridge layout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import Z88Adapter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_project_dir", help="Native Z88Arion project directory")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--runs-root", default="runs/z88", help="Directory for generated run folders")
    parser.add_argument("--project-name", help="Override staged run folder prefix")
    args = parser.parse_args()

    adapter = Z88Adapter(install_root=args.install_root, runs_root=args.runs_root)
    run_dir = adapter.stage_native_project(
        Path(args.source_project_dir).resolve(),
        project_name=args.project_name,
    )
    status = json.loads((run_dir / "bridge_status.json").read_text(encoding="utf-8"))
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
