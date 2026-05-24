"""Probe TetGen conversion from STL/OFF into Z88 structure output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import trimesh

from z88_bridge import discover_installation, parse_z88structure_header


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_mesh", help="Input STL/OFF mesh")
    parser.add_argument("--output-dir", default="z88_assets/outputs/tetgen_probe/latest")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--args", default="-pl", help="TetGen args. Default emits z88structure.txt.")
    parser.add_argument(
        "--probe-direct-stl",
        action="store_true",
        help="Also run TetGen directly against a copied STL before the OFF conversion probe.",
    )
    args = parser.parse_args()

    input_mesh = Path(args.input_mesh)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    mesh = trimesh.load(input_mesh, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    off_path = output_dir / f"{input_mesh.stem}.off"
    mesh.export(off_path)

    installation = discover_installation(args.install_root)
    tetgen = installation.bin_dir / "tetgen.exe"
    direct_stl_result = None
    if args.probe_direct_stl and input_mesh.suffix.lower() == ".stl":
        copied_stl = output_dir / input_mesh.name
        shutil.copy2(input_mesh, copied_stl)
        direct_stl_result = _run_tetgen_probe(
            tetgen=tetgen,
            cwd=output_dir,
            command_args=[*args.args.split(), copied_stl.name],
            prefix="direct_stl",
        )

    command = [str(tetgen), *args.args.split(), off_path.name]
    completed = _run_tetgen_probe(
        tetgen=tetgen,
        cwd=output_dir,
        command_args=[*args.args.split(), off_path.name],
        prefix="off",
    )

    structure = output_dir / "z88structure.txt"
    header = parse_z88structure_header(structure) if structure.exists() else None
    first_node_id = _first_node_id(structure) if structure.exists() else None
    payload = {
        "status": "completed" if completed["returncode"] == 0 and structure.exists() else "failed",
        "input_mesh": str(input_mesh.resolve()),
        "output_dir": str(output_dir.resolve()),
        "command": command,
        "returncode": completed["returncode"],
        "z88structure": str(structure.resolve()) if structure.exists() else None,
        "z88structure_header": header,
        "first_node_id": first_node_id,
        "node_indexing": "zero_based" if first_node_id == 0 else "one_based_or_unknown",
        "stdout_file": completed["stdout_file"],
        "stderr_file": completed["stderr_file"],
        "direct_stl_probe": direct_stl_result,
    }
    result_path = output_dir / "tetgen_probe.json"
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "completed" else 2


def _run_tetgen_probe(
    *,
    tetgen: Path,
    cwd: Path,
    command_args: list[str],
    prefix: str,
) -> dict[str, object]:
    command = [str(tetgen), *command_args]
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    stdout_file = cwd / f"tetgen.{prefix}.stdout.txt"
    stderr_file = cwd / f"tetgen.{prefix}.stderr.txt"
    stdout_file.write_text(completed.stdout, encoding="utf-8", errors="replace")
    stderr_file.write_text(completed.stderr, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_file": str(stdout_file.resolve()),
        "stderr_file": str(stderr_file.resolve()),
    }


def _first_node_id(path: Path) -> int | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[1:]:
        parts = line.split()
        if parts:
            try:
                return int(parts[0])
            except ValueError:
                return None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
