"""Best-available backend orchestration for Z88 workflows."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

from .workflow import GeneratedOCWorkflowResult, run_generated_topology_workflow


BackendMode = Literal["generated_topology", "guided_handoff"]


@dataclass(frozen=True)
class BackendRunResult:
    project_dir: str
    status: str
    mode: BackendMode
    workflow: GeneratedOCWorkflowResult | None = None
    handoff_file: str | None = None
    messages: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["workflow"] = self.workflow.to_dict() if self.workflow else None
        return data

    def compact_dict(self) -> dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "status": self.status,
            "mode": self.mode,
            "workflow": self.workflow.compact_dict() if self.workflow else None,
            "handoff_file": self.handoff_file,
            "messages": list(self.messages),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def run_best_available_backend(
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
    solver: str = "siccg",
    optimizer_timeout_s: float = 900.0,
    displacement_timeout_s: float = 300.0,
    stress_timeout_s: float = 300.0,
    run_optimizer: bool = True,
    generate_displacements: bool = True,
    generate_stress: bool = False,
) -> BackendRunResult:
    """Run the best confirmed Z88 backend path for a folder."""
    project_dir = Path(project_dir).resolve()
    generated_project_dir = find_generated_topology_project_dir(project_dir)
    if generated_project_dir is not None:
        workflow = run_generated_topology_workflow(
            generated_project_dir,
            install_root=install_root,
            solver=solver,
            optimizer_timeout_s=optimizer_timeout_s,
            displacement_timeout_s=displacement_timeout_s,
            stress_timeout_s=stress_timeout_s,
            run_optimizer=run_optimizer,
            generate_displacements=generate_displacements,
            generate_stress=generate_stress,
        )
        status = "completed" if workflow.status == "completed" else "partial"
        result = BackendRunResult(
            project_dir=str(project_dir),
            status=status,
            mode="generated_topology",
            workflow=workflow,
            messages=tuple(workflow.messages),
        )
    else:
        handoff_file = ensure_guided_handoff(project_dir)
        result = BackendRunResult(
            project_dir=str(project_dir),
            status="guided_handoff_required",
            mode="guided_handoff",
            handoff_file=str(handoff_file),
            messages=(
                "No GUI-generated Z88 OC optimizer files were found.",
                "Open the prepared STL/native project in Z88Arion, run/export there, then collect results.",
            ),
        )
    result.write_json(project_dir / "z88_backend_result.json")
    return result


def find_generated_topology_project_dir(project_dir: str | Path) -> Path | None:
    """Find a folder with the confirmed generated topology execution contract."""
    root = Path(project_dir).resolve()
    candidates = [root]
    if (root / "z88_project").is_dir():
        candidates.append(root / "z88_project")
    for candidate in candidates:
        if _is_generated_topology_project(candidate):
            return candidate
    return None


def find_generated_oc_project_dir(project_dir: str | Path) -> Path | None:
    """Backward-compatible alias for generated topology project detection."""
    return find_generated_topology_project_dir(project_dir)


def ensure_guided_handoff(project_dir: str | Path) -> Path:
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    handoff = project_dir / "Z88_GUIDED_BACKEND_HANDOFF.md"
    if handoff.exists():
        return handoff
    lines = [
        "# Z88 Guided Backend Handoff",
        "",
        "This folder is not a generated Z88 optimizer project yet.",
        "",
        "## Required Manual Step",
        "",
        "1. Open Z88Arion.",
        "2. Import the STL or open the native project from this run folder.",
        "3. Configure material, loads, supports, passive regions, and optimizer settings.",
        "4. Start the optimization once so Z88Arion generates native optimizer files.",
        "5. Save/copy the completed generated project folder.",
        "6. Run `python scripts/z88_run_backend.py <generated-project-folder> --solver siccg`.",
        "",
        "The confirmed automated backend currently requires these files in the target folder:",
        "",
        "- `Z88Arion.pth`",
        "- `Z88Arion.fea`",
        "- `z88i1.txt`",
        "- `z88i2.txt`",
        "- `z88control.txt`",
        "- `ConstitutiveLaw/`",
        "",
    ]
    handoff.write_text("\n".join(lines), encoding="utf-8")
    return handoff


def _is_generated_topology_project(path: Path) -> bool:
    required = (
        "Z88Arion.pth",
        "Z88Arion.fea",
        "z88i1.txt",
        "z88i2.txt",
        "z88control.txt",
    )
    return all((path / name).is_file() for name in required) and (path / "ConstitutiveLaw").is_dir()
