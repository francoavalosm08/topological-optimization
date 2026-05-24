"""Machine-readable Z88 backend capability status."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .project_files import summarize_project_files


ALGORITHM_NAMES = {
    1: "oc",
    3: "toss",
    4: "sko",
}


@dataclass(frozen=True)
class Z88Capability:
    name: str
    status: str
    detail: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def current_capabilities() -> dict[str, dict[str, Any]]:
    """Return the currently proven automation status by method."""
    capabilities = (
        Z88Capability(
            name="oc_h8_generated",
            status="confirmed",
            detail="Generated H8 voxel projects can run through the SICCG OC workflow.",
            evidence=(
                "native OC/H8 writer smoke",
                "generated OC workflow smoke",
                "representative sample API/native writer tests",
            ),
        ),
        Z88Capability(
            name="oc_gui_generated_replay",
            status="confirmed",
            detail="GUI-generated OC optimizer folders can be replayed with the SICCG solver patch.",
            evidence=("1_Balken_OC replay", "2_Querlenker_OC replay"),
        ),
        Z88Capability(
            name="toss_native_generation",
            status="guided_only",
            detail="TOSS project generation is not automated because required GUI/intermediate files are not confirmed.",
            evidence=("seeded z88rTOSS reaches Z88MANAGE.TXT gate",),
        ),
        Z88Capability(
            name="sko_native_generation",
            status="guided_only",
            detail="SKO project generation is not automated because required GUI/intermediate files are not confirmed.",
            evidence=("OPTALGORITHM 4 observed in bundled SKO fixture",),
        ),
        Z88Capability(
            name="tetrahedral_native_generation",
            status="deferred",
            detail=(
                "TetGen can emit a zero-based z88structure.txt from OFF input, "
                "but complete tetrahedral native project generation is still blocked "
                "until the remaining GUI/intermediate file contract is confirmed."
            ),
            evidence=(
                "TetGen direct binary STL probe returns 'Wrong number of vertices'",
                "TetGen OFF probe writes #AURORA_V2 z88structure.txt with zero-based IDs",
                "H8 ordering confirmed only for the production writer",
            ),
        ),
        Z88Capability(
            name="large_gui_fixture_stress",
            status="unstable",
            detail="z88rTOSS -SIG crashes on copied GUI-generated OC fixtures with Windows access violation 3221225477.",
            evidence=("1_Balken_OC stress probe",),
        ),
    )
    return {item.name: item.to_dict() for item in capabilities}


def summarize_native_project_capability(project_dir: str | Path) -> dict[str, Any]:
    """Summarize the optimizer algorithm and current automation support for a project."""
    summary = summarize_project_files(project_dir)
    tosolver = summary.get("control", {}).get("TOSOLVER", {})
    algorithm = tosolver.get("OPTALGORITHM") if isinstance(tosolver, dict) else None
    method = ALGORITHM_NAMES.get(algorithm, "unknown")
    if method == "oc":
        status = "confirmed_if_gui_generated_or_h8_writer_output"
    elif method in {"toss", "sko"}:
        status = "guided_only"
    else:
        status = "unknown"
    return {
        "project_dir": str(Path(project_dir)),
        "optalgorithm": algorithm,
        "method": method,
        "automation_status": status,
        "summary_warnings": summary.get("warnings", []),
    }
