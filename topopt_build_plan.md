# Research-Grade Roadmap From Current Prototype

This plan starts from the current implementation in this repository and defines
the path from the working prototype to a research-grade STL-first topology
optimization tool.

The target remains the original product goal: upload real STL files, define
loads/supports/passive regions, run accurate topology optimization, inspect
stress and mesh quality, and export a verified STL.

Build order is strict. Each phase has a validation gate. Do not proceed to the
next phase on a broken baseline.

---

## Current Prototype Snapshot

The current system is a working voxel/SIMP topology optimization prototype.

Implemented:

- 2D Q4 SIMP compliance solver with OC update.
- MBB beam validation gate.
- MMA baseline path through `mmapy`.
- FastAPI server with WebSocket iteration streaming.
- Three.js viewer for density fields and GLB outputs.
- 3D H8 solver and 3D cantilever support.
- Marching-cubes STL/GLB export.
- STL voxelization and procedural geometry primitives.
- Region masks for design, passive-solid, and void elements.
- Built-in L-bracket/bracket-style Phase 4 gate.
- Stress recovery utilities: centroid von Mises, qp relaxation, p-norm, KS.
- Heuristic stress-aware redistribution mode.
- Stress field streaming to the viewer.
- Mesh quality checks and density-model verification report.

Current validation baseline:

```powershell
python -m pytest tests/ -v
```

Known current limitations:

- The current stress-aware method is heuristic. It is not true
  stress-constrained MMA.
- Stress recovery is centroid-based, not Gauss-point based; no SPR
  (superconvergent patch recovery) at boundaries.
- Stress sensitivities for aggregated constraints are not implemented.
- Verification uses the optimization density model, not independent FEA on the
  exported STL.
- STL import works for prototype cases but is not yet robust enough for
  arbitrary user STLs (no formal repair pipeline, no partial-cell voxelization,
  no winding-number inside test).
- The viewer is useful but not yet a full operator workflow.
- Large 3D runs depend mostly on SciPy sparse solves and are not
  production-scale. No AMG preconditioner, no factorization reuse, no GPU
  path.
- No multi-load-case formulation. No filter/projection length-scale control.
  No manufacturing constraints (overhang, symmetry).
- MMA dependency (`mmapy`) inherits Svanberg's non-commercial license — this
  blocks any commercial distribution and must be replaced before then.

---

## Prior Art And Positioning

This project is not the first STL-first voxel topology optimization tool in
Python. Before writing each module, decide explicitly: **wrap / fork / port /
write from scratch**. Do not silently reinvent.

Reference implementations relevant to this roadmap:

- **PyTopo3D** (Kim, 2025) — Python, SIMP + OC, STL design domain + STL
  obstacle import, STL export, KD-tree sensitivity filter, optional PyPardiso,
  optional CuPy GPU. Closest cousin of the current prototype. No stress
  constraints, no robust filtering, no independent verification.
  https://github.com/jihoonkim888/PyTopo3D
- **TopOpt_in_PETSc_wrapped_in_Python** (Smit et al., 2021) — Python wrapper
  over a PETSc/MPI C++ solver. STL voxelization, design/solid/void/rigid
  regions, three-field Heaviside robust formulation, local-volume constraint,
  multi-load, continuation. Scales to ~hundreds of millions of elements.
  https://github.com/thsmit/TopOpt_in_PETSc_wrapped_in_Python
- **ToPy** (Hunter) — Lightweight Python 2D/3D compliance, mechanism, heat.
  Historical reference. https://github.com/williamhunter/topy
- **DL4TO** (PyTorch-based) — Useful only if a learned surrogate becomes part
  of the roadmap. Not on critical path. https://github.com/dl4to/dl4to
- **BESO (tomshannon1)** — Reference for evolutionary methods if BESO is ever
  considered as an alternative to SIMP. Not on critical path.
  https://github.com/tomshannon1/BESO
- **Fernandes ABAQUS code** — Reference Python implementations of OC, MMA,
  SLSQP including continuous and discrete stress-constrained variants. Useful
  as a cross-check oracle for `stress_mma`.
  https://github.com/pnfernandes/Python-Code-for-Stress-Constrained-Topology-Optimization-in-ABAQUS

Commercial tools we are *not* competing with on feature parity but should
study for UX:

- **nTopology / nTop** — implicit/B-spline modeling, lattice + TO hybrid.
- **Altair Inspire / OptiStruct** — production TO with manufacturing
  constraints. Gold-standard UX for "import CAD → run TO → export."
- **Ansys Discovery / Mechanical TO** — voxel-based TO inside a sim suite.
- **Autodesk Fusion 360 Generative Design** — cloud-only multi-outcome TO.

Decision defaults applied below:

- **STL import + repair pipeline**: wrap `trimesh` + `pymeshfix`. Do not write
  custom repair.
- **Voxelization**: write our own using `trimesh` ray casts and optional
  winding-number tests, with **partial-cell density** for boundary voxels.
- **Sparse solvers**: SciPy default, **PyPardiso** as optional fast backend,
  **PyAMG** as preconditioner option for CG on large 3D voxel grids,
  **CuPy** as optional GPU backend.
- **MMA**: keep `mmapy` for research/internal use; flag the license risk in
  `LICENSING.md`. Plan a swap to NLopt CCSA or clean-room MMA before any
  commercial use.
- **Verification mesher + solver**: `gmsh` for tetrahedral remesh, `CalculiX`
  for static FEA. Both LGPL/GPL, both Windows-buildable, both scriptable.
- **Robust filtering**: implement Wang/Sigmund/Lazarov 2011 three-field
  eroded/intermediate/dilated formulation. Reference Trillet et al. 2021 for
  analytical length-scale relations.
- **Overhang constraint**: implement Langelaar 2017 layer-by-layer filter as
  the additive-manufacturing default.

---

## Research-Grade Target

The research-grade version should be an engineering-grade STL optimization
tool, not a paper-only solver and not just a UI wrapper.

It should:

- Accept real STL parts reliably (watertight, near-watertight, or fail clearly).
- Preserve supports, load regions, bolt bosses, motor mounts, and other
  passive geometry through optimization, filtering, smoothing, and export.
- Run compliance and stress-constrained topology optimization with defensible
  numerics under multiple load cases.
- Produce clean, connected, watertight STL/GLB outputs.
- Verify final exported geometry with an independent CalculiX static FEA loop
  on a tetrahedral remesh.
