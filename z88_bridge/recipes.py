"""Recipe helpers that turn user intent into Z88 run configs."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from .config import (
    LoadCase,
    MaterialSpec,
    OptimizerSettings,
    RegionSpec,
    SupportSpec,
    Z88RunConfig,
)


DEFAULT_PRESETS_ROOT = Path("presets")


class RecipeInputError(ValueError):
    """Raised when recipe inputs are invalid or do not match the STL bounds."""


@dataclass(frozen=True)
class BoxSelector:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]

    def to_selector(self) -> dict[str, Any]:
        return {
            "type": "box",
            "min": list(self.minimum),
            "max": list(self.maximum),
        }


@dataclass(frozen=True)
class GenericBracketInputs:
    units: str = "mm"
    material_key: str = "al_6061_t6"
    safety_preset: str = "consumer_drone"
    support_box: BoxSelector | None = None
    load_box: BoxSelector | None = None
    force: tuple[float, float, float] = (0.0, -100.0, 0.0)
    project_name: str = "generic_bracket"
    voxel_pitch: float = 1.0
    optimizer_method: str = "oc"
    volume_fraction: float = 0.4
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    notes: str = ""


@dataclass(frozen=True)
class DroneMotorMountInputs:
    units: str = "mm"
    material_key: str = "al_6061_t6"
    safety_preset: str = "consumer_drone"
    frame_support_box: BoxSelector | None = None
    motor_mount_box: BoxSelector | None = None
    thrust: float = 10.0
    thrust_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    prop_diameter: float | None = None
    project_name: str = "drone_motor_mount"
    voxel_pitch: float = 1.0
    optimizer_method: str = "oc"
    volume_fraction: float = 0.4
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    notes: str = ""


@dataclass(frozen=True)
class DroneLandingGearInputs:
    units: str = "mm"
    material_key: str = "pa12_sls"
    safety_preset: str = "consumer_drone"
    frame_support_box: BoxSelector | None = None
    ground_contact_box: BoxSelector | None = None
    payload_mass: float = 1.0
    impact_g: float = 3.0
    load_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    project_name: str = "drone_landing_gear"
    voxel_pitch: float = 1.0
    optimizer_method: str = "oc"
    volume_fraction: float = 0.45
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    notes: str = ""


@dataclass(frozen=True)
class DroneGimbalMountInputs:
    units: str = "mm"
    material_key: str = "pa12_sls"
    safety_preset: str = "consumer_drone"
    frame_support_box: BoxSelector | None = None
    camera_mount_box: BoxSelector | None = None
    camera_mass: float = 0.25
    maneuver_g: float = 3.0
    load_direction: tuple[float, float, float] = (0.0, -1.0, 0.0)
    target_vibration_frequency: float | None = None
    project_name: str = "drone_gimbal_mount"
    voxel_pitch: float = 1.0
    optimizer_method: str = "oc"
    volume_fraction: float = 0.35
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    notes: str = ""


@dataclass(frozen=True)
class RingWingStrutInputs:
    units: str = "mm"
    material_key: str = "cf_pa"
    safety_preset: str = "consumer_drone"
    root_support_box: BoxSelector | None = None
    wing_load_box: BoxSelector | None = None
    lift_force_per_strut: float = 25.0
    lift_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    project_name: str = "ring_wing_strut"
    voxel_pitch: float = 1.0
    optimizer_method: str = "oc"
    volume_fraction: float = 0.4
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    notes: str = ""


def load_material_presets(presets_root: str | Path = DEFAULT_PRESETS_ROOT) -> dict[str, MaterialSpec]:
    materials_dir = Path(presets_root) / "materials"
    if not materials_dir.is_dir():
        raise FileNotFoundError(f"Material preset directory not found: {materials_dir}")
    materials: dict[str, MaterialSpec] = {}
    for path in sorted(materials_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        materials[path.stem] = MaterialSpec(
            name=data["name"],
            young_modulus=float(data["young_modulus"]),
            poisson_ratio=float(data["poisson_ratio"]),
            density=float(data["density"]),
            stress_limit=float(data["stress_limit"]),
        )
    if not materials:
        raise FileNotFoundError(f"No material presets found under {materials_dir}")
    return materials


def load_safety_presets(presets_root: str | Path = DEFAULT_PRESETS_ROOT) -> dict[str, float]:
    path = Path(presets_root) / "safety_factors.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value["factor"]) for key, value in data.items()}


def configure_generic_bracket(
    stl_path: str | Path,
    inputs: GenericBracketInputs,
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Create a basic bracket run config from explicit support/load boxes."""
    stl_path = Path(stl_path)
    if inputs.support_box is None:
        raise RecipeInputError("generic_bracket requires support_box")
    if inputs.load_box is None:
        raise RecipeInputError("generic_bracket requires load_box")
    _validate_box(inputs.support_box, "support_box")
    _validate_box(inputs.load_box, "load_box")
    _validate_force(inputs.force)

    if validate_geometry:
        bounds = _load_stl_bounds(stl_path)
        _require_box_intersects_bounds(inputs.support_box, bounds, "support_box")
        _require_box_intersects_bounds(inputs.load_box, bounds, "load_box")

    materials = load_material_presets(presets_root)
    try:
        material = materials[inputs.material_key]
    except KeyError as exc:
        raise RecipeInputError(
            f"Unknown material preset {inputs.material_key!r}. Choices: {', '.join(sorted(materials))}"
        ) from exc
    safety_factor = _safety_factor(inputs.safety_preset, presets_root)

    support_region = RegionSpec(
        name="generic_bracket_support",
        selector=inputs.support_box.to_selector(),
        role="support",
    )
    load_region = RegionSpec(
        name="generic_bracket_load",
        selector=inputs.load_box.to_selector(),
        role="load",
    )
    notes = _recipe_notes(inputs, material, safety_factor)
    return Z88RunConfig(
        input_stl=str(stl_path),
        units=inputs.units,
        project_name=inputs.project_name,
        voxel_pitch=inputs.voxel_pitch,
        material=material,
        optimizer=OptimizerSettings(
            method=inputs.optimizer_method,
            volume_fraction=inputs.volume_fraction,
            max_iterations=inputs.max_iterations,
            convergence_tolerance=inputs.convergence_tolerance,
        ),
        supports=(SupportSpec(name="fixed_support", region=support_region),),
        loads=(LoadCase(name="primary_load", region=load_region, force=inputs.force),),
        safety_factor=safety_factor,
        notes=notes,
    )


