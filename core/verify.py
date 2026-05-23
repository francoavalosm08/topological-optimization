"""Production export and stress verification helpers for Phase 6."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import trimesh

from .stress import StressSummary, analyze_design_stress


@dataclass(frozen=True)
class MeshQuality:
    path: str
    vertices: int
    faces: int
    watertight: bool
    components: int
    euler_number: int | None
    area: float
    volume: float | None
    degenerate_faces: int


@dataclass(frozen=True)
class VerificationReport:
    mesh: MeshQuality
    stress: StressSummary
    compliance: float
    stress_limit: float
    safety_factor: float
    allowable_stress: float
    passes_stress: bool
    notes: list[str]


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    mesh = trimesh.load(Path(path), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Expected mesh at {path}, got {type(mesh).__name__}")
    return mesh


def mesh_quality_report(path: str | Path) -> MeshQuality:
    mesh = load_mesh(path)
    area_faces = np.asarray(mesh.area_faces, dtype=np.float64)
    degenerate = int(np.sum(area_faces <= 1e-12))
    components = len(mesh.split(only_watertight=False))
    volume = float(mesh.volume) if mesh.is_watertight else None
    return MeshQuality(
        path=str(Path(path)),
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        watertight=bool(mesh.is_watertight),
        components=int(components),
        euler_number=int(mesh.euler_number) if mesh.euler_number is not None else None,
        area=float(mesh.area),
        volume=volume,
        degenerate_faces=degenerate,
    )


def verify_density_design(
    problem,
    density: np.ndarray,
    mesh_path: str | Path,
    *,
    penal: float = 3.0,
    E0: float = 1.0,
    Emin: float = 1e-9,
    nu: float = 0.3,
    stress_limit: float = 2.0,
    safety_factor: float = 1.0,
) -> VerificationReport:
    """Check exported mesh quality and stress in the solver density model.

    This is the Phase 6 local verification foundation. A later CalculiX/gmsh
    hook can replace the density-model stress check with an independent mesh FE
    solve while preserving this report contract.
    """
    if safety_factor <= 0.0:
        raise ValueError("safety_factor must be positive")
    masks = problem.region_masks
    analysis = analyze_design_stress(
        problem,
        density,
        penal=penal,
        E0=E0,
        Emin=Emin,
        nu=nu,
        stress_limit=stress_limit,
        mask=None if masks is None else ~masks.void,
    )
    mesh = mesh_quality_report(mesh_path)
    allowable = stress_limit / safety_factor
    notes: list[str] = []
    if not mesh.watertight:
        notes.append("mesh is not watertight")
    if mesh.degenerate_faces:
        notes.append(f"mesh has {mesh.degenerate_faces} degenerate faces")
    if mesh.components > 1:
        notes.append(f"mesh has {mesh.components} disconnected components")
    passes_stress = bool(analysis.summary.peak <= allowable)
    if not passes_stress:
        notes.append(
            f"peak stress {analysis.summary.peak:.6g} exceeds allowable {allowable:.6g}"
        )
    return VerificationReport(
        mesh=mesh,
        stress=analysis.summary,
        compliance=analysis.compliance,
        stress_limit=float(stress_limit),
        safety_factor=float(safety_factor),
        allowable_stress=float(allowable),
        passes_stress=passes_stress,
        notes=notes,
    )


def write_verification_report(report: VerificationReport, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
