"""Element stress recovery and aggregation utilities for Phase 5."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StressSummary:
    """Compact stress metrics for reporting and future constraints."""

    peak: float
    pnorm: float
    ks: float
    mean: float


@dataclass(frozen=True)
class StressAnalysis:
    """Recovered stress field and aggregate metrics for a solved design."""

    displacement: np.ndarray
    von_mises: np.ndarray
    relaxed_von_mises: np.ndarray
    compliance: float
    summary: StressSummary


def elasticity_matrix_2d(E: float = 1.0, nu: float = 0.3) -> np.ndarray:
    """Plane-stress constitutive matrix for strains [exx, eyy, gxy]."""
    return (E / (1.0 - nu**2)) * np.array(
        [
            [1.0, nu, 0.0],
            [nu, 1.0, 0.0],
            [0.0, 0.0, 0.5 * (1.0 - nu)],
        ],
        dtype=np.float64,
    )


def elasticity_matrix_3d(E: float = 1.0, nu: float = 0.3) -> np.ndarray:
    """3D isotropic constitutive matrix for [exx, eyy, ezz, gxy, gyz, gxz]."""
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E / (2.0 * (1.0 + nu))
    D = np.zeros((6, 6), dtype=np.float64)
    D[:3, :3] = lam
    np.fill_diagonal(D[:3, :3], lam + 2.0 * mu)
    D[3, 3] = mu
    D[4, 4] = mu
    D[5, 5] = mu
    return D


def q4_B_centroid() -> np.ndarray:
    """Strain-displacement matrix at the centroid of a unit Q4 element."""
    dndx = np.array([-0.5, 0.5, 0.5, -0.5], dtype=np.float64)
    dndy = np.array([-0.5, -0.5, 0.5, 0.5], dtype=np.float64)
    B = np.zeros((3, 8), dtype=np.float64)
    B[0, 0::2] = dndx
    B[1, 1::2] = dndy
    B[2, 0::2] = dndy
    B[2, 1::2] = dndx
    return B


def h8_B_centroid() -> np.ndarray:
    """Strain-displacement matrix at the centroid of a unit H8 element."""
    xi = np.array([-1, 1, 1, -1, -1, 1, 1, -1], dtype=np.float64)
    eta = np.array([-1, -1, 1, 1, -1, -1, 1, 1], dtype=np.float64)
    zeta = np.array([-1, -1, -1, -1, 1, 1, 1, 1], dtype=np.float64)
    dndx = 0.25 * xi
    dndy = 0.25 * eta
    dndz = 0.25 * zeta

    B = np.zeros((6, 24), dtype=np.float64)
    B[0, 0::3] = dndx
    B[1, 1::3] = dndy
    B[2, 2::3] = dndz
    B[3, 0::3] = dndy
    B[3, 1::3] = dndx
    B[4, 1::3] = dndz
    B[4, 2::3] = dndy
    B[5, 0::3] = dndz
    B[5, 2::3] = dndx
    return B


def von_mises_2d(stress: np.ndarray) -> np.ndarray:
    """Plane-stress von Mises from [sx, sy, txy]."""
    sx = stress[..., 0]
    sy = stress[..., 1]
    txy = stress[..., 2]
    return np.sqrt(np.maximum(sx**2 - sx * sy + sy**2 + 3.0 * txy**2, 0.0))


def von_mises_3d(stress: np.ndarray) -> np.ndarray:
    """3D von Mises from [sx, sy, sz, txy, tyz, txz]."""
    sx = stress[..., 0]
    sy = stress[..., 1]
    sz = stress[..., 2]
    txy = stress[..., 3]
    tyz = stress[..., 4]
    txz = stress[..., 5]
    vm2 = 0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
    vm2 += 3.0 * (txy**2 + tyz**2 + txz**2)
    return np.sqrt(np.maximum(vm2, 0.0))


def element_von_mises_2d(
    U: np.ndarray,
    edofMat: np.ndarray,
    *,
    E: float = 1.0,
    nu: float = 0.3,
) -> np.ndarray:
    """Recover centroid von Mises stress for each Q4 element."""
    B = q4_B_centroid()
    D = elasticity_matrix_2d(E=E, nu=nu)
    strains = U[edofMat] @ B.T
    stresses = strains @ D.T
    return von_mises_2d(stresses)


def element_von_mises_3d(
    U: np.ndarray,
    edofMat: np.ndarray,
    *,
    E: float = 1.0,
    nu: float = 0.3,
) -> np.ndarray:
    """Recover centroid von Mises stress for each H8 element."""
    B = h8_B_centroid()
    D = elasticity_matrix_3d(E=E, nu=nu)
    strains = U[edofMat] @ B.T
    stresses = strains @ D.T
    return von_mises_3d(stresses)


def apply_qp_relaxation(
    von_mises: np.ndarray,
    density: np.ndarray,
    *,
    q: float = 2.7,
    x_floor: float = 1e-3,
) -> np.ndarray:
    """Scale stress by x^q so near-void elements do not dominate constraints."""
    x_phys = np.maximum(np.asarray(density, dtype=np.float64), x_floor)
    return np.asarray(von_mises, dtype=np.float64) * (x_phys**q)


def stress_p_norm(
    stress: np.ndarray,
    *,
    stress_limit: float = 1.0,
    p: float = 8.0,
    mask: np.ndarray | None = None,
    normalized: bool = False,
) -> float:
    """Aggregate stress ratios with a p-norm."""
    values = _masked_ratios(stress, stress_limit, mask)
    if values.size == 0:
        return 0.0
    total = float(np.sum(values**p))
    if normalized:
        total /= values.size
    return total ** (1.0 / p)


def stress_ks(
    stress: np.ndarray,
    *,
    stress_limit: float = 1.0,
    rho: float = 35.0,
    mask: np.ndarray | None = None,
) -> float:
    """Kreisselmeier-Steinhauser aggregate of stress ratios."""
    values = _masked_ratios(stress, stress_limit, mask)
    if values.size == 0:
        return 0.0
    vmax = float(np.max(values))
    return vmax + float(np.log(np.sum(np.exp(rho * (values - vmax)))) / rho)


def summarize_stress(
    stress: np.ndarray,
    *,
    stress_limit: float = 1.0,
    p: float = 8.0,
    rho: float = 35.0,
    mask: np.ndarray | None = None,
) -> StressSummary:
    """Return peak, p-norm, KS, and mean stress over an optional mask."""
    values = np.asarray(stress, dtype=np.float64)
    if mask is not None:
        values = values[np.asarray(mask, dtype=bool)]
    if values.size == 0:
        return StressSummary(peak=0.0, pnorm=0.0, ks=0.0, mean=0.0)
    return StressSummary(
        peak=float(np.max(values)),
        pnorm=stress_p_norm(values, stress_limit=stress_limit, p=p),
        ks=stress_ks(values, stress_limit=stress_limit, rho=rho),
        mean=float(np.mean(values)),
    )


def analyze_design_stress(
    problem,
    density: np.ndarray,
    *,
    penal: float = 3.0,
    E0: float = 1.0,
    Emin: float = 1e-9,
    nu: float = 0.3,
    q: float = 2.7,
    stress_limit: float = 1.0,
    p: float = 8.0,
    rho: float = 35.0,
    mask: np.ndarray | None = None,
) -> StressAnalysis:
    """Solve the FE state and recover relaxed von Mises stress for a design."""
    from .fea import (
        assemble_K,
        build_assembly_indices,
        build_edof,
        build_edof_3d,
        element_stiffness,
        element_stiffness_3d,
        solve_displacement,
    )

    is_3d = problem.nelz > 0
    if is_3d:
        KE = element_stiffness_3d(E=1.0, nu=nu)
        edofMat = build_edof_3d(problem.nelx, problem.nely, problem.nelz)
    else:
        KE = element_stiffness(E=1.0, nu=nu)
        edofMat = build_edof(problem.nelx, problem.nely)

    x = np.asarray(density, dtype=np.float64).reshape(-1)
    iK, jK = build_assembly_indices(edofMat)
    K = assemble_K(x, KE, iK, jK, problem.ndof, penal, E0, Emin)
    U = solve_displacement(K, problem.F, problem.free_dofs)

    if is_3d:
        von_mises = element_von_mises_3d(U, edofMat, E=E0, nu=nu)
    else:
        von_mises = element_von_mises_2d(U, edofMat, E=E0, nu=nu)

    relaxed = apply_qp_relaxation(von_mises, x, q=q, x_floor=max(Emin, 1e-3))
    if mask is None and getattr(problem, "region_masks", None) is not None:
        mask = ~problem.region_masks.void
    summary = summarize_stress(
        relaxed,
        stress_limit=stress_limit,
        p=p,
        rho=rho,
        mask=mask,
    )
    return StressAnalysis(
        displacement=U,
        von_mises=von_mises,
        relaxed_von_mises=relaxed,
        compliance=float(np.dot(problem.F, U)),
        summary=summary,
    )


def _masked_ratios(
    stress: np.ndarray,
    stress_limit: float,
    mask: np.ndarray | None,
) -> np.ndarray:
    if stress_limit <= 0.0:
        raise ValueError("stress_limit must be positive")
    values = np.asarray(stress, dtype=np.float64)
    if mask is not None:
        values = values[np.asarray(mask, dtype=bool)]
    return np.maximum(values / stress_limit, 0.0)
