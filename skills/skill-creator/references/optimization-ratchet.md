# Skill Optimization Ratchet

Use this workflow for requests such as optimize, score, audit, Darwin, compare iterations, or improve all skills. The goal is measurable task quality and clean routing, not a larger `SKILL.md`.

## Evaluation Modes

Always label the result:

| Mode | Evidence | Allowed claim |
|---|---|---|
| `static_review` | Files and rubric only | Structural diagnosis |
| `dry_run` | Prompt simulation by independent reviewers | Qualitative boundary confidence |
| `full_test` | Executed with-skill and baseline outputs | Measured task effect |

Same-context prompt simulation is `exploratory_review`, not `dry_run`. Never report a static, exploratory, or dry-run score as benchmark improvement.

## Nine-Dimension Diagnostic Rubric

The weights total 100 and prioritize executable behavior:

| Dimension | Weight | What to inspect |
|---|---:|---|
| Frontmatter quality | 7 | Name, concrete positive triggers, nearby exclusions, length |
| Workflow clarity | 12 | Ordered steps, inputs, outputs, exit conditions |
| Failure modes | 12 | Explicit trigger -> action -> fallback branches |
| Checkpoints | 6 | Confirmation before destructive, expensive, private, or publishing actions |
| Executable specificity | 17 | Paths, commands, schemas, fixtures, objective checks |
| Resource integration | 4 | Existing scripts/references are reachable and used correctly |
| Architecture | 12 | Focused entry, minimal duplication, clear ownership and handoff |
| Measured effect | 23 | With-skill vs baseline task output, regressions, time/token tradeoff |
| Negative examples | 7 | Near misses, anti-patterns, unsafe actions, neighboring owners |

Rate each measured dimension with one integer:

| Rating | Anchor |
|---:|---|
| 0 | Missing, contradicted, unsafe, or consistently harmful |
| 1 | Major gaps; the intended behavior usually cannot be completed |
| 2 | Partial; the happy path exists but important branches or evidence are missing |
| 3 | Strong; minor gaps remain but normal tasks are handled consistently |
| 4 | Complete for the stated scope, with direct evidence and regression coverage |

For dimension `i`, calculate `weighted_i = weight_i * rating_i / 4`. Do not use fractional ratings. Record evidence and file/line references for every rating.

Score dimensions 1-7 and 9 from static evidence. Their maximum structural subtotal is 77. Report both `subtotal/77` and optional normalized structural percentage `subtotal / 77 * 100`; do not add the missing 23 points. Dimension 8 requires executed with-skill and baseline outputs; without them record `unmeasured`, not an invented number. A 0-100 total is valid only when all nine dimensions are measured.

## Baseline Gate

Before editing an existing skill:

1. Save the original `SKILL.md`, relevant resources, description, and eval set to an evaluation workspace.
2. Record neighboring descriptions and at least three near-miss prompts.
3. Run or simulate the current version first.
4. Define pass/fail assertions and the one behavior expected to improve.
5. Show prompts, assertions, runtime/cost plan, and scoring method to the user.

If the original output is unavailable, stop at static review and label that limitation.

## Iteration Ratchet

Each iteration changes one measurable hypothesis:

1. Diagnose the lowest-value failure, not merely the lowest rubric number.
2. Prefer deletion, routing, moving detail to references, fixing evals, or retiring overlap before adding prose.
3. Change the smallest owning files, including neighboring descriptions when required.
4. Rerun the same prompt set.
5. Grade with objective assertions where possible and at least one independent reviewer for subjective output.
6. Compare task completion, trigger accuracy, regressions, time, tokens, and output complexity.

Keep an iteration only when:

- the target behavior improves
- no critical assertion regresses
- near-miss ownership remains correct
- runtime and maintenance cost stay acceptable

Otherwise keep the baseline snapshot. Do not use `git reset --hard`.

## Early Stop

Stop when any condition holds:

1. One iteration regresses a critical behavior.
2. Two consecutive accepted iterations improve the selected metric by less than 2 percentage points or an equivalently small qualitative delta.
3. The next proposal only adds rubric-shaped wording without a failing eval.
4. More than 30% of effect evidence is dry-run and no full test can be run.
5. Independent judges disagree and no discriminating eval resolves the difference.

Present the current best and remaining unmeasured risks instead of forcing a fixed number of rounds.

## Independent Review

Do not let the same context both author and conclusively grade a subjective change. Use one of:

1. an objective test script
2. a fresh grader agent using `agents/grader.md`
3. two independent dry-run judges for subjective output, treating disagreement as failure
4. blind old-vs-new comparison using `agents/comparator.md`

The judge must receive the prompt, assertions, artifacts, and evaluation mode. It should not receive a preferred answer.

## Runtime Neutrality

Skills should describe capabilities, not assume one branded agent runtime, unless the skill is intentionally runtime-specific. Flag:

- hard-coded `.claude/skills` or another runtime-only install path
- instructions that require one tool name without a fallback or compatibility note
- absolute paths from an author's machine
- package steps that include `.git`, local config, logs, caches, credentials, or generated outputs

Runtime-specific tool instructions are valid when they are the skill's explicit purpose.

## Git Is Optional

Workspace snapshots are the default rollback mechanism. Before any branch, commit, stash, or revert:

🔴 CHECKPOINT: show repository root, current status, intended files, exact Git command, rollback path, and whether unrelated changes exist. Continue only after explicit user approval.

Never automatically commit each iteration, never amend without request, and never use destructive reset/checkout to implement the ratchet.

## Reporting

Report:

1. evaluation mode and prompts
2. baseline and current evidence
3. accepted and rejected hypotheses
4. trigger and task-output regressions
5. structural subtotal and unmeasured dimensions
6. files changed and validation commands
7. early-stop reason and remaining risk

Visual cards and screenshots are optional presentation artifacts, never part of the quality gate.
