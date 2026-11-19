#!/usr/bin/env python3
"""Validate Akamai specialist trigger and handoff boundaries."""

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
    require(fields.get("name") == "akamai-protocol-reverse", "frontmatter name mismatch", errors)

    required_literals = (
        "_abck",
        "bm_sz",
        "ak_bmsc",
        "sensor_data",
        "/akam/13/pixel_",
        "independent network/script/cookie-transition/transport corroboration",
        "cookie name alone",
        "generic sign tracing",
        "final browser automation",
        "browser-free python collector",
        "trace",
        "captcha-reverse",
        "iv8-web-reverse",
    )
    for literal in required_literals:
        require(literal in lower, f"missing boundary literal: {literal}", errors)

    require(
        "at least two independent evidence surfaces" in lower or "一个独立佐证面" in skill,
        "Akamai handoff must require corroborating evidence",
        errors,
    )
    require(
        "final browser dependency: rejected" in lower,
        "startup gate must reject final browser dependency",
        errors,
    )
    require(
        "camoufox-js-reverse" not in lower and "spider-king" not in lower,
        "stale retired skill route remains",
        errors,
    )

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
