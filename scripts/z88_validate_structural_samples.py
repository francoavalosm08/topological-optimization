"""Validate generated common mechanical structures through the Z88 H8 topology path."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import (
    Z88BridgeError,
    configure_recipe_from_payload,
    generate_structural_sample_assets,
    inspect_stl_geometry,
    run_generated_oc_workflow,
    write_native_oc_project,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples-dir", default="runs/z88_structural_validation/samples")
    parser.add_argument("--projects-dir", default="runs/z88_structural_validation/native_projects")
    parser.add_argument("--output", default="z88_assets/outputs/structural_sample_validation.json")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--max-elements", type=int, default=50_000)
    parser.add_argument(
        "--methods",
        default="oc",
        help="Comma-separated optimizer methods to validate: oc,toss,sko",
    )
    parser.add_argument("--run-workflow", action="store_true", help="Run optimizer/postprocess/export workflow.")
    parser.add_argument("--workflow-timeout", type=float, default=180.0)
    args = parser.parse_args()

    payload = validate_structural_samples(
        samples_dir=Path(args.samples_dir),
        projects_dir=Path(args.projects_dir),
        output=Path(args.output),
        install_root=args.install_root,
        max_elements=args.max_elements,
        methods=_parse_methods(args.methods),
        run_workflow=args.run_workflow,
        workflow_timeout_s=args.workflow_timeout,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 2


def validate_structural_samples(
    *,
    samples_dir: Path,
    projects_dir: Path,
    output: Path,
    install_root: str | None = None,
    max_elements: int = 50_000,
    methods: tuple[str, ...] = ("oc",),
    run_workflow: bool = False,
    workflow_timeout_s: float = 180.0,
) -> dict[str, Any]:
    samples = generate_structural_sample_assets(samples_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _validate_one_sample(
            sample,
            method=method,
            projects_dir=projects_dir,
            use_method_subdir=len(methods) > 1,
            install_root=install_root,
            max_elements=max_elements,
            run_workflow=run_workflow,
            workflow_timeout_s=workflow_timeout_s,
        )
        for sample in samples["samples"]
        for method in methods
    ]
    failed = [item for item in results if item["status"] != "ok"]
    payload = {
        "schema_version": 1,
        "status": "ok" if not failed else "failed",
        "sample_count": len(results),
        "asset_count": len(samples["samples"]),
        "method_count": len(methods),
        "methods": list(methods),
        "failed_count": len(failed),
        "samples_dir": str(samples_dir.resolve()),
        "projects_dir": str(projects_dir.resolve()),
        "run_workflow": run_workflow,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _validate_one_sample(
    sample: dict[str, Any],
    *,
    method: str,
    projects_dir: Path,
    use_method_subdir: bool,
    install_root: str | None,
    max_elements: int,
    run_workflow: bool,
    workflow_timeout_s: float,
) -> dict[str, Any]:
    name = sample["name"]
    try:
        payload = copy.deepcopy(sample["payload"])
        payload["optimizer_method"] = method
        payload["project_name"] = f"{payload.get('project_name', name)}_{method}"
        config = configure_recipe_from_payload(payload)
        config.validate()
        geometry = inspect_stl_geometry(config.input_stl)
        project_base = projects_dir / method / name if use_method_subdir else projects_dir / name
        project_dir = project_base / "z88_project"
        if project_dir.exists():
            shutil.rmtree(project_dir)
        write_result = write_native_oc_project(
            config,
            project_dir,
            install_root=install_root,
            max_elements=max_elements,
        )
        item: dict[str, Any] = {
            "name": name,
            "optimizer_method": method,
            "recipe": sample["recipe"],
            "status": "ok",
            "description": sample["description"],
            "stl_path": sample["stl_path"],
            "geometry": geometry,
            "native_project": write_result.to_dict(),
        }
        if run_workflow:
            workflow = run_generated_oc_workflow(
                write_result.project_dir,
                install_root=install_root,
                optimizer_timeout_s=workflow_timeout_s,
                displacement_timeout_s=workflow_timeout_s,
                generate_stress=True,
                stress_timeout_s=workflow_timeout_s,
            )
            item["workflow"] = workflow.compact_dict()
            if workflow.optimizer is None or workflow.optimizer.status != "completed":
                item["status"] = "failed"
            if workflow.displacement is None or workflow.displacement.status != "completed":
                item["status"] = "failed"
            if workflow.stress is None or workflow.stress.status != "completed":
                item["status"] = "failed"
            if workflow.optimized_export is None or workflow.optimized_export.status not in {
                "exported",
                "exported_with_warnings",
            }:
                item["status"] = "failed"
        return item
    except (FileNotFoundError, ValueError, Z88BridgeError) as exc:
        return {
            "name": name,
            "optimizer_method": method,
            "recipe": sample.get("recipe"),
            "status": "failed",
            "description": sample.get("description"),
            "error": str(exc),
        }


def _parse_methods(value: str) -> tuple[str, ...]:
    methods = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    allowed = {"oc", "toss", "sko"}
    invalid = [item for item in methods if item not in allowed]
    if not methods:
        raise ValueError("--methods must include at least one method")
    if invalid:
        raise ValueError(f"unsupported methods {invalid}; expected any of {sorted(allowed)}")
    return methods


if __name__ == "__main__":
    raise SystemExit(main())
