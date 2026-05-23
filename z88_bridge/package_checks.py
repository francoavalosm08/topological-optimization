"""Packaging and deployment preflight checks for the local Z88 wrapper."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
import platform
from pathlib import Path
import shutil
import sys
from typing import Any

from .adapter import Z88BridgeError, discover_installation


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PackagingPreflight:
    status: str
    checks: tuple[PreflightCheck, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }


def run_packaging_preflight(
    *,
    install_root: str | Path | None = None,
    require_packager: bool = False,
) -> PackagingPreflight:
    checks = [
        _check_python_version(),
        _check_platform(),
        _check_import("fastapi"),
        _check_import("uvicorn"),
        _check_import("trimesh"),
        _check_import("numpy"),
        _check_packaging_file("packaging_entrypoint", "packaging/z88_topopt_app.py", source_only=True),
        _check_packaging_file("pyinstaller_spec", "packaging/Z88TopologyOptimizer.spec", source_only=True),
        _check_packaging_file("build_script", "scripts/z88_build_package.ps1", source_only=True),
        _check_packaging_file("package_smoke_script", "scripts/z88_package_smoke.py", source_only=True),
        _check_packaging_file("web_ui", "web/index.html"),
        _check_packaging_file("material_presets", "presets/materials"),
        _check_packaging_file("safety_presets", "presets/safety_factors.json"),
        _check_z88_install(install_root),
        _check_pyinstaller(require_packager=require_packager),
    ]
    if any(check.status == "failed" for check in checks):
        status = "needs_attention"
    elif any(check.status == "warning" for check in checks):
        status = "ok_with_warnings"
    else:
        status = "ok"
    return PackagingPreflight(status=status, checks=tuple(checks))


def _check_python_version() -> PreflightCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    status = "ok" if sys.version_info >= (3, 11) else "failed"
    return PreflightCheck("python", status, version)


def _check_platform() -> PreflightCheck:
    system = platform.system()
    status = "ok" if system == "Windows" else "warning"
    detail = f"{system} {platform.release()}"
    return PreflightCheck("platform", status, detail)


def _check_import(module_name: str) -> PreflightCheck:
    spec = importlib.util.find_spec(module_name)
    status = "ok" if spec is not None else "failed"
    detail = "available" if spec is not None else "missing"
    return PreflightCheck(f"python_module:{module_name}", status, detail)


def _check_z88_install(install_root: str | Path | None) -> PreflightCheck:
    try:
        installation = discover_installation(install_root)
    except Z88BridgeError as exc:
        return PreflightCheck("z88_installation", "failed", str(exc))
    missing = [
        name
        for name, value in {
            "Z88OC.exe": installation.oc_exe,
            "z88r_opt.exe/z88rofl.exe": installation.solver_exe,
        }.items()
        if value is None
    ]
    if missing:
        return PreflightCheck("z88_installation", "warning", f"{installation.root}; missing {', '.join(missing)}")
    return PreflightCheck("z88_installation", "ok", str(installation.root))


def _check_packaging_file(name: str, relative_path: str, *, source_only: bool = False) -> PreflightCheck:
    path = _repo_root() / relative_path
    if path.exists():
        detail = "directory" if path.is_dir() else "file"
        return PreflightCheck(name, "ok", f"{detail}: {path}")
    if source_only and _is_frozen():
        return PreflightCheck(name, "warning", f"source-only file not bundled: {relative_path}")
    return PreflightCheck(name, "failed", f"missing: {path}")


def _check_pyinstaller(*, require_packager: bool) -> PreflightCheck:
    executable = shutil.which("pyinstaller")
    if executable:
        return PreflightCheck("pyinstaller", "ok", executable)
    status = "failed" if require_packager else "warning"
    return PreflightCheck("pyinstaller", status, "missing; install only when building a distributable")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
