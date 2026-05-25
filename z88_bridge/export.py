"""Export generated H8 topology density results to STL plus mesh QA."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import trimesh

from core.verify import mesh_quality_report


H8_FACE_NODE_POSITIONS = (
    (0, 1, 2, 3),  # x-min
    (4, 7, 6, 5),  # x-max
    (1, 5, 6, 2),  # y-min
    (0, 3, 7, 4),  # y-max
    (0, 4, 5, 1),  # z-min
    (3, 2, 6, 7),  # z-max
)
ITERATION_RE = re.compile(r"(\d+)(?=\.txt$)", re.IGNORECASE)


@dataclass(frozen=True)
class OptimizedStlExportResult:
    project_dir: str
    status: str
    optimized_stl: str | None
    mesh_quality_json: str | None
    density_file: str | None
    threshold: float
    selected_element_count: int
    total_element_count: int
    warnings: tuple[str, ...] = ()
    parse_errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def export_optimized_stl_from_generated_project(
    project_dir: str | Path,
    *,
    threshold: float | None = None,
    output_path: str | Path | None = None,
    mesh_quality_path: str | Path | None = None,
) -> OptimizedStlExportResult:
    """Export a thresholded H8 density field to `optimized.stl`.

    This is intentionally scoped to wrapper-generated OC/TOSS/SKO H8 projects.
    It does not attempt to export native Z88Arion tetrahedral geometry.
    """
    project_dir = Path(project_dir).resolve()
    threshold_value = _configured_iso_threshold(project_dir) if threshold is None else float(threshold)
    output = Path(output_path) if output_path is not None else project_dir / "optimized.stl"
    if not output.is_absolute():
        output = project_dir / output
    mesh_json = Path(mesh_quality_path) if mesh_quality_path is not None else project_dir / "mesh_quality.json"
    if not mesh_json.is_absolute():
        mesh_json = project_dir / mesh_json

    warnings: list[str] = []
    parse_errors: list[str] = []
    try:
        nodes, elements = parse_z88i1_h8(project_dir / "z88i1.txt")
    except Exception as exc:
        parse_errors.append(f"could not parse z88i1.txt: {exc}")
        return _result(project_dir, "parse_failed", None, None, None, threshold_value, 0, 0, warnings, parse_errors)

    density_file = _latest_density_file(project_dir)
    densities: dict[int, float] = {}
    if density_file is None:
        warnings.append("missing PhysicalDensity output; exporting all H8 elements")
    else:
        densities, density_errors = parse_scalar_field_values(density_file)
        parse_errors.extend(density_errors)
    if parse_errors:
        return _result(
            project_dir,
            "parse_failed",
            None,
            None,
            str(density_file) if density_file else None,
            threshold_value,
            0,
            len(elements),
            warnings,
            parse_errors,
        )

    selected_ids = [
        element_id
        for element_id in sorted(elements)
        if densities.get(element_id, 1.0) >= threshold_value
    ]
    if not selected_ids:
        warnings.append("density threshold selected no elements; STL export skipped")
        result = _result(
            project_dir,
            "empty_selection",
            None,
            None,
            str(density_file) if density_file else None,
            threshold_value,
            0,
            len(elements),
            warnings,
            parse_errors,
        )
        result.write_json(project_dir / "z88_optimized_stl_export.json")
        return result

    mesh = _surface_mesh_for_h8_selection(nodes, {element_id: elements[element_id] for element_id in selected_ids})
    output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output)
    quality = mesh_quality_report(output)
    mesh_json.write_text(json.dumps(asdict(quality), indent=2), encoding="utf-8")
    if not quality.watertight:
        warnings.append("exported optimized STL is not watertight")
    if quality.components != 1:
        warnings.append(f"exported optimized STL has {quality.components} components")
    if quality.degenerate_faces:
        warnings.append(f"exported optimized STL has {quality.degenerate_faces} degenerate faces")

    status = "exported" if not warnings else "exported_with_warnings"
    result = _result(
        project_dir,
        status,
        str(output),
        str(mesh_json),
        str(density_file) if density_file else None,
        threshold_value,
        len(selected_ids),
        len(elements),
        warnings,
        parse_errors,
    )
    result.write_json(project_dir / "z88_optimized_stl_export.json")
    return result


def parse_z88i1_h8(path: str | Path) -> tuple[dict[int, tuple[float, float, float]], dict[int, tuple[int, ...]]]:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        raise ValueError("empty z88i1.txt")
    header = lines[0].split()
    if len(header) < 3:
        raise ValueError("z88i1.txt header has too few fields")
    node_count = int(header[1])
    element_count = int(header[2])
    if len(lines) < 1 + node_count + element_count * 2:
        raise ValueError("z88i1.txt ended before expected node/element rows")

    nodes: dict[int, tuple[float, float, float]] = {}
    for raw in lines[1 : 1 + node_count]:
        parts = raw.split()
        if len(parts) < 5:
            raise ValueError(f"invalid node row: {raw!r}")
        nodes[int(parts[0])] = (float(parts[2]), float(parts[3]), float(parts[4]))

    elements: dict[int, tuple[int, ...]] = {}
    cursor = 1 + node_count
    for _ in range(element_count):
        meta = lines[cursor].split()
        node_row = lines[cursor + 1].split()
        cursor += 2
        if len(meta) < 2:
            raise ValueError("invalid element metadata row")
        element_id = int(meta[0])
        if len(node_row) != 8:
            raise ValueError(f"expected 8 H8 node ids for element {element_id}, got {len(node_row)}")
        elements[element_id] = tuple(int(item) for item in node_row)
    return nodes, elements


def parse_scalar_field_values(path: str | Path) -> tuple[dict[int, float], list[str]]:
    values: dict[int, float] = {}
    parse_errors: list[str] = []
    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            parts = raw.split()
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            try:
                values[int(parts[0])] = float(parts[1].replace("D", "E").replace("d", "E"))
            except ValueError:
                parse_errors.append(f"{path}:{line_number}: invalid scalar row {raw.strip()!r}")
    return values, parse_errors


def _surface_mesh_for_h8_selection(
    nodes: dict[int, tuple[float, float, float]],
    elements: dict[int, tuple[int, ...]],
) -> trimesh.Trimesh:
    coord_to_index: dict[tuple[float, float, float], int] = {}
    vertices: list[tuple[float, float, float]] = []
    boundary_faces: dict[tuple[tuple[float, float, float], ...], tuple[tuple[float, float, float], ...]] = {}

    def vertex_index(coord: tuple[float, float, float]) -> int:
        if coord not in coord_to_index:
            coord_to_index[coord] = len(vertices)
            vertices.append(coord)
        return coord_to_index[coord]

    for element_nodes in elements.values():
        coords = tuple(nodes[node_id] for node_id in element_nodes)
        for face_positions in H8_FACE_NODE_POSITIONS:
            face_coords = tuple(coords[index] for index in face_positions)
            key = tuple(sorted(face_coords))
            if key in boundary_faces:
                del boundary_faces[key]
            else:
                boundary_faces[key] = face_coords

    triangles: list[tuple[int, int, int]] = []
    for face_coords in boundary_faces.values():
        a, b, c, d = (vertex_index(coord) for coord in face_coords)
        triangles.append((a, b, c))
        triangles.append((a, c, d))
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(triangles), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _latest_density_file(project_dir: Path) -> Path | None:
    folder = project_dir / "PhysicalDensity"
    if not folder.is_dir():
        return None
    files = [path for path in folder.glob("*.txt") if path.is_file() and path.stat().st_size > 0]
    if not files:
        return None
    return max(files, key=lambda path: _iteration_from_name(path.name))


def _iteration_from_name(name: str) -> int:
    match = ITERATION_RE.search(name)
    return int(match.group(1)) if match else -1


def _configured_iso_threshold(project_dir: Path) -> float:
    config_path = project_dir / "config.json"
    if not config_path.is_file():
        return 0.5
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.5
    export = config.get("export")
    if isinstance(export, dict):
        value = export.get("iso_threshold")
        if isinstance(value, int | float):
            return float(value)
    return 0.5


def _result(
    project_dir: Path,
    status: str,
    optimized_stl: str | None,
    mesh_quality_json: str | None,
    density_file: str | None,
    threshold: float,
    selected_count: int,
    total_count: int,
    warnings: list[str],
    parse_errors: list[str],
) -> OptimizedStlExportResult:
    return OptimizedStlExportResult(
        project_dir=str(project_dir),
        status=status,
        optimized_stl=optimized_stl,
        mesh_quality_json=mesh_quality_json,
        density_file=density_file,
        threshold=threshold,
        selected_element_count=selected_count,
        total_element_count=total_count,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )
