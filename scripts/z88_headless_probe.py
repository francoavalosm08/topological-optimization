"""Probe installed Z88 binaries for help/cwd execution behavior."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from z88_bridge import diff_project_dirs, discover_installation, ensure_asset_layout


HELP_ARGS = ("-h", "--help", "/?")
OUTPUT_PREVIEW_CHARS = 4000
PROBE_BINARIES = {
    "Z88OC": "oc_exe",
    "z88optopus": "optopus_exe",
    "z88rTOSS": "toss_exe",
    "z88r_sko": "sko_exe",
    "z88r_opt": "solver_exe",
    "z88ag2oi": "ag2oi_exe",
}
ROOT_LOGS = ("Z88OC.log", "z88r.log", "z88rtoss.log", "z88r_opt.log", "z88r_sko.log")


def _run_capture(command: list[str], cwd: Path, out_dir: Path, label: str, timeout_s: float) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        timed_out = False
        stdout = _decode_stream(proc.stdout)
        stderr = _decode_stream(proc.stderr)
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = _decode_stream(exc.stdout)
        stderr = _decode_stream(exc.stderr)
        returncode = None
    elapsed = time.time() - started
    (out_dir / f"{label}.stdout.txt").write_text(stdout, encoding="utf-8", errors="replace")
    (out_dir / f"{label}.stderr.txt").write_text(stderr, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_s": elapsed,
        "stdout_file": str(out_dir / f"{label}.stdout.txt"),
        "stderr_file": str(out_dir / f"{label}.stderr.txt"),
        "stdout_preview": stdout[:OUTPUT_PREVIEW_CHARS],
        "stderr_preview": stderr[:OUTPUT_PREVIEW_CHARS],
    }


def _decode_stream(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def _classify(
    help_results: list[dict],
    cwd_result: dict | None,
    cwd_diff: dict | None = None,
    extra_output: str = "",
    ignored_added: set[str] | None = None,
) -> str:
    if cwd_result and cwd_result.get("timed_out"):
        return "timed_out"
    cwd_output = ""
    if cwd_result:
        cwd_output = cwd_result.get("stdout_preview", "") + cwd_result.get("stderr_preview", "") + extra_output
    if _mentions_missing(cwd_output, "Z88.DYN"):
        return "needs_solver_files"
    if _mentions_missing(cwd_output, "Z88MANAGE.TXT"):
        return "needs_project_files"
    if _mentions_converter_failure(cwd_output):
        return "conversion_failed"
    if _mentions_usage_error(cwd_output):
        return "usage_error"
    if _mentions_success(cwd_output):
        if cwd_diff and _diff_has_changes(cwd_diff, ignored_added=ignored_added):
            return "runs_from_cwd"
        return "runs_from_cwd"
    if cwd_result and _is_windows_crash(cwd_result.get("returncode")):
        return "crashed"
    if cwd_diff and _diff_has_changes(cwd_diff, ignored_added=ignored_added):
        if cwd_result and cwd_result.get("returncode") == 0:
            return "runs_from_cwd"
        return "mutated_project"
    if cwd_result and not cwd_result["timed_out"] and cwd_result["returncode"] == 0:
        return "runs_from_cwd"
    if cwd_result and (cwd_result["timed_out"] or cwd_result["returncode"] not in (0, None)):
        return "failed"
    combined_output = " ".join(
        [item.get("stdout_preview", "") + item.get("stderr_preview", "") for item in help_results]
        + [extra_output]
    )
    if _mentions_missing(combined_output, "Z88.DYN"):
        return "needs_solver_files"
    if _mentions_missing(combined_output, "Z88MANAGE.TXT"):
        return "needs_project_files"
    if _mentions_converter_failure(combined_output):
        return "conversion_failed"
    if _mentions_usage_error(combined_output):
        return "usage_error"
    if any(not item["timed_out"] and (item["stdout_preview"] or item["stderr_preview"]) for item in help_results):
        return "help_available"
    return "unknown"


def _is_windows_crash(returncode: int | None) -> bool:
    if returncode is None:
        return False
    # 0xC0000135 and similar NTSTATUS values can surface as large positive ints
    # or signed negative ints on Windows Python.
    unsigned = returncode + 2**32 if returncode < 0 else returncode
    return unsigned >= 0xC0000000


def _mentions_missing(output: str, filename: str) -> bool:
    normalized = output.lower()
    target = filename.lower()
    return (
        f"cannot open {target}" in normalized
        or f"kann {target} nicht" in normalized
        or f"can't open {target}" in normalized
    )


def _mentions_usage_error(output: str) -> bool:
    return any(
        marker in output
        for marker in (
            "Richtiger Aufruf",
            "Steuerflags falsch",
            "Fehlerhafter Programmaufruf",
            "Bitte Flag",
        )
    )


def _mentions_converter_failure(output: str) -> bool:
    return any(
        marker in output
        for marker in (
            "Problem while writing z88i1.txt",
            "Problem beim i1-Schreiben",
        )
    )


def _mentions_success(output: str) -> bool:
    return any(
        marker in output
        for marker in (
            ">>> Z88R >>> Programm erfolgreich gelaufen!",
            ">>> Programm erfolgreich gelaufen!",
        )
    )


def _diff_has_changes(diff: dict, *, ignored_added: set[str] | None = None) -> bool:
    counts = diff.get("counts", {})
    ignored_added = ignored_added or set()
    if isinstance(diff.get("added"), dict):
        added_count = len(set(diff["added"]) - ignored_added)
    else:
        added_count = counts.get("added", 0)
    return bool(added_count or counts.get("removed") or counts.get("modified"))


def _copy_fixture_for_probe(fixture: Path, work_root: Path, binary_name: str) -> Path:
    if not fixture.is_dir():
        raise FileNotFoundError(f"fixture does not exist: {fixture}")
    destination = work_root / binary_name
    if destination.exists():
        _remove_tree(destination)
    shutil.copytree(fixture, destination)
    return destination


def _seed_runtime_files(destination: Path, runtime_files: list[Path]) -> list[dict]:
    seeded: list[dict] = []
    for source in runtime_files:
        if not source.is_file():
            raise FileNotFoundError(f"runtime file does not exist: {source}")
        target_name = "Z88.DYN" if source.name.lower() == "z88.dyn" else source.name
        target = destination / target_name
        shutil.copy2(source, target)
        seeded.append(
            {
                "source": str(source),
                "destination": str(target),
                "relative_path": target.name,
                "bytes": target.stat().st_size,
            }
        )
    return seeded


def _remove_tree(path: Path) -> None:
    def _onexc(function, item, excinfo):
        try:
            os.chmod(item, stat.S_IWRITE)
            function(item)
        except OSError:
            raise excinfo[1]

    shutil.rmtree(path, onexc=_onexc)


def _collect_root_logs(cwd: Path, out_dir: Path) -> list[dict]:
    log_dir = out_dir / "root_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict] = []
    for name in ROOT_LOGS:
        source = cwd / name
        if not source.exists():
            continue
        destination = log_dir / name
        shutil.copy2(source, destination)
        copied.append(
            {
                "source": str(source),
                "destination": str(destination),
                "bytes": destination.stat().st_size,
                "preview": _safe_text_preview(destination),
            }
        )
    return copied


def _safe_text_preview(path: Path, limit: int = 1000) -> str:
    data = path.read_bytes()
    if len(data) > limit:
        data = data[-limit:]
    return data.decode("utf-8", errors="replace")


def _combined_log_preview(logs: list[dict]) -> str:
    return " ".join(str(item.get("preview", "")) for item in logs)


def _parse_candidate_argv(values: list[str] | None) -> list[list[str]]:
    return [shlex.split(value, posix=False) for value in values or []]


def _resolve_runtime_files(
    installation,
    *,
    seed_runtime: bool,
    runtime_files: list[str] | None,
) -> list[Path]:
    resolved: list[Path] = []
    if seed_runtime:
        default_dyn = installation.bin_dir / "z88.dyn"
        if default_dyn.exists():
            resolved.append(default_dyn)
    for value in runtime_files or []:
        resolved.append(Path(value))
    return resolved


def _run_cwd_probe(
    *,
    binary: Path,
    binary_name: str,
    fixture: Path,
    work_root: Path,
    binary_out: Path,
    label: str,
    timeout_s: float,
    runtime_files: list[Path],
    extra_args: list[str] | None = None,
) -> dict:
    copy_name = binary_name if label == "cwd_no_args" else f"{binary_name}_{label}"
    working_copy = _copy_fixture_for_probe(fixture, work_root, copy_name)
    seeded = _seed_runtime_files(working_copy, runtime_files) if runtime_files else []
    result = _run_capture(
        [str(binary), *(extra_args or [])],
        working_copy,
        binary_out,
        label,
        timeout_s,
    )
    root_logs = _collect_root_logs(working_copy, binary_out / label)
    cwd_diff = diff_project_dirs(fixture, working_copy)
    (binary_out / f"{label}.cwd_diff.json").write_text(
        json.dumps(cwd_diff, indent=2),
        encoding="utf-8",
    )
    return {
        "label": label,
        "argv": extra_args or [],
        "result": result,
        "cwd_diff": cwd_diff,
        "root_logs": root_logs,
        "runtime_files_seeded": seeded,
        "working_copy": str(working_copy),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", help="Override Z88Arion install root")
    parser.add_argument("--asset-root", default="z88_assets")
    parser.add_argument(
        "--fixture",
        default="z88_assets/examples/pre/2_Querlenker_OC",
        help="Copied fixture project directory used for cwd-only probes",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--mode",
        choices=("help-only", "cwd-no-args", "cwd-copy"),
        default="help-only",
        help="Probe mode. cwd modes run no-arg binary calls inside a copied fixture.",
    )
    parser.add_argument(
        "--binary",
        action="append",
        choices=tuple(PROBE_BINARIES),
        help="Probe only the selected binary. May be passed multiple times.",
    )
    parser.add_argument(
        "--working-copy",
        help="Directory for per-binary fixture copies used by cwd probes",
    )
    parser.add_argument(
        "--run-cwd",
        action="store_true",
        help="Backward-compatible alias for --mode cwd-copy",
    )
    parser.add_argument(
        "--seed-runtime",
        action="store_true",
        help="Copy default runtime files such as z88.dyn into each working-copy probe.",
    )
    parser.add_argument(
        "--runtime-file",
        action="append",
        help="Additional runtime file to copy into each working-copy probe. May be repeated.",
    )
    parser.add_argument(
        "--candidate-argv",
        action="append",
        help="Additional argv string to run in its own copied fixture, for example '-t -siccg'. May be repeated.",
    )
    parser.add_argument("--full-output", action="store_true", help="Print full probe JSON")
    args = parser.parse_args()

    installation = discover_installation(args.install_root)
    paths = ensure_asset_layout(args.asset_root)
    out_dir = paths["outputs"] / "headless_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture = Path(args.fixture)
    mode = "cwd-copy" if args.run_cwd else args.mode
    selected_binaries = args.binary or list(PROBE_BINARIES)
    work_root = Path(args.working_copy) if args.working_copy else out_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    runtime_files = _resolve_runtime_files(
        installation,
        seed_runtime=args.seed_runtime,
        runtime_files=args.runtime_file,
    )
    candidate_argv = _parse_candidate_argv(args.candidate_argv)

    results: dict[str, dict] = {}
    for binary_name in selected_binaries:
        attr = PROBE_BINARIES[binary_name]
        binary = getattr(installation, attr)
        if binary is None:
            results[binary_name] = {"status": "missing", "binary": None}
            continue
        binary_out = out_dir / binary_name
        if binary_out.exists():
            _remove_tree(binary_out)
        binary_out.mkdir(parents=True)
        help_results = [
            _run_capture([str(binary), help_arg], ROOT, binary_out, f"help_{idx}", args.timeout)
            for idx, help_arg in enumerate(HELP_ARGS)
        ]
        cwd_result = None
        cwd_diff = None
        root_logs: list[dict] = []
        working_copy = None
        runtime_files_seeded: list[dict] = []
        candidate_results: list[dict] = []
        if mode in {"cwd-no-args", "cwd-copy"}:
            try:
                primary = _run_cwd_probe(
                    binary=binary,
                    binary_name=binary_name,
                    fixture=fixture,
                    work_root=work_root,
                    binary_out=binary_out,
                    label="cwd_no_args",
                    timeout_s=args.timeout,
                    runtime_files=runtime_files,
                )
                cwd_result = primary["result"]
                cwd_diff = primary["cwd_diff"]
                root_logs = primary["root_logs"]
                working_copy = Path(primary["working_copy"])
                runtime_files_seeded = primary["runtime_files_seeded"]
                (binary_out / "cwd_diff.json").write_text(
                    json.dumps(cwd_diff, indent=2),
                    encoding="utf-8",
                )
                for idx, argv in enumerate(candidate_argv):
                    candidate = _run_cwd_probe(
                        binary=binary,
                        binary_name=binary_name,
                        fixture=fixture,
                        work_root=work_root,
                        binary_out=binary_out,
                        label=f"candidate_{idx}",
                        timeout_s=args.timeout,
                        runtime_files=runtime_files,
                        extra_args=argv,
                    )
                    candidate["status"] = _classify(
                        [],
                        candidate["result"],
                        candidate["cwd_diff"],
                        _combined_log_preview(candidate["root_logs"]),
                        ignored_added={
                            item["relative_path"] for item in candidate["runtime_files_seeded"]
                        },
                    )
                    candidate_results.append(candidate)
            except (FileNotFoundError, OSError, ValueError) as exc:
                cwd_result = {"error": str(exc)}
        results[binary_name] = {
            "binary": str(binary),
            "status": _classify(
                help_results,
                cwd_result if isinstance(cwd_result, dict) and "command" in cwd_result else None,
                cwd_diff,
                _combined_log_preview(root_logs),
                ignored_added={item["relative_path"] for item in runtime_files_seeded},
            ),
            "help_results": help_results,
            "cwd_result": cwd_result,
            "cwd_diff": cwd_diff,
            "root_logs": root_logs,
            "runtime_files_seeded": runtime_files_seeded,
            "candidate_results": candidate_results,
            "working_copy": str(working_copy) if working_copy else None,
        }

    payload = {
        "installation": installation.to_dict(),
        "fixture": str(fixture),
        "mode": mode,
        "runtime_files": [str(path) for path in runtime_files],
        "candidate_argv": candidate_argv,
        "working_copy_root": str(work_root),
        "output_dir": str(out_dir),
        "results": results,
    }
    output_path = out_dir / "probe_results.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.full_output:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps(_summarize_payload(payload, output_path), indent=2))
    return 0


def _summarize_payload(payload: dict, output_path: Path) -> dict:
    return {
        "mode": payload["mode"],
        "fixture": payload["fixture"],
        "output_json": str(output_path),
        "working_copy_root": payload["working_copy_root"],
        "runtime_files": payload.get("runtime_files", []),
        "candidate_argv": payload.get("candidate_argv", []),
        "results": {
            name: {
                "status": item["status"],
                "binary": item["binary"],
                "cwd_returncode": None
                if not isinstance(item.get("cwd_result"), dict)
                else item["cwd_result"].get("returncode"),
                "cwd_diff_counts": None
                if not isinstance(item.get("cwd_diff"), dict)
                else item["cwd_diff"].get("counts"),
                "working_copy": item.get("working_copy"),
                "candidate_results": [
                    {
                        "label": candidate["label"],
                        "argv": candidate["argv"],
                        "status": candidate.get("status"),
                        "returncode": candidate.get("result", {}).get("returncode"),
                        "timed_out": candidate.get("result", {}).get("timed_out"),
                        "cwd_diff_counts": candidate.get("cwd_diff", {}).get("counts"),
                        "working_copy": candidate.get("working_copy"),
                    }
                    for candidate in item.get("candidate_results", [])
                ],
            }
            for name, item in payload["results"].items()
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
