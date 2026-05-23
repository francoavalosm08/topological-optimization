from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from geometry.voxelize import VoxelGrid
from z88_bridge import (
    LoadCase,
    OptimizerSettings,
    RegionSpec,
    SupportSpec,
    Z88RunConfig,
    build_native_mesh,
    write_native_oc_project_from_grid,
)


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Z88Arion.exe").write_text("", encoding="utf-8")
    return root


def _grid() -> VoxelGrid:
    solid = np.ones((2, 1, 1), dtype=bool)
    return VoxelGrid(
        nelx=2,
        nely=1,
        nelz=1,
        solid=solid,
        pitch=1.0,
        origin=np.array([0.0, 0.0, 0.0]),
    )


def _config() -> Z88RunConfig:
    support = RegionSpec(
        name="fixed_x0",
        role="support",
        selector={"type": "box", "min": [0.0, 0.0, 0.0], "max": [0.0, 1.0, 1.0]},
    )
    load = RegionSpec(
        name="loaded_x2",
        role="load",
        selector={"type": "box", "min": [2.0, 0.0, 0.0], "max": [2.0, 1.0, 1.0]},
    )
    return Z88RunConfig(
        input_stl="not-needed-for-grid-writer.stl",
        units="mm",
        project_name="native_writer_test",
        voxel_pitch=1.0,
        optimizer=OptimizerSettings(method="oc", volume_fraction=1.0, max_iterations=1),
        supports=(SupportSpec(name="fixed", region=support),),
        loads=(LoadCase(name="down", region=load, force=(0.0, -100.0, 0.0)),),
    )


def test_build_native_mesh_uses_confirmed_h8_order() -> None:
    grid = VoxelGrid(
        nelx=1,
        nely=1,
        nelz=1,
        solid=np.ones((1, 1, 1), dtype=bool),
        pitch=1.0,
        origin=np.array([0.0, 0.0, 0.0]),
    )

    mesh = build_native_mesh(grid)

    assert len(mesh.nodes) == 8
    assert len(mesh.elements) == 1
    assert mesh.elements[0][1] == (1, 2, 3, 4, 5, 6, 7, 8)
    assert mesh.nodes[0] == (1, 0.0, 1.0, 0.0)
    assert mesh.nodes[1] == (2, 0.0, 0.0, 0.0)


def test_write_native_oc_project_from_grid_writes_confirmed_project_contract(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "Z88ArionV3")
    project = tmp_path / "native_project"

    result = write_native_oc_project_from_grid(_config(), _grid(), project, install_root=install)

    assert result.node_count == 12
    assert result.element_count == 2
    assert result.boundary_condition_count == 16
    assert result.fixed_element_count == 2
    assert result.material_modulus == 68_900.0
    assert (project / "Z88Arion.ctrl").exists()
    assert (project / "Z88Arion.fea").read_text(encoding="utf-8").count("-SICCG") >= 6
    assert (project / "z88i1.txt").read_text(encoding="utf-8").splitlines()[0] == "3 12 2 36 0 "
    assert (project / "z88int.txt").read_text(encoding="utf-8") == "1\n1 2 2 2 \n"
    assert "OPTVREL                      1.000000E+02" in (project / "z88control.txt").read_text(
        encoding="utf-8"
    )

    z88i2 = (project / "z88i2.txt").read_text(encoding="utf-8").splitlines()
    assert z88i2[0] == "16"
    assert sum(" 2 1  -2.5000000E+01 " in line for line in z88i2) == 4

    manifest = json.loads(Path(result.manifest_json).read_text(encoding="utf-8"))
    assert manifest["project_dir"] == str(project)
    summary = json.loads(Path(result.summary_json).read_text(encoding="utf-8"))
    assert summary["control"]["TOSOLVER"]["OPTALGORITHM"] == 1


def test_write_native_oc_project_rejects_empty_region_selection(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "Z88ArionV3")
    bad_support = RegionSpec(
        name="outside",
        role="support",
        selector={"type": "box", "min": [99, 99, 99], "max": [100, 100, 100]},
    )
    config = Z88RunConfig.from_dict(
        {
            **_config().to_dict(),
            "supports": [
                {
                    "name": "bad",
                    "region": bad_support.__dict__,
                    "constrained_dofs": ["x", "y", "z"],
                }
            ],
        }
    )

    try:
        write_native_oc_project_from_grid(config, _grid(), tmp_path / "project", install_root=install)
    except ValueError as exc:
        assert "selected no mesh nodes" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("expected empty support selection to fail")
