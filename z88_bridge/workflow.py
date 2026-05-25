"""Workflow orchestration for confirmed Z88Arion generated-project paths."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .export import OptimizedStlExportResult, export_optimized_stl_from_generated_project
from .headless import GeneratedOptimizerRunResult, run_generated_optimizer_project
from .postprocess import (
    Z88PostprocessRunResult,
    Z88StressPostprocessRunResult,
    run_displacement_postprocess,
    run_stress_postprocess,
)
from .results import NativeResultSummary, collect_native_results


@dataclass(frozen=True)
class GeneratedOCWorkflowResult:
    project_dir: str
    status: str
    optimizer: GeneratedOptimizerRunResult | None
    displacement: Z88PostprocessRunResult | None
    stress: Z88StressPostprocessRunResult | None
    optimized_export: OptimizedStlExportResult | None
    native_results: NativeResultSummary
    native_results_json: str
    messages: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "status": self.status,
            "optimizer": self.optimizer.to_dict() if self.optimizer else None,
            "displacement": self.displacement.to_dict() if self.displacement else None,
            "stress": self.stress.to_dict() if self.stress else None,
            "optimized_export": self.optimized_export.to_dict() if self.optimized_export else None,
            "native_results": self.native_results.to_dict(),
            "native_results_json": self.native_results_json,
            "messages": list(self.messages),
        }

    def compact_dict(self) -> dict[str, Any]:
        native = self.native_results.to_dict()
        histories = {
            name: {
                "count": history["count"],
                "final_value": history["final_value"],
            }
            for name, history in native["histories"].items()
        }
        snapshots = {
            name: {
                "count": snapshot["count"],
                "first_iteration": snapshot["first_iteration"],
                "last_iteration": snapshot["last_iteration"],
                "final_summary": _compact_field_summary(snapshot["final_summary"]),
            }
            for name, snapshot in native["snapshots"].items()
        }
        return {
            "project_dir": self.project_dir,
            "status": self.status,
            "optimizer_status": self.optimizer.status if self.optimizer else None,
            "displacement_status": self.displacement.status if self.displacement else None,
            "stress_status": self.stress.status if self.stress else None,
            "native_results_status": self.native_results.status,
            "histories": histories,
            "snapshots": snapshots,
            "displacement_summary": native["displacement"],
            "stress_summary": native["stress"],
            "optimized_export": self.optimized_export.to_dict() if self.optimized_export else None,
            "native_results_json": self.native_results_json,
            "messages": list(self.messages),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def run_generated_oc_workflow(
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
    solver: str = "siccg",
    optimizer_timeout_s: float = 900.0,
    displacement_timeout_s: float = 300.0,
    stress_timeout_s: float = 300.0,
    run_optimizer: bool = True,
    generate_displacements: bool = True,
    generate_stress: bool = False,
    export_optimized_stl: bool = True,
) -> GeneratedOCWorkflowResult:
    """Backward-compatible alias for the generated topology workflow."""
    return run_generated_topology_workflow(
        project_dir,
        install_root=install_root,
        solver=solver,
        optimizer_timeout_s=optimizer_timeout_s,
        displacement_timeout_s=displacement_timeout_s,
        stress_timeout_s=stress_timeout_s,
        run_optimizer=run_optimizer,
        generate_displacements=generate_displacements,
        generate_stress=generate_stress,
        export_optimized_stl=export_optimized_stl,
    )


def run_generated_topology_workflow(
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
    solver: str = "siccg",
    optimizer_timeout_s: float = 900.0,
    displacement_timeout_s: float = 300.0,
    stress_timeout_s: float = 300.0,
    run_optimizer: bool = True,
    generate_displacements: bool = True,
    generate_stress: bool = False,
    export_optimized_stl: bool = True,
) -> GeneratedOCWorkflowResult:
    """Run the confirmed generated OC/TOSS/SKO H8 topology workflow end to end."""
    project_dir = Path(project_dir).resolve()
    messages: list[str] = []
    optimizer: GeneratedOptimizerRunResult | None = None
    displacement: Z88PostprocessRunResult | None = None
    stress: Z88StressPostprocessRunResult | None = None
    optimized_export: OptimizedStlExportResult | None = None

    if run_optimizer:
        optimizer = run_generated_optimizer_project(
            project_dir,
            install_root=install_root,
            solver=solver,
            timeout_s=optimizer_timeout_s,
        )
        if optimizer.status != "completed":
            messages.append(f"optimizer status: {optimizer.status}")

    if generate_displacements and (optimizer is None or optimizer.status == "completed"):
        try:
            displacement = run_displacement_postprocess(
                project_dir,
                install_root=install_root,
                solver=solver,
                timeout_s=displacement_timeout_s,
            )
            if displacement.status != "completed":
                messages.append(f"displacement postprocess status: {displacement.status}")
        except Exception as exc:  # pragma: no cover - exact native failures vary by install
            messages.append(f"displacement postprocess failed: {exc}")
    if generate_stress and displacement is not None and displacement.status == "completed":
        if supports_automatic_stress_postprocess(project_dir):
            try:
                stress = run_stress_postprocess(
                    project_dir,
                    install_root=install_root,
                    solver=solver,
                    timeout_s=stress_timeout_s,
                )
                if stress.status != "completed":
                    messages.append(f"stress postprocess status: {stress.status}")
            except Exception as exc:  # pragma: no cover - exact native failures vary by install
                messages.append(f"stress postprocess failed: {exc}")
        else:
            stress = _unsupported_stress_result(project_dir)
            messages.append(
                "stress postprocess unsupported: automatic stress is confirmed only for "
                "wrapper-generated OC/TOSS/SKO H8 projects; use Z88Arion GUI export or independent "
                "verification for other Z88 project types"
            )

    native_results = collect_native_results(project_dir)
    native_results_json = project_dir / "z88_native_results.json"
    native_results.write_json(native_results_json)
    if export_optimized_stl and supports_automatic_stl_export(project_dir):
        optimized_export = export_optimized_stl_from_generated_project(project_dir)
        if optimized_export.status not in {"exported", "exported_with_warnings"}:
            messages.append(f"optimized STL export status: {optimized_export.status}")
        if optimized_export.warnings:
            messages.extend(f"optimized STL export warning: {warning}" for warning in optimized_export.warnings)
        if optimized_export.parse_errors:
            messages.extend(f"optimized STL export parse error: {error}" for error in optimized_export.parse_errors)

    status = _workflow_status(optimizer, displacement, native_results, messages)
    result = GeneratedOCWorkflowResult(
        project_dir=str(project_dir),
        status=status,
        optimizer=optimizer,
        displacement=displacement,
        stress=stress,
        optimized_export=optimized_export,
        native_results=native_results,
        native_results_json=str(native_results_json),
        messages=tuple(messages),
    )
    result.write_json(project_dir / "z88_generated_oc_workflow.json")
    return result


def _workflow_status(
    optimizer: GeneratedOptimizerRunResult | None,
    displacement: Z88PostprocessRunResult | None,
    native_results: NativeResultSummary,
    messages: list[str],
) -> str:
    if optimizer is not None and optimizer.status != "completed":
        return "optimizer_failed"
    if native_results.status == "parse_failed":
        return "parse_failed"
    if messages or native_results.status in {"partial", "missing_outputs"}:
        return "partial"
    if displacement is not None and displacement.status != "completed":
        return "partial"
    return "completed"


def supports_automatic_stress_postprocess(project_dir: str | Path) -> bool:
    """Return whether automatic stress postprocess is inside the confirmed scope.

    The `z88rTOSS -SIG` path is reliable for OC/TOSS/SKO H8 projects generated by this
    wrapper because the writer controls the mesh, material file layout, and
    runtime files. Copied GUI-generated projects can crash the same Z88 binary,
    so keep those as guided/manual stress-export workflows.
    """
    project_dir = Path(project_dir)
    write_json = project_dir / "z88_native_project_write.json"
    config_json = project_dir / "config.json"
    if not write_json.is_file() or not config_json.is_file():
        return False
    try:
        write_data = json.loads(write_json.read_text(encoding="utf-8"))
        config_data = json.loads(config_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    optimizer = config_data.get("optimizer", {})
    if not isinstance(optimizer, dict) or str(optimizer.get("method", "")).lower() not in {"oc", "toss", "sko"}:
        return False
    required_counts = ("node_count", "element_count", "boundary_condition_count")
    return all(isinstance(write_data.get(name), int) and write_data[name] > 0 for name in required_counts)


def supports_automatic_stl_export(project_dir: str | Path) -> bool:
    """Return whether density-to-STL export is inside the confirmed scope."""
    return supports_automatic_stress_postprocess(project_dir) and (Path(project_dir) / "z88i1.txt").is_file()


def _unsupported_stress_result(project_dir: Path) -> Z88StressPostprocessRunResult:
    return Z88StressPostprocessRunResult(
        project_dir=str(project_dir),
        command=(),
        returncode=None,
        timed_out=False,
        elapsed_s=0.0,
        status="unsupported",
        nodal_output_file="",
        element_output_file="",
        energy_output_file="",
        stdout_file="",
        stderr_file="",
    )


def _compact_field_summary(summary: dict | None) -> dict | None:
    if summary is None:
        return None
    return {
        "row_count": summary["row_count"],
        "min_value": summary["min_value"],
        "max_value": summary["max_value"],
        "mean_value": summary["mean_value"],
        "min_id": summary["min_id"],
        "max_id": summary["max_id"],
        "zero_count": summary["zero_count"],
        "nonzero_count": summary["nonzero_count"],
    }
