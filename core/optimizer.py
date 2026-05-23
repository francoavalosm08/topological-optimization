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
from .problem import Problem, RegionMasks


@dataclass
class OptParams:
    method: str = "oc"          # "oc", "mma", or "stress"
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
    stress_limit: float = 2.0
    stress_q: float = 2.7
    stress_pnorm: float = 8.0
    stress_ks_rho: float = 35.0
    stress_relief_radius: float = 3.0
    stress_relief_steps: int = 4
    stress_accept_tol: float = 1e-3
    stress_hotspot_density: float = 0.9
    stress_max_compliance_factor: float = 2.0

# Alias for backwards compatibility with Phase 1 scripts
OCParams = OptParams


@dataclass
class RunHistory:
    iters: list[int] = field(default_factory=list)
    compliance: list[float] = field(default_factory=list)
    change: list[float] = field(default_factory=list)
    volume: list[float] = field(default_factory=list)
    stress_peak: list[float] = field(default_factory=list)
    stress_pnorm: list[float] = field(default_factory=list)
    stress_ks: list[float] = field(default_factory=list)


def apply_region_constraints(
    x: np.ndarray,
    masks: RegionMasks,
    *,
    x_void: float,
) -> np.ndarray:
    """Pin passive voxels to 1 and void voxels to ``x_void``."""
    out = x.copy()
    out[masks.passive_solid] = 1.0
    out[masks.void] = x_void
    return out


def oc_update(
    x: np.ndarray,
    dc: np.ndarray,
    dv: np.ndarray,
    volfrac: float,
    move: float = 0.2,
    eta: float = 0.5,
    design_mask: np.ndarray | None = None,
) -> np.ndarray:
    """One OC step. Bisection on the Lagrange multiplier lambda.

    Volume target is ``volfrac * sum(dv)`` (``dv`` is zero outside the design region).
    """
    l1, l2 = 1e-9, 1e9
    xnew = np.empty_like(x)
    target = volfrac * float(np.sum(dv))
    dc_neg = np.minimum(dc, 0.0)
    while (l2 - l1) / max(l1 + l2, 1e-30) > 1e-3:
        lmid = 0.5 * (l1 + l2)
        be = np.zeros_like(dc_neg)
        np.divide(-dc_neg, lmid * dv, out=be, where=dv > 0)
        be = np.maximum(be, 0.0)
        xcand = x * (be ** eta)
        xnew = np.maximum(
            0.0,
            np.maximum(
                x - move,
                np.minimum(1.0, np.minimum(x + move, xcand)),
            ),
        )
        if np.sum(xnew * dv) > target:
            l1 = lmid
        else:
            l2 = lmid
    if design_mask is not None:
        xnew = np.where(design_mask, xnew, x)
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
    masks: RegionMasks | None = None,
    x_void: float = 1e-3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import mmapy.mma
    n = x.size
    m = 1
    
    xval = x.reshape(n, 1)
    xmin = np.zeros((n, 1))
    xmax = np.ones((n, 1))
    if masks is not None:
        xmin[masks.passive_solid, 0] = 1.0
        xmax[masks.passive_solid, 0] = 1.0
        xmin[masks.void, 0] = x_void
        xmax[masks.void, 0] = x_void
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


def _stress_analysis(problem: Problem, x: np.ndarray, p: OptParams, masks: RegionMasks):
    from .stress import analyze_design_stress

    return analyze_design_stress(
        problem,
        x,
        penal=p.penal,
        E0=p.E0,
        Emin=p.Emin,
        nu=p.nu,
        q=p.stress_q,
        stress_limit=p.stress_limit,
        p=p.stress_pnorm,
        rho=p.stress_ks_rho,
        mask=~masks.void,
    )


def _record_stress_metrics(hist: RunHistory, analysis) -> None:
    hist.stress_peak.append(analysis.summary.peak)
    hist.stress_pnorm.append(analysis.summary.pnorm)
    hist.stress_ks.append(analysis.summary.ks)


def _hotspot_relief_mask(
    problem: Problem,
    design_mask: np.ndarray,
    stress_values: np.ndarray,
    radius: float,
) -> np.ndarray:
    """Column-through-thickness relief region around the hottest design element."""
    if not np.any(design_mask):
        return np.zeros_like(design_mask)

    active_stress = np.where(design_mask, stress_values, -np.inf)
    hot_idx = int(np.argmax(active_stress))
    if not np.isfinite(active_stress[hot_idx]):
        return np.zeros_like(design_mask)

    if problem.nelz > 0:
        shape = (problem.nelx, problem.nely, problem.nelz)
        hot_x, hot_y, _ = np.unravel_index(hot_idx, shape, order="C")
        xx, yy, _ = np.meshgrid(
            np.arange(problem.nelx),
            np.arange(problem.nely),
            np.arange(problem.nelz),
            indexing="ij",
        )
        dist = np.sqrt(((xx - hot_x) / radius) ** 2 + ((yy - hot_y) / radius) ** 2)
        return (dist < 1.0).ravel(order="C") & design_mask

    shape = (problem.nelx, problem.nely)
    hot_x, hot_y = np.unravel_index(hot_idx, shape, order="C")
    xx, yy = np.meshgrid(np.arange(problem.nelx), np.arange(problem.nely), indexing="ij")
    dist = np.sqrt(((xx - hot_x) / radius) ** 2 + ((yy - hot_y) / radius) ** 2)
    return (dist < 1.0).ravel(order="C") & design_mask


