# Z88Arion Integration Roadmap With Implementation Gates

This is the implementation roadmap for bringing Z88Arion/Z88 into the current
topology optimization repo. It keeps the current architecture, uses ignored
local `z88_assets/` for heavy Z88 examples and outputs, and advances through
tested gates so we do not write project files, parse results, or build UI on
unverified format assumptions.

## Current Baseline

- Z88Arion V3 is installed at `C:\Z88ArionV3`.
- `z88_assets/` is ignored by Git and contains copied OC/TOSS/SKO examples.
- Current bridge can discover Z88, prepare STL handoff folders, stage native
  projects, summarize native files, capture manifests, diff project folders,
  collect exported STL, and probe binaries.
- Current bridge can replay GUI-generated OC optimizer folders with
  `scripts/z88_run_generated_optimizer.py`.
- Current native project parsing covers `z88control.txt`, `z88setsactive.txt`,
  and the `z88structure.txt` header. Current native result parsing covers OC
  histories, snapshot summaries, displacements, and generated OC/H8 stress
  summaries.
- Current successful generated-optimizer evidence:
  - `1_Balken_OC` was opened in the Z88Arion GUI so native optimizer files were
    generated.
  - Replaying that generated folder with `Z88Arion.fea` patched from
    `-PARAO` to `-SICCG` completed in 39 OC iterations.
  - Final observed scalar histories: compliance about `2.2141998514`, current
    volume about `418.50000343`, and SIMP convergence criterion about
    `8.7047E-04`.
  - `2_Querlenker_OC` also completed through the same replay path in 120 OC
    iterations.
  - Final observed `2_Querlenker_OC` scalar histories: compliance about
    `521.1895650750`, current volume about `2152001.618496718`, and SIMP
    convergence criterion about `1.5516E-05`.
- Current native result parsing evidence:
  - `scripts/z88_collect_native_results.py` writes `z88_native_results.json`
    for completed OC post folders.
  - It parses `OverallCompliance`, `AktuellesVolumen`,
    `Abbruchkriterium_SIMP`, and `Güte der 0-1-Verteilung` scalar histories.
  - It inventories `PhysicalDensity`, `DesignResponse`, `StrainEnergy`, and
    `YoungsModulus` snapshots without parsing large per-element arrays yet.
  - `scripts/z88_generate_displacements.py` can generate final Z88O2
    displacement output using `z88rofl.exe -U -SICCG`.
  - `z88_bridge/results.py` parses displacement summaries: node count,
    components per node, max magnitude, and max node.
  - `scripts/z88_generate_stress.py` can generate observed nodal and element
    scalar stress files for the confirmed generated OC/H8 path using
    `z88rTOSS.exe -SIG -SICCG`.
  - `z88_bridge/results.py` parses stress summaries for
    `Knotenspannungen/*.txt` and `Stresses_ELE/*.txt`.
  - Stress postprocess crashes on copied GUI-generated `1_Balken_OC` with
    Windows access violation return code `3221225477` after writing only a
    partial energy file and an empty nodal file. The postprocess status now
    reports this as `crashed`.
  - Product behavior decision: automatic stress is supported only for
    wrapper-generated OC/H8 projects. Other Z88 project types report
    `unsupported` and should use Z88Arion GUI export or later independent
    verification instead of running the unstable headless stress command.
- Current native writer evidence:
  - `scripts/z88_generate_native_project.py` generates an OC/H8 voxel project
    from `Z88RunConfig` and STL input.
  - The generated writer uses the confirmed H8 element ordering,
    `Z88Arion.ctrl`, `Z88Arion.pth`, `Z88Arion.fea`, `z88i1.txt`,
    `z88i2.txt`, `z88mat.txt`, `z88int.txt`, `z88elp.txt`, `FixSets.txt`,
    and runtime files.
  - A local 45-element STL smoke completed optimizer replay, displacement
    generation, stress generation, and JSON collection.
- Current TetGen/tetrahedral probe evidence:
  - `scripts/z88_tetgen_probe.py` can run the installed `tetgen.exe` against a
    working-copy mesh probe and record stdout/stderr plus `z88structure.txt`
    metadata.
  - Direct binary STL input failed locally with return code `3` and `Wrong
    number of vertices in file`.
  - Converting the same STL to OFF with `trimesh`, then running
    `tetgen.exe -pl`, completed and wrote `z88structure.txt`.
  - The observed header was `3 222 533 666 0 #AURORA_V2`, first node ID was
    `0`, and the first observed element block used element type `17`.
  - This confirms only a structure-file probe path. Tetrahedral native project
    generation remains gated until material, load/support, optimizer, runtime,
    and GUI intermediate files are confirmed.
  - A later online-STL probe confirmed the simple Wikimedia cube can produce
    `z88structure.txt` through OFF conversion, while direct STL still fails.
  - The NIST Additive Manufacturing Test Artifact failed through both direct
    STL and OFF conversion, so tetra generation is not reliable enough to
    become the default raw-STL path.
