"""STL → voxel occupancy grid for topology optimization."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh


@dataclass
class VoxelGrid:
    """Occupancy grid aligned with core/fea element ordering (column-major flatten)."""

    nelx: int
    nely: int
    nelz: int
    solid: np.ndarray  # bool (nelx, nely, nelz)
    pitch: float
    origin: np.ndarray  # shape (3,) world origin of voxel (0,0,0) corner

    @property
    def num_elements(self) -> int:
        return self.nelx * self.nely * self.nelz

    def flatten_solid(self) -> np.ndarray:
        """Flat bool array in the same order as build_edof_3d / filters."""
        return self.solid.ravel(order="C")

    def default_masks(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(design, passive_solid, void) flat bool masks."""
        flat = self.flatten_solid()
        design = flat.copy()
        passive = np.zeros_like(design)
        void = ~flat
        return design, passive, void


def voxelize_stl(
    path: str | Path,
    pitch: float,
    *,
    max_elements: int = 200_000,
) -> VoxelGrid:
    """Load an STL mesh, voxelize, and return a solid occupancy grid.

    Parameters
    ----------
    path:
        Path to ``.stl`` (or other format ``trimesh`` can load).
    pitch:
        Voxel edge length in the same units as the mesh (e.g. mm).
    max_elements:
        Refuse grids larger than this to avoid OOM in the sparse solve.
    """
    path = Path(path)
    mesh = trimesh.load(path, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)

    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
        if not mesh.is_watertight:
            raise ValueError(
                f"Mesh {path.name} is not watertight; fix the STL before voxelizing."
            )

    vox = mesh.voxelized(pitch)
    vox = vox.fill()
    solid = np.asarray(vox.matrix, dtype=bool)
    if solid.ndim != 3:
        raise ValueError(f"Expected 3D voxel matrix, got shape {solid.shape}")

    nelx, nely, nelz = solid.shape
    if nelx * nely * nelz > max_elements:
        raise ValueError(
            f"Voxel grid {nelx}x{nely}x{nelz} = {nelx*nely*nelz} elements "
            f"exceeds max_elements={max_elements}. Increase pitch."
        )

    origin = np.asarray(vox.transform[:3, 3], dtype=np.float64)
    return VoxelGrid(
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        solid=solid,
        pitch=float(pitch),
        origin=origin,
    )


def occupancy_glb_bytes(grid: VoxelGrid) -> bytes:
    """Export a coarse box preview of the occupancy grid as GLB bytes."""
    boxes = []
    for elx in range(grid.nelx):
        for ely in range(grid.nely):
            for elz in range(grid.nelz):
                if not grid.solid[elx, ely, elz]:
                    continue
                center = grid.origin + np.array([
                    (elx + 0.5) * grid.pitch,
                    (ely + 0.5) * grid.pitch,
                    (elz + 0.5) * grid.pitch,
                ])
                box = trimesh.creation.box(
                    extents=(grid.pitch, grid.pitch, grid.pitch),
                    transform=trimesh.transformations.translation_matrix(center),
                )
                boxes.append(box)
    if not boxes:
        scene = trimesh.creation.box(extents=(grid.pitch,) * 3)
    else:
        scene = trimesh.util.concatenate(boxes)
    return scene.export(file_type="glb")
