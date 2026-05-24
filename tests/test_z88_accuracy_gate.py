from __future__ import annotations

import json
from pathlib import Path

from scripts.z88_accuracy_gate import run_accuracy_gate


def _write_result(path: Path, final_compliance: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "collected",
                "histories": {"overall_compliance": {"final_value": final_compliance}},
            }
        ),
        encoding="utf-8",
    )


def test_accuracy_gate_passes_with_expected_local_evidence(tmp_path: Path) -> None:
    _write_result(
        tmp_path / "z88_assets" / "examples" / "post" / "1_Balken_OC" / "z88_native_results.json",
        2.21419985143696,
    )
    _write_result(
        tmp_path / "z88_assets" / "examples" / "post" / "2_Querlenker_OC" / "z88_native_results.json",
        521.1895650750068,
    )
    online = tmp_path / "z88_assets" / "outputs" / "online_stl_validation_workflow.json"
    online.parent.mkdir(parents=True, exist_ok=True)
    online.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "cube",
                        "status": "ok",
                        "workflow": {
                            "status": "partial",
                            "optimizer_status": "completed",
                            "displacement_status": "completed",
                            "stress_status": "completed",
                            "histories": {"overall_compliance": {"final_value": 1.0}},
                            "displacement_summary": {"max_magnitude": 0.1},
                            "stress_summary": {
                                "nodal": {"row_count": 2, "max_value": 3.0},
                                "elemental": {"row_count": 1, "max_value": 4.0},
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    for name, status in [
        ("online_wikimedia_cube", "completed"),
        ("online_nist_am_test_artifact", "failed"),
    ]:
        probe = tmp_path / "z88_assets" / "outputs" / "tetgen_probe" / name / "tetgen_probe.json"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(json.dumps({"status": status}), encoding="utf-8")

    report = run_accuracy_gate(tmp_path)

    assert report["status"] == "passed"
    assert report["passed_count"] == 3
    assert report["recorded_count"] == 2
    assert report["failed_count"] == 0


def test_accuracy_gate_is_partial_when_reference_missing(tmp_path: Path) -> None:
    report = run_accuracy_gate(tmp_path)

    assert report["status"] == "partial"
    assert report["missing_count"] > 0
