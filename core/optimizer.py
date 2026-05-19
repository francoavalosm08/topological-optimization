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
class OptParams:
    method: str = "oc"          # "oc" or "mma"
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

# Alias for backwards compatibility with Phase 1 scripts
OCParams = OptParams


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


def mma_update(
    x: np.ndarray,
    c: float,
    dc: np.ndarray,
    dv: np.ndarray,
    volfrac: float,
    it: int,
    xold1: np.ndarray,
    xold2: np.ndarray,
    low: np.ndarray,
    upp: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import mmapy.mma
    n = x.size
    m = 1
    
    xval = x.reshape(n, 1)
    xmin = np.zeros((n, 1))
    xmax = np.ones((n, 1))
    xold1_col = xold1.reshape(n, 1)
    xold2_col = xold2.reshape(n, 1)
    
    f0val = c
    df0dx = dc.reshape(n, 1)
    
    V_target = volfrac * np.sum(dv)
    V_current = np.sum(x * dv)
    fval = np.array([[V_current / V_target - 1.0]])
    dfdx = (dv / V_target).reshape(1, n)
    
    low_col = low.reshape(n, 1)
    upp_col = upp.reshape(n, 1)
    
    a0 = 1.0
    a = np.zeros((m, 1))
    c_mma = np.full((m, 1), 1000.0)
    d_mma = np.zeros((m, 1))
    
    res = mmapy.mma.mmasub(
        m, n, it + 1, xval, xmin, xmax, xold1_col, xold2_col,
        f0val, df0dx, fval, dfdx, low_col, upp_col, a0, a, c_mma, d_mma
    )
    xmma, _, _, _, _, _, _, _, _, low_new, upp_new = res
    return xmma.flatten(), low_new.flatten(), upp_new.flatten()


def run_topopt(
    problem: Problem,
    params: OptParams | None = None,
    on_iter: Callable[[int, np.ndarray, float, float], None] | None = None,
) -> tuple[np.ndarray, RunHistory]:
    """Run the Phase 1 SIMP+OC compliance optimizer.

    Returns the final flat density `x` (length nelx*nely, column-major) and history.
    """
    p = params or OptParams()
    nelx, nely, nelz = problem.nelx, problem.nely, problem.nelz
    is_3d = nelz > 0
    N = nelx * nely * nelz if is_3d else nelx * nely

    if is_3d:
        from .fea import element_stiffness_3d, build_edof_3d
        KE = element_stiffness_3d(E=1.0, nu=p.nu)
        edofMat = build_edof_3d(nelx, nely, nelz)
        H, Hs = build_filter(nelx, nely, nelz, p.rmin)
    else:
        KE = element_stiffness(E=1.0, nu=p.nu)
        edofMat = build_edof(nelx, nely)
        H, Hs = build_filter(nelx, nely, 0, p.rmin)

    iK, jK = build_assembly_indices(edofMat)

    x_init = p.volfrac if p.x_init is None else p.x_init
    x = np.full(N, x_init, dtype=np.float64)

    F = problem.F
    free_dofs = problem.free_dofs
    ndof = problem.ndof

    hist = RunHistory()
    
    # MMA state
    xold1 = x.copy()
    xold2 = x.copy()
    low = np.zeros(N)
    upp = np.ones(N)

    for it in range(p.max_iter):
        K = assemble_K(x, KE, iK, jK, ndof, p.penal, p.E0, p.Emin)
        U = solve_displacement(K, F, free_dofs)
        c, dc, _ = compliance_and_sensitivity(x, U, edofMat, KE, p.penal, p.E0, p.Emin)
        dv = np.ones(N, dtype=np.float64)

        dc = apply_sensitivity_filter(dc, x, H, Hs)

        if p.method.lower() == "mma":
            xnew, low, upp = mma_update(x, c, dc, dv, p.volfrac, it, xold1, xold2, low, upp)
        else:
            xnew = oc_update(x, dc, dv, p.volfrac, move=p.move, eta=p.eta)
            
        change = float(np.abs(xnew - x).max())
        xold2 = xold1.copy()
        xold1 = x.copy()
        x = xnew

        hist.iters.append(it)
        hist.compliance.append(c)
        hist.change.append(change)
        hist.volume.append(float(x.mean()))

        if on_iter is not None:
            on_iter(it, x, c, change)

        if change < p.tol:
            break

    if is_3d:
        try:
            from .postprocess import export_density_to_mesh
            export_density_to_mesh(x.reshape((nelx, nely, nelz)), "runs", "opt_final")
        except Exception as e:
            print(f"Error during mesh export: {e}")

    return x, hist
