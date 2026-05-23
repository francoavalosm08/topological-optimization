"""Local Z88 asset capture, manifest, and diff helpers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any

from .project_files import summarize_project_files


DEFAULT_ASSET_ROOT = Path("z88_assets")
DEFAULT_EXAMPLES = ("2_Querlenker_OC", "5_Winkelhalter_TOSS", "7_Balken_SKO")


@dataclass(frozen=True)
class FileRecord:
    path: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


def ensure_asset_layout(asset_root: str | Path = DEFAULT_ASSET_ROOT) -> dict[str, Path]:
    root = Path(asset_root)
    paths = {
        "root": root,
        "examples_pre": root / "examples" / "pre",
        "examples_post": root / "examples" / "post",
        "manifests": root / "manifests",
        "outputs": root / "outputs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_files(root: str | Path) -> dict[str, FileRecord]:
    root = Path(root)
    records: dict[str, FileRecord] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        records[rel] = FileRecord(
            path=rel,
            bytes=path.stat().st_size,
            sha256=sha256_file(path),
        )
    return records


def build_project_manifest(project_dir: str | Path, *, source: str | None = None) -> dict[str, Any]:
    project_dir = Path(project_dir)
    records = inventory_files(project_dir)
    manifest: dict[str, Any] = {
        "project_dir": str(project_dir),
        "source": source,
        "file_count": len(records),
        "total_bytes": sum(record.bytes for record in records.values()),
        "files": {name: record.to_dict() for name, record in records.items()},
        "summary": summarize_project_files(project_dir),
    }
    return manifest


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def capture_examples(
    examples_root: str | Path,
    *,
    asset_root: str | Path = DEFAULT_ASSET_ROOT,
    example_names: tuple[str, ...] = DEFAULT_EXAMPLES,
    overwrite: bool = True,
) -> list[dict[str, Any]]:
    paths = ensure_asset_layout(asset_root)
    examples_root = Path(examples_root)
    captured: list[dict[str, Any]] = []
    for name in example_names:
        source = examples_root / name
        if not source.is_dir():
            raise FileNotFoundError(f"Z88 example project not found: {source}")
        destination = paths["examples_pre"] / name
        if destination.exists():
            if not overwrite:
                raise FileExistsError(f"Destination already exists: {destination}")
            _remove_tree_within(destination, paths["root"])
        shutil.copytree(source, destination)
        manifest = build_project_manifest(destination, source=str(source))
        manifest_path = paths["manifests"] / f"{name}.manifest.json"
        write_manifest(manifest, manifest_path)
        captured.append(
            {
                "name": name,
                "source": str(source),
                "destination": str(destination),
                "manifest": str(manifest_path),
                "file_count": manifest["file_count"],
                "total_bytes": manifest["total_bytes"],
            }
        )
    return captured


def diff_project_dirs(pre_dir: str | Path, post_dir: str | Path) -> dict[str, Any]:
    pre_dir = Path(pre_dir)
    post_dir = Path(post_dir)
    pre = inventory_files(pre_dir)
    post = inventory_files(post_dir)
    pre_names = set(pre)
    post_names = set(post)
    added = sorted(post_names - pre_names)
    removed = sorted(pre_names - post_names)
    common = sorted(pre_names & post_names)
    modified = [
        name
        for name in common
        if pre[name].sha256 != post[name].sha256 or pre[name].bytes != post[name].bytes
    ]
    unchanged = [name for name in common if name not in modified]
    return {
        "pre_dir": str(pre_dir),
        "post_dir": str(post_dir),
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": len(unchanged),
        },
        "added": {name: post[name].to_dict() for name in added},
        "removed": {name: pre[name].to_dict() for name in removed},
        "modified": {
            name: {
                "pre": pre[name].to_dict(),
                "post": post[name].to_dict(),
            }
            for name in modified
        },
        "unchanged": {name: pre[name].to_dict() for name in unchanged},
        "pre_summary": summarize_project_files(pre_dir),
        "post_summary": summarize_project_files(post_dir),
    }


def record_post_run(
    fixture_name: str,
    source_dir: str | Path,
    *,
    asset_root: str | Path = DEFAULT_ASSET_ROOT,
    optimized_stl: str | Path | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    paths = ensure_asset_layout(asset_root)
    pre_dir = paths["examples_pre"] / fixture_name
    if not pre_dir.is_dir():
        raise FileNotFoundError(f"Missing matching pre fixture: {pre_dir}")

    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Completed Z88 project folder not found: {source_dir}")
    if not any(source_dir.iterdir()):
        raise ValueError(f"Completed Z88 project folder is empty: {source_dir}")
    if source_dir.resolve() == pre_dir.resolve():
        raise ValueError("source_dir points at the pre fixture; provide a completed post-run copy")

    post_dir = paths["examples_post"] / fixture_name
    if post_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Post fixture already exists: {post_dir}")
        _remove_tree_within(post_dir, paths["root"])
    shutil.copytree(source_dir, post_dir)

    copied_stl: str | None = None
    if optimized_stl is not None:
        stl_path = Path(optimized_stl)
        if stl_path.suffix.lower() != ".stl":
            raise ValueError(f"optimized_stl must be an STL file: {stl_path}")
        if not stl_path.is_file():
            raise FileNotFoundError(f"optimized STL not found: {stl_path}")
        destination = post_dir / stl_path.name
        if stl_path.resolve() != destination.resolve():
            shutil.copy2(stl_path, destination)
        copied_stl = str(destination)

    manifest = build_project_manifest(post_dir, source=str(source_dir))
    manifest_path = paths["manifests"] / f"{fixture_name}.post.manifest.json"
    write_manifest(manifest, manifest_path)
    diff = diff_project_dirs(pre_dir, post_dir)
    diff_path = paths["manifests"] / f"{fixture_name}.pre_post_diff.json"
    write_manifest(diff, diff_path)
    return {
        "fixture": fixture_name,
        "pre_dir": str(pre_dir),
        "post_dir": str(post_dir),
        "source_dir": str(source_dir),
        "optimized_stl": copied_stl,
        "manifest": str(manifest_path),
        "diff": str(diff_path),
        "diff_counts": diff["counts"],
    }


def _remove_tree_within(target: Path, allowed_root: Path) -> None:
    target_resolved = target.resolve()
    root_resolved = allowed_root.resolve()
    if root_resolved not in target_resolved.parents and target_resolved != root_resolved:
        raise ValueError(f"Refusing to remove path outside asset root: {target}")

    def _onexc(function, path, excinfo):
        try:
            os.chmod(path, stat.S_IWRITE)
            function(path)
        except OSError:
            raise excinfo[1]

    shutil.rmtree(target, onexc=_onexc)
