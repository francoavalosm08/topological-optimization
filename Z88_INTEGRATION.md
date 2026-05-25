# Z88Arion Integration

This repository now has a first-pass bridge for using Z88Arion/Z88 as the
authoritative solver and topology optimization engine while keeping the Python
project responsible for reproducible run folders, STL QA, and reports.

## Installed Baseline

Z88Arion V3 was installed from the official MSI download.

- MSI: `C:\Users\Box\Downloads\Z88ArionV3_64_de.msi`
- Installed root: `C:\Z88ArionV3`
- Binary directory: `C:\Z88ArionV3\win\bin`
- GUI binary: `C:\Z88ArionV3\win\bin\Z88Arion.exe`
- OC binary: `C:\Z88ArionV3\win\bin\Z88OC.exe`
- TOSS binary: `C:\Z88ArionV3\win\bin\z88rTOSS.exe`
- SKO binary: `C:\Z88ArionV3\win\bin\z88r_sko.exe`
- Solver candidates: `z88r_opt.exe`, `z88rofl.exe`
- Arion-to-optimizer-input converter candidate: `z88ag2oi.exe`
- Bundled meshing utilities: `tetgen.exe`, `netgen.exe`

The all-users MSI install required elevated privileges and failed with Windows
Installer exit code 1603. A per-user-style install succeeded, but the installer
still placed the application under `C:\Z88ArionV3`.

## Current Bridge Scope

Implemented:

- `Z88RunConfig` data contract for units, STL path, material, supports, loads,
  passive regions, optimizer settings, safety factor, and export settings.
- Z88 installation discovery for the installed Windows layout.
- `Z88Adapter.prepare_project(config)` to create a reproducible run folder.
- Manual handoff instructions per run in `Z88_HANDOFF.md`.
- `Z88Adapter.collect_results(project_dir)` to ingest `optimized.stl`, run mesh
  QA, and write `optimization_result.json`.
- Lightweight parsers for native `z88control.txt` and `z88setsactive.txt`.
- CLI scripts for capability audit, project preparation, and result collection.
- Native Z88 project staging with `scripts/z88_stage_project.py`.
- Local-only Z88 asset capture, manifests, diffs, and headless probes under
  ignored `z88_assets/`.
- Headless replay for GUI-generated OC optimizer projects with
  `scripts/z88_run_generated_optimizer.py`.
- Successful local OC replay on `1_Balken_OC` after patching generated solver
  commands from `-PARAO` to `-SICCG`.
- Successful local OC replay on `2_Querlenker_OC` with the same SICCG patch.
- Native OC scalar-history collection with
  `scripts/z88_collect_native_results.py`.
- Final displacement generation with `scripts/z88_generate_displacements.py`
  using the observed `z88rofl.exe -U -SICCG <out> <z88mat> <z88i1> <z88i2>`
  argv contract.
- Native OC project generation from STL/config with
  `scripts/z88_generate_native_project.py` for the confirmed H8 voxel scope.
- Native stress generation with `scripts/z88_generate_stress.py` using the
  observed `z88rTOSS.exe -SIG -SICCG <nodal> <z88mat> <z88i1> <z88i2>
  <element> <energy>` argv contract.
- End-to-end generated OC workflow orchestration with
  `scripts/z88_run_generated_workflow.py`.
- Automatic optimized STL export and mesh QA for wrapper-generated OC/H8
  projects. The workflow thresholds the final `PhysicalDensity` field, writes
  `optimized.stl`, writes `mesh_quality.json`, and records
  `z88_optimized_stl_export.json`.
- Best-available backend entry point with `scripts/z88_run_backend.py`.
- Phase G explicit-box recipe layer:
  - material presets under `presets/materials/`
  - safety presets in `presets/safety_factors.json`
  - generic bracket recipe via `scripts/z88_recipe.py generic_bracket`
  - drone motor mount recipe via `scripts/z88_recipe.py drone_motor_mount`
  - drone landing gear recipe via `scripts/z88_recipe.py drone_landing_gear`
  - drone gimbal mount recipe via `scripts/z88_recipe.py drone_gimbal_mount`
  - ring-wing strut recipe via `scripts/z88_recipe.py ring_wing_strut`
