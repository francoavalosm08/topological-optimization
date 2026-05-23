"""Phase 4 validation gate: procedural L-bracket with passive bolt bosses."""
from __future__ import annotations

import numpy as np
import pytest

from core.optimizer import OptParams, run_topopt
from core.problem import l_bracket_problem


def _run_bracket(volfrac: float, max_iter: int = 50) -> tuple[np.ndarray, object]:
    prob = l_bracket_problem(nelx=28, nely=20, nelz=6, leg_thickness=3)
    params = OptParams(volfrac=volfrac, penal=3.0, rmin=2.0, max_iter=max_iter, tol=0.02)
    x, hist = run_topopt(prob, params)
    return x, prob


def test_l_bracket_passive_stays_solid():
    x, prob = _run_bracket(volfrac=0.4)
    masks = prob.region_masks
    assert masks is not None
    assert masks.passive_solid.any()
    assert np.allclose(x[masks.passive_solid], 1.0, atol=1e-6)


def test_l_bracket_removes_material_in_design_region():
    x, prob = _run_bracket(volfrac=0.4)
    masks = prob.region_masks
    assert masks.design.any()
    design_mean = float(x[masks.design].mean())
    assert design_mean < 0.95, f"Expected material removal, design mean={design_mean:.3f}"
    assert design_mean > 0.15, f"Design region collapsed, mean={design_mean:.3f}"


def test_l_bracket_volfrac_changes_topology():
    x_lo, prob = _run_bracket(volfrac=0.3, max_iter=35)
    x_hi, _ = _run_bracket(volfrac=0.5, max_iter=35)
    m = prob.region_masks
    mean_lo = float(x_lo[m.design].mean())
    mean_hi = float(x_hi[m.design].mean())
    assert mean_hi > mean_lo + 0.05, (
        f"Higher volfrac should retain more material: {mean_lo:.3f} vs {mean_hi:.3f}"
    )


def test_l_bracket_compliance_finite():
    x, prob = _run_bracket(volfrac=0.4, max_iter=25)
    assert np.isfinite(x).all()
    assert prob.region_masks is not None
