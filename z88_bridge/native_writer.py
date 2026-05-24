"""Generate confirmed OC-native Z88 project folders from voxelized STL input."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

import numpy as np

from geometry.voxelize import VoxelGrid, voxelize_stl

from .adapter import discover_installation
from .assets import build_project_manifest
from .config import LoadCase, RegionSpec, SupportSpec, Z88RunConfig, write_config
from .project_files import summarize_project_files


DOF_INDEX = {"x": 1, "y": 2, "z": 3}
UNIT_LENGTH_M = {"m": 1.0, "cm": 1.0e-2, "mm": 1.0e-3, "in": 0.0254}
DEFAULT_SOLVER_FEA = """// Solver Aufrufe fuer OC Verfahren
z88rofl.exe -T -SICCG
z88rofl.exe -C -SICCG
z88rofl.exe -KEL -DUMMY
z88rofl.exe -U -SICCG
z88rofl.exe -IE -SICCG
z88rofl.exe -OTM -SICCG
// Solver Aufrufe fuer TOSS Verfahren
z88rTOSS.exe -T -SICCG
z88rTOSS.exe -C -SICCG
z88rTOSS.exe -IE -SICCG
z88rTOSS.exe -OTM -SICCG
z88rTOSS.exe -SIG -SICCG
z88rTOSS.exe -TSKO -SICCG
// Solver Aufrufe fuer CAO Verfahren
z88r_opt.exe -OPTU -SICCG
z88r_opt.exe -SIGN -SICCG
"""


@dataclass(frozen=True)
class NativeOCProjectWriteResult:
    project_dir: str
    node_count: int
    element_count: int
    boundary_condition_count: int
    fixed_element_count: int
    target_element_count: int
    minimum_fixed_volume_fraction: float
    solid_component_count: int
    material_modulus: float
    poisson_ratio: float
    units: str
    manifest_json: str
    summary_json: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


@dataclass(frozen=True)
class NativeMesh:
    nodes: tuple[tuple[int, float, float, float], ...]
    elements: tuple[tuple[int, tuple[int, ...], tuple[int, int, int]], ...]
    element_centers: dict[int, tuple[float, float, float]]


def write_native_oc_project(
    config: Z88RunConfig,
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
    max_elements: int = 200_000,
) -> NativeOCProjectWriteResult:
    """Voxelize `config.input_stl` and write a confirmed OC project folder.

    Scope is intentionally narrow: hexahedral voxel meshes, OC optimization,
    box-selected supports/loads/passive-solid regions, and SI-derived material
    scaling for the configured length unit. Tetrahedral/native GUI writers
    remain outside this confirmed contract.
    """
    config.validate()
    if config.optimizer.method.lower() != "oc":
        raise ValueError("native project generation is currently confirmed for optimizer.method='oc' only")
    grid = voxelize_stl(config.input_stl, config.voxel_pitch, max_elements=max_elements)
    return write_native_oc_project_from_grid(config, grid, project_dir, install_root=install_root)


def write_native_oc_project_from_grid(
    config: Z88RunConfig,
    grid: VoxelGrid,
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
) -> NativeOCProjectWriteResult:
    """Write a Z88 OC folder from an already voxelized grid."""
    config.validate(require_input_exists=False)
    if config.optimizer.method.lower() != "oc":
        raise ValueError("native project generation is currently confirmed for optimizer.method='oc' only")
    if grid.pitch <= 0:
        raise ValueError("voxel grid pitch must be positive")
    if not np.any(grid.solid):
        raise ValueError("voxel grid contains no solid elements")
    solid_component_count = _solid_component_count(grid.solid)
    if solid_component_count != 1:
        raise ValueError(
            f"voxel grid contains {solid_component_count} disconnected solid components; "
            "repair the STL, increase voxel_pitch, or split the run into one connected part"
        )
    if not config.supports:
        raise ValueError("at least one support is required for native project generation")
    if not config.loads:
        raise ValueError("at least one load is required for native project generation")

    installation = discover_installation(install_root)
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    mesh = build_native_mesh(grid)
    node_ids_by_region = _collect_node_region_maps(config.supports, config.loads, mesh.nodes)
    boundary_rows = _build_boundary_rows(config.supports, config.loads, node_ids_by_region)
    fixed_element_ids = _fixed_element_ids(config, mesh)
    target_element_count, minimum_fixed_volume_fraction = _validate_volume_feasibility(
        config,
        len(mesh.elements),
        len(fixed_element_ids),
    )
    material_modulus = _young_modulus_for_units(config)

    _write_project_files(
        config=config,
        project_dir=project_dir,
        install_bin_dir=installation.bin_dir,
        mesh=mesh,
        boundary_rows=boundary_rows,
        fixed_element_ids=fixed_element_ids,
        material_modulus=material_modulus,
    )

    write_config(config, project_dir / "config.json")
    manifest_path = project_dir / "z88_native_project_manifest.json"
    summary_path = project_dir / "z88_native_project_summary.json"
    manifest = build_project_manifest(project_dir)
    summary = summarize_project_files(project_dir)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    warnings = _project_warnings(config, fixed_element_ids)
    result = NativeOCProjectWriteResult(
        project_dir=str(project_dir),
        node_count=len(mesh.nodes),
        element_count=len(mesh.elements),
        boundary_condition_count=len(boundary_rows),
        fixed_element_count=len(fixed_element_ids),
        target_element_count=target_element_count,
        minimum_fixed_volume_fraction=minimum_fixed_volume_fraction,
        solid_component_count=solid_component_count,
        material_modulus=material_modulus,
        poisson_ratio=config.material.poisson_ratio,
        units=config.units,
        manifest_json=str(manifest_path),
        summary_json=str(summary_path),
        warnings=tuple(warnings),
    )
    result.write_json(project_dir / "z88_native_project_write.json")
    return result


def build_native_mesh(grid: VoxelGrid) -> NativeMesh:
    """Build Z88 H8 connectivity for occupied voxels.

    The H8 node order follows the locally confirmed `1_Balken_OC` order:
    x-min face with high-y to low-y around z, then x-max face in the same
    order. Using this order is what made the direct `z88rofl -U` smoke pass.
    """
    node_ids: dict[tuple[int, int, int], int] = {}
    node_rows: list[tuple[int, float, float, float]] = []

    def node_id(ix: int, iy: int, iz: int) -> int:
        key = (ix, iy, iz)
        if key in node_ids:
            return node_ids[key]
        ident = len(node_ids) + 1
        x = float(grid.origin[0] + ix * grid.pitch)
        y = float(grid.origin[1] + iy * grid.pitch)
        z = float(grid.origin[2] + iz * grid.pitch)
        node_ids[key] = ident
        node_rows.append((ident, x, y, z))
        return ident

    elements: list[tuple[int, tuple[int, ...], tuple[int, int, int]]] = []
    centers: dict[int, tuple[float, float, float]] = {}
    for ix in range(grid.nelx):
        for iy in range(grid.nely):
            for iz in range(grid.nelz):
                if not bool(grid.solid[ix, iy, iz]):
                    continue
                connectivity = (
                    node_id(ix, iy + 1, iz),
                    node_id(ix, iy, iz),
                    node_id(ix, iy, iz + 1),
                    node_id(ix, iy + 1, iz + 1),
                    node_id(ix + 1, iy + 1, iz),
                    node_id(ix + 1, iy, iz),
                    node_id(ix + 1, iy, iz + 1),
                    node_id(ix + 1, iy + 1, iz + 1),
                )
                element_id = len(elements) + 1
                elements.append((element_id, connectivity, (ix, iy, iz)))
                centers[element_id] = (
                    float(grid.origin[0] + (ix + 0.5) * grid.pitch),
                    float(grid.origin[1] + (iy + 0.5) * grid.pitch),
                    float(grid.origin[2] + (iz + 0.5) * grid.pitch),
                )

    return NativeMesh(tuple(sorted(node_rows)), tuple(elements), centers)


def _write_project_files(
    *,
    config: Z88RunConfig,
    project_dir: Path,
    install_bin_dir: Path,
    mesh: NativeMesh,
    boundary_rows: list[tuple[int, int, int, float]],
    fixed_element_ids: set[int],
    material_modulus: float,
) -> None:
    element_count = len(mesh.elements)
    node_count = len(mesh.nodes)
    dof_count = node_count * 3

    _ensure_output_dirs(project_dir)
    _write_z88i1(project_dir / "z88i1.txt", mesh, node_count, element_count, dof_count)
    shutil.copy2(project_dir / "z88i1.txt", project_dir / "z88structure.txt")
    _write_z88i2(project_dir / "z88i2.txt", boundary_rows)
    _write_material_files(project_dir, element_count, material_modulus, config.material.poisson_ratio)
    _write_z88control(project_dir / "z88control.txt", config)
    _write_z88arion_ctrl(project_dir / "Z88Arion.ctrl", config)
    _write_runtime_files(project_dir, node_count, element_count, dof_count, len(boundary_rows))
    _write_sets(project_dir, config, element_count, fixed_element_ids)
    (project_dir / "Z88Arion.pth").write_text(
        f"{install_bin_dir.resolve()}\n{project_dir.resolve()}\n",
        encoding="utf-8",
    )
    (project_dir / "Z88Arion.fea").write_text(DEFAULT_SOLVER_FEA, encoding="utf-8")


def _write_z88i1(path: Path, mesh: NativeMesh, node_count: int, element_count: int, dof_count: int) -> None:
    lines = [f"3 {node_count} {element_count} {dof_count} 0 "]
    for node_id, x, y, z in mesh.nodes:
        lines.append(f"{node_id:10d}{3:11d} {_fmt_e12(x)} {_fmt_e12(y)} {_fmt_e12(z)} ")
    for element_id, connectivity, _index in mesh.elements:
        lines.append(f"{element_id} 1 ")
        lines.append("".join(f"{node:10d}" for node in connectivity) + " ")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_z88i2(path: Path, boundary_rows: list[tuple[int, int, int, float]]) -> None:
    lines = [str(len(boundary_rows))]
    for node_id, dof, flag, value in boundary_rows:
        lines.append(f"{node_id} {dof} {flag}  {value:+.7E} ")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_material_files(project_dir: Path, element_count: int, young_modulus: float, poisson_ratio: float) -> None:
    (project_dir / "z88mat.txt").write_text(f"1\n1 {element_count} r_2.txt\n", encoding="utf-8")
    (project_dir / "r_2.txt").write_text(f"{young_modulus:.6f} {poisson_ratio:.6f} \n", encoding="utf-8")
    (project_dir / "z88elp.txt").write_text(
        f"1\n1 {element_count} 0 0 0 0 0 0 0\n",
        encoding="utf-8",
    )
    (project_dir / "z88int.txt").write_text(
        f"1\n1 {element_count} 2 2 \n",
        encoding="utf-8",
    )
    material_lines = [
        f"{element_id:2d} {element_id} 2 {young_modulus:+.25E} {poisson_ratio:+.25E}"
        for element_id in range(1, element_count + 1)
    ]
    (project_dir / "ConstitutiveLaw" / "z88mat000.txt").write_text(
        "\n".join(material_lines) + "\n",
        encoding="utf-8",
    )


def _write_z88control(path: Path, config: Z88RunConfig) -> None:
    volume_percent = config.optimizer.volume_fraction * 100.0
    lines = f"""DYNAMIC START
