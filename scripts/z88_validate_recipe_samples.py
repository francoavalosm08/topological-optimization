"""Validate generated sample recipes through config and native OC/H8 writing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import (
    Z88BridgeError,
    configure_recipe_from_payload,
    generate_sample_assets,
    inspect_stl_geometry,
    write_native_oc_project,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples-dir", default="runs/z88_recipe_validation/samples")
    parser.add_argument("--projects-dir", default="runs/z88_recipe_validation/native_projects")
    parser.add_argument("--output", default="z88_assets/outputs/recipe_sample_validation.json")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--max-elements", type=int, default=20_000)
    parser.add_argument(
        "--skip-native-projects",
        action="store_true",
        help="Only validate recipe configs and STL geometry; do not write native projects.",
    )
    args = parser.parse_args()

    payload = validate_recipe_samples(
        samples_dir=Path(args.samples_dir),
        projects_dir=Path(args.projects_dir),
        output=Path(args.output),
        install_root=args.install_root,
        max_elements=args.max_elements,
        write_projects=not args.skip_native_projects,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 2


def validate_recipe_samples(
    *,
    samples_dir: Path,
    projects_dir: Path,
    output: Path,
    install_root: str | None = None,
    max_elements: int = 20_000,
    write_projects: bool = True,
) -> dict[str, Any]:
    samples = generate_sample_assets(samples_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for sample in samples["samples"]:
        results.append(
            _validate_one_sample(
                sample,
                projects_dir=projects_dir,
                install_root=install_root,
                max_elements=max_elements,
                write_project=write_projects,
            )
        )
    failed = [item for item in results if item["status"] != "ok"]
    payload = {
        "schema_version": 1,
        "status": "ok" if not failed else "failed",
        "sample_count": len(results),
        "failed_count": len(failed),
        "samples_dir": str(samples_dir.resolve()),
        "projects_dir": str(projects_dir.resolve()) if write_projects else None,
        "write_projects": write_projects,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _validate_one_sample(
    sample: dict[str, Any],
    *,
    projects_dir: Path,
    install_root: str | None,
    max_elements: int,
    write_project: bool,
) -> dict[str, Any]:
    name = sample["name"]
    try:
        config = configure_recipe_from_payload(sample["payload"])
        config.validate()
        geometry = inspect_stl_geometry(config.input_stl)
        item: dict[str, Any] = {
            "name": name,
            "recipe": sample["recipe"],
            "status": "ok",
            "config_run_id": config.run_id(),
            "geometry": geometry,
        }
        if write_project:
            project_dir = projects_dir / name / "z88_project"
            write_result = write_native_oc_project(
                config,
                project_dir,
                install_root=install_root,
                max_elements=max_elements,
            )
            item["native_project"] = write_result.to_dict()
        return item
    except (FileNotFoundError, ValueError, Z88BridgeError) as exc:
        return {
            "name": name,
            "recipe": sample.get("recipe"),
            "status": "failed",
            "error": str(exc),
        }


if __name__ == "__main__":
    raise SystemExit(main())
