"""Generate a confirmed OC-native Z88 project from a Z88RunConfig JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import Z88RunConfig, run_generated_oc_workflow, write_native_oc_project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_json", help="Path to a serialized Z88RunConfig JSON file")
    parser.add_argument(
        "--project-dir",
        help="Output native project folder. Defaults to runs/z88/native_<run-id>/z88_project",
    )
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--max-elements", type=int, default=200_000)
    parser.add_argument(
        "--run-workflow",
        action="store_true",
        help="After writing, run the confirmed generated-OC backend workflow",
    )
    parser.add_argument("--optimizer-timeout", type=float, default=900.0)
    parser.add_argument("--displacement-timeout", type=float, default=300.0)
    parser.add_argument(
        "--generate-stress",
        action="store_true",
        help="Run observed z88rTOSS -SIG stress postprocess after displacements",
    )
    parser.add_argument("--stress-timeout", type=float, default=300.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = Z88RunConfig.from_json_file(args.config_json)
    project_dir = Path(args.project_dir) if args.project_dir else _default_project_dir(config)
    result = write_native_oc_project(
        config,
        project_dir,
        install_root=args.install_root,
        max_elements=args.max_elements,
    )
    payload: dict[str, object] = {"write": result.to_dict()}
    exit_code = 0
    if args.run_workflow:
        workflow = run_generated_oc_workflow(
            project_dir,
            install_root=args.install_root,
            optimizer_timeout_s=args.optimizer_timeout,
            displacement_timeout_s=args.displacement_timeout,
            stress_timeout_s=args.stress_timeout,
            generate_stress=args.generate_stress,
        )
        payload["workflow"] = workflow.to_dict() if args.verbose else workflow.compact_dict()
        exit_code = 0 if workflow.status == "completed" else 2
    print(json.dumps(payload, indent=2))
    return exit_code


def _default_project_dir(config: Z88RunConfig) -> Path:
    return Path("runs") / "z88" / f"native_{config.project_name}_{config.run_id()}" / "z88_project"


if __name__ == "__main__":
    raise SystemExit(main())
