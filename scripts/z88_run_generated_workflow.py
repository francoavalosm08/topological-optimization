"""Run the confirmed generated Z88 topology workflow end to end."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import run_generated_topology_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Folder containing generated Z88 optimizer files")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--solver", default="siccg", help="Solver mode patched into generated files")
    parser.add_argument("--optimizer-timeout", type=float, default=900.0)
    parser.add_argument("--displacement-timeout", type=float, default=300.0)
    parser.add_argument(
        "--skip-optimizer",
        action="store_true",
        help="Only generate displacements and collect native results",
    )
    parser.add_argument(
        "--skip-displacements",
        action="store_true",
        help="Run optimizer and collect histories without final displacement generation",
    )
    parser.add_argument(
        "--generate-stress",
        action="store_true",
        help="Run observed z88rTOSS -SIG stress postprocess after displacements",
    )
    parser.add_argument("--stress-timeout", type=float, default=300.0)
    parser.add_argument("--verbose", action="store_true", help="Print full workflow JSON")
    args = parser.parse_args()

    result = run_generated_topology_workflow(
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
    payload = result.to_dict() if args.verbose else result.compact_dict()
    print(json.dumps(payload, indent=2))
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
