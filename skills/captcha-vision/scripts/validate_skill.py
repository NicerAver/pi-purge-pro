#!/usr/bin/env python3
"""Validate CAPTCHA vision specialist boundaries."""

from __future__ import annotations

import re
import sys
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)


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
    require(fields.get("name") == "captcha-vision", "frontmatter name mismatch", errors)

    required_positive = (
        "训练识别模型",
        "YOLOv8",
        "Chinese-CLIP",
        "server oracle",
        "ONNX",
        "fresh challenge",
    )
    for literal in required_positive:
        require(literal.lower() in lower, f"missing positive trigger: {literal}", errors)

    required_negative = (
        "captcha-reverse",
        "恢复 `w`",
        "PoW",
        "GCT",
        "AES/RSA",
        "滑块距离",
        "无感",
        "消消乐",
        "五子棋",
    )
    for literal in required_negative:
        require(literal.lower() in lower, f"missing negative boundary: {literal}", errors)

    require("真实 `/verify` 响应统计" in skill, "fresh verify acceptance invariant missing", errors)
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
