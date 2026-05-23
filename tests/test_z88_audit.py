from __future__ import annotations

import json
from pathlib import Path

from z88_bridge import audit_fixture, audit_to_json, render_audit_markdown, write_audit_outputs


def _fixture(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "z88control.txt").write_text(
        "TOSOLVER START\n   OPTALGORITHM 1\nTOSOLVER END\n",
        encoding="utf-8",
    )
    (path / "z88sets.txt").write_text("#NODES CONSTRAINT 1 1 \"fixed\"\n1\n", encoding="utf-8")
    (path / "z88setsactive.txt").write_text(
        '#NODES CONSTRAINT 1 1 "fixed"\n',
        encoding="utf-8",
    )
    (path / "z88structure.txt").write_text("3 1 1 3 0\n", encoding="utf-8")
    (path / "mystery.bin").write_bytes(b"\x00\x81raw")
    return path


def test_audit_fixture_classifies_known_unknown_and_parsed_content(tmp_path: Path) -> None:
    project = _fixture(tmp_path / "project")

    audit = audit_fixture(project)

    assert audit["fixture"] == "project"
    assert "z88control.txt" in audit["known_files"]
    assert "mystery.bin" in audit["unknown_files"]
    assert audit["unknown_files"]["mystery.bin"]["preview"]["binary_like"] is True
    assert audit["missing_core_files"] == []
    assert audit["parsed"]["control"]["TOSOLVER"]["OPTALGORITHM"] == 1


def test_render_audit_markdown_is_bounded_and_human_readable(tmp_path: Path) -> None:
    audit = audit_fixture(_fixture(tmp_path / "project"))

    markdown = render_audit_markdown(audit)

    assert "# Z88 Fixture Audit: project" in markdown
    assert "## Known Files" in markdown
    assert "## Unknown Files" in markdown
    assert "mystery.bin" in markdown


def test_write_audit_outputs_writes_json_and_markdown(tmp_path: Path) -> None:
    audit = audit_fixture(_fixture(tmp_path / "project"))
    json_path = tmp_path / "audit.json"
    md_path = tmp_path / "audit.md"

    write_audit_outputs(audit, json_path, md_path)

    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["fixture"] == "project"
    assert md_path.read_text(encoding="utf-8").startswith("# Z88 Fixture Audit")


def test_audit_to_json_round_trips(tmp_path: Path) -> None:
    audit = audit_fixture(_fixture(tmp_path / "project"))

    loaded = json.loads(audit_to_json(audit))

    assert loaded["fixture"] == "project"
