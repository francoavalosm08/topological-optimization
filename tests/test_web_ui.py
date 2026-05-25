from __future__ import annotations

from pathlib import Path


def test_web_ui_uses_current_origin_for_local_api_calls() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert "const API_ORIGIN = window.location.origin" in html
    assert "const WS_URL =" in html
    assert "127.0.0.1:8000" not in html


def test_web_ui_exposes_region_box_helper() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert "Region Box Helper" in html
    assert "applyZ88BoxToPayload" in html
    assert "inspectZ88Stl" in html
    assert "loadZ88BoundsIntoBoxFields" in html
    assert "suggestZ88EndBoxes" in html
    assert "validateZ88PayloadOnly" in html
    assert "Visual Box Picker" in html
    assert "applyZ88VisualSlab" in html
    assert "z88BoxPreview" in html
    assert "generated OC/TOSS/SKO H8 only" in html
    assert "optimized.stl" in html
    assert "mesh_quality.json" in html


def test_web_ui_loads_z88_capabilities() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert "/z88/capabilities" in html
    assert "/z88/recipes/validate" in html
    assert "/z88/stl/inspect" in html
    assert "/z88/stl/suggest_end_boxes" in html
