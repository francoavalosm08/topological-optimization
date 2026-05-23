"""Programmatic design domains without CAD import."""
from __future__ import annotations

import numpy as np

from .voxelize import VoxelGrid


def box_domain(nelx: int, nely: int, nelz: int) -> VoxelGrid:
    """Fully solid rectangular design domain."""
    solid = np.ones((nelx, nely, nelz), dtype=bool)
    return VoxelGrid(
        nelx=nelx,
        nely=nely,
        nelz=nelz,
        solid=solid,
        pitch=1.0,
        origin=np.zeros(3, dtype=np.float64),
    )


def mark_box_mask(
    mask: np.ndarray,
    nelx: int,
    nely: int,
    nelz: int,
    *,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    z0: int = 0,
    z1: int | None = None,
    value: bool = True,
) -> np.ndarray:
    """Set a sub-box in a flat or 3D mask (element index ranges, inclusive start)."""
    if z1 is None:
        z1 = nelz
    out = mask.reshape(nelx, nely, nelz).copy()
    out[x0:x1, y0:y1, z0:z1] = value
    return out.ravel(order="C")
