"""Deterministic sample STL generation for packaging and workflow smoke tests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

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


def generate_sample_assets(output_dir: str | Path) -> dict[str, Any]:
    """Write small watertight STL samples and a catalog JSON file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog: list[dict[str, Any]] = []
    for sample in SAMPLE_ASSETS:
        stl_path = output_dir / sample.filename
        mesh = trimesh.creation.box(extents=sample.extents)
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
