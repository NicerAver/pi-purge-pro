#!/usr/bin/env python3
"""Validate iv8 specialist trigger, runtime, and Reese84 boundaries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
PATH_RE = re.compile(r"`((?:references|scripts)/[A-Za-z0-9_.\/-]+)`")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.search(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill_path = root / "SKILL.md"
    require(skill_path.is_file(), "missing SKILL.md", errors)
    if not skill_path.is_file():
        return errors

    skill = read_text(skill_path)
    lower = skill.lower()
    fields = parse_frontmatter(skill)
    require(fields.get("name") == "iv8-web-reverse", "frontmatter name mismatch", errors)

    required_literals = (
        "python + iv8",
        "requests",
        "curl_cffi",
        "reese84",
        "普通 403/412",
        "未知 sign",
        "不负责定位普通签名入口",
        "js_reverse_cache",
        "同一个 python session",
        "不写入 skill 目录",
        "observe/capture",
        "captcha-reverse",
        "akamai-protocol-reverse",
    )
    for literal in required_literals:
        require(literal.lower() in lower, f"missing iv8 boundary literal: {literal}", errors)

    require(
        "camoufox-js-reverse" not in lower and "spider-king" not in lower,
        "stale retired skill route remains",
        errors,
    )

    reese_path = root / "references" / "profiles" / "reese84" / "index.md"
    require(reese_path.is_file(), "missing Reese84 profile index", errors)
    if reese_path.is_file():
        reese = read_text(reese_path).lower()
        for literal in (
            "solution.interrogation",
            "renewinsec",
            "cookiedomain",
            "threadpoolexecutor",
            "edge admission",
            "cf-mitigated",
        ):
            require(literal in reese, f"missing Reese84 invariant: {literal}", errors)
        require("最终运行时" in reese or "final runtime" in reese, "missing Reese84 invariant: final runtime", errors)
        require("业务 api" in reese or "business html/api" in reese, "missing Reese84 invariant: business API acceptance", errors)

    edge_path = root / "references" / "profiles" / "reese84" / "edge-admission.md"
    require(edge_path.is_file(), "missing Reese84 edge admission reference", errors)
    if edge_path.is_file():
        edge = read_text(edge_path).lower()
        for literal in (
            "window.__cf$cv$params",
            "managed challenge",
            "随机闭包",
            "eventloop.drain",
            "同一个 python",
        ):
            require(literal in edge, f"missing edge admission invariant: {literal}", errors)

    for match in PATH_RE.finditer(skill):
        rel = match.group(1).rstrip(".,):;]}`")
        require((root / rel).exists(), f"broken routed path: {rel}", errors)

    for json_path in sorted((root / "evals").glob("*.json")):
        try:
            json.loads(read_text(json_path))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {json_path.relative_to(root)}: {exc}")

    require(not list(root.rglob("*.pyc")), "generated .pyc files must not be stored", errors)
    require(not list(root.rglob("__pycache__")), "__pycache__ directories must not be stored", errors)
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    root = root.resolve()
    errors = validate(root)
    print(f"root={root}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"validation=FAIL errors={len(errors)}")
        return 1
    print("validation=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
