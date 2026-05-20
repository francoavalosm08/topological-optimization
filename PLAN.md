# Project Plan & Progress — Topological Optimization

This document mirrors the planning file at `~/.claude/plans/hashed-swinging-walrus.md`
(written when the project started, scoped to Phase 0 + Phase 1) and adds a
**Current Progress** section reflecting how far we have actually advanced.

---

## Current Progress (as of 2026-05-19)

The project has moved past the original plan's Phase 1 scope. Per the staged
build plan in `topopt_build_plan.md`, the following phases have been committed
to `master`:

| Commit | Phase | What landed |
|---|---|---|
| `6682d07` | **Phase 1** | 2D SIMP + Optimality Criteria solver; MBB beam validation gate. |
| `d70c188` | **Phase 2** | MMA optimizer (via `mmapy`) integrated; FastAPI + WebSocket live streaming server; viewer updates every iteration. |
| `5758e15` | **Phase 3** | 3D H8 solver; Three.js viewer with GLB loading, OrbitControls, iso-threshold slider; marching-cubes post-processing for STL/GLB export. |

**Where we are now:** Phase 3 is committed and runnable. The next staged gate is
**Phase 4** (geometry import: STL → voxel occupancy grid, passive/design/void
region tagging, click-to-tag UI in the viewer) — not yet started.

**Known open items / debt carried forward:**
- The Phase 1 FD gradient check (`tests/test_gradient.py`) and the MBB
  validation gate (`tests/test_mbb.py`) exist but have **not been run with
  `pytest` in CI** — they were exercised manually during Phase 1 development.
  Re-run them whenever the FEA core changes.
- `mmapy` on Python 3.13 was a flagged risk in the original plan; Phase 2
  landed successfully, so this risk is now closed.
- The dumb PNG-per-iteration viewer from Phase 1 was superseded by the
  WebSocket viewer in Phase 2; the original `web/index.html` from Phase 1 is
  no longer the live viewer.

---

# Phase 1: 2D SIMP Topology Optimizer — MBB Beam Validation Gate

## Context

The user wants to build a topology optimization pipeline per `topopt_build_plan.md`, ultimately for heavy-lift drone parts. The build plan is **strictly staged**: each phase ends in a numerical validation gate that must pass before the next phase begins. The working directory is empty.

This plan covers **Phase 0 (setup) + Phase 1 (2D solver + dumb viewer)** only — Phase 1's gate is the MBB beam reproducing compliance ≈ 205 (within 1%) of Andreassen et al. (2011). Per the build plan: *"If it doesn't, stop and debug — do not start Phase 2."* So Phase 2+ are out of scope until Phase 1 passes.

Approach is a direct port of the Aage & Johansen 165-line Python code (which itself ports Andreassen 88-line MATLAB), with extra safeguards the build plan mandates: finite-difference gradient check, zero-based indexing throughout, density arrays as `np.float64` of shape `(nelx, nely)` for 2D / `(nelx, nely, nelz)` for 3D, `x_min = 1e-9` (not 0), mandatory filter from day one.

## Scope of this plan

**In scope (Phase 0 + Phase 1):**
- Directory skeleton + `requirements.txt`
- Install Phase 1 deps (`numpy`, `scipy`, `matplotlib`, `pillow`) — Phase 2+ deps deferred
- 2D Q4 plane-stress FEA, SIMP `E = Emin + x^p (E0 - Emin)`, p=3
- Sensitivity filter, rmin=1.5
- Optimality Criteria update with bisection on λ, move limit 0.2
- MBB beam problem (nelx=60, nely=20, volfrac=0.5)
- Finite-difference gradient check
- Dumb viewer: solver writes PNG/iteration to `runs/`, `web/index.html` has a "load latest" button (plain `<img>` + JS, no build tooling)
- Validation: run MBB, confirm compliance within 1% of 205

**Out of scope (deferred to next conversation/phase):**
- MMA, FastAPI server, WebSocket streaming (Phase 2)
- 3D, marching cubes, GLB viewer (Phase 3)
- STL import, passive regions (Phase 4)
- Stress constraints (Phase 5)
- STEP export, verification loop (Phase 6)

## Files to create

```
core/__init__.py
core/fea.py          — Q4 element stiffness k0, edofMat, K assembly, KU=F solve, compliance
core/filters.py      — sensitivity filter (Sigmund 1994/1997), H matrix + Hs normalization
core/problem.py      — MBB beam: domain dims, fixed DOFs (left edge x-sym, bottom-right roller), load (top-left, downward)
core/optimizer.py    — OC update with bisection on λ, main run() loop, convergence on max|x-x_prev|<0.01
tests/test_gradient.py — FD check: perturb one element by 1e-6, recompute c, compare to analytic dc/dx (must agree to ~4 sig figs)
tests/test_mbb.py    — runs Phase 1 gate, asserts compliance within 1% of 205
web/index.html       — <img id="frame">, "Load latest" button reads /runs/iter_latest.png
runs/                — output dir; solver writes iter_NNNN.png each iteration, plus final_density.npy
requirements.txt
README.md (one-paragraph: how to run Phase 1)
```

## Key implementation details (gotchas the build plan calls out)

1. **Sensitivity sign**: `dc/dxe = -p * xe^(p-1) * (E0-Emin) * ue.T @ k0 @ ue`. Negative everywhere. Build plan: *"agents get the sign wrong ~30% of the time"* → FD-check before anything else.
2. **`x_min = 1e-9`** (not 0), else K singular.
3. **Filter from Phase 1**, else checkerboarding. Sensitivity filter: replace `dc[e]` by `sum(H[e,i] * x[i] * dc[i]) / (max(x[e], 1e-3) * sum(H[e,i]))`. H is hat-function on element-center distance, radius rmin.
4. **Zero-based indexing** throughout — easy bug source when porting from MATLAB.
5. **Density array shape `(nelx, nely)`** for 2D (column-major flatten when building edofMat is the usual gotcha — follow Andreassen's vectorized assembly).
6. **OC move limit 0.2, damping η=0.5, bisection range λ ∈ [0, 1e9]**, terminate when `(λhi-λlo)/(λhi+λlo+1e-12) < 1e-3`.
7. **MBB BCs (half-symmetry model)**: left edge nodes have `u_x = 0` (symmetry); bottom-right corner node has `u_y = 0` (roller); point load `F_y = -1` at top-left corner node.

## Verification (Phase 1 gate)

1. `python -m pytest tests/test_gradient.py` → FD-vs-analytic agree to ≥4 sig figs on ≥10 random elements.
2. `python -m pytest tests/test_mbb.py` → MBB run with `nelx=60, nely=20, volfrac=0.5, penal=3, rmin=1.5` converges and final compliance is `205 ± 2.05` (1%).
3. Open `web/index.html` in browser, click "Load latest", confirm the heatmap of the converged density looks like Andreassen et al. (2011) Figure 4 (two-truss MBB topology).
4. Only after all three pass: stage Phase 2 work in a new conversation.

## Risks / unknowns

- **mmapy on Python 3.13**: deferred — Phase 1 uses only OC, so not relevant yet. Flag for Phase 2.
- **Pure-Python OC for 60×20 is fast** (~seconds), so no perf optimization needed in Phase 1.
- **PNG-per-iteration disk write** is fine at 60×20; at 3D scale this becomes a bottleneck — replaced by WebSocket in Phase 2.
