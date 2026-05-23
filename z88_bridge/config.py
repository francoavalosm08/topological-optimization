"""Serializable contracts for Z88Arion bridge runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any


VALID_UNITS = {"mm", "cm", "m", "in"}
VALID_OPTIMIZERS = {"oc", "sko", "toss"}


@dataclass(frozen=True)
class MaterialSpec:
    name: str = "Al-6061-T6"
    young_modulus: float = 68.9e9
    poisson_ratio: float = 0.33
    density: float = 2700.0
    stress_limit: float = 276e6


@dataclass(frozen=True)
class RegionSpec:
    name: str
    selector: dict[str, Any]
    role: str = "region"


@dataclass(frozen=True)
class SupportSpec:
    name: str
    region: RegionSpec
    constrained_dofs: tuple[str, ...] = ("x", "y", "z")


@dataclass(frozen=True)
class LoadCase:
    name: str
    region: RegionSpec
    force: tuple[float, float, float]
    weight: float = 1.0


@dataclass(frozen=True)
class OptimizerSettings:
    method: str = "oc"
    volume_fraction: float = 0.4
    max_iterations: int = 100
    convergence_tolerance: float = 1e-3


@dataclass(frozen=True)
class ExportSettings:
    iso_threshold: float = 0.5
    smoothing_iterations: int = 20
    min_component_volume_fraction: float = 0.05


@dataclass(frozen=True)
class Z88RunConfig:
    input_stl: str
    units: str
    project_name: str = "z88_topopt_run"
    voxel_pitch: float = 1.0
    material: MaterialSpec = field(default_factory=MaterialSpec)
    optimizer: OptimizerSettings = field(default_factory=OptimizerSettings)
    supports: tuple[SupportSpec, ...] = field(default_factory=tuple)
    loads: tuple[LoadCase, ...] = field(default_factory=tuple)
    passive_solid: tuple[RegionSpec, ...] = field(default_factory=tuple)
    passive_void: tuple[RegionSpec, ...] = field(default_factory=tuple)
    safety_factor: float = 1.5
    export: ExportSettings = field(default_factory=ExportSettings)
    notes: str = ""

    def validate(self, *, require_input_exists: bool = True) -> None:
        if self.units not in VALID_UNITS:
            raise ValueError(f"units must be one of {sorted(VALID_UNITS)}, got {self.units!r}")
        if self.voxel_pitch <= 0:
            raise ValueError("voxel_pitch must be positive")
        if self.material.young_modulus <= 0:
            raise ValueError("material.young_modulus must be positive")
        if not (0.0 < self.material.poisson_ratio < 0.5):
            raise ValueError("material.poisson_ratio must be in (0, 0.5)")
        if self.material.stress_limit <= 0:
            raise ValueError("material.stress_limit must be positive")
        if self.optimizer.method.lower() not in VALID_OPTIMIZERS:
            raise ValueError(
                f"optimizer.method must be one of {sorted(VALID_OPTIMIZERS)}, "
                f"got {self.optimizer.method!r}"
            )
        if not (0.0 < self.optimizer.volume_fraction <= 1.0):
            raise ValueError("optimizer.volume_fraction must be in (0, 1]")
        if self.safety_factor <= 0:
            raise ValueError("safety_factor must be positive")
        if require_input_exists and not Path(self.input_stl).exists():
            raise FileNotFoundError(f"input STL not found: {self.input_stl}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def run_id(self) -> str:
        payload = self.to_json().encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Z88RunConfig":
        return cls(
            input_stl=data["input_stl"],
            units=data["units"],
            project_name=data.get("project_name", "z88_topopt_run"),
            voxel_pitch=float(data.get("voxel_pitch", 1.0)),
            material=MaterialSpec(**data.get("material", {})),
            optimizer=OptimizerSettings(**data.get("optimizer", {})),
            supports=tuple(_support_from_dict(item) for item in data.get("supports", [])),
            loads=tuple(_load_from_dict(item) for item in data.get("loads", [])),
            passive_solid=tuple(_region_from_dict(item) for item in data.get("passive_solid", [])),
            passive_void=tuple(_region_from_dict(item) for item in data.get("passive_void", [])),
            safety_factor=float(data.get("safety_factor", 1.5)),
            export=ExportSettings(**data.get("export", {})),
            notes=data.get("notes", ""),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Z88RunConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class OptimizationResult:
    run_id: str
    project_dir: str
    status: str
    backend: str = "z88arion"
    optimized_stl: str | None = None
    mesh_quality_json: str | None = None
    verification_json: str | None = None
    raw_result_dir: str | None = None
    messages: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def write_config(config: Z88RunConfig, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(config.to_json(), encoding="utf-8")


def _region_from_dict(data: dict[str, Any]) -> RegionSpec:
    return RegionSpec(
        name=data["name"],
        selector=dict(data.get("selector", {})),
        role=data.get("role", "region"),
    )


def _support_from_dict(data: dict[str, Any]) -> SupportSpec:
    return SupportSpec(
        name=data["name"],
        region=_region_from_dict(data["region"]),
        constrained_dofs=tuple(data.get("constrained_dofs", ("x", "y", "z"))),
    )


def _load_from_dict(data: dict[str, Any]) -> LoadCase:
    return LoadCase(
        name=data["name"],
        region=_region_from_dict(data["region"]),
        force=tuple(float(v) for v in data["force"]),
        weight=float(data.get("weight", 1.0)),
    )
