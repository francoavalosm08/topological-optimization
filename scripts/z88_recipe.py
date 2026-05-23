"""Create Z88 run folders from high-level recipe inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import (
    BoxSelector,
    DroneGimbalMountInputs,
    DroneLandingGearInputs,
    DroneMotorMountInputs,
    GenericBracketInputs,
    RingWingStrutInputs,
    configure_drone_gimbal_mount,
    configure_drone_landing_gear,
    Z88Adapter,
    configure_drone_motor_mount,
    configure_generic_bracket,
    configure_ring_wing_strut,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="recipe", required=True)
    bracket = subparsers.add_parser("generic_bracket", help="Explicit support/load box bracket recipe")
    bracket.add_argument("--stl", required=True)
    bracket.add_argument("--units", default="mm")
    bracket.add_argument("--project-name", default="generic_bracket")
    bracket.add_argument("--material", default="al_6061_t6")
    bracket.add_argument("--safety-preset", default="consumer_drone")
    bracket.add_argument("--support-min", required=True, help="Comma-separated x,y,z")
    bracket.add_argument("--support-max", required=True, help="Comma-separated x,y,z")
    bracket.add_argument("--load-min", required=True, help="Comma-separated x,y,z")
    bracket.add_argument("--load-max", required=True, help="Comma-separated x,y,z")
    bracket.add_argument("--force", required=True, help="Comma-separated Fx,Fy,Fz")
    bracket.add_argument("--volume-fraction", type=float, default=0.4)
    bracket.add_argument("--voxel-pitch", type=float, default=1.0)
    bracket.add_argument("--max-iterations", type=int, default=120)
    bracket.add_argument("--convergence-tolerance", type=float, default=1e-3)
    bracket.add_argument("--install-root", help="Override Z88Arion install root")
    bracket.add_argument("--runs-root", default="runs/z88")
    bracket.add_argument("--config-out", help="Write only config JSON to this path instead of preparing a run folder")
    motor = subparsers.add_parser("drone_motor_mount", help="Explicit box drone motor mount recipe")
    motor.add_argument("--stl", required=True)
    motor.add_argument("--units", default="mm")
    motor.add_argument("--project-name", default="drone_motor_mount")
    motor.add_argument("--material", default="al_6061_t6")
    motor.add_argument("--safety-preset", default="consumer_drone")
    motor.add_argument("--frame-min", required=True, help="Comma-separated x,y,z")
    motor.add_argument("--frame-max", required=True, help="Comma-separated x,y,z")
    motor.add_argument("--motor-min", required=True, help="Comma-separated x,y,z")
    motor.add_argument("--motor-max", required=True, help="Comma-separated x,y,z")
    motor.add_argument("--thrust", required=True, type=float)
    motor.add_argument("--thrust-direction", default="0,0,1", help="Comma-separated unit or non-unit vector")
    motor.add_argument("--prop-diameter", type=float)
    motor.add_argument("--volume-fraction", type=float, default=0.4)
    motor.add_argument("--voxel-pitch", type=float, default=1.0)
    motor.add_argument("--max-iterations", type=int, default=120)
    motor.add_argument("--convergence-tolerance", type=float, default=1e-3)
    motor.add_argument("--install-root", help="Override Z88Arion install root")
    motor.add_argument("--runs-root", default="runs/z88")
    motor.add_argument("--config-out", help="Write only config JSON to this path instead of preparing a run folder")
    landing = subparsers.add_parser("drone_landing_gear", help="Explicit box drone landing gear recipe")
    landing.add_argument("--stl", required=True)
    landing.add_argument("--units", default="mm")
    landing.add_argument("--project-name", default="drone_landing_gear")
    landing.add_argument("--material", default="pa12_sls")
    landing.add_argument("--safety-preset", default="consumer_drone")
    landing.add_argument("--frame-min", required=True, help="Comma-separated x,y,z")
    landing.add_argument("--frame-max", required=True, help="Comma-separated x,y,z")
    landing.add_argument("--contact-min", required=True, help="Comma-separated x,y,z")
    landing.add_argument("--contact-max", required=True, help="Comma-separated x,y,z")
    landing.add_argument("--payload-mass", required=True, type=float)
    landing.add_argument("--impact-g", type=float, default=3.0)
    landing.add_argument("--load-direction", default="0,0,1", help="Comma-separated unit or non-unit vector")
    landing.add_argument("--volume-fraction", type=float, default=0.45)
    landing.add_argument("--voxel-pitch", type=float, default=1.0)
    landing.add_argument("--max-iterations", type=int, default=120)
    landing.add_argument("--convergence-tolerance", type=float, default=1e-3)
    landing.add_argument("--install-root", help="Override Z88Arion install root")
    landing.add_argument("--runs-root", default="runs/z88")
    landing.add_argument("--config-out", help="Write only config JSON to this path instead of preparing a run folder")
    gimbal = subparsers.add_parser("drone_gimbal_mount", help="Explicit box drone gimbal mount recipe")
    gimbal.add_argument("--stl", required=True)
    gimbal.add_argument("--units", default="mm")
    gimbal.add_argument("--project-name", default="drone_gimbal_mount")
    gimbal.add_argument("--material", default="pa12_sls")
    gimbal.add_argument("--safety-preset", default="consumer_drone")
    gimbal.add_argument("--frame-min", required=True, help="Comma-separated x,y,z")
    gimbal.add_argument("--frame-max", required=True, help="Comma-separated x,y,z")
    gimbal.add_argument("--camera-min", required=True, help="Comma-separated x,y,z")
    gimbal.add_argument("--camera-max", required=True, help="Comma-separated x,y,z")
    gimbal.add_argument("--camera-mass", required=True, type=float)
    gimbal.add_argument("--maneuver-g", type=float, default=3.0)
    gimbal.add_argument("--load-direction", default="0,-1,0", help="Comma-separated unit or non-unit vector")
    gimbal.add_argument("--target-vibration-frequency", type=float)
    gimbal.add_argument("--volume-fraction", type=float, default=0.35)
    gimbal.add_argument("--voxel-pitch", type=float, default=1.0)
    gimbal.add_argument("--max-iterations", type=int, default=120)
    gimbal.add_argument("--convergence-tolerance", type=float, default=1e-3)
    gimbal.add_argument("--install-root", help="Override Z88Arion install root")
    gimbal.add_argument("--runs-root", default="runs/z88")
    gimbal.add_argument("--config-out", help="Write only config JSON to this path instead of preparing a run folder")
    strut = subparsers.add_parser("ring_wing_strut", help="Explicit box ring-wing strut recipe")
    strut.add_argument("--stl", required=True)
    strut.add_argument("--units", default="mm")
    strut.add_argument("--project-name", default="ring_wing_strut")
    strut.add_argument("--material", default="cf_pa")
    strut.add_argument("--safety-preset", default="consumer_drone")
    strut.add_argument("--root-min", required=True, help="Comma-separated x,y,z")
    strut.add_argument("--root-max", required=True, help="Comma-separated x,y,z")
    strut.add_argument("--wing-min", required=True, help="Comma-separated x,y,z")
    strut.add_argument("--wing-max", required=True, help="Comma-separated x,y,z")
    strut.add_argument("--lift-force-per-strut", required=True, type=float)
    strut.add_argument("--lift-direction", default="0,0,1", help="Comma-separated unit or non-unit vector")
    strut.add_argument("--volume-fraction", type=float, default=0.4)
    strut.add_argument("--voxel-pitch", type=float, default=1.0)
    strut.add_argument("--max-iterations", type=int, default=120)
    strut.add_argument("--convergence-tolerance", type=float, default=1e-3)
    strut.add_argument("--install-root", help="Override Z88Arion install root")
    strut.add_argument("--runs-root", default="runs/z88")
    strut.add_argument("--config-out", help="Write only config JSON to this path instead of preparing a run folder")
    args = parser.parse_args()

    if args.recipe == "generic_bracket":
        config = configure_generic_bracket(
            args.stl,
            GenericBracketInputs(
                units=args.units,
                material_key=args.material,
                safety_preset=args.safety_preset,
                support_box=BoxSelector(_parse_vec3(args.support_min), _parse_vec3(args.support_max)),
                load_box=BoxSelector(_parse_vec3(args.load_min), _parse_vec3(args.load_max)),
                force=_parse_vec3(args.force),
                project_name=args.project_name,
                voxel_pitch=args.voxel_pitch,
                volume_fraction=args.volume_fraction,
                max_iterations=args.max_iterations,
                convergence_tolerance=args.convergence_tolerance,
            ),
        )
        return _write_or_prepare(args, config)
    if args.recipe == "drone_motor_mount":
        config = configure_drone_motor_mount(
            args.stl,
            DroneMotorMountInputs(
                units=args.units,
                material_key=args.material,
                safety_preset=args.safety_preset,
                frame_support_box=BoxSelector(_parse_vec3(args.frame_min), _parse_vec3(args.frame_max)),
                motor_mount_box=BoxSelector(_parse_vec3(args.motor_min), _parse_vec3(args.motor_max)),
                thrust=args.thrust,
                thrust_direction=_parse_vec3(args.thrust_direction),
                prop_diameter=args.prop_diameter,
                project_name=args.project_name,
                voxel_pitch=args.voxel_pitch,
                volume_fraction=args.volume_fraction,
                max_iterations=args.max_iterations,
                convergence_tolerance=args.convergence_tolerance,
            ),
        )
        return _write_or_prepare(args, config)
    if args.recipe == "drone_landing_gear":
        config = configure_drone_landing_gear(
            args.stl,
            DroneLandingGearInputs(
                units=args.units,
                material_key=args.material,
                safety_preset=args.safety_preset,
                frame_support_box=BoxSelector(_parse_vec3(args.frame_min), _parse_vec3(args.frame_max)),
                ground_contact_box=BoxSelector(_parse_vec3(args.contact_min), _parse_vec3(args.contact_max)),
                payload_mass=args.payload_mass,
                impact_g=args.impact_g,
                load_direction=_parse_vec3(args.load_direction),
                project_name=args.project_name,
                voxel_pitch=args.voxel_pitch,
                volume_fraction=args.volume_fraction,
                max_iterations=args.max_iterations,
                convergence_tolerance=args.convergence_tolerance,
            ),
        )
        return _write_or_prepare(args, config)
    if args.recipe == "drone_gimbal_mount":
        config = configure_drone_gimbal_mount(
            args.stl,
            DroneGimbalMountInputs(
                units=args.units,
                material_key=args.material,
                safety_preset=args.safety_preset,
                frame_support_box=BoxSelector(_parse_vec3(args.frame_min), _parse_vec3(args.frame_max)),
                camera_mount_box=BoxSelector(_parse_vec3(args.camera_min), _parse_vec3(args.camera_max)),
                camera_mass=args.camera_mass,
                maneuver_g=args.maneuver_g,
                load_direction=_parse_vec3(args.load_direction),
                target_vibration_frequency=args.target_vibration_frequency,
                project_name=args.project_name,
                voxel_pitch=args.voxel_pitch,
                volume_fraction=args.volume_fraction,
                max_iterations=args.max_iterations,
                convergence_tolerance=args.convergence_tolerance,
            ),
        )
        return _write_or_prepare(args, config)
    if args.recipe == "ring_wing_strut":
        config = configure_ring_wing_strut(
            args.stl,
            RingWingStrutInputs(
                units=args.units,
                material_key=args.material,
                safety_preset=args.safety_preset,
                root_support_box=BoxSelector(_parse_vec3(args.root_min), _parse_vec3(args.root_max)),
                wing_load_box=BoxSelector(_parse_vec3(args.wing_min), _parse_vec3(args.wing_max)),
                lift_force_per_strut=args.lift_force_per_strut,
                lift_direction=_parse_vec3(args.lift_direction),
                project_name=args.project_name,
                voxel_pitch=args.voxel_pitch,
                volume_fraction=args.volume_fraction,
                max_iterations=args.max_iterations,
                convergence_tolerance=args.convergence_tolerance,
            ),
        )
        return _write_or_prepare(args, config)
    raise AssertionError(f"unhandled recipe {args.recipe}")


def _write_or_prepare(args, config) -> int:
    if args.config_out:
        output = Path(args.config_out).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(config.to_json(), encoding="utf-8")
        print(json.dumps({"status": "config_written", "config": str(output)}, indent=2))
        return 0
    adapter = Z88Adapter(install_root=args.install_root, runs_root=args.runs_root)
    run_dir = adapter.prepare_project(config)
    print(json.dumps({"status": "prepared", "run_dir": str(run_dir), "config": config.to_dict()}, indent=2))
    return 0


def _parse_vec3(value: str) -> tuple[float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected three comma-separated values, got {value!r}")
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid numeric vector {value!r}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
