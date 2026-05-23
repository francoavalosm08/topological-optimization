"""Phase 4 smoke test: box domain with passive region (no STL required)."""
from __future__ import annotations

from core.optimizer import OptParams, run_topopt
from core.problem import RegionMasks, apply_point_load, custom_problem_3d, fix_nodes_in_box
from geometry.primitives import box_domain, mark_box_mask


def main() -> None:
    nelx, nely, nelz = 24, 16, 8
    grid = box_domain(nelx, nely, nelz)
    design, passive, void = grid.default_masks()
    passive = mark_box_mask(
        passive, nelx, nely, nelz,
        x0=0, x1=3, y0=0, y1=3, z0=0, z1=2, value=True,
    )
    design = design & ~passive
    masks = RegionMasks.from_flat(design, passive, void)

    prob = custom_problem_3d(nelx, nely, nelz, masks)
    fix_nodes_in_box(prob, x0=0, x1=0, y0=0, y1=nely, z0=0, z1=nelz)
    apply_point_load(prob, col=nelx, row=nely // 2, layer=nelz // 2, fy=-1.0)

    params = OptParams(volfrac=0.4, penal=3.0, rmin=2.0, max_iter=60)
    x, hist = run_topopt(prob, params)
    print(f"Final compliance: {hist.compliance[-1]:.4f}")
    print(f"Design vol mean: {x[masks.design].mean():.3f}")
    print(f"Passive pinned at 1: {x[masks.passive_solid].min():.3f}..{x[masks.passive_solid].max():.3f}")


if __name__ == "__main__":
    main()
