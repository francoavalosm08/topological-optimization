from __future__ import annotations

from pathlib import Path

import z88_bridge.backend as backend
from z88_bridge import (
    GeneratedOCWorkflowResult,
    NativeResultSummary,
    ScalarHistory,
    ensure_guided_handoff,
    find_generated_oc_project_dir,
    run_best_available_backend,
)


def _generated_project(path: Path) -> Path:
    path.mkdir(parents=True)
    for name in ("Z88Arion.pth", "Z88Arion.fea", "z88i1.txt", "z88i2.txt", "z88control.txt"):
        (path / name).write_text(name, encoding="utf-8")
    (path / "ConstitutiveLaw").mkdir()
    return path


def _workflow(project_dir: Path, status: str = "completed") -> GeneratedOCWorkflowResult:
    native = NativeResultSummary(
        schema_version=2,
        project_dir=str(project_dir),
        status="collected",
        histories={
            "overall_compliance": ScalarHistory(
                "overall_compliance",
                "tmp/OverallCompliance.txt",
                values=(2.0, 1.0),
            )
        },
    )
    return GeneratedOCWorkflowResult(
        project_dir=str(project_dir),
        status=status,
        optimizer=None,
        displacement=None,
        stress=None,
        native_results=native,
        native_results_json=str(project_dir / "z88_native_results.json"),
        messages=(),
    )


def test_find_generated_oc_project_dir_detects_root_and_nested_z88_project(tmp_path: Path) -> None:
    root_project = _generated_project(tmp_path / "root_project")
    run_folder = tmp_path / "run"
    nested_project = _generated_project(run_folder / "z88_project")

    assert find_generated_oc_project_dir(root_project) == root_project
    assert find_generated_oc_project_dir(run_folder) == nested_project
    assert find_generated_oc_project_dir(tmp_path / "missing") is None


def test_best_available_backend_runs_generated_oc_workflow(tmp_path: Path, monkeypatch) -> None:
    generated = _generated_project(tmp_path / "project")
    called: list[Path] = []
    kwargs_seen: dict[str, object] = {}

    def fake_workflow(project_dir, **kwargs):
        called.append(Path(project_dir))
        kwargs_seen.update(kwargs)
        return _workflow(Path(project_dir))

    monkeypatch.setattr(backend, "run_generated_oc_workflow", fake_workflow)

    result = run_best_available_backend(generated, generate_stress=True, stress_timeout_s=12.0)

    assert result.status == "completed"
    assert result.mode == "generated_oc"
    assert called == [generated.resolve()]
    assert kwargs_seen["generate_stress"] is True
    assert kwargs_seen["stress_timeout_s"] == 12.0
    assert (generated / "z88_backend_result.json").exists()


def test_best_available_backend_writes_guided_handoff_when_not_generated(tmp_path: Path) -> None:
    result = run_best_available_backend(tmp_path)

    assert result.status == "guided_handoff_required"
    assert result.mode == "guided_handoff"
    assert result.handoff_file is not None
    assert Path(result.handoff_file).exists()
    assert (tmp_path / "z88_backend_result.json").exists()


def test_ensure_guided_handoff_is_idempotent(tmp_path: Path) -> None:
    first = ensure_guided_handoff(tmp_path)
    second = ensure_guided_handoff(tmp_path)

    assert first == second
    assert "Z88 Guided Backend Handoff" in first.read_text(encoding="utf-8")
