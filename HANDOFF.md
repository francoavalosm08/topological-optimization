# Handoff — Next Session

**Last update:** 2026-05-19 (end of Phase 3 commit `b5abc21`, plus `PLAN.md` and `README.md` housekeeping).
**Repo:** <https://github.com/francoavalosm08/topological-optimization>
**Default branch:** `main`.

If you are a new LLM or a new dev picking this up, read these in order before touching anything:

1. [`README.md`](README.md) — the entry point, repo layout, quickstart.
2. [`PLAN.md`](PLAN.md) — original Phase 1 plan + Current Progress section.
3. [`topopt_build_plan.md`](topopt_build_plan.md) — the staged build plan, source of truth.
4. [`compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md`](compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md) — the math, the references, the open-source-stack inventory, the honest STEP-export caveats.

---

## What's done

- **Phase 0** — directory tree, `requirements.txt`, deps installed.
- **Phase 1** (`cc415c8`) — 2D Q4 SIMP solver, OC update with λ-bisection, Sigmund sensitivity filter, MBB beam validation gate. FD gradient check landed.
- **Phase 2** (`7687d8e`) — `mmapy`-based MMA optimizer alongside OC (`OptParams.method = "oc" | "mma"`); FastAPI server with `POST /run` and WebSocket `/ws` streaming `{iter, compliance, change, density_b64}` per iteration; viewer wired to live updates.
- **Phase 3** (`b5abc21`) — H8 3D solver (`core/fea.py:element_stiffness_3d`, `build_edof_3d`), 3D cantilever problem, marching-cubes + Taubin smoothing → STL/GLB export in `core/postprocess.py`, Three.js viewer with `GLTFLoader` + `OrbitControls` and an iso-threshold slider.

## What's next — Phase 4: geometry import

**Phase 4 gate (from `topopt_build_plan.md`):** *"Import a real bracket STL, define BCs in the viewer, run, get a sensible optimized topology that keeps passive regions solid."*

### Files to create

```text
geometry/__init__.py
geometry/voxelize.py     — STL via trimesh.voxelized; STEP via pythonocc-core → mesh → voxelize. Output: occupancy grid bounding the part.
geometry/primitives.py   — programmatic box/cylinder + boolean-subtracted holes for quick design domains.
```

### Files to modify

- **`core/problem.py`** — extend `Problem` to carry three voxel masks: `design`, `passive_solid`, `void`. Each iteration of the optimizer loop must:
  - force `x[passive_solid] = 1.0`
  - force `x[void] = Emin`  (or simply `x_min` per the build plan)
  - exclude both from volume accounting (target is `volfrac * design.sum()`, and the OC bisection should only redistribute over `design` voxels).
  - support marking fixed DOFs and load DOFs by selecting node regions (helper functions on `Problem` like `fix_nodes_in_box(...)`, `apply_load_at_nodes(...)`).
- **`core/optimizer.py:oc_update` (and `mma_update`)** — accept a `design_mask` so the bisection target divides by `design_mask.sum()`, not `x.size`; only update `x` where `design_mask` is true.
- **`server/app.py`** — add `POST /upload_stl` (multipart) that voxelizes the STL and returns the resulting occupancy grid + a GLB preview; `RunRequest` grows fields for `design_mask`, `passive_solid`, `void`, `fixed_dofs`, `load_dofs` (or — easier — accept higher-level region descriptions and resolve to DOFs server-side).
- **`web/index.html`** + new `web/controls.js` — upload control that POSTs the STL, then GLB preview before optimizing; click-to-tag or region-box UI to mark passive regions, supports, and load points directly on the model.

### Dependencies to add

Uncomment / add in `requirements.txt`:

- `trimesh>=4.0` (already listed)
- `pygmsh` and `gmsh` (already commented in `requirements.txt`)
- `pythonocc-core` is **conda-only**; the build plan explicitly says to use it for STEP if needed. For Phase 4 it's fine to support **STL only** and defer STEP — flag STEP as a Phase 4.5 stretch goal.

### Validation gate

1. Pick a real-world bracket STL (a simple L-bracket or motor mount works).
2. Upload via the viewer, click-tag a couple of passive-solid bolt-boss regions and a fixed-support region, set a load point.
3. Run with `volfrac=0.4`, `penal=3`, `rmin=2`.
4. Confirm visually: optimizer keeps the passive regions solid, removes material from the design region, produces a connected load path from loads to supports.
5. Re-run with the same setup but a different `volfrac` (0.3 and 0.5). Topology should change consistently — fewer/more members — with passive regions still solid.

### Known gotchas (Phase 4)

- **STL is a surface, not a solid.** `trimesh.voxelized(pitch)` rasterizes the surface; you need `.fill()` to get a solid occupancy grid. Watertightness check (`trimesh.Trimesh.is_watertight`) before voxelizing — non-watertight inputs make `.fill()` unreliable.
- **Voxel resolution dictates feature fidelity.** Pick `pitch` so the smallest feature you care about is ≥3 voxels wide. Above ~100×100×100 grid (10⁶ elements), `scipy.sparse.linalg.spsolve` runs out of memory — install `pypardiso` and switch the solver (compass notes: 5–10× speedup typical).
- **Density-flat ordering must stay column-major** — when the voxelizer produces a `(nx, ny, nz)` boolean array, flatten as `.ravel(order='F')` (or whatever matches `build_edof_3d`'s element ordering) before handing it to the optimizer. Mismatched flattening will look like a working optimizer that produces garbage topology.
- **Volume fraction with passive elements** — `volfrac` is the fraction of the **design region**, not the bounding box. If the user expects "30% of the bracket bounding box" the UI math must match.
- **DOF selection by node region** — be careful with the column-major node ordering convention in `core/fea.py`: `node(elx, ely, elz) = elz * (nelx+1) * (nely+1) + elx * (nely+1) + ely`. Off-by-one mistakes in node selection will look like missing supports = singular K = NaNs.

### Validation hygiene (carries forward from earlier phases)

- Re-run `python -m pytest tests/test_gradient.py tests/test_gradient_3d.py tests/test_mbb.py -v` whenever you touch `core/fea.py` or `core/optimizer.py`. These are the safety net for sensitivity-sign and assembly bugs.
- After Phase 4 lands, add a `tests/test_passive_mask.py`: tiny problem with one passive-solid voxel and one void voxel, run a few iterations, assert those voxels' densities are pinned at 1 and `Emin` respectively.

---

## Things this handoff deliberately does NOT pre-decide

- **Which click-to-tag UI library** (raycasting on a GLB in Three.js is enough — no need for a heavyweight 3D-CAD editor in-browser).
- **STEP import** — defer unless a downstream consumer demands it. The compass markdown is explicit that organic-TO → STEP is unsolved in OSS.
- **mmapy with passive regions** — MMA needs the gradient with respect to design variables only; how passive masking interacts with MMA's history vectors (`xold1`, `xold2`, `low`, `upp`) needs design. Suggest: keep `x` full-length but freeze passive entries' design variables (don't update); or restrict the design vector to design voxels only and reconstruct full `x` for the FE step. The second is cleaner.

## Quick "is the repo healthy?" smoke test

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/ -v          # all gates should pass
python scripts/run_mbb.py           # MBB final compliance prints ~205
python -m uvicorn server.app:app --reload --port 8000
# → http://localhost:8000  shows the viewer; trigger a run and watch live updates
```

If any of those fail, **fix that before starting Phase 4** — same rule as every other phase.
