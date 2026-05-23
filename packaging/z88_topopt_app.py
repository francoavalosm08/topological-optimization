"""Packaged desktop entry point for the Z88-backed topology optimizer."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import webbrowser


def main() -> int:
    _bootstrap_import_path()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Start server without opening a browser")
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--smoke-test", action="store_true", help="Import app and run package preflight, then exit")
    parser.add_argument(
        "--allow-missing-z88",
        action="store_true",
        help="For clean-machine smoke tests, allow startup when Z88Arion is not installed",
    )
    args = parser.parse_args()

    if args.install_root:
        os.environ["Z88ARION_ROOT"] = args.install_root

    try:
        if args.smoke_test:
            return _smoke_test(args.allow_missing_z88)
        return _serve(args.host, args.port, args.no_browser, args.log_level)
    except Exception as exc:
        from z88_bridge import write_crash_report

        report = write_crash_report(
            exc,
            context={
                "argv": sys.argv,
                "frozen": bool(getattr(sys, "frozen", False)),
                "bundle_root": str(_bundle_root()),
            },
        )
        print(json.dumps({"status": "crashed", "crash_report": report.to_dict()}, indent=2), file=sys.stderr)
        return 1


def _serve(host: str, port: int, no_browser: bool, log_level: str) -> int:
    import uvicorn

    url = f"http://{host}:{port}"
    if not no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("server.app:app", host=host, port=port, log_level=log_level)
    return 0


def _smoke_test(allow_missing_z88: bool) -> int:
    from server.app import app
    from z88_bridge import run_packaging_preflight

    preflight = run_packaging_preflight()
    checks = preflight.to_dict()["checks"]
    failed = [check for check in checks if check["status"] == "failed"]
    if allow_missing_z88:
        failed = [check for check in failed if check["name"] != "z88_installation"]

    payload = {
        "status": "ok" if not failed else "failed",
        "route_count": len(app.routes),
        "preflight": preflight.to_dict(),
        "failed_checks": failed,
        "bundle_root": str(_bundle_root()),
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failed else 2


def _bootstrap_import_path() -> None:
    root = _bundle_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(main())
