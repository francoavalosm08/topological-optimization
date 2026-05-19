# Topology Optimization Pipeline — Build Plan

A staged implementation plan for a coding agent (Claude Code / IDE) to execute. Build order is strict: **each phase has a validation gate that must pass before the next phase starts.** Do not proceed on a broken baseline.

---

## 0. Project setup

```
topopt/
├── core/                  # the solver — pure Python, no web deps
│   ├── fea.py             # element stiffness, assembly, KU=F solve
│   ├── filters.py         # sensitivity / density / PDE filter
│   ├── optimizer.py       # OC and MMA update loop
│   ├── stress.py          # von Mises, aggregation (added Phase 5)
│   ├── problem.py         # design domain, BCs, loads container
│   └── postprocess.py     # marching cubes, smoothing, STL export
├── geometry/
│   ├── voxelize.py        # STL/STEP -> occupancy grid
│   └── primitives.py      # box/cylinder + boolean holes
├── server/
│   ├── app.py             # FastAPI: REST + WebSocket
│   └── jobs.py            # run management, progress streaming
├── web/
│   ├── index.html         # Three.js viewer + control panel
│   ├── viewer.js          # GLB load, density-field render
│   └── controls.js        # param panel, WebSocket client
├── tests/                 # benchmark validation
├── runs/                  # output: density fields, STLs, logs
└── requirements.txt
```

**Dependencies:** `numpy scipy scikit-image trimesh meshio gmsh pygmsh mmapy fastapi uvicorn websockets`. Optional: `pypardiso` (faster solve), `pythonocc-core` (STEP I/O, conda-only). Frontend: Three.js via CDN, no build step.

**Convention rules for the agent:** zero-based indexing throughout; every FEA function gets a finite-difference gradient check in `tests/`; density arrays are always `np.float64` shaped `(nelx, nely, nelz)`; never use browser `localStorage`.

---

## Phase 1 — 2D solver + viewer skeleton (validation gate: MBB beam)

**Solver.** Implement `core/fea.py`, `core/filters.py`, `core/optimizer.py`, `core/problem.py` for 2D Q4 plane-stress, porting the DTU 88-line / 165-line Python code. SIMP interpolation `E = Emin + x^p*(E0-Emin)`, p=3. OC update with bisection on the Lagrange multiplier, move limit 0.2. Sensitivity filter, rmin=1.5. Self-adjoint compliance sensitivity `dc/dxe = -p*xe^(p-1)*ue.T@k0@ue` — **finite-difference check this before anything else.**

**Viewer (start now, keep it dumb).** `web/index.html` + Three.js. Phase 1 it only needs to: render a 2D density field as a heatmap on a canvas/plane, and show a parameter panel (volfrac, penal, rmin, max_iter). No server yet — solver writes a PNG per iteration to `runs/`, viewer has a "load latest" button. This proves the render path works.

**Validation gate:** MBB beam, nelx=60 nely=20 volfrac=0.5 penal=3 rmin=1.5. Final compliance must be **≈205, within 1%** of Andreassen et al. (2011). Topology must visually match their Figure 4. **If it doesn't, stop and debug — do not start Phase 2.**

---

## Phase 2 — MMA + live server (validation gate: cantilever, live streaming)

**Solver.** Add `mmapy`-based MMA path in `core/optimizer.py` alongside OC (keep both; OC stays the default for single-constraint compliance). Add the 2D cantilever as a second problem definition.

**Server.** Build `server/app.py`: FastAPI with one REST endpoint `POST /run` (takes params, starts a job) and one **WebSocket** `/ws` that streams `{iteration, compliance, change, density_field}` every iteration. `server/jobs.py` runs the solver in a background thread/process and pushes updates to the socket.

**Viewer.** `controls.js` connects to the WebSocket; the param panel's "Run" button hits `/run`; the density heatmap now updates **live every iteration** with a compliance/change plot ticking alongside. This is the core feedback loop you wanted.

**Validation gate:** cantilever converges; MMA result matches or slightly beats OC compliance; live view updates smoothly without falling behind the solver.

---

## Phase 3 — 3D solver + GLB viewer (validation gate: 3D cantilever)

**Solver.** Extend to 3D H8 hex elements (port `top3d` / pull PyTopo3D as reference). Switch the linear solve to PyPardiso if `spsolve` runs >30 min. Density field is now a 3D array.

**Post-processing.** Implement `core/postprocess.py`: `skimage.measure.marching_cubes` on the density field at level 0.5 → vertices/faces → Taubin smoothing via `trimesh.smoothing.filter_taubin` → export `.stl`. Also export the iso-surface as **`.glb`** (`trimesh` exports GLB directly).

