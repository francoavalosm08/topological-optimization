"""Postprocess helpers for generated Z88Arion optimizer projects."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Literal

from .adapter import Z88BridgeError, discover_installation
from .headless import normalize_solver_arg


MATERIAL_ITERATION_RE = re.compile(r"z88mat(\d+)\.txt$", re.IGNORECASE)
SUCCESS_MARKER = ">>> Z88R >>> Programm erfolgreich gelaufen!"

PostprocessStatus = Literal["completed", "missing_inputs", "timed_out", "crashed", "failed", "unsupported"]


@dataclass(frozen=True)
class Z88PostprocessRunResult:
    project_dir: str
    command: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    elapsed_s: float
    status: PostprocessStatus
    output_file: str
    stdout_file: str
    stderr_file: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


@dataclass(frozen=True)
class Z88StressPostprocessRunResult:
    project_dir: str
    command: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    elapsed_s: float
    status: PostprocessStatus
    nodal_output_file: str
    element_output_file: str
    energy_output_file: str
    stdout_file: str
    stderr_file: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def find_latest_constitutive_law(project_dir: str | Path) -> Path:
    """Return the highest-iteration material law file from OC/TOSS or SKO outputs."""
    project_dir = Path(project_dir)
    folders = (project_dir / "ConstitutiveLaw", project_dir / "ConstitutiveLaw_SKO")
    candidates: list[tuple[int, Path]] = []
    missing: list[Path] = []
    for folder in folders:
        if not folder.is_dir():
            missing.append(folder)
            continue
        for path in folder.glob("z88mat*.txt"):
            match = MATERIAL_ITERATION_RE.match(path.name)
            if match:
                candidates.append((int(match.group(1)), path))
    if not candidates:
        searched = ", ".join(str(folder) for folder in folders)
        if len(missing) == len(folders):
            raise FileNotFoundError(f"Missing material law folders: {searched}")
        raise FileNotFoundError(f"No z88matNNN.txt files found in {searched}")
    return max(candidates, key=lambda item: item[0])[1]


def build_displacement_postprocess_command(
    project_dir: str | Path,
    *,
    solver: str = "siccg",
    output_file: str | Path | None = None,
    material_file: str | Path | None = None,
    install_root: str | Path | None = None,
) -> tuple[list[str], Path]:
    """Build the observed `z88rofl -U` displacement postprocess command."""
    project_dir = Path(project_dir).resolve()
    installation = discover_installation(install_root)
    solver_exe = installation.bin_dir / "z88rofl.exe"
    if not solver_exe.exists():
        raise Z88BridgeError(f"z88rofl.exe not found under {installation.bin_dir}")
    z88i1 = project_dir / "z88i1.txt"
    z88i2 = project_dir / "z88i2.txt"
    missing = [path for path in (z88i1, z88i2) if not path.is_file()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing required solver input files: {names}")

    output = Path(output_file) if output_file is not None else project_dir / "Displacements" / "Displacements_final.txt"
    if not output.is_absolute():
        output = project_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)

    material = Path(material_file) if material_file is not None else find_latest_constitutive_law(project_dir)
    if not material.is_absolute():
        material = project_dir / material
    if not material.is_file():
        raise FileNotFoundError(f"Constitutive law file not found: {material}")

    command = [
        str(solver_exe),
        "-U",
        normalize_solver_arg(solver),
        _native_relative_arg(project_dir, output),
        _native_relative_arg(project_dir, material),
        _native_relative_arg(project_dir, z88i1),
        _native_relative_arg(project_dir, z88i2),
    ]
    return command, output


def run_displacement_postprocess(
    project_dir: str | Path,
    *,
    solver: str = "siccg",
    output_file: str | Path | None = None,
    material_file: str | Path | None = None,
    install_root: str | Path | None = None,
    timeout_s: float = 300.0,
    output_dir: str | Path | None = None,
) -> Z88PostprocessRunResult:
    """Generate a Z88O2 displacement file from a completed native project."""
    project_dir = Path(project_dir).resolve()
    command, displacement_output = build_displacement_postprocess_command(
        project_dir,
        solver=solver,
        output_file=output_file,
        material_file=material_file,
        install_root=install_root,
    )
    run_dir = Path(output_dir) if output_dir is not None else project_dir / "z88_postprocess_run"
    run_dir.mkdir(parents=True, exist_ok=True)
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

    stdout_path = run_dir / "z88rofl_u.stdout.txt"
    stderr_path = run_dir / "z88rofl_u.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    status = classify_postprocess_run(
        returncode=returncode,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        output_exists=displacement_output.is_file(),
    )
    result = Z88PostprocessRunResult(
        project_dir=str(project_dir),
        command=tuple(command),
        returncode=returncode,
        timed_out=timed_out,
        elapsed_s=elapsed,
        status=status,
        output_file=str(displacement_output),
        stdout_file=str(stdout_path),
        stderr_file=str(stderr_path),
    )
    result.write_json(run_dir / "z88_postprocess_run.json")
    return result


def build_stress_postprocess_command(
    project_dir: str | Path,
    *,
    solver: str = "siccg",
    nodal_output_file: str | Path | None = None,
    element_output_file: str | Path | None = None,
    energy_output_file: str | Path | None = None,
    material_file: str | Path | None = None,
    install_root: str | Path | None = None,
) -> tuple[list[str], Path, Path, Path]:
    """Build the observed `z88rTOSS -SIG` stress postprocess command."""
    project_dir = Path(project_dir).resolve()
    installation = discover_installation(install_root)
    solver_exe = installation.bin_dir / "z88rTOSS.exe"
    if not solver_exe.exists():
        raise Z88BridgeError(f"z88rTOSS.exe not found under {installation.bin_dir}")
    z88i1 = project_dir / "z88i1.txt"
    z88i2 = project_dir / "z88i2.txt"
    missing = [path for path in (z88i1, z88i2) if not path.is_file()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing required solver input files: {names}")

    nodal = Path(nodal_output_file) if nodal_output_file is not None else (
        project_dir / "Knotenspannungen" / "Knot_final.txt"
    )
    if not nodal.is_absolute():
        nodal = project_dir / nodal
    nodal.parent.mkdir(parents=True, exist_ok=True)

    element = Path(element_output_file) if element_output_file is not None else (
        project_dir / "Stresses_ELE" / "Stress_ele_final.txt"
    )
    if not element.is_absolute():
        element = project_dir / element
    element.parent.mkdir(parents=True, exist_ok=True)

    energy = Path(energy_output_file) if energy_output_file is not None else (
        project_dir / "tmp" / "ElementEnergy_final.txt"
    )
    if not energy.is_absolute():
        energy = project_dir / energy
    energy.parent.mkdir(parents=True, exist_ok=True)

    material = Path(material_file) if material_file is not None else find_latest_constitutive_law(project_dir)
    if not material.is_absolute():
        material = project_dir / material
    if not material.is_file():
        raise FileNotFoundError(f"Constitutive law file not found: {material}")

    command = [
        str(solver_exe),
        "-SIG",
        normalize_solver_arg(solver),
        _native_relative_arg(project_dir, nodal),
        _native_relative_arg(project_dir, material),
        _native_relative_arg(project_dir, z88i1),
        _native_relative_arg(project_dir, z88i2),
        _native_relative_arg(project_dir, element),
        _native_relative_arg(project_dir, energy),
    ]
    return command, nodal, element, energy


def run_stress_postprocess(
    project_dir: str | Path,
    *,
    solver: str = "siccg",
    nodal_output_file: str | Path | None = None,
    element_output_file: str | Path | None = None,
    energy_output_file: str | Path | None = None,
    material_file: str | Path | None = None,
    install_root: str | Path | None = None,
    timeout_s: float = 300.0,
    output_dir: str | Path | None = None,
) -> Z88StressPostprocessRunResult:
    """Generate observed nodal and element von-Mises/stress scalar files."""
    project_dir = Path(project_dir).resolve()
    _ensure_z88r_runtime(project_dir)
    command, nodal_output, element_output, energy_output = build_stress_postprocess_command(
        project_dir,
        solver=solver,
        nodal_output_file=nodal_output_file,
        element_output_file=element_output_file,
        energy_output_file=energy_output_file,
        material_file=material_file,
        install_root=install_root,
    )
    run_dir = Path(output_dir) if output_dir is not None else project_dir / "z88_stress_postprocess_run"
    run_dir.mkdir(parents=True, exist_ok=True)
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

    stdout_path = run_dir / "z88rtoss_sig.stdout.txt"
    stderr_path = run_dir / "z88rtoss_sig.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    status = classify_stress_postprocess_run(
        returncode=returncode,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        nodal_output_exists=nodal_output.is_file() and nodal_output.stat().st_size > 0,
        element_output_exists=element_output.is_file() and element_output.stat().st_size > 0,
    )
    result = Z88StressPostprocessRunResult(
        project_dir=str(project_dir),
        command=tuple(command),
        returncode=returncode,
        timed_out=timed_out,
        elapsed_s=elapsed,
        status=status,
        nodal_output_file=str(nodal_output),
        element_output_file=str(element_output),
        energy_output_file=str(energy_output),
        stdout_file=str(stdout_path),
        stderr_file=str(stderr_path),
    )
    result.write_json(run_dir / "z88_stress_postprocess_run.json")
    return result


def classify_postprocess_run(
    *,
    returncode: int | None,
    timed_out: bool,
    stdout: str = "",
    stderr: str = "",
    output_exists: bool = False,
) -> PostprocessStatus:
    if timed_out:
        return "timed_out"
    combined = stdout + "\n" + stderr
    if SUCCESS_MARKER in combined and output_exists:
        return "completed"
    if "fehlt" in combined or "cannot open" in combined.lower():
        return "missing_inputs"
    if _is_crash_returncode(returncode):
        return "crashed"
    if returncode == 0 and output_exists:
        return "completed"
    return "failed"


def classify_stress_postprocess_run(
    *,
    returncode: int | None,
    timed_out: bool,
    stdout: str = "",
    stderr: str = "",
    nodal_output_exists: bool = False,
    element_output_exists: bool = False,
) -> PostprocessStatus:
    if timed_out:
        return "timed_out"
    combined = stdout + "\n" + stderr
    if "fehlt" in combined or "cannot open" in combined.lower():
        return "missing_inputs"
    success = ">>> Z88RTOSS >>> Programm erfolgreich gelaufen!" in combined
    if success and nodal_output_exists and element_output_exists:
        return "completed"
    if _is_crash_returncode(returncode):
        return "crashed"
    if returncode == 0 and nodal_output_exists and element_output_exists:
        return "completed"
    return "failed"


def _native_relative_arg(project_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_dir)).replace("/", "\\")
    except ValueError:
        return str(path)


def _decode_process_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def _is_crash_returncode(returncode: int | None) -> bool:
    if returncode is None:
        return False
    # Windows access violation is commonly reported as unsigned 0xC0000005 by
    # Python subprocess on this machine. Negative codes represent terminated
    # processes on other platforms, but keep the observed Z88 success sentinel.
    return returncode == 0xC0000005 or (returncode < 0 and returncode != -12345)


def _ensure_z88r_runtime(project_dir: Path) -> None:
    target = project_dir / "Z88R.DYN"
    if target.exists():
        return
    source = project_dir / "z88rofl.dyn"
    if source.exists():
        shutil.copy2(source, target)
