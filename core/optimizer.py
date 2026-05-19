"""SIMP topology optimizer — Optimality Criteria (OC) main loop (Phase 1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .fea import (
    assemble_K,
    build_assembly_indices,
    build_edof,
    compliance_and_sensitivity,
    element_stiffness,
    solve_displacement,
)
from .filters import apply_sensitivity_filter, build_filter
from .problem import Problem


@dataclass
class OCParams:
    volfrac: float = 0.5
    penal: float = 3.0
    rmin: float = 1.5
    move: float = 0.2
    eta: float = 0.5            # OC damping exponent
    max_iter: int = 200
    tol: float = 0.01           # convergence on max|x_new - x_old|
    x_init: float | None = None # default = volfrac (uniform)
    E0: float = 1.0
    Emin: float = 1e-9
    nu: float = 0.3


@dataclass
class RunHistory:
    iters: list[int] = field(default_factory=list)
    compliance: list[float] = field(default_factory=list)
    change: list[float] = field(default_factory=list)
    volume: list[float] = field(default_factory=list)


def oc_update(
    x: np.ndarray,
    dc: np.ndarray,
    dv: np.ndarray,
    volfrac: float,
    move: float = 0.2,
    eta: float = 0.5,
) -> np.ndarray:
    """One OC step. Bisection on the Lagrange multiplier lambda.

    Update rule (Bendsoe & Sigmund 2003):
        B_e   = -dc_e / (lambda * dv_e)
        x_new = clip( x * B_e^eta, [x - move, x + move] inside [0, 1] )

    lambda found such that mean(x_new) == volfrac.
    """
    l1, l2 = 1e-9, 1e9
    xnew = np.empty_like(x)
    target = volfrac * x.size
    # dc must be negative for OC to be meaningful; clamp upper at 0.
    dc_neg = np.minimum(dc, 0.0)
    while (l2 - l1) / max(l1 + l2, 1e-30) > 1e-3:
        lmid = 0.5 * (l1 + l2)
        be = -dc_neg / (lmid * dv)
        be = np.maximum(be, 0.0)
        xcand = x * (be ** eta)
        xnew = np.maximum(
            0.0,
            np.maximum(
                x - move,
                np.minimum(1.0, np.minimum(x + move, xcand)),
            ),
        )
        if xnew.sum() > target:
            l1 = lmid
        else:
            l2 = lmid
    return xnew


def run_topopt(
    problem: Problem,
    params: OCParams | None = None,
    on_iter: Callable[[int, np.ndarray, float, float], None] | None = None,
) -> tuple[np.ndarray, RunHistory]:
    """Run the Phase 1 SIMP+OC compliance optimizer.

    Returns the final flat density `x` (length nelx*nely, column-major) and history.
    """
    p = params or OCParams()
    nelx, nely = problem.nelx, problem.nely
    N = nelx * nely

    KE = element_stiffness(E=1.0, nu=p.nu)        # element stiffness at E=1
    edofMat = build_edof(nelx, nely)
    iK, jK = build_assembly_indices(edofMat)
    H, Hs = build_filter(nelx, nely, p.rmin)

    x_init = p.volfrac if p.x_init is None else p.x_init
    x = np.full(N, x_init, dtype=np.float64)

    F = problem.F
    free_dofs = problem.free_dofs
    ndof = problem.ndof

    hist = RunHistory()

    for it in range(p.max_iter):
        K = assemble_K(x, KE, iK, jK, ndof, p.penal, p.E0, p.Emin)
        U = solve_displacement(K, F, free_dofs)
        c, dc, _ = compliance_and_sensitivity(x, U, edofMat, KE, p.penal, p.E0, p.Emin)
        dv = np.ones(N, dtype=np.float64)

        dc = apply_sensitivity_filter(dc, x, H, Hs)

        xnew = oc_update(x, dc, dv, p.volfrac, move=p.move, eta=p.eta)
        change = float(np.abs(xnew - x).max())
        x = xnew

        hist.iters.append(it)
        hist.compliance.append(c)
        hist.change.append(change)
        hist.volume.append(float(x.mean()))

        if on_iter is not None:
            on_iter(it, x, c, change)

        if change < p.tol:
            break

    return x, hist