- Provide repeatable run configs and reports.
- Expose enough diagnostics that solver failures are explainable.

Primary deliverable: verified STL.

Secondary deliverables: GLB preview, density field, convergence history, run
config JSON, mesh QA report, and independent verification report.

### Quantitative Scale Targets

Set on a 32 GB / 16-core workstation with a single NVIDIA GPU optional:

| Resolution     | Elements    | Target wall time (compliance) | Target wall time (stress) |
| -------------- | ----------- | ----------------------------- | ------------------------- |
| 2D coarse      | 10k         | <10 s                         | <30 s                     |
| 2D fine        | 100k        | <60 s                         | <5 min                    |
| 3D bracket low | 200k        | <5 min                        | <20 min                   |
| 3D bracket mid | 1M          | <20 min                       | <90 min                   |
| 3D bracket hi  | 5M          | <90 min                       | overnight acceptable      |

Above 5M elements is out of scope for the workstation tier; defer to the
PETSc-wrapped path described in Phase RG-5.

### Non-Goals (Explicit)

These are deliberately out of scope. Do not let them creep in.

- Clean parametric STEP reconstruction from organic TO output.
- Body-fitted tetrahedral primary optimization (voxel remains primary).
- Buckling, modal, fatigue, transient dynamic, fluid–structure, multiphysics.
- Multi-material topology optimization.
- Lattice infill generation (out of scope until after RG-11).
- Cloud / distributed compute. PETSc/MPI scaling is referenced but not built.
- Mobile UI.
- Real-time interactivity during the solve beyond iteration streaming.
- A learned/neural surrogate for the solver.

STEP export is optional triangle-BRep compatibility only.

---

## Risk Register

Track these continuously. Re-evaluate at each phase gate.

| ID  | Risk                                                                                                       | Mitigation                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| R1  | MMA license blocks any commercial distribution                                                             | Document early in `LICENSING.md`; plan NLopt CCSA or clean-room MMA swap before any release                 |
| R2  | Silent unit errors (mm vs m vs in) produce plausible but wrong stress                                      | Mandate explicit `units` field in `RunConfig`; refuse import without it; cross-check bounding-box magnitude |
| R3  | STL → smoothed STL diverges from optimization density (the "design-as-built mismatch")                     | Independent FEA on the smoothed STL is the only authoritative verification (Phase RG-4 / RG-9)              |
| R4  | Load/support BCs do not map cleanly from voxel space onto a tetrahedral remesh                             | Persist BCs as **named surface patches** in `RunConfig`; remap by nearest-face within tolerance             |
| R5  | Stress aggregation under-estimates true peak; design passes KS but fails independent FEA                   | Always report peak von Mises alongside KS/p-norm; pass/fail uses peak with safety factor                    |
| R6  | Disconnected components in final STL                                                                       | Largest-connected-component filter mandatory; flag if it drops > 5% of design volume                        |
| R7  | Optimizer mutates passive-solid or void due to flattening-order disagreement between modules               | Unit tests pin flattening order across FEA, filter, stress, export; passive-invariance assertion every step |
| R8  | Large run runs out of memory mid-iteration                                                                 | Pre-flight memory estimate; refuse jobs above configured limit; cancel-safe background runs                 |
| R9  | Stress sensitivities wrong → solver descends into NaN                                                      | Finite-difference check every new sensitivity term; gate it in CI                                           |
| R10 | Heuristic stress mode confused with true stress-constrained MMA in code, UI, or reports                    | Method names `oc`, `mma`, `stress_heuristic`, `stress_mma`; UI shows method explicitly in every report      |
| R11 | CalculiX or gmsh produces silent garbage on a malformed STL                                                | Pre-validate input to verification; refuse if not watertight or has > N degenerate faces                    |
| R12 | Min-member-size control kills the load path on small parts                                                 | Robust three-field formulation tied to a physical length, not voxel count; safety check on final volume     |
| R13 | Three.js viewer falls behind the solve and starves the browser                                             | Throttle iteration stream; render-on-idle; keep all compute in Python                                       |

---

## Phase RG-0: Freeze Current Prototype Baseline

Goal: make the current state explicit before deeper solver work.

Implementation work:

- Keep this document as the source of truth for future phases.
- Record the current test baseline command in `README.md`.
- Add `LICENSING.md` capturing the MMA non-commercial restriction (R1).
- Make clear that the current `stress` method is a practical heuristic, not a
  final research-grade stress optimizer. Rename it now in code to
  `stress_heuristic`. Add a clear deprecation notice; keep it callable.
- Make clear that the current verification report checks the density-model
  stress and mesh quality, not independent FEA.
- Ensure generated caches and run artifacts are not treated as source. Add
  `.gitignore` rules for `__pycache__/`, `scratch/`, run output dirs.

Validation gate:

- `python -m pytest tests/ -v` passes.
- The plan and `README.md` clearly distinguish implemented prototype features
  from missing research-grade work.
- `LICENSING.md` exists and is referenced from `README.md`.
- `stress_heuristic` is callable; the old `stress` name still works with a
  deprecation warning so existing scripts do not break mid-roadmap.

Failure criteria:

- Any core solver gate fails.
- The docs imply the current heuristic stress method is true stress-constrained
  optimization.
- MMA license risk is undocumented.

---

## Phase RG-1: Robust STL Import And Run Setup

Goal: make real STL upload reliable and repeatable.

Implementation work:

