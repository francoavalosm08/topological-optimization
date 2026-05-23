"""Phase 4: passive-solid and void voxels stay pinned during optimization."""
from __future__ import annotations

import numpy as np

from core.optimizer import OptParams, run_topopt
from core.problem import RegionMasks, custom_problem_3d, fix_nodes_in_box, apply_point_load
from geometry.primitives import box_domain, mark_box_mask


def test_passive_and_void_pins():
    nelx, nely, nelz = 6, 4, 2
    grid = box_domain(nelx, nely, nelz)

    design = grid.flatten_solid().copy()
    passive = mark_box_mask(
        np.zeros_like(design), nelx, nely, nelz,
        x0=0, x1=2, y0=0, y1=2, z0=0, z1=1, value=True,
    )
    void = mark_box_mask(
        np.zeros_like(design), nelx, nely, nelz,
        x0=4, x1=6, y0=2, y1=4, z0=0, z1=1, value=True,
    )
    design = design & ~passive & ~void

    masks = RegionMasks.from_flat(design, passive, void)
    prob = custom_problem_3d(nelx, nely, nelz, masks)
    fix_nodes_in_box(prob, x0=0, x1=0, y0=0, y1=nely, z0=0, z1=nelz, fix_x=True, fix_y=True, fix_z=True)
    apply_point_load(prob, col=nelx, row=nely // 2, layer=nelz // 2, fy=-1.0)

    params = OptParams(volfrac=0.4, penal=3.0, rmin=1.2, max_iter=12, tol=1e-3)
    x, _ = run_topopt(prob, params)

    x_void = max(params.Emin, 1e-3)
    assert np.allclose(x[masks.passive_solid], 1.0, atol=1e-6)
    assert np.allclose(x[masks.void], x_void, atol=1e-6)
    assert masks.design.any()
    assert float(x[masks.design].mean()) <= 0.55
