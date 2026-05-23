from __future__ import annotations

from pathlib import Path

from scripts.z88_headless_probe import (
    _classify,
    _copy_fixture_for_probe,
    _diff_has_changes,
    _parse_candidate_argv,
    _seed_runtime_files,
)


def test_probe_classifies_timeout() -> None:
    status = _classify([], {"timed_out": True, "returncode": None})

    assert status == "timed_out"


def test_probe_classifies_windows_crash() -> None:
    status = _classify([], {"timed_out": False, "returncode": 0xC0000135})

    assert status == "crashed"


def test_probe_classifies_signed_windows_crash() -> None:
    status = _classify([], {"timed_out": False, "returncode": -1073741795})

    assert status == "crashed"


def test_probe_classifies_z88_success_marker_before_negative_returncode() -> None:
    status = _classify(
        [],
        {
            "timed_out": False,
            "returncode": -12345,
            "stdout_preview": ">>> Z88R >>> Programm erfolgreich gelaufen!",
            "stderr_preview": "",
        },
    )

    assert status == "runs_from_cwd"


def test_probe_classifies_missing_solver_files() -> None:
    status = _classify(
        [{"timed_out": False, "stdout_preview": "### cannot open Z88.DYN ..stop ###", "stderr_preview": ""}],
        None,
    )

    assert status == "needs_solver_files"


def test_probe_classifies_missing_project_files_from_log_preview() -> None:
    status = _classify(
        [],
        {"timed_out": False, "returncode": 0xC0000417, "stdout_preview": "", "stderr_preview": ""},
        extra_output="opening file Z88.DYN\n### kann Z88MANAGE.TXT nicht oeffnen ..Stop ###",
    )

    assert status == "needs_project_files"


def test_probe_classifies_usage_errors_before_failed() -> None:
    status = _classify(
        [],
        {
            "timed_out": False,
            "returncode": 1,
            "stdout_preview": "### Richtiger Aufruf: z88rTOSS -c -2.Flag ###",
            "stderr_preview": "",
        },
    )

    assert status == "usage_error"


def test_probe_classifies_converter_usage_errors() -> None:
    status = _classify(
        [],
        {
            "timed_out": False,
            "returncode": 0,
            "stdout_preview": "Fehlerhafter Programmaufruf!\nBitte Flag fuer die Sprache angeben",
            "stderr_preview": "",
        },
    )

    assert status == "usage_error"


def test_probe_classifies_converter_failure_before_crash() -> None:
    status = _classify(
        [],
        {
            "timed_out": False,
            "returncode": 0xFFFFFFFF,
            "stdout_preview": "Problem while writing z88i1.txt. See file Z88AG2OI.LOG",
            "stderr_preview": "",
        },
    )

    assert status == "conversion_failed"


def test_probe_classifies_project_mutation() -> None:
    diff = {"counts": {"added": 1, "removed": 0, "modified": 0}}
    status = _classify([], {"timed_out": False, "returncode": 1}, diff)

    assert status == "mutated_project"


def test_probe_classifies_successful_cwd_run() -> None:
    diff = {"counts": {"added": 1, "removed": 0, "modified": 0}}
    status = _classify([], {"timed_out": False, "returncode": 0}, diff)

    assert status == "runs_from_cwd"


def test_copy_fixture_for_probe_does_not_mutate_source(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    source_file = fixture / "z88control.txt"
    source_file.write_text("original", encoding="utf-8")
    work_root = tmp_path / "work"

    copy = _copy_fixture_for_probe(fixture, work_root, "Z88OC")
    (copy / "z88control.txt").write_text("changed", encoding="utf-8")

    assert source_file.read_text(encoding="utf-8") == "original"
    assert (work_root / "Z88OC" / "z88control.txt").read_text(encoding="utf-8") == "changed"


def test_seed_runtime_files_uses_expected_z88dyn_name(tmp_path: Path) -> None:
    runtime = tmp_path / "z88.dyn"
    runtime.write_text("runtime config", encoding="utf-8")
    destination = tmp_path / "work"
    destination.mkdir()

    seeded = _seed_runtime_files(destination, [runtime])

    assert (destination / "Z88.DYN").read_text(encoding="utf-8") == "runtime config"
    assert seeded == [
        {
            "source": str(runtime),
            "destination": str(destination / "Z88.DYN"),
            "relative_path": "Z88.DYN",
            "bytes": len("runtime config"),
        }
    ]


def test_diff_change_detection_ignores_seeded_runtime_file() -> None:
    diff = {
        "counts": {"added": 1, "removed": 0, "modified": 0},
        "added": {"Z88.DYN": {"path": "Z88.DYN"}},
    }

    assert not _diff_has_changes(diff, ignored_added={"Z88.DYN"})


def test_parse_candidate_argv() -> None:
    assert _parse_candidate_argv(["-t -siccg", "-c -sorcg"]) == [
        ["-t", "-siccg"],
        ["-c", "-sorcg"],
    ]
