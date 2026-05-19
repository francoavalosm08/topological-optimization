# Building Your Own Topology Optimization Pipeline in Python for a Heavy-Lift Drone

## TL;DR

- **You can absolutely build a working SIMP-based static-structural topology optimizer in pure Python by starting from Aage & Johansen's 165-line educational port of the Andreassen 88-line code (hosted on the DTU TopOpt site), wrapping a 3D extension based on Liu & Tovar's 169-line `top3d` (the PyTopo3D port on GitHub is essentially this code), and bolting on Arjen Deetman's `GCMMA-MMA-Python` once you outgrow Optimality Criteria — this gets you to a converged drone bracket on a laptop in days, not months.**
- **For the drone use case, run minimum-compliance SIMP with a volume constraint first, then add stress awareness with a p-norm or KS aggregation of element von Mises stresses plus qp-relaxation — full stress-constrained TO is a known hard problem (singular optima, thousands of nonlinear constraints, high mesh sensitivity) and you should expect to iterate on hyperparameters; do not start there.**
- **The pipeline ends realistically in STL, not STEP: marching cubes from scikit-image gives you a clean iso-surface from the converged density field that prints/CNCs immediately, but "clean parametric STEP from organic TO geometry" is an unsolved problem in open-source — FreeCAD's `Part.Shape().makeShapeFromMesh` produces one B-Rep face per triangle and OCCT itself has no mesh-to-BRep primitive.**

---

## Key Findings

1. **The SIMP method is the right starting point.** Density-based topology optimization with the modified power-law interpolation E(x) = E_min + x^p · (E_0 − E_min), penalization p = 3, an Optimality Criteria update, and a sensitivity or density filter is the published baseline (Sigmund 2001, Andreassen et al. 2011, Bendsøe & Sigmund 2003) and has direct, free Python reference implementations.

2. **Optimality Criteria (OC) is fine for a single volume constraint; MMA is required for stress.** The bisection-on-λ OC update is what every educational code uses. As soon as you add stress constraints, multiple load cases, or local volume constraints, switch to Svanberg's Method of Moving Asymptotes — Arjen Deetman's `GCMMA-MMA-Python` is a faithful Python port of Svanberg's MATLAB code, distributed under GPLv3 ("you can redistribute it and/or modify it under the terms of the GNU General Public License … either version 3 of the License, or (at your option) any later version"), and pip-installable as `mmapy`.

3. **Stress-constrained TO is genuinely hard.** Three coupled difficulties: singular optima from the stress discontinuity at zero density (cured by ε- or qp-relaxation), millions of local constraints (cured by p-norm or Kreisselmeier-Steinhauser aggregation), and extreme nonlinearity. Expect to tune more, converge slower, and validate against the L-bracket benchmark which is the canonical stress-concentration test case.

4. **Filtering is non-negotiable.** Without a filter of radius rmin ≥ ~1.5·element-size you will get checkerboarding and mesh-dependent designs. Use sensitivity filtering (Sigmund 1994/1997) for the simplest path, density filtering (Bruns & Tortorelli; Bourdin) for cleaner sensitivities, or the PDE/Helmholtz filter of Lazarov & Sigmund (2011) for unstructured 3D meshes. Add Heaviside projection (Guest et al. 2004) once your topology is stable, to push gray to crisp 0/1.

5. **The right Python stack exists today.** NumPy + SciPy sparse + scikit-image (marching_cubes) + `mmapy` + `pygmsh`/`meshio`/`gmsh` for unstructured meshes + `pythonocc-core` for STEP I/O + optional PyPardiso for the linear solve. For larger problems FEniCSx + dolfin-adjoint give you a PDE-constrained-optimization framework with automatic adjoints.

6. **Export realism.** STL out is trivial and good. STEP out from an organic TO output is, in 2026, not solved by any open-source tool: the only OSS routine that works at all (`Part.Shape().makeShapeFromMesh`) creates one planar B-rep face per triangle, producing a "heavy, unparametric" STEP. The authoritative Open CASCADE forum response says OCCT "does not provide such a functionality" and that automatic reconstruction is "extremely difficult".

7. **An AI coding assistant is best used incrementally.** Have it port `top88.m` first, verify the MBB result, then extend to 3D against `top3d.m`'s benchmark, then add geometry import, then stress. Each stage has a known-good answer to validate against; do not skip validation steps.

---

## Details

### 1. The actual math of topology optimization

#### 1.1 The SIMP material interpolation

