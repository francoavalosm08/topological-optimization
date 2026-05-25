from __future__ import annotations

import json
from pathlib import Path

from z88_bridge import (
    collect_native_results,
    inventory_snapshot_folder,
    parse_counted_scalar_field_summary,
    parse_displacement_summary,
    parse_scalar_field_summary,
    parse_scalar_history,
    parse_youngs_modulus_summary,
)


def test_parse_scalar_history_reads_values_and_fortran_exponents(tmp_path: Path) -> None:
    history_file = tmp_path / "OverallCompliance.txt"
    history_file.write_text(
        "\n# comment\n +1.250000E+00\n +2.500000D+01\n",
        encoding="utf-8",
    )

    history = parse_scalar_history(history_file, name="overall_compliance")

    assert history.name == "overall_compliance"
    assert history.count == 2
    assert history.values == (1.25, 25.0)
    assert history.final_value == 25.0
    assert history.warnings == ()
    assert history.parse_errors == ()


def test_parse_scalar_history_reports_malformed_lines_without_crashing(tmp_path: Path) -> None:
    history_file = tmp_path / "OverallCompliance.txt"
    history_file.write_bytes(b"+1.0\n\x81bad\n+3.0\n")

    history = parse_scalar_history(history_file)

    assert history.values == (1.0, 3.0)
    assert len(history.parse_errors) == 1
    assert "invalid float" in history.parse_errors[0]


def test_inventory_snapshot_folder_extracts_iteration_and_hash(tmp_path: Path) -> None:
    folder = tmp_path / "PhysicalDensity"
    folder.mkdir()
    (folder / "PhysicalDensity001.txt").write_text("1 0.5\n", encoding="utf-8")
    (folder / "PhysicalDensity010.txt").write_text("1 0.7\n", encoding="utf-8")

    inventory = inventory_snapshot_folder(tmp_path, "PhysicalDensity", name="physical_density")

    assert inventory.name == "physical_density"
    assert inventory.count == 2
    assert inventory.first_iteration == 1
    assert inventory.last_iteration == 10
    assert len(inventory.files[0].sha256) == 64
    assert inventory.final_summary is not None
    assert inventory.final_summary.row_count == 1
    assert inventory.final_summary.max_value == 0.7


def test_parse_scalar_field_summary_streams_two_column_rows(tmp_path: Path) -> None:
    field = tmp_path / "PhysicalDensity010.txt"
    field.write_text(
        """
0
3
1 +0.0000000000000000E+00
2 +5.0000000000000000E-01
3 +1.0000000000000000E+00
""".strip(),
        encoding="utf-8",
    )

    summary = parse_scalar_field_summary(field)

    assert summary.row_count == 3
    assert summary.min_value == 0.0
    assert summary.max_value == 1.0
    assert summary.mean_value == 0.5
    assert summary.min_id == 1
    assert summary.max_id == 3
    assert summary.zero_count == 1
    assert summary.nonzero_count == 2
    assert summary.parse_errors == ()


def test_parse_youngs_modulus_summary_supports_sko_value_poisson_rows(tmp_path: Path) -> None:
    field = tmp_path / "YoungsModulus_SKO_Iteration1.txt"
    field.write_text("68900 0.33\n60000 0.33\n", encoding="utf-8")

    summary = parse_youngs_modulus_summary(field)

    assert summary.row_count == 2
    assert summary.min_value == 60000
    assert summary.max_value == 68900
    assert summary.min_id == 2
    assert summary.max_id == 1


def test_parse_counted_scalar_field_summary_validates_header_count(tmp_path: Path) -> None:
    field = tmp_path / "Knot_final.txt"
    field.write_text(
        """
3
1 +1.0E+00
2 +2.0E+00
3 +3.0E+00
""".strip(),
        encoding="utf-8",
    )

    summary = parse_counted_scalar_field_summary(field)

    assert summary.row_count == 3
    assert summary.max_id == 3
    assert summary.max_value == 3.0
    assert summary.warnings == ()


def test_collect_native_results_parses_oc_scalar_histories_and_snapshots(tmp_path: Path) -> None:
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    (tmp_dir / "OverallCompliance.txt").write_text("+1.0\n+2.0\n", encoding="utf-8")
    (tmp_dir / "AktuellesVolumen.txt").write_text("+3.0\n", encoding="utf-8")
    (tmp_dir / "Abbruchkriterium_SIMP.txt").write_text("+4.0E-04\n", encoding="utf-8")
    (tmp_dir / "G\u00fcte der 0-1-Verteilung.txt").write_text("+5.0E-02\n", encoding="utf-8")
    for folder_name in ("PhysicalDensity", "DesignResponse", "StrainEnergy", "YoungsModulus"):
        folder = tmp_path / folder_name
        folder.mkdir()
        (folder / f"{folder_name}001.txt").write_text("1 1.0\n", encoding="utf-8")

    summary = collect_native_results(tmp_path)

    assert summary.status == "collected"
    assert summary.histories["overall_compliance"].final_value == 2.0
    assert summary.histories["current_volume"].final_value == 3.0
    assert summary.histories["simp_convergence"].final_value == 4.0e-4
    assert summary.histories["zero_one_distribution_quality"].final_value == 5.0e-2
    assert summary.snapshots["physical_density"].last_iteration == 1
    assert summary.snapshots["physical_density"].final_summary is not None
    assert summary.snapshots["physical_density"].final_summary.row_count == 1
    assert summary.parse_errors == ()


def test_parse_displacement_summary_reports_max_magnitude(tmp_path: Path) -> None:
    displacement = tmp_path / "Displacements_final.txt"
    displacement.write_text(
        """
Ausgabedatei Z88O2.TXT: Verschiebungen
Knoten         U(1)              U(2)              U(3)
    1   +3.0000000E+000   +4.0000000E+000   +0.0000000E+000
    2   +1.0000000E+000   +2.0000000E+000   +2.0000000E+000
""".strip(),
        encoding="utf-8",
    )

    summary = parse_displacement_summary(displacement)

    assert summary.node_count == 2
    assert summary.components_per_node == 3
    assert summary.max_node == 1
    assert summary.max_magnitude == 5.0
    assert summary.parse_errors == ()


def test_collect_native_results_includes_displacement_summary_when_present(tmp_path: Path) -> None:
    displacements = tmp_path / "Displacements"
    displacements.mkdir()
    (displacements / "Displacements_final.txt").write_text(
        "    1   +0.0000000E+000   +5.0000000E+000   +0.0000000E+000\n",
        encoding="utf-8",
    )

    summary = collect_native_results(tmp_path)

    assert summary.displacement is not None
    assert summary.displacement.max_node == 1
    assert summary.displacement.max_magnitude == 5.0


def test_collect_native_results_includes_stress_summary_when_present(tmp_path: Path) -> None:
    nodal = tmp_path / "Knotenspannungen"
    elemental = tmp_path / "Stresses_ELE"
    nodal.mkdir()
    elemental.mkdir()
    (nodal / "Knot_final.txt").write_text("2\n1 +1.0E+00\n2 +3.0E+00\n", encoding="utf-8")
    (elemental / "Stress_ele_final.txt").write_text("1\n1 +5.0E+00\n", encoding="utf-8")

    summary = collect_native_results(tmp_path)

    assert summary.stress is not None
    assert summary.stress.nodal is not None
    assert summary.stress.nodal.max_value == 3.0
    assert summary.stress.elemental is not None
    assert summary.stress.elemental.max_value == 5.0


def test_collect_native_results_marks_missing_outputs(tmp_path: Path) -> None:
    summary = collect_native_results(tmp_path)

    assert summary.status == "missing_outputs"
    assert summary.parse_errors == ()
    assert any("missing scalar history" in warning for warning in summary.warnings)


def test_native_result_summary_writes_json(tmp_path: Path) -> None:
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    (tmp_dir / "OverallCompliance.txt").write_text("+1.0\n", encoding="utf-8")

    summary = collect_native_results(tmp_path)
    output = tmp_path / "z88_native_results.json"
    summary.write_json(output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["histories"]["overall_compliance"]["final_value"] == 1.0
