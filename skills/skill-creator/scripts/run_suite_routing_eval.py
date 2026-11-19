#!/usr/bin/env python3
"""Run real-model routing evals against the installed skill suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_eval import find_project_root, opencode_executable


CREATE_NEW_PROCESS_GROUP = 0x00000200 if os.name == "nt" else 0


def load_eval_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("routing eval file must contain a non-empty cases list")
    normalized: list[dict] = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")
        query = case.get("query", case.get("prompt"))
        expected_skill = case.get("expected_skill")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"case {index} must contain a non-empty query")
        if not isinstance(expected_skill, str) or not expected_skill.strip():
            raise ValueError(f"case {index} must contain expected_skill")
        normalized.append({**case, "query": query, "expected_skill": expected_skill})
    return normalized


def parse_loaded_skills(output: str) -> list[str]:
    loaded: list[str] = []
    seen: set[str] = set()
    valid_events = 0
    malformed_lines = 0
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            continue
        valid_events += 1
        if event.get("type") != "tool_use":
            continue
        part = event.get("part", {})
        if part.get("tool") != "skill":
            continue
        state = part.get("state", {})
        tool_input = state.get("input", {})
        name = tool_input.get("name")
        if isinstance(name, str) and name not in seen:
            seen.add(name)
            loaded.append(name)
    if malformed_lines:
        raise ValueError(f"opencode returned {malformed_lines} malformed JSON event line(s)")
    if valid_events == 0:
        raise ValueError("opencode returned no valid JSON event stream")
    return loaded


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()


def run_opencode_command(cmd: list[str], project_root: str, timeout: int) -> tuple[int | None, str, str, str | None]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.Popen(
        cmd,
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NEW_PROCESS_GROUP,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return None, stdout, stderr, f"timeout after {timeout}s"
    return process.returncode, stdout, stderr, None


def run_single_query(
    query: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
) -> dict:
    cmd = [
        opencode_executable(),
        "run",
        "--format",
        "json",
        "--dir",
        project_root,
        query,
    ]
    if model:
        cmd.extend(["--model", model])

    returncode, stdout, stderr, timeout_error = run_opencode_command(cmd, project_root, timeout)
    if timeout_error:
        return {"loaded_skills": None, "error": timeout_error}
    if returncode != 0:
        return {
            "loaded_skills": None,
            "error": f"opencode exited {returncode}: {stderr.strip()}",
        }
    try:
        loaded_skills = parse_loaded_skills(stdout)
    except ValueError as exc:
        return {"loaded_skills": None, "error": str(exc)}
    return {"loaded_skills": loaded_skills, "error": None}


def build_result(
    results: list[dict],
    model: str | None,
    project_root: Path,
    runs_per_query: int,
    match_threshold: float,
) -> dict:
    passed = sum(1 for item in results if item["pass"])
    infra_failures = sum(item["infra_failures"] for item in results)
    return {
        "eval_type": "suite_routing",
        "model": model,
        "project_root": str(project_root),
        "runs_per_query": runs_per_query,
        "match_threshold": match_threshold,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "infra_failures": infra_failures,
            "pass_rate": passed / len(results) if results else 0.0,
        },
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score_case(case: dict, outcomes: list[dict], match_threshold: float) -> dict:
    expected_skill = case["expected_skill"]
    infra_errors = [outcome["error"] for outcome in outcomes if outcome.get("error")]
    valid_outcomes = [outcome for outcome in outcomes if outcome.get("loaded_skills") is not None]
    forbidden_skills = set(case.get("not_expected_skills", []))
    forbidden_hits = [
        bool(forbidden_skills.intersection(outcome["loaded_skills"]))
        for outcome in valid_outcomes
    ]
    if expected_skill == "none":
        matches = [not outcome["loaded_skills"] and not forbidden_hit
                   for outcome, forbidden_hit in zip(valid_outcomes, forbidden_hits)]
    else:
        matches = [
            expected_skill in outcome["loaded_skills"] and not forbidden_hit
            for outcome, forbidden_hit in zip(valid_outcomes, forbidden_hits)
        ]
    match_rate = sum(matches) / len(matches) if matches else 0.0
    first_skills = [
        outcome["loaded_skills"][0] if outcome["loaded_skills"] else None
        for outcome in valid_outcomes
    ]
    did_pass = not infra_errors and match_rate >= match_threshold
    return {
        "query": case["query"],
        "expected_skill": expected_skill,
        "reason": case.get("reason"),
        "not_expected_skills": sorted(forbidden_skills),
        "forbidden_owner_hits": sum(forbidden_hits),
        "match_rate": match_rate,
        "matches": sum(matches),
        "runs": len(outcomes),
        "infra_failures": len(infra_errors),
        "errors": infra_errors,
        "first_skills": first_skills,
        "loaded_skills_by_run": [outcome.get("loaded_skills") for outcome in outcomes],
        "pass": did_pass,
    }


def run_suite_eval(
    cases: list[dict],
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int,
    match_threshold: float,
    model: str | None,
    checkpoint_path: Path | None = None,
    progress: bool = False,
) -> dict:
    if num_workers == 1:
        results: list[dict] = []
        total = len(cases)
        for index, case in enumerate(cases, start=1):
            if progress:
                preview = case["query"].replace("\n", " ")[:90]
                print(
                    f"[{index}/{total}] expected={case['expected_skill']} query={preview}",
                    file=sys.stderr,
                    flush=True,
                )
            outcomes = [
                run_single_query(case["query"], timeout, str(project_root), model)
                for _ in range(runs_per_query)
            ]
            scored = score_case(case, outcomes, match_threshold)
            results.append(scored)
            if progress:
                status = "PASS" if scored["pass"] else "FAIL"
                print(
                    f"[{index}/{total}] {status} loaded={scored['loaded_skills_by_run']}",
                    file=sys.stderr,
                    flush=True,
                )
            if checkpoint_path:
                write_json(
                    checkpoint_path,
                    build_result(results, model, project_root, runs_per_query, match_threshold),
                )
        return build_result(results, model, project_root, runs_per_query, match_threshold)

    query_runs: dict[str, list[dict]] = {}
    query_cases: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_case = {}
        for case in cases:
            query_cases[case["query"]] = case
            for _ in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    case["query"],
                    timeout,
                    str(project_root),
                    model,
                )
                future_to_case[future] = case
        for future in as_completed(future_to_case):
            case = future_to_case[future]
            query = case["query"]
            query_runs.setdefault(query, [])
            try:
                query_runs[query].append(future.result())
            except Exception as exc:
                query_runs[query].append({"loaded_skills": None, "error": f"executor failure: {exc}"})

    results = [
        score_case(query_cases[query], outcomes, match_threshold)
        for query, outcomes in query_runs.items()
    ]
    results.sort(key=lambda item: item["query"])
    return build_result(results, model, project_root, runs_per_query, match_threshold)


def main(argv: list[str]) -> int:
    default_eval = Path(__file__).resolve().parents[1] / "evals" / "reverse-suite-routing-evals.json"
    parser = argparse.ArgumentParser(description="Run routing evals against the installed skill suite.")
    parser.add_argument("eval_file", nargs="?", default=str(default_eval))
    parser.add_argument("--project-root", default=str(find_project_root()))
    parser.add_argument("--model", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--runs-per-query", type=int, default=1)
    parser.add_argument("--match-threshold", type=float, default=0.5)
    parser.add_argument("--offset", type=int, default=0, help="Start case index, zero-based.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of cases to run.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args(argv[1:])

    cases = load_eval_cases(Path(args.eval_file))
    if args.offset < 0:
        raise ValueError("--offset must be non-negative")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be positive")
    cases = cases[args.offset:]
    if args.limit is not None:
        cases = cases[: args.limit]
    output_path = Path(args.output) if args.output else None
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial") if output_path else None
    result = run_suite_eval(
        cases=cases,
        num_workers=args.workers,
        timeout=args.timeout,
        project_root=Path(args.project_root).resolve(),
        runs_per_query=args.runs_per_query,
        match_threshold=args.match_threshold,
        model=args.model,
        checkpoint_path=checkpoint_path,
        progress=not args.no_progress,
    )
    if output_path:
        write_json(output_path, result)
        print(str(output_path))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
