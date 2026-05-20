# Topology Optimization Pipeline

Python + Three.js implementation of SIMP-based topology optimization, aimed at
heavy-lift drone parts. Built strictly to the staged plan in
[`topopt_build_plan.md`](topopt_build_plan.md): each phase has a numerical
validation gate that must pass before the next phase starts.

## Status

| Phase | What | State |
| --- | --- | --- |
| 1 | 2D Q4 SIMP + OC solver, MBB beam gate | done (commit `cc415c8`) |
| 2 | MMA optimizer + FastAPI / WebSocket live viewer | done (commit `7687d8e`) |
| 3 | 3D H8 solver + Three.js GLB viewer + marching-cubes STL | done (commit `b5abc21`) |
| 4 | Geometry import (STL/STEP → voxels), passive regions, click-to-tag BCs | **next — not started** |
| 5 | Stress constraints (qp-relaxation, p-norm / KS aggregation) | planned |
| 6 | Production STL export + independent FEA verification loop | planned |

## Read this first (for humans and new LLM sessions)

1. **[`PLAN.md`](PLAN.md)** — the original Phase 1 plan, plus a Current
   Progress section showing what's landed and what's open.
2. **[`HANDOFF.md`](HANDOFF.md)** — concrete next steps to start Phase 4,
   including expected files, validation gate, and known gotchas.
3. **[`topopt_build_plan.md`](topopt_build_plan.md)** — the full staged build
   plan with all six validation gates. Source of truth for what each phase
   must deliver.
4. **[`compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md`](compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md)** — the
   background research markdown: the math, the citations, the open-source stack,
   the realistic expectations (especially around STEP export).

## Repo layout

```text
core/        — solver (FEA, filters, SIMP, OC/MMA optimizer, post-processing)
  fea.py            — 2D Q4 + 3D H8 element stiffness, assembly, KU=F solve, compliance + sensitivity
  filters.py        — Sigmund sensitivity filter (2D and 3D)
  optimizer.py      — OC + MMA main loop, run_topopt() with on_iter callback
  problem.py        — MBB, 2D/3D cantilever problem definitions
  postprocess.py    — marching-cubes iso-surface → smoothing → STL/GLB export
geometry/    — (Phase 4) STL/STEP voxelizer, primitives
server/      — FastAPI app: POST /run, WebSocket /ws streams iterations live
web/         — Three.js viewer (density-field render, GLB iso-surface, iso-threshold slider)
scripts/     — runnable entry points
  run_mbb.py        — Phase 1: writes PNG/iter to runs/, prints final compliance
  run_cantilever.py — Phase 2: OC vs MMA timing comparison
tests/       — pytest gates
  test_gradient.py    — finite-difference check on dc/dx (2D)
  test_gradient_3d.py — FD check on dc/dx (3D)
  test_mbb.py         — Phase 1 validation gate: MBB compliance within 1% of 205
scratch/     — development experiments (KE3D derivation, MMA prototype, edof tests)
runs/        — output (gitignored): iteration PNGs, density .npy, exported STL/GLB
```

## Quickstart

```powershell
# 1. install
python -m pip install -r requirements.txt

# 2. validate Phase 1 (must pass before trusting anything else)
python -m pytest tests/test_gradient.py -v   # FD vs analytic gradient
python -m pytest tests/test_mbb.py -v        # MBB compliance ~= 205

# 3. run the 2D MBB with PNG output (Phase 1 viewer)
python scripts/run_mbb.py
# → writes runs/iter_NNNN.png and runs/iter_latest.png

# 4. compare OC vs MMA on the cantilever (Phase 2)
python scripts/run_cantilever.py

# 5. start the live web server (Phase 2/3 viewer)
python -m uvicorn server.app:app --reload --port 8000
# → open http://localhost:8000  (Three.js viewer with live WebSocket updates)
```

## Conventions (load-bearing — do not break)

- **Zero-based indexing** throughout.
- **Density arrays** `np.float64`, shape `(nelx, nely)` for 2D or
  `(nelx, nely, nelz)` for 3D, flattened in **column-major** order for the
  solver's internal flat vector.
- **`Emin = 1e-9`** in the SIMP interpolation (never 0 — K becomes singular).
- **Filter is mandatory from Phase 1** — without it you get checkerboarding.
- **Sensitivity sign**: `dc/dx_e = -p * x_e^(p-1) * (E0-Emin) * (u_e^T k0 u_e)`
  — negative everywhere. Always FD-check this when touching the FEA core.
- **Each phase ends in a committed, validated, runnable state.** Do not start
  the next phase on a broken gate.