*-------------------------------------------------------------------------------
Z88Arion V3.0
-------------------------------------------------------------------------------*

GLOBAL START
   SIMCASE         384
   ICORE           2
GLOBAL END

LMSOLVER START
   ICFLAG          2
   SOLVER_SPEEDUP  -8
   MAXIT           10000
   EPS             1.000000E-006
   ALPHA           1.000000E-004
   OMEGA           1.20
LMSOLVER END

TOSOLVER START
   ICFLAG                       4
   MAXIT                        10000
   EPS                          1.000000E-008
   ALPHA                        1.000000E-004
   OMEGA                        1.00
   OPTMAXIT                     {config.optimizer.max_iterations}
   OPTALGORITHM                 1
   OPTMETHOD                    1
   OPTFILTERTYPE                1
   OPTFILTERVERS                1
   OPTRADIUSTYPE                2
   OPTWEIGHTFUNC                1
   OPTEPS                       {config.optimizer.convergence_tolerance:.6E}
   OPTVREL                      {volume_percent:.6E}
   OPTQPAR                      1.000000E+001
   OPTPENALTY                   3.000000E+000
   OPTRADIUSVALUE               1.000000E+000
   OPTOCLAGFACUP                1.000000E+006
   OPTOCLAGFACLOW               0.000000E+000
   OPTOCSTEPWIDTH               3.000000E-001
   OPTOCDAMPING                 5.000000E-001
   OPTTOSSMAXIT                 100
   OPTTOSSEPS                   1.000000E-006
   OPTTOSSREFSTRESS             2.000000E+001
   OPTTOSSSTEPWIDTH             2.000000E+000
   OPTSMOOTHINGLAST             1
   OPTSMOOTHINGITERATIONS       {config.export.smoothing_iterations}
   OPTSMOOTHINGDISPLAYTHRESHOLD {config.export.iso_threshold:.6E}
   OPTOPENAURORA                0
   OPTMINST                     0
   OPTENTRATE                   0.000000E+000
   OPTENTX                      0.000000E+000
   OPTENTY                      1.000000E+000
   OPTENTZ                      0.000000E+000
   OPTENTWIN                    1.000000E+001
   OPTENTTOLW                   3.000000E+001
   OPTENTTOLS                   1.000000E-010