- FastAPI Z88 endpoints for presets, recipe configuration, run preparation,
  native OC/H8 project generation, backend execution, and native result
  collection.
- FastAPI Z88 preflight endpoints for STL bounds inspection and recipe
  validation without writing a run folder:
  - `POST /z88/stl/inspect`
  - `POST /z88/stl/suggest_end_boxes`
  - `POST /z88/recipes/validate`
- Browser Z88 workflow panel in `web/index.html`, including explicit native
  OC/H8 generation, optional stress generation controls, STL bounds inspection,
  visual bounding-box slab picking, and region-box payload helpers.
- Packaged app entry point, PyInstaller spec, package build script, packaged
  smoke test, and generated sample STL workflow:
  - `packaging/z88_topopt_app.py`
  - `packaging/Z88TopologyOptimizer.spec`
  - `scripts/z88_build_package.ps1`
  - `scripts/z88_package_smoke.py`
  - `scripts/z88_generate_samples.py`
- Local crash-report helper and packaging preflight:
  `scripts/z88_packaging_preflight.py`.

Not implemented yet:

- Fully automated solver or optimizer execution starting from only the copied
  bundled pre-project files.
- Native project generation for tetrahedral meshes, TOSS/SKO, or arbitrary
  Z88Arion GUI intermediate files.

The current proven automated path is a replay path for folders where the
Z88Arion GUI has already generated native optimizer files such as
`Z88Arion.pth`, `Z88Arion.fea`, `z88i1.txt`, and `z88i2.txt`, plus a generated
OC/H8 path for voxelized STL configs.

## Commands

Audit the installed Z88Arion baseline:

```powershell
python scripts/z88_capability_audit.py
```

Capture bundled Z88 examples into ignored local assets:

```powershell
python scripts/z88_capture_assets.py
```

Audit a copied fixture into JSON and Markdown:

```powershell
python scripts/z88_audit_fixture.py z88_assets\examples\pre\2_Querlenker_OC
```

Record a manually completed Z88Arion project as a post-run fixture:

```powershell
python scripts/z88_record_post_run.py 2_Querlenker_OC --source path\to\completed_project --optimized-stl path\to\optimized.stl
```

Run a GUI-generated OC optimizer project headlessly:

```powershell
python scripts/z88_run_generated_optimizer.py z88_assets\examples\post_work\1_Balken_OC_gui_run --solver siccg --timeout 900
```

This command rewrites `Z88Arion.pth` to the current project folder and patches
solver flags in `Z88Arion.fea`. Use `--solver siccg` by default on this
machine. The GUI default `-PARAO`/PARDISO path reaches `Start PARDISO` and then
crashes locally with signed Windows NTSTATUS `-1073741795`.

Collect observed native OC result histories:

```powershell
python scripts/z88_collect_native_results.py z88_assets\examples\post\2_Querlenker_OC
```

This writes `z88_native_results.json` in the completed native project folder.
The current collector intentionally covers only observed OC scalar histories
and snapshot inventories:

