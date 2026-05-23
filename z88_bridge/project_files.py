"""Small parsers for native Z88Arion project text files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


_QUOTED_RE = re.compile(r'"([^"]*)"')


@dataclass(frozen=True)
class ActiveSet:
    kind: str
    role: str
    label: str | None
    fields: tuple[str, ...]
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "role": self.role,
            "label": self.label,
            "fields": list(self.fields),
            "raw": self.raw,
        }


def parse_z88control(path: str | Path) -> dict[str, dict[str, Any]]:
    """Parse block/key/value data from `z88control.txt`.

    The file is plain text with `BLOCK START` / `BLOCK END` markers. Values are
    returned as ints or floats when possible; otherwise they remain strings.
    """
    blocks: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for raw_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("*") or line in {"DYNAMIC START", "DYNAMIC END"}:
            continue
        parts = line.split()
        if len(parts) == 2 and parts[1] == "START":
            current = parts[0]
            blocks.setdefault(current, {})
            continue
        if len(parts) == 2 and parts[1] == "END":
            current = None
            continue
        if current is None or len(parts) < 2:
            continue
        key = parts[0]
        value = " ".join(parts[1:])
        blocks[current][key] = _parse_scalar(value)
    return blocks


def parse_z88setsactive(path: str | Path) -> list[ActiveSet]:
    """Parse active set descriptors from `z88setsactive.txt`.

    Large membership lists stay in `z88sets.txt`; this parser only extracts the
    compact active set metadata and display names.
    """
    sets: list[ActiveSet] = []
    for raw_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        label_match = _QUOTED_RE.search(line)
        label = label_match.group(1) if label_match else None
        unquoted = _QUOTED_RE.sub("", line).strip()
        parts = unquoted[1:].split()
        if len(parts) < 2:
            continue
        sets.append(
            ActiveSet(
                kind=parts[0],
                role=parts[1],
                label=label,
                fields=tuple(parts[2:]),
                raw=line,
            )
        )
    return sets


def summarize_project_files(project_dir: str | Path) -> dict[str, Any]:
    """Return a lightweight machine-readable inventory for a Z88 project dir."""
    project_dir = Path(project_dir)
    files = {path.name: path for path in project_dir.iterdir() if path.is_file()}
    warnings: list[str] = []
    summary: dict[str, Any] = {
        "project_dir": str(project_dir),
        "files": {
            name: {"path": str(path), "bytes": path.stat().st_size}
            for name, path in sorted(files.items())
        },
        "previews": {
            name: preview_project_file(path)
            for name, path in sorted(files.items())
        },
        "warnings": warnings,
    }
    control = files.get("z88control.txt")
    if control is not None:
        try:
            summary["control"] = parse_z88control(control)
        except OSError as exc:
            warnings.append(f"could not parse z88control.txt: {exc}")
    active_sets = files.get("z88setsactive.txt")
    if active_sets is not None:
        try:
            summary["active_sets"] = [item.to_dict() for item in parse_z88setsactive(active_sets)]
        except OSError as exc:
            warnings.append(f"could not parse z88setsactive.txt: {exc}")
    structure = files.get("z88structure.txt")
    if structure is not None:
        try:
            summary["structure"] = parse_z88structure_header(structure)
        except OSError as exc:
            warnings.append(f"could not parse z88structure.txt: {exc}")
    return summary


def preview_project_file(path: str | Path, *, max_first_line_chars: int = 240) -> dict[str, Any]:
    """Return a bounded, binary-safe preview for a project file."""
    path = Path(path)
    raw = path.read_bytes()
    binary_like = b"\x00" in raw[:4096]
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    return {
        "bytes": path.stat().st_size,
        "line_count": len(lines),
        "binary_like": binary_like,
        "empty": len(raw) == 0,
        "first_line": first_line[:max_first_line_chars],
        "first_line_truncated": len(first_line) > max_first_line_chars,
    }


def parse_z88structure_header(path: str | Path) -> dict[str, Any]:
    """Parse the first numeric header line from `z88structure.txt`."""
    for raw_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        values = [_parse_scalar(part) for part in line.split()]
        return {
            "raw": line,
            "fields": values,
            "field_count": len(values),
        }
    return {"raw": "", "fields": [], "field_count": 0}


def _parse_scalar(raw: str) -> Any:
    try:
        value = int(raw)
    except ValueError:
        pass
    else:
        return value

    try:
        value = float(raw)
    except ValueError:
        return raw
    return value
