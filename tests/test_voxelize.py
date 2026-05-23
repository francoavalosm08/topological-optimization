"""Phase 4: STL voxelization smoke test."""
from __future__ import annotations

import numpy as np
import trimesh

from geometry.voxelize import voxelize_stl


def test_voxelize_box_stl(tmp_path):
    mesh = trimesh.creation.box(extents=(4.0, 2.0, 1.0))
    stl_path = tmp_path / "box.stl"
    mesh.export(str(stl_path))

    grid = voxelize_stl(stl_path, pitch=1.0)
    assert grid.nelx >= 3
    assert grid.nely >= 1
    assert grid.nelz >= 1
    assert grid.solid.sum() > 0

    design, passive, void = grid.default_masks()
    assert design.sum() + void.sum() == design.size
    assert passive.sum() == 0
    flat = grid.flatten_solid()
    assert flat.shape == (grid.num_elements,)
    assert flat.ravel(order="C").shape == flat.shape
