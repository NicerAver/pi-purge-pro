#!/usr/bin/env python3
"""Run paired pi-native routing evals with and without the local skill suite."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.dont_write_bytecode = True

OWNER_PATTERN = re.compile(r'"OWNER"\s*:\s*"([^"]+)"')
PLAIN_OWNER_PATTERN = re.compile(r'''(?im)^\s*OWNER\s*[:=]\s*["']?([a-z0-9-]+)["']?\s*$''')
VALID_OWNERS = {
    "trace",
    "akamai-protocol-reverse",
    "captcha-reverse",
    "captcha-vision",
    "iv8-web-reverse",
    "nv8-node-runtime",
    "wechat-miniapp-reverse",
    "skill-creator",
    "customize-opencode",
    "none",
}
ROUTING_PREAMBLE = (
    "This is a routing-only evaluation. Choose exactly one OWNER from: "
    "trace, akamai-protocol-reverse, captcha-reverse, captcha-vision, "
    "iv8-web-reverse, nv8-node-runtime, wechat-miniapp-reverse, "
    "skill-creator, customize-opencode, none. "
    "Return only compact JSON with one key OWNER."
)
ROUTING_INSTRUCTION = f"{ROUTING_PREAMBLE} User request: "


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("eval file must contain a non-empty cases list")
    return cases


def parse_owner(output: str) -> str | None:
    # Prefer a valid JSON envelope, but tolerate a bare OWNER line from a model
    # so routing correctness is not conflated with formatting noise.
    for pattern in (OWNER_PATTERN, PLAIN_OWNER_PATTERN):
        for match in pattern.finditer(output):
            owner = match.group(1)
            if owner in VALID_OWNERS:
                return owner
    return None


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)")
    match = pattern.search(text)
    if not match:
        raise ValueError(f"missing markdown section: {heading}")
    return match.group("body").strip()


def load_routing_gate(path: Path | None) -> str | None:
    if path is None:
        return None
    text = path.read_text(encoding="utf-8-sig")
    return extract_markdown_section(text, "Routing Precedence")


def build_routing_instruction(routing_gate: str | None) -> str:
    if not routing_gate:
        return ROUTING_INSTRUCTION
    return (
        f"{ROUTING_PREAMBLE}\n\n"
        "Apply this routing gate before selecting OWNER:\n"
        f"{routing_gate}\n\n"
        "User request: "
    )


def run_one(
    *,
    mode: str,
    case_index: int,
    case: dict,
    node: str,
    pi_cli: Path,
    model: str,
    skill_paths: list[Path],
    timeout: int,
    routing_instruction: str,
) -> dict:
    cmd = [
        node,
        str(pi_cli),
        "--print",
        "--no-session",
        "--provider",
        model.split("/", 1)[0],
        "--model",
        model.split("/", 1)[1],
        "--thinking",
        "off",
        "--no-extensions",
        "--no-skills",
    ]
    if mode == "with_skill":
        for path in skill_paths:
            cmd.extend(["--skill", str(path)])
    cmd.extend(
        [
            "--no-prompt-templates",
            "--no-context-files",
            "--no-tools",
            routing_instruction + case["query"],
        ]
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(Path.home()),
            env={**os.environ, "PI_SKIP_VERSION_CHECK": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        output = completed.stdout.strip()
        owner = parse_owner(output)
        error = None
        if completed.returncode != 0:
            error = f"exit {completed.returncode}: {completed.stderr.strip()}"
        elif owner is None:
            error = f"unparseable output: {output[:500]}"
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        owner = None
        error = f"timeout after {timeout}s"

    expected = case["expected_skill"]
    forbidden = case.get("not_expected_skills", [])
    return {
        "case_index": case_index,
        "mode": mode,
        "query": case["query"],
        "expected_owner": expected,
        "not_expected_owners": forbidden,
        "owner": owner,
        "correct": owner == expected and owner not in forbidden,
        "forbidden_owner_hit": owner in forbidden,
        "elapsed_ms": elapsed_ms,
        "output_chars": len(output),
        "output": output,
        "error": error,
    }


def summarize(results: list[dict], total_cases: int) -> dict:
    summary: dict[str, object] = {"total_cases": total_cases, "completed_runs": len(results)}
    for mode in ("baseline", "with_skill"):
        rows = [row for row in results if row["mode"] == mode]
        valid = [row for row in rows if row["error"] is None]
        summary[mode] = {
            "runs": len(rows),
            "valid": len(valid),
            "correct": sum(bool(row["correct"]) for row in valid),
            "accuracy": (sum(bool(row["correct"]) for row in valid) / len(valid)) if valid else None,
            "errors": len(rows) - len(valid),
            "mean_elapsed_ms": (round(sum(row["elapsed_ms"] for row in valid) / len(valid))) if valid else None,
            "mean_output_chars": (round(sum(row["output_chars"] for row in valid) / len(valid))) if valid else None,
            "forbidden_owner_hits": sum(bool(row.get("forbidden_owner_hit")) for row in valid),
        }
    paired = []
    by_key = {(row["case_index"], row["mode"]): row for row in results}
    for index in range(total_cases):
        baseline = by_key.get((index, "baseline"))
        with_skill = by_key.get((index, "with_skill"))
        if baseline and with_skill and baseline["error"] is None and with_skill["error"] is None:
            paired.append((baseline, with_skill))
    summary["paired_valid"] = len(paired)
    summary["improved"] = sum(not base["correct"] and skilled["correct"] for base, skilled in paired)
    summary["regressed"] = sum(base["correct"] and not skilled["correct"] for base, skilled in paired)
    summary["unchanged_correct"] = sum(base["correct"] and skilled["correct"] for base, skilled in paired)
    summary["unchanged_wrong"] = sum(not base["correct"] and not skilled["correct"] for base, skilled in paired)
    summary["paired_forbidden_owner_hits"] = sum(
        bool(base.get("forbidden_owner_hit")) or bool(skilled.get("forbidden_owner_hit"))
        for base, skilled in paired
    )
    return summary


def portable_path(path: Path, root: Path) -> str:
    """Store paths relative to the skills root in reusable eval artifacts."""
    resolved = path.resolve()
    try:
        return "./" + resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<external>/" + resolved.name


def write_result(path: Path, metadata: dict, results: list[dict], total_cases: int) -> None:
    ordered = sorted(results, key=lambda row: (row["case_index"], row["mode"]))
    payload = {**metadata, "summary": summarize(ordered, total_cases), "results": ordered}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str]) -> int:
    skill_root = Path(__file__).resolve().parents[2]
    default_eval = skill_root / "skill-creator" / "evals" / "reverse-suite-routing-evals.json"
    default_output = skill_root / "skill-creator" / "evals" / "pi-routing-benchmark.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_file", nargs="?", default=str(default_eval))
    parser.add_argument("--output", default=str(default_output))
    parser.add_argument("--pi-cli", required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--model", default="openai/gpt-5.5")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--routing-gate",
        default=None,
        help="Optional markdown file; its 'Routing Precedence' section is injected into each routing prompt.",
    )
    args = parser.parse_args(argv[1:])

    if "/" not in args.model:
        raise ValueError("--model must use provider/model format")
    cases = load_cases(Path(args.eval_file))
    skill_names = [
        "trace",
        "akamai-protocol-reverse",
        "captcha-reverse",
        "captcha-vision",
        "iv8-web-reverse",
        "nv8-node-runtime",
        "wechat-miniapp-reverse",
        "skill-creator",
    ]
    skill_paths = [skill_root / name / "SKILL.md" for name in skill_names]
    missing = [str(path) for path in skill_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing skill files: {missing}")

    routing_gate_path = Path(args.routing_gate).resolve() if args.routing_gate else None
    routing_gate = load_routing_gate(routing_gate_path)
    routing_instruction = build_routing_instruction(routing_gate)

    output = Path(args.output)
    metadata = {
        "eval_type": "pi_native_suite_routing_paired",
        "model": args.model,
        "thinking": "off",
        "eval_file": portable_path(Path(args.eval_file), skill_root),
        "skill_paths": [portable_path(path, skill_root) for path in skill_paths],
        "workers": args.workers,
        "timeout_seconds": args.timeout,
        "routing_gate_path": portable_path(routing_gate_path, skill_root) if routing_gate_path else None,
        "routing_gate_chars": len(routing_gate) if routing_gate else 0,
    }
    results: list[dict] = []
    lock = Lock()
    jobs = [
        (mode, index, case)
        for index, case in enumerate(cases)
        for mode in ("baseline", "with_skill")
    ]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_one,
                mode=mode,
                case_index=index,
                case=case,
                node=args.node,
                pi_cli=Path(args.pi_cli),
                model=args.model,
                skill_paths=skill_paths,
                timeout=args.timeout,
                routing_instruction=routing_instruction,
            ): (mode, index)
            for mode, index, case in jobs
        }
        for future in as_completed(futures):
            row = future.result()
            with lock:
                results.append(row)
                write_result(output, metadata, results, len(cases))
                status = "PASS" if row["correct"] else "FAIL"
                print(
                    f"[{len(results)}/{len(jobs)}] case={row['case_index'] + 1} "
                    f"mode={row['mode']} {status} owner={row['owner']} "
                    f"expected={row['expected_owner']} forbidden={row['forbidden_owner_hit']} "
                    f"elapsed_ms={row['elapsed_ms']}",
                    file=sys.stderr,
                    flush=True,
                )

    final_summary = summarize(results, len(cases))
    print(json.dumps(final_summary, ensure_ascii=False, indent=2))
    return 0 if all(
        row["error"] is None and row["correct"] and not row["forbidden_owner_hit"]
        for row in results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