def configure_drone_motor_mount(
    stl_path: str | Path,
    inputs: DroneMotorMountInputs,
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Create a drone motor mount config from explicit frame and motor boxes."""
    stl_path = Path(stl_path)
    if inputs.frame_support_box is None:
        raise RecipeInputError("drone_motor_mount requires frame_support_box")
    if inputs.motor_mount_box is None:
        raise RecipeInputError("drone_motor_mount requires motor_mount_box")
    _validate_box(inputs.frame_support_box, "frame_support_box")
    _validate_box(inputs.motor_mount_box, "motor_mount_box")
    if inputs.thrust <= 0:
        raise RecipeInputError("thrust must be positive")
    direction = _normalize(inputs.thrust_direction, "thrust_direction")
    force = tuple(inputs.thrust * component for component in direction)

    if validate_geometry:
        bounds = _load_stl_bounds(stl_path)
        _require_box_intersects_bounds(inputs.frame_support_box, bounds, "frame_support_box")
        _require_box_intersects_bounds(inputs.motor_mount_box, bounds, "motor_mount_box")

    materials = load_material_presets(presets_root)
    try:
        material = materials[inputs.material_key]
    except KeyError as exc:
        raise RecipeInputError(
            f"Unknown material preset {inputs.material_key!r}. Choices: {', '.join(sorted(materials))}"
        ) from exc
    safety_factor = _safety_factor(inputs.safety_preset, presets_root)
    support_region = RegionSpec(
        name="frame_support",
        selector=inputs.frame_support_box.to_selector(),
        role="support",
    )
    load_region = RegionSpec(
        name="motor_thrust_interface",
        selector=inputs.motor_mount_box.to_selector(),
        role="load",
    )
    notes = _drone_motor_mount_notes(inputs, material, safety_factor, force)
    return Z88RunConfig(
        input_stl=str(stl_path),
        units=inputs.units,
        project_name=inputs.project_name,
        voxel_pitch=inputs.voxel_pitch,
        material=material,
        optimizer=OptimizerSettings(
            method=inputs.optimizer_method,
            volume_fraction=inputs.volume_fraction,
            max_iterations=inputs.max_iterations,
            convergence_tolerance=inputs.convergence_tolerance,
        ),
        supports=(SupportSpec(name="frame_fixed_support", region=support_region),),
        loads=(LoadCase(name="motor_thrust", region=load_region, force=force),),
        safety_factor=safety_factor,
        notes=notes,
    )


def configure_drone_landing_gear(
    stl_path: str | Path,
    inputs: DroneLandingGearInputs,
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Create a landing gear config from explicit frame and ground-contact boxes."""
    stl_path = Path(stl_path)
    if inputs.frame_support_box is None:
        raise RecipeInputError("drone_landing_gear requires frame_support_box")
    if inputs.ground_contact_box is None:
        raise RecipeInputError("drone_landing_gear requires ground_contact_box")
    _validate_box(inputs.frame_support_box, "frame_support_box")
    _validate_box(inputs.ground_contact_box, "ground_contact_box")
    _validate_positive(inputs.payload_mass, "payload_mass")
    _validate_positive(inputs.impact_g, "impact_g")
    direction = _normalize(inputs.load_direction, "load_direction")
    force_magnitude = inputs.payload_mass * 9.80665 * inputs.impact_g
    force = tuple(force_magnitude * component for component in direction)

    if validate_geometry:
        bounds = _load_stl_bounds(stl_path)
        _require_box_intersects_bounds(inputs.frame_support_box, bounds, "frame_support_box")
        _require_box_intersects_bounds(inputs.ground_contact_box, bounds, "ground_contact_box")

    material = _material(inputs.material_key, presets_root)
    safety_factor = _safety_factor(inputs.safety_preset, presets_root)
    support_region = RegionSpec(
        name="landing_gear_frame_support",
        selector=inputs.frame_support_box.to_selector(),
        role="support",
    )
    load_region = RegionSpec(
        name="landing_gear_ground_contact",
        selector=inputs.ground_contact_box.to_selector(),
        role="load",
    )
    notes = _drone_landing_gear_notes(inputs, material, safety_factor, force)
    return Z88RunConfig(
        input_stl=str(stl_path),
        units=inputs.units,
        project_name=inputs.project_name,
        voxel_pitch=inputs.voxel_pitch,
        material=material,
        optimizer=OptimizerSettings(
            method=inputs.optimizer_method,
            volume_fraction=inputs.volume_fraction,
            max_iterations=inputs.max_iterations,
            convergence_tolerance=inputs.convergence_tolerance,
        ),
        supports=(SupportSpec(name="frame_fixed_support", region=support_region),),
        loads=(LoadCase(name="landing_impact", region=load_region, force=force),),
        safety_factor=safety_factor,
        notes=notes,
    )


def configure_drone_gimbal_mount(
    stl_path: str | Path,
    inputs: DroneGimbalMountInputs,
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Create a gimbal mount config from explicit frame and camera-interface boxes."""
    stl_path = Path(stl_path)
    if inputs.frame_support_box is None:
        raise RecipeInputError("drone_gimbal_mount requires frame_support_box")
    if inputs.camera_mount_box is None:
        raise RecipeInputError("drone_gimbal_mount requires camera_mount_box")
    _validate_box(inputs.frame_support_box, "frame_support_box")
    _validate_box(inputs.camera_mount_box, "camera_mount_box")
    _validate_positive(inputs.camera_mass, "camera_mass")
    _validate_positive(inputs.maneuver_g, "maneuver_g")
    if inputs.target_vibration_frequency is not None:
        _validate_positive(inputs.target_vibration_frequency, "target_vibration_frequency")
    direction = _normalize(inputs.load_direction, "load_direction")
    force_magnitude = inputs.camera_mass * 9.80665 * inputs.maneuver_g
    force = tuple(force_magnitude * component for component in direction)

    if validate_geometry:
        bounds = _load_stl_bounds(stl_path)
        _require_box_intersects_bounds(inputs.frame_support_box, bounds, "frame_support_box")
        _require_box_intersects_bounds(inputs.camera_mount_box, bounds, "camera_mount_box")

    material = _material(inputs.material_key, presets_root)
    safety_factor = _safety_factor(inputs.safety_preset, presets_root)
    support_region = RegionSpec(
        name="gimbal_frame_support",
        selector=inputs.frame_support_box.to_selector(),
        role="support",
    )
    load_region = RegionSpec(
        name="camera_mount_interface",
        selector=inputs.camera_mount_box.to_selector(),
        role="load",
    )
    notes = _drone_gimbal_mount_notes(inputs, material, safety_factor, force)
    return Z88RunConfig(
        input_stl=str(stl_path),
        units=inputs.units,
        project_name=inputs.project_name,
        voxel_pitch=inputs.voxel_pitch,
        material=material,
        optimizer=OptimizerSettings(
            method=inputs.optimizer_method,
            volume_fraction=inputs.volume_fraction,
            max_iterations=inputs.max_iterations,
            convergence_tolerance=inputs.convergence_tolerance,
        ),
        supports=(SupportSpec(name="frame_fixed_support", region=support_region),),
        loads=(LoadCase(name="camera_inertial_load", region=load_region, force=force),),
        safety_factor=safety_factor,
        notes=notes,
    )


def configure_ring_wing_strut(
    stl_path: str | Path,
    inputs: RingWingStrutInputs,
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Create a ring-wing strut config from explicit root and wing-interface boxes."""
    stl_path = Path(stl_path)
    if inputs.root_support_box is None:
        raise RecipeInputError("ring_wing_strut requires root_support_box")
    if inputs.wing_load_box is None:
        raise RecipeInputError("ring_wing_strut requires wing_load_box")
    _validate_box(inputs.root_support_box, "root_support_box")
    _validate_box(inputs.wing_load_box, "wing_load_box")
    _validate_positive(inputs.lift_force_per_strut, "lift_force_per_strut")
    direction = _normalize(inputs.lift_direction, "lift_direction")
    force = tuple(inputs.lift_force_per_strut * component for component in direction)

    if validate_geometry:
        bounds = _load_stl_bounds(stl_path)
        _require_box_intersects_bounds(inputs.root_support_box, bounds, "root_support_box")
        _require_box_intersects_bounds(inputs.wing_load_box, bounds, "wing_load_box")

    material = _material(inputs.material_key, presets_root)
    safety_factor = _safety_factor(inputs.safety_preset, presets_root)
    support_region = RegionSpec(
        name="strut_root_support",
        selector=inputs.root_support_box.to_selector(),
        role="support",
    )
    load_region = RegionSpec(
        name="ring_wing_lift_interface",
        selector=inputs.wing_load_box.to_selector(),
        role="load",
    )
    notes = _ring_wing_strut_notes(inputs, material, safety_factor, force)
    return Z88RunConfig(
        input_stl=str(stl_path),
        units=inputs.units,
        project_name=inputs.project_name,
        voxel_pitch=inputs.voxel_pitch,
        material=material,
        optimizer=OptimizerSettings(
            method=inputs.optimizer_method,
            volume_fraction=inputs.volume_fraction,
            max_iterations=inputs.max_iterations,
            convergence_tolerance=inputs.convergence_tolerance,
        ),
        supports=(SupportSpec(name="root_fixed_support", region=support_region),),
        loads=(LoadCase(name="wing_lift_load", region=load_region, force=force),),
        safety_factor=safety_factor,
        notes=notes,
    )


def available_recipes() -> dict[str, dict[str, Any]]:
    return {
        "generic_bracket": {
            "description": "Explicit support/load box bracket setup.",
            "required_regions": ("support_box", "load_box"),
            "loads": ("force",),
        },
        "drone_motor_mount": {
            "description": "Frame-fixed motor mount with thrust applied at the motor interface.",
            "required_regions": ("frame_support_box", "motor_mount_box"),
            "loads": ("thrust", "thrust_direction"),
        },
        "drone_landing_gear": {
            "description": "Frame-fixed landing gear with impact load at the ground contact interface.",
            "required_regions": ("frame_support_box", "ground_contact_box"),
            "loads": ("payload_mass", "impact_g", "load_direction"),
        },
        "drone_gimbal_mount": {
            "description": "Frame-fixed camera/gimbal mount with inertial camera load.",
            "required_regions": ("frame_support_box", "camera_mount_box"),
            "loads": ("camera_mass", "maneuver_g", "load_direction"),
        },
        "ring_wing_strut": {
            "description": "Root-fixed ring-wing strut with lift load at the wing interface.",
            "required_regions": ("root_support_box", "wing_load_box"),
            "loads": ("lift_force_per_strut", "lift_direction"),
        },
    }


def configure_recipe_from_payload(
    payload: dict[str, Any],
    *,
    presets_root: str | Path = DEFAULT_PRESETS_ROOT,
    validate_geometry: bool = True,
) -> Z88RunConfig:
    """Build a recipe config from the JSON payload used by CLI/API/UI surfaces."""
    recipe = str(payload.get("recipe", ""))
    stl_path = payload.get("stl_path")
    if not stl_path:
        raise RecipeInputError("stl_path is required")
    material_key = payload.get("material") or _default_material(recipe)
    project_name = payload.get("project_name") or recipe
    volume_fraction = float(payload.get("volume_fraction", _default_volume_fraction(recipe)))
    common = {
        "units": payload.get("units", "mm"),
        "material_key": material_key,
        "safety_preset": payload.get("safety_preset", "consumer_drone"),
        "project_name": project_name,
        "voxel_pitch": float(payload.get("voxel_pitch", 1.0)),
        "volume_fraction": volume_fraction,
        "max_iterations": int(payload.get("max_iterations", 120)),
        "convergence_tolerance": float(payload.get("convergence_tolerance", 1e-3)),
    }
    if recipe == "generic_bracket":
        return configure_generic_bracket(
            stl_path,
            GenericBracketInputs(
                **common,
                support_box=_box_from_payload(payload, "support_box"),
                load_box=_box_from_payload(payload, "load_box"),
                force=_vector_from_payload(payload, "force", default=(0.0, -100.0, 0.0)),
            ),
            presets_root=presets_root,
            validate_geometry=validate_geometry,
        )
    if recipe == "drone_motor_mount":
        return configure_drone_motor_mount(
            stl_path,
            DroneMotorMountInputs(
                **common,
                frame_support_box=_box_from_payload(payload, "frame_support_box"),
                motor_mount_box=_box_from_payload(payload, "motor_mount_box"),
                thrust=_required_float_payload(payload, "thrust"),
                thrust_direction=_vector_from_payload(payload, "thrust_direction", default=(0.0, 0.0, 1.0)),
                prop_diameter=_optional_float_payload(payload, "prop_diameter"),
            ),
            presets_root=presets_root,
            validate_geometry=validate_geometry,
        )
    if recipe == "drone_landing_gear":
        return configure_drone_landing_gear(
            stl_path,
            DroneLandingGearInputs(
                **common,
                frame_support_box=_box_from_payload(payload, "frame_support_box"),
                ground_contact_box=_box_from_payload(payload, "ground_contact_box"),
                payload_mass=_required_float_payload(payload, "payload_mass"),
                impact_g=float(payload.get("impact_g", 3.0)),
                load_direction=_vector_from_payload(payload, "load_direction", default=(0.0, 0.0, 1.0)),
            ),
            presets_root=presets_root,
            validate_geometry=validate_geometry,
        )
    if recipe == "drone_gimbal_mount":
        return configure_drone_gimbal_mount(
            stl_path,
            DroneGimbalMountInputs(
                **common,
                frame_support_box=_box_from_payload(payload, "frame_support_box"),
                camera_mount_box=_box_from_payload(payload, "camera_mount_box"),
                camera_mass=_required_float_payload(payload, "camera_mass"),
                maneuver_g=float(payload.get("maneuver_g", 3.0)),
                load_direction=_vector_from_payload(payload, "load_direction", default=(0.0, -1.0, 0.0)),
                target_vibration_frequency=_optional_float_payload(payload, "target_vibration_frequency"),
            ),
            presets_root=presets_root,
            validate_geometry=validate_geometry,
        )
    if recipe == "ring_wing_strut":
        return configure_ring_wing_strut(
            stl_path,
            RingWingStrutInputs(
                **common,
                root_support_box=_box_from_payload(payload, "root_support_box"),
                wing_load_box=_box_from_payload(payload, "wing_load_box"),
                lift_force_per_strut=_required_float_payload(payload, "lift_force_per_strut"),
                lift_direction=_vector_from_payload(payload, "lift_direction", default=(0.0, 0.0, 1.0)),
            ),
            presets_root=presets_root,
            validate_geometry=validate_geometry,
        )
    raise RecipeInputError(f"Unknown recipe {recipe!r}. Choices: {', '.join(sorted(available_recipes()))}")


def inspect_stl_geometry(stl_path: str | Path) -> dict[str, Any]:
    """Return bounded mesh metadata for UI and recipe preflight checks."""
    stl_path = Path(stl_path)
    if not stl_path.is_file():
        raise FileNotFoundError(f"STL not found: {stl_path}")
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    if mesh.is_empty:
        raise RecipeInputError(f"STL mesh is empty: {stl_path}")
    bounds = np.asarray(mesh.bounds, dtype=float)
    extents = np.asarray(mesh.extents, dtype=float)
    center = np.asarray(mesh.centroid, dtype=float)
    return {
        "path": str(stl_path.resolve()),
        "bounds": {
            "min": [float(value) for value in bounds[0]],
            "max": [float(value) for value in bounds[1]],
        },
        "extents": [float(value) for value in extents],
        "center": [float(value) for value in center],
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume": float(mesh.volume) if mesh.is_watertight else None,
        "area": float(mesh.area),
    }


def suggest_end_boxes_from_stl(
    stl_path: str | Path,
    *,
    axis: str = "longest",
    thickness_fraction: float = 0.1,
    minimum_thickness: float | None = None,
) -> dict[str, Any]:
    """Suggest simple support/load slabs at opposite ends of an STL bounding box."""
    if not math.isfinite(thickness_fraction) or not (0.0 < thickness_fraction <= 0.5):
        raise RecipeInputError("thickness_fraction must be finite and in (0, 0.5]")
    geometry = inspect_stl_geometry(stl_path)
    lower = geometry["bounds"]["min"]
    upper = geometry["bounds"]["max"]
    extents = [upper[index] - lower[index] for index in range(3)]
    axis_index = _axis_index(axis, extents)
    thickness = extents[axis_index] * thickness_fraction
    if minimum_thickness is not None:
        if not math.isfinite(minimum_thickness) or minimum_thickness <= 0.0:
            raise RecipeInputError("minimum_thickness must be positive and finite")
        thickness = max(thickness, minimum_thickness)
    thickness = min(thickness, extents[axis_index])
    support_min = list(lower)
    support_max = list(upper)
    load_min = list(lower)
    load_max = list(upper)
    support_max[axis_index] = min(upper[axis_index], lower[axis_index] + thickness)
    load_min[axis_index] = max(lower[axis_index], upper[axis_index] - thickness)
    return {
        "axis": ("x", "y", "z")[axis_index],
        "thickness": float(thickness),
        "support_box": {"min": support_min, "max": support_max},
        "load_box": {"min": load_min, "max": load_max},
        "geometry": geometry,
        "warnings": (
            "Suggested boxes are bounding-box slabs only; inspect and adjust them before engineering use.",
        ),
    }


def _material(material_key: str, presets_root: str | Path) -> MaterialSpec:
    materials = load_material_presets(presets_root)
    try:
        return materials[material_key]
    except KeyError as exc:
        raise RecipeInputError(
            f"Unknown material preset {material_key!r}. Choices: {', '.join(sorted(materials))}"
        ) from exc


def _safety_factor(name: str, presets_root: str | Path) -> float:
    safety_presets = load_safety_presets(presets_root)
    try:
        return safety_presets[name]
    except KeyError as exc:
        raise RecipeInputError(
            f"Unknown safety preset {name!r}. Choices: {', '.join(sorted(safety_presets))}"
        ) from exc


def _default_material(recipe: str) -> str:
    return {
        "drone_landing_gear": "pa12_sls",
        "drone_gimbal_mount": "pa12_sls",
        "ring_wing_strut": "cf_pa",
    }.get(recipe, "al_6061_t6")


def _default_volume_fraction(recipe: str) -> float:
    return {
        "drone_landing_gear": 0.45,
        "drone_gimbal_mount": 0.35,
    }.get(recipe, 0.4)


def _box_from_payload(payload: dict[str, Any], label: str) -> BoxSelector | None:
    value = payload.get(label)
    if value is None:
        return None
    try:
        minimum = tuple(float(item) for item in value["min"])
        maximum = tuple(float(item) for item in value["max"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RecipeInputError(f"{label} must have min and max arrays") from exc
    return BoxSelector(minimum, maximum)


def _vector_from_payload(
    payload: dict[str, Any],
    label: str,
    *,
    default: tuple[float, float, float],
) -> tuple[float, float, float]:
    raw = payload.get(label, default)
    try:
        vector = tuple(float(item) for item in raw)
    except (TypeError, ValueError) as exc:
        raise RecipeInputError(f"{label} must be a numeric vector") from exc
    return vector


def _required_float_payload(payload: dict[str, Any], label: str) -> float:
    if payload.get(label) is None:
        raise RecipeInputError(f"{label} is required")
    return float(payload[label])


def _optional_float_payload(payload: dict[str, Any], label: str) -> float | None:
    if payload.get(label) is None:
        return None
    return float(payload[label])


def _axis_index(axis: str, extents: list[float]) -> int:
    if axis == "longest":
        return max(range(3), key=lambda index: extents[index])
    mapping = {"x": 0, "y": 1, "z": 2}
    try:
        return mapping[axis.lower()]
    except KeyError as exc:
        raise RecipeInputError("axis must be one of 'longest', 'x', 'y', or 'z'") from exc


def _validate_box(box: BoxSelector, label: str) -> None:
    if len(box.minimum) != 3 or len(box.maximum) != 3:
        raise RecipeInputError(f"{label} must have three min and max coordinates")
    for value in (*box.minimum, *box.maximum):
        if not math.isfinite(value):
            raise RecipeInputError(f"{label} coordinates must be finite")
    if any(high <= low for low, high in zip(box.minimum, box.maximum)):
        raise RecipeInputError(f"{label} max coordinates must be greater than min coordinates")


def _validate_force(force: tuple[float, float, float]) -> None:
    if len(force) != 3:
        raise RecipeInputError("force must have three components")
    if any(not math.isfinite(component) for component in force):
        raise RecipeInputError("force vector must be finite")
    if all(component == 0.0 for component in force):
        raise RecipeInputError("force vector must be nonzero")


def _normalize(vector: tuple[float, float, float], label: str) -> tuple[float, float, float]:
    if len(vector) != 3:
        raise RecipeInputError(f"{label} must have three components")
    if any(not math.isfinite(component) for component in vector):
        raise RecipeInputError(f"{label} must be finite")
    magnitude = sum(component * component for component in vector) ** 0.5
    if magnitude == 0.0:
        raise RecipeInputError(f"{label} must be nonzero")
    return tuple(component / magnitude for component in vector)


def _validate_positive(value: float, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise RecipeInputError(f"{label} must be positive and finite")


def _load_stl_bounds(stl_path: Path) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if not stl_path.is_file():
        raise FileNotFoundError(f"STL not found: {stl_path}")
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    if mesh.is_empty:
        raise RecipeInputError(f"STL mesh is empty: {stl_path}")
    bounds = mesh.bounds
    return tuple(float(value) for value in bounds[0]), tuple(float(value) for value in bounds[1])


def _require_box_intersects_bounds(
    box: BoxSelector,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    label: str,
) -> None:
    lower, upper = bounds
    intersects = all(box.maximum[index] >= lower[index] and box.minimum[index] <= upper[index] for index in range(3))
    if not intersects:
        raise RecipeInputError(f"{label} does not intersect STL bounds {lower} to {upper}")


def _recipe_notes(inputs: GenericBracketInputs, material: MaterialSpec, safety_factor: float) -> str:
    generated = (
        "Recipe: generic_bracket. "
        f"Material preset: {inputs.material_key} ({material.name}). "
        f"Safety preset: {inputs.safety_preset} ({safety_factor}x). "
        "Support and load regions were provided as explicit axis-aligned boxes; "
        "verify these selections before trusting a solve."
    )
    return f"{generated}\n{inputs.notes}".strip()


def _drone_motor_mount_notes(
    inputs: DroneMotorMountInputs,
    material: MaterialSpec,
    safety_factor: float,
    force: tuple[float, float, float],
) -> str:
    prop = f" Prop diameter: {inputs.prop_diameter} {inputs.units}." if inputs.prop_diameter else ""
    generated = (
        "Recipe: drone_motor_mount. "
        f"Material preset: {inputs.material_key} ({material.name}). "
        f"Safety preset: {inputs.safety_preset} ({safety_factor}x). "
        f"Thrust load: {inputs.thrust} in normalized direction {inputs.thrust_direction}; "
        f"applied force vector: {force}.{prop} "
        "Frame support and motor interface regions were provided as explicit axis-aligned boxes; "
        "verify these selections and thrust direction before trusting a solve."
    )
    return f"{generated}\n{inputs.notes}".strip()


def _drone_landing_gear_notes(
    inputs: DroneLandingGearInputs,
    material: MaterialSpec,
    safety_factor: float,
    force: tuple[float, float, float],
) -> str:
    generated = (
        "Recipe: drone_landing_gear. "
        f"Material preset: {inputs.material_key} ({material.name}). "
        f"Safety preset: {inputs.safety_preset} ({safety_factor}x). "
        f"Payload mass: {inputs.payload_mass} kg. Impact factor: {inputs.impact_g} g. "
        f"Applied contact load vector: {force}. "
        "This is a static equivalent impact load, not a transient landing simulation. "
        "Frame support and ground-contact regions were provided as explicit axis-aligned boxes."
    )
    return f"{generated}\n{inputs.notes}".strip()


def _drone_gimbal_mount_notes(
    inputs: DroneGimbalMountInputs,
    material: MaterialSpec,
    safety_factor: float,
    force: tuple[float, float, float],
) -> str:
    frequency = (
        f" Target vibration frequency: {inputs.target_vibration_frequency} Hz."
        if inputs.target_vibration_frequency
        else " No modal/frequency constraint is solved yet."
    )
    generated = (
        "Recipe: drone_gimbal_mount. "
        f"Material preset: {inputs.material_key} ({material.name}). "
        f"Safety preset: {inputs.safety_preset} ({safety_factor}x). "
        f"Camera mass: {inputs.camera_mass} kg. Maneuver factor: {inputs.maneuver_g} g. "
        f"Applied camera interface load vector: {force}.{frequency} "
        "Frame support and camera interface regions were provided as explicit axis-aligned boxes."
    )
    return f"{generated}\n{inputs.notes}".strip()


def _ring_wing_strut_notes(
    inputs: RingWingStrutInputs,
    material: MaterialSpec,
    safety_factor: float,
    force: tuple[float, float, float],
) -> str:
    generated = (
        "Recipe: ring_wing_strut. "
        f"Material preset: {inputs.material_key} ({material.name}). "
        f"Safety preset: {inputs.safety_preset} ({safety_factor}x). "
        f"Lift force per strut: {inputs.lift_force_per_strut}. "
        f"Applied wing-interface load vector: {force}. "
        "Root support and wing interface regions were provided as explicit axis-aligned boxes."
    )
    return f"{generated}\n{inputs.notes}".strip()
