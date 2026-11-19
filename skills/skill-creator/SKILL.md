---
name: skill-creator
description: >-
  Create, revise, evaluate, optimize, score, and package OpenCode skills. Use when the user wants a new skill, trigger-boundary cleanup, evals, benchmark comparison, overlap review, 9-dimension quality scoring, validation-gated iteration, Darwin-style skill optimization, or a full skill-set audit. Trigger on requests such as “turn this workflow into a skill”, “improve/test/score this skill”, “optimize the description”, “add evals”, “skill quality review”, “Darwin skill optimization”, or “check all current skills and micro-tune them”. Do not trigger when the user only wants to apply a domain skill, or when editing OpenCode config, agents, plugins, MCP servers, or permissions without changing a skill definition.
compatibility: "建议具备 Python 3；若要做自动评测，额外需要本地脚本执行能力，浏览器调试与子代理能力为可选增强。"
argument-hint: "[skill 名称或待处理问题]"
---

# Skill Creator

A workflow for creating, revising, evaluating, optimizing, and packaging OpenCode skills.

Prefer the smallest skill that reliably triggers and gives clear execution guidance. When reviewing an existing skill set, check neighboring skills for overlap and tighten trigger boundaries together rather than editing one skill in isolation.

Do not use this skill when the user is applying an existing skill to a normal task, such as reversing a website or writing a hook. Use it only when the object of work is a skill definition, description, eval, packaged resource, or trigger boundary.

If the user is editing `opencode.json`, agents, plugins, MCP servers, or permission rules and is not changing a skill, use `customize-opencode` instead.

`customize-opencode` is an OpenCode built-in skill, so it is intentionally not a top-level directory under this local skill repository.

## Core Loop

1. Capture the skill's intent and success criteria.
2. Draft or revise `SKILL.md` and any bundled resources.
3. Run `scripts/quick_validate.py <skill-path>`, parse changed JSON, and check referenced relative paths. For whole-suite changes, run `scripts/validate_all_skills.py <skills-root>`; for real-model routing comparison, run `scripts/run_suite_routing_eval.py evals/reverse-suite-routing-evals.json`; for stage-gate output checks, run `scripts/run_output_contract_eval.py evals/reverse-suite-output-contract-evals.json`.
4. Add realistic eval prompts and, where useful, objective assertions.
5. Run the skill against test prompts and compare against a baseline when feasible.
6. Review qualitative outputs and quantitative benchmark data with the user.
7. Improve the skill based on feedback and rerun.
8. Package the final skill when the user is satisfied.

Use the shortest loop that proves the requested outcome. If the user asks for a lightweight cleanup, edit only the target `SKILL.md` and nearby trigger boundaries. If the user asks whether a skill helps, run the evaluation workflow.

For optimization or scoring, first establish a baseline and read `references/optimization-ratchet.md`. Static rubric scores diagnose structure; only validated task outputs can prove effect.

When auditing this reverse-engineering skill suite and the user explicitly asks to output only a stage gate, use `_shared/js-reverse-workflow.md` Stage-Gate Output fields: `MODE`, `OWNER`, `NEXT_GATE`, `REQUIRED_EVIDENCE`, and `DO_NOT_USE`. Do not run benchmarks or mutate files from a stage-gate-only prompt.

## Checkpoints

Use explicit checkpoints before actions that change files, spend significant runtime, or publish packaged artifacts.

1. 🔴 CHECKPOINT: before creating a new skill directory or overwriting an existing `SKILL.md`, state the target path and intended change.
2. 🔴 CHECKPOINT: before running benchmarks or generated eval loops, show the prompt set and pass/fail criteria.
3. 🔴 CHECKPOINT: before applying an optimized frontmatter `description`, show the before/after trigger boundary and expected tradeoff.
4. 🔴 CHECKPOINT: before packaging or installing a skill, show included files and excluded local artifacts.
5. 🔴 CHECKPOINT: before creating a branch, commit, stash, or revert for an optimization loop, show the exact Git action and obtain explicit approval. Git is optional; never mutate history automatically.

## Failure Modes