- Current backend workflow evidence:
  - `scripts/z88_run_generated_workflow.py` orchestrates the confirmed
    GUI-generated OC path: optimizer replay, displacement postprocess, and
    native result collection.
  - A copied `1_Balken_OC` GUI-generated folder completed this workflow
    locally in about 50 seconds.
  - `scripts/z88_run_backend.py` now routes GUI-generated OC folders to the
    confirmed workflow and prepared STL/config folders to guided handoff.
- Current recipe evidence:
  - Material presets and safety presets exist under `presets/`.
  - `scripts/z88_recipe.py generic_bracket` creates a validated
    `Z88RunConfig` and prepared handoff folder from explicit support/load boxes.
  - `scripts/z88_recipe.py drone_motor_mount` creates a validated
    `Z88RunConfig` and prepared handoff folder from explicit frame/motor boxes
    plus thrust magnitude and direction.
  - `scripts/z88_recipe.py drone_landing_gear` creates a static-equivalent
    impact-load config from payload mass, impact g, and explicit
    frame/contact boxes.
  - `scripts/z88_recipe.py drone_gimbal_mount` creates an inertial camera-load
    config from camera mass, maneuver g, optional target vibration frequency,
    and explicit frame/camera boxes.
  - `scripts/z88_recipe.py ring_wing_strut` creates a lift-load strut config
    from lift force per strut and explicit root/wing boxes.
  - `z88_bridge.configure_recipe_from_payload()` is the shared payload-to-config
    path used by CLI/API/UI validation.
  - `z88_bridge.inspect_stl_geometry()` reports bounded STL geometry metadata
    for recipe preflight and UI region-box work.
  - `scripts/z88_validate_recipe_samples.py` validates all five generated
    sample recipes through config generation, STL inspection, and native OC/H8
    project writing.
  - Current local validation report:
    `z88_assets/outputs/recipe_sample_validation.json`, `sample_count=5`,
    `failed_count=0`.
  - A generated box STL recipe smoke produced a prepared run folder, and the
    backend correctly returned `guided_handoff_required`.
  - `z88_bridge.suggest_end_boxes_from_stl()` creates support/load slab
    suggestions at opposite bounding-box ends for simple structures. This is
    an ergonomic helper only; users must inspect suggested boxes before
    engineering use.
- Current simple-structure online STL evidence:
  - `scripts/z88_validate_online_stls.py` downloads trusted public test STLs
    into ignored `z88_assets/online_stls/`, builds generic-bracket
    configurations, writes native OC/H8 projects, and can run the confirmed
    generated workflow.
  - Current sources are Wikimedia Commons `Cube.stl` and the NIST Additive
    Manufacturing Test Artifact STL.
  - Current workflow report:
    `z88_assets/outputs/online_stl_validation_workflow.json`, `source_count=2`,
    `failed_count=0`.
  - Both online STLs completed optimizer replay, displacement postprocess, and
    generated OC/H8 stress postprocess. Workflow status remains `partial`
    because optimized STL export and mesh QA are not yet part of the generated
    workflow.
- Current accuracy-gate evidence:
  - `scripts/z88_accuracy_gate.py` validates known GUI OC compliance
    references, generated online STL workflow results, and recorded TetGen
    gate status.
  - Current report: `z88_assets/outputs/accuracy_gate.json`, status `passed`.
  - `1_Balken_OC` final compliance matches the stored reference
    `2.21419985143696` within the 0.5% gate.
  - `2_Querlenker_OC` final compliance matches the stored reference
    `521.1895650750` within the 0.5% gate.
- Current UI/API evidence:
  - The FastAPI app exposes Z88 material presets, safety presets, recipe
    metadata, recipe configuration, recipe validation, STL inspection,
    run-folder preparation, explicit native OC/H8 project generation, backend
    execution, and native result collection.
  - The browser UI has a Z88 workflow panel for recipe payload editing,
    STL bounds inspection, region-box payload editing, run-folder preparation,
    native OC/H8 generation, optional stress generation, and backend/guided
    handoff execution.
  - Step 7 implementation scope: the browser UI now includes a visual
    bounding-box slab picker. It uses inspected STL bounds, axis/end/thickness
    controls, and writes the chosen slab to the selected recipe box field. This
    is intentionally not full triangle face picking.
