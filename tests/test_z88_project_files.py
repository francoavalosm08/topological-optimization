from __future__ import annotations

from pathlib import Path

from z88_bridge import (
    parse_z88control,
    parse_z88setsactive,
    parse_z88structure_header,
    preview_project_file,
    summarize_project_files,
)


def test_parse_z88control_extracts_topology_settings(tmp_path: Path) -> None:
    control = tmp_path / "z88control.txt"
    control.write_text(
        """
DYNAMIC START
TOSOLVER START
   OPTMAXIT         300
   OPTALGORITHM     1
   OPTVREL          7.060000E+001
   OPTPENALTY       3.000000E+000
TOSOLVER END
DYNAMIC END
""".strip(),
        encoding="utf-8",
    )

    parsed = parse_z88control(control)

    assert parsed["TOSOLVER"]["OPTMAXIT"] == 300
    assert parsed["TOSOLVER"]["OPTALGORITHM"] == 1
    assert parsed["TOSOLVER"]["OPTVREL"] == pytest_approx(70.6)
    assert parsed["TOSOLVER"]["OPTPENALTY"] == pytest_approx(3.0)


def test_parse_z88setsactive_extracts_labels(tmp_path: Path) -> None:
    active = tmp_path / "z88setsactive.txt"
    active.write_text(
        """
2
#NODES CONSTRAINT 1 4 1 11 123 1 0.000000E+000 "Festlager_1"
#ELEMENTS MATERIAL 1 12 13 4 1 "Warmfester Baustahl"
""".strip(),
        encoding="utf-8",
    )

    sets = parse_z88setsactive(active)

    assert len(sets) == 2
    assert sets[0].kind == "NODES"
    assert sets[0].role == "CONSTRAINT"
    assert sets[0].label == "Festlager_1"
    assert sets[1].kind == "ELEMENTS"
    assert sets[1].role == "MATERIAL"


def test_summarize_project_files_includes_control_and_active_sets(tmp_path: Path) -> None:
    (tmp_path / "z88control.txt").write_text(
        "TOSOLVER START\n   OPTALGORITHM 3\nTOSOLVER END\n",
        encoding="utf-8",
    )
    (tmp_path / "z88setsactive.txt").write_text(
        '#NODES CONSTRAINT 1 11 4 11 2 3 -1.000000E+002 "Kraft_1"\n',
        encoding="utf-8",
    )
    (tmp_path / "z88structure.txt").write_text(
        "3 17220 70040 51660 0\n       1 3  1.0 2.0 3.0\n",
        encoding="utf-8",
    )

    summary = summarize_project_files(tmp_path)

    assert summary["files"]["z88control.txt"]["bytes"] > 0
    assert summary["control"]["TOSOLVER"]["OPTALGORITHM"] == 3
    assert summary["active_sets"][0]["label"] == "Kraft_1"
    assert summary["structure"]["fields"] == [3, 17220, 70040, 51660, 0]


def test_parse_z88structure_header_reads_first_count_line(tmp_path: Path) -> None:
    structure = tmp_path / "z88structure.txt"
    structure.write_text("3 10 20 30 0\n1 3 0.0 0.0 0.0\n", encoding="utf-8")

    parsed = parse_z88structure_header(structure)

    assert parsed["field_count"] == 5
    assert parsed["fields"] == [3, 10, 20, 30, 0]


def test_summarize_project_files_tolerates_missing_optional_files(tmp_path: Path) -> None:
    (tmp_path / "z88structure.txt").write_text("3 1 1 3 0\n", encoding="utf-8")

    summary = summarize_project_files(tmp_path)

    assert "control" not in summary
    assert "active_sets" not in summary
    assert summary["structure"]["fields"] == [3, 1, 1, 3, 0]
    assert summary["warnings"] == []


def test_preview_project_file_handles_empty_and_non_utf8(tmp_path: Path) -> None:
    empty = tmp_path / "empty.log"
    empty.write_bytes(b"")
    encoded = tmp_path / "encoded.log"
    encoded.write_bytes(b"\x81not utf8\nsecond")

    empty_preview = preview_project_file(empty)
    encoded_preview = preview_project_file(encoded)

    assert empty_preview["empty"] is True
    assert empty_preview["line_count"] == 0
    assert encoded_preview["empty"] is False
    assert encoded_preview["line_count"] == 2
    assert "not utf8" in encoded_preview["first_line"]


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value)
