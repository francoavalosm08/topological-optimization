from __future__ import annotations

from pathlib import Path

from scripts.z88_validate_online_stls import _extract_stl


def test_extract_stl_returns_plain_stl(tmp_path: Path) -> None:
    stl = tmp_path / "part.stl"
    stl.write_text("solid empty\nendsolid empty\n", encoding="utf-8")

    assert _extract_stl(stl, tmp_path / "extract", "stl") == stl
