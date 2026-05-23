"""Run local packaging/deployment readiness checks for the Z88 wrapper."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import run_packaging_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--require-packager", action="store_true", help="Fail if PyInstaller is missing")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    result = run_packaging_preflight(
        install_root=args.install_root,
        require_packager=args.require_packager,
    )
    payload = result.to_dict()
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["output"] = str(output)
    print(json.dumps(payload, indent=2))
    return 0 if result.status in {"ok", "ok_with_warnings"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