- Current packaging-readiness evidence:
  - Local crash-report helpers write traceback, JSON context, and selected
    copied files under `crash_reports/`.
  - `scripts/z88_packaging_preflight.py` checks Python, platform, required
    modules, Z88 installation, and PyInstaller availability.
  - `packaging/z88_topopt_app.py` is the packaged app entry point.
  - `packaging/Z88TopologyOptimizer.spec` builds the FastAPI/browser app and
    includes web assets, presets, docs, and generated sample STLs when present.
  - `scripts/z88_build_package.ps1` generates samples, runs preflight, builds
    the executable, and runs packaged smoke.
  - Generated sample STLs use conservative no-removal smoke settings
    (`volume_fraction=1.0`, one optimizer iteration) so first-run validation
    does not fail from low-volume singularity.
  - `dist/Z88TopologyOptimizer.exe` was built locally and served the Z88 UI in
    a runtime smoke test.
- Current local solver limitation:
  - The GUI default `-PARAO`/PARDISO path crashes locally in `z88rofl.exe` at
    `Start PARDISO` with signed Windows NTSTATUS `-1073741795`.
  - Use `-SICCG` for local replay unless later evidence proves PARDISO is fixed
    on this machine.
- Current test baseline: `python -m pytest tests -v`.
- Current working-copy headless probe evidence for `2_Querlenker_OC`:
  - `Z88OC.exe`: `crashed`, adds `Z88OC.log` in the working copy.
  - `z88rTOSS.exe`: `needs_solver_files`, reports missing `Z88.DYN`.
  - `z88r_sko.exe`: `crashed`, no project mutation observed.
  - `z88r_opt.exe`: `mutated_project`, adds `z88r.log`.
- Current seeded-runtime TOSS probe evidence:
  - Copying `C:\Z88ArionV3\win\bin\z88.dyn` into a copied fixture as
    `Z88.DYN` gets `z88rTOSS.exe` past the missing-runtime-file error.
  - No-arg seeded `z88rTOSS.exe` reports a usage error and prints candidate
    call patterns.
  - Seeded `z88rTOSS.exe -t -siccg` and `z88rTOSS.exe -c -siccg` reach the next
    missing project-file gate: `Z88MANAGE.TXT`.
- Current TOSS/SKO gate evidence:
  - `5_Winkelhalter_TOSS` probe evidence is preserved under
    `z88_assets/outputs/headless_probe_toss_gate/probe_results.json`.
  - TOSS has visible usage help once `Z88.DYN` is seeded, but candidate
    `-t -siccg` and `-c -siccg` runs stop at missing `Z88MANAGE.TXT`.
  - `7_Balken_SKO` probe evidence is preserved under
    `z88_assets/outputs/headless_probe_sko_gate/probe_results.json`.
  - SKO currently exits with Windows code `3221225781` without useful output,
    so SKO headless execution is not proven.
- Current converter probe evidence:
  - `z88ag2oi.exe` appears to be the Arion-to-optimizer-input converter.
  - It accepts language/console/SIMCASE-style args such as `2 1 384`.
  - On copied pre fixtures it starts, then fails while writing `z88i1.txt`,
    which implies required GUI/intermediate state is still missing.
- Do not implement full native writers or UI until fixture evidence confirms
  the file formats.
- Native result parsing may now start against the concrete OC outputs from the
  successful `1_Balken_OC` post fixture, but only for files already observed.

## Key Decisions

- Keep this repo as the implementation target; do not create a standalone
  `z88wrapper` package.
- Keep `z88_bridge/` as the Z88 backend integration package.
- Keep `Z88_INTEGRATION.md` as operational docs.
- Keep this file as the roadmap.
- Store all large Z88 examples, outputs, logs, and manual post-run projects in
  ignored `z88_assets/`.
- Z88Arion/Z88 are authoritative for Z88-backed solve results.
- The current Python prototype remains useful for fallback, comparison,
  reporting, and research extensions.
- Backend correctness comes before UI work.

## Phase A: File-Format Lockdown

Goal: create a factual map of the Z88 project files we already captured.

Coding steps:

1. Maintain `FILE_FORMAT_REFERENCE.md` with sections for `z88control.txt`,
   `z88setsactive.txt`, `z88sets.txt`, `z88structure.txt`, `z88marks.txt`,
   known logs, and unknown output files.
