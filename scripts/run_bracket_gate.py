"""Phase 4 gate: run the built-in L-bracket and print/check results."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.optimizer import OptParams, run_topopt
from core.problem import l_bracket_problem
from geometry.bracket import build_l_bracket, export_bracket_stl


def main() -> None:
    prob = l_bracket_problem(nelx=28, nely=20, nelz=6, leg_thickness=3)
    masks = prob.region_masks
    assert masks is not None

    params = OptParams(volfrac=0.4, penal=3.0, rmin=2.0, max_iter=60, tol=0.02)
    x, hist = run_topopt(prob, params)

    x_void = max(params.Emin, 1e-3)
    passive_ok = bool(np.allclose(x[masks.passive_solid], 1.0, atol=1e-6))
    void_ok = bool(np.allclose(x[masks.void], x_void, atol=1e-6))
    design_mean = float(x[masks.design].mean())

    print("Phase 4 L-bracket gate")
    print(f"  Grid: {prob.nelx} x {prob.nely} x {prob.nelz}")
    print(f"  Passive voxels stay at 1.0: {passive_ok}")
    print(f"  Void voxels pinned: {void_ok}")
    print(f"  Design-region density mean: {design_mean:.3f} (target volfrac {params.volfrac})")
    print(f"  Final compliance: {hist.compliance[-1]:.4f}")
    print(f"  Iterations: {len(hist.iters)}")

    runs = Path(__file__).resolve().parent.parent / "runs"
    grid, _ = build_l_bracket(prob.nelx, prob.nely, prob.nelz, leg_thickness=3)
    export_bracket_stl(grid, str(runs / "bracket_reference.stl"))
    print(f"  Wrote reference mesh: {runs / 'bracket_reference.stl'}")

    if not passive_ok or not void_ok or design_mean > 0.95:
        raise SystemExit(1)
    print("  GATE PASSED")


if __name__ == "__main__":
    main()