- `tmp\OverallCompliance.txt`
- `tmp\AktuellesVolumen.txt`
- `tmp\Abbruchkriterium_SIMP.txt`
- `tmp\Güte der 0-1-Verteilung.txt`
- `PhysicalDensity\`
- `DesignResponse\`
- `StrainEnergy\`
- `YoungsModulus\`

Generate and collect final displacements:

```powershell
python scripts/z88_generate_displacements.py z88_assets\examples\post\2_Querlenker_OC --solver siccg
python scripts/z88_collect_native_results.py z88_assets\examples\post\2_Querlenker_OC
```

Observed local displacement summaries:

- `1_Balken_OC`: `11222` nodes, max displacement about `0.0231349` at node
  `91`.
- `2_Querlenker_OC`: `17220` nodes, max displacement about `0.0767051` at node
  `1004`.

Generate and collect final stress for a confirmed generated OC/H8 project:

```powershell
python scripts/z88_generate_stress.py path\to\generated_oc_project --solver siccg
python scripts/z88_collect_native_results.py path\to\generated_oc_project
```

The observed stress command writes:

- `Knotenspannungen\Knot_final.txt`
- `Stresses_ELE\Stress_ele_final.txt`
- `tmp\ElementEnergy_final.txt`

The final argument to `z88rTOSS.exe -SIG` is an energy output file. Do not point
it at `Displacements\Displacements_final.txt`; doing that overwrites the
displacement file.

Automatic stress is intentionally limited to wrapper-generated OC/H8 projects
that include `z88_native_project_write.json`. Copied GUI-generated folders,
TOSS/SKO projects, and tetrahedral probes should report `unsupported` for
automatic stress and should use Z88Arion GUI export or later independent
verification instead.

Generate a native OC/H8 project directly from an STL config:

```powershell
python scripts/z88_generate_native_project.py path\to\config.json --project-dir runs\z88\my_project\z88_project
```

Run the generated project immediately, including displacement and stress
collection:

```powershell
python scripts/z88_generate_native_project.py path\to\config.json `
  --project-dir runs\z88\my_project\z88_project `
  --run-workflow `
  --generate-stress `
  --optimizer-timeout 900
```

Current generated-project limits:

- OC optimizer only.
- H8/hexahedral voxel mesh only.
- Explicit box selectors for supports, loads, and passive-solid regions.
- Material modulus is scaled from Pa to force-per-configured-length-squared;
  for `units="mm"`, Pa is converted to N/mm^2.
- The writer rejects disconnected voxel solids before writing native Z88 files.
- The writer rejects `volume_fraction` values that are below the mandatory
  support/load/passive-solid fixed element volume.
- `z88_native_project_write.json` reports `target_element_count`,
  `minimum_fixed_volume_fraction`, and `solid_component_count` so a rejected or
  marginal setup can be adjusted before running Z88.
- Very low volume fractions can still produce singular Z88 solves even after
  these checks if the remaining design region cannot form a connected load path.
- Generated OC/H8 workflows now produce `optimized.stl` and `mesh_quality.json`
  automatically when final density output is available. This export is a
  thresholded voxel surface, not Z88Arion's smoothed GUI STL.

Validate every generated recipe sample through recipe config, STL inspection,
and native OC/H8 project writing:

```powershell
python scripts/z88_validate_recipe_samples.py --output z88_assets\outputs\recipe_sample_validation.json
```

Current local result:

- `sample_count`: `5`
- `failed_count`: `0`
- All five sample recipes wrote native projects under
  `runs\z88_recipe_validation\native_projects\`.
- The report includes STL bounds, watertightness, mesh counts, native element
  counts, fixed-region volume requirements, and writer warnings.

Validate simple online STL structures through the confirmed OC/H8 generated
workflow:

```powershell
python scripts/z88_validate_online_stls.py --run-workflow --workflow-timeout 180 --output z88_assets\outputs\online_stl_validation_workflow.json
```

Current online sources:

- Wikimedia Commons `Cube.stl`.
- NIST Additive Manufacturing Test Artifact STL.
- Wikimedia Commons `Sphere.stl`.
- Wikimedia Commons `Cilindro_3D.stl`.

Current local result:

- `source_count`: `4`
- `failed_count`: `0`
- All four sources completed optimizer replay, displacement postprocess,
  generated OC/H8 stress postprocess, optimized STL export, and mesh QA.
- Workflow status remains `partial` because these are one-iteration smoke runs
  and some optional native histories, such as SIMP convergence, are not emitted.
- The validator reuses cached downloads when present and deletes only its own
  generated validation project folder before rewriting it. This avoids public
  host rate-limit failures and stale Z88 output contamination during repeated
  local gate runs.

Run the current accuracy evidence gate:

```powershell
python scripts/z88_accuracy_gate.py --output z88_assets\outputs\accuracy_gate.json
```

Current gate status: `passed` for confirmed GUI OC compliance references and
the generated H8 online-STL workflows. TOSS/SKO, larger copied-fixture stress,
and general tetra generation are recorded as capability gates rather than
passed accuracy gates.

Probe the installed TetGen path without enabling tetrahedral project writing:

```powershell
python scripts/z88_tetgen_probe.py runs\z88_representative_drone_samples\generic_bracket_box.stl --probe-direct-stl --output-dir z88_assets\outputs\tetgen_probe\representative_generic_bracket
```

Current TetGen evidence:

- Direct binary STL input failed locally with return code `3` and `Wrong number
  of vertices in file`.
- Converting the same STL to OFF first allowed TetGen to write
  `z88structure.txt`.
- The generated structure header was `3 222 533 666 0 #AURORA_V2`.
- The first node ID was `0`, so this path emits zero-based IDs.
- This is probe evidence only. Tetrahedral native project generation remains
  disabled until the rest of the Z88 project file contract is confirmed.