2. Use confidence tags: `CONFIRMED`, `OBSERVED`, `INFERRED`, `DEFERRED`.
3. Keep `scripts/z88_audit_fixture.py` as the audit CLI.
4. Reuse `build_project_manifest`, `summarize_project_files`, and
   `inventory_files`.
5. Project summaries must include safe previews for every root file: first
   line, line count, byte count, SHA-256, empty flag, and binary-like flag.
6. Parser helpers must not crash on malformed optional files. Optional parse
   failures are warnings.
7. Generate local audits for the captured pre fixtures under
   `z88_assets/manifests/`.

Testing after coding:

- Add synthetic fixture tests for audit JSON and Markdown.
- Add parser tests for missing optional files.
- Add parser tests for empty files and non-UTF8 bytes.
- Run targeted Z88 tests.
- Run full suite.

Bug and crash risks:

- Z88 files can contain non-UTF8 bytes; readers must decode with replacement or
  stay binary-safe.
- Logs can be zero-byte; summaries must handle empty files.
- Some folders may omit `z88control.txt`; audit must not crash.
- Large files like `z88sets.txt` must not be fully printed into Markdown.

Exit gate:

- Every captured OC/TOSS/SKO pre-fixture has audit JSON and Markdown under
  `z88_assets/manifests/`.
- `FILE_FORMAT_REFERENCE.md` reflects observed local fixtures rather than
  guesses from the temporary roadmap.

## Phase B: Manual Pre/Post Run Audit

Goal: determine exactly what Z88Arion writes after a real optimization.

Coding steps:

1. Keep `scripts/z88_record_post_run.py` as the standardized post-run recorder.
2. Validate that the matching pre fixture exists.
3. Reject `--source` if it points at the pre fixture.
4. Reject empty source folders.
5. Copy the completed manual project into
   `z88_assets/examples/post/<fixture-name>`.
6. If `--optimized-stl` is supplied, copy it into the post folder and accept
   `.stl` case-insensitively.
7. Write `<fixture-name>.post.manifest.json` and
   `<fixture-name>.pre_post_diff.json` under `z88_assets/manifests/`.
8. Print added, removed, modified, and unchanged file counts.

Manual workflow:

1. Open `z88_assets/examples/pre/2_Querlenker_OC` in Z88Arion.
2. Run OC optimization manually.
3. Save or copy the completed project somewhere temporary.
4. Export optimized STL if Z88Arion does not save it automatically.
5. Run:

```powershell
python scripts/z88_record_post_run.py 2_Querlenker_OC --source <completed-project-folder> --optimized-stl <optional-stl>
```

Testing after coding:

- Synthetic pre/post tests for added, removed, modified, unchanged files.
- Test missing pre fixture failure.
- Test accidental pre-folder source failure.
- Test empty source failure.
- Test optional STL copy and manifest inclusion.
- Run full suite.

Bug and crash risks:

- User may point `--source` at the pre folder; detect by resolved path.
- User may point to an empty folder; fail with an actionable message.
- Z88 probes may mutate copied assets; manifests and diffs must make this
  visible.
- Paths with spaces are normal on this machine; scripts must use `Path` objects
  and avoid string-built shell commands.

Exit gate:

- The pre/post diff for `2_Querlenker_OC` exists.
- The diff identifies real output files or confirms the GUI did not save them
  into the project folder.
- The next parser phase has concrete filenames to target.

## Phase C: Headless Solve Discovery

Goal: prove or disprove a reliable non-GUI command path.

Coding steps:

1. Keep `scripts/z88_headless_probe.py` probe modes: help-only, cwd-no-args,
   cwd-copy, and single-binary.
2. Keep `--working-copy` support so probes never mutate canonical pre assets.
3. Before any cwd run, copy the fixture into
   `z88_assets/outputs/headless_probe/work/<binary-name>/`.
4. Capture stdout, stderr, exit code, elapsed time, root logs, and file diffs
   before/after each binary run.
5. Classify results as `help_available`, `needs_solver_files`,
   `needs_project_files`, `usage_error`, `conversion_failed`,
   `mutated_project`, `runs_from_cwd`, `failed`, `timed_out`, or `crashed`.
6. Add a summary that identifies the next missing requirement, such as
   `Z88.DYN` or `Z88MANAGE.TXT`.
7. Keep runtime seeding opt-in with `--seed-runtime`; this copies install
   runtime files into working copies only.
8. Keep candidate argv probing opt-in with `--candidate-argv`; each candidate
   must run in its own copied fixture.
