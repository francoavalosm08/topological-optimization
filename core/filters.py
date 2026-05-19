"""Length-scale filters for SIMP topology optimization (Phase 1: sensitivity filter)."""
from __future__ import annotations

import numpy as np
import scipy.sparse


def build_filter(nelx: int, nely: int, nelz: int, rmin: float) -> tuple[scipy.sparse.csr_matrix, np.ndarray]:
    """Build the convolution operator H (Sigmund 1994/1997).

    H[e, i] = max(0, rmin - dist(center_e, center_i))
    Element centers are at (elx + 0.5, ely + 0.5); distance is in element units.
    Returns (H, Hs) where Hs[e] = sum_i H[e, i] (row sums for normalization).
    """
    nelx, nely, nelz = int(nelx), int(nely), int(nelz)
    is_3d = nelz > 1
    if nelz == 0:
        nelz = 1
        
    rceil = int(np.ceil(rmin))
    nmax = nelx * nely * nelz * (2 * rceil - 1) ** (3 if is_3d else 2)
    iH = np.empty(nmax, dtype=np.int64)
    jH = np.empty(nmax, dtype=np.int64)
    sH = np.empty(nmax, dtype=np.float64)
    cc = 0
    for elx in range(nelx):
        for ely in range(nely):
            for elz_idx in range(nelz):
                row = elx * (nely * nelz) + ely * nelz + elz_idx
                kk_min = max(elx - (rceil - 1), 0)
                kk_max = min(elx + rceil, nelx)
                ll_min = max(ely - (rceil - 1), 0)
                ll_max = min(ely + rceil, nely)
                mm_min = max(elz_idx - (rceil - 1), 0) if is_3d else 0
                mm_max = min(elz_idx + rceil, nelz) if is_3d else 1
                
                for kx in range(kk_min, kk_max):
                    for ly in range(ll_min, ll_max):
                        for mz in range(mm_min, mm_max):
                            col = kx * (nely * nelz) + ly * nelz + mz
                            dist = np.sqrt((elx - kx) ** 2 + (ely - ly) ** 2 + (elz_idx - mz) ** 2)
                            fac = rmin - dist
                            if fac > 0.0:
                                iH[cc] = row
                                jH[cc] = col
                                sH[cc] = fac
                                cc += 1
    N = nelx * nely * nelz
    H = scipy.sparse.csr_matrix(
        (sH[:cc], (iH[:cc], jH[:cc])), shape=(N, N)
    )
    Hs = np.asarray(H.sum(axis=1)).ravel()
    return H, Hs


def apply_sensitivity_filter(
    dc: np.ndarray, x: np.ndarray, H: scipy.sparse.csr_matrix, Hs: np.ndarray
) -> np.ndarray:
    """Sigmund's original sensitivity filter.

    dc_filt[e] = sum_i (H[e,i] * x[i] * dc[i]) / (max(x[e], 1e-3) * sum_i H[e,i])

    The 1e-3 floor prevents division-by-zero at void elements; it is *not*
    the SIMP Emin (which lives in the stiffness interpolation).
    """
    return np.asarray(H @ (x * dc) / Hs) / np.maximum(x, 1e-3)