In the **Solid Isotropic Material with Penalization** approach (Bendsøe 1989; Rozvany; Mlejnek; rigorously justified in Bendsøe & Sigmund 1999), every finite element e in the design domain carries one design variable x_e ∈ [x_min, 1] interpreted as a relative density. Young's modulus is interpolated as:

> **E(x_e) = E_min + x_e^p · (E_0 − E_min)**

with E_0 the modulus of the solid material, E_min a small positive number (≈1e-9 · E_0) that keeps the stiffness matrix positive definite at void, and **p the penalization power, typically p = 3**. Penalization makes intermediate densities "expensive": at p > 1, the marginal stiffness gained by going from 0.5 to 1.0 is much greater than the marginal volume cost, which drives the optimizer toward 0/1 (black/white) designs and away from physically meaningless gray. Bendsøe and Sigmund showed in 1999 that the power-law is physically admissible when p satisfies bounds depending on Poisson's ratio (p ≥ 3 is the common safe choice for ν ≈ 1/3).

#### 1.2 The compliance problem

The canonical statement is:

> minimize over x: c(x) = U(x)^T K(x) U(x)
> subject to:  K(x) U(x) = F        (FE equilibrium)
>              V(x)/V_0 ≤ f         (volume fraction constraint)
>              x_min ≤ x_e ≤ 1, ∀ e

K is the assembled global stiffness, **K = Σ_e E(x_e) · k_0 / E_0** where k_0 is the element stiffness matrix evaluated at full density (geometry- and Poisson-ratio-dependent only). U is the nodal displacement vector solving KU = F. Compliance c = U^T K U = F^T U is twice the strain energy and inversely measures global stiffness.

#### 1.3 The FE underpinning

The design domain Ω is meshed into N elements (regular Q4 squares in 2D educational codes, H8 hex bricks in `top3d`, tetrahedra for unstructured meshes). For Q4 plane-stress with Poisson ν = 0.3 the element stiffness has the closed form Sigmund prints in the 99-line code. Assembly uses `scipy.sparse.coo_matrix((sK, (iK, jK)))` then `.tocsr()`; the linear solve is `scipy.sparse.linalg.spsolve` for small problems, **PyPardiso** (Intel MKL Pardiso) for anything large — per the haasad/PyPardiso README, "PyPardiso provides the same functionality as SciPy's scipy.sparse.linalg.spsolve for solving the sparse linear system Ax=b. However in many cases it is significantly faster than SciPy's built-in single-threaded SuperLU solver."

#### 1.4 Sensitivity analysis (the adjoint result)

Because compliance is self-adjoint, the sensitivity collapses to a clean closed form. Differentiating c = U^T K U and using K U = F:

> **∂c/∂x_e = − p · x_e^(p−1) · (E_0 − E_min) · u_e^T k_0 u_e**

where u_e is the element's displacement sub-vector. The sensitivity is negative everywhere (more material always reduces compliance) — what the optimizer redistributes is *where* the most compliance is bought per unit volume. Volume sensitivity is trivially **∂V/∂x_e = v_e** (the element volume). Note that for a generic, non-self-adjoint objective (e.g. displacement at a point, stress at a point), you must explicitly solve the adjoint system K^T λ = ∂g/∂U — this is where `dolfin-adjoint` / `pyadjoint` earns its keep by deriving adjoints automatically from the UFL form.

#### 1.5 The Optimality Criteria update

OC is a fixed-point rule from the KKT conditions. With Lagrange multiplier λ on the volume constraint and η = 1/2 a damping coefficient:

> B_e = − (∂c/∂x_e) / (λ · ∂V/∂x_e)
> x_e^new = max(x_min, max(x_e − m, min(1, min(x_e + m, x_e · B_e^η))))

with **move limit m** (typically 0.2). λ is found by an outer bisection: starting from λ ∈ [0, 10^5], evaluate the candidate update, check whether the resulting Σ v_e · x_e exceeds the target volume; if yes, increase λ, else decrease, halving the interval until |λ_hi − λ_lo|/(λ_hi + λ_lo) < 1e-3. This bisection is what the 99-/88-/169-line codes implement.

#### 1.6 The Method of Moving Asymptotes

Svanberg's MMA (1987) builds, at each iteration, a separable convex approximation of the objective and constraints using moving lower/upper asymptotes (L_j, U_j) for each design variable, then solves the resulting strictly convex subproblem to global optimality with a primal-dual interior point method. MMA handles arbitrary inequality constraints (including stress), is the field's workhorse, and is freely available in Python via **Arjen Deetman's `GCMMA-MMA-Python`** (`pip install mmapy`), ported faithfully from Svanberg's reference MATLAB code under GPLv3. The companion repo `arjendeetman/TopOpt-MMA-Python` ships a working example that wires MMA into the DTU 165-line Python topology code. Use OC for single-constraint compliance only; use MMA the moment you add stress, multiple load cases, displacement constraints, or local volume bounds.