TOSOLVER END

STRESS START
   KDFLAG          0
   ISFLAG          1
STRESS END
DYNAMIC END
"""
    path.write_text(lines, encoding="utf-8")


def _write_z88arion_ctrl(path: Path, config: Z88RunConfig) -> None:
    volume_percent = config.optimizer.volume_fraction * 100.0
    lines = f"""XXXXXXXXXXXXXXXX                                        XXXXXXXXXXXXXXXX
 XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
  XX                                                                XX
   X            Steuerparameter fuer Optimierungsprogramm            X
   X                     Z88Arion Version 2.0                       X
  XX                                                                XX
 XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXX                                         XXXXXXXXXXXXXXX

------------------------------------------------------------------------
 allgemeine Programmparameter                 common program parameters
------------------------------------------------------------------------
 PARAMETER COMMON START
   Programmsprache                          = Language     :GERMAN
   LogLevel                                 = LogLvl       :INFO
   Prozesslog Schrittweite (DEBUG)          = Progress     :10 %
 PARAMETER COMMON END

------------------------------------------------------------------------
 Topologieoptimierung                             topology optimization
------------------------------------------------------------------------
 PARAMETER OPT START
   Optimierungsmethode                      = OptMethod    :SIMP
   Art des Abbruchkriteriums                = OptEpsTyp    :Crel
   Abbruchkriterium (Wert)                  = OptEps       : {config.optimizer.convergence_tolerance:+.7E}
   Maximale Anzahl Iterationen              = OptMaxIt     :{config.optimizer.max_iterations}
   Optimierungsalgorithmus                  = OptAlgorithm :OC
   Enthinterschneidungsstufe                = OptMinSt     :0
   Enthinterschneidungsrate                 = OptEntRate   :0.000000E+00
   Entfromungsrichtung x                    = OptEntX      :0.000000E+00
   Entfromungsrichtung y                    = OptEntY      :1.000000E+00
   Entfromungsrichtung z                    = OptEntZ      :0.000000E+00
   Entfromungswinkel                        = OptEntWin    :1.000000E+01
   Entfromungstoleranzwinkel                = OptEntTolW   :3.000000E+01
   Entfromungstoleranzstrecke               = OptEntTolS   :1.000000E-10
 PARAMETER OPT END