| Trigger | Action | Fallback |
|---|---|---|
| Target skill path is ambiguous | Ask for the exact skill name or directory before editing | If the user wants a new skill, create a draft plan without touching files |
| Nearby skills overlap | Compare frontmatter descriptions and trigger boundaries first | Tighten handoff rules in all affected skills before adding new capability |
| Eval runner or fresh judge is unavailable | Mark same-context simulation `static_review` or `exploratory_review` | Use `dry_run` only with a fresh independent judge; never claim benchmark improvement |
| Baseline output is missing | Generate the baseline before scoring the revised skill | If baseline cannot run, stop at static review and record the blocker |
| Generated description improves trigger rate but steals adjacent tasks | Reject the description and add near-miss negative evals | Keep the current description until a safer variant is tested |
| Packaging validation fails | Fix only the reported package/schema issue | If validation still fails, leave files unpackaged and report exact errors |
| User asks to edit OpenCode config instead of a skill | Stop this skill workflow | Use `customize-opencode` for config, agents, plugins, MCP servers, or permissions |
| Static score is used as proof of improvement | Mark the result `static_review` or `dry_run` | Require with-skill/baseline outputs before claiming measured improvement |
| Independent judges disagree | Treat the iteration as unproven | Keep the baseline and add a discriminating eval |
| Optimization gain is marginal twice in a row | Stop the loop | Present the current best instead of adding rubric-shaped prose |
| Git action was not explicitly approved | Do not create branches, commits, stashes, or reverts | Use snapshots in the evaluation workspace |

## Communicating With The User

Match the user's technical level.

1. Use terms like evaluation, benchmark, JSON, and assertion when the user appears comfortable with them.
2. Briefly define terms when the user may not know them.
3. For lightweight requests, give concise findings and edits.
4. For evaluation-heavy requests, explain what will be tested and how the user can review results.

## Creating Or Revising A Skill

### Capture Intent

Extract what you can from the current conversation before asking questions.

Clarify only what is needed:

1. What should this skill enable OpenCode to do?
2. When should this skill trigger, and when should it not?
3. What output should a successful run produce?
4. Should this skill include evals, scripts, templates, references, or assets?

If the answer changes the skill's core purpose rather than its instructions, stop and confirm the new scope before editing.

### Research Nearby Skills

Check available skills and adjacent trigger areas before editing.

Common overlaps:

1. Browser hook injection vs crypto entry tracing.
2. Crypto entry tracing vs Node.js environment patching.
3. AST deobfuscation vs runtime debugging.
4. General workflow guidance vs a narrow task-specific skill.

When overlap exists, tighten all relevant surfaces:

1. Frontmatter `description`.
2. Trigger boundary section.
3. Handoff guidance.
4. Near-miss negative eval prompts.

### Write `SKILL.md`

Required frontmatter:

1. `name`: kebab-case skill identifier.
2. `description`: primary trigger signal; include concrete trigger contexts and nearby non-trigger cases.

Optional frontmatter:

1. `compatibility`.
2. `argument-hint`.
3. `allowed-tools`.
4. `metadata`.
5. `version`.
6. `user-invocable`.

Recommended structure:

```text
skill-name/
├── SKILL.md
├── scripts/       # deterministic helpers or templates
├── references/    # detailed docs loaded as needed
├── assets/        # templates, icons, HTML review pages
└── evals/         # local test prompts, usually excluded from package output
```

Keep `SKILL.md` focused. If it approaches 500 lines, move long procedures to `references/` and leave clear pointers.

## Writing Guidance

1. Put trigger guidance in the frontmatter `description`, not only in the body.
2. Use imperative instructions.
3. Explain why important constraints exist instead of relying only on rigid MUST/NEVER wording.
4. Include examples when output format matters.
5. Bundle scripts only for repeatable work that future runs would otherwise recreate.
6. Do not include malware, credential exfiltration, misleading behavior, or surprising capabilities.
7. If a skill uses `skill_checkpoint`, tell it to store engineering facts only in `evidence`, `hardConstraints`, `nextStep`, and `artifacts`; treat `hardConstraints` as correctness/acceptance notes, never as a permission, tool, event, browser, or network denylist.

