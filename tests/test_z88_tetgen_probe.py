from __future__ import annotations

from pathlib import Path

from scripts.z88_tetgen_probe import _first_node_id


def test_first_node_id_reads_zero_based_structure(tmp_path: Path) -> None:
    structure = tmp_path / "z88structure.txt"
    structure.write_text(
        "3 2 1 6 0 #AURORA_V2\n"
        "   0  3   0.0   0.0   0.0\n"
        "   1  3   1.0   0.0   0.0\n",
        encoding="utf-8",
    )

    assert _first_node_id(structure) == 0


def test_first_node_id_returns_none_for_malformed_first_data_row(tmp_path: Path) -> None:
    structure = tmp_path / "z88structure.txt"
    structure.write_text(
        "3 2 1 6 0 #AURORA_V2\n"
        "node bad row\n",
        encoding="utf-8",
    )

    assert _first_node_id(structure) is None