9. Do not wire `Z88Adapter.run()` yet.
10. Probe converter binaries only in copied fixtures. If a converter starts but
    fails because intermediate GUI state is missing, document that as a manual
    fixture dependency rather than guessing the missing files.

Testing after coding:

- Unit test classification from fake probe dictionaries.
- Unit test working-copy creation does not mutate source fixture.
- Unit test timeout classification.
- Unit test runtime-file seeding.
- Unit test missing project-file classification from copied root logs.
- Run full suite.

Bug and crash risks:

- Running binaries directly in `z88_assets/examples/pre` can pollute canonical
  fixtures; always probe in copies.
- Windows return codes may be large unsigned values.
- Subprocess output can contain invalid encoding; capture bytes and decode with
  replacement.
- Future cancellation must kill process trees, not only parent processes.
- Help probes can fail for missing runtime files outside the copied fixture;
  cwd classification must not be polluted by help-only output.
- Candidate argv probes can crash after progressing farther through startup;
  copied root logs are more useful than return codes alone.

Exit gate:

- We know the current copied-project cwd behavior for the installed binaries.
- If no command path is confirmed, v1 backend remains guided handoff plus
  automated collection.
- Current result: a reliable generated-project replay path is confirmed for
  `1_Balken_OC` and `2_Querlenker_OC` when solver templates are patched to
  `-SICCG`. This is not yet full native project generation from an STL or
  copied pre fixture.
- Current TOSS discovery result: `Z88.DYN` is a required cwd/runtime file, and
  `Z88MANAGE.TXT` is the next missing project file for `-t/-c -siccg`.
- Current converter discovery result: `z88ag2oi.exe` likely produces the solver
  inputs, but copied pre fixtures are insufficient because conversion fails at
  `z88i1.txt` generation.

Implementation addition already made:

- `z88_bridge/headless.py` patches `Z88Arion.pth`, patches solver flags in
  `Z88Arion.fea`, runs `z88optopus.exe -parao`, captures stdout/stderr, and
  writes `z88_headless_run/z88_headless_run.json`.
- `scripts/z88_run_generated_optimizer.py` exposes this path as a CLI.

Next Phase C validation:

1. Keep `1_Balken_OC` and `2_Querlenker_OC` as confirmed generated-project
   replay fixtures.
2. Use SICCG as the default local solver patch.
3. Continue probing TOSS/SKO separately because the confirmed path is currently
   OC-specific.

## Phase D: Native Result Pipeline

Goal: parse real Z88 post-run outputs into structured JSON.

Status: complete for the confirmed GUI-generated OC scalar/displacement scope
and the generated OC/H8 stress scope.

Coding steps:

1. Keep `z88_bridge/results.py` as the native result parsing module.
2. Keep `schema_version` in native Z88 result JSON.
3. Implement parsers only for files identified in the recorded post fixtures.
4. Current implemented scope: OC scalar history files:
   `tmp/OverallCompliance.txt`, `tmp/AktuellesVolumen.txt`,
   `tmp/Abbruchkriterium_SIMP.txt`, and
   `tmp/Güte der 0-1-Verteilung.txt`.
5. Current implemented scope: snapshot inventory and final scalar-field summary
   for `PhysicalDensity/`, `DesignResponse/`, `StrainEnergy/`, and
   `YoungsModulus/` without dumping large arrays into JSON.
6. Current implemented scope: final displacement generation and summary parsing.
7. Current implemented scope: stress generation with `z88rTOSS.exe -SIG` and
   counted scalar stress parsing for generated OC/H8 projects.
8. Parse by explicit node or element ID where IDs exist, never row position
   alone for field data.
9. Add `warnings` and `parse_errors` arrays.
10. Allow native result collection even if STL export is missing.
11. Keep existing STL mesh QA behavior for `optimized.stl`.
12. Add result statuses: `collected`, `partial`, `missing_outputs`,
   `parse_failed`, `mesh_qa_failed`.

Testing after coding:

- Synthetic parser tests with headers, comments, blank lines, malformed rows,
  and non-monotonic IDs.
- Partial collection tests when only some files exist.
- Missing-STL test still producing native JSON.
- Invalid numeric fields should return parse errors rather than crashing.
- Run full suite.

Bug and crash risks:

- Output headers may vary between OC, TOSS, and SKO; use state-machine parsers.
- Some output files may be huge; stream line-by-line where possible.
- Element ordering may differ from input order; store IDs explicitly.
- Stress singularities can produce huge values; report formatting must not
  overflow or truncate meaningfully.

Exit gate:

- Completed `2_Querlenker_OC` post folder produces machine-readable native JSON.
- Parsed values can be compared to Z88Arion postprocessor manually.
- `1_Balken_OC` successful post folder produces at least OC scalar history JSON
  before deeper stress/displacement parsing starts.
- Current status: `1_Balken_OC` and `2_Querlenker_OC` both produce
  `z88_native_results.json` with collected scalar histories and snapshot
  inventories.
- Current status: both fixtures also produce displacement summaries after
  running `scripts/z88_generate_displacements.py`.
- Current status: generated OC/H8 STL projects produce nodal and element stress
  summaries after running `scripts/z88_generate_stress.py` or
  `scripts/z88_generate_native_project.py --run-workflow --generate-stress`.
- Current limitation: the same stress command is not reliable on the larger
  copied GUI-generated OC fixtures; keep stress generation optional there.

## Phase E: Native Project Writer

Goal: generate Z88 project files from our config only after input/output formats
are sufficiently confirmed.

Status: complete for the limited OC/H8 voxel writer. Tetrahedral, TOSS/SKO, and
full Z88Arion GUI-project generation remain deferred.

Coding steps:

1. Keep current dataclasses during parser work.
2. Add compatibility tests before any config schema change.
3. Current implemented scope: `z88_bridge/native_writer.py`.
4. Current implemented scope: `scripts/z88_generate_native_project.py`.
5. Generate into caller-selected folders; default CLI output is under
   `runs/z88/`.
6. Include a manifest and summary immediately after writing.
7. Write `z88_native_project_write.json` with node/element/BC counts.
8. Add manual smoke checklist in `Z88_INTEGRATION.md`.

Testing after coding:

- Synthetic writer tests for exact file content where format is confirmed.
- Round-trip parser/writer tests for small synthetic files.
- Semantic comparison tests against local captured summaries when
  `z88_assets/` exists.
- Local smoke from STL/config through optimizer, displacements, stress, and
  native JSON.
- Run full suite.

Bug and crash risks:

- Tet node ordering can create garbled geometry; do not generate tet meshes
  until ordering is confirmed.
- Unit systems can silently mismatch; write units into config notes and reports.
- `z88sets.txt` may be version-sensitive; make version assumptions explicit.
- Writing native projects too early creates false confidence; gate every writer
  on fixture evidence.

Exit gate:

- A generated OC project opens in Z88Arion and displays expected setup.
- Manual run of generated project produces plausible output and parseable
  result.
- Current status: local generated OC/H8 project runs headlessly with SICCG and
  produces parseable compliance, displacement, and stress summaries.

## Phase F: Backend End-To-End Workflow

Goal: one backend command takes a config or staged project through the best
available Z88 workflow.

Status: complete for the confirmed generated-OC path and guided handoff fallback.

Coding steps:

1. Current implemented scope: `scripts/z88_run_backend.py`.
2. Current implemented scope: if the input is a GUI-generated OC optimizer
   folder, call the proven `z88optopus` replay path.
3. Current implemented scope: `scripts/z88_generate_native_project.py` can
   produce the generated project before calling the confirmed workflow.
4. Current implemented scope: `POST /z88/native/generate_project` exposes that
   same native OC/H8 generation path to the API, with optional immediate
   workflow execution and opt-in stress generation.
5. If headless is not confirmed for the input, print guided handoff steps and
   collect the user-provided post folder or exported STL path.
6. Always write a run manifest, logs, collection report, and mesh QA.
7. Store large outputs in `runs/` or `z88_assets/outputs/`.
8. Update `Z88Adapter.run()` only when the implementation can distinguish
   headless versus guided mode.

Testing after coding:

- End-to-end fake backend test with synthetic pre/post folders.
- Guided-mode missing-output tests.
- Headless-mode test using mocked subprocess.
- Run full suite.

Bug and crash risks:

- Long-running subprocess can hang; use timeout and cancel semantics.
- Partial runs must not be overwritten silently; use unique run folders.
- Manual handoff paths with spaces must be quoted and normalized.
- Solver crash must still produce a partial report with captured logs.

Exit gate:

- One repeatable command produces either optimized STL/report or a clear guided
  handoff state with no hidden assumptions.
- Current status: `scripts/z88_run_generated_workflow.py` satisfies this for
  GUI-generated OC project folders and generated OC/H8 native projects.
- Current status: `scripts/z88_run_backend.py` is the preferred entry point
  because it runs the generated-OC path when possible and otherwise writes a
  guided handoff result.
- Current status: raw STL/config native generation is handled explicitly by
  `scripts/z88_generate_native_project.py` and
  `POST /z88/native/generate_project`; `z88_run_backend.py` is still kept
  conservative for generic prepared handoff folders.