#### 1.7 Filtering — and why you must filter

Without regularization, two pathologies appear: **checkerboarding** (alternating 0/1 elements form a high-stiffness numerical artifact stiffer than any real material) and **mesh dependence** (refining the mesh produces a qualitatively different design, with ever-finer features). The cure (Sigmund 1994/1997; Bourdin 2001; Bruns & Tortorelli 2001) is a length-scale filter of radius rmin:

- **Sensitivity filter:** replace ∂c/∂x_e by a weighted average of neighbors' sensitivities (rmin set in mesh units, typically rmin = 1.5–3 × element size). This is the original Sigmund approach and what the 99-line code uses.
- **Density filter:** define a "physical density" x̃_e = Σ H_ei x_i / Σ H_ei with hat-function weights H_ei = max(0, rmin − dist(e,i)) and run the FE analysis on x̃. The 88-line code adds this option.
- **PDE / Helmholtz filter** (Lazarov & Sigmund 2011): the filtered field is the solution of −r²∇²x̃ + x̃ = x with Neumann BCs. Trivially parallelizable, works on unstructured meshes (essential when you import CAD), and is the right choice for FEniCSx pipelines.
- **Heaviside projection** (Guest, Prévost, Belytschko 2004): pass the filtered density through a smoothed step x̄ = 1 − exp(−β x̃) + x̃ exp(−β) and ramp β from 1 to ~64 in a continuation. This crisps the gray boundary into 0/1 and gives interpretable parts. Use it after a stable topology has emerged — projecting too early prevents the topology from finding its right answer.

#### 1.8 Convergence

The standard rule is:

- max(|x^k − x^(k-1)|) < 0.01 (change in any design variable below 1%), **or**
- iteration count reaches a hard cap (200 for 2D, 100–300 for 3D).

For continuation schemes (β ramp, p ramp from 1→3) you restart the convergence counter at each step. The compliance must monotonically decrease until you turn on projection; oscillations indicate that the move limit is too aggressive or the filter is too small.

### 2. Stress-constrained topology optimization

This is what you actually care about for a heavy-lift drone arm or motor mount. Three coupled difficulties (Le et al. 2010; Holmberg, Torstenfelt, Klarbring 2013; Duysinx & Sigmund 1998):

#### 2.1 The singularity problem

At low densities the SIMP-interpolated von Mises stress does *not* go to zero (it goes to a finite "phantom" value because the strain stays bounded), so an empty element can paradoxically violate a stress constraint and block the optimizer from removing it. The fix is **stress relaxation**: define a relaxed stress σ_e^rel = x_e^q · σ_e^vm with **q < p** and typically **p − q ∈ [0.2, 0.5]**. Equivalently, the Cheng-Guo ε-relaxation. As q → 0 in continuation, the stress at void asymptotes to zero and singular sub-spaces become accessible to the optimizer.

#### 2.2 The local-constraint problem

A stress limit applies at every Gauss point — for a 200 × 100 mesh in 2D that is ~80,000 constraints, untenable for MMA. **Aggregate** into one (or a few) global measures:

- **p-norm:** σ_PN = (Σ_e (σ_e^rel/σ_lim)^P)^(1/P), with **P typically 6–12**. As P → ∞ this converges to the max stress; small P underestimates, large P is numerically nasty.
- **Kreisselmeier–Steinhauser:** σ_KS = (1/P) · ln(Σ_e exp(P · σ_e^rel/σ_lim)) — smoother and more stable for large P, but the lower-bound form is preferred to avoid overshoot.

Practical recipe: cluster the domain into ~10–50 regional aggregates rather than one global one (Le et al. 2010; París et al. 2009) — this preserves enough locality to actually push down peak stresses without exploding the constraint count.

#### 2.3 Nonlinearity

Stress is wildly more sensitive to density changes than compliance is, especially near re-entrant corners. Symptoms: oscillating objective, peak stress jumping between two members, convergence stalling. Counter-measures: tighter move limits (0.05–0.1 instead of 0.2), longer continuation on q and on the projection β, and starting from a compliance-optimized design rather than uniform density.

#### 2.4 Compliance-vs-stress: practical choice

