from __future__ import annotations

from pathlib import Path

from z88_bridge import (
    build_displacement_postprocess_command,
    build_stress_postprocess_command,
    classify_postprocess_run,
    classify_stress_postprocess_run,
    find_latest_constitutive_law,
)


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Z88Arion.exe").write_text("", encoding="utf-8")
    (bin_dir / "z88rofl.exe").write_text("", encoding="utf-8")
    (bin_dir / "z88rTOSS.exe").write_text("", encoding="utf-8")
    return root


def _native_project(path: Path) -> Path:
    path.mkdir()
    (path / "z88i1.txt").write_text("i1", encoding="utf-8")
    (path / "z88i2.txt").write_text("i2", encoding="utf-8")
    material = path / "ConstitutiveLaw"
    material.mkdir()
    (material / "z88mat001.txt").write_text("old", encoding="utf-8")
    (material / "z88mat010.txt").write_text("latest", encoding="utf-8")
    return path


def test_find_latest_constitutive_law_uses_highest_iteration(tmp_path: Path) -> None:
    project = _native_project(tmp_path / "project")

    latest = find_latest_constitutive_law(project)

    assert latest.name == "z88mat010.txt"


def test_build_displacement_postprocess_command_uses_observed_argv(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "Z88ArionV3")
    project = _native_project(tmp_path / "project")

    command, output = build_displacement_postprocess_command(project, install_root=install)

    assert command[0].endswith("z88rofl.exe")
    assert command[1:4] == ["-U", "-SICCG", "Displacements\\Displacements_final.txt"]
    assert command[4:] == ["ConstitutiveLaw\\z88mat010.txt", "z88i1.txt", "z88i2.txt"]
    assert output == project / "Displacements" / "Displacements_final.txt"


def test_build_stress_postprocess_command_uses_observed_argv(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "Z88ArionV3")
    project = _native_project(tmp_path / "project")

    command, nodal, element, energy = build_stress_postprocess_command(
        project,
        install_root=install,
    )

    assert command[0].endswith("z88rTOSS.exe")
    assert command[1:4] == ["-SIG", "-SICCG", "Knotenspannungen\\Knot_final.txt"]
    assert command[4:] == [
        "ConstitutiveLaw\\z88mat010.txt",
        "z88i1.txt",
        "z88i2.txt",
        "Stresses_ELE\\Stress_ele_final.txt",
        "tmp\\ElementEnergy_final.txt",
    ]
    assert nodal == project / "Knotenspannungen" / "Knot_final.txt"
    assert element == project / "Stresses_ELE" / "Stress_ele_final.txt"
    assert energy == project / "tmp" / "ElementEnergy_final.txt"


def test_classify_postprocess_accepts_z88_success_marker_with_negative_returncode() -> None:
    status = classify_postprocess_run(
        returncode=-12345,
        timed_out=False,
        stdout=">>> Z88R >>> Programm erfolgreich gelaufen!",
        output_exists=True,
    )

    assert status == "completed"


def test_classify_postprocess_reports_missing_inputs() -> None:
    status = classify_postprocess_run(
        returncode=1,
        timed_out=False,
        stdout="Pfadangabe und Dateiname fuer Materialdatei fehlt!",
        output_exists=False,
    )

    assert status == "missing_inputs"


def test_classify_stress_postprocess_requires_success_and_outputs() -> None:
    status = classify_stress_postprocess_run(
        returncode=4294954951,
        timed_out=False,
        stdout=">>> Z88RTOSS >>> Programm erfolgreich gelaufen!",
        nodal_output_exists=True,
        element_output_exists=True,
    )

    assert status == "completed"


def test_classify_stress_postprocess_reports_windows_access_violation_as_crash() -> None:
    status = classify_stress_postprocess_run(
        returncode=0xC0000005,
        timed_out=False,
        stdout="",
        nodal_output_exists=False,
        element_output_exists=False,
    )

    assert status == "crashed"


def test_classify_postprocess_keeps_observed_success_sentinel_completed() -> None:
    status = classify_postprocess_run(
        returncode=-12345,
        timed_out=False,
        stdout=">>> Z88R >>> Programm erfolgreich gelaufen!",
        output_exists=True,
    )

    assert status == "completed"
