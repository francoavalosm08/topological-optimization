"""Collect a manually exported Z88Arion result into the bridge report format."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import Z88Adapter


def copy_optimized_stl(source: Path, project_dir: Path) -> None:
    destination = project_dir / "optimized.stl"
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def copy_raw_results(source: Path, project_dir: Path) -> None:
    destination = project_dir / "z88_raw_results"
    destination.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copy2(source, destination / source.name)
        return
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Run folder created by z88_prepare_project.py")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--optimized-stl", help="Path to STL exported from Z88Arion")
    parser.add_argument("--raw-results", help="File or directory of raw Z88 result files to archive")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if args.optimized_stl:
        copy_optimized_stl(Path(args.optimized_stl).resolve(), project_dir)
    if args.raw_results:
        copy_raw_results(Path(args.raw_results).resolve(), project_dir)

    adapter = Z88Adapter(install_root=args.install_root, runs_root=project_dir.parent)
    result = adapter.collect_results(project_dir)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "collected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