For a drone, run the pipeline as: (a) minimum-compliance with a generous volume fraction (say 0.4); (b) evaluate the von Mises field, identify hotspots; (c) re-optimize as minimum-volume subject to KS-aggregated von Mises ≤ σ_lim — this is the formulation Holmberg et al. use and what gives weight-minimal designs with bounded peak stress. Validate every run against the **L-bracket benchmark** (rectangular cantilever with a 90° re-entrant corner under a tip load on the short leg, top fixed) — the canonical result is that pure compliance optimization leaves the sharp corner in place and concentrates stress there, while a stress-constrained run rounds the corner to a smooth arc.

### 3. The open-source Python implementation stack

Concrete inventory, all free, all installable today:

#### 3.1 Educational reference codes (start here)

- **Sigmund (2001), "A 99-line topology optimization code written in Matlab,"** *Struct Multidisc Optim* 21:120–127. Q4 mesh, OC, sensitivity filter, MBB beam. The "Hello World" of TO. Downloadable from topopt.dtu.dk.
- **Andreassen, Clausen, Schevenels, Lazarov, Sigmund (2011), "Efficient topology optimization in MATLAB using 88 lines of code,"** *Struct Multidisc Optim* 43:1–16. Vectorized, adds density filter, ~100× faster than the 99-line version. Variants: top82.m (PDE filter), top110.m (Heaviside).
- **Aage & Johansen, "A 165 LINE TOPOLOGY OPTIMIZATION CODE" (2013),** the official Python port hosted at https://www.topopt.mek.dtu.dk/apps-and-software/topology-optimization-codes-written-in-python. Direct equivalent of top88.m. **This is your starting file.**
- **Liu & Tovar (2014), "An efficient 3D topology optimization code written in Matlab,"** *Struct Multidisc Optim* 50:1175–1196 — the 169-line `top3d.m` with H8 elements. Site: top3dapp.com. The Python equivalent **PyTopo3D** (Kim & Kang, arXiv:2504.05604, 2025; github.com/jihoonkim888/PyTopo3D) ports this and adds GPU + PyPardiso acceleration, and per the paper "incorporates functionalities vital for practical engineering workflows, including the direct import of complex design domains and non-design obstacles via STL files" — directly usable for drone parts.

#### 3.2 Higher-level Python frameworks

- **`topy`** (github.com/williamhunter/topy) — lightweight; compliance, heat conduction, mechanism synthesis; 2D and 3D; problem definition by TPD text file or dict; outputs PNG/VTK. Good for quick experiments, limited extensibility.
- **`topopt`** (github.com/zfergus/topopt) — clean OO Python library: `ComplianceProblem`, `DensityBasedFilter`, `TopOptSolver`, built-in GUI. MMA-based. The README example reproduces the MBB beam in ~15 lines of user code.
- **`TopOpt_in_PETSc_wrapped_in_Python`** (Smit, Ferguson & Helgason, *Struct Multidisc Optim* 64(6):4343–4353, 2021, DOI 10.1007/s00158-021-03018-7) — Python wrapper around the parallel C++ TopOpt-in-PETSc framework of Aage et al. (2015). Scales to multi-million-element 3D problems on a cluster; supports passive domains and local volume constraints. Heavy install (PETSc), but the right answer when you outgrow scipy.
- **DL4TO** (github.com/dl4to/dl4to) — PyTorch-based 3D SIMP with differentiable physics, good for users who want to plug in neural-network surrogates later.

#### 3.3 FEniCS / FEniCSx + dolfin-adjoint

For unstructured meshes and PDE-constrained optimization with automatic adjoints:

- **FEniCSx** (the modern successor to FEniCS / dolfin) gives you a high-level UFL-based FE solver.
- **`pyadjoint` / `dolfin-adjoint`** (dolfin-adjoint.org) automatically derives adjoint equations from your forward solve and provides hooks into **IPOPT** (the well-established interior-point nonlinear solver) via `pyipopt`. The official Poisson-topology and Stokes-topology examples on dolfin-adjoint.org are the canonical reference.
- A direct, modern reimplementation of the Sigmund 99-line code on FEniCSx is at github.com/floating-gates/Sigmund---A-99-Line-Topology-Optimization-Code-Written-in-MATLAB---FEniCSx-rewrite.

#### 3.4 Optimizers

- **`mmapy`** (Arjen Deetman, GPLv3) — `pip install mmapy`. Provides `mmasub`, `gcmmasub`, `subsolv`, `kktcheck`. The companion repo `arjendeetman/TopOpt-MMA-Python` shows how to wire it into the Aage–Johansen Python code.
- **NLopt** — broad gradient-based & gradient-free; good for shape problems where you have few variables.
- **SciPy `minimize`** with method='SLSQP' or 'L-BFGS-B' works for very small TO problems but does not scale.
- **IPOPT** via `cyipopt` — robust for stress-constrained TO (used by the dolfin-adjoint examples).

