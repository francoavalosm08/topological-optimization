"""Headless execution helpers for GUI-generated Z88Arion optimizer projects."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Literal

from .adapter import Z88BridgeError, discover_installation


SOLVER_ARGS = {
    "parao": "-PARAO",
    "pardiso": "-PARAO",
    "siccg": "-SICCG",
    "sorcg": "-SORCG",
    "choly": "-CHOLY",
}
SOLVER_ARG_PATTERN = re.compile(r"-(?:PARAO|SICCG|SORCG|CHOLY)\b", re.IGNORECASE)
SUCCESS_MARKERS = (
    ">>> Programm erfolgreich gelaufen!",
    "Optimierungsaufgabe",
)
SOLVER_FAILURE_MARKERS = (
    "Diagonalelement",
    "Randbedingungen pruefen",
    "Randbedingungen checken",
)
OPTIMIZER_FAILURE_MARKERS = (
    "Z88Arion mit Fehler beenden",
    "Solverinfo: Fehler",
)


HeadlessStatus = Literal[
    "completed",
    "crashed",
    "solver_failed",
    "optimizer_failed",
    "timed_out",
    "failed",
]


@dataclass(frozen=True)
class GeneratedOptimizerPreparation:
    project_dir: str
    z88arion_pth: str
    z88arion_fea: str
    install_bin_dir: str
    solver_arg: str
    replacements: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True)
class GeneratedOptimizerRunResult:
    project_dir: str
    command: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    elapsed_s: float
    solver_arg: str
    status: HeadlessStatus
    output_dir: str
    stdout_file: str
    stderr_file: str
    z88oc_log: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def normalize_solver_arg(solver: str) -> str:
    """Normalize a user-facing solver name or native flag to a Z88 solver flag."""
    key = solver.strip().lower()
    if key.startswith("-"):
        key = key[1:]
    try:
        return SOLVER_ARGS[key]
    except KeyError as exc:
        choices = ", ".join(sorted(SOLVER_ARGS))
        raise ValueError(f"Unsupported Z88 solver mode {solver!r}. Expected one of: {choices}") from exc


def prepare_generated_optimizer_project(
    project_dir: str | Path,
    *,
    install_bin_dir: str | Path,
    solver: str = "siccg",
) -> GeneratedOptimizerPreparation:
    """Patch GUI-generated optimizer files so z88optopus can run from cwd.

    Z88Arion writes two execution-control files before launching the optimizer:
    `Z88Arion.pth` stores the install bin path and project path, while
    `Z88Arion.fea` stores solver command templates. The GUI defaults to
    `-PARAO`; on this machine that PARDISO path crashes, while `-SICCG` runs.
    """
    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Generated Z88 project directory not found: {project_dir}")
    pth_path = project_dir / "Z88Arion.pth"
    fea_path = project_dir / "Z88Arion.fea"
    if not pth_path.exists():
        raise FileNotFoundError(f"Missing GUI-generated path file: {pth_path}")
    if not fea_path.exists():
        raise FileNotFoundError(f"Missing GUI-generated solver template: {fea_path}")

    install_bin_dir = Path(install_bin_dir).resolve()
    if not install_bin_dir.is_dir():
        raise FileNotFoundError(f"Z88 install bin directory not found: {install_bin_dir}")
    solver_arg = normalize_solver_arg(solver)

    pth_path.write_text(f"{install_bin_dir}\n{project_dir}\n", encoding="utf-8")
    fea_text = fea_path.read_text(encoding="utf-8", errors="replace")
    patched, replacements = SOLVER_ARG_PATTERN.subn(solver_arg, fea_text)
    if replacements == 0:
        raise ValueError(f"No solver flags found to patch in {fea_path}")
    fea_path.write_text(patched, encoding="utf-8")

    return GeneratedOptimizerPreparation(
        project_dir=str(project_dir),
        z88arion_pth=str(pth_path),
        z88arion_fea=str(fea_path),
        install_bin_dir=str(install_bin_dir),
        solver_arg=solver_arg,
        replacements=replacements,
    )


def classify_generated_optimizer_run(
    *,
    returncode: int | None,
    timed_out: bool,
    stdout: str = "",
    stderr: str = "",
    z88oc_log: str = "",
) -> HeadlessStatus:
    if timed_out:
        return "timed_out"
    combined = "\n".join((stdout, stderr, z88oc_log))
    if _is_windows_crash(returncode):
        return "crashed"
    if any(marker in combined for marker in SOLVER_FAILURE_MARKERS):
        return "solver_failed"
    if any(marker in combined for marker in OPTIMIZER_FAILURE_MARKERS):
        return "optimizer_failed"
    if returncode == 0 and any(marker in combined for marker in SUCCESS_MARKERS):
        return "completed"
    if returncode == 0:
        return "completed"
    return "failed"


def run_generated_optimizer_project(
    project_dir: str | Path,
    *,
    install_root: str | Path | None = None,
    solver: str = "siccg",
    timeout_s: float = 900.0,
    patch_project: bool = True,
    output_dir: str | Path | None = None,
) -> GeneratedOptimizerRunResult:
    """Run `z88optopus.exe` against a GUI-generated native project folder."""
    installation = discover_installation(install_root)
    if installation.optopus_exe is None:
        raise Z88BridgeError(f"z88optopus.exe not found under {installation.bin_dir}")
    project_dir = Path(project_dir).resolve()
    solver_arg = normalize_solver_arg(solver)
    if patch_project:
        preparation = prepare_generated_optimizer_project(
            project_dir,
            install_bin_dir=installation.bin_dir,
            solver=solver,
        )
        solver_arg = preparation.solver_arg

    output_dir = Path(output_dir) if output_dir is not None else project_dir / "z88_headless_run"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [str(installation.optopus_exe), "-parao"]
    started = time.time()
    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        proc = subprocess.run(
            command,
            cwd=str(project_dir),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        returncode = proc.returncode
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = _decode_process_output(exc.stdout)
        stderr = _decode_process_output(exc.stderr)
    elapsed = time.time() - started

    stdout_path = output_dir / "z88optopus.stdout.txt"
    stderr_path = output_dir / "z88optopus.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    log_path = project_dir / "Z88OC.log"
    z88oc_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    status = classify_generated_optimizer_run(
        returncode=returncode,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        z88oc_log=z88oc_log,
    )
    result = GeneratedOptimizerRunResult(
        project_dir=str(project_dir),
        command=tuple(command),
        returncode=returncode,
        timed_out=timed_out,
        elapsed_s=elapsed,
        solver_arg=solver_arg,
        status=status,
        output_dir=str(output_dir),
        stdout_file=str(stdout_path),
        stderr_file=str(stderr_path),
        z88oc_log=str(log_path) if log_path.exists() else None,
    )
    result.write_json(output_dir / "z88_headless_run.json")
    return result


def _is_windows_crash(returncode: int | None) -> bool:
    if returncode is None:
        return False
    unsigned = returncode + 2**32 if returncode < 0 else returncode
    return unsigned >= 0xC0000000


def _decode_process_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")
