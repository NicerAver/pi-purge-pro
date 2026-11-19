# pi-purge-pro

[English](README.md) | [中文](README.zh-CN.md)

> **This project is a fork of [pi-purge](https://github.com/ZiChuanLan/pi-purge) by [@ZiChuanLan](https://github.com/ZiChuanLan), modified from it.** The original purge switch, its three modes, and session-scoped state are kept as-is. From 1.0.0, [@NicerAver](https://github.com/NicerAver) added reverse-engineering skill routing plus the bundled skill bodies, and renamed the package to `pi-purge-pro`. The original MIT license and attribution are preserved — see [LICENSE](LICENSE).

A [pi](https://github.com/earendil-works/pi-coding-agent) extension for system-prompt experiments: `/purge` switches which system prompt a session runs with — pi's stock prompt, a trimmed variant, or only a persona prompt.

It is meant for prompt engineering work: comparing how the same request behaves when the harness prompt is present, trimmed, or absent; regression-testing your own instructions; and studying instruction-following and prompt-injection robustness under controlled conditions.

With it off, nothing changes — no prompt rewrite, no disk reads. pi behaves exactly as if the extension were not installed.

## Install

```bash
pi install npm:pi-purge-pro
```

Then, inside a session:

```text
/purge
```

That is all. A default persona ships inside the package; no prompt file is needed.

To use your own prompt instead:

```text
/purge source C:/prompts/my-instructions.md
/purge mode replace
/purge on
```

`/purge source embedded` switches back to the bundled persona.

## Commands

| Command | Effect |
| --- | --- |
| `/purge` | Toggle on/off for this session |
| `/purge on` / `off` | Enable or disable the rewrite |
| `/purge status` | Mode, prompt source, loaded size, and what the previous turn actually changed |
| `/purge mode append\|replace\|strict` | Switch composition mode (default `strict`) |
| `/purge source <path\|embedded>` | Change the prompt file, or go back to the bundled persona; a failed switch rolls back |
| `/purge reload` | Re-read an external prompt file after editing it |
| `/purge skills` | Reverse-engineering skill routing status: switch, root, skill count, whether RE is locked |
| `/purge skills on\|off` | Toggle skill routing explicitly (on by default with `/purge`) |
| `/purge skills <path>` | Change the skill root, rolling back on failure; defaults to the bundled `skills/`, overridable with `PI_PURGE_SKILLS` or a direct path |
| `/purge skills list` | List discovered skills with their frontmatter descriptions |
| `/purge skills reload` | Rescan the root after adding a skill |

## Modes

| Mode | System prompt sent to the model | Use it when |
| --- | --- | --- |
| `append` | Your prompt prepended to pi's prompt, unchanged. | You want a control run: baseline behavior plus your instructions on top. |
| `replace` | Your prompt, then pi's prompt with its built-in assistant identity line and bundled documentation section removed. Tool list, guidelines, and project context stay. | You want to measure the effect of the harness framing without losing tool context. |
| `strict` | Your prompt plus `Current working directory: …` only. | You want to isolate your instructions as a single variable. This is the default. |

`replace` finds both sections by exact wording. If a pi update rewords them, it leaves the prompt intact rather than cutting the wrong text — `/purge status` then reports `身份段 未匹配` (identity line not found) and behavior falls back to `append`. `strict` does no matching at all, so it behaves the same across pi versions.

Tool schemas are passed through the API `tools` parameter rather than the system prompt, so tools keep working in every mode, including `strict`.

## Reverse-engineering skill routing

While `/purge` is on, a prompt classified as reverse-engineering work (`逆向`, `脱壳`, `抓包`, `协议还原`, `验证码`, `小程序`, `apk`, `iv8`, `collector`, and similar triggers) gets a **skill routing block** appended to the end of the system prompt:

- It states `SKILL_ROOT` and the mandatory order: pick the family → read `SKILL_ROOT/<skill>/SKILL.md` in full → follow its gates → read `references/`, run `scripts/` as needed → deliver artifacts plus verification evidence.
- The root defaults to the bundled `skills/` (shipped with the package, so it works wherever it is installed). `PI_PURGE_SKILLS` or `/purge skills <path>` points it elsewhere. `/purge skills status` shows which one is live.
- It carries a curated routing table: `trace` (coordinator for unknown families, layered chains, deobfuscation, env patching), `iv8-web-reverse`, `nv8-node-runtime`, `akamai-protocol-reverse`, `captcha-reverse`, `captcha-vision`, `wechat-miniapp-reverse`, `reverse-engineer-anything`, `skill-creator`.
- Skill directories found on disk but not in the table are appended automatically, so adding a skill needs no code change.
- A hit locks the session: follow-ups like “continue” keep the block. The block tells the model to ignore it when the request is not RE work.

Why it exists: `strict` mode drops pi's entire prompt, including pi's own skills list. The routing therefore cannot come from the harness and has to be injected here.

Cost when it does not apply: no RE trigger, `/purge skills off`, or `/purge off` add nothing to the prompt and read nothing from disk.

## Session scope and defaults

- Scope is the session. Every `session_start` — startup, `new`, `resume`, `reload` — begins **disabled**. Quitting pi always returns to stock behavior.
- Nothing is written to disk: there is no state file, no cache, no marker. Two pi processes cannot affect each other.
- The default prompt is the persona bundled inside `extensions/pi-purge-pro.ts`. `/purge source <path>` points at your own file; `/purge source embedded` comes back.
- The default mode is `strict`.
- Skill routing is on by default. It reads only `*/SKILL.md` frontmatter under the root: no bodies, no script execution, no files written.
- The skill bodies ship under `skills/` as a full copy. To use a different set, point `/purge skills` at it; no code change needed.

## What differs from upstream pi-purge

| Item | Upstream `pi-purge` | This repo `pi-purge-pro` |
| --- | --- | --- |
| Package name | `pi-purge` | `pi-purge-pro` |
| Extension file | `extensions/pi-purge.ts` | `extensions/pi-purge-pro.ts` |
| Version | 0.2.1 | 1.0.0 |
| RE skill routing | none | injects skill root, routing table, mandatory flow on RE prompts |
| Skill bodies | none | shipped in `skills/`, 9 sets, works wherever installed |
| Persona, three modes, `/purge` command | — | unchanged from upstream |

Upstream is a pure prompt-experiment tool; this repo adds the "auto-mount skills on RE work" layer on top. If you only want single-variable prompt experiments, upstream behaves identically.

## 1.0.0: renamed, skills bundled

`pi-purge` is now **`pi-purge-pro`** at **1.0.0**, because it gained the reverse-engineering skill routing block plus the skill bodies shipped in the package.

- The command is still `/purge` with the same arguments. Only the package name, version, extension filename (`extensions/pi-purge-pro.ts`), and footer status key (`pi-purge-pro`) changed.
- Git installs need no change: `pi list` resolves by directory, so `git:github.com/ZiChuanLan/pi-purge@…` still points at the same checkout. npm installs should re-run `pi install npm:pi-purge-pro`; the old package name is no longer published.

## Upgrading from 0.1.x

0.2 no longer writes or reads `pi-purge.json`, and it no longer auto-detects a prompt file — the persona is bundled and the mode defaults to `strict`.

- Delete `<agent dir>/pi-purge.json`; it is ignored from now on.
- Enabling is per session: after a restart or `/resume`, run `/purge` again.
- `append` and `replace` are unchanged if you need them.

## Notes for experiments

- `strict` also drops `AGENTS.md` / project context, the skills list, and prompt text injected by other extensions. That is what makes it a clean single-variable setup, and also what makes results from `strict` not comparable to a normal session (the RE skill block above is the compensation for reverse-engineering work).
- `append` is the least invasive mode and usually the weakest signal: later sections of the harness prompt still carry a lot of weight, so differences can be small.
- `replace` still leaves harness text behind, and other extensions may append their own prompt sections after this one runs. In practice `strict` is the only mode where the persona is not competing with other framing.
- Extension load order affects what `before_agent_start` sees. Prefer recording `/purge status` output alongside any results you keep.

## Development

```bash
npm test   # 15 assertion groups; runs against a temporary agent dir and asserts nothing is written
```

The extension registers one `before_agent_start` hook, one `session_start` hook, and a `/purge` command. No other hooks, no background work, no file writes. Skill scanning runs once per root and is cached; `/purge skills reload` refreshes it.

## License

MIT
