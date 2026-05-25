from __future__ import annotations

from pathlib import Path

import scripts.z88_validate_online_stls as online_stls
from scripts.z88_validate_online_stls import _download, _extract_stl, validate_online_stls


def test_extract_stl_returns_plain_stl(tmp_path: Path) -> None:
    stl = tmp_path / "part.stl"
    stl.write_text("solid empty\nendsolid empty\n", encoding="utf-8")

    assert _extract_stl(stl, tmp_path / "extract", "stl") == stl


def test_download_reuses_existing_cached_file(tmp_path: Path, monkeypatch) -> None:
    cached = tmp_path / "cached.stl"
    cached.write_text("solid cached\nendsolid cached\n", encoding="utf-8")

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("urlopen should not be called for an existing cached file")

    monkeypatch.setattr(online_stls, "urlopen", fail_urlopen)

    _download("https://example.invalid/cached.stl", cached)

    assert cached.read_text(encoding="utf-8") == "solid cached\nendsolid cached\n"


def test_validate_online_stls_cleans_existing_generated_project(tmp_path: Path, monkeypatch) -> None:
    source_stl = tmp_path / "source.stl"
    source_stl.write_text("solid source\nendsolid source\n", encoding="utf-8")
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "cached_source" / "z88_project"
    project_dir.mkdir(parents=True)
    stale = project_dir / "stale_z88_output.txt"
    stale.write_text("old output", encoding="utf-8")

    monkeypatch.setattr(
        online_stls,
        "ONLINE_STL_SOURCES",
        (
            {
                "name": "cached_source",
                "source_page": "https://example.invalid/source",
                "download_url": "https://example.invalid/source.stl",
                "filename": "source.stl",
                "kind": "stl",
                "description": "cached source",
                "voxel_pitch": 1.0,
                "force": (0.0, -1.0, 0.0),
            },
        ),
    )
    monkeypatch.setattr(online_stls, "_download", lambda _url, output: output.write_text("cached", encoding="utf-8"))
    monkeypatch.setattr(online_stls, "_extract_stl", lambda _downloaded, _extract_dir, _kind: source_stl)
    monkeypatch.setattr(
        online_stls,
        "suggest_end_boxes_from_stl",
        lambda *_args, **_kwargs: {
            "support_box": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "load_box": {"min": [1, 1, 1], "max": [2, 2, 2]},
        },
    )
    monkeypatch.setattr(online_stls, "inspect_stl_geometry", lambda _path: {"watertight": True})

    class FakeConfig:
        def validate(self) -> None:
            return None

        def to_dict(self) -> dict:
            return {"project_name": "fake"}

    class FakeWriteResult:
        def __init__(self, output_dir: Path) -> None:
            self.project_dir = output_dir

        def to_dict(self) -> dict:
            return {"project_dir": str(self.project_dir)}

    def fake_configure(_payload):
        return FakeConfig()

    def fake_write(_config, output_dir, **_kwargs):
        assert Path(output_dir) == project_dir
        assert not stale.exists()
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return FakeWriteResult(Path(output_dir))

    monkeypatch.setattr(online_stls, "configure_recipe_from_payload", fake_configure)
    monkeypatch.setattr(online_stls, "write_native_oc_project", fake_write)

    report = validate_online_stls(
        asset_dir=tmp_path / "assets",
        projects_dir=projects_dir,
        output=tmp_path / "report.json",
    )

    assert report["status"] == "ok"
    assert report["source_count"] == 1
    assert not stale.exists()
