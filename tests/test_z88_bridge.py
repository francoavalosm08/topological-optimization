from __future__ import annotations

import json
from pathlib import Path

import pytest
import trimesh

from z88_bridge import (
    LoadCase,
    RegionSpec,
    SupportSpec,
    Z88Adapter,
    Z88NotInstalledError,
    Z88RunConfig,
    discover_installation,
)


def _write_box_stl(path: Path) -> Path:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    mesh.export(path)
    return path


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    for name in (
        "Z88Arion.exe",
        "Z88OC.exe",
        "z88optopus.exe",
        "z88rTOSS.exe",
        "z88r_sko.exe",
        "z88r_opt.exe",
        "z88rofl.exe",
    ):
        (bin_dir / name).write_text("", encoding="utf-8")
    return root


def _config(stl: Path) -> Z88RunConfig:
    fixed = RegionSpec(
        name="fixed_face",
        selector={"type": "box", "min": [0, 0, 0], "max": [0.1, 1, 1]},
        role="support",
    )
    loaded = RegionSpec(
        name="load_face",
        selector={"type": "box", "min": [0.9, 0, 0], "max": [1, 1, 1]},
        role="load",
    )
    return Z88RunConfig(
        input_stl=str(stl),
        units="mm",
        project_name="fixture",
        supports=(SupportSpec(name="fixed", region=fixed),),
        loads=(LoadCase(name="down", region=loaded, force=(0.0, -100.0, 0.0)),),
    )


def test_config_round_trip_and_validation(tmp_path: Path) -> None:
    stl = _write_box_stl(tmp_path / "input.stl")
    config = _config(stl)

    config.validate()
    path = tmp_path / "config.json"
    path.write_text(config.to_json(), encoding="utf-8")

    loaded = Z88RunConfig.from_json_file(path)
    assert loaded == config
    assert loaded.run_id() == config.run_id()


def test_config_rejects_invalid_optimizer(tmp_path: Path) -> None:
    stl = _write_box_stl(tmp_path / "input.stl")
    config = Z88RunConfig(input_stl=str(stl), units="mm")
    bad = Z88RunConfig.from_dict({**config.to_dict(), "optimizer": {"method": "made_up"}})

    with pytest.raises(ValueError, match="optimizer.method"):
        bad.validate()


def test_discover_installation_uses_explicit_root_only(tmp_path: Path) -> None:
    fake = _fake_install(tmp_path / "Z88ArionV3")

    installation = discover_installation(fake)
    assert installation.root == fake
    assert installation.arion_exe == fake / "win" / "bin" / "Z88Arion.exe"

    with pytest.raises(Z88NotInstalledError):
        discover_installation(tmp_path / "missing")


def test_discover_installation_uses_environment_fallback(tmp_path: Path, monkeypatch) -> None:
    fake = _fake_install(tmp_path / "EnvZ88")
    monkeypatch.setenv("Z88ARION_ROOT", str(fake))

    installation = discover_installation()

    assert installation.root == fake
    assert installation.arion_exe == fake / "win" / "bin" / "Z88Arion.exe"


def test_prepare_project_creates_reproducible_handoff(tmp_path: Path) -> None:
    fake = _fake_install(tmp_path / "Z88ArionV3")
    stl = _write_box_stl(tmp_path / "input.stl")
    adapter = Z88Adapter(install_root=fake, runs_root=tmp_path / "runs")

    project_dir = adapter.prepare_project(_config(stl))

    assert (project_dir / "config.json").exists()
    assert (project_dir / "input.stl").exists()
    assert (project_dir / "z88_project").is_dir()
    assert (project_dir / "z88_raw_results").is_dir()
    assert (project_dir / "Z88_HANDOFF.md").exists()
    assert (project_dir / "bridge_status.json").exists()
    manifest = json.loads((project_dir / "z88_installation.json").read_text(encoding="utf-8"))
    assert manifest["arion_exe"].endswith("Z88Arion.exe")


def test_collect_results_without_export_reports_manual_step(tmp_path: Path) -> None:
    fake = _fake_install(tmp_path / "Z88ArionV3")
    stl = _write_box_stl(tmp_path / "input.stl")
    adapter = Z88Adapter(install_root=fake, runs_root=tmp_path / "runs")
    project_dir = adapter.prepare_project(_config(stl))

    result = adapter.collect_results(project_dir)

    assert result.status == "needs_manual_export"
    assert result.optimized_stl is None
    assert (project_dir / "optimization_result.json").exists()
    assert "optimized.stl was not found" in result.messages[0]


def test_collect_results_with_export_writes_mesh_quality(tmp_path: Path) -> None:
    fake = _fake_install(tmp_path / "Z88ArionV3")
    stl = _write_box_stl(tmp_path / "input.stl")
    adapter = Z88Adapter(install_root=fake, runs_root=tmp_path / "runs")
    project_dir = adapter.prepare_project(_config(stl))
    _write_box_stl(project_dir / "optimized.stl")

    result = adapter.collect_results(project_dir)

    assert result.status == "collected"
    assert result.optimized_stl == str(project_dir / "optimized.stl")
    assert result.mesh_quality_json == str(project_dir / "mesh_quality.json")
    mesh_quality = json.loads((project_dir / "mesh_quality.json").read_text(encoding="utf-8"))
    assert mesh_quality["watertight"] is True
    assert mesh_quality["components"] == 1


def test_stage_native_project_copies_and_summarizes_project(tmp_path: Path) -> None:
    fake = _fake_install(tmp_path / "Z88ArionV3")
    native = tmp_path / "native_project"
    native.mkdir()
    (native / "z88control.txt").write_text(
        "TOSOLVER START\n   OPTALGORITHM 1\nTOSOLVER END\n",
        encoding="utf-8",
    )
    (native / "z88sets.txt").write_text("#NODES CONSTRAINT 1 1 \"fixed\"\n1\n", encoding="utf-8")
    (native / "z88setsactive.txt").write_text(
        '#NODES CONSTRAINT 1 1 "fixed"\n',
        encoding="utf-8",
    )
    (native / "z88structure.txt").write_text("3 1 1 1 0\n", encoding="utf-8")
    adapter = Z88Adapter(install_root=fake, runs_root=tmp_path / "runs")

    run_dir = adapter.stage_native_project(native, project_name="native")

    assert (run_dir / "z88_project" / "z88control.txt").exists()
    assert (run_dir / "Z88_NATIVE_HANDOFF.md").exists()
    summary = json.loads((run_dir / "z88_project_summary.json").read_text(encoding="utf-8"))
    assert summary["control"]["TOSOLVER"]["OPTALGORITHM"] == 1
    assert summary["active_sets"][0]["label"] == "fixed"
    assert summary["structure"]["fields"] == [3, 1, 1, 1, 0]
