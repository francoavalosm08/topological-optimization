# Z88 File Format Reference

This file records the current repo's evidence about native Z88Arion/Z88 files.
It is intentionally conservative: anything not proven from local fixtures stays
`INFERRED` or `DEFERRED`.

Confidence tags:

- `CONFIRMED`: verified by repeated fixture evidence or successful round-trip.
- `OBSERVED`: seen in local Z88Arion V3 examples.
- `INFERRED`: plausible but not proven enough for writers or parsers.
- `DEFERRED`: not needed yet or blocked on post-run/output fixtures.

## Local Evidence

Installed Z88Arion:

- Root: `C:\Z88ArionV3`
- Example project root: `C:\Z88ArionV3\docu\examples\project`
- Local copied fixtures: `z88_assets/examples/pre/`

Default local fixtures:

- `2_Querlenker_OC`
- `1_Balken_OC` (added after the first GUI/solver smoke because it is small
  enough for fast headless optimizer replay)
- `5_Winkelhalter_TOSS`
- `7_Balken_SKO`

## `z88control.txt`

Confidence: `OBSERVED`

Role: Aurora solver and topology optimization settings.

Observed blocks:

- `GLOBAL`
- `LMSOLVER`
- `TOSOLVER`
- `STRESS`

Observed `TOSOLVER` fields:

- `ICFLAG`
- `MAXIT`
- `EPS`
- `ALPHA`
- `OMEGA`
- `OPTMAXIT`
- `OPTALGORITHM`
- `OPTMETHOD`
- `OPTFILTERTYPE`
- `OPTFILTERVERS`
- `OPTRADIUSTYPE`
- `OPTWEIGHTFUNC`
- `OPTEPS`
- `OPTVREL`
- `OPTQPAR`
- `OPTPENALTY`
- `OPTRADIUSVALUE`
- `OPTOCLAGFACUP`
- `OPTOCLAGFACLOW`
- `OPTOCSTEPWIDTH`
- `OPTOCDAMPING`
- `OPTTOSSMAXIT`
- `OPTTOSSEPS`
- `OPTTOSSREFSTRESS`
- `OPTTOSSSTEPWIDTH`

Observed optimizer algorithm values:

- `OPTALGORITHM 1`: OC examples.
- `OPTALGORITHM 3`: TOSS examples.
- `OPTALGORITHM 4`: SKO examples.

Writer status: `DEFERRED`. Do not write `z88control.txt` until the pre/post
manual run audit confirms which settings Z88Arion mutates or requires.

## `z88setsactive.txt`

Confidence: `OBSERVED`

Role: compact active set descriptors for mesh rules, constraints, material
sets, loads, and fixed/non-design sets.

Observed line pattern:

```text
#<KIND> <ROLE> <numeric fields...> "<label>"
```

Observed kinds and roles:

- `MESH FREE_MESH`
- `NODES CONSTRAINT`
- `ELEMENTS MATERIAL`

Parser status: current parser extracts kind, role, label, raw line, and
remaining fields. Expanded semantics of the numeric fields remain `INFERRED`.

Writer status: `DEFERRED`.

## `z88sets.txt`

Confidence: `OBSERVED`

Role: expanded node/element set membership. Large file; do not dump into docs
or logs.

Current status:

- Inventory and preview only.
- Full parser is `DEFERRED` until required by writer/result work.

Bug risk:

- File can be large enough to make Markdown audits noisy. Audit tooling must
  record first line, line count, byte count, hash, and role only.

## `z88structure.txt`

Confidence: `OBSERVED`

Role: mesh structure. Observed examples begin with a numeric header.

Observed header example:

```text
3 17220 70040 51660 0
```

Observed header fields are currently recorded as positional values only:

- Field 1: likely dimension.
- Field 2: likely node count.
- Field 3: likely element count.
- Field 4: likely DOF count.
- Field 5: unknown flag.

Important correction from local evidence:

- The installed example headers observed so far do not include `#AURORA_V3`.

Writer status: `DEFERRED`.

Bug risk:

- Tet element type and node ordering are not confirmed for generated files.
  Native project writing must not assume a node ordering before fixture proof.

## `z88marks.txt`

Confidence: `OBSERVED`

Role: present in some TOSS/undercut examples. Likely related to manufacturing
or undercut constraints.

Current status:

- Inventory and preview only.
- Full parser and writer are `DEFERRED`.

## `project.z88`

Confidence: `OBSERVED`

Role: Aurora project descriptor present in some bundled examples.

