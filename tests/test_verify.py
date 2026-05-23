"""Phase 6 production export verification checks."""
from __future__ import annotations

import json

import numpy as np
import trimesh

from core.problem import cantilever_2d
from core.verify import mesh_quality_report, verify_density_design, write_verification_report


def test_mesh_quality_report_for_watertight_box(tmp_path):
    path = tmp_path / "box.stl"
    trimesh.creation.box(extents=(1, 2, 3)).export(path)

    report = mesh_quality_report(path)

    assert report.watertight
    assert report.vertices > 0
    assert report.faces > 0
    assert report.components == 1
    assert report.degenerate_faces == 0
    assert report.volume is not None


def test_verify_density_design_writes_json_report(tmp_path):
    prob = cantilever_2d(nelx=4, nely=2)
    density = np.ones(prob.n_elements, dtype=np.float64)
    mesh_path = tmp_path / "box.stl"
    trimesh.creation.box(extents=(4, 2, 1)).export(mesh_path)

    report = verify_density_design(
        prob,
        density,
        mesh_path,
        penal=3.0,
        stress_limit=100.0,
        safety_factor=2.0,
    )
    out = tmp_path / "report.json"
    write_verification_report(report, out)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["passes_stress"] is True
    assert data["mesh"]["watertight"] is True
    assert data["stress"]["peak"] > 0.0
