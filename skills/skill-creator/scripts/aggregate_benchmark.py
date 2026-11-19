#!/usr/bin/env python3
"""
Aggregate individual run results into benchmark summary statistics.

Reads grading.json files from run directories and produces:
- run_summary with mean, stddev, min, max for each metric
- delta between with_skill and without_skill configurations

Usage:
    python aggregate_benchmark.py <benchmark_dir>

Example:
    python aggregate_benchmark.py benchmarks/2026-01-15T10-30-00/

The script supports two directory layouts:

    Workspace layout (from skill-creator iterations):
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/grading.json
        ├── with_skill/timing.json
        ├── without_skill/grading.json
        └── old_skill/grading.json

    Repeated-run layout:
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/run-1/grading.json
        └── without_skill/run-1/grading.json

    Legacy layout (with runs/ subdirectory):
    <benchmark_dir>/
    └── runs/
        └── eval-N/
            ├── with_skill/
            │   └── run-1/grading.json
            └── without_skill/
                └── run-1/grading.json
"""

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_EVALUATION_MODES = {"static_review", "dry_run", "full_test"}


def validate_evaluation_mode(value, source: Path) -> str:
    """Validate a declared mode; missing legacy values stay explicitly unlabeled."""
    if value is None:
        return "unlabeled"
    if not isinstance(value, str) or value not in ALLOWED_EVALUATION_MODES:
        allowed = ", ".join(sorted(ALLOWED_EVALUATION_MODES))
        raise ValueError(f"Invalid evaluation_mode {value!r} in {source}; expected one of: {allowed}")
    return value


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    # Support both layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif list(benchmark_dir.glob("eval-*")):
        search_dir = benchmark_dir
    else:
        print(f"No eval directories found in {benchmark_dir} or {benchmark_dir / 'runs'}")
        return {}

    results: dict[str, list] = {}

    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        metadata_path = eval_dir / "eval_metadata.json"
        eval_metadata = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as mf:
                    eval_metadata = json.load(mf)
                    eval_id = eval_metadata.get("eval_id", eval_idx)
            except (json.JSONDecodeError, OSError) as error:
                print(f"Warning: Could not read {metadata_path}: {error}")
                eval_id = eval_idx
        else:
            try:
                eval_id = int(eval_dir.name.split("-")[1])
            except ValueError:
                eval_id = eval_idx
        metadata_mode = validate_evaluation_mode(
            eval_metadata.get("evaluation_mode"),
            metadata_path,
        )

        # Discover config directories dynamically rather than hardcoding names
        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            config = config_dir.name
            if config not in results:
                results[config] = []

            run_dirs = sorted(config_dir.glob("run-*"))
            if not run_dirs and (config_dir / "grading.json").exists():
                run_dirs = [config_dir]
            if not run_dirs:
                continue

            for run_dir in run_dirs:
                if run_dir.name.startswith("run-"):
                    run_number = int(run_dir.name.split("-")[1])
                else:
                    run_number = 1
                grading_file = run_dir / "grading.json"

                if not grading_file.exists():
                    print(f"Warning: grading.json not found in {run_dir}")
                    continue

                try:
                    with open(grading_file, encoding="utf-8") as f:
                        grading = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON in {grading_file}: {e}")
                    continue

                grading_mode = validate_evaluation_mode(
                    grading.get("evaluation_mode"),
                    grading_file,
                )
                if grading_mode != "unlabeled" and metadata_mode != "unlabeled" and grading_mode != metadata_mode:
                    raise ValueError(
                        f"Conflicting evaluation_mode values for {run_dir}: "
                        f"metadata={metadata_mode!r}, grading={grading_mode!r}"
                    )
                evaluation_mode = grading_mode if grading_mode != "unlabeled" else metadata_mode

                # Extract metrics
                result = {
                    "eval_id": eval_id,
                    "run_number": run_number,
                    "evaluation_mode": evaluation_mode,
                    "pass_rate": grading.get("summary", {}).get("pass_rate", 0.0),
                    "passed": grading.get("summary", {}).get("passed", 0),
                    "failed": grading.get("summary", {}).get("failed", 0),
                    "total": grading.get("summary", {}).get("total", 0),
                }

                # Extract timing — check grading.json first, then sibling timing.json
                timing = grading.get("timing", {})
                result["time_seconds"] = timing.get("total_duration_seconds", 0.0)
                timing_file = run_dir / "timing.json"
                if result["time_seconds"] == 0.0 and timing_file.exists():
                    try:
                        with open(timing_file, encoding="utf-8") as tf:
                            timing_data = json.load(tf)
                        result["time_seconds"] = timing_data.get("total_duration_seconds", 0.0)
                        result["tokens"] = timing_data.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass

                # Extract metrics if available
                metrics = grading.get("execution_metrics", {})
                result["tool_calls"] = metrics.get("total_tool_calls", 0)
                if not result.get("tokens"):
                    result["tokens"] = metrics.get("output_chars", 0)
                result["errors"] = metrics.get("errors_encountered", 0)

                # Extract expectations — viewer requires fields: text, passed, evidence
                raw_expectations = grading.get("expectations", [])
                for exp in raw_expectations:
                    if "text" not in exp or "passed" not in exp:
                        print(f"Warning: expectation in {grading_file} missing required fields (text, passed, evidence): {exp}")
                result["expectations"] = raw_expectations

                # Extract notes from user_notes_summary
                notes_summary = grading.get("user_notes_summary", {})
                notes = []
                notes.extend(notes_summary.get("uncertainties", []))
                notes.extend(notes_summary.get("needs_review", []))
                notes.extend(notes_summary.get("workarounds", []))
                result["notes"] = notes

                results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta.
    """
    run_summary = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": {"mean": 0, "stddev": 0, "min": 0, "max": 0},
                "evidence_modes": []
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        tokens = [r.get("tokens", 0) for r in runs]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens),
            "evidence_modes": sorted({r["evaluation_mode"] for r in runs}),
        }

    # Calculate delta as with_skill minus the most relevant baseline.
    if "with_skill" in run_summary:
        primary_name = "with_skill"
        if "without_skill" in run_summary:
            baseline_name = "without_skill"
        elif "old_skill" in run_summary:
            baseline_name = "old_skill"
        else:
            baseline_name = next((c for c in configs if c != primary_name), None)
    else:
        primary_name = configs[0] if configs else None
        baseline_name = configs[1] if len(configs) >= 2 else None

    primary = run_summary.get(primary_name, {}) if primary_name else {}
    baseline = run_summary.get(baseline_name, {}) if baseline_name else {}

    delta_pass_rate = primary.get("pass_rate", {}).get("mean", 0) - baseline.get("pass_rate", {}).get("mean", 0)
    delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get("time_seconds", {}).get("mean", 0)
    delta_tokens = primary.get("tokens", {}).get("mean", 0) - baseline.get("tokens", {}).get("mean", 0)

    comparison_runs = []
    if primary_name:
        comparison_runs.extend(results.get(primary_name, []))
    if baseline_name:
        comparison_runs.extend(results.get(baseline_name, []))
    comparison_modes = sorted({run["evaluation_mode"] for run in comparison_runs})
    primary_counts = Counter(run["eval_id"] for run in results.get(primary_name, [])) if primary_name else Counter()
    baseline_counts = Counter(run["eval_id"] for run in results.get(baseline_name, [])) if baseline_name else Counter()
    primary_eval_ids = set(primary_counts)
    baseline_eval_ids = set(baseline_counts)
    evals_are_paired = bool(primary_eval_ids) and primary_eval_ids == baseline_eval_ids
    repeat_counts_are_balanced = evals_are_paired and primary_counts == baseline_counts
    claimable = (
        bool(primary_name and baseline_name and comparison_runs)
        and comparison_modes == ["full_test"]
        and repeat_counts_are_balanced
    )
    if not primary_name or not baseline_name:
        claim_reason = "A primary and baseline configuration are both required."
    elif not comparison_runs:
        claim_reason = "No comparison runs were loaded."
    elif not evals_are_paired:
        claim_reason = "Primary and baseline runs do not cover the same eval IDs."
    elif not repeat_counts_are_balanced:
        claim_reason = "Primary and baseline runs have different repeat counts per eval ID."
    elif not claimable:
        claim_reason = "Delta is descriptive only because every compared run is not full_test."
    else:
        claim_reason = "Every compared primary and baseline run is full_test."

    run_summary["delta"] = {
        "primary": primary_name or "",
        "baseline": baseline_name or "",
        "pass_rate": f"{delta_pass_rate:+.2f}",
        "time_seconds": f"{delta_time:+.1f}",
        "tokens": f"{delta_tokens:+.0f}",
        "evidence_modes": comparison_modes,
        "claimable": claimable,
        "claim_reason": claim_reason,
    }

    return run_summary


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array for benchmark.json
    runs = []
    for config in results:
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "configuration": config,
                "run_number": result["run_number"],
                "evaluation_mode": result["evaluation_mode"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens", 0),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0)
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))
    evidence_modes = sorted({run["evaluation_mode"] for run in runs})
    claim_status = "measured" if run_summary.get("delta", {}).get("claimable") else "unproven"
    run_counts = {
        config: dict(sorted(Counter(run["eval_id"] for run in config_runs).items()))
        for config, config_runs in results.items()
    }
    distinct_run_counts = sorted({count for counts in run_counts.values() for count in counts.values()})
    if not distinct_run_counts:
        runs_per_configuration = 0
    elif len(distinct_run_counts) == 1:
        runs_per_configuration = distinct_run_counts[0]
    else:
        runs_per_configuration = "varied"

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": runs_per_configuration,
            "run_counts": run_counts,
            "evidence_modes": evidence_modes,
            "claim_status": claim_status,
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]
    config_a = configs[0] if len(configs) >= 1 else "config_a"
    config_b = configs[1] if len(configs) >= 2 else "config_b"
    label_a = config_a.replace("_", " ").title()
    label_b = config_b.replace("_", " ").title()

    run_count = metadata["runs_per_configuration"]
    run_count_text = (
        f"{run_count} runs each per configuration"
        if isinstance(run_count, int)
        else "varied run counts"
    )

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({run_count_text})",
        f"**Evidence modes**: {', '.join(metadata.get('evidence_modes', [])) or 'none'}",
        f"**Claim status**: {metadata.get('claim_status', 'unproven')}",
        "",
        "## Summary",
        "",
        f"| Metric | {label_a} | {label_b} | Delta |",
        "|--------|------------|---------------|-------|",
    ]

    a_summary = run_summary.get(config_a, {})
    b_summary = run_summary.get(config_b, {})
    delta = run_summary.get("delta", {})

    # Format pass rate
    a_pr = a_summary.get("pass_rate", {})
    b_pr = b_summary.get("pass_rate", {})
    lines.append(f"| Pass Rate | {a_pr.get('mean', 0)*100:.0f}% ± {a_pr.get('stddev', 0)*100:.0f}% | {b_pr.get('mean', 0)*100:.0f}% ± {b_pr.get('stddev', 0)*100:.0f}% | {delta.get('pass_rate', '—')} |")

    # Format time
    a_time = a_summary.get("time_seconds", {})
    b_time = b_summary.get("time_seconds", {})
    lines.append(f"| Time | {a_time.get('mean', 0):.1f}s ± {a_time.get('stddev', 0):.1f}s | {b_time.get('mean', 0):.1f}s ± {b_time.get('stddev', 0):.1f}s | {delta.get('time_seconds', '—')}s |")

    # Format tokens
    a_tokens = a_summary.get("tokens", {})
    b_tokens = b_summary.get("tokens", {})
    lines.append(f"| Tokens | {a_tokens.get('mean', 0):.0f} ± {a_tokens.get('stddev', 0):.0f} | {b_tokens.get('mean', 0):.0f} ± {b_tokens.get('stddev', 0):.0f} | {delta.get('tokens', '—')} |")

    if not delta.get("claimable", False):
        lines.extend(["", f"**Unproven delta**: {delta.get('claim_reason', 'Full-test evidence is incomplete.')}"])

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark run results into summary statistics"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="Path to the benchmark directory"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="Name of the skill being benchmarked"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="Path to the skill being benchmarked"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"Directory not found: {args.benchmark_dir}")
        sys.exit(1)

    # Generate benchmark
    try:
        benchmark = generate_benchmark(args.benchmark_dir, args.skill_name, args.skill_path)
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, indent=2)
    print(f"Generated: {output_json}")

    # Write benchmark.md
    markdown = generate_markdown(benchmark)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Generated: {output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print(f"\nSummary:")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = config.replace("_", " ").title()
        print(f"  {label}: {pr*100:.1f}% pass rate")
    print(f"  Delta:         {delta.get('pass_rate', '—')}")
    print(f"  Claim status:  {benchmark['metadata'].get('claim_status', 'unproven')}")


if __name__ == "__main__":
    main()
