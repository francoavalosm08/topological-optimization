"""Procedural L-bracket for Phase 4 validation (no user STL required)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .primitives import mark_box_mask
from .voxelize import VoxelGrid


@dataclass(frozen=True)
class BracketSpec:
    """Canonical regions for the built-in L-bracket (element indices)."""

    nelx: int
    nely: int
    nelz: int
    leg_thickness: int
    vertical_height: int
    horizontal_length: int
    # Passive bolt bosses on the mount face (vertical leg, y ≈ 0).
    boss1: tuple[int, int, int, int, int, int]  # x0,x1,y0,y1,z0,z1
    boss2: tuple[int, int, int, int, int, int]
    # Fixed support: entire face x = 0 over the vertical leg.
    fixed: tuple[int, int, int, int, int, int]
    # Tip load on horizontal flange (col, row, layer).
    load: tuple[int, int, int]


def build_l_bracket(
    nelx: int = 32,
    nely: int = 24,
    nelz: int = 8,
    *,
    leg_thickness: int = 4,
    vertical_height: int | None = None,
    horizontal_length: int | None = None,
) -> tuple[VoxelGrid, BracketSpec]:
    """Voxel L-bracket: vertical web + horizontal flange, re-entrant inner corner.

    Coordinate convention matches ``core/fea`` (x right, y down, z out-of-plane).
    """
    t = leg_thickness
    H = vertical_height if vertical_height is not None else max(t + 2, nely - 4)
    L = horizontal_length if horizontal_length is not None else max(t + 2, nelx - 4)
    if H > nely or L > nelx:
        raise ValueError(f"Bracket {L}x{H} does not fit grid {nelx}x{nely}")

    solid = np.zeros((nelx, nely, nelz), dtype=bool)
    # Vertical web (mount leg).
    solid[0:t, 0:H, :] = True
    # Horizontal flange (load leg).
    solid[0:L, H - t : H, :] = True

    # Two bolt bosses on the mount face (low y, inside the web).
    bz1, bz2 = nelz // 4, 3 * nelz // 4
    boss_h = max(2, nelz // 4)
    boss1 = (1, min(t + 2, nelx), 0, min(4, H), bz1, min(bz1 + boss_h, nelz))
    boss2 = (1, min(t + 2, nelx), 0, min(4, H), bz2, min(bz2 + boss_h, nelz))

    spec = BracketSpec(
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        leg_thickness=t,
        vertical_height=H,
        horizontal_length=L,
        boss1=boss1,
        boss2=boss2,
        fixed=(0, 0, 0, H, 0, nelz),
        load=(L - 1, H - 2, nelz // 2),
    )

    grid = VoxelGrid(
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        solid=solid,
        pitch=1.0,
        origin=np.zeros(3, dtype=np.float64),
    )
    return grid, spec


def bracket_region_masks(grid: VoxelGrid, spec: BracketSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(design, passive_solid, void) flat masks for ``RegionMasks``."""
    solid = grid.flatten_solid()
    passive = np.zeros(solid.size, dtype=bool)
    for box in (spec.boss1, spec.boss2):
        passive = mark_box_mask(
            passive, spec.nelx, spec.nely, spec.nelz,
            x0=box[0], x1=box[1], y0=box[2], y1=box[3], z0=box[4], z1=box[5],
            value=True,
        )
    passive &= solid
    void = ~solid
    design = solid & ~passive
    return design, passive, void


def export_bracket_stl(grid: VoxelGrid, path: str) -> None:
    """Write a voxel preview mesh (``.stl`` or ``.glb``)."""
    from pathlib import Path

    import trimesh

    boxes = []
    for elx in range(grid.nelx):
        for ely in range(grid.nely):
            for elz in range(grid.nelz):
                if not grid.solid[elx, ely, elz]:
                    continue
                c = grid.origin + np.array([
                    (elx + 0.5) * grid.pitch,
                    (ely + 0.5) * grid.pitch,
                    (elz + 0.5) * grid.pitch,
                ])
                boxes.append(
                    trimesh.creation.box(
                        extents=(grid.pitch,) * 3,
                        transform=trimesh.transformations.translation_matrix(c),
                    )
                )
    mesh = trimesh.util.concatenate(boxes) if boxes else trimesh.creation.box()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)