**Viewer — the real one.** `viewer.js` now loads GLB with Three.js `GLTFLoader`, OrbitControls for rotate/zoom/pan. Two render modes: (a) **voxel density mode** — instanced cubes colored/opacity-mapped by density, updated live during the run; (b) **surface mode** — the smoothed GLB iso-surface, shown on convergence. A slider sweeps the iso-threshold (0.3–0.7) and re-extracts the surface so you can see how robust the topology is.

**Validation gate:** 3D cantilever (60×20×4, volfrac 0.3) matches Liu & Tovar Fig. 4. GLB loads and orbits in-browser. Iso-threshold slider works.

---

## Phase 4 — Geometry in (validation gate: imported bracket)

**Geometry.** `geometry/voxelize.py`: load STL via `trimesh` (or STEP via `pythonocc-core` → mesh → voxelize), produce an occupancy grid bounding the part. `geometry/primitives.py`: programmatic box/cylinder with boolean-subtracted holes for quick design domains.

**Problem definition.** Extend `core/problem.py` to mark each voxel **design / passive-solid / void**. Passive-solid (motor mounts, bolt bosses) forced to x=1 each iteration; void forced to x_min; both excluded from volume accounting. Loads and fixed DOFs assigned by selecting node regions.

**Viewer.** Upload control for STL → previews as GLB before optimizing. Click-to-tag or region-box UI to mark passive regions, supports, and load points directly on the 3D model — these write into the problem definition sent to `/run`.

**Validation gate:** import a real bracket STL, define BCs in the viewer, run, get a sensible optimized topology that keeps passive regions solid.

---

## Phase 5 — Stress constraints (validation gate: L-bracket corner rounds)

**Solver.** `core/stress.py`: element von Mises from FE displacements. qp-relaxation (`p−q ≈ 0.3`) for the singularity problem. KS or p-norm aggregation (P≈8), clustered into ~10–30 regional aggregates. Use the Holmberg et al. (2013) formulation — **minimize volume s.t. aggregated von Mises ≤ σ_limit**, MMA optimizer, tighter move limits (0.05–0.1). Start stress runs from a compliance-optimized design.

**Viewer.** Add a von Mises stress colormap render mode; hotspots visible live. Show peak stress vs. limit on the convergence plot.

**Validation gate:** L-bracket — compliance-only run keeps the sharp re-entrant corner and concentrates stress there; stress-constrained run **rounds the corner into a smooth arc**. If the corner doesn't round, stress handling is broken.

---

## Phase 6 — Production export + verification loop

**Export.** Finalize STL pipeline (marching cubes → Taubin → watertightness check via `trimesh.is_watertight` → hole-fill). STEP: honest expectations — wrap the smoothed STL into a heavyweight one-face-per-triangle STEP via headless FreeCAD *only if* a downstream tool demands it; the real deliverable is STL.

**Verification loop.** Re-mesh the smoothed STL in gmsh, run an independent static FE check (FEniCSx or CalculiX), confirm peak von Mises stays under limit with the drone's safety factor (1.5–2× on quasi-static thrust). TO optima degrade 5–15% through smoothing — this gate catches it.

**Viewer.** Final dashboard: input part, optimized surface, stress field, convergence history, downloadable STL/GLB — all in one page.

---

## Architecture summary for the agent

```
Browser (web/)                    Python (server/ + core/)
─────────────                     ────────────────────────
Three.js GLB viewer    ──REST──►   FastAPI  ──►  solver job (background)
density/stress render  ◄─WebSocket─  streams {iter, compliance, density}
param + BC panel       ──run──►    core/ optimizer + fea + filters
                       ◄────────   final STL + GLB written to runs/
```

The browser **never runs optimization** — it views and controls. All heavy linear algebra is Python. The WebSocket is what makes iterations visible live.

## Validation gates — do not skip

| Phase | Gate | Pass criterion |
|---|---|---|
| 1 | MBB beam | compliance ≈205, within 1% |
| 2 | Cantilever + live stream | MMA ≥ OC quality, smooth streaming |
| 3 | 3D cantilever | matches Liu & Tovar Fig. 4 |
| 4 | Imported bracket | passive regions stay solid |
| 5 | L-bracket | re-entrant corner rounds |
| 6 | Verification | smoothed STL peak stress < limit × safety factor |

## Standing rules

- Finite-difference-check every sensitivity (agents get the sign wrong ~30% of the time).
- Build viewer and solver in parallel each phase — never let the viewer lag a phase behind.
- Each phase ends with a committed, validated, runnable state.
- `x_min` is 1e-3 to 1e-9, never 0 (singular K otherwise).
- Filter is mandatory from Phase 1 (checkerboarding otherwise).