- Add a formal `RunConfig` JSON model. See Public Interfaces section for the
  full schema; minimum required fields:
  - STL artifact (path or upload id)
  - units (**mandatory**, one of `mm`, `cm`, `m`, `in`; no default)
  - voxel pitch (in declared units)
  - material (Young's modulus, Poisson ratio, density, stress limit)
  - load cases (each with named surface region, force vector, magnitude)
  - support regions (named surface regions)
  - passive-solid regions (named volumes)
  - passive-void regions (named volumes)
  - optimizer settings (method, volume target or fraction, move limit,
    max iters, convergence tolerance, continuation schedule)
  - export settings (iso threshold, smoothing strength, min component volume)
  - safety factor
- Improve STL ingestion using `trimesh` + `pymeshfix`:
  - watertightness check (`trimesh.is_watertight`)
  - degenerate face / duplicate vertex / non-manifold edge counts
  - automatic repair attempt via `pymeshfix.MeshFix.repair()` (which assumes
    a single closed solid — flag if input clearly is not)
  - actionable error for unrecoverable meshes with named diagnostics
  - voxel-count estimate before voxelization (from bounding box / voxel pitch)
  - memory and runtime class estimate before solve (uses Phase RG-5 table)
  - scale/unit warning if declared units produce a bounding box outside
    the range `[1 mm, 10 m]` along any axis
- Implement proper voxelization:
  - default: ray-casting (`trimesh.voxel.creation.voxelize`) with axis-aligned
    rays from cell centers
  - optional: winding-number inside test for thin-wall or near-non-manifold
    inputs (slower, more robust)
  - boundary voxels get **partial fill fractions** in `[0, 1]`, not just
    binary in/out, to reduce staircase artifacts and improve gradients
- Support region definitions in **physical coordinates**, not raw voxel
  indices:
  - axis-aligned boxes, spheres, cylinders in part-frame coordinates
  - named surface patches (a list of triangle indices, persisted as a named
    region on the original STL — see R4)
  - "by-face-normal" selection (e.g. all faces with normal within N° of -Z)
- Save each run setup next to outputs so a run can be reproduced exactly.
  Output directory layout (one per run):
  ```
  runs/<timestamp>_<slug>/
    config.json
    input.stl
    repaired.stl
    density.npy
    history.json
    optimized.stl
    optimized.glb
    verification.json
    log.txt
  ```
- Keep STL as the primary import format. Triangle-soup OBJ is acceptable;
  PLY is acceptable; STEP is **not** an import path in this phase.

Validation gate:

- A watertight STL bracket imports, voxelizes (with partial cells), previews,
  and runs a compliance optimization end-to-end.
- A simple STL with small holes is repaired by `pymeshfix` and runs.
- A broken/non-watertight STL fails with a useful, named error.
- A run with missing `units` is rejected at config-load time, not at solve.
- Saved run config can re-run the same setup deterministically (same hash on
  output density).
- Bounding-box / unit cross-check warns on probable unit mistakes.

Failure criteria:

- Invalid STLs crash the server or produce silent NaN runs.
- A saved setup does not reproduce the same masks and boundary conditions.
- Region selection depends on ambiguous voxel ordering.
- A run config without explicit units is accepted.

---

## Phase RG-2: Solver Core Hardening

Goal: make the solver architecture strong enough for advanced constraints.

Implementation work:

- Separate optimizer design variables from full FE density fields:
  - `x_design ∈ R^{n_design}` is what the optimizer touches
  - `rho_full ∈ R^{n_elem}` is what FEA, filter, stress, and export consume
  - Reconstruction: `rho_full[i] = 1` if passive-solid, `0` if passive-void,
    else interpolated from `x_design`
  - All sensitivities defined w.r.t. `x_design`
- Exclude passive-solid and void elements from the optimizer vector.
  This applies to OC, MMA, and (later) `stress_mma`.
- Standardize and test flattening order across:
  - FEA assembly
  - voxelization output
  - filters (sensitivity, density, Helmholtz/PDE — see RG-6)
  - stress recovery (centroid → Gauss → SPR — see RG-8)
  - viewer payloads
  - STL export
  Pin the order in a single `core/layout.py` module. Every other module
  imports the convention; do not re-derive it.
- Stress recovery upgrade (groundwork for RG-8):
  - keep centroid von Mises as a fast path
  - add **Gauss-point** evaluation (2×2×2 for H8)
  - prepare hook for **superconvergent patch recovery (SPR)** at boundary
    elements where stress matters; full SPR lands in RG-8
- Add material/load units to problem definitions:
  - Young's modulus (Pa)
  - Poisson ratio
  - density (kg/m³) — for future self-weight; unused in static-only
  - force (N, applied to nodes by area-weighting on surface patches)
  - voxel pitch (m, after unit conversion)
  - stress limit (Pa)
- Track run metadata in `history.json`:
  - run id (hash of `config.json`)
  - grid shape, element count, design-variable count
  - solver method
  - material + load cases
  - constraints
  - convergence status (converged / max-iter / diverged / cancelled / error)
  - per-iteration: compliance, design volume, volume-constraint residual,
    stress aggregates (peak von Mises, KS, p-norm), max move, solve status,
    wall-clock
- Acceptance-test invariants (RG-2 closure):
  - **No method may mutate passive-solid or void elements.** Assert at every
    iteration, in tests, and in CI.
  - Two runs with identical `config.json` produce bitwise-identical density
    and report metadata.

Validation gate:

- Existing MBB, gradient, passive-mask, bracket, stress, verify tests pass.
- New tests prove passive-solid and void regions cannot be changed by OC,
  MMA, or stress methods (FD check + per-iteration assertion).
- Same config produces identical final density and report metadata across
  two runs on the same machine.
- Flattening-order test confirms FEA / filter / stress / export agree on
  index conventions.

Failure criteria:

- Any method mutates passive-solid or void regions.
- Any module disagrees on flat density ordering.
- Repeated deterministic runs produce different results without an explicit
  stochastic setting.
- Units are not honored end-to-end (a known-stress unit test fails).

---

## Phase RG-3: Mesh Extraction And Production STL Export

> Note: This phase is **promoted** from RG-6 in the original plan. Reason:
> the entire downstream pipeline (verification, UI, regression) needs a clean
> STL pipeline first. Doing this before stress optimization means you find
> STL-pipeline bugs in compliance-only mode instead of stacking them under
> stress-mode pathologies.

Goal: produce clean STL/GLB artifacts every run.

Implementation work:

- Build on the current marching-cubes export and mesh QA.
- Parameterize:
  - iso threshold (default 0.5, but report robustness across {0.4, 0.5, 0.6})
  - smoothing strength
  - component-volume filter (drop components smaller than X% of largest)
  - hole filling (only after smoothing)
- Smoothing: implement **Taubin λ/μ smoothing** as the default, not plain
  Laplacian (Taubin preserves volume within ~15%; Laplacian shrinks ~28% per
  Yu et al. 2021). Keep Laplacian as a fallback for comparison.
- **Preserve passive-solid and passive-void boundaries through smoothing.**
  Tag vertices that came from a passive boundary; pin them or restrict their
  smoothing to in-surface motion only. Do not let smoothing eat a bolt boss.
- **Connectivity guarantee**: extract largest connected component; if it
  drops more than 5% of design volume, fail the run with a clear error
  (likely a disconnected design — re-run with better filtering / continuation).
- **Named load-patch persistence (R4)**: for each named surface region on
  the input STL, find the nearest patch of triangles on the smoothed output
  STL within a tolerance equal to `2 × voxel_pitch`. Store the mapping in
  `verification.json` so RG-4 / RG-9 can re-apply BCs.
- Always report (in `mesh_qa.json`, also embedded in `verification.json`):
  - watertightness
  - component count, largest component volume fraction
  - degenerate face count
  - face count, vertex count
  - surface area
  - volume
  - bounding box
  - manifold edge count, non-manifold edge count
  - load-patch mapping result (success / partial / failure per patch)
- Export the full artifact set per run (see RG-1 layout).
- Keep STL as the real production output.
- Treat STEP only as optional triangle-BRep compatibility export, behind a
  flag, and never in the validation gate.

Validation gate:

- Exported STL is watertight.
- Exported STL has one connected component above 95% of design volume.
- Exported STL has zero degenerate faces and zero non-manifold edges.
- GLB loads in the viewer.
- Mesh QA report is written for every production run.
- Robustness across iso thresholds {0.4, 0.5, 0.6}: face count varies by
  < 20%, surface area varies by < 10%, no topology change in
  connected-component count.
- Passive boundaries (bolt bosses, support flanges) are visually intact in
  the smoothed STL.
- All named load patches map onto a non-empty triangle set on the output.

Failure criteria:

- Export silently drops the main load path.
- Export contains floating fragments above the configured threshold.
- Exported GLB/STL does not match the density field visually.
- A passive bolt boss is smoothed off.
- A named load patch fails to map and the run does not fail loudly.

---

## Phase RG-4: Independent FEA Verification (Smoke)

> Note: This is the **smoke** version of verification, run on
> compliance-optimized designs only. Full stress-trend comparison lives in
> RG-9, after stress-constrained optimization exists. Doing the smoke version
> now exercises the STL → tet mesh → CalculiX → BC remap pipeline end-to-end
> before harder optimization stacks on top.

Goal: prove the verification pipeline works on a known case.

Implementation work:

- Remesh final STL with `gmsh`:
  - tetrahedral, target element size proportional to voxel pitch
  - quality target: min dihedral angle > 10°, min Jacobian > 0.1
  - retry with mesh-size refinement on failure; fail loudly if still bad
- Use **CalculiX** as the default local static verification backend:
  - shell out to `ccx`, parse `.dat` and `.frd` output
  - linear static elastic only in this phase
- Map supports and loads from `RunConfig` onto the verification mesh using
  the named load-patch mapping built in RG-3.
- Run independent displacement/stress solve.
- Compare optimization-grid stress (peak von Mises, KS, mean) to
  independent mesh stress.
- Extend `VerificationReport` with:
  - independent peak von Mises (overall, and per load case)
  - max nodal displacement
  - safety factor (default 1.5 for quasi-static drone bracket loads;
    configurable up to 2.0)
  - pass/fail = `independent_peak * safety_factor < stress_limit`
  - verification mesh stats (tet count, min-quality)
  - warnings and failure reasons

Validation gate:

- `gmsh` produces a tet mesh for the L-bracket compliance result.
- CalculiX runs without diverging on the tet mesh.
- BC mapping completes for all named load patches; report names any that
  needed fallback or failed.
- Verification report includes independent FEA results.
- A deliberately weakened L-bracket (artificially low Young's modulus or
  shrunken member) fails the safety-factor check, proving the gate is real.

Failure criteria:

- Load/support mapping is ambiguous or silent.
- Verification mesh generation fails silently.
- Density-model verification is mistaken for independent verification in
  any output.
- The verification gate passes everything including known-bad cases.

---

## Phase RG-5: Performance And Scale

Goal: make useful STL resolutions feasible on a local workstation, hitting
the quantitative scale targets above.

Implementation work:

- Add **optional `pypardiso`** sparse solve backend with SciPy fallback.
  Select backend through config; CI tests both for numerical equivalence.
- Add **PyAMG** preconditioner option for **CG** on large 3D voxel grids.
  AMG (algebraic multigrid) is the right preconditioner for voxel-FE
  stiffness matrices; direct factorization stops scaling around a few
  million DOFs on 32 GB.
- Add **optional CuPy** GPU sparse path for stiffness assembly and CG with
  Jacobi/AMG preconditioning. Mirror PyTopo3D's approach. GPU is opt-in;
  CPU remains the default.
- **Reuse symbolic factorization** across iterations where possible
  (PyPardiso supports this). Density changes every iter but sparsity pattern
  does not.
- Cache reusable structures by grid shape:
  - element stiffness `K_e` (constant for uniform voxel grid)
  - element DOF index matrix
  - assembly indices (COO rows/cols)
  - filter matrix (density or Helmholtz — see RG-6)
- Pre-run memory estimate: rough rule for H8 voxel grid is
  `~150 bytes/element` for the stiffness matrix at low fill plus
  `~80 bytes/element` per stored history vector. Estimate before solve;
  refuse jobs above configured limit with a clear error.
- Add job cancellation (cooperative inside the iteration loop) and
  background job status surfaced through the FastAPI server.
- Avoid blocking the viewer during large runs (already partly done).
- Add benchmark script for 3D cantilever and 3D L-bracket at the scale
  table sizes.

Beyond-workstation scaling (decision, not build):

- If a real user case needs > 5M elements, the path is to defer to the
  PETSc-wrapped backend (Smit et al.). Do not try to roll our own MPI
  solver. Document this as the escape hatch.

Validation gate:

- SciPy, PyPardiso, and PyAMG-CG produce equivalent compliance and stress
  within tolerance (`|Δ| / |ref| < 1e-3`).
- Large jobs are refused gracefully when estimated memory exceeds configured
  limits, with the estimate shown to the user.
- Benchmark report records grid size, elements, iterations, solve time per
  iter, peak memory, and backend, for each row of the scale table.
- All scale-table targets are met on the reference workstation, or each
  miss is documented with a reason.

Failure criteria:

- Large runs crash the process instead of failing early.
- Optional `pypardiso` or PyAMG path changes numerical results outside
  tolerance.
- Server cannot cancel or report status for long runs.

---

## Phase RG-6: Robust Filtering, Projection, Length-Scale Control

> Note: This is the **robust three-field formulation** phase. Without it,
> stress-constrained TO (RG-8) will not behave because boundary artifacts
> dominate stress.

Goal: produce optimized shapes that are not numerical artifacts, with a
provable minimum length scale.

Implementation work:

- Add **density filter** (linear hat, configurable radius) as the baseline.
  Keep current sensitivity-filter mode as a legacy comparison option.
- Add **PDE/Helmholtz filter** (Lazarov & Sigmund 2011) as the scalable
  option for large 3D grids — solve `−r² ∇²ρ̃ + ρ̃ = ρ` with mass-lumped FE.
  Linear in DOFs, parallelizable, no neighborhood lookups.
- Add **smoothed Heaviside projection** with continuation:
  - `β` schedule, e.g. `β = 1 → 32` over the run with doubling every
    ~20–40 iters after volume constraint stabilizes
  - threshold parameter `μ` controls dilation/erosion
- Implement the **Wang/Sigmund/Lazarov 2011 three-field robust formulation**:
  - eroded design (`μ = 0.75`)
  - intermediate design (`μ = 0.5`)
  - dilated design (`μ = 0.25`)
  - objective: worst-of-three compliance (or min-max formulation)
  - constraint: volume on the dilated design
- Use **analytical length-scale relations** (Trillet et al. 2021) to set
  filter radius and projection parameters from a physical
  `min_member_size_mm` user input. Do not make the user tune `β`, `μ`, and
  `r` directly.
- Add **minimum cavity size** control symmetrically (also from Trillet 2021).
- Preserve passive-solid and passive-void regions through filtering and
  projection. The filter must not bleed across passive boundaries.
- Add iso-threshold robustness checks at representative thresholds
  `{0.4, 0.5, 0.6}` — these now reuse the eroded/intermediate/dilated
  designs from the robust formulation.

Validation gate:

- No checkerboarding on the 3D cantilever benchmark.
- Passive regions survive filtering, projection, smoothing, and export.
- Final topology remains connected across `{0.4, 0.5, 0.6}` iso-thresholds.
- Thin disconnected fragments are suppressed.
- Two runs with the same `min_member_size_mm` and different voxel pitches
  produce structures with the same physical minimum member size (within
  one voxel).
- Robust three-field run produces a design where intermediate-design
  compliance is within ~10% of the worst-of-three compliance — i.e. the
  design is genuinely robust to uniform manufacturing under/overgrowth.

Failure criteria:

- Filtering erodes support/load/passive regions.
- Exported result depends wildly on a narrow iso-threshold choice.
- Minimum member-size control destroys load paths.
- `min_member_size_mm` is not honored (FD-style check fails).

---

## Phase RG-7: Multi-Load Cases

Goal: real bracket problems have multiple load directions; the optimizer
must respect all of them.

Implementation work:

- Allow `RunConfig.load_cases` to be a list of N cases, each with weight.
- Two aggregation modes, both implemented, both tested:
  1. **Weighted sum compliance**: minimize `Σ w_i * C_i`. Linear in
     sensitivities (no extra adjoint solves beyond one per case). Default.
  2. **Min-max compliance (bound formulation)**: introduce slack `β`,
     minimize `β` subject to `C_i ≤ β` for all `i`. Use MMA. Required for
     designs where worst-case dominates (e.g. one rare but critical load).
- Sensitivity reuse: factorize stiffness once per iteration, solve N
  right-hand sides for the N load cases. With PyPardiso this is essentially
  free per extra RHS.
- For stress (later in RG-8): aggregate stress over both space and load
  cases. Either max over load cases of regional KS, or KS over the union.
- Track per-load-case metrics in `history.json`.

Validation gate:

- 2-load-case cantilever (down + side) under weighted sum produces a
  cross-braced topology, not the single-load triangle.
- Same problem under min-max produces a more conservative topology with
  balanced compliances within ~5%.
- N=6 load cases on the bracket complete in less than 2× the runtime of
  the N=1 case (factorization-reuse check).
- Per-load-case compliance is reported and matches a from-scratch
  single-load-case run on the final design (within FE tolerance).

Failure criteria:

- N-load-case run takes ~N× the single-load time (factorization not reused).
- Min-max design degenerates to single-load design (formulation bug).
- Per-load-case stress aggregates are reported as a single number with no
  per-case breakdown.

---

## Phase RG-8: True Stress-Constrained MMA

Goal: replace heuristic stress handling with real research-grade
stress-constrained topology optimization.

Implementation work:

- Confirm the rename to `stress_heuristic` (done in RG-0). Add the true
  method name `stress_mma`.
- Recover stress at **Gauss points** (2×2×2 for H8), with optional
  **superconvergent patch recovery (SPR)** at boundary elements. Stress
  governs near surfaces, where SPR matters most.
- Implement **qp-relaxed stress constraints** (Le, Norato, Bruns, Ha,
  Tortorelli 2010):
  - configurable `q` (typically 0.5)
  - continuation schedule on `q` and `p` (penalty)
  - density floor `ρ_min ≈ 1e-3` to keep stiffness positive
- **Aggregate stress constraints regionally**:
  - 10 to 50 spatial clusters (k-means on element centroids, restricted to
    the active solid/design domain)
  - **KS** with `ρ_KS = 10 → 50` under continuation, or **p-norm** with
    `p = 6 → 20`
  - Only active solid/design domain regions; do not aggregate over voids
    or passive-solids
- Implement **adjoint sensitivities** for aggregated stress constraints.
  Reference: Holmberg, Torstenfelt, Klarbring 2013 for the formulation.
- **Finite-difference check** every stress sensitivity term in CI. A failing
  FD check blocks the merge.
- Extend MMA to solve the actual constrained problem:
  - objective: minimize volume (default), or compliance-volume blend
  - constraints: regional stress ratios `≤ 1`
  - design variables exclude passive-solid and void
  - move limit tightened to `0.05 → 0.1` for stress runs
- Always **start stress-constrained runs from a compliance-optimized
  design**. Cold starts diverge; warm starts converge.
- Always report **both** the aggregate (KS or p-norm) and the true peak
  von Mises (R5). Pass/fail uses peak with safety factor, not the aggregate.

Validation gate:

- Stress aggregate finite-difference tests pass (gradient error
  `< 1e-3` relative).
- 2D L-bracket stress-constrained run relieves the re-entrant corner — the
  classical published behavior.
- 3D L-bracket stress-constrained run lowers KS/peak stress versus the
  compliance baseline by ≥ 30% at equal volume, matching the published
  Holmberg-class result within ~20%.
- `stress_mma` converges without NaNs on the accepted benchmark cases
  (2D L-bracket, 3D L-bracket, imported bracket with bolt bosses).
- Per-cluster stress trace shows the active set shifting between clusters
  as the design changes — proof the aggregation is doing useful work.

Failure criteria:

- Stress constraints lower volume but do not reduce peak stress.
- Corner relief only occurs through heuristic patching.
- MMA history vectors break with passive/void masks.
- Finite-difference checks do not match analytic sensitivities.
- The aggregate passes but the independent FEA peak fails — and the
  pass/fail logic does not catch it.

---

## Phase RG-9: Manufacturing Constraints

Goal: produce printable designs without manual rework.

Implementation work:

- **Overhang / self-supporting constraint** (Langelaar 2017): layer-by-layer
  density filter that requires each element to be supported from below
  within a configurable build angle (default 45°). Implemented as a
  density-projection step inside the filter chain.
  - configurable build direction (default `+Z`)
  - optional Gaynor/Guest wedge filter as alternative
- **Symmetry constraints**: enforce reflective symmetry across user-named
  planes by averaging design variables across the symmetric pair before
  the FE step. Simple to implement, common ask on brackets.
- **Maximum member size** constraint (Trillet 2021 dual to min member size)
  for thermal/lattice-style designs. Optional.
- All manufacturing constraints must preserve passive-solid and
  passive-void regions unchanged.

Validation gate:

- 3D cantilever with `build_dir = +Z` and `angle = 45°` produces a
  self-supporting design (max overhang angle in final STL < 45° + 5°
  tolerance, checked geometrically).
- Symmetric L-bracket with a YZ symmetry plane produces a design symmetric
  to within voxel resolution.
- Stress-constrained run with overhang constraint converges (combined-
  constraint convergence is the hard case).
- Overhang constraint on a bracket with passive bolt bosses does not
  modify or relocate the bosses.

Failure criteria:

- Overhang-constrained design still has overhangs > 50°.
- Symmetry constraint breaks gradient flow (FD check fails).
- Manufacturing constraint conflicts with stress constraint and the solver
  silently violates one of them.

---

## Phase RG-10: Full STL Workflow UI

Goal: make the app usable without editing Python.

> Note: The original plan deferred this entirely to the end. Move
> **basic browser load/support painting** earlier — alongside RG-1 — because
> typed-in voxel ranges are where users fail. Full polish stays at this phase.

Implementation work:

- Replace the prototype control surface with a workflow:
  - import STL
  - pick units (mandatory selector, no default)
  - pick voxel pitch (with live element-count and memory estimate)
  - preview voxelization (transparent overlay on input STL)
  - **paint supports** on the input STL by clicking faces (named patch)
  - **paint loads** on the input STL by clicking faces; set force vector
    and magnitude per patch
  - **paint passive-solid / passive-void regions** with box/sphere widgets
    or by selecting closed sub-meshes
  - choose material from a small built-in library + custom
  - choose stress limit and safety factor
  - choose optimizer (`oc`, `mma`, `stress_mma`, `stress_heuristic`)
  - choose `min_member_size_mm` (one slider, drives RG-6 internals)
  - choose manufacturing constraints (overhang on/off + build direction;
    symmetry planes)
  - run optimization
  - inspect density, stress, convergence, and final mesh
  - download STL/GLB/report
- Add stress colormap legend.
- Add convergence plots (compliance, volume, KS, peak von Mises, move).
- Add mesh QA panel.
- Add final pass/fail state with reason ("independent peak von Mises
  exceeds limit × safety factor", etc.).
- Add server-side project save/load using JSON (`RunConfig`).
- Keep all heavy computation in Python.
- Keep the browser as viewer/controller only.

Validation gate:

- A user with no Python knowledge can run an imported STL bracket from
  browser upload to exported STL/report.
- Failed imports, failed solves, and failed verification show useful,
  named messages — not stack traces.
- Stress and verification outputs are visible in the UI.
- Painted load patches in the browser produce the same BCs as the same
  patches encoded in JSON `RunConfig` (round-trip test).

Failure criteria:

- User must edit Python to run a normal STL job.
- UI hides failed verification.
- Browser tries to perform optimization work.
- Painted patches cannot be saved or reloaded.

---

## Phase RG-11: Benchmark And Regression Suite

Goal: make the solver defensible and prevent drift.

Implementation work:

- Add benchmark cases with **versioned expected values from literature** or
  prior in-house runs. Each case stores: input, expected metrics, tolerance.
  - MBB compliance, 60×20: published reference compliance within 2%.
  - 2D cantilever OC vs MMA: same final volume, compliance within 2%.
  - 3D cantilever, 60×20×20: reference compliance within 5%.
  - 2D L-bracket compliance vs stress-constrained: peak von Mises drops
    by ≥ 30% under stress constraint, volume within 10%.
  - 3D L-bracket compliance vs stress-constrained: same, with reference
    values cross-checked against Holmberg-class published results.
  - Imported STL bracket with passive bolt bosses: bosses preserved,
    independent FEA pass under nominal load.
  - Multi-load (N=4) bracket: weighted sum vs min-max produce different
    topologies; both pass independent FEA.
  - Overhang-constrained 3D cantilever: max overhang in final STL < 50°.
- Store expected metrics with tolerances:
  - compliance, volume, peak von Mises, stress aggregate (KS), iterations,
    pass/fail status, runtime envelope
- Add benchmark runner (`scripts/run_benchmarks.py`) that writes a
  reproducibility report (`benchmarks/<date>_report.json`) and a markdown
  summary.
- Keep finite-difference sensitivity checks in the default safety suite.
- CI run: subset of fast benchmarks on every PR; full suite nightly.
- Make benchmark configs versioned alongside solver code; any change that
  shifts a benchmark requires updating the expected value with a justification
  comment.

Validation gate:

- Benchmarks pass on a clean install (verified by `git clean -fdx` + fresh
  venv).
- Any change that breaks compliance, gradients, passive masks, stress
  aggregates, export QA, or verification fails tests.
- Benchmark report is reproducible run-to-run on the same machine.

Failure criteria:

- Benchmarks rely only on visual inspection.
- Stress or export regressions are not caught automatically.
- Expected values are not versioned with solver changes.

---

## Public Interfaces To Add

### `RunConfig`

Serialized JSON for reproducible STL runs. Lock the schema early; bump a
version field on breaking changes.

```jsonc
{
  "version": 1,
  "run_id": null,                    // auto-filled = sha256(config)
  "input": {
    "stl_path": "input.stl",         // or "upload_id"
    "units": "mm",                   // mandatory: mm|cm|m|in
    "repair": { "enabled": true, "max_hole_diameter_mm": 5.0 }
  },
  "domain": {
    "voxel_pitch_mm": 1.0,
    "use_partial_cells": true
  },
  "material": {
    "name": "Al-6061-T6",
    "young_modulus_Pa": 6.89e10,
    "poisson_ratio": 0.33,
    "density_kg_m3": 2700,
    "stress_limit_Pa": 2.76e8
  },
  "load_cases": [
    {
      "name": "vertical_lift",
      "weight": 1.0,
      "patches": [ { "name": "motor_mount_top", "selector": {...} } ],
      "force_N": [0, 0, -100],
      "distribution": "area_weighted"
    }
  ],
  "supports": [
    { "name": "bolt_holes", "patches": [{ "selector": {...} }],
      "constrained_dofs": ["x","y","z"] }
  ],
  "passive_solid": [ { "name": "bolt_boss_1", "selector": {...} } ],
  "passive_void": [ { "name": "tool_clearance", "selector": {...} } ],
  "optimizer": {
    "method": "stress_mma",          // oc|mma|stress_heuristic|stress_mma
    "objective": "min_volume",       // min_compliance|min_volume|blend
    "volume_fraction_target": 0.30,
    "move_limit": 0.1,
    "max_iters": 200,
    "convergence_tol": 1e-3,
    "continuation": {
      "penalty_schedule": [1, 2, 3],
      "beta_schedule": [1, 2, 4, 8, 16, 32],
      "qp_schedule": [0.5]
    }
  },
  "filter": {
    "type": "helmholtz",             // density|sensitivity|helmholtz
    "min_member_size_mm": 2.0,
    "min_cavity_size_mm": 2.0,
    "robust_three_field": true
  },
  "manufacturing": {
    "overhang": { "enabled": true, "build_direction": [0,0,1], "angle_deg": 45 },
    "symmetry_planes": []
  },
  "multi_load_aggregation": "weighted_sum", // weighted_sum|min_max
  "safety_factor": 1.5,
  "export": {
    "iso_threshold": 0.5,
    "smoothing": { "method": "taubin", "iterations": 30, "lambda": 0.5, "mu": -0.53 },
    "min_component_volume_fraction": 0.05,
    "fill_holes": true
  },
  "verification": {
    "enabled": true,
    "remesher": "gmsh",
    "solver": "calculix",
    "target_element_size_mm": 1.0
  },
  "solver_backend": {
    "linear_solver": "pypardiso",    // scipy|pypardiso|amg_cg|cupy_cg
    "use_gpu": false
  },
  "limits": {
    "max_memory_gb": 24,
    "max_runtime_min": 120
  }
}
```

### `OptimizationResult`

Serialized JSON for completed runs.

Required fields:

- final density artifact path
- history path
- STL path, GLB path
- run config path
- verification report path
- final compliance (per load case + aggregate)
- final volume
- final stress metrics (peak von Mises, KS, p-norm, per cluster)
- convergence status
- wall time, peak memory

### `VerificationReport`

Extend the current density-model report.

Required final fields:

- mesh quality (verification tet mesh stats)
- density-model stress metrics
- independent FEA stress metrics (per load case + worst)
- independent max nodal displacement
- safety factor used
- pass/fail state with explicit reason string
- warnings
- artifact paths
- load-patch mapping result (per named patch)

### Optimizer Methods

- `oc` — compliance baseline.
- `mma` — compliance baseline via MMA.
- `stress_heuristic` — current heuristic (renamed in RG-0). Kept callable
  for legacy scripts; not on the recommended path.
- `stress_mma` — true research-grade stress method, lands in RG-8.

---

## Numerical Method Choices (Reference)

A one-stop summary of the canonical method picks behind the phase work
above. When something seems ambiguous in a phase, this section is the
arbiter.

- **Penalization**: SIMP with continuation `p = 1 → 3`. `Emin ≈ E/1e6`,
  never zero.
- **Filter**: Helmholtz/PDE filter (Lazarov & Sigmund 2011) as default for
  3D scale; linear density filter as 2D default; sensitivity filter as
  legacy comparison only.
- **Projection**: smoothed Heaviside (`tanh`-based) with `β = 1 → 32`
  continuation.
- **Robustness**: three-field eroded/intermediate/dilated (Wang, Lazarov,
  Sigmund 2011); length-scale parameters from Trillet et al. 2021.
- **Stress recovery**: Gauss-point (2×2×2 for H8); SPR at boundary.
- **Stress relaxation**: qp (Bruns/Tortorelli style), `q = 0.5`.
- **Aggregation**: regional KS (10–50 clusters), `ρ_KS = 10 → 50`.
- **Optimizer**: OC for pure compliance; MMA for everything else
  (with the licensing caveat in R1).
- **Linear solver**: PyPardiso (default), AMG-CG for very large,
  CuPy CG (GPU) optional, SciPy `spsolve` fallback.
- **Stress sensitivities**: adjoint method, FD-checked in CI.
- **Multi-load aggregation**: weighted sum default; min-max via bound
  formulation when worst-case matters.
- **Overhang**: Langelaar 2017 layer filter.
- **Mesh extraction**: marching cubes → Taubin smoothing → connectivity
  filter → optional hole fill → passive-boundary preservation.
- **Remesh for verification**: gmsh, tet, size ∝ voxel pitch.
- **Verification solver**: CalculiX (`ccx`), linear static elastic.

---

## Test Plan

Default safety command:

```powershell
python -m pytest tests/ -v
```

Phase-specific tests:

- RG-0: baseline still passes; deprecation warning on legacy `stress` name.
- RG-1: STL import, repair, invalid-input, saved-config repeatability,
  units-required, partial-cell voxelization sanity.
- RG-2: design-vector masking, flattening-order parity across modules,
  passive/void invariance per iteration, determinism.
- RG-3: marching-cubes output is watertight, single-component, connectivity
  filter triggers correctly, Taubin preserves volume within tolerance,
  passive-boundary preservation, load-patch mapping round-trip.
- RG-4: gmsh remesh on L-bracket succeeds, CalculiX runs, weakened bracket
  fails the safety gate.
- RG-5: backend equivalence (SciPy ↔ PyPardiso ↔ AMG-CG), memory-estimate
  refusal, benchmark report generation.
- RG-6: length-scale honored across voxel pitches, robust three-field
  produces robust design, passive preservation through filter.
- RG-7: factorization reuse linear-in-N, min-max ≠ weighted-sum,
  per-case metrics reported.
- RG-8: finite-difference stress sensitivities pass, 2D and 3D L-bracket
  stress gates, no-NaN convergence on benchmark set.
- RG-9: overhang geometric check, symmetry geometric check, combined
  stress+overhang convergence.
- RG-10: API/viewer smoke tests for full STL workflow, painted-patch
  round-trip.
- RG-11: benchmark report generation, regression thresholds, fresh-install
  reproducibility.

---

## Standing Rules

- Do not start the next phase on a broken validation gate.
- Finite-difference-check every new sensitivity.
- Keep passive-solid and void regions immutable across optimization,
  filtering, stress, export, and verification.
- Keep density ordering consistent across all modules (`core/layout.py`
  is the single source of truth).
- Never use zero stiffness for voids; keep `Emin` positive.
- Mandate explicit units in every `RunConfig`. No silent defaults.
- Always report **both** stress aggregate (KS / p-norm) and **true peak
  von Mises**. Pass/fail uses peak.
- Prefer STL as the production output.
- Do not promise clean parametric STEP reconstruction.
- Browser controls and visualizes; Python performs optimization.
- Every production run must write enough artifacts to reproduce it.
- Method names are sacred: `oc`, `mma`, `stress_heuristic`, `stress_mma`.
  Never alias `stress_heuristic` as `stress` in user-facing output.
- License-incompatible code must be flagged in `LICENSING.md`. The MMA
  swap is a planned milestone, not a TODO.

---

## Assumptions

- The primary target is an STL-first engineering tool for real topology
  optimization, especially bracket/motor-mount-style drone parts.
- Computational accuracy and verification matter more than UI polish in the
  research-grade phases (RG-0 through RG-9).
- Voxel/H8 remains the main discretization until the voxel workflow is
  research-grade; body-fitted tet TO is deferred indefinitely.
- CalculiX + gmsh is the default planned independent verification path on
  Windows and Linux workstations.
- `topopt_build_plan.md` is the source of truth for this roadmap.
- The reference workstation is 32 GB RAM, 16 CPU cores, one consumer
  NVIDIA GPU. Scale targets assume this class of machine.
- Loads are quasi-static. No dynamic, modal, buckling, or fatigue.
- Materials are linear elastic and isotropic.

---

## Open Questions / Decisions To Make

These are not yet decided. Track them; close them by the phase listed.

| Q   | Question                                                                                            | Decide by phase | Default if undecided                                |
| --- | --------------------------------------------------------------------------------------------------- | --------------- | --------------------------------------------------- |
| Q1  | Wrap PETSc backend or stay on PyPardiso/AMG only?                                                   | RG-5            | PyPardiso + AMG, defer PETSc unless a user hits 5M+ |
| Q2  | Replace `mmapy` with NLopt CCSA or clean-room MMA?                                                  | Before any release | Keep `mmapy`, document R1 risk                   |
| Q3  | Default smoothing: Taubin vs HC-Laplacian vs subdivision?                                           | RG-3            | Taubin                                              |
| Q4  | Default filter: linear density vs Helmholtz vs sensitivity?                                         | RG-6            | Helmholtz for 3D, linear density for 2D             |
| Q5  | Default multi-load aggregation: weighted sum vs min-max?                                            | RG-7            | Weighted sum                                        |
| Q6  | Cluster the stress aggregation by k-means on centroid, by spatial blocks, or by user-named regions? | RG-8            | k-means on active solid centroids                   |
| Q7  | GPU path mandatory in v1 or optional?                                                               | RG-5            | Optional                                            |
| Q8  | Distribute as a Python package, a Docker image, or both?                                            | RG-10           | Both (image is for CalculiX/gmsh bundling)          |
| Q9  | Authentication / multi-user in the FastAPI server?                                                  | RG-10           | Single-user local-only; no auth                     |
| Q10 | License of the project itself?                                                                      | Before release  | LGPL-2.1 to align with TopOpt_in_PETSc precedent    |

---

## References

Open-source reference implementations:

- PyTopo3D — https://github.com/jihoonkim888/PyTopo3D
- TopOpt_in_PETSc_wrapped_in_Python — https://github.com/thsmit/TopOpt_in_PETSc_wrapped_in_Python
- ToPy — https://github.com/williamhunter/topy
- DL4TO — https://github.com/dl4to/dl4to
- BESO (tomshannon1) — https://github.com/tomshannon1/BESO
- Fernandes stress-TO ABAQUS scripts — https://github.com/pnfernandes/Python-Code-for-Stress-Constrained-Topology-Optimization-in-ABAQUS
- trimesh — https://trimesh.org
- pymeshfix — https://pymeshfix.pyvista.org
- gmsh — https://gmsh.info
- CalculiX — http://www.calculix.de
- PyAMG — https://pyamg.github.io
- PyPardiso — https://github.com/haasad/PyPardisoProject
- CuPy — https://cupy.dev

Key papers (search by title; not linking out to specific paywalls):

- Wang, Lazarov, Sigmund (2011) — *On projection methods, convergence and
  robust formulations in topology optimization.*
- Lazarov, Sigmund (2011) — *Filters in topology optimization based on
  Helmholtz-type differential equations.*
- Bruns, Tortorelli (2003) and Le, Norato, Bruns, Ha, Tortorelli (2010) —
  qp-relaxed stress-constrained topology optimization.
- Holmberg, Torstenfelt, Klarbring (2013) — *Stress constrained topology
  optimization* (regional aggregation, adjoint sensitivities).
- Trillet, Duysinx, Fernández (2021) — *Analytical relationships for
  imposing minimum length scale in the robust TO formulation.*
- Langelaar (2017) — *An additive manufacturing filter for topology
  optimization of print-ready designs.*
- Gaynor, Guest (2016) — *Topology optimization considering overhang
  constraints.*
- Yu, Zhang et al. (2021) — *Surface smoothing for topological optimized
  3D models* (Taubin vs Laplacian volume preservation).
- Kim (2025) — *PyTopo3D.*
- Smit et al. (2021) — *Topology optimization using PETSc: a Python wrapper
  and extended functionality.*
