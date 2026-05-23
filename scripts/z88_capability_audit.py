"""Report the local Z88Arion/Z88 installation capabilities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import Z88NotInstalledError, discover_installation, summarize_project_files


IMPORTANT_BINARIES = (
    "Z88Arion.exe",
    "Z88OC.exe",
    "z88rTOSS.exe",
    "z88r_sko.exe",
    "z88r_opt.exe",
    "z88rofl.exe",
    "tetgen.exe",
    "netgen.exe",
)


def build_audit(install_root: str | None) -> dict[str, object]:
    try:
        installation = discover_installation(install_root)
    except Z88NotInstalledError as exc:
        return {
            "installed": False,
            "error": str(exc),
            "searched_install_root": install_root,
        }

    root = installation.root
    bin_dir = installation.bin_dir
    doc_dir = root / "docu"
    examples_dir = doc_dir / "examples"
    docs = sorted(str(path) for path in doc_dir.rglob("*.pdf")) if doc_dir.exists() else []
    example_files = sorted(str(path) for path in examples_dir.rglob("*") if path.is_file())
    project_summaries = []
    project_root = examples_dir / "project"
    if project_root.exists():
        for project_dir in sorted(path for path in project_root.iterdir() if path.is_dir()):
            project_summaries.append(summarize_project_files(project_dir))

    algorithms = {}
    for item in project_summaries:
        control = item.get("control", {})
        tosolver = control.get("TOSOLVER", {}) if isinstance(control, dict) else {}
        algorithm = tosolver.get("OPTALGORITHM") if isinstance(tosolver, dict) else None
        if algorithm is not None:
            algorithms.setdefault(str(algorithm), []).append(Path(item["project_dir"]).name)

    return {
        "installed": True,
        "installation": installation.to_dict(),
        "important_binaries": {
            name: str(bin_dir / name) if (bin_dir / name).exists() else None
            for name in IMPORTANT_BINARIES
        },
        "docs_dir": str(doc_dir) if doc_dir.exists() else None,
        "example_file_count": len(example_files),
        "sample_docs": docs[:20],
        "sample_examples": example_files[:50],
        "observed_optalgorithm_projects": algorithms,
        "sample_project_summaries": project_summaries[:5],
        "headless_status": (
            "unknown: project/result file contract must be mapped from a manual "
            "Z88Arion fixture before enabling automated solves"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--json", action="store_true", help="Print compact JSON")
    args = parser.parse_args()

    audit = build_audit(args.install_root)
    print(json.dumps(audit, indent=None if args.json else 2))
    return 0 if audit.get("installed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
