from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from z88_bridge import generate_sample_assets, run_packaging_preflight, write_crash_report


def test_crash_report_writes_traceback_context_and_selected_files(tmp_path: Path) -> None:
    context_file = tmp_path / "config.json"
    context_file.write_text('{"name": "test"}', encoding="utf-8")

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        report = write_crash_report(
            exc,
            root=tmp_path / "crash_reports",
            context={"project_dir": "example"},
            files=(context_file, tmp_path / "missing.log"),
        )

    report_dir = Path(report.report_dir)
    assert report_dir.is_dir()
    assert "RuntimeError: boom" in Path(report.traceback_file).read_text(encoding="utf-8")
    context = json.loads(Path(report.context_file).read_text(encoding="utf-8"))
    assert context["context"]["project_dir"] == "example"
    assert len(report.copied_files) == 1
    assert Path(report.copied_files[0]).name == "config.json"


def test_packaging_preflight_reports_status_and_checks() -> None:
    result = run_packaging_preflight()
    payload = result.to_dict()

    assert result.status in {"ok", "ok_with_warnings", "needs_attention"}
    assert payload["checks"]
    assert any(check["name"] == "python" for check in payload["checks"])
    assert any(check["name"] == "z88_installation" for check in payload["checks"])
    assert any(check["name"] == "packaging_entrypoint" for check in payload["checks"])
    assert any(check["name"] == "pyinstaller_spec" for check in payload["checks"])
    assert any(check["name"] == "web_ui" for check in payload["checks"])


def test_generate_sample_assets_writes_stls_and_catalog(tmp_path: Path) -> None:
    result = generate_sample_assets(tmp_path / "samples")

    catalog = json.loads(Path(result["catalog_json"]).read_text(encoding="utf-8"))
    assert result["sample_count"] == 5
    assert len(catalog["samples"]) == 5
    assert all(Path(sample["stl_path"]).is_file() for sample in catalog["samples"])
    assert {sample["recipe"] for sample in catalog["samples"]} == {
        "generic_bracket",
        "drone_motor_mount",
        "drone_landing_gear",
        "drone_gimbal_mount",
        "ring_wing_strut",
    }


def test_packaged_entrypoint_smoke_test_allows_missing_z88() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "packaging/z88_topopt_app.py",
            "--smoke-test",
            "--no-browser",
            "--allow-missing-z88",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "ok"
    assert payload["route_count"] > 0