#### 3.5 Geometry, meshing, I/O

- **`gmsh`** (Python API: `import gmsh`) — primary unstructured mesher. Supports OpenCASCADE geometry, STL import, classify-and-reparametrize for remeshing.
- **`pygmsh`** (Schlömer) — higher-level pythonic wrapper; returns `meshio` Mesh objects.
- **`meshio`** — universal mesh format converter (.msh, .vtk, .vtu, .xdmf, .stl, .obj, ...).
- **`pythonocc-core`** (Paviot, LGPL) — Python bindings for OpenCASCADE; reads STEP/IGES/BREP/STL via `STEPControl_Reader`, exposes the full OCCT API; `conda install -c conda-forge pythonocc-core`. Use `from OCC.Core.STEPControl import STEPControl_Reader; reader.ReadFile('part.step'); reader.TransferRoots(); shape = reader.OneShape()`.
- **`trimesh`** — fast STL/OBJ I/O, watertightness checks, voxelization, hole filling.
- **FreeCAD's Python API** — usable headless (`import FreeCAD`), gives you `Part`, `Mesh`, `MeshPart`, and the most complete OSS STEP I/O.
- **scikit-image `measure.marching_cubes`** — *the* function to extract an iso-surface from a 3D density array. Returns vertices, faces, normals, values — directly writable as STL via `trimesh` or `meshio`.

#### 3.6 Linear solvers

- **`scipy.sparse.linalg.spsolve`** — SuperLU, single-threaded. Fine up to ~10^5 DOF.
- **PyPardiso** (`pip install pypardiso`) — Intel MKL Pardiso, multi-threaded direct solver. Drop-in replacement: `from pypardiso import spsolve`. Linux/Windows; macOS users should use `scikit-umfpack`.
- **CVXOPT's `cholmod`** — sparse Cholesky for SPD systems (which K is). Often the fastest if you can install it.
- **PyAMG** — algebraic multigrid for very large 3D problems where direct solvers blow up RAM.

### 4. The full pipeline — from CAD in to STL out

#### 4.1 Importing CAD

Two practical paths:

- **STEP/IGES → mesh:** use `pythonocc-core` to read the file, then convert the resulting `TopoDS_Shape` to a mesh with OCCT's `BRepMesh_IncrementalMesh` or hand it to gmsh via `gmsh.merge('part.step')` followed by `gmsh.model.mesh.generate(3)` for tetrahedra. The Firedrake project's `OpenCascadeMeshHierarchy` is a good reference implementation.
- **STL → mesh:** load with `trimesh.load('part.stl')` for surface manipulation, or `gmsh.merge('part.stl')` + `classifySurfaces` + `createGeometry` to build a remeshable model. Note: an STL is a surface, not a solid — for FEM you must close it and tetrahedralize the interior.

#### 4.2 Voxel vs unstructured

| | Voxel (structured H8) | Unstructured tetrahedral |
|---|---|---|
| Mesh assembly | `edofMat` is closed-form; vectorizable; ~10× faster | Per-element loop or vectorized via `meshio` |
| Stiffness | One precomputed `k_0` for all elements | Recompute per element (different J) |
| Pre-existing code | top88, top3d, PyTopo3D directly applicable | Custom — FEniCSx is the easiest path |
| CAD boundary fidelity | Stair-stepped; needs fine mesh near features | Body-fitted; better stress accuracy at corners |
| Recommended for | First prototype, regular design domains | Imported drone bracket with complex BCs |

For your first end-to-end pipeline, use a **voxel grid that bounds your CAD** and mark each voxel as design, non-design (passive solid where loads attach and where motor bolts pass through), or void (carved out by the CAD) — this is exactly the obstacle-mask approach in PyTopo3D, which accepts the obstacle geometry as STL. Body-fitted tet meshes are the second step.

#### 4.3 Defining design domain, loads, supports

Programmatically:

```python
# voxel approach
design_mask = np.ones((nelx, nely, nelz), dtype=bool)
design_mask[bolt_hole_region] = False     # passive void
passive_solid = np.zeros_like(design_mask)
passive_solid[motor_mount_region] = True  # must remain x = 1
# fixed nodes (Dirichlet)
fixed_dofs = np.concatenate([node_ids_at_battery_tray * 3 + 0,
                             node_ids_at_battery_tray * 3 + 1,
                             node_ids_at_battery_tray * 3 + 2])
# load vector (Neumann)
F[motor_thrust_nodes * 3 + 2] = -thrust_N  # downward thrust reaction
```

