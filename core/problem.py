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

    @property
    def ndof(self) -> int:
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
