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
            name="generated_h8_topology",
            status="confirmed",
            detail="Generated H8 voxel projects can run OC, TOSS, and SKO through the SICCG workflow.",
            evidence=(
                "structural sample OC/TOSS/SKO method matrix",
                "native H8 writer tests",
                "generated topology workflow tests",
            ),
        ),
        Z88Capability(
            name="oc_gui_generated_replay",
            status="confirmed",
            detail="GUI-generated OC optimizer folders can be replayed with the SICCG solver patch.",
            evidence=("1_Balken_OC replay", "2_Querlenker_OC replay"),
        ),
        Z88Capability(
            name="copied_gui_toss_replay",
            status="guided_only",
            detail="Copied GUI TOSS fixture replay is not automated because required GUI/intermediate files are not confirmed.",
            evidence=("seeded z88rTOSS reaches Z88MANAGE.TXT gate on copied pre fixtures",),
        ),
        Z88Capability(
            name="copied_gui_sko_replay",
            status="guided_only",
            detail="Copied GUI SKO fixture replay is not automated; generated H8 SKO is confirmed separately.",
            evidence=("OPTALGORITHM 4 observed in bundled SKO fixture", "generated H8 SKO method matrix passed"),
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
    write_json = Path(project_dir) / "z88_native_project_write.json"
    if method in {"oc", "toss", "sko"} and write_json.is_file():
        status = "confirmed_generated_h8"
    elif method == "oc":
        status = "confirmed_if_gui_generated"
    elif method in {"toss", "sko"}:
        status = "guided_only_for_copied_gui_fixtures"
    else:
        status = "unknown"
    return {
        "project_dir": str(Path(project_dir)),
        "optalgorithm": algorithm,
        "method": method,
        "automation_status": status,
        "summary_warnings": summary.get("warnings", []),
    }