## Phase G: Recipe Library

Goal: reduce configuration burden once backend workflow is reliable.

Status: complete for the explicit-box recipe scope. Automatic face picking and
modal/frequency optimization remain future UI/research work.

Coding steps:

1. Current implemented scope: material and safety preset JSON files.
2. Current implemented scope: recipe helpers returning `Z88RunConfig`.
3. Current implemented scope: generic bracket with explicit support/load boxes.
4. Current implemented scope: drone motor mount with explicit frame/motor boxes.
5. Current implemented scope: drone landing gear with explicit frame/contact
   boxes, payload mass, impact g, and static-equivalent impact load.
6. Current implemented scope: drone gimbal mount with explicit frame/camera
   boxes, camera mass, maneuver g, and optional target vibration frequency
   recorded in notes.
7. Current implemented scope: ring-wing strut with explicit root/wing boxes
   and lift force per strut.
8. Write recipe assumptions to `notes`.
9. Validate selected regions before run folder creation.
10. Reject non-finite boxes, non-finite vectors, zero vectors, and non-positive
    masses/loads before they reach Z88.
11. Current implemented scope: generated sample recipes are validated as a
    batch by `scripts/z88_validate_recipe_samples.py`.

Testing after coding:

- Material JSON schema tests.
- Recipe config generation tests.
- Region intersection sanity tests.
- Unit conversion tests.
- CLI smoke tests for every recipe using the local generated box STL.
- Run full suite.

Bug and crash risks:

- Recipe force assumptions may be wrong for real geometry.
- Region guessing can select the wrong face; require preview or confirmation.
- Unit conversion bugs can invalidate results; test every unit path.

Exit gate:

- At least one drone-relevant part can be configured by recipe and run through
  the backend workflow.
- Current status: all five planned recipes can prepare run folders from explicit
  boxes.
- Current status: those recipe configs can now be fed into the explicit native
  OC/H8 generation path when the selected method is `oc` and the STL can be
  voxelized within the element limit.
- Current status: all five generated sample recipes validate through config
  generation, STL inspection, and native OC/H8 project writing with
  `failed_count=0`.

## Phase H: UI Strategy

Goal: make the workflow usable without jumping to a heavyweight UI too early.

Status: complete for the lightweight browser/API integration scope. A richer
region-picking UI remains gated on confirmed backend needs.

Coding steps:

1. Keep current browser UI until backend proves inputs and outputs.
2. Current implemented scope: FastAPI endpoints for:
   - `GET /z88/materials`
   - `GET /z88/safety_presets`
   - `GET /z88/recipes`
   - `POST /z88/stl/inspect`
   - `POST /z88/recipes/validate`
   - `POST /z88/recipes/configure`
   - `POST /z88/project/prepare`
   - `POST /z88/native/generate_project`
   - `POST /z88/backend/run`
   - `POST /z88/native/collect`
3. Current implemented scope: browser Z88 workflow panel for editing recipe
   payload JSON, inspecting STL bounds, validating payloads, preparing run
   folders, generating native OC/H8 projects, toggling optional stress
   generation, and running the best-available backend.
4. Re-evaluate PySide6/PyVista only if browser UI cannot handle region picking
   or result visualization.
5. UI must show logs, missing outputs, mesh QA, native result warnings, and
   export paths.

Testing after coding:

- API tests for new backend endpoints.
- Browser smoke test for loading local app.
- Result display smoke using synthetic collected report.
- Run full suite.

Bug and crash risks:

- UI can desync from filesystem state; backend must be authoritative.
- WebSocket progress can fail during long solver runs; persist logs to disk.
- Browser cannot access arbitrary local files; route through server APIs.

Exit gate:

- User can complete guided or automated Z88 workflow without editing Python.
- Current status: user can configure/prepare Z88 recipe runs and trigger the
  native OC/H8 generation path or backend/guided handoff through the browser
  UI. Detailed geometric region picking is still explicit-coordinate based.

## Phase I: Packaging

Goal: package only after backend and UI gates pass.

Status: complete for a local Windows executable build. A formal installer
wrapper and clean-VM validation remain release tasks, not core integration
blockers.

Coding steps:

1. Current implemented scope: Z88 install discovery remains available through
   `discover_installation()` and adapter `install_root` overrides.
2. Current implemented scope: `Z88ARION_ROOT` environment fallback for packaged
   or clean-machine installs outside the default path.
3. Current implemented scope: browser UI has a Z88 install-root field and a
   **Check Z88 Install** button.
