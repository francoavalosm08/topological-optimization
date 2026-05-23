from __future__ import annotations

import json
from pathlib import Path

from z88_bridge import (
    build_project_manifest,
    capture_examples,
    diff_project_dirs,
    ensure_asset_layout,
    inventory_files,
    record_post_run,
)


def _native_project(path: Path, *, control_algorithm: int = 1, extra: str = "") -> Path:
    path.mkdir(parents=True)
    (path / "z88control.txt").write_text(
        f"TOSOLVER START\n   OPTALGORITHM {control_algorithm}\nTOSOLVER END\n",
        encoding="utf-8",
    )
    (path / "z88sets.txt").write_text("#NODES CONSTRAINT 1 1 \"fixed\"\n1\n", encoding="utf-8")
    (path / "z88setsactive.txt").write_text(
        '#NODES CONSTRAINT 1 1 "fixed"\n',
        encoding="utf-8",
    )
    (path / "z88structure.txt").write_text("3 1 1 3 0\n", encoding="utf-8")
    if extra:
        (path / "extra.txt").write_text(extra, encoding="utf-8")
    return path


def test_ensure_asset_layout_creates_expected_directories(tmp_path: Path) -> None:
    paths = ensure_asset_layout(tmp_path / "z88_assets")

    assert paths["examples_pre"].is_dir()
    assert paths["examples_post"].is_dir()
    assert paths["manifests"].is_dir()
    assert paths["outputs"].is_dir()


def test_inventory_and_manifest_include_hashes_and_summary(tmp_path: Path) -> None:
    project = _native_project(tmp_path / "project")

    inventory = inventory_files(project)
    manifest = build_project_manifest(project, source="synthetic")

    assert "z88control.txt" in inventory
    assert len(inventory["z88control.txt"].sha256) == 64
    assert manifest["source"] == "synthetic"
    assert manifest["file_count"] == 4
    assert manifest["summary"]["control"]["TOSOLVER"]["OPTALGORITHM"] == 1
    assert manifest["summary"]["active_sets"][0]["label"] == "fixed"


def test_capture_examples_copies_defaults_and_writes_manifest(tmp_path: Path) -> None:
    examples_root = tmp_path / "installed_examples"
    _native_project(examples_root / "Example_OC", control_algorithm=1)

    captured = capture_examples(
        examples_root,
        asset_root=tmp_path / "assets",
        example_names=("Example_OC",),
    )

    destination = tmp_path / "assets" / "examples" / "pre" / "Example_OC"
    manifest_path = tmp_path / "assets" / "manifests" / "Example_OC.manifest.json"
    assert captured[0]["name"] == "Example_OC"
    assert destination.exists()
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["summary"]["control"]["TOSOLVER"]["OPTALGORITHM"] == 1


def test_diff_project_dirs_reports_added_removed_modified_unchanged(tmp_path: Path) -> None:
    pre = _native_project(tmp_path / "pre")
    post = _native_project(tmp_path / "post")
    (post / "z88control.txt").write_text(
        "TOSOLVER START\n   OPTALGORITHM 3\nTOSOLVER END\n",
        encoding="utf-8",
    )
    (post / "added.txt").write_text("new", encoding="utf-8")
    (pre / "removed.txt").write_text("gone", encoding="utf-8")

    diff = diff_project_dirs(pre, post)

    assert diff["counts"]["added"] == 1
    assert diff["counts"]["removed"] == 1
    assert diff["counts"]["modified"] == 1
    assert "added.txt" in diff["added"]
    assert "removed.txt" in diff["removed"]
    assert "z88control.txt" in diff["modified"]
    assert diff["pre_summary"]["control"]["TOSOLVER"]["OPTALGORITHM"] == 1
    assert diff["post_summary"]["control"]["TOSOLVER"]["OPTALGORITHM"] == 3


def test_record_post_run_copies_project_and_optional_stl(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    pre = asset_root / "examples" / "pre" / "Example_OC"
    _native_project(pre)
    completed = _native_project(tmp_path / "completed", control_algorithm=3)
    stl = tmp_path / "Optimized.STL"
    stl.write_text("solid x\nendsolid x\n", encoding="utf-8")

    result = record_post_run(
        "Example_OC",
        completed,
        asset_root=asset_root,
        optimized_stl=stl,
    )

    post = asset_root / "examples" / "post" / "Example_OC"
    assert post.exists()
    assert (post / "Optimized.STL").exists()
    assert Path(result["manifest"]).exists()
    assert Path(result["diff"]).exists()
    assert result["diff_counts"]["modified"] == 1


def test_record_post_run_rejects_missing_pre_fixture(tmp_path: Path) -> None:
    completed = _native_project(tmp_path / "completed")

    try:
        record_post_run("missing", completed, asset_root=tmp_path / "assets")
    except FileNotFoundError as exc:
        assert "Missing matching pre fixture" in str(exc)
    else:
        raise AssertionError("expected missing pre fixture failure")


def test_record_post_run_rejects_pre_folder_as_source(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    pre = asset_root / "examples" / "pre" / "Example_OC"
    _native_project(pre)

    try:
        record_post_run("Example_OC", pre, asset_root=asset_root)
    except ValueError as exc:
        assert "pre fixture" in str(exc)
    else:
        raise AssertionError("expected pre folder source failure")


def test_record_post_run_rejects_empty_source(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    _native_project(asset_root / "examples" / "pre" / "Example_OC")
    empty = tmp_path / "empty"
    empty.mkdir()

    try:
        record_post_run("Example_OC", empty, asset_root=asset_root)
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("expected empty source failure")
