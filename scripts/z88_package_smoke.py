"""Run package-oriented smoke checks without requiring a full installer build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import generate_sample_assets, run_packaging_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", help="Optional packaged executable to smoke-test")
    parser.add_argument("--allow-missing-z88", action="store_true")
    parser.add_argument("--samples-dir", default="runs/package_smoke/samples")
    args = parser.parse_args()

    samples = generate_sample_assets(args.samples_dir)
    preflight = run_packaging_preflight()
    exe_result = None
    if args.exe:
        exe_result = _run_exe_smoke(Path(args.exe), allow_missing_z88=args.allow_missing_z88)

    failed = [check for check in preflight.checks if check.status == "failed"]
    if args.allow_missing_z88:
        failed = [check for check in failed if check.name != "z88_installation"]

    payload = {
        "status": "ok" if not failed and (exe_result is None or exe_result["returncode"] == 0) else "failed",
        "samples": samples,
        "preflight": preflight.to_dict(),
        "exe_smoke": exe_result,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 2


def _run_exe_smoke(exe: Path, *, allow_missing_z88: bool) -> dict[str, object]:
    if not exe.is_file():
        return {"returncode": 2, "error": f"executable not found: {exe}"}
    args = [str(exe), "--smoke-test", "--no-browser"]
    if allow_missing_z88:
        args.append("--allow-missing-z88")
    completed = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


if __name__ == "__main__":
    raise SystemExit(main())
