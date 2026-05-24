from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from z88_bridge import (
    BoxSelector,
    DroneGimbalMountInputs,
    DroneLandingGearInputs,
    DroneMotorMountInputs,
    GenericBracketInputs,
    RecipeInputError,
    RingWingStrutInputs,
    available_recipes,
    configure_drone_gimbal_mount,
    configure_drone_landing_gear,
    configure_drone_motor_mount,
    configure_generic_bracket,
    configure_recipe_from_payload,
    configure_ring_wing_strut,
    inspect_stl_geometry,
    load_material_presets,
    load_safety_presets,
    suggest_end_boxes_from_stl,
)


def _box_stl(path: Path) -> Path:
    mesh = trimesh.creation.box(extents=(10.0, 4.0, 2.0))
    mesh.export(path)
    return path


def test_material_and_safety_presets_load() -> None:
    materials = load_material_presets()
    safety = load_safety_presets()

    assert {"al_6061_t6", "al_7075_t6", "ti_6al_4v", "pa12_sls", "petg", "cf_pa"} <= set(materials)
    assert materials["al_6061_t6"].young_modulus > 0
    assert safety["consumer_drone"] == 1.5


def test_available_recipes_lists_all_supported_recipes() -> None:
    recipes = available_recipes()

    assert {
        "generic_bracket",
        "drone_motor_mount",
        "drone_landing_gear",
        "drone_gimbal_mount",
        "ring_wing_strut",
    } <= set(recipes)


