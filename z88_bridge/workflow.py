"""Workflow orchestration for confirmed Z88Arion generated-project paths."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

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
) -> GeneratedOCWorkflowResult:
    """Run the currently confirmed generated-OC workflow end to end."""
    project_dir = Path(project_dir).resolve()
    messages: list[str] = []
    optimizer: GeneratedOptimizerRunResult | None = None
    displacement: Z88PostprocessRunResult | None = None
    stress: Z88StressPostprocessRunResult | None = None

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

    native_results = collect_native_results(project_dir)
    native_results_json = project_dir / "z88_native_results.json"
    native_results.write_json(native_results_json)

    status = _workflow_status(optimizer, displacement, native_results, messages)
    result = GeneratedOCWorkflowResult(
        project_dir=str(project_dir),
        status=status,
        optimizer=optimizer,
        displacement=displacement,
        stress=stress,
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
