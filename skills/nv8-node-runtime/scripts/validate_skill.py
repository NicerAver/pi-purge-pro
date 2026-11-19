#!/usr/bin/env python3
"""Validate the nv8-node-runtime skill: structure, frontmatter, and referenced paths."""

from __future__ import annotations

import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
PATH_RE = re.compile(r"`((?:references|scripts)/[A-Za-z0-9_./-]+)`")

REQUIRED_SECTIONS = [
    "## 唯一职责",
    "## 直接路由",
    "## 准入条件",
    "## 硬约束",
    "## 装配路径选择",
    "## 生成流程",
    "## Maintenance Check",
]

# Facts measured on a real run; the skill must keep stating them or they get lost.
REQUIRED_FACTS = [
    ("20", "measured ~20s first EdgeSandbox.create()"),
    ("timeoutMs", "timeout budget guidance"),
    (".value", "evaluate() result envelope unwrapping"),
    ("Node 22", "fingerprint-sensitive Node floor"),
    ("Node 24", "window enumeration-order parity"),
    ("离线回放", "offline replay default"),
    ("createNv8", "in-process entry (no child-process boundary)"),
    ("EdgeSandbox", "primary protocol-recovery entry"),
    ("createAgentSession", "agent session entry"),
]

# Sibling skills this one must route away to, and the trigger words for that.
ROUTE_BOUNDARIES = [
    ("iv8-web-reverse", "Python + iv8"),
    ("trace", "entry location / AST"),
    ("captcha-reverse", "complete CAPTCHA protocol"),
    ("akamai-protocol-reverse", "Akamai end-to-end"),
    ("wechat-miniapp-reverse", "WMPF runtime"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple `key: value` frontmatter, including YAML folded/literal scalars.

    The skills in this suite write long values as `description: >-` + indented
    continuation lines. A naive line splitter drops those lines and reports the
    description as a two-character string, so continuation lines are folded back
    into their key here.
    """
    match = FRONTMATTER_RE.search(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in match.group("body").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() and current_key is not None:
            # Continuation of the previous key's folded/literal scalar.
            fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        # `>-`, `>`, `|`, `|-` introduce a multi-line scalar: start it empty.
        fields[current_key] = "" if value in {">-", ">", "|", "|-", "|+"} else value
    # Normalise the folded whitespace so keyword checks are not spacing-sensitive.
    return {k: " ".join(v.split()) for k, v in fields.items()}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill_path = root / "SKILL.md"

    if not skill_path.is_file():
        return [f"missing {skill_path}"]
    text = read_text(skill_path)

    # --- frontmatter ---
    fields = parse_frontmatter(text)
    if not fields:
        errors.append("SKILL.md has no YAML frontmatter")
    name = fields.get("name", "")
    if name != "nv8-node-runtime":
        errors.append(f'frontmatter name must be "nv8-node-runtime", got "{name}"')
    desc = fields.get("description", "")
    if len(desc) < 200:
        errors.append(f"description too short ({len(desc)} chars); triggers will be unreliable")
    for kw in ["NV8", "EdgeSandbox", "Node", "采集"]:
        if kw not in desc:
            errors.append(f'description missing trigger keyword "{kw}"')

    # --- required sections ---
    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f'missing section "{section}"')

    # --- measured facts must survive edits ---
    for needle, why in REQUIRED_FACTS:
        if needle not in text:
            errors.append(f'body lost required fact "{needle}" ({why})')

    # --- routing boundaries must name the siblings ---
    shared = root.parent / "_shared" / "js-reverse-workflow.md"
    for sibling, why in ROUTE_BOUNDARIES:
        if sibling not in text and not shared.is_file():
            errors.append(f'route boundary to "{sibling}" missing ({why})')
    if not shared.is_file():
        errors.append(f"shared dispatch contract not found at {shared}")

    # --- referenced paths must exist ---
    for rel in sorted(set(PATH_RE.findall(text))):
        if not (root / rel).exists():
            errors.append(f"SKILL.md references missing path: {rel}")

    # --- every reference doc must be reachable from SKILL.md ---
    ref_dir = root / "references"
    if not ref_dir.is_dir():
        errors.append("missing references/ directory")
    else:
        referenced = set(PATH_RE.findall(text))
        for doc in sorted(ref_dir.glob("*.md")):
            if f"references/{doc.name}" not in referenced:
                errors.append(f"references/{doc.name} is never referenced from SKILL.md")

    # --- scripts referenced must exist and parse ---
    script_dir = root / "scripts"
    if not script_dir.is_dir():
        errors.append("missing scripts/ directory")
    else:
        for script in sorted(script_dir.glob("*.mjs")):
            body = read_text(script)
            if "import { EdgeSandbox }" in body and "limits" not in body:
                errors.append(f"{script.name} omits the limits/timeout guidance")
            if "await sandbox.close()" not in body and "sandbox.close()" not in body:
                errors.append(f"{script.name} never closes the sandbox")

    return errors


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    errors = validate(root)
    if errors:
        print(f"FAIL ({len(errors)} issue(s)) in {root}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {root} passes all structural, trigger, fact and reference checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
