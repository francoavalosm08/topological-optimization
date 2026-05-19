"""Length-scale filters for SIMP topology optimization (Phase 1: sensitivity filter)."""
from __future__ import annotations

import numpy as np
import scipy.sparse


def build_filter(nelx: int, nely: int, rmin: float) -> tuple[scipy.sparse.csr_matrix, np.ndarray]:
    """Build the convolution operator H (Sigmund 1994/1997).

    H[e, i] = max(0, rmin - dist(center_e, center_i))
    Element centers are at (elx + 0.5, ely + 0.5); distance is in element units.
    Returns (H, Hs) where Hs[e] = sum_i H[e, i] (row sums for normalization).
    """
    nelx, nely = int(nelx), int(nely)
    rceil = int(np.ceil(rmin))
    nmax = nelx * nely * (2 * rceil - 1) ** 2  # upper bound on nonzeros
    iH = np.empty(nmax, dtype=np.int64)
    jH = np.empty(nmax, dtype=np.int64)
    sH = np.empty(nmax, dtype=np.float64)
    cc = 0
    for elx in range(nelx):
        for ely in range(nely):
            row = elx * nely + ely
            kk_min = max(elx - (rceil - 1), 0)
            kk_max = min(elx + rceil, nelx)
            ll_min = max(ely - (rceil - 1), 0)
            ll_max = min(ely + rceil, nely)
            for kx in range(kk_min, kk_max):
                for ly in range(ll_min, ll_max):
                    col = kx * nely + ly
                    fac = rmin - np.sqrt((elx - kx) ** 2 + (ely - ly) ** 2)
                    if fac > 0.0:
                        iH[cc] = row
                        jH[cc] = col
                        sH[cc] = fac
                        cc += 1
    H = scipy.sparse.csr_matrix(
        (sH[:cc], (iH[:cc], jH[:cc])), shape=(nelx * nely, nelx * nely)
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