Inside the OC/MMA loop, force `x[passive_solid] = 1` and `x[~design_mask] = x_min` after every update, and exclude them from the volume-fraction accounting.

#### 4.4 Post-processing the density field

The optimizer hands you a 3D array `x[i,j,k] ∈ [0,1]`. Steps:

1. **Threshold** at 0.5 (or sweep around the iso-value to see how sensitive your topology is — robust designs should be insensitive in a band around 0.5).
2. **Marching cubes:** `verts, faces, normals, _ = skimage.measure.marching_cubes(x, level=0.5)`.
3. **Smooth:** Taubin smoothing via `trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=10)` — Taubin preserves volume better than naive Laplacian smoothing.
4. **Remesh:** `pymeshlab` or gmsh's remesh-from-STL to get a regular triangulation. Useful before stress verification.
5. **Verify:** mesh the smoothed STL in gmsh, re-run FEA at the smoothed geometry, confirm peak von Mises is within the limit — TO optima can degrade by 5–15 % through smoothing.

#### 4.5 STL export

Trivial: `trimesh.Trimesh(vertices=verts, faces=faces).export('drone_arm.stl')` or `meshio.write_points_cells('drone_arm.stl', verts, [('triangle', faces)])`. The resulting STL is immediately printable on FDM/SLA and CNC-millable from any slicer.

#### 4.6 STEP export — the brutal truth

You will not get a clean parametric STEP out of an open-source pipeline for an organic TO geometry as of 2026. The honest picture:

- **OpenCASCADE itself does not have a mesh-to-BRep operation.** Per the official OCCT developer forum: *"Is it OK to have a single B-Rep face for each individual triangle? Otherwise, the problem is extremely difficult to solve, and there is no open source solution for that on the earth (afaik). … OCCT does not provide such a functionality."*
- **FreeCAD's `Part.Shape().makeShapeFromMesh(mesh.Topology, tolerance)`** is documented in the FreeCAD API stubs as "Make a compound shape out of mesh data. **Note: This should be used for rather small meshes only.**" It produces a compound of planar triangle-faces. The `Part.RefineShape` cleanup helps but does not fit cylinders or NURBS.
- **Jeff Strater, Senior Software Architect on the Fusion 360 team, publicly stated about Autodesk's own Mesh-to-BRep command:** *"This is a very dumb conversion. Each triangle is converted into a separate BRep face. … Cylinders are not cylinders afterward. … the representation is inaccurate, and the model is very heavy. I wish we had never introduced this command into Fusion at all."* Fusion is commercial; OSS is no better.
- **Gmsh's `gmsh.model.mesh.classifySurfaces(...)` + `createGeometry()`** (Beaufort, Geuzaine, Remacle, *J. Comp. Phys.* 417 (2020)) builds a *discrete reparametrization* — patches with per-patch harmonic maps. The Gmsh manual is explicit: *"Gmsh does not perform geometrical operations on such discrete entities, but they can be equipped with a geometry through a so-called 'reparametrization' procedure. The parametrization is then used for meshing, in exactly the same way as for CAD entities."* This is good enough to re-mesh for FEM but is **not** an analytic NURBS B-Rep and a downstream CAD program will not edit it parametrically.

Practical recommendations for STEP:

1. **Best:** treat STL as the deliverable. Modern additive manufacturing and 5-axis CAM accept STL directly.
2. **Acceptable:** use FreeCAD headless to wrap the smoothed STL into a heavyweight STEP (one face per triangle) — `script tsebukas/stl_reverse_engineering` on GitHub automates this. Useful when a downstream tool *demands* a STEP file but does not actually edit it.
3. **Manual:** trace the organic shape in FreeCAD PartDesign sketches to produce a parametric approximation. Time-consuming but gives a real CAD body.
4. **Commercial (out of scope but worth knowing):** Ansys SpaceClaim AutoSkin, nTopology, Rhino 8 ShrinkWrap + QuadRemesh + ToNURBS — these fit SubD/NURBS to TO geometry. There is no free equivalent.

#### 4.7 FreeCAD as a comparison

FreeCAD has no native TO workbench. Two community efforts exist:

- **`calculix/beso`** — Python BESO (Bi-directional ESO) implementation using the CalculiX FEM solver, integrated into FreeCAD. Uses element-removal not SIMP; works on tetrahedral meshes; lighter on theory but produces useful results.
- **`Serince/FEMbyGEN`** — FreeCAD addon for generative/topology design via the standard FEM workbench. Maintained, with a forum thread.
- **`Foxelmanian/ToOptixFreeCADAddon`** — wraps the ToOptix engine.

