from __future__ import annotations

from pathlib import Path

import pytest

from z88_bridge import (
    classify_generated_optimizer_run,
    normalize_solver_arg,
    prepare_generated_optimizer_project,
)


def _generated_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "generated"
    project.mkdir()
    bin_dir = tmp_path / "Z88ArionV3" / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (project / "Z88Arion.pth").write_text("old_bin\nold_project\n", encoding="utf-8")
    (project / "Z88Arion.fea").write_text(
        "\n".join(
            [
                "z88rofl.exe -OTM -PARAO",
                "z88rofl.exe -IE -PARAO",
                "z88rTOSS.exe -C -PARAO",
            ]
        ),
        encoding="utf-8",
    )
    return project, bin_dir


def test_normalize_solver_arg_accepts_names_and_flags() -> None:
    assert normalize_solver_arg("siccg") == "-SICCG"
    assert normalize_solver_arg("-SICCG") == "-SICCG"
    assert normalize_solver_arg("pardiso") == "-PARAO"


def test_normalize_solver_arg_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported Z88 solver mode"):
        normalize_solver_arg("not-a-solver")


def test_prepare_generated_optimizer_project_patches_pth_and_fea(tmp_path: Path) -> None:
    project, bin_dir = _generated_project(tmp_path)

    result = prepare_generated_optimizer_project(project, install_bin_dir=bin_dir, solver="siccg")

    assert result.solver_arg == "-SICCG"
    assert result.replacements == 3
    assert (project / "Z88Arion.pth").read_text(encoding="utf-8").splitlines() == [
        str(bin_dir.resolve()),
        str(project.resolve()),
    ]
    assert "-PARAO" not in (project / "Z88Arion.fea").read_text(encoding="utf-8")
    assert (project / "Z88Arion.fea").read_text(encoding="utf-8").count("-SICCG") == 3


def test_prepare_generated_optimizer_project_requires_generated_files(tmp_path: Path) -> None:
    project = tmp_path / "generated"
    project.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="Z88Arion.pth"):
        prepare_generated_optimizer_project(project, install_bin_dir=bin_dir)


def test_classify_generated_optimizer_success() -> None:
    status = classify_generated_optimizer_run(
        returncode=0,
        timed_out=False,
        z88oc_log="Optimierungsaufgabe in 39 Iterationen gelöst!\n>>> Programm erfolgreich gelaufen!",
    )

    assert status == "completed"


def test_classify_generated_optimizer_windows_crash_signed_returncode() -> None:
    status = classify_generated_optimizer_run(
        returncode=-1073741795,
        timed_out=False,
        stdout="*** Start PARDISO ***",
    )

    assert status == "crashed"


def test_classify_generated_optimizer_solver_failure() -> None:
    status = classify_generated_optimizer_run(
        returncode=1,
        timed_out=False,
        stdout="### Diagonalelement im G-System Null oder negativ..Stop ###",
    )

    assert status == "solver_failed"
