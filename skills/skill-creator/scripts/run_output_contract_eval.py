#!/usr/bin/env python3
"""Run real-model output contract evals for the installed skill suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_eval import find_project_root, opencode_executable
from scripts.run_suite_routing_eval import run_opencode_command


OUTPUT_INSTRUCTION = (
    "Triage the complete user request between REQUEST<<< and >>>. "
    "Do not ask for another prompt. Do not call external tools, browse, edit files, "
    "implement code, or run benchmarks. Choose the owning skill/stage and answer only "
    "with these fields: MODE, OWNER, NEXT_GATE, DO_NOT_USE, REQUIRED_EVIDENCE, NOTES. "
    "REQUEST<<<"
)


def load_eval_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("output contract eval file must contain a non-empty cases list")
    return cases


def parse_events(output: str) -> tuple[list[str], str]:
    loaded: list[str] = []
    seen: set[str] = set()
    texts: list[str] = []
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
        part = event.get("part", {})
        if event.get("type") == "tool_use" and part.get("tool") == "skill":
            state = part.get("state", {})
            name = state.get("input", {}).get("name")
            if isinstance(name, str) and name not in seen:
                seen.add(name)
                loaded.append(name)
        elif event.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
    if malformed_lines:
        raise ValueError(f"opencode returned {malformed_lines} malformed JSON event line(s)")
    if valid_events == 0:
        raise ValueError("opencode returned no valid JSON event stream")
    return loaded, "\n".join(texts)


def run_single_case(case: dict, timeout: int, project_root: Path, model: str | None = None) -> dict:
    query = case.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("case is missing query")
    prompt = OUTPUT_INSTRUCTION + query.replace("\n", " ") + ">>>"
    cmd = [opencode_executable(), "run", "--format", "json", "--dir", str(project_root), prompt]
    if model:
        cmd.extend(["--model", model])
    returncode, stdout, stderr, timeout_error = run_opencode_command(cmd, str(project_root), timeout)
    if timeout_error:
        return {"loaded_skills": None, "text": "", "error": timeout_error}
    if returncode != 0:
        return {"loaded_skills": None, "text": "", "error": f"opencode exited {returncode}: {stderr.strip()}"}
    try:
        loaded_skills, text = parse_events(stdout)
    except ValueError as exc:
        return {"loaded_skills": None, "text": "", "error": str(exc)}
    return {"loaded_skills": loaded_skills, "text": text, "error": None}


def score_case(case: dict, outcome: dict) -> dict:
    expected_skill = case.get("expected_skill")
    text = outcome.get("text") or ""
    text_lower = text.lower()
    loaded_skills = outcome.get("loaded_skills")
    errors: list[str] = []
    if outcome.get("error"):
        errors.append(outcome["error"])
    if expected_skill == "none":
        skill_ok = loaded_skills == [] or "owner: none" in text_lower
    elif loaded_skills is None:
        skill_ok = str(expected_skill).lower() in text_lower
    else:
        skill_ok = expected_skill in loaded_skills or str(expected_skill).lower() in text_lower
    if not skill_ok:
        errors.append(f"expected skill {expected_skill!r}, loaded {loaded_skills!r}")
    for term in case.get("must_include", []):
        if str(term).lower() not in text_lower:
            errors.append(f"missing required term: {term}")
    for term in case.get("must_not_include", []):
        if str(term).lower() in text_lower:
            errors.append(f"forbidden term present: {term}")
    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "expected_skill": expected_skill,
        "loaded_skills": loaded_skills,
        "text": text,
        "errors": errors,
        "pass": not errors,
    }


def run_eval(cases: list[dict], timeout: int, project_root: Path, model: str | None) -> dict:
    results = []
    for index, case in enumerate(cases, start=1):
        preview = str(case.get("query", "")).replace("\n", " ")[:90]
        print(f"[{index}/{len(cases)}] id={case.get('id')} query={preview}", file=sys.stderr, flush=True)
        outcome = run_single_case(case, timeout, project_root, model)
        scored = score_case(case, outcome)
        results.append(scored)
        print(f"[{index}/{len(cases)}] {'PASS' if scored['pass'] else 'FAIL'} loaded={scored['loaded_skills']}", file=sys.stderr, flush=True)
    passed = sum(1 for item in results if item["pass"])
    return {
        "eval_type": "output_contract",
        "model": model,
        "project_root": str(project_root),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": passed / len(results) if results else 0.0,
        },
    }


def main(argv: list[str]) -> int:
    default_eval = Path(__file__).resolve().parents[1] / "evals" / "reverse-suite-output-contract-evals.json"
    parser = argparse.ArgumentParser(description="Run output-contract evals against the installed skill suite.")
    parser.add_argument("eval_file", nargs="?", default=str(default_eval))
    parser.add_argument("--project-root", default=str(find_project_root()))
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--offset", type=int, default=0, help="Start case index, zero-based.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of cases to run.")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv[1:])

    cases = load_eval_cases(Path(args.eval_file))
    if args.offset < 0:
        raise ValueError("--offset must be non-negative")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be positive")
    cases = cases[args.offset:]
    if args.limit is not None:
        cases = cases[: args.limit]
    result = run_eval(
        cases,
        timeout=args.timeout,
        project_root=Path(args.project_root).resolve(),
        model=args.model,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(text)
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
