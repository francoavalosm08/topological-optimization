"""Download trusted simple STL files and validate the confirmed OC/H8 path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import (
    Z88BridgeError,
    configure_recipe_from_payload,
    inspect_stl_geometry,
    run_generated_oc_workflow,
    suggest_end_boxes_from_stl,
    write_native_oc_project,
)


ONLINE_STL_SOURCES = (
    {
        "name": "wikimedia_cube",
        "source_page": "https://commons.wikimedia.org/wiki/File:Cube.stl",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/b/be/Cube.stl",
        "filename": "wikimedia_cube.stl",
        "kind": "stl",
        "description": "Public-domain cube STL from Wikimedia Commons.",
        "voxel_pitch": 0.2,
        "force": (0.0, -25.0, 0.0),
    },
    {
        "name": "nist_am_test_artifact",
        "source_page": (
            "https://www.nist.gov/el/intelligent-systems-division-73500/"
            "production-systems-group/nist-additive-manufacturing-test"
        ),
        "download_url": "https://www.nist.gov/document/nist-test-artifact-stlzip",
        "filename": "nist_test_artifact.zip",
        "kind": "zip_stl",
        "description": "NIST Additive Manufacturing Test Artifact STL.",
        "voxel_pitch": 8.0,
        "force": (0.0, -100.0, 0.0),
    },
    {
        "name": "wikimedia_sphere",
        "source_page": "https://commons.wikimedia.org/wiki/File:Sphere.stl",
        "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Sphere.stl",
        "filename": "wikimedia_sphere.stl",
        "kind": "stl",
        "description": "Public-domain sphere STL from Wikimedia Commons.",
        "voxel_pitch": 10.0,
        "force": (0.0, -100.0, 0.0),
    },
    {
        "name": "wikimedia_cylinder",
        "source_page": "https://commons.wikimedia.org/wiki/File:Cilindro_3D.stl",
        "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Cilindro_3D.stl",
        "filename": "wikimedia_cylinder.stl",
        "kind": "stl",
        "description": "Right-cylinder STL from Wikimedia Commons.",
        "voxel_pitch": 3.0,
        "force": (0.0, -50.0, 0.0),
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", default="z88_assets/online_stls")
    parser.add_argument("--projects-dir", default="runs/online_stl_validation")
    parser.add_argument("--output", default="z88_assets/outputs/online_stl_validation.json")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--max-elements", type=int, default=20_000)
    parser.add_argument("--run-workflow", action="store_true", help="Run the generated OC workflow after writing.")
    parser.add_argument("--workflow-timeout", type=float, default=180.0)
    args = parser.parse_args()

    payload = validate_online_stls(
        asset_dir=Path(args.asset_dir),
        projects_dir=Path(args.projects_dir),
        output=Path(args.output),
        install_root=args.install_root,
        max_elements=args.max_elements,
        run_workflow=args.run_workflow,
        workflow_timeout_s=args.workflow_timeout,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 2


def validate_online_stls(
    *,
    asset_dir: Path,
    projects_dir: Path,
    output: Path,
    install_root: str | None = None,
    max_elements: int = 20_000,
    run_workflow: bool = False,
    workflow_timeout_s: float = 180.0,
) -> dict[str, Any]:
    downloads_dir = asset_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for source in ONLINE_STL_SOURCES:
        results.append(
            _validate_source(
                source,
                downloads_dir=downloads_dir,
                projects_dir=projects_dir,
                install_root=install_root,
                max_elements=max_elements,
                run_workflow=run_workflow,
                workflow_timeout_s=workflow_timeout_s,
            )
        )
    failed = [item for item in results if item["status"] != "ok"]
    payload = {
        "schema_version": 1,
        "status": "ok" if not failed else "failed",
        "source_count": len(results),
        "failed_count": len(failed),
        "asset_dir": str(asset_dir.resolve()),
        "projects_dir": str(projects_dir.resolve()),
        "run_workflow": run_workflow,
        "sources": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _validate_source(
    source: dict[str, Any],
    *,
    downloads_dir: Path,
    projects_dir: Path,
    install_root: str | None,
    max_elements: int,
    run_workflow: bool,
    workflow_timeout_s: float,
) -> dict[str, Any]:
    try:
        downloaded = downloads_dir / source["filename"]
        _download(source["download_url"], downloaded)
        stl_path = _extract_stl(downloaded, downloads_dir / source["name"], source["kind"])
        suggestion = suggest_end_boxes_from_stl(
            stl_path,
            thickness_fraction=0.1,
            minimum_thickness=float(source["voxel_pitch"]) * 1.5,
        )
        payload = {
            "recipe": "generic_bracket",
            "stl_path": str(stl_path.resolve()),
            "project_name": f"online_{source['name']}",
            "support_box": suggestion["support_box"],
            "load_box": suggestion["load_box"],
            "force": list(source["force"]),
            "material": "al_6061_t6",
            "safety_preset": "consumer_drone",
            "voxel_pitch": source["voxel_pitch"],
            "volume_fraction": 1.0,
            "max_iterations": 1,
        }
        config = configure_recipe_from_payload(payload)
        config.validate()
        project_dir = projects_dir / source["name"] / "z88_project"
        if project_dir.exists():
            shutil.rmtree(project_dir)
        write_result = write_native_oc_project(
            config,
            project_dir,
            install_root=install_root,
            max_elements=max_elements,
        )
        item: dict[str, Any] = {
            "name": source["name"],
            "status": "ok",
            "description": source["description"],
            "source_page": source["source_page"],
            "download_url": source["download_url"],
            "downloaded_file": str(downloaded.resolve()),
            "stl_path": str(stl_path.resolve()),
            "geometry": inspect_stl_geometry(stl_path),
            "suggestion": suggestion,
            "config": config.to_dict(),
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
            if workflow.status not in {"completed", "partial"}:
                item["status"] = "failed"
        return item
    except (OSError, ValueError, Z88BridgeError) as exc:
        return {
            "name": source["name"],
            "status": "failed",
            "description": source["description"],
            "source_page": source["source_page"],
            "download_url": source["download_url"],
            "error": str(exc),
        }


def _download(url: str, output: Path) -> None:
    if output.is_file() and output.stat().st_size > 0:
        return
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        output.write_bytes(response.read())


def _extract_stl(downloaded: Path, extract_dir: Path, kind: str) -> Path:
    if kind == "stl":
        return downloaded
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(downloaded) as archive:
        archive.extractall(extract_dir)
    stls = sorted(extract_dir.rglob("*.stl")) + sorted(extract_dir.rglob("*.STL"))
    if not stls:
        raise FileNotFoundError(f"no STL file found inside {downloaded}")
    return stls[0]


if __name__ == "__main__":
    raise SystemExit(main())