Current status:

- Inventory and preview only.
- Full parser is `DEFERRED`.

## `z88.inp`

Confidence: `OBSERVED`

Role: imported FE/project input present in some bundled examples.

Current status:

- Inventory and preview only.
- Full parser is `DEFERRED`.

## Z88 Logs

Confidence: `OBSERVED`

Observed during headless probes:

- `Z88OC.log`
- `z88rofl.log`
- `z88r.log`
- `z88rtoss.log`

Observed copied-fixture probe behavior on `2_Querlenker_OC`:

- `Z88OC.exe`: writes `Z88OC.log` and exits with a crash-like Windows return
  code in the no-arg cwd probe.
- `z88rTOSS.exe`: writes `z88rtoss.log` and reports missing `Z88.DYN`.
- `z88r_sko.exe`: exits with a crash-like Windows return code and no observed
  project mutation in the no-arg cwd probe.
- `z88r_opt.exe`: writes `z88r.log` and exits nonzero.

Observed seeded-runtime TOSS behavior:

- Copying `C:\Z88ArionV3\win\bin\z88.dyn` into a copied fixture as `Z88.DYN`
  satisfies the first runtime-file check for `z88rTOSS.exe`.
- No-arg seeded `z88rTOSS.exe` prints usage guidance rather than running.
- `z88rTOSS.exe -t -siccg` and `z88rTOSS.exe -c -siccg` progress farther, then
  `z88rtoss.log` reports missing `Z88MANAGE.TXT`.

Current status:

- Stored under `z88_assets/outputs/headless_probe/` when possible.
- Root-level logs are ignored by Git.
- `Z88OC.log` is the primary OC optimizer log. In a successful
  `1_Balken_OC` SICCG run it reports: optimizer solved in 39 iterations and
  ended with `>>> Programm erfolgreich gelaufen!`.
- In a successful `2_Querlenker_OC` SICCG run it reports: optimizer solved in
  120 iterations and ended with `>>> Programm erfolgreich gelaufen!`.
- `z88rofl.log` records the linear solver handoff. On this machine the
  `-PARAO`/PARDISO path reaches `Start PARDISO` and then crashes with a signed
  Windows NTSTATUS return code from the parent process. The same generated
  projects run with `-SICCG`.

## `Z88.DYN`

Confidence: `OBSERVED`

Role: runtime/memory configuration read by solver binaries from the working
directory.

Observed installed source:

- `C:\Z88ArionV3\win\bin\z88.dyn`

Observed content includes:

- `DYNAMIC START`
- `Z88Arion V3.0`
- `LANGUAGE`
- `COMMON START`
- `MAXE`
- `MAXK`

Current status:

- Probe tooling can seed this file into copied fixtures with `--seed-runtime`.
- Do not treat it as a native project file generated by our writer.

## `Z88MANAGE.TXT`

Confidence: `OBSERVED`

Role: required by `z88rTOSS.exe` after runtime seeding when called with solver
argv such as `-t -siccg` or `-c -siccg`.

Current status:

- Not present in the captured pre fixtures.
- Not found in the installed bundled example project folders during the current
  audit.
- Exact schema is `DEFERRED` until a manual post-run or GUI-generated solver
  working directory reveals it.

## `z88ag2oi.exe`

Confidence: `OBSERVED`

Role: installed converter binary that appears to translate Z88Arion project
state into optimizer/solver input files.

Binary-string evidence:

- Contains command templates for `z88rTOSS.exe -T -PARAO`,
  `z88rTOSS.exe -C -PARAO`, `z88rTOSS.exe -IE -PARAO`,
  `z88rTOSS.exe -OTM -PARAO`, `z88rTOSS.exe -SIG -PARAO`, and
  `z88rTOSS.exe -TSKO -PARAO`.
- References `z88manage.txt`, `z88man.txt`, `z88i1.txt`, and
  `Z88Arion.ctrl`.

Copied-fixture probe evidence:

- No-arg calls print a usage error requesting language and console-output
  flags.
- Calls with `1 1 384` or `2 1 384` start the converter and then fail while
  writing `z88i1.txt`.

Current status:

- Not wired into the adapter.
- The converter likely requires GUI-generated intermediate files not present in
  the copied pre fixtures.
- Next evidence source should be a manual GUI-created post/working folder.

## `Z88Arion.pth`

Confidence: `OBSERVED`

Role: two-line path file consumed by `z88optopus.exe`.

Observed from GUI-generated OC runs:

```text
C:\Z88ArionV3\win\bin
<absolute project working directory>
```