def _rebalance_design_volume(
    candidate: np.ndarray,
    reference: np.ndarray,
    masks: RegionMasks,
    protected: np.ndarray,
    stress_values: np.ndarray,
    *,
    x_void: float,
) -> np.ndarray:
    """Drain low-stress design elements so hotspot reinforcement keeps volume."""
    out = candidate.copy()
    target = float(np.sum(reference[masks.design]))
    excess = float(np.sum(out[masks.design]) - target)
    if excess <= 0.0:
        return out

    drainable = masks.design & ~protected
    drain_order = np.flatnonzero(drainable)[np.argsort(stress_values[drainable])]
    for idx in drain_order:
        if excess <= 1e-12:
            break
        available = max(0.0, out[idx] - x_void)
        take = min(excess, available)
        if take > 0.0:
            out[idx] -= take
            excess -= take
    return out


def _run_stress_relief(
    problem: Problem,
    x: np.ndarray,
    p: OptParams,
    masks: RegionMasks,
    hist: RunHistory,
    on_iter: Callable[[int, np.ndarray, float, float], None] | None,
    x_void: float,
) -> np.ndarray:
    """Accepted stress-aware redistribution pass for the Phase 5 L-bracket gate.

    This is a pragmatic stress-aware continuation. It reinforces verified
    hotspots, drains equal volume from low-stress elements, and accepts only
    changes that lower the KS aggregate without a large compliance regression.
    The full analytic MMA stress-sensitivity path is left as a later upgrade.
    """
    current = _stress_analysis(problem, x, p, masks)
    if hist.stress_peak:
        hist.stress_peak[-1] = current.summary.peak
        hist.stress_pnorm[-1] = current.summary.pnorm
        hist.stress_ks[-1] = current.summary.ks
    else:
        _record_stress_metrics(hist, current)

    radii = [
        max(1.0, p.stress_relief_radius),
        max(1.0, p.stress_relief_radius - 1.0),
        max(1.0, p.stress_relief_radius + 1.0),
    ]

    for _ in range(max(0, p.stress_relief_steps)):
        if current.summary.ks <= 1.0:
            break

        best_x = None
        best_analysis = current
        best_change = 0.0
        for radius in radii:
            relief = _hotspot_relief_mask(
                problem,
                masks.design,
                current.relaxed_von_mises,
                radius,
            )
            if not np.any(relief):
                continue

            candidate = x.copy()
            candidate[relief] = np.maximum(candidate[relief], p.stress_hotspot_density)
            candidate = _rebalance_design_volume(
                candidate,
                x,
                masks,
                relief,
                current.relaxed_von_mises,
                x_void=x_void,
            )
            candidate = apply_region_constraints(candidate, masks, x_void=x_void)
            change = float(np.max(np.abs(candidate[masks.design] - x[masks.design])))
            if change == 0.0:
                continue

            analysis = _stress_analysis(problem, candidate, p, masks)
            if analysis.compliance > current.compliance * p.stress_max_compliance_factor:
                continue
            if analysis.summary.ks < best_analysis.summary.ks:
                best_x = candidate
                best_analysis = analysis
                best_change = change

        min_improvement = p.stress_accept_tol * max(1.0, abs(current.summary.ks))
        if best_x is None or best_analysis.summary.ks > current.summary.ks - min_improvement:
            break

        x = best_x
        current = best_analysis
        it = hist.iters[-1] + 1 if hist.iters else 0
        hist.iters.append(it)
        hist.compliance.append(current.compliance)
        hist.change.append(best_change)
        hist.volume.append(float(x[masks.design].mean()) if masks.design.any() else 0.0)
        _record_stress_metrics(hist, current)

        if on_iter is not None:
            on_iter(it, x, current.compliance, best_change)

    return x


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

    masks = problem.region_masks
    assert masks is not None
    x_void = max(p.Emin, 1e-3)

    x_init = p.volfrac if p.x_init is None else p.x_init
    x = np.full(N, x_init, dtype=np.float64)
    x = apply_region_constraints(x, masks, x_void=x_void)

    F = problem.F
    free_dofs = problem.free_dofs
    ndof = problem.ndof
    dv_design = masks.design.astype(np.float64)

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
        dc = dc * masks.design
        dc = apply_sensitivity_filter(dc, x, H, Hs)

        method = p.method.lower()
        if method == "mma":
            xnew, low, upp = mma_update(
                x, c, dc, dv_design, p.volfrac, it, xold1, xold2, low, upp,
                masks=masks, x_void=x_void,
            )
        else:
            xnew = oc_update(
                x, dc, dv_design, p.volfrac, move=p.move, eta=p.eta,
                design_mask=masks.design,
            )

        xnew = apply_region_constraints(xnew, masks, x_void=x_void)
        change = float(np.abs(xnew[masks.design] - x[masks.design]).max()) if masks.design.any() else 0.0
        xold2 = xold1.copy()
        xold1 = x.copy()
        x = xnew

        hist.iters.append(it)
        hist.compliance.append(c)
        hist.change.append(change)
        design_mean = float(x[masks.design].mean()) if masks.design.any() else 0.0
        hist.volume.append(design_mean)
        hist.stress_peak.append(float("nan"))
        hist.stress_pnorm.append(float("nan"))
        hist.stress_ks.append(float("nan"))

        if on_iter is not None:
            on_iter(it, x, c, change)

        if change < p.tol:
            break

    if p.method.lower() in ("stress", "stress_oc", "stress-relief"):
        x = _run_stress_relief(problem, x, p, masks, hist, on_iter, x_void)

    if is_3d:
        try:
            from .postprocess import export_density_to_mesh
            export_density_to_mesh(x.reshape((nelx, nely, nelz)), "runs", "opt_final")
        except Exception as e:
            print(f"Error during mesh export: {e}")

    return x, hist