For comparison-validation of your own Python pipeline, run the same MBB geometry through `beso` and the Python script and check the topologies match qualitatively — they should.

### 5. The AI-assisted development workflow

#### 5.1 Incremental plan (recommended order)

1. **Week 1 — port and verify 2D.** Have your AI assistant convert `top88.m` line-by-line into Python (or just clone the Aage–Johansen 165-line file). Reproduce the canonical MBB beam (nelx=60, nely=20, volfrac=0.5, penal=3, rmin=1.5) and visually compare to Figure 4 of Andreassen et al. (2011). Expected final compliance ≈ 205 (depends slightly on filter and convergence tolerance).
2. **Week 2 — cantilever, MMA swap.** Same code, change BCs to a tip-loaded cantilever. Replace OC with `mmapy`'s `mmasub`. Verify the solution matches (MMA should give slightly better compliance and converge in fewer iterations).
3. **Week 3 — go 3D.** Port `top3d.m` or pull PyTopo3D directly. Run the 3D cantilever benchmark (Liu & Tovar Section 5.1). On a modest laptop, 60×20×4 elements converges in ~5 minutes.
4. **Week 4 — geometry import.** Build a voxelizer: `pythonocc-core` reads the STEP, `gmsh` or `trimesh.voxelized` produces an occupancy mask, you assemble design/passive/void masks on the voxel grid. Test on a simple bracket.
5. **Week 5 — stress.** Compute element von Mises from the FE displacements (closed form for H8: `σ_vm = sqrt(0.5·((σ_xx − σ_yy)² + (σ_yy − σ_zz)² + (σ_zz − σ_xx)² + 6·(τ_xy² + τ_yz² + τ_zx²)))`). Add a KS aggregator over the design domain and an MMA inequality constraint. Validate against the L-bracket benchmark — the corner should round.
6. **Week 6 — export.** Marching cubes → Taubin smoothing → STL. Stress-verify the smoothed STL with a fresh tet mesh in gmsh + a quick CalculiX or FEniCSx static solve to confirm peak σ stays below limit.

For each step, prompt the AI assistant with: (a) the relevant equations explicitly, (b) the named educational code to mimic, (c) the benchmark result to hit, (d) a list of likely bug classes ("check sign of sensitivity", "verify edofMat indexing zero-based vs one-based") — this dramatically improves output quality versus a vague "write me a topology optimizer".

#### 5.2 Benchmarks and expected values

| Benchmark | Domain | Loading | Volfrac | Expected outcome |
|---|---|---|---|---|
| MBB beam (half) | 60×20 | Tip down-load at top-left | 0.5 | Symmetric truss-like structure; c ≈ 205 (penal=3, rmin=1.5) |
| Cantilever 2D | 60×30 | Mid-right vertical | 0.5 | Two-bar truss splitting from left wall |
| Cantilever 3D | 60×20×4 | Mid-right vertical | 0.3 | Frame-like 3D structure; see Liu & Tovar Fig. 4 |
| L-bracket | L-shape, 100×100 with top-right 60×60 void | Down-load at right tip of top arm | 0.4 | Compliance: sharp corner kept; stress-constrained: corner becomes a smooth arc |

#### 5.3 Common bugs

- **Checkerboard pattern in result** → filter is disabled or rmin too small. Set rmin ≥ 1.5 × element size.
- **Mesh-dependent result** (refining mesh changes topology) → same fix; or switch to PDE filter.
- **Gray everywhere** → penalization p too low (raise to 3), or projection β too low (continuation up to 64), or volume fraction too high.
- **Non-convergence / oscillation** → move limit too large (drop from 0.2 to 0.05), or stress constraint too tight, or OC bisection bounds wrong.
- **Wrong-sign sensitivity** (compliance increases) → check the explicit minus sign in ∂c/∂x_e = − p · x_e^(p−1) · u_e^T k_0 u_e. The 99-line code has this in the `dc` definition; many ports flip a sign.
- **NaNs from KU=F** → low-density floor x_min too small (use 1e-3 to 1e-9, not 0).
- **Stress doesn't drop** → forgot qp-relaxation; or aggregation P too small; or you minimized compliance and only *post-checked* stress instead of constraining it.

#### 5.4 Hyperparameters worth tuning

| Parameter | Typical | Range to sweep |
|---|---|---|
| volume fraction f | 0.3 (3D), 0.5 (2D) | 0.2–0.5 |
| penalization p | 3 | 1 → 3 (continuation), max 5 |
| filter radius rmin | 1.5 × elem size | 1.5–4 |
| move limit (OC) | 0.2 | 0.05–0.2 |
| Heaviside β | 1 → 64 | start 1, ramp ×2 every 50 iters |
| Stress aggregation P | 8 | 4–16 |
| qp gap (p − q) | 0.3 | 0.2–0.5 |
| max iterations | 200 | 100–500 |

