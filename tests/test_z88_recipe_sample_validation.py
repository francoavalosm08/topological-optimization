from __future__ import annotations

from pathlib import Path

from scripts.z88_validate_recipe_samples import validate_recipe_samples


def _fake_install(root: Path) -> Path:
    bin_dir = root / "win" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Z88Arion.exe").write_text("", encoding="utf-8")
    return root


def test_validate_recipe_samples_writes_all_native_projects(tmp_path: Path) -> None:
    output = tmp_path / "validation.json"

    result = validate_recipe_samples(
        samples_dir=tmp_path / "samples",
        projects_dir=tmp_path / "projects",
        output=output,
        install_root=str(_fake_install(tmp_path / "Z88ArionV3")),
        max_elements=20_000,
        write_projects=True,
    )

    assert result["status"] == "ok"
    assert result["sample_count"] == 5
    assert result["failed_count"] == 0
    assert output.is_file()
    assert all(item["native_project"]["solid_component_count"] == 1 for item in result["results"])
    assert all(Path(item["native_project"]["summary_json"]).is_file() for item in result["results"])
