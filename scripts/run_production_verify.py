"""Phase 6 smoke: optimize bracket, export mesh, write verification report."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.optimizer import OptParams, run_topopt
from core.problem import l_bracket_problem
from core.verify import verify_density_design, write_verification_report


def main() -> None:
    prob = l_bracket_problem(nelx=28, nely=20, nelz=6, leg_thickness=3)
    params = OptParams(
        method="stress",
        volfrac=0.4,
        penal=3.0,
        rmin=2.0,
        max_iter=50,
        tol=0.02,
        stress_limit=1.6,
        stress_relief_radius=2.0,
        stress_relief_steps=6,
        stress_hotspot_density=0.9,
    )
    x, hist = run_topopt(prob, params)

    mesh_path = ROOT / "runs" / "opt_final.stl"
    report = verify_density_design(
        prob,
        x,
        mesh_path,
        penal=params.penal,
        E0=params.E0,
        Emin=params.Emin,
        nu=params.nu,
        stress_limit=2.0,
        safety_factor=1.0,
    )
    report_path = ROOT / "runs" / "verification_report.json"
    write_verification_report(report, report_path)

    print("Phase 6 production verification smoke")
    print(f"  Iterations: {len(hist.iters)}")
    print(f"  Mesh: {mesh_path}")
    print(f"  Watertight: {report.mesh.watertight}")
    print(f"  Components: {report.mesh.components}")
    print(f"  Degenerate faces: {report.mesh.degenerate_faces}")
    print(f"  Peak stress: {report.stress.peak:.6f}")
    print(f"  Allowable stress: {report.allowable_stress:.6f}")
    print(f"  Stress pass: {report.passes_stress}")
    print(f"  Report: {report_path}")
    if report.notes:
        print("  Notes: " + "; ".join(report.notes))


if __name__ == "__main__":
    main()
