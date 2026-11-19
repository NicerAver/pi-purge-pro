#!/usr/bin/env python3
"""Validate CAPTCHA protocol specialist routing and hygiene."""

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
    reference_text = "\n".join(read_text(path) for path in sorted((root / "references").glob("*.md")))
    combined = f"{skill}\n{reference_text}"
    lower = combined.lower()
    fields = parse_frontmatter(skill)
    require(fields.get("name") == "captcha-reverse", "frontmatter name mismatch", errors)

    required_boundaries = (
        "普通 OCR",
        "泛化定位 sign",
        "DevTools hook",
        "通用 Node.js 补环境",
        "Python + iv8",
        "captcha-vision",
        "trace",
        "iv8-web-reverse",
    )
    for literal in required_boundaries:
        require(literal.lower() in lower, f"missing routing boundary: {literal}", errors)

    required_families = (
        "GT3",
        "GT4",
        "腾讯",
        "网易易盾",
        "数美",
        "云片",
        "360 天御",
        "百度 Passport",
        "苏宁 IAR",
        "阿里云 Captcha V2",
        "阿里云 Captcha V3",
        "字节系 VerifyCenter",
    )
    for literal in required_families:
        require(literal.lower() in lower, f"missing family route: {literal}", errors)

    require("同一轮" in combined and "verify/check" in lower, "same-round verify/check invariant missing", errors)
    require("服务端" in combined and "响应" in combined, "server response acceptance invariant missing", errors)
    require("浏览器自动化只作为取证手段" in combined, "browser automation final-delivery boundary missing", errors)
    require(
        "skill_checkpoint" in combined and "工程事实" in combined and "缺哪个端点或字段" in combined,
        "checkpoint field language rule missing",
        errors,
    )
    require(
        "camoufox-js-reverse" not in lower and "captcha-slide-reverse" not in lower,
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

    pyc_files = list(root.rglob("*.pyc"))
    pycache_dirs = list(root.rglob("__pycache__"))
    require(not pyc_files, "generated .pyc files must not be stored", errors)
    require(not pycache_dirs, "__pycache__ directories must not be stored", errors)
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
