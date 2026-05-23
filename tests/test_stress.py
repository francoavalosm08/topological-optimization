"""Phase 5 stress recovery checks."""
from __future__ import annotations

import numpy as np
import pytest

from core.fea import build_edof, build_edof_3d
from core.optimizer import OptParams, run_topopt
from core.problem import cantilever_2d, l_bracket_problem, node_index_2d, node_index_3d
from core.stress import (
    analyze_design_stress,
    apply_qp_relaxation,
    element_von_mises_2d,
    element_von_mises_3d,
    stress_ks,
    stress_p_norm,
    summarize_stress,
)


def test_q4_uniaxial_plane_stress_von_mises():
    E = 2.5
    nu = 0.3
    eps = 0.01
    edof = build_edof(1, 1)
    U = np.zeros(8, dtype=np.float64)

    for col in range(2):
        for row in range(2):
            node = node_index_2d(1, col, row)
            U[2 * node] = eps * col
            U[2 * node + 1] = -nu * eps * row

    vm = element_von_mises_2d(U, edof, E=E, nu=nu)
    assert vm == pytest.approx(np.array([E * eps]), rel=1e-12, abs=1e-12)


def test_h8_hydrostatic_strain_has_zero_von_mises():
    E = 1.7
    nu = 0.28
    eps = 0.01
    edof = build_edof_3d(1, 1, 1)
    U = np.zeros(24, dtype=np.float64)

    for col in range(2):
        for row in range(2):
            for layer in range(2):
                node = node_index_3d(1, 1, col, row, layer)
                U[3 * node] = eps * col
                U[3 * node + 1] = eps * row
                U[3 * node + 2] = eps * layer

    vm = element_von_mises_3d(U, edof, E=E, nu=nu)
    assert vm == pytest.approx(np.array([0.0]), abs=1e-12)


def test_h8_uniaxial_stress_von_mises():
    E = 3.0
    nu = 0.3
    eps = 0.02
    edof = build_edof_3d(1, 1, 1)
    U = np.zeros(24, dtype=np.float64)

    for col in range(2):
        for row in range(2):
            for layer in range(2):
                node = node_index_3d(1, 1, col, row, layer)
                U[3 * node] = eps * col
                U[3 * node + 1] = -nu * eps * row
                U[3 * node + 2] = -nu * eps * layer

    vm = element_von_mises_3d(U, edof, E=E, nu=nu)
    assert vm == pytest.approx(np.array([E * eps]), rel=1e-12, abs=1e-12)


def test_relaxation_and_aggregates_respect_mask():
    vm = np.array([10.0, 20.0, 30.0], dtype=np.float64)
    density = np.array([1.0, 0.5, 0.1], dtype=np.float64)
    relaxed = apply_qp_relaxation(vm, density, q=2.0)

    assert relaxed == pytest.approx(np.array([10.0, 5.0, 0.3]))

    mask = np.array([True, True, False])
    assert stress_p_norm(relaxed, stress_limit=10.0, p=4.0, mask=mask) == pytest.approx(
        (1.0**4 + 0.5**4) ** 0.25
    )
    assert stress_ks(relaxed, stress_limit=10.0, rho=30.0, mask=mask) >= 1.0

    summary = summarize_stress(relaxed, stress_limit=10.0, mask=mask)
    assert summary.peak == pytest.approx(10.0)
    assert summary.mean == pytest.approx(7.5)


def test_analyze_design_stress_returns_finite_summary():
    prob = cantilever_2d(nelx=4, nely=2)
    density = np.ones(prob.n_elements, dtype=np.float64)

    analysis = analyze_design_stress(prob, density, penal=3.0, stress_limit=1.0)

    assert np.isfinite(analysis.displacement).all()
    assert np.isfinite(analysis.von_mises).all()
    assert np.isfinite(analysis.relaxed_von_mises).all()
    assert analysis.summary.peak > 0.0


def test_stress_method_reduces_l_bracket_ks_aggregate():
    prob = l_bracket_problem(nelx=16, nely=12, nelz=4, leg_thickness=2)
    masks = prob.region_masks
    assert masks is not None

    stress_limit = 1.8
    base_params = OptParams(volfrac=0.4, penal=3.0, rmin=1.5, max_iter=30, tol=0.03)
    x_base, _ = run_topopt(prob, base_params)
    base = analyze_design_stress(
        prob,
        x_base,
        penal=base_params.penal,
        stress_limit=stress_limit,
        mask=~masks.void,
    )

    stress_params = OptParams(
        method="stress",
        volfrac=0.4,
        penal=3.0,
        rmin=1.5,
        max_iter=30,
        tol=0.03,
        stress_limit=stress_limit,
        stress_relief_radius=2.0,
        stress_relief_steps=2,
    )
    x_stress, hist = run_topopt(prob, stress_params)
    stress = analyze_design_stress(
        prob,
        x_stress,
        penal=stress_params.penal,
        stress_limit=stress_limit,
        mask=~masks.void,
    )

    assert stress.summary.ks < base.summary.ks * 0.95
    assert hist.stress_ks[-1] == pytest.approx(stress.summary.ks)
    assert float(x_stress[masks.design].mean()) == pytest.approx(
        float(x_base[masks.design].mean())
    )
