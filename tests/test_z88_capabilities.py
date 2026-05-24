from __future__ import annotations

from pathlib import Path

from z88_bridge import current_capabilities, summarize_native_project_capability


def test_current_capabilities_report_confirmed_and_guided_methods() -> None:
    capabilities = current_capabilities()

    assert capabilities["oc_h8_generated"]["status"] == "confirmed"
    assert capabilities["toss_native_generation"]["status"] == "guided_only"
    assert capabilities["sko_native_generation"]["status"] == "guided_only"
    assert capabilities["tetrahedral_native_generation"]["status"] == "deferred"


def test_summarize_native_project_capability_maps_optalgorithm(tmp_path: Path) -> None:
    project = tmp_path / "toss_project"
    project.mkdir()
    (project / "z88control.txt").write_text(
        "TOSOLVER START\n   OPTALGORITHM 3\nTOSOLVER END\n",
        encoding="utf-8",
    )

    summary = summarize_native_project_capability(project)

    assert summary["optalgorithm"] == 3
    assert summary["method"] == "toss"
    assert summary["automation_status"] == "guided_only"
