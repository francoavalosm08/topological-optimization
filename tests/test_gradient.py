"""Finite-difference check on dc/dx (Phase 1's most important sanity test).

Build-plan rule: 'AI coding assistants get sensitivity signs wrong about
30% of the time. Always validate the gradient against finite differences.'
Analytic vs FD must agree to >=4 significant figures.
"""
from __future__ import annotations

import numpy as np
import pytest

from core.fea import (
    assemble_K,
    build_assembly_indices,
    build_edof,
    compliance_and_sensitivity,
    element_stiffness,
    solve_displacement,
)
from core.problem import mbb_beam


def _compliance(x, KE, edofMat, iK, jK, ndof, free_dofs, F, penal):
    K = assemble_K(x, KE, iK, jK, ndof, penal)
    U = solve_displacement(K, F, free_dofs)
    c, _, _ = compliance_and_sensitivity(x, U, edofMat, KE, penal)
    return c


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_fd_gradient(seed):
    rng = np.random.default_rng(seed)
    # Use a tiny domain so the FE solve is cheap and we can perturb many elements.
    nelx, nely = 8, 5
    prob = mbb_beam(nelx, nely)
    N = nelx * nely

    KE = element_stiffness()
    edofMat = build_edof(nelx, nely)
    iK, jK = build_assembly_indices(edofMat)
    penal = 3.0

    # Pick a non-uniform, well-away-from-zero density field so x^(p-1) is sane.
    x = 0.3 + 0.6 * rng.random(N)

    # Analytic sensitivity at x.
    K = assemble_K(x, KE, iK, jK, prob.ndof, penal)
    U = solve_displacement(K, prob.F, prob.free_dofs)
    c0, dc_analytic, _ = compliance_and_sensitivity(x, U, edofMat, KE, penal)

    # Central differences on 10 randomly chosen elements.
    h = 1e-6
    idxs = rng.choice(N, size=10, replace=False)
    for e in idxs:
        x_plus = x.copy();  x_plus[e]  += h
        x_minus = x.copy(); x_minus[e] -= h
        c_plus = _compliance(x_plus,  KE, edofMat, iK, jK, prob.ndof, prob.free_dofs, prob.F, penal)
        c_minus = _compliance(x_minus, KE, edofMat, iK, jK, prob.ndof, prob.free_dofs, prob.F, penal)
        dc_fd = (c_plus - c_minus) / (2 * h)

        # Relative error must be <1e-4 (4 sig figs); also enforce sign agreement.
        rel = abs(dc_fd - dc_analytic[e]) / max(abs(dc_fd), 1e-12)
        assert np.sign(dc_fd) == np.sign(dc_analytic[e]), (
            f"sensitivity sign disagrees at element {e}: "
            f"analytic={dc_analytic[e]:.4e}, fd={dc_fd:.4e}"
        )
        assert rel < 1e-4, (
            f"FD vs analytic mismatch at element {e}: "
            f"analytic={dc_analytic[e]:.6e}, fd={dc_fd:.6e}, rel={rel:.2e}"
        )


def test_sensitivity_is_negative():
    """dc/dx_e must be <= 0 for all elements: more material can only reduce compliance."""
    nelx, nely = 12, 6
    prob = mbb_beam(nelx, nely)
    KE = element_stiffness()
    edofMat = build_edof(nelx, nely)
    iK, jK = build_assembly_indices(edofMat)
    x = np.full(nelx * nely, 0.5)
    K = assemble_K(x, KE, iK, jK, prob.ndof, 3.0)
    U = solve_displacement(K, prob.F, prob.free_dofs)
    _, dc, _ = compliance_and_sensitivity(x, U, edofMat, KE, 3.0)
    assert (dc <= 1e-12).all(), f"positive sensitivity found: max={dc.max():.4e}"
