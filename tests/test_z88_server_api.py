from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
import trimesh

import server.app as api
from z88_bridge import NativeOCProjectWriteResult


def _box_stl(path: Path) -> Path:
    mesh = trimesh.creation.box(extents=(10.0, 4.0, 2.0))
    mesh.export(path)
    return path


def test_z88_preset_endpoints_return_serializable_payloads() -> None:
    materials = api.z88_materials()
    safety = api.z88_safety_presets()
    recipes = api.z88_recipes()

    assert materials["al_6061_t6"]["young_modulus"] > 0
    assert safety["consumer_drone"] == 1.5
    assert "drone_landing_gear" in recipes


def test_z88_discovery_endpoint_reports_missing_install(tmp_path: Path) -> None:
    response = api.z88_discovery(install_root=str(tmp_path / "missing"))

    assert response["status"] == "missing"
    assert "Z88Arion was not found" in response["detail"]


def test_z88_generate_samples_endpoint_writes_catalog(tmp_path: Path) -> None:
    response = api.z88_generate_samples(api.Z88SampleGenerateRequest(output_dir=str(tmp_path / "samples")))

    assert response["status"] == "generated"
    assert response["sample_count"] == 5
    assert Path(response["catalog_json"]).is_file()


def test_z88_configure_recipe_endpoint_returns_config_only(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    response = api.z88_configure_recipe(
        api.Z88RecipeConfigureRequest(
            recipe="ring_wing_strut",
            stl_path=str(stl),
            root_support_box=api.Z88BoxRequest(min=(-5.0, -2.0, -1.0), max=(-4.0, 2.0, 1.0)),
            wing_load_box=api.Z88BoxRequest(min=(4.0, -2.0, -1.0), max=(5.0, 2.0, 1.0)),
            lift_force_per_strut=30.0,
        )
    )

    assert response["status"] == "configured"
    assert response["config"]["project_name"] == "ring_wing_strut"
    assert response["config"]["loads"][0]["force"] == (0.0, 0.0, 30.0)


def test_z88_configure_recipe_endpoint_reports_bad_input(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(HTTPException) as exc:
        api.z88_configure_recipe(
            api.Z88RecipeConfigureRequest(
                recipe="drone_motor_mount",
                stl_path=str(stl),
                frame_support_box=api.Z88BoxRequest(min=(-5.0, -2.0, -1.0), max=(-4.0, 2.0, 1.0)),
                motor_mount_box=api.Z88BoxRequest(min=(4.0, -2.0, -1.0), max=(5.0, 2.0, 1.0)),
            )
        )

    assert exc.value.status_code == 400
    assert "thrust is required" in exc.value.detail


def test_z88_backend_endpoint_writes_guided_handoff_for_non_generated_project(tmp_path: Path) -> None:
    response = api.z88_backend_run(api.Z88BackendRunRequest(project_dir=str(tmp_path)))

    assert response["status"] == "guided_handoff_required"
    assert (tmp_path / "Z88_GUIDED_BACKEND_HANDOFF.md").exists()
    assert (tmp_path / "z88_backend_result.json").exists()


def test_z88_backend_endpoint_passes_optional_stress_request(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBackendResult:
        def compact_dict(self):
            return {"status": "completed", "mode": "generated_oc"}

    def fake_backend(project_dir, **kwargs):
        captured["project_dir"] = project_dir
        captured.update(kwargs)
        return FakeBackendResult()

    monkeypatch.setattr(api, "run_best_available_backend", fake_backend)

    response = api.z88_backend_run(
        api.Z88BackendRunRequest(
            project_dir=str(tmp_path),
            generate_stress=True,
            stress_timeout=42.0,
        )
    )

    assert response["status"] == "completed"
    assert captured["generate_stress"] is True
    assert captured["stress_timeout_s"] == 42.0


def test_z88_native_generate_endpoint_writes_project_and_runs_optional_workflow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "native_project"
    config = {
        "input_stl": "not-needed-when-writer-is-patched.stl",
        "units": "mm",
        "project_name": "api_native",
        "voxel_pitch": 1.0,
        "optimizer": {"method": "oc", "volume_fraction": 0.5, "max_iterations": 1},
        "supports": [
            {
                "name": "fixed",
                "region": {
                    "name": "fixed_face",
                    "role": "support",
                    "selector": {"type": "box", "min": [0, 0, 0], "max": [0, 1, 1]},
                },
            }
        ],
        "loads": [
            {
                "name": "load",
                "region": {
                    "name": "load_face",
                    "role": "load",
                    "selector": {"type": "box", "min": [1, 0, 0], "max": [1, 1, 1]},
                },
                "force": [0, -10, 0],
            }
        ],
    }
    captured: dict[str, object] = {}

    def fake_write_native_oc_project(run_config, project_dir, **kwargs):
        project_dir = Path(project_dir)
        project_dir.mkdir(parents=True)
        captured["write_project_dir"] = project_dir
        captured["write_max_elements"] = kwargs["max_elements"]
        return NativeOCProjectWriteResult(
            project_dir=str(project_dir),
            node_count=8,
            element_count=1,
            boundary_condition_count=7,
            fixed_element_count=1,
            material_modulus=68_900.0,
            poisson_ratio=0.33,
            units=run_config.units,
            manifest_json=str(project_dir / "manifest.json"),
            summary_json=str(project_dir / "summary.json"),
        )

    class FakeWorkflow:
        status = "completed"

        def compact_dict(self):
            return {"status": self.status, "stress_status": "completed"}

    def fake_run_generated_oc_workflow(project_dir, **kwargs):
        captured["workflow_project_dir"] = project_dir
        captured["workflow_generate_stress"] = kwargs["generate_stress"]
        captured["workflow_stress_timeout_s"] = kwargs["stress_timeout_s"]
        return FakeWorkflow()

    monkeypatch.setattr(api, "write_native_oc_project", fake_write_native_oc_project)
    monkeypatch.setattr(api, "run_generated_oc_workflow", fake_run_generated_oc_workflow)

    response = api.z88_generate_native_project(
        api.Z88NativeProjectGenerateRequest(
            config=config,
            project_dir=str(project),
            max_elements=123,
            run_workflow=True,
            generate_stress=True,
            stress_timeout=15.0,
        )
    )

    assert response["status"] == "workflow_completed"
    assert response["project_dir"] == str(project.resolve())
    assert response["write"]["element_count"] == 1
    assert response["workflow"]["stress_status"] == "completed"
    assert captured["write_project_dir"] == project
    assert captured["write_max_elements"] == 123
    assert captured["workflow_project_dir"] == str(project)
    assert captured["workflow_generate_stress"] is True
    assert captured["workflow_stress_timeout_s"] == 15.0


def test_z88_collect_native_endpoint_returns_missing_outputs_for_empty_folder(tmp_path: Path) -> None:
    response = api.z88_collect_native(api.Z88CollectNativeRequest(project_dir=str(tmp_path)))

    assert response["status"] == "missing_outputs"
    assert response["histories"]["overall_compliance"]["count"] == 0