------------------------------------------------------------------------
 SIMP                    Solid Isotropic Material with Penalization
 RAMP                    Rational Approximation of Material Properties
------------------------------------------------------------------------
 PARAMETER OPT_ANSATZ START
   relatives Zielvolumen                    = V[rel]       :{volume_percent:.6f}%
   Strafparameter_SIMP                      = penalty      :3
   Parameter_RAMP                           = qpar         :1
   Art der Filterung                        = FilterType   :SENS
   Variante des ausgewaehlten Filters       = FilterVers   :1
   Filterparameter Radius (Typ)             = r[typ]       :AVR
   Filterparameter Radius (Wert)            = r[min]       :1
   Gewichtungsfunktion                      = h[ei]        :LINEAR
 PARAMETER OPT_ANSATZ END

------------------------------------------------------------------------
 Optimalitaetskriterium                             optimality criterion
------------------------------------------------------------------------
 PARAMETER OC START
   Untergrenze Lagrangefaktor               = L[min]       : +0.0000000E+00
   Obergrenze Lagrangefaktor                = L[max]       : +1.0000000E+06
   Schrittweite Bisektion                   = alpha        : +3.0000000E-01
   Daempfungsfaktor                         = damp         : +5.0000000E-01
 PARAMETER OC END

------------------------------------------------------------------------
 SKO                                                   soft kill option