4. Current implemented scope: local crash reports with traceback, JSON context,
   and selected copied files.
5. Current implemented scope: packaging preflight script for Python, platform,
   required modules, source/runtime assets, Z88 install, and PyInstaller
   availability.
6. Current implemented scope: PyInstaller spec and build script.
7. Current implemented scope: packaged smoke mode and packaged server runtime
   smoke.
8. Current implemented scope: generated sample STLs and sample catalog for
   first-run validation.
9. Validate on a clean Windows VM before calling this release-ready.
10. Document limitations and confirmed methods.

Testing after coding:

- Fresh app-import smoke.
- Missing Z88 install behavior.
- Crash report generation test.
- Sample generation test.
- Packaging preflight smoke writes local JSON under `z88_assets/outputs/`.
- Packaged executable smoke test.
- Packaged server smoke test.

Bug and crash risks:

- Z88 installed outside default path; user must be able to select path.
- PyInstaller may miss native DLLs if PySide/PyVista is added later.
- Clean machine may lack VC++ runtime.
- The executable is a local app/server package, not a signed installer.

Exit gate:

- Clean Windows can run the app, complete a sample workflow, and export
  optimized STL plus report.
- Current status: local Windows build passes:
  - `powershell -ExecutionPolicy Bypass -File scripts/z88_build_package.ps1`
  - `dist/Z88TopologyOptimizer.exe --smoke-test --no-browser --allow-missing-z88`
  - packaged server smoke on `http://127.0.0.1:8010/`
- Remaining release-only gate: validate on a clean Windows VM.

## Accuracy Definition

- GUI regression: final compliance and max stress within 0.5% on confirmed
  fixtures.
- Mesh refinement: compliance trends toward a stable value.
- Cross-method sanity: OC and TOSS produce plausible load paths.
- Result parser accuracy: parsed values match Z88Arion postprocessor display
  for confirmed fields.

## Usability Definition

- User can load STL or staged project.
- User can define or select loads, supports, passive regions, material, and
  optimizer.
- User can run headless or follow guided Z88 handoff.
- User can collect results without searching folders manually.
- User gets optimized STL, mesh QA, native result JSON, and warnings.
- No Python editing required.

## Immediate Next Implementation Pass

Completed by this roadmap update:

1. Rewrite this file with implementation gates.
2. Add `FILE_FORMAT_REFERENCE.md`.
3. Add `scripts/z88_audit_fixture.py`.
4. Add synthetic tests for audit output and parser hardening.
5. Run audits on current `z88_assets/examples/pre/` fixtures.
6. Run targeted tests.
7. Run full suite.

Current next pass:

1. Test the browser/API native OC/H8 generation path on a real drone STL part
   and record the generated run output under `runs/` or `z88_assets/outputs/`.
2. Run a clean Windows VM validation of `dist/Z88TopologyOptimizer.exe`.
3. Completed in tests: the API now generates sample STLs, configures the
   `generic_bracket_box` recipe payload, and writes a native OC/H8 project from
   that generated sample using the real writer path.
4. Test the five explicit-box recipes on real parts and refine region input
   ergonomics.
5. Completed for representative samples: all five generated recipes validate
   through `scripts/z88_validate_recipe_samples.py`, including native OC/H8
   project writing. Real user parts are still needed for engineering acceptance.
6. Completed for current UI scope: add STL bounds inspection and payload
   validation endpoints/UI controls so box coordinates can be checked before
   any run folder or native project is written.
7. Completed for current UI scope: add visual bounding-box slab picking after
   recipe payload shape validation. Full triangle/face picking remains a later
   UI decision if the browser helper is not enough.
8. Completed: add generated OC/H8 writer guardrails for disconnected voxel
   solids and volume fractions below the mandatory fixed/passive element
   volume. The writer now fails before Z88 sees those unsafe inputs and records
   `target_element_count`, `minimum_fixed_volume_fraction`, and
   `solid_component_count` in `z88_native_project_write.json`.
9. Product decision complete: automatic stress generation is limited to
   wrapper-generated OC/H8 projects. Large GUI-generated OC fixtures remain
   unsupported for automatic stress because the current probe on `1_Balken_OC`
   returns Windows access violation `3221225477`; other project types should
   use Z88Arion GUI export or later independent verification.
10. Completed: add a TetGen probe script and run it against a representative
   generated STL. OFF conversion can write `z88structure.txt`; direct STL input
   fails; tetrahedral native generation remains gated instead of enabled.
11. Run targeted tests.
12. Run full suite.
