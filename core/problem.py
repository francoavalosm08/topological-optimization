"""Problem definitions: design domain + BCs + loads + region masks."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RegionMasks:
    """Per-element region tags (flat, column-major / C-order with fea indexing)."""

    design: np.ndarray
    passive_solid: np.ndarray
    void: np.ndarray

    def __post_init__(self) -> None:
        n = self.design.size
        for name, arr in (
            ("design", self.design),
            ("passive_solid", self.passive_solid),
            ("void", self.void),
        ):
            if arr.shape != (n,):
                raise ValueError(f"{name} must be flat length {n}, got {arr.shape}")
        overlap = self.design & self.passive_solid
        overlap |= self.design & self.void
        overlap |= self.passive_solid & self.void
        if np.any(overlap):
            raise ValueError("design, passive_solid, and void must be mutually exclusive")

    @classmethod
    def all_design(cls, n_elements: int) -> RegionMasks:
        return cls(
            design=np.ones(n_elements, dtype=bool),
            passive_solid=np.zeros(n_elements, dtype=bool),
            void=np.zeros(n_elements, dtype=bool),
        )

    @classmethod
    def from_flat(
        cls,
        design: np.ndarray,
        passive_solid: np.ndarray | None = None,
        void: np.ndarray | None = None,
    ) -> RegionMasks:
        n = design.size
        return cls(
            design=design.astype(bool),
            passive_solid=(
                np.zeros(n, dtype=bool)
                if passive_solid is None
                else passive_solid.astype(bool)
            ),
            void=np.zeros(n, dtype=bool) if void is None else void.astype(bool),
        )


@dataclass
class Problem:
    """Design domain + BCs + optional region masks (Phase 4)."""

    name: str
    nelx: int
    nely: int
    F: np.ndarray
    fixed_dofs: np.ndarray
    nelz: int = 0
    region_masks: RegionMasks | None = None

    def __post_init__(self) -> None:
        n = self.nelx * self.nely * max(1, self.nelz)
        if self.region_masks is None:
            self.region_masks = RegionMasks.all_design(n)
        elif self.region_masks.design.size != n:
            raise ValueError(
                f"region_masks length {self.region_masks.design.size} != nelx*nely*nelz={n}"
            )

    @property
    def ndof(self) -> int:
        if self.nelz > 0:
            return 3 * (self.nelx + 1) * (self.nely + 1) * (self.nelz + 1)
        return 2 * (self.nelx + 1) * (self.nely + 1)

    @property
    def free_dofs(self) -> np.ndarray:
        return np.setdiff1d(np.arange(self.ndof), self.fixed_dofs)

    @property
    def n_elements(self) -> int:
        return self.nelx * self.nely * max(1, self.nelz)


def node_index_2d(nely: int, col: int, row: int) -> int:
    return col * (nely + 1) + row


def node_index_3d(nelx: int, nely: int, col: int, row: int, layer: int) -> int:
    return layer * (nelx + 1) * (nely + 1) + col * (nely + 1) + row


def _append_fixed(problem: Problem, dofs: np.ndarray) -> None:
    problem.fixed_dofs = np.unique(np.concatenate([problem.fixed_dofs, dofs.astype(np.int64)]))


def fix_nodes_in_box(
    problem: Problem,
    *,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    z0: int = 0,
    z1: int | None = None,
    fix_x: bool = True,
    fix_y: bool = True,
    fix_z: bool = True,
) -> None:
    """Fix DOFs for all nodes in an axis-aligned box (inclusive node indices)."""
    if z1 is None:
        z1 = problem.nelz if problem.nelz > 0 else 0
    dofs: list[int] = []
    if problem.nelz > 0:
        for col in range(x0, x1 + 1):
            for row in range(y0, y1 + 1):
                for layer in range(z0, z1 + 1):
                    n = node_index_3d(problem.nelx, problem.nely, col, row, layer)
                    if fix_x:
                        dofs.append(3 * n)
                    if fix_y:
                        dofs.append(3 * n + 1)
                    if fix_z:
                        dofs.append(3 * n + 2)
    else:
        for col in range(x0, x1 + 1):
            for row in range(y0, y1 + 1):
                n = node_index_2d(problem.nely, col, row)
                if fix_x:
                    dofs.append(2 * n)
                if fix_y:
                    dofs.append(2 * n + 1)
    _append_fixed(problem, np.array(dofs, dtype=np.int64))


def apply_point_load(
    problem: Problem,
    *,
    col: int,
    row: int,
    layer: int = 0,
    fx: float = 0.0,
    fy: float = 0.0,
    fz: float = 0.0,
) -> None:
    """Add a concentrated nodal load at (col, row, layer)."""
    if problem.nelz > 0:
        n = node_index_3d(problem.nelx, problem.nely, col, row, layer)
        problem.F[3 * n] += fx
        problem.F[3 * n + 1] += fy
        problem.F[3 * n + 2] += fz
    else:
        n = node_index_2d(problem.nely, col, row)
        problem.F[2 * n] += fx
        problem.F[2 * n + 1] += fy


def l_bracket_problem(
    nelx: int = 32,
    nely: int = 24,
    nelz: int = 8,
    *,
    leg_thickness: int = 4,
) -> Problem:
    """Built-in L-bracket with two passive bolt bosses (Phase 4 gate geometry)."""
    from geometry.bracket import bracket_region_masks, build_l_bracket

    grid, spec = build_l_bracket(
        nelx, nely, nelz, leg_thickness=leg_thickness,
    )
    design, passive, void = bracket_region_masks(grid, spec)
    masks = RegionMasks.from_flat(design, passive, void)
    prob = custom_problem_3d(nelx, nely, nelz, masks, name="l_bracket")

    fx = spec.fixed
    fix_nodes_in_box(
        prob,
        x0=fx[0], x1=fx[1], y0=fx[2], y1=fx[3] - 1, z0=fx[4], z1=fx[5] - 1,
        fix_x=True, fix_y=True, fix_z=True,
    )
    col, row, layer = spec.load
    apply_point_load(prob, col=col, row=row, layer=layer, fy=-1.0)
    return prob


def custom_problem_3d(
    nelx: int,
    nely: int,
    nelz: int,
    region_masks: RegionMasks,
    *,
    name: str = "custom3d",
) -> Problem:
    """Empty 3D problem; caller sets BCs via fix_nodes_in_box / apply_point_load."""
    ndof = 3 * (nelx + 1) * (nely + 1) * (nelz + 1)
    return Problem(
        name=name,
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        F=np.zeros(ndof, dtype=np.float64),
        fixed_dofs=np.array([], dtype=np.int64),
        region_masks=region_masks,
    )


def mbb_beam(nelx: int = 60, nely: int = 20) -> Problem:
    """MBB beam, half-symmetry model (Andreassen et al. 2011)."""
    ndof = 2 * (nelx + 1) * (nely + 1)
    F = np.zeros(ndof, dtype=np.float64)
    F[1] = -1.0

    left_x_dofs = 2 * np.arange(nely + 1)
    br_node = nelx * (nely + 1) + nely
    br_y_dof = np.array([2 * br_node + 1])
    fixed_dofs = np.unique(np.concatenate([left_x_dofs, br_y_dof]))

    return Problem(name="mbb", nelx=nelx, nely=nely, F=F, fixed_dofs=fixed_dofs)


def cantilever_2d(nelx: int = 60, nely: int = 30) -> Problem:
    """2D cantilever: left edge fully clamped, mid-right tip vertical load."""
    ndof = 2 * (nelx + 1) * (nely + 1)
    F = np.zeros(ndof, dtype=np.float64)
    mid_node = nelx * (nely + 1) + nely // 2
    F[2 * mid_node + 1] = -1.0
    left_nodes = np.arange(nely + 1)
    fixed_dofs = np.unique(np.concatenate([2 * left_nodes, 2 * left_nodes + 1]))
    return Problem(name="cantilever2d", nelx=nelx, nely=nely, F=F, fixed_dofs=fixed_dofs)


def cantilever_3d(nelx: int = 60, nely: int = 20, nelz: int = 4) -> Problem:
    """3D cantilever: left face fully clamped, mid-right tip vertical load."""
    ndof = 3 * (nelx + 1) * (nely + 1) * (nelz + 1)
    F = np.zeros(ndof, dtype=np.float64)

    def get_node(x: int, y: int, z: int) -> int:
        return z * (nelx + 1) * (nely + 1) + x * (nely + 1) + y

    mid_node = get_node(nelx, nely // 2, nelz // 2)
    F[3 * mid_node + 1] = -1.0

    y_idx, z_idx = np.meshgrid(np.arange(nely + 1), np.arange(nelz + 1), indexing="ij")
    left_nodes = get_node(0, y_idx.ravel(), z_idx.ravel())
    fixed_dofs = np.unique(
        np.concatenate([3 * left_nodes, 3 * left_nodes + 1, 3 * left_nodes + 2])
    )

    return Problem(
        name="cantilever3d",
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        F=F,
        fixed_dofs=fixed_dofs,
    )
