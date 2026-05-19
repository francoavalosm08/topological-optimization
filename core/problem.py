"""Problem definitions: design domain + BCs + loads."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Problem:
    """Phase-1 problem container (2D).

    Attributes:
        name: human label, used for output filenames.
        nelx, nely: design domain dims (elements).
        F: global load vector, shape (ndof,).
        fixed_dofs: 1-D int array of constrained DOF indices.
    """
    name: str
    nelx: int
    nely: int
    F: np.ndarray
    fixed_dofs: np.ndarray
    nelz: int = 0

    @property
    def ndof(self) -> int:
        if self.nelz > 0:
            return 3 * (self.nelx + 1) * (self.nely + 1) * (self.nelz + 1)
        return 2 * (self.nelx + 1) * (self.nely + 1)

    @property
    def free_dofs(self) -> np.ndarray:
        return np.setdiff1d(np.arange(self.ndof), self.fixed_dofs)


def mbb_beam(nelx: int = 60, nely: int = 20) -> Problem:
    """MBB beam, half-symmetry model (Andreassen et al. 2011).

    - Domain nelx x nely.
    - Symmetry plane on the left edge: all left-edge nodes have u_x = 0.
    - Roller at the bottom-right corner: that node has u_y = 0.
    - Point load F_y = -1 at the top-left corner node.
    """
    ndof = 2 * (nelx + 1) * (nely + 1)
    F = np.zeros(ndof, dtype=np.float64)
    # Top-left node has index 0 (column 0, row 0 in column-major node ordering).
    # Its y-DOF is index 1. Apply unit downward (positive y is "down" in our convention).
    F[1] = -1.0

    # Symmetry: x-DOFs of left-column nodes (0..nely).
    left_x_dofs = 2 * np.arange(nely + 1)
    # Roller: y-DOF of bottom-right corner, node index (nelx)*(nely+1) + nely.
    br_node = nelx * (nely + 1) + nely
    br_y_dof = np.array([2 * br_node + 1])
    fixed_dofs = np.unique(np.concatenate([left_x_dofs, br_y_dof]))

    return Problem(name="mbb", nelx=nelx, nely=nely, F=F, fixed_dofs=fixed_dofs)


def cantilever_2d(nelx: int = 60, nely: int = 30) -> Problem:
    """2D cantilever: left edge fully clamped, mid-right tip vertical load.

    Provided here for Phase 2 readiness; not used in the Phase 1 gate.
    """
    ndof = 2 * (nelx + 1) * (nely + 1)
    F = np.zeros(ndof, dtype=np.float64)
    # Mid-right node: column nelx, row nely//2.
    mid_node = nelx * (nely + 1) + nely // 2
    F[2 * mid_node + 1] = -1.0
    # Clamp left edge: both DOFs of left-column nodes.
    left_nodes = np.arange(nely + 1)
    fixed_dofs = np.unique(np.concatenate([2 * left_nodes, 2 * left_nodes + 1]))
    return Problem(name="cantilever2d", nelx=nelx, nely=nely, F=F, fixed_dofs=fixed_dofs)


def cantilever_3d(nelx: int = 60, nely: int = 20, nelz: int = 4) -> Problem:
    """3D cantilever: left face fully clamped, mid-right tip vertical load."""
    ndof = 3 * (nelx + 1) * (nely + 1) * (nelz + 1)
    F = np.zeros(ndof, dtype=np.float64)
    
    def get_node(x, y, z):
        return z * (nelx + 1) * (nely + 1) + x * (nely + 1) + y
        
    # Mid-right tip load (downward in y)
    mid_node = get_node(nelx, nely // 2, nelz // 2)
    F[3 * mid_node + 1] = -1.0
    
    # Clamp left face (x = 0)
    y_idx, z_idx = np.meshgrid(np.arange(nely + 1), np.arange(nelz + 1), indexing="ij")
    left_nodes = get_node(0, y_idx.ravel(), z_idx.ravel())
    fixed_dofs = np.unique(np.concatenate([3 * left_nodes, 3 * left_nodes + 1, 3 * left_nodes + 2]))
    
    return Problem(name="cantilever3d", nelx=nelx, nely=nely, nelz=nelz, F=F, fixed_dofs=fixed_dofs)
