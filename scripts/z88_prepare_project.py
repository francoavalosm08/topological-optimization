"""Prepare a reproducible Z88Arion handoff project from an STL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import (
    ExportSettings,
    LoadCase,
    MaterialSpec,
    OptimizerSettings,
    RegionSpec,
    SupportSpec,
    Z88Adapter,
    Z88RunConfig,
)


def _region_from_cli(data: dict[str, object]) -> RegionSpec:
    return RegionSpec(
        name=str(data["name"]),
        selector=dict(data.get("selector", {})),
        role=str(data.get("role", "region")),
    )


def _support_from_cli(data: dict[str, object]) -> SupportSpec:
    return SupportSpec(
        name=str(data["name"]),
        region=_region_from_cli(dict(data["region"])),
        constrained_dofs=tuple(str(item) for item in data.get("constrained_dofs", ("x", "y", "z"))),
    )


def _load_from_cli(data: dict[str, object]) -> LoadCase:
    return LoadCase(
        name=str(data["name"]),
        region=_region_from_cli(dict(data["region"])),
        force=tuple(float(item) for item in data["force"]),
        weight=float(data.get("weight", 1.0)),
    )


def _parse_json_list(raw: str | None) -> tuple[dict[str, object], ...]:
    if not raw:
        return ()
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list")
    return tuple(dict(item) for item in parsed)


def build_config(args: argparse.Namespace) -> Z88RunConfig:
    supports = tuple(_support_from_cli(item) for item in _parse_json_list(args.supports_json))
    loads = tuple(_load_from_cli(item) for item in _parse_json_list(args.loads_json))
    passive_solid = tuple(
        _region_from_cli(item) for item in _parse_json_list(args.passive_solid_json)
    )
    passive_void = tuple(_region_from_cli(item) for item in _parse_json_list(args.passive_void_json))

    return Z88RunConfig(
        input_stl=str(Path(args.input_stl).resolve()),
        units=args.units,
        project_name=args.project_name,
        voxel_pitch=args.voxel_pitch,
        material=MaterialSpec(
            name=args.material_name,
            young_modulus=args.young_modulus,
            poisson_ratio=args.poisson_ratio,
            density=args.density,
            stress_limit=args.stress_limit,
        ),
        optimizer=OptimizerSettings(
            method=args.method,
            volume_fraction=args.volume_fraction,
            max_iterations=args.max_iterations,
            convergence_tolerance=args.convergence_tolerance,
        ),
        supports=supports,
        loads=loads,
        passive_solid=passive_solid,
        passive_void=passive_void,
        safety_factor=args.safety_factor,
        export=ExportSettings(
            iso_threshold=args.iso_threshold,
            smoothing_iterations=args.smoothing_iterations,
            min_component_volume_fraction=args.min_component_volume_fraction,
        ),
        notes=args.notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_stl", help="Input STL to hand off to Z88Arion")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--runs-root", default="runs/z88", help="Directory for generated run folders")
    parser.add_argument("--project-name", default="z88_topopt_run")
    parser.add_argument("--units", default="mm", choices=("mm", "cm", "m", "in"))
    parser.add_argument("--voxel-pitch", type=float, default=1.0)
    parser.add_argument("--method", default="oc", choices=("oc", "sko", "toss"))
    parser.add_argument("--volume-fraction", type=float, default=0.4)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--convergence-tolerance", type=float, default=1e-3)
    parser.add_argument("--material-name", default="Al-6061-T6")
    parser.add_argument("--young-modulus", type=float, default=68.9e9)
    parser.add_argument("--poisson-ratio", type=float, default=0.33)
    parser.add_argument("--density", type=float, default=2700.0)
    parser.add_argument("--stress-limit", type=float, default=276e6)
    parser.add_argument("--safety-factor", type=float, default=1.5)
    parser.add_argument("--iso-threshold", type=float, default=0.5)
    parser.add_argument("--smoothing-iterations", type=int, default=20)
    parser.add_argument("--min-component-volume-fraction", type=float, default=0.05)
    parser.add_argument("--supports-json", help="JSON list of support specs")
    parser.add_argument("--loads-json", help="JSON list of load specs")
    parser.add_argument("--passive-solid-json", help="JSON list of passive-solid region specs")
    parser.add_argument("--passive-void-json", help="JSON list of passive-void region specs")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    config = build_config(args)
    adapter = Z88Adapter(install_root=args.install_root, runs_root=args.runs_root)
    project_dir = adapter.prepare_project(config)
    print(project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