- Additional online-STL evidence: the simple Wikimedia cube can produce
  `z88structure.txt` through OFF conversion, while the NIST artifact fails
  through both direct STL and OFF conversion. Keep tetrahedral generation
  disabled as the default raw-STL path.

Run the confirmed generated OC workflow end to end:

```powershell
python scripts/z88_run_generated_workflow.py path\to\gui_generated_oc_project --solver siccg
```

Add `--generate-stress` to run the observed stress postprocess after
displacement generation.

The workflow does:

- Patch `Z88Arion.pth` and `Z88Arion.fea`.
- Run `z88optopus.exe -parao` with local solver flags patched to `-SICCG`.
- Generate `Displacements\Displacements_final.txt`.
- Write `z88_native_results.json`.
- Write `z88_generated_oc_workflow.json`.

Real local smoke:

- `1_Balken_OC` copied GUI-generated folder completed end to end in about 50
  seconds.

Run the best currently available backend path:

```powershell
python scripts/z88_run_backend.py path\to\run_or_project_folder --solver siccg
```

Behavior:

- If the folder is a GUI-generated OC project, it runs the confirmed headless
  workflow.
- If the folder is only a prepared STL/config run, it writes
  `Z88_GUIDED_BACKEND_HANDOFF.md` and returns `guided_handoff_required`.
- It always writes `z88_backend_result.json`.

Create a generic bracket recipe run:

```powershell
python scripts/z88_recipe.py generic_bracket `
  --stl path\to\part.stl `
  --support-min=-5,-2,-1 --support-max=-4,2,1 `
  --load-min=4,-2,-1 --load-max=5,2,1 `
  --force=0,-250,0 `
  --material al_6061_t6 `
  --safety-preset consumer_drone
```

The recipe validates that support/load boxes intersect the STL bounds, writes
assumptions into `config.json`, and prepares a Z88 handoff run folder.

Create a drone motor mount recipe run:

```powershell
python scripts/z88_recipe.py drone_motor_mount `
  --stl path\to\mount.stl `
  --frame-min=-5,-2,-1 --frame-max=-4,2,1 `
  --motor-min=4,-2,-1 --motor-max=5,2,1 `
  --thrust=25 `
  --thrust-direction=0,0,1 `
  --prop-diameter 10
```

This recipe still uses explicit boxes. It does not automatically pick motor
faces yet; that belongs in a later UI/geometry-selection step.

Create a drone landing gear recipe run:

```powershell
python scripts/z88_recipe.py drone_landing_gear `
  --stl path\to\landing_gear.stl `
  --frame-min=-5,-2,-1 --frame-max=-4,2,1 `
  --contact-min=4,-2,-1 --contact-max=5,2,1 `
  --payload-mass 2.0 `
  --impact-g 4.0 `
  --load-direction=0,0,1
```

This applies a static-equivalent contact load of
`payload_mass * 9.80665 * impact_g` in the normalized load direction. It is not
a transient impact simulation.

Create a drone gimbal mount recipe run:

```powershell
python scripts/z88_recipe.py drone_gimbal_mount `
  --stl path\to\gimbal_mount.stl `
  --frame-min=-5,-2,-1 --frame-max=-4,2,1 `
  --camera-min=4,-2,-1 --camera-max=5,2,1 `
  --camera-mass 0.4 `
  --maneuver-g 2.5 `
  --load-direction=0,-1,0 `
  --target-vibration-frequency 120
```

The target vibration frequency is recorded in `config.json` notes only. No
modal/frequency-constrained optimizer is implemented yet.

Create a ring-wing strut recipe run:

```powershell
python scripts/z88_recipe.py ring_wing_strut `
  --stl path\to\strut.stl `
  --root-min=-5,-2,-1 --root-max=-4,2,1 `
  --wing-min=4,-2,-1 --wing-max=5,2,1 `
  --lift-force-per-strut 30 `
  --lift-direction=0,0,1
```

All recipe commands validate that explicit boxes intersect the STL bounds and
reject non-finite boxes, zero vectors, and non-positive masses or loads before
preparing a run folder.

Use the browser Z88 panel:

```powershell
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`, scroll to **Z88Arion Workflow**, paste a local
STL path, adjust the recipe payload, and choose one of:

- **Configure Only**: validate the recipe and return `Z88RunConfig`.
- **Inspect STL Bounds**: read bounded STL metadata from the server and show
  min/max bounds, extents, watertightness, area, and volume when available.
- **Validate Payload**: run `/z88/recipes/validate`, returning both the config
  and geometry metadata without writing any run folder.
- **Prepare Run Folder**: create the conservative STL handoff folder.
- **Generate Native OC Project**: voxelize the STL and write the confirmed
  OC/H8 native project contract.
- **Run / Guide Backend**: run the best available backend for the selected
  project folder, or write a guided handoff when the folder is not runnable.

The **Generate stress output** checkbox is intentionally optional. It is
confirmed for generated OC/H8 projects, but remains risky on larger copied
GUI-generated fixtures.

Generate local sample STLs and load the first sample into the browser panel:

```powershell
python scripts/z88_generate_samples.py --output samples
```

The browser **Generate Samples** button writes the same sample catalog under
`runs/z88_samples` and populates the panel with the first sample recipe.
These samples use conservative `volume_fraction=1.0` and one optimizer
iteration by default. They are smoke-test geometry, not engineering-quality
optimization targets.

Run packaging/deployment preflight:

```powershell
python scripts/z88_packaging_preflight.py --output z88_assets\outputs\packaging_preflight.json
```

Build the local executable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/z88_build_package.ps1
```

The build script:

- generates sample STLs under `samples/`;
- writes preflight JSON under `z88_assets/outputs/`;
- runs PyInstaller using `packaging/Z88TopologyOptimizer.spec`;
- runs `dist\Z88TopologyOptimizer.exe --smoke-test --no-browser --allow-missing-z88`.

Run the packaged server manually:

```powershell
dist\Z88TopologyOptimizer.exe --host 127.0.0.1 --port 8000
```

Or run a non-server smoke test:

```powershell
dist\Z88TopologyOptimizer.exe --smoke-test --no-browser --allow-missing-z88
```

Current local packaging status:

- PyInstaller is installed in the active Python environment.
- `dist\Z88TopologyOptimizer.exe` builds successfully.
- The packaged smoke test passes.
- A packaged runtime server smoke on `http://127.0.0.1:8010/` served the Z88
  browser UI successfully.