Current status:

- Required for headless replay of a GUI-generated optimizer folder.
- If a generated project is copied, this file must be rewritten so line 2
  points to the copied folder. Otherwise `z88optopus.exe` continues to call
  `z88rofl.exe` against the original project path.

## `Z88Arion.fea`

Confidence: `OBSERVED`

Role: command template file for solver calls launched by `z88optopus.exe`.

Observed OC commands:

```text
z88rofl.exe -T -PARAO
z88rofl.exe -C -PARAO
z88rofl.exe -KEL -DUMMY
z88rofl.exe -U -PARAO
z88rofl.exe -IE -PARAO
z88rofl.exe -OTM -PARAO
```

Observed TOSS/SKO/CAO command templates are also present in the same file.

Current status:

- GUI generation defaults OC commands to `-PARAO`.
- Local execution with `-PARAO` crashes at the PARDISO solve on this machine.
- Replacing solver flags with `-SICCG` allowed `1_Balken_OC` to complete
  headlessly in 39 iterations.
- Replacing solver flags with `-SICCG` allowed `2_Querlenker_OC` to complete
  headlessly in 120 iterations.
- This execution patch is now also used by the OC voxel native writer generated
  by `z88_bridge/native_writer.py`.

## OC Output Folders

Confidence: `OBSERVED`

Observed in successful `1_Balken_OC` SICCG replay:

- `ConstitutiveLaw/`
- `DesignResponse/`
- `PhysicalDensity/`
- `StrainEnergy/`
- `YoungsModulus/`
- `tmp/`

Observed files:

- `DesignResponse/ComplianceNNN.txt`: per-element compliance/design response
  snapshots.
- `PhysicalDensity/PhysicalDensityNNN.txt`: per-element physical density
  snapshots.
- `StrainEnergy/StrainEnergyNNN.txt`: per-element strain energy snapshots.
- `YoungsModulus/YoungsModulus_IterationNNN.txt`: per-element Young's modulus
  snapshots.
- `tmp/OverallCompliance.txt`: scalar compliance history. Final observed value
  for the successful `1_Balken_OC` replay: approximately `2.2141998514`.
- `tmp/AktuellesVolumen.txt`: scalar current-volume history. Final observed
  value: approximately `418.50000343`.
- `tmp/Abbruchkriterium_SIMP.txt`: scalar convergence criterion history. Final
  observed value: approximately `8.7047E-04`.
- `tmp/Güte der 0-1-Verteilung.txt`: scalar 0/1 distribution quality history.
  Final observed value: approximately `2.4332E-02`.

Additional successful `2_Querlenker_OC` final observed values:

- `tmp/OverallCompliance.txt`: approximately `521.1895650750`.
- `tmp/AktuellesVolumen.txt`: approximately `2152001.618496718`.
- `tmp/Abbruchkriterium_SIMP.txt`: approximately `1.5516E-05`.
- `tmp/Güte der 0-1-Verteilung.txt`: approximately `9.9946E-03`.

Parser status: `OBSERVED`.

- `z88_bridge/results.py` parses these scalar histories.
- `scripts/z88_collect_native_results.py` writes `z88_native_results.json`.
- Snapshot folders are inventoried with file count, first/last iteration,
  byte size, and SHA-256.
- The final snapshot in each folder is summarized with row count, min, max,
  mean, min/max element IDs, zero count, and nonzero count. Full per-element
  arrays are not dumped into JSON yet.

## Solver Output Files

Confidence: `OBSERVED`

The first concrete successful output fixture is
`z88_assets/examples/post/1_Balken_OC`, generated by GUI setup plus headless
`z88optopus.exe` replay with `Z88Arion.fea` patched to `-SICCG`.

The second successful output fixture is `z88_assets/examples/post/2_Querlenker_OC`,
generated by the same GUI setup plus SICCG replay path.

Expected future parser requirements:

- Parse by explicit node/element IDs, not row position.
- Treat malformed rows as parse errors, not crashes.
- Stream large files line-by-line where possible.

## `Displacements/Displacements_final.txt`

Confidence: `OBSERVED`

Role: final Z88O2 nodal displacement output generated after optimization.

Observed generation command:

```text
z88rofl.exe -U -SICCG Displacements\Displacements_final.txt ConstitutiveLaw\z88matNNN.txt z88i1.txt z88i2.txt
```

Important runtime detail:

- `z88rofl.exe` can return `4294954951` / signed `-12345` while still writing
  the output file and printing `>>> Z88R >>> Programm erfolgreich gelaufen!`.
  Treat the success marker plus output file as authoritative for this command.

Observed header:

```text
Ausgabedatei Z88O2.TXT: Verschiebungen
Knoten         U(1)              U(2)              U(3)
```

Current parser status: `OBSERVED`.

- `z88_bridge/results.py` parses node count, components per node, maximum
  displacement magnitude, and the node where that maximum occurs.
- Full nodal vector export is deferred to avoid large JSON until the UI/report
  contract needs it.

Observed local summaries:

- `1_Balken_OC`: `11222` nodes, 3 components per node, max displacement about
  `0.0231349014` at node `91`.
- `2_Querlenker_OC`: `17220` nodes, 3 components per node, max displacement
  about `0.0767050791` at node `1004`.

## Native OC Voxel Project Writer

Confidence: `CONFIRMED` for the limited OC/H8 voxel scope.

Confirmed generation path:

```powershell
python scripts\z88_generate_native_project.py <config.json> --project-dir <project> --run-workflow --generate-stress
```

Confirmed scope:

- Input geometry is voxelized from STL into H8/hexahedral elements.
- Optimizer is OC only.
- Region selectors are explicit axis-aligned boxes.
- Supports and loads are written to `z88i2.txt`.
- Material uses `r_2.txt`, `z88mat.txt`, and per-element
  `ConstitutiveLaw/z88mat000.txt`.
- `z88int.txt` must contain both lines:

```text
1
1 <element-count> 2 2
```

This second line is required. Without it, `z88optopus.exe` writes invalid
iteration material files and the subsequent solver call can fail with a zero or
negative diagonal element.

Confirmed H8 node order:

```text
x-min/high-y/low-z
x-min/low-y/low-z
x-min/low-y/high-z
x-min/high-y/high-z
x-max/high-y/low-z
x-max/low-y/low-z
x-max/low-y/high-z
x-max/high-y/high-z
```

`Z88Arion.ctrl` is required by `z88optopus.exe`; omitting it caused a silent
optimizer crash before solver logs were written.

Current writer status:

- Implemented in `z88_bridge/native_writer.py`.
- Exposed as `scripts/z88_generate_native_project.py`.
- Local STL smoke wrote a 45-element native project, ran OC with SICCG,
  generated displacements, generated stress, and collected JSON summaries.
- Tetrahedral/native GUI project writing remains `DEFERRED`.

## Stress / Von Mises Outputs

Confidence: `CONFIRMED` for the generated OC/H8 voxel scope.

Current evidence:

- The successful OC fixtures contain empty `Stresses/`, `Stresses_ELE/`, and
  `Knotenspannungen/` folders before explicit stress probing.
- `z88rofl.exe -SIG -SICCG` is rejected as an invalid OC solver call.
- `z88rTOSS.exe -SIG -SICCG` accepts stress-style arguments and asks for:
  nodal-stress output path, material file, `z88i1.txt`, `z88i2.txt`,
  element-stress output path, and an energy output path.
- On the copied `1_Balken_OC` OC fixture, that `z88rTOSS.exe -SIG` probe
  crashed after creating an empty nodal-stress output.
- On the generated 45-element OC/H8 smoke project, this command completed and
  wrote non-empty nodal and element stress files:

```text
z88rTOSS.exe -SIG -SICCG Knotenspannungen\Knot_final.txt ConstitutiveLaw\z88mat1.txt z88i1.txt z88i2.txt Stresses_ELE\Stress_ele_final.txt tmp\ElementEnergy_final.txt
```

Important runtime detail:

- `z88rTOSS.exe` can return `4294954951` / signed `-12345` while printing
  `>>> Z88RTOSS >>> Programm erfolgreich gelaufen!` and writing output files.
  Treat the success marker plus non-empty output files as authoritative.
- The final argument is an output file for element energy/`uKu`; do not point it
  at `Displacements\Displacements_final.txt` or the displacement file will be
  overwritten.

Observed stress file format:

```text
<row-count>
<node-or-element-id> <scalar-stress-value>
...
```

Parser status: `OBSERVED`.

- `scripts/z88_generate_stress.py` runs the confirmed stress postprocess.
- `z88_bridge/results.py` parses counted nodal and element scalar stress files
  into `stress.nodal` and `stress.elemental` summaries.
- The command is confirmed for the generated OC/H8 writer path. It is not yet
  reliable on the larger copied GUI-generated OC fixtures, so those should keep
  stress generation optional.
