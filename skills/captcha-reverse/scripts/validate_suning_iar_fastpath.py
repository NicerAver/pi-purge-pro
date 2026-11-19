#!/usr/bin/env python3
"""Validate the Suning IAR fast-path reference and runtime asset."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    reference_path = root / "references" / "suning-iar-jigsaw-workflow.md"
    asset_path = root / "assets" / "suning-iar" / "iv8-runtime-patch.js"
    errors: list[str] = []

    require(reference_path.is_file(), "missing Suning workflow reference", errors)
    require(asset_path.is_file(), "missing Suning iv8 runtime asset", errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    reference = reference_path.read_text(encoding="utf-8-sig")
    asset = asset_path.read_text(encoding="utf-8-sig")

    reference_markers = (
        "assets/suning-iar/iv8-runtime-patch.js",
        "SnCaptcha.init",
        'time_mode="system"',
        "setAttribute(\"src\"",
        "EventTarget",
        "element.style.top",
        "piece_left ~= gap_x",
        "resp_code",
    )
    for marker in reference_markers:
        require(marker in reference, f"reference missing marker: {marker}", errors)

    asset_markers = (
        "pyLoadScript",
        "Node.prototype.appendChild",
        "Node.prototype.insertBefore",
        "HTMLImageElement.prototype",
        'setAttribute = __iv8__.wrapNative',
        "CanvasRenderingContext2D.prototype",
        "listenerTargets",
        "getBoundingClientRect",
        "/iar_prd_jigsaw/",
    )
    for marker in asset_markers:
        require(marker in asset, f"runtime asset missing marker: {marker}", errors)

    secret_patterns = (
        r"\b1[3-9]\d{9}\b",
        r"ticket\s*[:=]\s*['\"][A-Za-z0-9_-]{40,}",
        r"token\s*[:=]\s*['\"][A-Za-z0-9_-]{20,}",
        r"Cookie\s*:",
    )
    for pattern in secret_patterns:
        require(not re.search(pattern, asset, re.I), f"runtime asset matches secret pattern: {pattern}", errors)

    node_binary = shutil.which("node")
    if node_binary:
        node = subprocess.run(
            [node_binary, "--check", str(asset_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        require(node.returncode == 0, f"node --check failed: {node.stderr.strip()}", errors)
    else:
        print("node-check=SKIP (node unavailable)")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"validation=FAIL errors={len(errors)}")
        return 1
    print(f"root={root}")
    print("validation=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
