"""Parsers for observed native Z88Arion optimization outputs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any

from .assets import sha256_file


SCHEMA_VERSION = 2

OC_SCALAR_HISTORY_FILES = {
    "overall_compliance": Path("tmp") / "OverallCompliance.txt",
    "current_volume": Path("tmp") / "AktuellesVolumen.txt",
    "simp_convergence": Path("tmp") / "Abbruchkriterium_SIMP.txt",
    "zero_one_distribution_quality": Path("tmp") / "G\u00fcte der 0-1-Verteilung.txt",
}

OC_SNAPSHOT_FOLDERS = {
    "physical_density": "PhysicalDensity",
    "design_response": "DesignResponse",
    "strain_energy": "StrainEnergy",
    "youngs_modulus": "YoungsModulus",
}

ITERATION_RE = re.compile(r"(\d+)(?=\.txt$)", re.IGNORECASE)


@dataclass(frozen=True)
class ScalarHistory:
    name: str
    path: str
    values: tuple[float, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def final_value(self) -> float | None:
        return self.values[-1] if self.values else None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["count"] = self.count
        data["final_value"] = self.final_value
        return data


@dataclass(frozen=True)
class SnapshotFile:
    relative_path: str
    bytes: int
    sha256: str
    iteration: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScalarFieldSummary:
    path: str
    row_count: int
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    min_id: int | None
    max_id: int | None
    zero_count: int
    nonzero_count: int
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotInventory:
    name: str
    folder: str
    files: tuple[SnapshotFile, ...] = field(default_factory=tuple)
    final_summary: ScalarFieldSummary | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def first_iteration(self) -> int | None:
        iterations = [item.iteration for item in self.files if item.iteration is not None]
        return min(iterations) if iterations else None

    @property
    def last_iteration(self) -> int | None:
        iterations = [item.iteration for item in self.files if item.iteration is not None]
        return max(iterations) if iterations else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "folder": self.folder,
            "count": self.count,
            "first_iteration": self.first_iteration,
            "last_iteration": self.last_iteration,
            "warnings": list(self.warnings),
            "final_summary": self.final_summary.to_dict() if self.final_summary else None,
            "files": [item.to_dict() for item in self.files],
        }


@dataclass(frozen=True)
class DisplacementSummary:
    path: str
    node_count: int
    components_per_node: int | None
    max_magnitude: float | None
    max_node: int | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StressSummary:
    nodal: ScalarFieldSummary | None = None
    elemental: ScalarFieldSummary | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodal": self.nodal.to_dict() if self.nodal else None,
            "elemental": self.elemental.to_dict() if self.elemental else None,
            "warnings": list(self.warnings),
            "parse_errors": list(self.parse_errors),
        }


@dataclass(frozen=True)
class NativeResultSummary:
    schema_version: int
    project_dir: str
    status: str
    histories: dict[str, ScalarHistory] = field(default_factory=dict)
    snapshots: dict[str, SnapshotInventory] = field(default_factory=dict)
    displacement: DisplacementSummary | None = None
    stress: StressSummary | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_dir": self.project_dir,
            "status": self.status,
            "histories": {key: value.to_dict() for key, value in self.histories.items()},
            "snapshots": {key: value.to_dict() for key, value in self.snapshots.items()},
            "displacement": self.displacement.to_dict() if self.displacement else None,
            "stress": self.stress.to_dict() if self.stress else None,
            "warnings": list(self.warnings),
            "parse_errors": list(self.parse_errors),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def parse_scalar_history(path: str | Path, *, name: str | None = None) -> ScalarHistory:
    """Parse a one-value-per-line Z88 scalar history file."""
    path = Path(path)
    label = name or path.stem
    warnings: list[str] = []
    parse_errors: list[str] = []
    values: list[float] = []
    if not path.exists():
        warnings.append(f"missing scalar history file: {path}")
        return ScalarHistory(label, str(path), warnings=tuple(warnings))
    if path.is_dir():
        parse_errors.append(f"expected file but found directory: {path}")
        return ScalarHistory(label, str(path), parse_errors=tuple(parse_errors))

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip()
                if not text or text.startswith("#"):
                    continue
                try:
                    values.append(_parse_float(text))
                except ValueError:
                    parse_errors.append(f"{path}:{line_number}: invalid float {text!r}")
    except OSError as exc:
        parse_errors.append(f"could not read {path}: {exc}")

    if not values and not parse_errors:
        warnings.append(f"scalar history file is empty: {path}")
    return ScalarHistory(
        label,
        str(path),
        values=tuple(values),
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def inventory_snapshot_folder(
    project_dir: str | Path,
    folder_name: str,
    *,
    name: str | None = None,
) -> SnapshotInventory:
    """Inventory observed per-iteration output folders without parsing arrays."""
    project_dir = Path(project_dir)
    folder = project_dir / folder_name
    label = name or folder_name
    warnings: list[str] = []
    files: list[SnapshotFile] = []
    if not folder.exists():
        warnings.append(f"missing snapshot folder: {folder}")
        return SnapshotInventory(label, str(folder), warnings=tuple(warnings))
    if not folder.is_dir():
        warnings.append(f"snapshot path is not a folder: {folder}")
        return SnapshotInventory(label, str(folder), warnings=tuple(warnings))

    for path in sorted(item for item in folder.rglob("*") if item.is_file()):
        rel = path.relative_to(project_dir).as_posix()
        files.append(
            SnapshotFile(
                relative_path=rel,
                bytes=path.stat().st_size,
                sha256=sha256_file(path),
                iteration=_iteration_from_name(path.name),
            )
        )
    final_summary: ScalarFieldSummary | None = None
    if files:
        latest = max(files, key=lambda item: item.iteration if item.iteration is not None else -1)
        if label == "youngs_modulus":
            final_summary = parse_youngs_modulus_summary(project_dir / latest.relative_path)
        else:
            final_summary = parse_scalar_field_summary(project_dir / latest.relative_path)
    else:
        warnings.append(f"snapshot folder is empty: {folder}")
    if final_summary is not None:
        warnings.extend(final_summary.warnings)
    return SnapshotInventory(
        label,
        str(folder),
        files=tuple(files),
        final_summary=final_summary,
        warnings=tuple(warnings),
    )


def parse_scalar_field_summary(path: str | Path) -> ScalarFieldSummary:
    """Summarize an observed two-column element scalar file without retaining rows."""
    path = Path(path)
    warnings: list[str] = []
    parse_errors: list[str] = []
    row_count = 0
    zero_count = 0
    nonzero_count = 0
    total = 0.0
    min_value: float | None = None
    max_value: float | None = None
    min_id: int | None = None
    max_id: int | None = None
    if not path.exists():
        warnings.append(f"missing scalar field file: {path}")
        return ScalarFieldSummary(str(path), 0, None, None, None, None, None, 0, 0, warnings=tuple(warnings))
    if path.is_dir():
        parse_errors.append(f"expected scalar field file but found directory: {path}")
        return ScalarFieldSummary(str(path), 0, None, None, None, None, None, 0, 0, parse_errors=tuple(parse_errors))

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parts = raw_line.split()
                if len(parts) != 2 or not parts[0].isdigit():
                    continue
                try:
                    item_id = int(parts[0])
                    value = _parse_float(parts[1])
                except ValueError:
                    parse_errors.append(f"{path}:{line_number}: invalid scalar field row {raw_line.strip()!r}")
                    continue
                row_count += 1
                total += value
                if value == 0.0:
                    zero_count += 1
                else:
                    nonzero_count += 1
                if min_value is None or value < min_value:
                    min_value = value
                    min_id = item_id
                if max_value is None or value > max_value:
                    max_value = value
                    max_id = item_id
    except OSError as exc:
        parse_errors.append(f"could not read {path}: {exc}")

    if row_count == 0 and not parse_errors:
        warnings.append(f"scalar field file contains no data rows: {path}")
    mean_value = total / row_count if row_count else None
    return ScalarFieldSummary(
        str(path),
        row_count,
        min_value,
        max_value,
        mean_value,
        min_id,
        max_id,
        zero_count,
        nonzero_count,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def parse_youngs_modulus_summary(path: str | Path) -> ScalarFieldSummary:
    """Summarize OC/TOSS ID-value rows and SKO value-poisson rows for modulus snapshots."""
    path = Path(path)
    warnings: list[str] = []
    parse_errors: list[str] = []
    row_count = 0
    zero_count = 0
    nonzero_count = 0
    total = 0.0
    min_value: float | None = None
    max_value: float | None = None
    min_id: int | None = None
    max_id: int | None = None
    if not path.exists():
        warnings.append(f"missing YoungsModulus file: {path}")
        return ScalarFieldSummary(str(path), 0, None, None, None, None, None, 0, 0, warnings=tuple(warnings))
    if path.is_dir():
        parse_errors.append(f"expected YoungsModulus file but found directory: {path}")
        return ScalarFieldSummary(str(path), 0, None, None, None, None, None, 0, 0, parse_errors=tuple(parse_errors))

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parts = raw_line.split()
                if len(parts) != 2:
                    continue
                try:
                    first = _parse_float(parts[0])
                    second = _parse_float(parts[1])
                except ValueError:
                    parse_errors.append(f"{path}:{line_number}: invalid YoungsModulus row {raw_line.strip()!r}")
                    continue
                if parts[0].lstrip("+-").isdigit() and abs(second) > 1.0:
                    item_id = int(first)
                    value = second
                else:
                    item_id = row_count + 1
                    value = first
                row_count += 1
                total += value
                if value == 0.0:
                    zero_count += 1
                else:
                    nonzero_count += 1
                if min_value is None or value < min_value:
                    min_value = value
                    min_id = item_id
                if max_value is None or value > max_value:
                    max_value = value
                    max_id = item_id
    except OSError as exc:
        parse_errors.append(f"could not read {path}: {exc}")

    if row_count == 0 and not parse_errors:
        warnings.append(f"YoungsModulus file contains no data rows: {path}")
    mean_value = total / row_count if row_count else None
    return ScalarFieldSummary(
        str(path),
        row_count,
        min_value,
        max_value,
        mean_value,
        min_id,
        max_id,
        zero_count,
        nonzero_count,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def parse_counted_scalar_field_summary(path: str | Path) -> ScalarFieldSummary:
    """Parse Z88 scalar files that begin with an expected row count."""
    summary = parse_scalar_field_summary(path)
    path = Path(path)
    if not path.exists() or path.is_dir():
        return summary
    warnings = list(summary.warnings)
    parse_errors = list(summary.parse_errors)
    expected: int | None = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    expected = int(stripped.split()[0])
                except (ValueError, IndexError):
                    parse_errors.append(f"{path}: first non-empty line is not a row count")
                break
    except OSError as exc:
        parse_errors.append(f"could not read {path}: {exc}")
    if expected is not None and summary.row_count != expected:
        warnings.append(f"expected {expected} rows from header, parsed {summary.row_count}")
    return ScalarFieldSummary(
        path=summary.path,
        row_count=summary.row_count,
        min_value=summary.min_value,
        max_value=summary.max_value,
        mean_value=summary.mean_value,
        min_id=summary.min_id,
        max_id=summary.max_id,
        zero_count=summary.zero_count,
        nonzero_count=summary.nonzero_count,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def parse_displacement_summary(path: str | Path) -> DisplacementSummary:
    """Parse an observed Z88O2 displacement file into summary metrics."""
    path = Path(path)
    warnings: list[str] = []
    parse_errors: list[str] = []
    node_count = 0
    components_per_node: int | None = None
    max_magnitude: float | None = None
    max_node: int | None = None
    if not path.exists():
        warnings.append(f"missing displacement file: {path}")
        return DisplacementSummary(str(path), 0, None, None, None, warnings=tuple(warnings))
    if path.is_dir():
        parse_errors.append(f"expected displacement file but found directory: {path}")
        return DisplacementSummary(str(path), 0, None, None, None, parse_errors=tuple(parse_errors))

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parts = raw_line.split()
                if len(parts) < 2 or not parts[0].isdigit():
                    continue
                try:
                    node = int(parts[0])
                    values = tuple(_parse_float(item) for item in parts[1:])
                except ValueError:
                    parse_errors.append(f"{path}:{line_number}: invalid displacement row {raw_line.strip()!r}")
                    continue
                if components_per_node is None:
                    components_per_node = len(values)
                elif len(values) != components_per_node:
                    parse_errors.append(
                        f"{path}:{line_number}: expected {components_per_node} components, got {len(values)}"
                    )
                    continue
                magnitude = math.sqrt(sum(value * value for value in values))
                node_count += 1
                if max_magnitude is None or magnitude > max_magnitude:
                    max_magnitude = magnitude
                    max_node = node
    except OSError as exc:
        parse_errors.append(f"could not read {path}: {exc}")

    if node_count == 0 and not parse_errors:
        warnings.append(f"displacement file contains no node rows: {path}")
    return DisplacementSummary(
        str(path),
        node_count,
        components_per_node,
        max_magnitude,
        max_node,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def collect_native_results(project_dir: str | Path) -> NativeResultSummary:
    """Collect the currently confirmed subset of native Z88 optimization output."""
    project_dir = Path(project_dir).resolve()
    histories: dict[str, ScalarHistory] = {}
    snapshots: dict[str, SnapshotInventory] = {}
    warnings: list[str] = []
    parse_errors: list[str] = []

    for name, relative_path in OC_SCALAR_HISTORY_FILES.items():
        history = parse_scalar_history(project_dir / relative_path, name=name)
        histories[name] = history
        warnings.extend(history.warnings)
        parse_errors.extend(history.parse_errors)

    for name, folder_name in OC_SNAPSHOT_FOLDERS.items():
        inventory = inventory_snapshot_folder(project_dir, folder_name, name=name)
        snapshots[name] = inventory
        warnings.extend(inventory.warnings)
        if inventory.final_summary is not None:
            parse_errors.extend(inventory.final_summary.parse_errors)

    displacement = _collect_displacement(project_dir)
    if displacement is not None:
        warnings.extend(displacement.warnings)
        parse_errors.extend(displacement.parse_errors)
    stress = _collect_stress(project_dir)
    if stress is not None:
        warnings.extend(stress.warnings)
        parse_errors.extend(stress.parse_errors)

    status = _native_result_status(histories, snapshots, warnings, parse_errors, displacement, stress)
    return NativeResultSummary(
        schema_version=SCHEMA_VERSION,
        project_dir=str(project_dir),
        status=status,
        histories=histories,
        snapshots=snapshots,
        displacement=displacement,
        stress=stress,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def write_native_results(project_dir: str | Path, output_path: str | Path | None = None) -> Path:
    summary = collect_native_results(project_dir)
    output = Path(output_path) if output_path is not None else Path(project_dir) / "z88_native_results.json"
    summary.write_json(output)
    return output


def _parse_float(text: str) -> float:
    return float(text.replace("D", "E").replace("d", "E"))


def _iteration_from_name(name: str) -> int | None:
    match = ITERATION_RE.search(name)
    return int(match.group(1)) if match else None


def _native_result_status(
    histories: dict[str, ScalarHistory],
    snapshots: dict[str, SnapshotInventory],
    warnings: list[str],
    parse_errors: list[str],
    displacement: DisplacementSummary | None,
    stress: StressSummary | None,
) -> str:
    if parse_errors:
        return "parse_failed"
    has_values = any(history.values for history in histories.values())
    has_snapshots = any(inventory.files for inventory in snapshots.values())
    has_displacement = displacement is not None and displacement.node_count > 0
    has_stress = stress is not None and (
        (stress.nodal is not None and stress.nodal.row_count > 0)
        or (stress.elemental is not None and stress.elemental.row_count > 0)
    )
    if not has_values and not has_snapshots and not has_displacement and not has_stress:
        return "missing_outputs"
    if warnings:
        return "partial"
    return "collected"


def _collect_displacement(project_dir: Path) -> DisplacementSummary | None:
    folder = project_dir / "Displacements"
    if not folder.is_dir():
        return None
    candidates = sorted(path for path in folder.glob("*.txt") if path.is_file())
    if not candidates:
        return None
    return parse_displacement_summary(candidates[-1])


def _collect_stress(project_dir: Path) -> StressSummary | None:
    nodal_path = _latest_nonempty(project_dir / "Knotenspannungen")
    element_path = _latest_nonempty(project_dir / "Stresses_ELE")
    if nodal_path is None and element_path is None:
        return None
    warnings: list[str] = []
    parse_errors: list[str] = []
    nodal = parse_counted_scalar_field_summary(nodal_path) if nodal_path is not None else None
    elemental = parse_counted_scalar_field_summary(element_path) if element_path is not None else None
    if nodal is None:
        warnings.append(f"missing nodal stress output under {project_dir / 'Knotenspannungen'}")
    else:
        warnings.extend(nodal.warnings)
        parse_errors.extend(nodal.parse_errors)
    if elemental is None:
        warnings.append(f"missing element stress output under {project_dir / 'Stresses_ELE'}")
    else:
        warnings.extend(elemental.warnings)
        parse_errors.extend(elemental.parse_errors)
    return StressSummary(
        nodal=nodal,
        elemental=elemental,
        warnings=tuple(warnings),
        parse_errors=tuple(parse_errors),
    )


def _latest_nonempty(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    files = [path for path in folder.glob("*.txt") if path.is_file() and path.stat().st_size > 0]
    if not files:
        return None
    preferred = [path for path in files if "final" in path.stem.lower()]
    return sorted(preferred or files)[-1]
