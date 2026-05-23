"""Run z88optopus against a GUI-generated Z88Arion optimizer project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import run_generated_optimizer_project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Folder containing GUI-generated Z88Arion optimizer files")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument(
        "--solver",
        default="siccg",
        help="Solver mode to patch into Z88Arion.fea. Default: siccg",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--no-patch", action="store_true", help="Run without patching pth/fea files")
    parser.add_argument("--output-dir", help="Directory for captured stdout/stderr JSON")
    args = parser.parse_args()

    result = run_generated_optimizer_project(
        args.project_dir,
        install_root=args.install_root,
        solver=args.solver,
        timeout_s=args.timeout,
        patch_project=not args.no_patch,
        output_dir=args.output_dir,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
