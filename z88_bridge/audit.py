"""Fixture audit helpers for native Z88Arion project folders."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .assets import build_project_manifest, write_manifest


KNOWN_PROJECT_FILES = {
    "z88control.txt": "Aurora solver/topology optimization settings",
    "z88setsactive.txt": "Aurora active set descriptors",
    "z88sets.txt": "Aurora expanded set membership",
    "z88structure.txt": "Aurora mesh structure: header, nodes, elements",
    "z88marks.txt": "Observed in TOSS/undercut examples; likely manufacturing marks",
    "project.z88": "Aurora project descriptor observed in some examples",
    "z88.inp": "Imported FE/project input observed in some examples",
}


def audit_fixture(project_dir: str | Path, *, source: str | None = None) -> dict[str, Any]:
    project_dir = Path(project_dir)
    manifest = build_project_manifest(project_dir, source=source)
    files = manifest["files"]
    known = sorted(name for name in files if Path(name).name in KNOWN_PROJECT_FILES)
    unknown = sorted(name for name in files if Path(name).name not in KNOWN_PROJECT_FILES)
    missing_core = [
        name
        for name in ("z88sets.txt", "z88setsactive.txt", "z88structure.txt")
        if name not in files
    ]
    return {
        "fixture": project_dir.name,
        "project_dir": str(project_dir),
        "source": source,
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "known_files": {
            name: {
                "role": KNOWN_PROJECT_FILES[Path(name).name],
                "record": files[name],
                "preview": manifest["summary"]["previews"].get(name),
            }
            for name in known
        },
        "unknown_files": {
            name: {
                "record": files[name],
                "preview": manifest["summary"]["previews"].get(name),
            }
            for name in unknown
        },
        "missing_core_files": missing_core,
        "parsed": {
            key: value
            for key, value in manifest["summary"].items()
            if key in {"control", "active_sets", "structure", "warnings"}
        },
        "manifest": manifest,
    }


def render_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        f"# Z88 Fixture Audit: {audit['fixture']}",
        "",
        f"- Project dir: `{audit['project_dir']}`",
        f"- Source: `{audit.get('source') or ''}`",
        f"- File count: `{audit['file_count']}`",
        f"- Total bytes: `{audit['total_bytes']}`",
        "",
        "## Missing Core Files",
        "",
    ]
    if audit["missing_core_files"]:
        lines.extend(f"- `{name}`" for name in audit["missing_core_files"])
    else:
        lines.append("- None")

    lines.extend(["", "## Known Files", ""])
    for name, item in audit["known_files"].items():
        preview = item.get("preview") or {}
        lines.extend(
            [
                f"### `{name}`",
                "",
                f"- Role: {item['role']}",
                f"- Bytes: `{item['record']['bytes']}`",
                f"- SHA-256: `{item['record']['sha256']}`",
                f"- Lines: `{preview.get('line_count', 0)}`",
                f"- Binary-like: `{preview.get('binary_like', False)}`",
                f"- First line: `{preview.get('first_line', '')}`",
                "",
            ]
        )

    lines.extend(["## Unknown Files", ""])
    if audit["unknown_files"]:
        for name, item in audit["unknown_files"].items():
            preview = item.get("preview") or {}
            lines.extend(
                [
                    f"### `{name}`",
                    "",
                    f"- Bytes: `{item['record']['bytes']}`",
                    f"- SHA-256: `{item['record']['sha256']}`",
                    f"- Lines: `{preview.get('line_count', 0)}`",
                    f"- Binary-like: `{preview.get('binary_like', False)}`",
                    f"- First line: `{preview.get('first_line', '')}`",
                    "",
                ]
            )
    else:
        lines.append("- None")

    parsed = audit.get("parsed", {})
    control = parsed.get("control", {})
    active_sets = parsed.get("active_sets", [])
    structure = parsed.get("structure", {})
    lines.extend(
        [
            "",
            "## Parsed Highlights",
            "",
            f"- Control blocks: `{', '.join(sorted(control)) if control else ''}`",
            f"- Active sets: `{len(active_sets)}`",
            f"- Structure header: `{structure.get('raw', '')}`",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = parsed.get("warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_audit_outputs(audit: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> None:
    write_manifest(audit, json_path)
    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_audit_markdown(audit), encoding="utf-8")


def audit_to_json(audit: dict[str, Any]) -> str:
    return json.dumps(audit, indent=2)