------------------------------------------------------------------------
 PARAMETER SKO START
   Referenzspannung                         = SigmaRSKO    : +2.0000000E+01
   Schrittweite fuer neue Temperatur        = alpha        : +2.0000000E+00
   Darstellungsgrenze                       = ShowEps      :0.001
   Epsilon zum Abbruch durch Konvergenz     = EpsAbbruch   : +1.0000000E-06
   Minimale Temperatur                      = Tmin         :0.001
 PARAMETER SKO END
"""
    path.write_text(lines, encoding="utf-8")


def _write_runtime_files(
    project_dir: Path,
    node_count: int,
    element_count: int,
    dof_count: int,
    boundary_condition_count: int,
) -> None:
    (project_dir / "z88.dyn").write_text(
        """DYNAMIC START
Z88Arion V3.0
LANGUAGE
GERMAN
QUIET
COMMON START
  MAXE            1000000
  MAXK            1000000
COMMON END
DYNAMIC END
""",
        encoding="utf-8",
    )
    (project_dir / "z88manage.txt").write_text(
        """DYNAMIC START
---------------------------------------------------------------------------
Z88R
---------------------------------------------------------------------------
GLOBAL START
   NEG                 1
   ICORE                2
GLOBAL END
SOLVER START
   MAXIT                10000
   EPS                   +1.0000000E-06
   RALPHA                +1.0000000E-04
   ROMEGA                +1.2000000E+00
SOLVER END
STRESS START
   NINTO                3
   KSFLAG               0
   ISFLAG               1
STRESS END
DYNAMIC END
""",
        encoding="utf-8",
    )
    maxgs = max(1_000_000, element_count * 256)
    maxkoi = max(1_000_000, element_count * 64)
    (project_dir / "z88rofl.dyn").write_text(
        f"""DYNAMIC START
---------------------------------
* Z88R.DYN build by z88_bridge
---------------------------------
SPARSE solvers were selected
---------------------------------
* Language for Z88R
---------------------------------
GERMAN
---------------------------------
* Entries for Z88R
---------------------------------
COMMON START
  MAXGS   {maxgs}
  MAXIEZ  {maxgs}
  MAXKOI  {maxkoi}
  MAXK    {node_count + 100}
  MAXE    {element_count + 100}
  MAXNFG  {dof_count + 100}
  MAXNEG  {element_count + 100}
  MAXRBD  {boundary_condition_count + 100}
  MAXPR   1000
  MAXGP   1000
