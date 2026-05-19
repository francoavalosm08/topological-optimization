"""2D Q4 plane-stress FEA for SIMP topology optimization.

Conventions (Phase 1, zero-based throughout):
  - Domain is `nelx` columns by `nely` rows of square unit-side Q4 elements.
  - x-axis points right (increasing column index), y-axis points DOWN
    (increasing row index) — matches top88.m / Andreassen et al. (2011).
  - Nodes are numbered column-major: node(col, row) = col * (nely+1) + row.
    Total nodes = (nelx+1) * (nely+1). Total DOFs = 2 * nodes.
  - Each node has 2 DOFs: x first, then y. DOF indices: 2*node, 2*node+1.
  - Elements are numbered column-major: elem(elx, ely) = elx * nely + ely.
  - Density array `x` is flat, length nelx*nely, in the same column-major order.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse
import scipy.sparse.linalg


def element_stiffness(E: float = 1.0, nu: float = 0.3) -> np.ndarray:
    """8x8 plane-stress stiffness for a square Q4 element of unit side.

    Canonical closed form from Sigmund (2001), 99-line code.
    """
    k = np.array([
        1/2 - nu/6,    1/8 + nu/8,   -1/4 - nu/12,  -1/8 + 3*nu/8,
       -1/4 + nu/12,  -1/8 - nu/8,    nu/6,          1/8 - 3*nu/8,
    ])
    KE = (E / (1 - nu**2)) * np.array([
        [k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]],
        [k[1], k[0], k[7], k[6], k[5], k[4], k[3], k[2]],
        [k[2], k[7], k[0], k[5], k[6], k[3], k[4], k[1]],
        [k[3], k[6], k[5], k[0], k[7], k[2], k[1], k[4]],
        [k[4], k[5], k[6], k[7], k[0], k[1], k[2], k[3]],
        [k[5], k[4], k[3], k[2], k[1], k[0], k[7], k[6]],
        [k[6], k[3], k[4], k[1], k[2], k[7], k[0], k[5]],
        [k[7], k[2], k[1], k[4], k[3], k[6], k[5], k[0]],
    ])
    return KE


def build_edof(nelx: int, nely: int) -> np.ndarray:
    """Element-to-DOF connectivity table, shape (nelx*nely, 8).

    Node ordering counter-clockwise from top-left of element:
        n1 = (elx,   ely)         n2 = (elx+1, ely)
        n4 = (elx,   ely+1)       n3 = (elx+1, ely+1)
    Each node contributes [2*node, 2*node+1] (x then y) to the 8-DOF row.
    """
    elx, ely = np.meshgrid(np.arange(nelx), np.arange(nely), indexing="ij")
    elx = elx.ravel()
    ely = ely.ravel()
    n1 = elx * (nely + 1) + ely
    n2 = (elx + 1) * (nely + 1) + ely
    n3 = (elx + 1) * (nely + 1) + ely + 1
    n4 = elx * (nely + 1) + ely + 1
    edof = np.column_stack([
        2*n1, 2*n1 + 1,
        2*n2, 2*n2 + 1,
        2*n3, 2*n3 + 1,
        2*n4, 2*n4 + 1,
    ]).astype(np.int64)
    return edof


def build_assembly_indices(edofMat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """COO row/col arrays for sparse stiffness assembly."""
    # For each element row e of length 8: outer-product layout (8x8) → 64.
    # Row index repeats each DOF 8 times; col index tiles the 8-DOF list 8 times.
    iK = np.repeat(edofMat, 8, axis=1).ravel()
    jK = np.tile(edofMat, (1, 8)).ravel()
    return iK, jK


def assemble_K(
    x: np.ndarray,
    KE: np.ndarray,
    iK: np.ndarray,
    jK: np.ndarray,
    ndof: int,
    penal: float,
    E0: float = 1.0,
    Emin: float = 1e-9,
) -> scipy.sparse.csc_matrix:
    """Assemble global stiffness via SIMP interpolation."""
    E_arr = Emin + (x ** penal) * (E0 - Emin)            # (N,)
    sK = (E_arr[:, None] * KE.ravel()[None, :]).ravel()  # (N*64,)
    K = scipy.sparse.coo_matrix((sK, (iK, jK)), shape=(ndof, ndof)).tocsc()
    return K


def solve_displacement(
    K: scipy.sparse.csc_matrix,
    F: np.ndarray,
    free_dofs: np.ndarray,
) -> np.ndarray:
    """Solve K U = F with Dirichlet conditions (fixed DOFs = 0)."""
    U = np.zeros(F.shape[0], dtype=np.float64)
    Kff = K[free_dofs, :][:, free_dofs]
    U[free_dofs] = scipy.sparse.linalg.spsolve(Kff, F[free_dofs])
    return U


def compliance_and_sensitivity(
    x: np.ndarray,
    U: np.ndarray,
    edofMat: np.ndarray,
    KE: np.ndarray,
    penal: float,
    E0: float = 1.0,
    Emin: float = 1e-9,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Return (c, dc/dx, element strain energy at E=1).

    dc/dx_e = -p * x_e^(p-1) * (E0 - Emin) * (u_e^T k0 u_e)   (adjoint result)
    c       = sum_e (Emin + x_e^p * (E0 - Emin)) * (u_e^T k0 u_e)
    """
    ue = U[edofMat]                                 # (N, 8)
    ce_unit = np.einsum("ei,ij,ej->e", ue, KE, ue)  # (N,)  strain energy at E=1
    E_arr = Emin + (x ** penal) * (E0 - Emin)
    c = float(np.sum(E_arr * ce_unit))
    dc = -penal * (x ** (penal - 1.0)) * (E0 - Emin) * ce_unit
    return c, dc, ce_unit
