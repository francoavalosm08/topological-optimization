"""Adapter for wrapping an installed Z88Arion/Z88 toolchain."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess

from core.verify import mesh_quality_report

from .config import OptimizationResult, Z88RunConfig, write_config
from .project_files import summarize_project_files


class Z88BridgeError(RuntimeError):
    """Base class for Z88 bridge failures."""


class Z88NotInstalledError(Z88BridgeError):
    """Raised when the expected Z88Arion binaries cannot be found."""


class Z88HeadlessUnavailableError(Z88BridgeError):
    """Raised when a requested headless solve is not supported yet."""


@dataclass(frozen=True)
class Z88Installation:
    root: Path
    bin_dir: Path
    arion_exe: Path
    oc_exe: Path | None
    optopus_exe: Path | None
    toss_exe: Path | None
    sko_exe: Path | None
    solver_exe: Path | None
    ag2oi_exe: Path | None

    def to_dict(self) -> dict[str, str | None]:
        data = asdict(self)
        return {key: str(value) if value is not None else None for key, value in data.items()}


class Z88Adapter:
    """File-oriented bridge to Z88Arion.

    The current implementation prepares reproducible project folders and can
    collect manually exported Z88Arion results. Headless execution is explicitly
    guarded until the exact Z88 project/CLI contract is mapped from fixtures.
    """

    def __init__(
        self,
        *,
        install_root: str | Path | None = None,
        runs_root: str | Path = "runs/z88",
        allow_headless: bool = False,
    ) -> None:
        self.installation = discover_installation(install_root)
        self.runs_root = Path(runs_root)
        self.allow_headless = allow_headless

    def prepare_project(self, config: Z88RunConfig) -> Path:
        config.validate()
        run_dir = self.runs_root / f"{config.project_name}_{config.run_id()}"
        z88_project = run_dir / "z88_project"
        raw_results = run_dir / "z88_raw_results"
        run_dir.mkdir(parents=True, exist_ok=True)
        z88_project.mkdir(parents=True, exist_ok=True)
        raw_results.mkdir(parents=True, exist_ok=True)

        input_dst = run_dir / "input.stl"
        shutil.copy2(config.input_stl, input_dst)
        write_config(config, run_dir / "config.json")
        _write_installation_manifest(self.installation, run_dir / "z88_installation.json")
        _write_handoff(config, self.installation, run_dir / "Z88_HANDOFF.md")

        placeholder = {
            "status": "prepared",
            "message": "Open this run folder in Z88Arion or import input.stl manually, then export optimized.stl back here.",
            "z88_project_dir": str(z88_project),
            "raw_result_dir": str(raw_results),
        }
        (run_dir / "bridge_status.json").write_text(
            json.dumps(placeholder, indent=2),
            encoding="utf-8",
        )
        return run_dir

    def stage_native_project(
        self,
        source_project_dir: str | Path,
        *,
        project_name: str | None = None,
    ) -> Path:
        """Archive an existing native Z88Arion project into a bridge run folder."""
        source_project_dir = Path(source_project_dir)
        if not source_project_dir.is_dir():
            raise FileNotFoundError(f"Z88 project directory not found: {source_project_dir}")
        required = ("z88sets.txt", "z88setsactive.txt", "z88structure.txt")
        missing = [name for name in required if not (source_project_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Z88 project is missing required files: {', '.join(missing)}"
            )

        name = project_name or source_project_dir.name
        fingerprint = _project_fingerprint(source_project_dir)
        run_dir = self.runs_root / f"{name}_{fingerprint}"
        z88_project = run_dir / "z88_project"
        raw_results = run_dir / "z88_raw_results"
        run_dir.mkdir(parents=True, exist_ok=True)
        raw_results.mkdir(parents=True, exist_ok=True)
        if z88_project.exists():
            shutil.rmtree(z88_project)
        shutil.copytree(source_project_dir, z88_project)

        summary = summarize_project_files(z88_project)
        summary_path = run_dir / "z88_project_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _write_installation_manifest(self.installation, run_dir / "z88_installation.json")
        _write_native_handoff(self.installation, run_dir / "Z88_NATIVE_HANDOFF.md")
        status = {
            "status": "native_project_staged",
            "source_project_dir": str(source_project_dir),
            "z88_project_dir": str(z88_project),
            "raw_result_dir": str(raw_results),
            "summary_json": str(summary_path),
        }
        (run_dir / "bridge_status.json").write_text(
            json.dumps(status, indent=2),
            encoding="utf-8",
        )
        return run_dir

    def run(self, project_dir: str | Path) -> Path:
        project_dir = Path(project_dir)
        if not self.allow_headless:
            raise Z88HeadlessUnavailableError(
                "Headless Z88Arion execution is not enabled yet. "
                "Use prepare_project(), run/export in Z88Arion, then collect_results()."
            )
        # Reserved for the fixture-backed headless contract once Z88 project files
        # are mapped. The GUI launcher is useful for guided handoff only.
        subprocess.Popen([str(self.installation.arion_exe)], cwd=str(project_dir))
        return project_dir / "z88_raw_results"

    def collect_results(self, project_dir: str | Path) -> OptimizationResult:
        project_dir = Path(project_dir)
        config_path = project_dir / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing Z88 bridge config: {config_path}")
        config = Z88RunConfig.from_json_file(config_path)

        optimized = project_dir / "optimized.stl"
        mesh_json = project_dir / "mesh_quality.json"
        messages: list[str] = []
        status = "needs_manual_export"
        optimized_str: str | None = None
        mesh_str: str | None = None

        if optimized.exists():
            quality = mesh_quality_report(optimized)
            mesh_json.write_text(json.dumps(asdict(quality), indent=2), encoding="utf-8")
            optimized_str = str(optimized)
            mesh_str = str(mesh_json)
            status = "collected"
            if not quality.watertight:
                messages.append("optimized STL is not watertight")
            if quality.components != 1:
                messages.append(f"optimized STL has {quality.components} components")
            if quality.degenerate_faces:
                messages.append(f"optimized STL has {quality.degenerate_faces} degenerate faces")
        else:
            messages.append("optimized.stl was not found; export it from Z88Arion into the run folder")

        result = OptimizationResult(
            run_id=config.run_id(),
            project_dir=str(project_dir),
            status=status,
            optimized_stl=optimized_str,
            mesh_quality_json=mesh_str,
            raw_result_dir=str(project_dir / "z88_raw_results"),
            messages=tuple(messages),
        )
        result.write_json(project_dir / "optimization_result.json")
        return result

    def export_final_stl(self, project_dir: str | Path) -> Path:
        optimized = Path(project_dir) / "optimized.stl"
        if not optimized.exists():
            raise FileNotFoundError(
                f"Expected exported Z88Arion STL at {optimized}. "
                "Export the smoothed result from Z88Arion using this filename."
            )
        return optimized


def discover_installation(install_root: str | Path | None = None) -> Z88Installation:
    if install_root is not None:
        candidates = [Path(install_root)]
    else:
        env_root = os.environ.get("Z88ARION_ROOT")
        candidates = [
            *([Path(env_root)] if env_root else []),
            Path("C:/Z88ArionV3"),
            Path("C:/Program Files/Z88ArionV3"),
            Path("C:/Program Files (x86)/Z88ArionV3"),
        ]

    for root in candidates:
        bin_dir = root / "win" / "bin"
        arion = bin_dir / "Z88Arion.exe"
        if arion.exists():
            return Z88Installation(
                root=root,
                bin_dir=bin_dir,
                arion_exe=arion,
                oc_exe=_existing(bin_dir / "Z88OC.exe"),
                optopus_exe=_existing(bin_dir / "z88optopus.exe"),
                toss_exe=_existing(bin_dir / "z88rTOSS.exe"),
                sko_exe=_existing(bin_dir / "z88r_sko.exe"),
                solver_exe=_existing(bin_dir / "z88r_opt.exe") or _existing(bin_dir / "z88rofl.exe"),
                ag2oi_exe=_existing(bin_dir / "z88ag2oi.exe"),
            )
    raise Z88NotInstalledError(
        "Z88Arion was not found. Install it or pass install_root=... "
        "Expected layout: <root>/win/bin/Z88Arion.exe"
    )


def _existing(path: Path) -> Path | None:
    return path if path.exists() else None


def _project_fingerprint(project_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(item for item in project_dir.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(project_dir)).replace("\\", "/").encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _write_installation_manifest(installation: Z88Installation, path: Path) -> None:
    path.write_text(json.dumps(installation.to_dict(), indent=2), encoding="utf-8")


def _write_handoff(config: Z88RunConfig, installation: Z88Installation, path: Path) -> None:
    lines = [
        "# Z88Arion Manual Handoff",
        "",
        f"Run id: `{config.run_id()}`",
        f"Project: `{config.project_name}`",
        f"Z88Arion: `{installation.arion_exe}`",
        "",
        "## Steps",
        "",
        "1. Open Z88Arion.",
        "2. Import `input.stl` from this run folder.",
        "3. Apply material, supports, loads, passive regions, and optimizer settings from `config.json`.",
        "4. Run the Z88Arion topology optimization.",
        "5. Export the final smoothed STL as `optimized.stl` into this run folder.",
        "6. Put any raw Z88 output files under `z88_raw_results/`.",
        "7. Run `python scripts/z88_collect_results.py <run-folder>`.",
        "",
        "## Key Settings",
        "",
        f"- Units: `{config.units}`",
        f"- Optimizer: `{config.optimizer.method}`",
        f"- Volume fraction: `{config.optimizer.volume_fraction}`",
        f"- Safety factor: `{config.safety_factor}`",
        f"- Material: `{config.material.name}`",
        f"- Young's modulus: `{config.material.young_modulus}`",
        f"- Poisson ratio: `{config.material.poisson_ratio}`",
        f"- Stress limit: `{config.material.stress_limit}`",
        "",
        "This bridge intentionally keeps Z88Arion as the authoritative FE/TO tool "
        "until a fixture-backed headless project contract is mapped.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_native_handoff(installation: Z88Installation, path: Path) -> None:
    lines = [
        "# Z88Arion Native Project Handoff",
        "",
        f"Z88Arion: `{installation.arion_exe}`",
        "",
        "## Steps",
        "",
        "1. Open Z88Arion.",
        "2. Open/import the native project files from `z88_project/`.",
        "3. Run or inspect the project in Z88Arion.",
        "4. Export the final smoothed STL as `optimized.stl` into this run folder.",
        "5. Put any raw Z88 output files under `z88_raw_results/`.",
        "6. Run `python scripts/z88_collect_results.py <run-folder>` after export.",
        "",
        "The parsed native project summary is in `z88_project_summary.json`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