## Testing And Evaluation

Use `references/evaluation-workflow.md` when the user asks to test, benchmark, add evals, compare iterations, or prove that a skill helps.

🔴 CHECKPOINT: show the eval prompts, baseline plan, and scoring method before running multi-prompt benchmarks.

Short version:

1. Save realistic prompts to the evals/evals.json file in the target skill.
2. Run with-skill and baseline outputs when feasible.
3. Draft objective assertions while runs execute.
4. Save timing and grading data.
5. Aggregate with `scripts/aggregate_benchmark.py`.
6. Present qualitative outputs and benchmark results for user review.

Use `agents/grader.md`, `agents/analyzer.md`, and `agents/comparator.md` when grading, analyzing benchmarks, or doing blind comparisons.

## Optimization And Quality Scoring

Use `references/optimization-ratchet.md` when the user asks to optimize, score, audit, Darwin-test, or repeatedly improve one or more skills.

Short version:

1. Freeze the original description, files, eval prompts, and outputs as the baseline.
2. Score structure only as diagnosis; mark the evaluation mode explicitly.
3. Choose one measurable hypothesis, including neighboring trigger boundaries.
4. Change the smallest owning surface.
5. Rerun the same prompts and use an independent judge or objective assertions.
6. Keep the change only when effect improves and no adjacent task is stolen.
7. Stop after two marginal iterations or one regression.

Do not optimize every rubric dimension by adding text. Removal, routing, resource extraction, eval correction, and retirement are valid improvements.

For a full skill-set audit, check active `SKILL.md` discovery, duplicate names, frontmatter validity, overlap, missing positive/near-miss evals, dangling relative or skill-name references, stale retired entries, package exclusions, local secrets, and generated artifacts. Keep the audit read-only unless the user asks for fixes.

## Description Optimization

Use `references/description-optimization.md` when the user asks to improve trigger accuracy, optimize a description, add trigger evals, or reduce skill overlap.

Use `references/trigger-eval-quickcheck.md` when the user only wants a lightweight review of existing trigger evals without running the full optimization loop.

Short version:

1. Create about 20 realistic trigger eval queries.
2. Include both should-trigger and near-miss should-not-trigger prompts.
3. Let the user review the eval set with `assets/eval_review.html` when possible.
4. Run `scripts/run_loop.py` if the required CLI dependencies are available.
5. Apply `best_description` and report before/after scores.

## Environment Adaptation

Use `references/environment-adaptation.md` when the environment is limited, headless, remote, or when packaging/updating installed skills.

Key rules:

1. In limited environments, run test prompts yourself and use inline review.
2. In headless environments, prefer static artifacts or conversation review over local browser servers.
3. Preserve the existing skill name when updating a skill.
4. Package with `scripts/package_skill.py` when ready.

## Improvement Heuristics

When revising a skill after feedback:

1. Generalize from feedback rather than overfitting to one prompt.
2. Remove instructions that cause wasted work or excessive token use.
3. Split repeated helper code into `scripts/` if multiple evals recreate it.
4. Move long background material to `references/`.
5. Strengthen trigger boundaries when a skill steals work from a neighboring skill.
6. Add near-miss evals for every boundary bug you fix.

## Packaging

When the skill is ready:

```bash
python scripts/package_skill.py <path/to/skill-folder> [output-directory]
```

The packager validates the skill and excludes local build artifacts such as `__pycache__` and `.pyc` files.

## Reference Files

1. `references/evaluation-workflow.md`: full eval, benchmark, grading, and review loop.
2. `references/description-optimization.md`: trigger eval generation and description optimization loop.
3. `references/environment-adaptation.md`: limited/headless environment handling and packaging notes.
4. `references/trigger-eval-quickcheck.md`: lightweight trigger eval coverage review.
5. `references/schemas.md`: JSON schemas for eval and benchmark artifacts.
6. `references/optimization-ratchet.md`: 9-dimension diagnosis, independent judging, validation ratchet, and early stopping.
7. `agents/grader.md`: grading assertions against outputs.
8. `agents/analyzer.md`: analyzing benchmark results.
9. `agents/comparator.md`: blind A/B comparison.