COMMON END
DYNAMIC END
""",
        encoding="utf-8",
    )


def _write_sets(
    project_dir: Path,
    config: Z88RunConfig,
    element_count: int,
    fixed_element_ids: set[int],
) -> None:
    active_lines = [
        "#ELEMENTS MATERIAL 1 1 1 2 1 \"material\"",
    ]
    if fixed_element_ids:
        active_lines.append('#ELEMENTS FIXSET 1 2 2 384 1 "fixed_topology"')
    (project_dir / "z88setsactive.txt").write_text(
        "\n".join([str(len(active_lines)), *active_lines]) + "\n",
        encoding="utf-8",
    )

    set_lines = [str(1 + (1 if fixed_element_ids else 0)), f'#ELEMENTS MATERIAL 1 {element_count} "material"']
    set_lines.extend(_format_id_lines(range(1, element_count + 1)))
    if fixed_element_ids:
        fixed_sorted = sorted(fixed_element_ids)
        set_lines.append(f'#ELEMENTS FIXSET 2 {len(fixed_sorted)} "fixed_topology"')
        set_lines.extend(_format_id_lines(fixed_sorted))
    (project_dir / "z88sets.txt").write_text("\n".join(set_lines) + "\n", encoding="utf-8")

    fixed_lines = [str(len(fixed_element_ids))]
    fixed_lines.extend(f"{element_id}  +1.0000000E+00 " for element_id in sorted(fixed_element_ids))
    (project_dir / "FixSets.txt").write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")


def _ensure_output_dirs(project_dir: Path) -> None:
    for dirname in (
        "ConstitutiveLaw",
        "ConstitutiveLaw_SKO",
        "DesignResponse",
        "PhysicalDensity",
        "StrainEnergy",
        "YoungsModulus",
        "tmp",
        "Displacements",
        "Output",
        "Stresses",
        "Stresses_ELE",
        "Knotenspannungen",
    ):
        (project_dir / dirname).mkdir(parents=True, exist_ok=True)
    (project_dir / "z88i5.txt").write_text("0\n", encoding="utf-8")


def _collect_node_region_maps(
    supports: tuple[SupportSpec, ...],
    loads: tuple[LoadCase, ...],
    nodes: tuple[tuple[int, float, float, float], ...],
) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    for support in supports:
        node_ids = _node_ids_in_region(nodes, support.region)
        if not node_ids:
            raise ValueError(f"support region {support.name!r} selected no mesh nodes")
        result[f"support:{support.name}"] = node_ids
    for load in loads:
        node_ids = _node_ids_in_region(nodes, load.region)
        if not node_ids:
            raise ValueError(f"load region {load.name!r} selected no mesh nodes")
        result[f"load:{load.name}"] = node_ids
    return result


def _build_boundary_rows(
    supports: tuple[SupportSpec, ...],
    loads: tuple[LoadCase, ...],
    node_ids_by_region: dict[str, tuple[int, ...]],
) -> list[tuple[int, int, int, float]]:
    rows: list[tuple[int, int, int, float]] = []
    seen_constraints: set[tuple[int, int]] = set()
    for support in supports:
        node_ids = node_ids_by_region[f"support:{support.name}"]
        for node_id in node_ids:
            for dof_name in support.constrained_dofs:
                dof = DOF_INDEX[dof_name.lower()]
                key = (node_id, dof)
                if key in seen_constraints:
                    continue
                rows.append((node_id, dof, 2, 0.0))
                seen_constraints.add(key)
    for load in loads:
        node_ids = node_ids_by_region[f"load:{load.name}"]
        for component_index, value in enumerate(load.force, start=1):
            weighted = float(value) * load.weight
            if weighted == 0.0:
                continue
            per_node = weighted / len(node_ids)
            for node_id in node_ids:
                rows.append((node_id, component_index, 1, per_node))
    if not rows:
        raise ValueError("no boundary condition rows were generated")
    return rows


def _fixed_element_ids(config: Z88RunConfig, mesh: NativeMesh) -> set[int]:
    fixed: set[int] = set()
    node_lookup = {node_id: (x, y, z) for node_id, x, y, z in mesh.nodes}
    for region in config.passive_solid:
        for element_id, center in mesh.element_centers.items():
            if _point_in_region(center, region):
                fixed.add(element_id)
    boundary_regions = [support.region for support in config.supports]
    boundary_regions.extend(load.region for load in config.loads)
    for region in boundary_regions:
        for element_id, connectivity, _index in mesh.elements:
            if element_id in fixed:
                continue
            if any(_point_in_region(node_lookup[node_id], region) for node_id in connectivity):
                fixed.add(element_id)
    return fixed


def _solid_component_count(solid: np.ndarray) -> int:
    occupied = {tuple(int(value) for value in index) for index in np.argwhere(solid)}
    components = 0
    while occupied:
        components += 1
        stack = [occupied.pop()]
        while stack:
            ix, iy, iz = stack.pop()
            for neighbor in (
                (ix - 1, iy, iz),
                (ix + 1, iy, iz),
                (ix, iy - 1, iz),
                (ix, iy + 1, iz),
                (ix, iy, iz - 1),
                (ix, iy, iz + 1),
            ):
                if neighbor in occupied:
                    occupied.remove(neighbor)
                    stack.append(neighbor)
    return components


def _validate_volume_feasibility(
    config: Z88RunConfig,
    element_count: int,
    fixed_element_count: int,
) -> tuple[int, float]:
    target_element_count = int(np.ceil(config.optimizer.volume_fraction * element_count))
    minimum_fixed_volume_fraction = fixed_element_count / element_count
    if fixed_element_count > target_element_count:
        raise ValueError(
            "optimizer.volume_fraction is below the mandatory fixed/passive volume: "
            f"target keeps about {target_element_count}/{element_count} elements, "
            f"but supports/loads/passive-solid regions require {fixed_element_count}. "
            f"Use volume_fraction >= {minimum_fixed_volume_fraction:.6f}, reduce passive regions, "
            "or increase voxel_pitch."
        )
    return target_element_count, minimum_fixed_volume_fraction


def _node_ids_in_region(
    nodes: tuple[tuple[int, float, float, float], ...],
    region: RegionSpec,
) -> tuple[int, ...]:
    return tuple(node_id for node_id, x, y, z in nodes if _point_in_region((x, y, z), region))


def _point_in_region(point: tuple[float, float, float], region: RegionSpec) -> bool:
    selector = region.selector
    if selector.get("type") != "box":
        raise ValueError(f"unsupported region selector for {region.name!r}: {selector!r}")
    try:
        lower = tuple(float(value) for value in selector["min"])
        upper = tuple(float(value) for value in selector["max"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid box selector for {region.name!r}: {selector!r}") from exc
    if len(lower) != 3 or len(upper) != 3:
        raise ValueError(f"box selector for {region.name!r} must have three min/max values")
    lo = tuple(min(a, b) for a, b in zip(lower, upper))
    hi = tuple(max(a, b) for a, b in zip(lower, upper))
    tol = 1.0e-9
    return all(lo[index] - tol <= point[index] <= hi[index] + tol for index in range(3))


def _young_modulus_for_units(config: Z88RunConfig) -> float:
    factor = UNIT_LENGTH_M[config.units] ** 2
    return config.material.young_modulus * factor


def _project_warnings(config: Z88RunConfig, fixed_element_ids: set[int]) -> list[str]:
    warnings: list[str] = []
    if config.units != "mm":
        warnings.append(
            f"native writer scaled Young's modulus for {config.units}; verify force/length unit consistency"
        )
    if not fixed_element_ids:
        warnings.append("no fixed/passive elements were generated; low volume fractions can disconnect load/support regions")
    if config.optimizer.volume_fraction < 0.2:
        warnings.append("very low volume fractions can produce singular Z88 solves without more passive-solid regions")
    fixed_count = len(fixed_element_ids)
    if fixed_count:
        warnings.append(
            "supports, loads, and passive-solid regions are written as fixed topology elements; "
            "keep volume_fraction above the reported minimum_fixed_volume_fraction"
        )
    return warnings


def _fmt_e12(value: float) -> str:
    return f"{value:+.12E}"


def _format_id_lines(ids: Iterable[int], *, per_line: int = 10) -> list[str]:
    rows: list[str] = []
    chunk: list[int] = []
    for item in ids:
        chunk.append(int(item))
        if len(chunk) == per_line:
            rows.append("".join(f"{value:10d}" for value in chunk))
            chunk = []
    if chunk:
        rows.append("".join(f"{value:10d}" for value in chunk))
    return rows
