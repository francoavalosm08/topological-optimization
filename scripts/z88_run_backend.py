"""Run the best available Z88 backend path for a run or project folder."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import run_best_available_backend, write_crash_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Run folder, staged native folder, or GUI-generated OC folder")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--solver", default="siccg", help="Solver mode. Default: siccg")
    parser.add_argument("--optimizer-timeout", type=float, default=900.0)
    parser.add_argument("--displacement-timeout", type=float, default=300.0)
    parser.add_argument("--stress-timeout", type=float, default=300.0)
    parser.add_argument(
        "--generate-stress",
        action="store_true",
        help="Generate stress output when the project is a wrapper-generated OC/H8 project",
    )
    parser.add_argument("--skip-optimizer", action="store_true")
    parser.add_argument("--skip-displacements", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print full backend JSON")
    args = parser.parse_args()

    try:
        result = run_best_available_backend(
            args.project_dir,
            install_root=args.install_root,
            solver=args.solver,
            optimizer_timeout_s=args.optimizer_timeout,
            displacement_timeout_s=args.displacement_timeout,
            stress_timeout_s=args.stress_timeout,
            run_optimizer=not args.skip_optimizer,
            generate_displacements=not args.skip_displacements,
            generate_stress=args.generate_stress,
        )
    except Exception as exc:
        project_dir = Path(args.project_dir).resolve()
        report = write_crash_report(
            exc,
            context={
                "command": "z88_run_backend",
                "project_dir": str(project_dir),
                "solver": args.solver,
            },
            files=(
                project_dir / "config.json",
                project_dir / "z88_backend_result.json",
                project_dir / "z88_generated_oc_workflow.json",
            ),
        )
        print(json.dumps({"status": "crashed", "crash_report": report.to_dict()}, indent=2))
        return 1
    payload = result.to_dict() if args.verbose else result.compact_dict()
    print(json.dumps(payload, indent=2))
    return 0 if result.status in {"completed", "guided_handoff_required"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
