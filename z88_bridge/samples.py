"""Deterministic sample STL generation for packaging and workflow smoke tests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


@dataclass(frozen=True)
class SampleAsset:
    name: str
    filename: str
    recipe: str
    description: str
    extents: tuple[float, float, float]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SAMPLE_ASSETS: tuple[SampleAsset, ...] = (
    SampleAsset(
        name="generic_bracket_box",
        filename="generic_bracket_box.stl",
        recipe="generic_bracket",
        description="Small rectangular bracket smoke-test part with opposed support/load regions.",
        extents=(10.0, 4.0, 2.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "sample_generic_bracket",
            "support_box": {"min": [-5.0, -2.0, -1.0], "max": [-4.0, 2.0, 1.0]},
            "load_box": {"min": [4.0, -2.0, -1.0], "max": [5.0, 2.0, 1.0]},
            "force": [0.0, -100.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 1.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="drone_motor_mount_box",
        filename="drone_motor_mount_box.stl",
        recipe="drone_motor_mount",
        description="Flat motor-mount smoke-test part with frame and motor-side boxes.",
        extents=(20.0, 20.0, 3.0),
        payload={
            "recipe": "drone_motor_mount",
            "project_name": "sample_drone_motor_mount",
            "frame_support_box": {"min": [-10.0, -10.0, -1.5], "max": [-9.0, 10.0, 1.5]},
            "motor_mount_box": {"min": [9.0, -10.0, -1.5], "max": [10.0, 10.0, 1.5]},
            "thrust": 25.0,
            "thrust_direction": [0.0, 0.0, 1.0],
            "prop_diameter": 10.0,
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="drone_landing_gear_box",
        filename="drone_landing_gear_box.stl",
        recipe="drone_landing_gear",
        description="Landing-gear beam smoke-test part with frame and ground-contact boxes.",
        extents=(24.0, 5.0, 5.0),
        payload={
            "recipe": "drone_landing_gear",
            "project_name": "sample_drone_landing_gear",
            "frame_support_box": {"min": [-12.0, -2.5, -2.5], "max": [-11.0, 2.5, 2.5]},
            "ground_contact_box": {"min": [11.0, -2.5, -2.5], "max": [12.0, 2.5, 2.5]},
            "payload_mass": 1.0,
            "impact_g": 3.0,
            "load_direction": [0.0, 0.0, 1.0],
            "material": "pa12_sls",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 1.5,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="drone_gimbal_mount_box",
        filename="drone_gimbal_mount_box.stl",
        recipe="drone_gimbal_mount",
        description="Gimbal-mount smoke-test part with frame and camera boxes.",
        extents=(16.0, 10.0, 3.0),
        payload={
            "recipe": "drone_gimbal_mount",
            "project_name": "sample_drone_gimbal_mount",
            "frame_support_box": {"min": [-8.0, -5.0, -1.5], "max": [-7.0, 5.0, 1.5]},
            "camera_mount_box": {"min": [7.0, -5.0, -1.5], "max": [8.0, 5.0, 1.5]},
            "camera_mass": 0.25,
            "maneuver_g": 2.5,
            "load_direction": [0.0, -1.0, 0.0],
            "target_vibration_frequency": 120.0,
            "material": "pa12_sls",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 1.5,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="ring_wing_strut_box",
        filename="ring_wing_strut_box.stl",
        recipe="ring_wing_strut",
        description="Long strut smoke-test part with root and wing load boxes.",
        extents=(30.0, 3.0, 3.0),
        payload={
            "recipe": "ring_wing_strut",
            "project_name": "sample_ring_wing_strut",
            "root_support_box": {"min": [-15.0, -1.5, -1.5], "max": [-14.0, 1.5, 1.5]},
            "wing_load_box": {"min": [14.0, -1.5, -1.5], "max": [15.0, 1.5, 1.5]},
            "lift_force_per_strut": 30.0,
            "lift_direction": [0.0, 0.0, 1.0],
            "material": "cf_pa",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
)


STRUCTURAL_SAMPLE_ASSETS: tuple[SampleAsset, ...] = (
    SampleAsset(
        name="cantilever_beam",
        filename="cantilever_beam.stl",
        recipe="generic_bracket",
        description="Straight cantilever beam with one fixed end and one loaded end.",
        extents=(30.0, 4.0, 4.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "structural_cantilever_beam",
            "support_box": {"min": [-15.0, -2.0, -2.0], "max": [-12.0, 2.0, 2.0]},
            "load_box": {"min": [12.0, -2.0, -2.0], "max": [15.0, 2.0, 2.0]},
            "force": [0.0, -100.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="l_bracket",
        filename="l_bracket.stl",
        recipe="generic_bracket",
        description="Voxel L-bracket with a wall leg and a horizontal loaded arm.",
        extents=(24.0, 5.0, 18.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "structural_l_bracket",
            "support_box": {"min": [-12.0, -2.5, -2.0], "max": [-9.0, 2.5, 16.0]},
            "load_box": {"min": [9.0, -2.5, -2.0], "max": [12.0, 2.5, 2.0]},
            "force": [0.0, -120.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="bridge_beam",
        filename="bridge_beam.stl",
        recipe="generic_bracket",
        description="Bridge-style beam with enlarged end pads and a center load pad.",
        extents=(36.0, 6.0, 5.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "structural_bridge_beam",
            "support_box": {"min": [-18.0, -3.0, -2.5], "max": [-14.0, 3.0, 2.5]},
            "load_box": {"min": [-2.5, -3.0, -2.5], "max": [2.5, 3.0, 2.5]},
            "force": [0.0, -150.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="gusset_bracket",
        filename="gusset_bracket.stl",
        recipe="generic_bracket",
        description="Triangular gusset-style bracket for diagonal load-path checks.",
        extents=(24.0, 5.0, 18.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "structural_gusset_bracket",
            "support_box": {"min": [-12.0, -2.5, -2.0], "max": [-9.0, 2.5, 16.0]},
            "load_box": {"min": [8.0, -2.5, -2.0], "max": [12.0, 2.5, 3.0]},
            "force": [0.0, -125.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.5,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
    SampleAsset(
        name="plate_with_hole",
        filename="plate_with_hole.stl",
        recipe="generic_bracket",
        description="Flat plate with a center hole to exercise stress concentration behavior.",
        extents=(28.0, 16.0, 4.0),
        payload={
            "recipe": "generic_bracket",
            "project_name": "structural_plate_with_hole",
            "support_box": {"min": [-14.0, -8.0, -2.0], "max": [-11.0, 8.0, 2.0]},
            "load_box": {"min": [11.0, -8.0, -2.0], "max": [14.0, 8.0, 2.0]},
            "force": [0.0, -100.0, 0.0],
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": 2.0,
            "volume_fraction": 1.0,
            "max_iterations": 1,
        },
    ),
)


def generate_sample_assets(output_dir: str | Path) -> dict[str, Any]:
    """Write small watertight STL samples and a catalog JSON file."""
    return _generate_assets(SAMPLE_ASSETS, output_dir)


def generate_structural_sample_assets(output_dir: str | Path) -> dict[str, Any]:
    """Write common mechanical structure STL samples and a catalog JSON file."""
    return _generate_assets(STRUCTURAL_SAMPLE_ASSETS, output_dir)


def _generate_assets(assets: tuple[SampleAsset, ...], output_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog: list[dict[str, Any]] = []
    for sample in assets:
        stl_path = output_dir / sample.filename
        mesh = _sample_mesh(sample)
        mesh.export(stl_path)
        item = sample.to_dict()
        item["stl_path"] = str(stl_path.resolve())
        item["payload"] = {**sample.payload, "stl_path": str(stl_path.resolve())}
        catalog.append(item)

    catalog_payload = {"schema_version": 1, "samples": catalog}
    catalog_path = output_dir / "sample_catalog.json"
    catalog_path.write_text(json.dumps(catalog_payload, indent=2), encoding="utf-8")
    return {
        "output_dir": str(output_dir.resolve()),
        "catalog_json": str(catalog_path.resolve()),
        "sample_count": len(catalog),
        "samples": catalog,
    }


def _sample_mesh(sample: SampleAsset) -> trimesh.Trimesh:
    if sample.name == "generic_bracket_box":
        return _combine_boxes(
            [
                ((10.0, 4.0, 2.0), (0.0, 0.0, 0.0)),
                ((3.0, 4.0, 8.0), (-3.5, 0.0, 3.0)),
            ]
        )
    if sample.name == "drone_motor_mount_box":
        return _combine_boxes(
            [
                ((20.0, 6.0, 3.0), (0.0, 0.0, 0.0)),
                ((6.0, 20.0, 3.0), (0.0, 0.0, 0.0)),
                ((10.0, 10.0, 4.0), (0.0, 0.0, 0.0)),
            ]
        )
    if sample.name == "drone_landing_gear_box":
        return _combine_boxes(
            [
                ((24.0, 3.0, 3.0), (0.0, 0.0, 1.0)),
                ((4.0, 5.0, 6.0), (-10.0, 0.0, -1.0)),
                ((4.0, 5.0, 6.0), (10.0, 0.0, -1.0)),
            ]
        )
    if sample.name == "drone_gimbal_mount_box":
        return _combine_boxes(
            [
                ((16.0, 4.0, 3.0), (0.0, 0.0, 0.0)),
                ((4.0, 10.0, 3.0), (0.0, 0.0, 0.0)),
                ((6.0, 6.0, 4.0), (4.0, 0.0, 0.0)),
            ]
        )
    if sample.name == "ring_wing_strut_box":
        return _combine_boxes(
            [
                ((30.0, 2.0, 2.0), (0.0, 0.0, 0.0)),
                ((5.0, 3.0, 3.0), (-12.5, 0.0, 0.0)),
                ((5.0, 3.0, 3.0), (12.5, 0.0, 0.0)),
            ]
        )
    if sample.name == "l_bracket":
        return _combine_boxes(
            [
                ((24.0, 5.0, 4.0), (0.0, 0.0, 0.0)),
                ((5.0, 5.0, 18.0), (-9.5, 0.0, 7.0)),
            ]
        )
    if sample.name == "bridge_beam":
        return _combine_boxes(
            [
                ((36.0, 3.0, 3.0), (0.0, 0.0, 0.0)),
                ((5.0, 6.0, 5.0), (-15.5, 0.0, 0.0)),
                ((5.0, 6.0, 5.0), (15.5, 0.0, 0.0)),
                ((6.0, 5.0, 4.0), (0.0, 0.0, 0.5)),
            ]
        )
    if sample.name == "gusset_bracket":
        return _gusset_bracket_mesh()
    if sample.name == "plate_with_hole":
        return _plate_with_hole_mesh()
    return trimesh.creation.box(extents=sample.extents)


def _combine_boxes(parts: list[tuple[tuple[float, float, float], tuple[float, float, float]]]) -> trimesh.Trimesh:
    solid, origin, pitch = _voxel_box_union(parts)
    mesh = _surface_mesh_from_voxels(solid, origin=origin, pitch=pitch)
    if not mesh.is_watertight:
        raise ValueError("generated sample mesh is not watertight")
    return mesh


def _voxel_box_union(
    parts: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    *,
    pitch: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, float]:
    lowers = []
    uppers = []
    for extents, translation in parts:
        ext = np.asarray(extents, dtype=float)
        center = np.asarray(translation, dtype=float)
        lowers.append(center - ext / 2.0)
        uppers.append(center + ext / 2.0)
    lower = np.floor(np.min(np.vstack(lowers), axis=0) / pitch) * pitch
    upper = np.ceil(np.max(np.vstack(uppers), axis=0) / pitch) * pitch
    dims = np.maximum(1, np.ceil((upper - lower) / pitch).astype(int))
    solid = np.zeros(tuple(int(value) for value in dims), dtype=bool)

    xs = lower[0] + (np.arange(dims[0]) + 0.5) * pitch
    ys = lower[1] + (np.arange(dims[1]) + 0.5) * pitch
    zs = lower[2] + (np.arange(dims[2]) + 0.5) * pitch
    xgrid, ygrid, zgrid = np.meshgrid(xs, ys, zs, indexing="ij")
    for extents, translation in parts:
        ext = np.asarray(extents, dtype=float)
        center = np.asarray(translation, dtype=float)
        lo = center - ext / 2.0
        hi = center + ext / 2.0
        solid |= (
            (lo[0] <= xgrid) & (xgrid <= hi[0])
            & (lo[1] <= ygrid) & (ygrid <= hi[1])
            & (lo[2] <= zgrid) & (zgrid <= hi[2])
        )
    return solid, lower.astype(float), pitch


def _gusset_bracket_mesh(*, pitch: float = 1.0) -> trimesh.Trimesh:
    lower = np.asarray([-12.0, -2.5, -2.0], dtype=float)
    upper = np.asarray([12.0, 2.5, 16.0], dtype=float)
    dims = np.ceil((upper - lower) / pitch).astype(int)
    solid = np.zeros(tuple(int(value) for value in dims), dtype=bool)
    xs = lower[0] + (np.arange(dims[0]) + 0.5) * pitch
    ys = lower[1] + (np.arange(dims[1]) + 0.5) * pitch
    zs = lower[2] + (np.arange(dims[2]) + 0.5) * pitch
    xgrid, ygrid, zgrid = np.meshgrid(xs, ys, zs, indexing="ij")

    base_arm = (-2.0 <= zgrid) & (zgrid <= 2.0)
    wall_arm = (-12.0 <= xgrid) & (xgrid <= -7.0)
    diagonal = zgrid <= (-0.75 * xgrid + 9.0)
    solid |= base_arm | wall_arm | diagonal
    mesh = _surface_mesh_from_voxels(solid, origin=lower, pitch=pitch)
    if not mesh.is_watertight:
        raise ValueError("generated gusset bracket is not watertight")
    return mesh


def _plate_with_hole_mesh(*, pitch: float = 1.0) -> trimesh.Trimesh:
    lower = np.asarray([-14.0, -8.0, -2.0], dtype=float)
    upper = np.asarray([14.0, 8.0, 2.0], dtype=float)
    dims = np.ceil((upper - lower) / pitch).astype(int)
    xs = lower[0] + (np.arange(dims[0]) + 0.5) * pitch
    ys = lower[1] + (np.arange(dims[1]) + 0.5) * pitch
    zs = lower[2] + (np.arange(dims[2]) + 0.5) * pitch
    xgrid, ygrid, _zgrid = np.meshgrid(xs, ys, zs, indexing="ij")
    radius = 3.5
    solid = (xgrid * xgrid + ygrid * ygrid) >= radius * radius
    mesh = _surface_mesh_from_voxels(solid, origin=lower, pitch=pitch)
    if not mesh.is_watertight:
        raise ValueError("generated plate-with-hole is not watertight")
    return mesh


def _surface_mesh_from_voxels(solid: np.ndarray, *, origin: np.ndarray, pitch: float) -> trimesh.Trimesh:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertex_ids: dict[tuple[int, int, int], int] = {}

    def vertex_id(corner: tuple[int, int, int]) -> int:
        if corner not in vertex_ids:
            vertex_ids[corner] = len(vertices)
            vertices.append(tuple((origin + np.asarray(corner, dtype=float) * pitch).tolist()))
        return vertex_ids[corner]

    face_defs = (
        ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
        ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
        ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
        ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
        ((0, 0, -1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
        ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    )
    shape = solid.shape
    for ix, iy, iz in np.argwhere(solid):
        ix = int(ix)
        iy = int(iy)
        iz = int(iz)
        for normal, corners in face_defs:
            nx, ny, nz = ix + normal[0], iy + normal[1], iz + normal[2]
            if 0 <= nx < shape[0] and 0 <= ny < shape[1] and 0 <= nz < shape[2] and solid[nx, ny, nz]:
                continue
            ids = [vertex_id((ix + cx, iy + cy, iz + cz)) for cx, cy, cz in corners]
            faces.append((ids[0], ids[1], ids[2]))
            faces.append((ids[0], ids[2], ids[3]))
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh
