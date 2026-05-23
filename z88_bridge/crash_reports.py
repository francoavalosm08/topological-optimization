"""Local crash-report helpers for Z88 wrapper commands and UI integrations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import traceback
from typing import Any


@dataclass(frozen=True)
class CrashReport:
    report_dir: str
    traceback_file: str
    context_file: str
    copied_files: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_crash_report(
    exc: BaseException,
    *,
    root: str | Path = "crash_reports",
    context: dict[str, Any] | None = None,
    files: tuple[str | Path, ...] = (),
) -> CrashReport:
    """Write a purely local crash report with traceback, context, and selected files."""
    root = Path(root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = _unique_report_dir(root / timestamp)
    report_dir.mkdir(parents=True, exist_ok=False)

    traceback_file = report_dir / "traceback.txt"
    traceback_file.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")

    copied_files: list[str] = []
    files_dir = report_dir / "files"
    for source in files:
        source_path = Path(source)
        if not source_path.is_file():
            continue
        files_dir.mkdir(exist_ok=True)
        destination = _unique_copy_path(files_dir / source_path.name)
        shutil.copy2(source_path, destination)
        copied_files.append(str(destination))

    context_payload = {
        "schema_version": 1,
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "context": context or {},
        "copied_files": copied_files,
    }
    context_file = report_dir / "context.json"
    context_file.write_text(json.dumps(context_payload, indent=2, sort_keys=True), encoding="utf-8")

    report = CrashReport(
        report_dir=str(report_dir),
        traceback_file=str(traceback_file),
        context_file=str(context_file),
        copied_files=tuple(copied_files),
    )
    (report_dir / "crash_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _unique_report_dir(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.name}_{index:02d}")
        if not candidate.exists():
            return candidate
        index += 1


def _unique_copy_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1
