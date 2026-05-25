from __future__ import annotations

import json
from pathlib import Path

from scripts.z88_validate_structural_samples import validate_structural_samples
from z88_bridge import generate_structural_sample_assets


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Z88Arion.exe").write_text("", encoding="utf-8")
    return root


def test_generate_structural_sample_assets_writes_common_structures(tmp_path: Path) -> None:
    result = generate_structural_sample_assets(tmp_path / "structures")

    catalog = json.loads(Path(result["catalog_json"]).read_text(encoding="utf-8"))
    names = {sample["name"] for sample in catalog["samples"]}
    assert result["sample_count"] == 5
    assert names == {
        "cantilever_beam",
        "l_bracket",
        "bridge_beam",
        "gusset_bracket",
        "plate_with_hole",
    }
    assert all(Path(sample["stl_path"]).is_file() for sample in catalog["samples"])
    assert {sample["recipe"] for sample in catalog["samples"]} == {"generic_bracket"}


def test_validate_structural_samples_writes_native_projects(tmp_path: Path) -> None:
    output = tmp_path / "structural_validation.json"

    result = validate_structural_samples(
        samples_dir=tmp_path / "samples",
        projects_dir=tmp_path / "projects",
        output=output,
        install_root=str(_fake_install(tmp_path / "Z88ArionV3")),
        max_elements=50_000,
        run_workflow=False,
    )

    assert result["status"] == "ok"
    assert result["sample_count"] == 5
    assert result["methods"] == ["oc"]
    assert result["failed_count"] == 0
    assert output.is_file()
    assert all(item["native_project"]["solid_component_count"] == 1 for item in result["results"])
    assert all(Path(item["native_project"]["summary_json"]).is_file() for item in result["results"])


def test_validate_structural_samples_can_prepare_oc_toss_sko_projects(tmp_path: Path) -> None:
    output = tmp_path / "structural_method_validation.json"

    result = validate_structural_samples(
        samples_dir=tmp_path / "samples",
        projects_dir=tmp_path / "projects",
        output=output,
        install_root=str(_fake_install(tmp_path / "Z88ArionV3")),
        max_elements=50_000,
        methods=("oc", "toss", "sko"),
        run_workflow=False,
    )

    assert result["status"] == "ok"
    assert result["sample_count"] == 15
    assert result["asset_count"] == 5
    assert result["method_count"] == 3
    assert result["failed_count"] == 0
    assert {item["optimizer_method"] for item in result["results"]} == {"oc", "toss", "sko"}
    assert all(Path(item["native_project"]["summary_json"]).is_file() for item in result["results"])
