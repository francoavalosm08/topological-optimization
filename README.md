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
| 4 | Geometry import, built-in L-bracket gate, passive regions, upload API | **bracket gate passing** |
| 5 | Stress constraints (qp-relaxation, p-norm / KS aggregation) | started: stress recovery + aggregates |
| 6 | Production STL export + verification report | started: mesh QA + density-model stress report |

## Read this first (for humans and new LLM sessions)

1. **[`PLAN.md`](PLAN.md)** — the original Phase 1 plan, plus a Current
   Progress section showing what's landed and what's open.
2. **[`HANDOFF.md`](HANDOFF.md)** — concrete next steps to start Phase 4,
   including expected files, validation gate, and known gotchas.
3. **[`topopt_build_plan.md`](topopt_build_plan.md)** — the full staged build
   plan with all six validation gates. Source of truth for what each phase
   must deliver.
4. **[`Z88_INTEGRATION.md`](Z88_INTEGRATION.md)** - installed Z88Arion
   baseline plus the bridge workflow for guided Z88-backed STL optimization.
5. **[`z88_integration_plan.md`](z88_integration_plan.md)** - Z88 integration
   roadmap from local fixture capture to headless execution.
6. **[`compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md`](compass_artifact_wf-b9b66ca3-c38f-4030-a795-a395a0d7fdc3_text_markdown.md)** — the
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
  stress.py         — centroid von Mises recovery, qp relaxation, p-norm/KS aggregates
  verify.py         — mesh-quality checks and production verification reports
geometry/    — (Phase 4) STL/STEP voxelizer, primitives
z88_bridge/  - Z88Arion wrapper contract, installation discovery, handoff adapter
server/      — FastAPI app: POST /run, WebSocket /ws, and local Z88 workflow endpoints
web/         — Three.js viewer plus lightweight Z88 recipe/backend panel
scripts/     — runnable entry points
  run_mbb.py        — Phase 1: writes PNG/iter to runs/, prints final compliance
  run_cantilever.py — Phase 2: OC vs MMA timing comparison
  z88_capability_audit.py - reports the installed Z88Arion/Z88 baseline
  z88_prepare_project.py  - creates a reproducible Z88Arion handoff run folder
  z88_stage_project.py    - stages an existing native Z88Arion project fixture
  z88_summarize_project.py - summarizes native Z88 project text files
  z88_capture_assets.py   - copies bundled Z88 examples into ignored z88_assets/
  z88_audit_fixture.py    - writes JSON/Markdown audits for native Z88 fixtures
  z88_diff_project.py     - compares pre/post native Z88 project folders
  z88_record_post_run.py  - records a manually completed Z88 project fixture
  z88_headless_probe.py   - captures binary help/cwd execution behavior
  z88_collect_results.py  - collects exported STL and writes mesh/report JSON
  z88_recipe.py           - creates Z88 run configs/folders from explicit-box recipes
  z88_run_backend.py      - runs generated Z88 topology replay or writes guided handoff state
  z88_validate_structural_samples.py - validates generated cantilever/bracket/plate STLs across OC/TOSS/SKO
  z88_packaging_preflight.py - checks local packaging/deployment readiness
tests/       — pytest gates
  test_gradient.py    — finite-difference check on dc/dx (2D)
  test_gradient_3d.py — FD check on dc/dx (3D)
  test_mbb.py         — Phase 1 validation gate: MBB compliance within 1% of 205
  test_stress.py      — Phase 5 stress recovery and aggregate checks
  test_verify.py      — Phase 6 mesh-quality and report checks
scratch/     — development experiments (KE3D derivation, MMA prototype, edof tests)
runs/        — output (gitignored): iteration PNGs, density .npy, exported STL/GLB
z88_assets/  - local Z88 examples/outputs/manifests (gitignored)
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
