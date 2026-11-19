#!/usr/bin/env python3
"""Run the local skill-suite validation gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


STALE_TERMS = (
    "camoufox-js-reverse",
    "spider-king",
    "captcha-slide-reverse",
)
TEXT_SUFFIXES = {".md", ".json", ".html", ".yaml", ".yml"}
GENERATED_NAMES = {"__pycache__", "node_modules", ".pytest_cache"}
GENERATED_SUFFIXES = {".pyc"}
GENERATED_FILES = {"package-lock.json"}
# A lockfile is normally build output, but the static-AST profile ships one on
# purpose: its documented workflow copies `package.json` + `package-lock.json`
# into a task-local directory, records both hashes, and runs
# `npm ci --ignore-scripts` (which fails without a lock). Removing it would
# drop transitive-dependency pinning for target-supplied JavaScript tooling.
# Scoped to this exact path so the rule still applies everywhere else.
PINNED_LOCKFILE_ALLOWLIST = frozenset(
    {"trace/references/profiles/static-ast/package-lock.json"}
)
GENERATED_PREFIXES = ("routing-results", "output-contract-results")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def run_command(name: str, args: list[str], cwd: Path) -> CheckResult:
    python_args = list(args)
    if python_args and Path(python_args[0]).name.startswith("python"):
        python_args = [python_args[0], "-B", *python_args[1:]]
    completed = subprocess.run(
        python_args,
        cwd=str(cwd),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout.strip()
    return CheckResult(name=name, ok=completed.returncode == 0, detail=output)


def active_skills(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if (path / "SKILL.md").is_file())


def scan_stale_terms(root: Path) -> CheckResult:
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in GENERATED_NAMES or part == ".git" for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        lower = text.lower()
        for term in STALE_TERMS:
            if term in lower:
                hits.append(f"{path.relative_to(root)}: {term}")
    detail = "no stale route terms" if not hits else "\n".join(hits)
    return CheckResult("stale-route-scan", not hits, detail)


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def scan_json_syntax(root: Path) -> CheckResult:
    hits: list[str] = []
    for path in root.rglob("*.json"):
        if any(part in GENERATED_NAMES or part == ".git" for part in path.parts):
            continue
        try:
            json.loads(
                path.read_text(encoding="utf-8-sig"),
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            hits.append(f"{path.relative_to(root)}: {exc}")
    detail = "all JSON files parse" if not hits else "\n".join(hits)
    return CheckResult("json-syntax-scan", not hits, detail)


def scan_routing_eval_schema(root: Path) -> CheckResult:
    hits: list[str] = []
    allowed_skills = {path.name for path in active_skills(root)} | {"customize-opencode", "none"}
    for path in root.rglob("*routing-evals.json"):
        if any(part in GENERATED_NAMES or part == ".git" for part in path.parts):
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        cases = data.get("cases") if isinstance(data, dict) else None
        if not isinstance(cases, list) or not cases:
            hits.append(f"{path.relative_to(root)}: missing non-empty cases list")
            continue
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                hits.append(f"{path.relative_to(root)} case {index}: must be an object")
                continue
            query = case.get("query")
            expected_skill = case.get("expected_skill")
            if not isinstance(query, str) or not query.strip():
                hits.append(f"{path.relative_to(root)} case {index}: missing query")
            if expected_skill not in allowed_skills:
                hits.append(
                    f"{path.relative_to(root)} case {index}: invalid expected_skill {expected_skill!r}"
                )
            not_expected = case.get("not_expected_skills", [])
            if not isinstance(not_expected, list):
                hits.append(f"{path.relative_to(root)} case {index}: not_expected_skills must be a list")
            else:
                for value in not_expected:
                    if value not in allowed_skills:
                        hits.append(
                            f"{path.relative_to(root)} case {index}: invalid not_expected_skills value {value!r}"
                        )
                    if value == expected_skill:
                        hits.append(
                            f"{path.relative_to(root)} case {index}: expected_skill cannot also be not_expected_skills"
                        )
    detail = "routing eval schemas are valid" if not hits else "\n".join(hits)
    return CheckResult("routing-eval-schema-scan", not hits, detail)


def scan_output_contract_eval_schema(root: Path) -> CheckResult:
    hits: list[str] = []
    allowed_skills = {path.name for path in active_skills(root)} | {"customize-opencode", "none"}
    for path in root.rglob("*output-contract-evals.json"):
        if any(part in GENERATED_NAMES or part == ".git" for part in path.parts):
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        cases = data.get("cases") if isinstance(data, dict) else None
        if not isinstance(cases, list) or not cases:
            hits.append(f"{path.relative_to(root)}: missing non-empty cases list")
            continue
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                hits.append(f"{path.relative_to(root)} case {index}: must be an object")
                continue
            if not isinstance(case.get("query"), str) or not case["query"].strip():
                hits.append(f"{path.relative_to(root)} case {index}: missing query")
            if case.get("expected_skill") not in allowed_skills:
                hits.append(f"{path.relative_to(root)} case {index}: invalid expected_skill")
            if not isinstance(case.get("must_include"), list):
                hits.append(f"{path.relative_to(root)} case {index}: missing must_include list")
            if not isinstance(case.get("must_not_include", []), list):
                hits.append(f"{path.relative_to(root)} case {index}: must_not_include must be a list")
    detail = "output contract eval schemas are valid" if not hits else "\n".join(hits)
    return CheckResult("output-contract-eval-schema-scan", not hits, detail)


def scan_generated_artifacts(root: Path) -> CheckResult:
    hits: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part == ".git" for part in path.parts):
            continue
        if path.name in GENERATED_NAMES or path.name in GENERATED_FILES:
            if rel.as_posix() in PINNED_LOCKFILE_ALLOWLIST:
                continue
            hits.append(str(rel))
        elif any(path.name.startswith(prefix) for prefix in GENERATED_PREFIXES):
            hits.append(str(rel))
        elif path.is_file() and path.suffix.lower() in GENERATED_SUFFIXES:
            hits.append(str(rel))
    detail = "no generated artifacts" if not hits else "\n".join(sorted(hits))
    return CheckResult("generated-artifact-scan", not hits, detail)


def validate_all(root: Path, run_trace_tests: bool) -> list[CheckResult]:
    results: list[CheckResult] = []
    quick_validate = root / "skill-creator" / "scripts" / "quick_validate.py"
    if not quick_validate.is_file():
        return [CheckResult("bootstrap", False, f"missing {quick_validate}")]

    for skill_root in active_skills(root):
        skill_name = skill_root.name
        results.append(
            run_command(
                f"quick_validate:{skill_name}",
                [sys.executable, str(quick_validate), skill_name],
                root,
            )
        )
        specialist_validator = skill_root / "scripts" / "validate_skill.py"
        if specialist_validator.is_file():
            results.append(
                run_command(
                    f"specialist_validate:{skill_name}",
                    [sys.executable, str(specialist_validator), skill_name],
                    root,
                )
            )

    trace_tests = root / "trace" / "tests"
    if run_trace_tests and trace_tests.is_dir():
        results.append(
            run_command(
                "pytest:trace/tests",
                [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", str(trace_tests)],
                root,
            )
        )

    results.append(scan_stale_terms(root))
    results.append(scan_json_syntax(root))
    results.append(scan_routing_eval_schema(root))
    results.append(scan_output_contract_eval_schema(root))
    results.append(scan_generated_artifacts(root))
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate the local OpenCode skill suite.")
    parser.add_argument(
        "skills_root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[2]),
        help="Path to the skills root directory.",
    )
    parser.add_argument(
        "--skip-trace-tests",
        action="store_true",
        help="Skip pytest for trace/tests.",
    )
    args = parser.parse_args(argv[1:])

    root = Path(args.skills_root).resolve()
    results = validate_all(root, run_trace_tests=not args.skip_trace_tests)
    failures = [result for result in results if not result.ok]

    print(f"skills_root={root}")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name}")
        if not result.ok or result.name.endswith("scan"):
            print(result.detail)

    if failures:
        print(f"validation=FAIL failures={len(failures)} checks={len(results)}")
        return 1
    print(f"validation=PASS checks={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
