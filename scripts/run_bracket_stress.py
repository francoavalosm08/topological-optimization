"""Phase 5 smoke test: compliance-optimize the bracket, then report stress."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.optimizer import OptParams, run_topopt
from core.problem import l_bracket_problem
from core.stress import analyze_design_stress


def main() -> None:
    prob = l_bracket_problem(nelx=28, nely=20, nelz=6, leg_thickness=3)
    masks = prob.region_masks
    assert masks is not None

    base_params = OptParams(volfrac=0.4, penal=3.0, rmin=2.0, max_iter=50, tol=0.02)
    x_base, base_hist = run_topopt(prob, base_params)
    base = analyze_design_stress(
        prob,
        x_base,
        penal=base_params.penal,
        E0=base_params.E0,
        Emin=base_params.Emin,
        nu=base_params.nu,
        q=base_params.stress_q,
        stress_limit=1.0,
        mask=~masks.void,
    )

    stress_params = OptParams(
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
        stress_max_compliance_factor=2.0,
    )
    x_stress, stress_hist = run_topopt(prob, stress_params)
    stress = analyze_design_stress(
        prob,
        x_stress,
        penal=stress_params.penal,
        E0=stress_params.E0,
        Emin=stress_params.Emin,
        nu=stress_params.nu,
        q=stress_params.stress_q,
        stress_limit=1.0,
        mask=~masks.void,
    )

    hot_idx = int(np.argmax(np.where(~masks.void, stress.relaxed_von_mises, -np.inf)))
    hot_xyz = tuple(int(v) for v in np.unravel_index(hot_idx, (prob.nelx, prob.nely, prob.nelz), order="C"))

    print("Phase 5 bracket stress smoke")
    print(f"  Compliance-only iterations: {len(base_hist.iters)}")
    print(f"  Stress-aware iterations: {len(stress_hist.iters)}")
    print(f"  Compliance-only final compliance: {base_hist.compliance[-1]:.4f}")
    print(f"  Stress-aware final compliance: {stress_hist.compliance[-1]:.4f}")
    print(f"  Relaxed peak von Mises: {base.summary.peak:.6f} -> {stress.summary.peak:.6f}")
    print(f"  p-norm stress ratio: {base.summary.pnorm:.6f} -> {stress.summary.pnorm:.6f}")
    print(f"  KS stress ratio: {base.summary.ks:.6f} -> {stress.summary.ks:.6f}")
    print(f"  Design density mean: {x_base[masks.design].mean():.3f} -> {x_stress[masks.design].mean():.3f}")
    print(f"  Hot element index: {hot_idx} at {hot_xyz}")
    print("  NOTE: stress relief accepts only changes that reduce the KS aggregate.")


if __name__ == "__main__":
    main()