- Local packaged validation passed with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/z88_clean_vm_validate.ps1 -Exe dist\Z88TopologyOptimizer.exe -Port 8020 -Output z88_assets\outputs\clean_vm_validation_local.json
```

This is a local packaged-server validation, not a true fresh Windows VM release
test.

Current stress/von-Mises status:

- `z88rofl.exe -SIG` is not accepted by the OC solver binary.
- `z88rTOSS.exe -SIG` is confirmed for generated OC/H8 projects when the final
  argument is `tmp\ElementEnergy_final.txt`.
- `z88_bridge/results.py` parses counted scalar summaries from
  `Knotenspannungen\*.txt` and `Stresses_ELE\*.txt`.
- The same stress command is not proven reliable on the larger copied
  GUI-generated OC fixtures, so backend/API/UI stress generation remains
  opt-in.
- Current copied GUI-fixture probe: `1_Balken_OC` returns Windows access
  violation code `3221225477` after writing a partial energy file and an empty
  nodal file. The wrapper reports this as `status="crashed"`.

Compare manually run pre/post project folders:

```powershell
python scripts/z88_diff_project.py z88_assets\examples\pre\2_Querlenker_OC z88_assets\examples\post\2_Querlenker_OC
```

Probe installed binaries for headless behavior:

```powershell
python scripts/z88_headless_probe.py --mode cwd-copy
```

Probe TOSS with the installed runtime file seeded into copied fixtures and
candidate solver argv:

```powershell
python scripts/z88_headless_probe.py --binary z88rTOSS --mode cwd-copy --seed-runtime --candidate-argv "-t -siccg" --candidate-argv "-c -siccg"
```

The probe uses per-binary working copies under
`z88_assets\outputs\headless_probe\work\` so canonical fixtures in
`z88_assets\examples\pre\` are not mutated.

Current observed TOSS behavior:

- Without runtime seeding, `z88rTOSS.exe` reports missing `Z88.DYN`.
- With `--seed-runtime`, no-arg `z88rTOSS.exe` prints usage guidance.
- With `--seed-runtime --candidate-argv "-t -siccg"` or `"-c -siccg"`, the
  binary reaches the next missing project-file gate, `Z88MANAGE.TXT`.

Probe the Arion-to-optimizer-input converter:

```powershell
python scripts/z88_headless_probe.py --binary z88ag2oi --mode cwd-copy --seed-runtime --candidate-argv "2 1 384"
```

Current observed converter behavior:

- No-arg `z88ag2oi.exe` prints usage guidance for language and console-output
  flags.
- `z88ag2oi.exe 2 1 384` starts conversion for the copied OC fixture and then
  fails while writing `z88i1.txt`.
- This suggests the copied pre fixture is missing GUI/intermediate state needed
  to generate solver input files.

Current observed generated-optimizer behavior:

- `1_Balken_OC` was opened in Z88Arion and the GUI generated optimizer files.
- Default GUI execution failed locally because the generated `-PARAO` PARDISO
  solver path crashes in `z88rofl.exe`.
- Replaying the same generated project with `Z88Arion.fea` patched to `-SICCG`
  allowed `z88optopus.exe -parao` to complete in 39 iterations.
- `2_Querlenker_OC` also completes with the same SICCG replay path in 120
  iterations.
- The successful post-run fixture is recorded under
  `z88_assets\examples\post\1_Balken_OC`.
- The successful `2_Querlenker_OC` post-run fixture is recorded under
  `z88_assets\examples\post\2_Querlenker_OC`.

Prepare a run folder from an STL:

```powershell
python scripts/z88_prepare_project.py path\to\part.stl --project-name bracket_z88 --method oc --volume-fraction 0.4
```

Stage an existing native Z88Arion project folder:

```powershell
python scripts/z88_stage_project.py C:\Z88ArionV3\docu\examples\project\2_Querlenker_OC --project-name querlenker_fixture
```

Summarize a native or staged Z88 project folder:

```powershell
python scripts/z88_summarize_project.py C:\Z88ArionV3\docu\examples\project\2_Querlenker_OC
```

Then open Z88Arion, import the generated `input.stl`, apply the settings from
`config.json`, run the optimization, and export the smoothed result as
`optimized.stl` into the generated run folder.

Collect the exported result:

```powershell
python scripts/z88_collect_results.py runs\z88\bracket_z88_<run_id>
```

Or copy the exported STL during collection:

```powershell
python scripts/z88_collect_results.py runs\z88\bracket_z88_<run_id> --optimized-stl path\to\exported.stl
```

## Run Folder Contract

Each prepared run folder contains:

- `config.json`: serialized `Z88RunConfig`.
- `input.stl`: normalized copy of the input STL for Z88Arion.
- `z88_project/`: reserved for native Z88 project files once mapped.
- `z88_raw_results/`: archive location for native Z88 result files.
- `Z88_HANDOFF.md`: exact manual handoff instructions.
- `z88_installation.json`: discovered binary paths.
- `bridge_status.json`: current bridge state.

After collection, it also contains:

- `optimized.stl`: exported Z88Arion result.
- `mesh_quality.json`: watertightness, components, area, volume, and degenerate
  face count.
- `optimization_result.json`: machine-readable bridge result.

For staged native projects, `z88_project/` contains the copied native project
files and `z88_project_summary.json` contains parsed control, active set, and
structure-header metadata.

## Local Asset Contract

`z88_assets/` is the local fixture and large-output workspace. It is ignored by
Git and may contain copied bundled examples, manually run projects, solver logs,
exported STL files, and comparison artifacts.

Expected layout:

- `z88_assets/examples/pre/`: copied bundled Z88 project folders.
- `z88_assets/examples/post/`: manually run/exported Z88 project folders.
- `z88_assets/manifests/`: checksum manifests and parsed summaries.
- `z88_assets/outputs/`: large logs, probes, exported STL, and comparisons.

The roadmap for this work lives in `z88_integration_plan.md`.

## Native Z88 Project Files Found

The installed example projects under `C:\Z88ArionV3\docu\examples\project`
confirm these recurring files:

- `z88control.txt`: solver and topology optimization settings. The
  `TOSOLVER` block includes fields such as `OPTMAXIT`, `OPTALGORITHM`,
  `OPTVREL`, `OPTPENALTY`, filter settings, OC settings, and TOSS settings.
- `z88setsactive.txt`: compact active material, load, constraint, mesh, and
  fixed/non-design set descriptors with display labels.
- `z88sets.txt`: expanded set membership lists, often large.
- `z88structure.txt`: mesh node coordinates and element/connectivity data,
  often large.
- `z88marks.txt`: present in some TOSS/undercut examples.

Observed `OPTALGORITHM` values in bundled examples:

- OC examples use `OPTALGORITHM 1`.
- TOSS examples use `OPTALGORITHM 3`.
- SKO examples use `OPTALGORITHM 4`.

These observations are useful but not yet sufficient for safe project writing.
Pre/post OC fixtures now exist, and the remaining writer gate is confirming how
to regenerate the GUI-only intermediate files from STL/config without manually
using Z88Arion.

## Next Integration Gate

The next useful implementation steps are:

1. Run the browser/API native OC generation path on at least one real STL part
   with conservative volume fraction and explicit support/load boxes.
2. Test the five explicit-box recipes on real parts and refine region input
   ergonomics.
3. Continue investigating TOSS/SKO and tetrahedral native generation as
   separate gated tracks; do not infer them from the confirmed OC/H8 path.
4. Continue investigating stress generation on larger copied GUI-generated
   fixtures, keeping it optional until reliable.
5. Only then consider enabling `Z88Adapter.run()` as a broad automated entry
   point instead of keeping backend execution mode-explicit.