def test_generic_bracket_recipe_creates_valid_config(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_generic_bracket(
        stl,
        GenericBracketInputs(
            project_name="bracket_test",
            support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
            load_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            force=(0.0, -250.0, 0.0),
            material_key="al_7075_t6",
            safety_preset="aerospace",
        ),
    )

    config.validate()
    assert config.project_name == "bracket_test"
    assert config.material.name == "Al 7075-T6"
    assert config.safety_factor == 2.0
    assert config.supports[0].region.selector["type"] == "box"
    assert config.loads[0].force == (0.0, -250.0, 0.0)
    assert "generic_bracket" in config.notes


def test_configure_recipe_from_payload_matches_ui_contract(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_recipe_from_payload(
        {
            "recipe": "generic_bracket",
            "stl_path": str(stl),
            "project_name": "payload_bracket",
            "support_box": {"min": [-5.0, -2.0, -1.0], "max": [-4.0, 2.0, 1.0]},
            "load_box": {"min": [4.0, -2.0, -1.0], "max": [5.0, 2.0, 1.0]},
            "force": [0.0, -250.0, 0.0],
            "volume_fraction": 0.5,
        }
    )

    config.validate()
    assert config.project_name == "payload_bracket"
    assert config.optimizer.volume_fraction == 0.5
    assert config.loads[0].force == (0.0, -250.0, 0.0)


def test_inspect_stl_geometry_reports_bounds_and_mesh_counts(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    geometry = inspect_stl_geometry(stl)

    assert geometry["bounds"]["min"] == [-5.0, -2.0, -1.0]
    assert geometry["bounds"]["max"] == [5.0, 2.0, 1.0]
    assert geometry["watertight"] is True
    assert geometry["faces"] > 0


def test_suggest_end_boxes_from_stl_uses_longest_axis(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    suggestion = suggest_end_boxes_from_stl(stl, thickness_fraction=0.1)

    assert suggestion["axis"] == "x"
    assert suggestion["support_box"]["min"] == [-5.0, -2.0, -1.0]
    assert suggestion["support_box"]["max"][0] == -4.0
    assert suggestion["load_box"]["min"][0] == 4.0
    assert suggestion["load_box"]["max"] == [5.0, 2.0, 1.0]


def test_generic_bracket_recipe_rejects_non_intersecting_regions(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="support_box does not intersect"):
        configure_generic_bracket(
            stl,
            GenericBracketInputs(
                support_box=BoxSelector((20.0, 20.0, 20.0), (21.0, 21.0, 21.0)),
                load_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
                force=(0.0, -250.0, 0.0),
            ),
        )


def test_generic_bracket_recipe_rejects_zero_force(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="force vector"):
        configure_generic_bracket(
            stl,
            GenericBracketInputs(
                support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
                load_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
                force=(0.0, 0.0, 0.0),
            ),
        )


def test_drone_motor_mount_recipe_creates_thrust_load_config(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_drone_motor_mount(
        stl,
        DroneMotorMountInputs(
            project_name="motor_mount",
            frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
            motor_mount_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            thrust=25.0,
            thrust_direction=(0.0, 0.0, 2.0),
            prop_diameter=10.0,
        ),
    )

    config.validate()
    assert config.project_name == "motor_mount"
    assert config.loads[0].force == (0.0, 0.0, 25.0)
    assert config.supports[0].region.name == "frame_support"
    assert "drone_motor_mount" in config.notes
    assert "Prop diameter" in config.notes


def test_drone_motor_mount_recipe_rejects_zero_thrust_direction(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="thrust_direction"):
        configure_drone_motor_mount(
            stl,
            DroneMotorMountInputs(
                frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
                motor_mount_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
                thrust=25.0,
                thrust_direction=(0.0, 0.0, 0.0),
            ),
        )


def test_drone_landing_gear_recipe_creates_static_impact_load(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_drone_landing_gear(
        stl,
        DroneLandingGearInputs(
            project_name="landing",
            frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
            ground_contact_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            payload_mass=2.0,
            impact_g=4.0,
            load_direction=(0.0, 0.0, 2.0),
        ),
    )

    config.validate()
    assert config.project_name == "landing"
    assert config.loads[0].force == (0.0, 0.0, 2.0 * 9.80665 * 4.0)
    assert config.material.name == "PA12 SLS"
    assert "static equivalent impact load" in config.notes


def test_drone_landing_gear_recipe_rejects_bad_payload(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="payload_mass"):
        configure_drone_landing_gear(
            stl,
            DroneLandingGearInputs(
                frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
                ground_contact_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
                payload_mass=0.0,
            ),
        )


def test_drone_gimbal_mount_recipe_creates_inertial_load(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_drone_gimbal_mount(
        stl,
        DroneGimbalMountInputs(
            project_name="gimbal",
            frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
            camera_mount_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            camera_mass=0.4,
            maneuver_g=2.5,
            load_direction=(0.0, -2.0, 0.0),
            target_vibration_frequency=120.0,
        ),
    )

    config.validate()
    assert config.project_name == "gimbal"
    assert config.loads[0].force == (0.0, -0.4 * 9.80665 * 2.5, 0.0)
    assert "Target vibration frequency" in config.notes


def test_drone_gimbal_mount_recipe_rejects_bad_frequency(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="target_vibration_frequency"):
        configure_drone_gimbal_mount(
            stl,
            DroneGimbalMountInputs(
                frame_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
                camera_mount_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
                target_vibration_frequency=-1.0,
            ),
        )


def test_ring_wing_strut_recipe_creates_lift_load(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    config = configure_ring_wing_strut(
        stl,
        RingWingStrutInputs(
            project_name="strut",
            root_support_box=BoxSelector((-5.0, -2.0, -1.0), (-4.0, 2.0, 1.0)),
            wing_load_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            lift_force_per_strut=30.0,
            lift_direction=(0.0, 0.0, 3.0),
        ),
    )

    config.validate()
    assert config.project_name == "strut"
    assert config.loads[0].force == (0.0, 0.0, 30.0)
    assert config.material.name == "CF-PA"
    assert "ring_wing_strut" in config.notes


def test_recipe_rejects_non_finite_box(tmp_path: Path) -> None:
    stl = _box_stl(tmp_path / "box.stl")

    with pytest.raises(RecipeInputError, match="coordinates must be finite"):
        configure_ring_wing_strut(
            stl,
            RingWingStrutInputs(
                root_support_box=BoxSelector((float("nan"), -2.0, -1.0), (-4.0, 2.0, 1.0)),
                wing_load_box=BoxSelector((4.0, -2.0, -1.0), (5.0, 2.0, 1.0)),
            ),
        )