---

## Recommendations

**Stage 1 — Day 0 to Week 2 (commit budget: low).** Clone `arjendeetman/TopOpt-MMA-Python` and the DTU Python 165-line code. Reproduce the MBB beam exactly. If compliance ≠ published value to within 1 %, stop and debug — do not move on with a broken baseline.

**Stage 2 — Week 2 to 4 (commit budget: medium).** Move to `PyTopo3D` (Kim & Kang 2025; github.com/jihoonkim888/PyTopo3D) for 3D. It already supports importing passive/obstacle regions as STL files — wrap your drone CAD bounding box, set the bolt-hole and motor-mount regions as passive solid via STL, set non-design exterior as void, and run. Threshold-update: if 3D run > 30 min on your laptop, install **PyPardiso** (`pip install pypardiso`); 5–10× speedup on the linear solve is typical.

**Stage 3 — Week 4 to 6 (commit budget: high).** Add stress. Use the **Holmberg, Torstenfelt, Klarbring (2013)** formulation: minimize volume subject to clustered (region-aggregated) p-norm constraints with qp-relaxation, MMA optimizer. Validate against L-bracket; if the corner doesn't round, your stress is broken.

**Stage 4 — production.** Export the converged density field as STL via scikit-image marching_cubes + Taubin smoothing in trimesh. Re-mesh in gmsh, verify stress field meets the drone load spec (typically include a 1.5–2× safety factor on quasi-static motor thrust, plus a fatigue check via Goodman or local Crossland criterion — TO under fatigue is a 2020s research frontier).

**Stop-loss thresholds.** Reconsider the approach if any of these trigger:
- Your problem has > 5 × 10^6 elements and direct solvers exhaust RAM → switch to TopOpt-in-PETSc or PyAMG iterative + MG preconditioner.
- You need a parametric STEP output that downstream engineers will edit → accept that this requires manual CAD remodeling or a commercial tool (nTopology, Ansys SpaceClaim). No OSS path solves this in 2026.
- You need fatigue, nonlinear material, or multi-physics coupling → step up to FEniCSx + dolfin-adjoint instead of a hand-rolled NumPy code; the adjoint complexity overwhelms the convenience of an 88-line port.

---

## Caveats

- **Stress constraints are research-grade.** Even in commercial code (Tosca, OptiStruct), stress-constrained TO is fragile and requires expert tuning. Set realistic expectations — your first stress-constrained run will likely produce a topology that violates the constraint locally or fails to converge. Compliance + post-check stress is a robust pragmatic alternative.
- **Voxel resolution dictates feature fidelity.** A 100×100×100 grid uses 10^6 elements; below that, fine drone-arm features (1–3 mm) get under-resolved. Above that, RAM and solve time explode. The right answer is body-fitted tets, but that doubles the engineering effort.
- **The L-bracket and MBB benchmarks tell you *qualitatively* whether your code works, not whether it is right for the drone.** You must also validate the converged design with an independent FE tool (CalculiX, FEniCSx, or even FreeCAD FEM with the gmsh-remeshed STL) to be sure your hand-built solver isn't masking a bug.
- **STEP export is the weakest link.** Set expectations with downstream stakeholders before you start — "the output is an STL, and STEP from organic TO geometry is not a solved open-source problem" is an honest answer.
- **Marching cubes outputs are not manifold-guaranteed.** Watertightness checks (`trimesh.Trimesh.is_watertight`) and hole-filling are mandatory before any printing or FEM verification.
- **AI coding assistants get sensitivity signs wrong about 30 % of the time.** Always validate the gradient against finite differences (perturb one element by 1e-6, recompute compliance, compare to the analytic derivative — they must agree to 4 significant figures). This is the single highest-value debug step in topology optimization.
- **Citation honesty.** The seminal references — Bendsøe (1989), Bendsøe & Sigmund (*Topology Optimization: Theory, Methods, and Applications*, Springer, 2nd ed. 2003/2004, ISBN 978-3-642-07698-5), Sigmund (2001), Andreassen et al. (2011), Liu & Tovar (2014), Svanberg (1987), Duysinx & Sigmund (1998), Le et al. (2010), Lazarov & Sigmund (2011), Guest et al. (2004) — should be read in original before you trust any AI-generated derivation. The textbook in particular is the only place where the existence theory and physical admissibility of SIMP are rigorously developed.