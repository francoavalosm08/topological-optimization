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
    export_optimized_stl_from_generated_project,
    parse_z88i1_h8,
    write_native_oc_project_from_grid,
)


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Z88Arion.exe").write_text("", encoding="utf-8")
    return root


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
        project_name="export_test",
        voxel_pitch=1.0,
        optimizer=OptimizerSettings(method="oc", volume_fraction=1.0, max_iterations=1),
        supports=(SupportSpec(name="fixed", region=support),),
        loads=(LoadCase(name="down", region=load, force=(0.0, -100.0, 0.0)),),
    )


def _grid() -> VoxelGrid:
    return VoxelGrid(
        nelx=2,
        nely=1,
        nelz=1,
        solid=np.ones((2, 1, 1), dtype=bool),
        pitch=1.0,
        origin=np.array([0.0, 0.0, 0.0]),
    )


def test_parse_z88i1_h8_reads_generated_nodes_and_elements(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_native_oc_project_from_grid(_config(), _grid(), project, install_root=_fake_install(tmp_path / "Z88"))

    nodes, elements = parse_z88i1_h8(project / "z88i1.txt")

    assert len(nodes) == 12
    assert len(elements) == 2
    assert elements[1] == (1, 2, 3, 4, 5, 6, 7, 8)


def test_export_optimized_stl_from_generated_density_writes_mesh_qa(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_native_oc_project_from_grid(_config(), _grid(), project, install_root=_fake_install(tmp_path / "Z88"))
    density = project / "PhysicalDensity"
    density.mkdir(exist_ok=True)
    (density / "PhysicalDensity1.txt").write_text("1 1.0\n2 1.0\n", encoding="utf-8")

    result = export_optimized_stl_from_generated_project(project, threshold=0.5)

    assert result.status == "exported"
    assert result.selected_element_count == 2
    assert result.total_element_count == 2
    assert result.optimized_stl is not None
    assert result.mesh_quality_json is not None
    quality = json.loads(Path(result.mesh_quality_json).read_text(encoding="utf-8"))
    assert quality["watertight"] is True
    assert quality["components"] == 1
    assert quality["degenerate_faces"] == 0
    assert Path(result.optimized_stl).exists()
    assert (project / "z88_optimized_stl_export.json").exists()


def test_export_optimized_stl_reports_empty_density_selection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_native_oc_project_from_grid(_config(), _grid(), project, install_root=_fake_install(tmp_path / "Z88"))
    density = project / "PhysicalDensity"
    density.mkdir(exist_ok=True)
    (density / "PhysicalDensity1.txt").write_text("1 0.1\n2 0.2\n", encoding="utf-8")

    result = export_optimized_stl_from_generated_project(project, threshold=0.5)

    assert result.status == "empty_selection"
    assert result.optimized_stl is None
    assert "selected no elements" in result.warnings[0]
