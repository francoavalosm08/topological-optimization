"""Collect observed native Z88 optimizer outputs into JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import collect_native_results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Completed native Z88 optimizer project folder")
    parser.add_argument(
        "--output",
        help="Output JSON path. Defaults to <project_dir>/z88_native_results.json",
    )
    parser.add_argument("--verbose", action="store_true", help="Print the full collected JSON payload")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    summary = collect_native_results(project_dir)
    output = Path(args.output).resolve() if args.output else project_dir / "z88_native_results.json"
    summary.write_json(output)
    payload = summary.to_dict() if args.verbose else _compact_payload(summary.to_dict())
    payload["output"] = str(output)
    print(json.dumps(payload, indent=2))
    return 0 if summary.status in {"collected", "partial"} else 2


def _compact_payload(payload: dict) -> dict:
    histories = {
        name: {
            "count": history["count"],
            "final_value": history["final_value"],
            "warnings": history["warnings"],
            "parse_errors": history["parse_errors"],
        }
        for name, history in payload["histories"].items()
    }
    snapshots = {
        name: {
            "count": snapshot["count"],
            "first_iteration": snapshot["first_iteration"],
            "last_iteration": snapshot["last_iteration"],
            "final_summary": _compact_field_summary(snapshot["final_summary"]),
            "warnings": snapshot["warnings"],
        }
        for name, snapshot in payload["snapshots"].items()
    }
    return {
        "schema_version": payload["schema_version"],
        "project_dir": payload["project_dir"],
        "status": payload["status"],
        "histories": histories,
        "snapshots": snapshots,
        "displacement": payload["displacement"],
        "warnings": payload["warnings"],
        "parse_errors": payload["parse_errors"],
    }


def _compact_field_summary(summary: dict | None) -> dict | None:
    if summary is None:
        return None
    return {
        "row_count": summary["row_count"],
        "min_value": summary["min_value"],
        "max_value": summary["max_value"],
        "mean_value": summary["mean_value"],
        "min_id": summary["min_id"],
        "max_id": summary["max_id"],
        "zero_count": summary["zero_count"],
        "nonzero_count": summary["nonzero_count"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
