"""Audit a native Z88Arion fixture folder into JSON and Markdown."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import audit_fixture, ensure_asset_layout, write_audit_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Native Z88 project folder to audit")
    parser.add_argument("--asset-root", default="z88_assets")
    parser.add_argument("--name", help="Fixture name override")
    parser.add_argument("--out-json", help="JSON audit output path")
    parser.add_argument("--out-md", help="Markdown audit output path")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    fixture_name = args.name or project_dir.name
    paths = ensure_asset_layout(args.asset_root)
    json_path = Path(args.out_json) if args.out_json else paths["manifests"] / f"{fixture_name}.audit.json"
    markdown_path = Path(args.out_md) if args.out_md else paths["manifests"] / f"{fixture_name}.audit.md"

    audit = audit_fixture(project_dir)
    write_audit_outputs(audit, json_path, markdown_path)
    print(json.dumps({"fixture": fixture_name, "json": str(json_path), "markdown": str(markdown_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
