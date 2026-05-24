from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ComplianceReference:
    name: str
    path: Path
    expected_final_compliance: float
    tolerance_fraction: float = 0.005


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _final_compliance(result: dict[str, Any]) -> float | None:
    histories = result.get("histories")
    if not isinstance(histories, dict):
        return None
    compliance = histories.get("overall_compliance")
    if not isinstance(compliance, dict):
        return None
    value = compliance.get("final_value")
    if isinstance(value, int | float):
        return float(value)
    values = compliance.get("values")
    if isinstance(values, list) and values and isinstance(values[-1], int | float):
        return float(values[-1])
    return None


def _summary_has_rows(summary: Any) -> bool:
    return isinstance(summary, dict) and isinstance(summary.get("row_count"), int) and summary["row_count"] > 0


def _check_reference(reference: ComplianceReference) -> dict[str, Any]:
    check: dict[str, Any] = {
        "name": reference.name,
        "path": str(reference.path),
        "expected_final_compliance": reference.expected_final_compliance,
        "tolerance_fraction": reference.tolerance_fraction,
    }
    if not reference.path.exists():
        check.update({"status": "missing", "message": "reference result JSON is missing"})
        return check

    try:
        result = _load_json(reference.path)
    except Exception as exc:
        check.update({"status": "failed", "message": f"could not read result JSON: {exc}"})
        return check

    actual = _final_compliance(result)
    check["actual_final_compliance"] = actual
    if actual is None:
        check.update({"status": "failed", "message": "overall compliance final value is missing"})
        return check

    delta = abs(actual - reference.expected_final_compliance)
    allowed = abs(reference.expected_final_compliance) * reference.tolerance_fraction
    check["absolute_delta"] = delta
    check["allowed_delta"] = allowed
    check["status"] = "passed" if delta <= allowed else "failed"
    return check


def _check_online_workflow(path: Path) -> dict[str, Any]:
    check: dict[str, Any] = {"name": "online_stl_workflows", "path": str(path)}
    if not path.exists():
        check.update({"status": "missing", "message": "online STL workflow report is missing"})
        return check

    try:
        report = _load_json(path)
    except Exception as exc:
        check.update({"status": "failed", "message": f"could not read workflow report: {exc}"})
        return check

    sources = report.get("sources")
    if not isinstance(sources, list) or not sources:
        check.update({"status": "failed", "message": "workflow report has no sources"})
        return check

    source_checks: list[dict[str, Any]] = []
    for source in sources:
        item: dict[str, Any] = {
            "name": source.get("name") if isinstance(source, dict) else None,
            "status": "failed",
        }
        if not isinstance(source, dict):
            item["message"] = "source entry is not an object"
            source_checks.append(item)
            continue

        workflow = source.get("workflow")
        if not isinstance(workflow, dict):
            item["message"] = "workflow result missing"
            source_checks.append(item)
            continue

        histories = workflow.get("histories")
        displacement = workflow.get("displacement_summary")
        stress = workflow.get("stress_summary")
        nodal_stress = stress.get("nodal") if isinstance(stress, dict) else None
        elemental_stress = stress.get("elemental") if isinstance(stress, dict) else None
        compliance = histories.get("overall_compliance") if isinstance(histories, dict) else None
        final_compliance = compliance.get("final_value") if isinstance(compliance, dict) else None

        item.update(
            {
                "workflow_status": workflow.get("status"),
                "optimizer_status": workflow.get("optimizer_status"),
                "displacement_status": workflow.get("displacement_status"),
                "stress_status": workflow.get("stress_status"),
                "final_compliance": final_compliance,
                "max_displacement": displacement.get("max_magnitude") if isinstance(displacement, dict) else None,
                "max_nodal_stress": nodal_stress.get("max_value") if isinstance(nodal_stress, dict) else None,
                "max_elemental_stress": elemental_stress.get("max_value") if isinstance(elemental_stress, dict) else None,
            }
        )

        passed = (
            source.get("status") == "ok"
            and workflow.get("optimizer_status") == "completed"
            and workflow.get("displacement_status") == "completed"
            and workflow.get("stress_status") == "completed"
            and isinstance(final_compliance, int | float)
            and isinstance(displacement, dict)
            and isinstance(displacement.get("max_magnitude"), int | float)
            and _summary_has_rows(nodal_stress)
            and _summary_has_rows(elemental_stress)
        )
        item["status"] = "passed" if passed else "failed"
        source_checks.append(item)

    failed = [item for item in source_checks if item.get("status") != "passed"]
    check["sources"] = source_checks
    check["status"] = "passed" if not failed else "failed"
    return check


def _check_json_status(name: str, path: Path, expected_statuses: set[str]) -> dict[str, Any]:
    check: dict[str, Any] = {"name": name, "path": str(path), "expected_statuses": sorted(expected_statuses)}
    if not path.exists():
        check.update({"status": "missing", "message": "gate evidence JSON is missing"})
        return check
    try:
        data = _load_json(path)
    except Exception as exc:
        check.update({"status": "failed", "message": f"could not read gate evidence: {exc}"})
        return check
    observed = data.get("status")
    check["observed_status"] = observed
    check["status"] = "recorded" if observed in expected_statuses else "failed"
    return check


def run_accuracy_gate(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(
        _check_reference(
            ComplianceReference(
                name="1_Balken_OC_gui_compliance",
                path=root / "z88_assets" / "examples" / "post" / "1_Balken_OC" / "z88_native_results.json",
                expected_final_compliance=2.21419985143696,
            )
        )
    )
    checks.append(
        _check_reference(
            ComplianceReference(
                name="2_Querlenker_OC_gui_compliance",
                path=root / "z88_assets" / "examples" / "post" / "2_Querlenker_OC" / "z88_native_results.json",
                expected_final_compliance=521.1895650750,
            )
        )
    )
    checks.append(_check_online_workflow(root / "z88_assets" / "outputs" / "online_stl_validation_workflow.json"))
    checks.append(
        _check_json_status(
            "tetgen_simple_cube_gate",
            root / "z88_assets" / "outputs" / "tetgen_probe" / "online_wikimedia_cube" / "tetgen_probe.json",
            {"completed"},
        )
    )
    checks.append(
        _check_json_status(
            "tetgen_nist_artifact_gate",
            root / "z88_assets" / "outputs" / "tetgen_probe" / "online_nist_am_test_artifact" / "tetgen_probe.json",
            {"failed"},
        )
    )

    hard_failed = [item for item in checks if item.get("status") == "failed"]
    missing = [item for item in checks if item.get("status") == "missing"]
    passed = [item for item in checks if item.get("status") == "passed"]
    recorded = [item for item in checks if item.get("status") == "recorded"]
    status = "passed" if not hard_failed and not missing else "partial"
    return {
        "schema_version": 1,
        "status": status,
        "passed_count": len(passed),
        "recorded_count": len(recorded),
        "missing_count": len(missing),
        "failed_count": len(hard_failed),
        "checks": checks,
        "notes": [
            "This gate validates confirmed OC fixture compliance and generated H8 voxel workflows.",
            "TOSS/SKO, large GUI-fixture stress, and general tetra generation remain capability gates, not passed accuracy gates.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current Z88 integration accuracy evidence gate.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("z88_assets") / "outputs" / "accuracy_gate.json",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    report = run_accuracy_gate(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
