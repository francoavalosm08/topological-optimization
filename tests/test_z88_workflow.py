from __future__ import annotations

from pathlib import Path

import z88_bridge.workflow as workflow
from z88_bridge import (
    GeneratedOptimizerRunResult,
    NativeResultSummary,
    ScalarHistory,
    Z88StressPostprocessRunResult,
    Z88PostprocessRunResult,
    run_generated_oc_workflow,
)


def _optimizer(status: str = "completed") -> GeneratedOptimizerRunResult:
    return GeneratedOptimizerRunResult(
        project_dir="project",
        command=("z88optopus.exe", "-parao"),
        returncode=0,
        timed_out=False,
        elapsed_s=1.0,
        solver_arg="-SICCG",
        status=status,
        output_dir="out",
        stdout_file="stdout.txt",
        stderr_file="stderr.txt",
        z88oc_log="Z88OC.log",
    )


def _displacement(status: str = "completed") -> Z88PostprocessRunResult:
    return Z88PostprocessRunResult(
        project_dir="project",
        command=("z88rofl.exe", "-U"),
        returncode=4294954951,
        timed_out=False,
        elapsed_s=1.0,
        status=status,
        output_file="Displacements/Displacements_final.txt",
        stdout_file="stdout.txt",
        stderr_file="stderr.txt",
    )


def _stress(status: str = "completed") -> Z88StressPostprocessRunResult:
    return Z88StressPostprocessRunResult(
        project_dir="project",
        command=("z88rTOSS.exe", "-SIG"),
        returncode=4294954951,
        timed_out=False,
        elapsed_s=1.0,
        status=status,
        nodal_output_file="Knotenspannungen/Knot_final.txt",
        element_output_file="Stresses_ELE/Stress_ele_final.txt",
        energy_output_file="tmp/ElementEnergy_final.txt",
        stdout_file="stdout.txt",
        stderr_file="stderr.txt",
    )


def _native(status: str = "collected") -> NativeResultSummary:
    return NativeResultSummary(
        schema_version=1,
        project_dir="project",
        status=status,
        histories={
            "overall_compliance": ScalarHistory(
                "overall_compliance",
                "tmp/OverallCompliance.txt",
                values=(1.0, 0.5),
            )
        },
    )


def test_generated_oc_workflow_runs_optimizer_displacement_and_collection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_optimizer(*args, **kwargs):
        calls.append("optimizer")
        return _optimizer()

    def fake_displacement(*args, **kwargs):
        calls.append("displacement")
        return _displacement()

    def fake_collect(*args, **kwargs):
        calls.append("collect")
        return _native()

    monkeypatch.setattr(workflow, "run_generated_optimizer_project", fake_optimizer)
    monkeypatch.setattr(workflow, "run_displacement_postprocess", fake_displacement)
    monkeypatch.setattr(workflow, "collect_native_results", fake_collect)

    result = run_generated_oc_workflow(tmp_path)

    assert result.status == "completed"
    assert calls == ["optimizer", "displacement", "collect"]
    assert (tmp_path / "z88_native_results.json").exists()
    assert (tmp_path / "z88_generated_oc_workflow.json").exists()
    assert result.compact_dict()["histories"]["overall_compliance"]["final_value"] == 0.5
    assert result.compact_dict()["stress_status"] is None


def test_generated_oc_workflow_can_run_stress_after_displacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(workflow, "run_generated_optimizer_project", lambda *args, **kwargs: _optimizer())
    monkeypatch.setattr(workflow, "run_displacement_postprocess", lambda *args, **kwargs: _displacement())

    def fake_stress(*args, **kwargs):
        calls.append("stress")
        return _stress()

    monkeypatch.setattr(workflow, "run_stress_postprocess", fake_stress)
    monkeypatch.setattr(workflow, "collect_native_results", lambda *args, **kwargs: _native())

    result = run_generated_oc_workflow(tmp_path, generate_stress=True)

    assert calls == ["stress"]
    assert result.stress is not None
    assert result.compact_dict()["stress_status"] == "completed"


def test_generated_oc_workflow_skips_displacement_after_optimizer_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_optimizer(*args, **kwargs):
        calls.append("optimizer")
        return _optimizer(status="solver_failed")

    def fake_displacement(*args, **kwargs):
        calls.append("displacement")
        return _displacement()

    monkeypatch.setattr(workflow, "run_generated_optimizer_project", fake_optimizer)
    monkeypatch.setattr(workflow, "run_displacement_postprocess", fake_displacement)
    monkeypatch.setattr(workflow, "collect_native_results", lambda *args, **kwargs: _native())

    result = run_generated_oc_workflow(tmp_path)

    assert result.status == "optimizer_failed"
    assert calls == ["optimizer"]
    assert result.messages == ("optimizer status: solver_failed",)
