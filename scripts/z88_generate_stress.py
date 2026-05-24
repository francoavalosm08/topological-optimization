"""Generate observed Z88 nodal and element stress files for a completed project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import run_stress_postprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Completed native Z88 optimizer project folder")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--solver", default="siccg", help="Solver mode. Default: siccg")
    parser.add_argument("--nodal-output-file", help="Defaults to Knotenspannungen\\Knot_final.txt")
    parser.add_argument("--element-output-file", help="Defaults to Stresses_ELE\\Stress_ele_final.txt")
    parser.add_argument("--energy-output-file", help="Defaults to tmp\\ElementEnergy_final.txt")
    parser.add_argument("--material-file", help="Override ConstitutiveLaw\\z88matNNN.txt")
    parser.add_argument("--output-dir", help="Directory for stdout/stderr/run JSON. Defaults inside the project.")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    result = run_stress_postprocess(
        args.project_dir,
        install_root=args.install_root,
        solver=args.solver,
        nodal_output_file=args.nodal_output_file,
        element_output_file=args.element_output_file,
        energy_output_file=args.energy_output_file,
        material_file=args.material_file,
        timeout_s=args.timeout,
        output_dir=args.output_dir,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
