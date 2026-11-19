# JS Reverse Workflow

This is the canonical local stage and handoff contract for the JavaScript reverse-engineering skills under this `skills/` directory. It is a shared reference, not a skill.

## Resource Paths

Resolve bundled resources from their owning skill directory, independently of the task's working directory:

- `references/`, `scripts/`, and `evals/` in a skill entry or root reference use that skill root.
- Inside a Trace profile index or its local documents, short `references/` and `scripts/` paths use the profile root first; fall back to the Trace root only if the profile-local target is absent. Fully qualified `references/profiles/` paths always use the Trace root. If both roots contain different files under one short name, qualify the path before reading or executing it.
- Cross-skill paths name the sibling explicitly. From this shared file, `../trace/scripts/evidence_normalizer.py` identifies the Trace tool; a runtime example's project-relative output path remains relative to that executing project.

Read the selected skill entry, then the relevant section of one matching reference. Use an index to locate that section; do not preload its catalog or sibling playbooks. Add a reference when a named missing fact requires it, and reuse already-read guidance while that fact remains current. A file-count limit must not force an incomplete task handoff.

## Routing Precedence

Choose one primary skill in this order:

1. Respect a special runtime surface first. WeChat mini program / WMPF / WeChatAppEx / AppService / WebView evidence is owned by `wechat-miniapp-reverse` whenever the requested artifact must be obtained inside that runtime.
2. Decide whether the user wants full protocol recovery or one focused stage artifact.
3. For full protocol recovery, a confirmed family skill owns the task only when its declared scope includes that outcome. Unknown, multi-layer, or unsupported deep-family work goes to `trace`, with the narrow family skill supplying evidence artifacts.
4. For a focused artifact, the current stage owner is primary even when the protocol family is known. Preserve the family evidence in the handoff.
5. Select Node.js/VM, Python+iv8, or another backend only after the requested artifact and prerequisites are clear.

For mixed prompts, apply these tie-breakers before using family keywords:

- **Requested artifact beats marker words.** Decide whether the user wants evidence or entry location, full protocol recovery, a model-only artifact, or a runtime backend. A cookie, `403`, `Reese84`, `best.pt`, `YOLO`, or `Python + iv8` mention cannot override that deliverable.
- **WMPF runtime surface owns miniapp evidence.** 微信小程序, PC 微信小程序, WMPF, WeChatAppEx, AppService, WebView, `127.0.0.1:62000`, and WMPFDebugger targets belong to `wechat-miniapp-reverse` for `Observe` and `Capture`, even when the delivery word is hook, Console, Snippets, call stack, or fingerprint, and even when a protection family is already named. No CDP browser family (`js-reverse` Edge, `chrome-devtools`, Camoufox) may take `TARGET_ACTIVE` for a WMPF target; they may only supply methodology sidecars. This priority ends when the prompt explicitly says the WMPF evidence/entry is already captured and asks for a downstream `Port` implementation: an explicit iv8/NV8 backend or a protocol owner then takes the handoff, while WMPF remains the evidence provider. Ordinary Web pages and ordinary Web APIs never route here.
- **Observation owns observation.** Hook-only, entry-location, script/call-stack, AST, fingerprint, or other evidence-only work remains `trace`, even when the family is known. For a WMPF target, the observation owner is `wechat-miniapp-reverse` instead of a browser family.
- **Protocol state machine owns protocol replay.** Complete CAPTCHA/TDC `/load` through `/verify` or post-verify replay remains `captcha-reverse`, even when the prompt also names `Python + iv8`, `best.pt`, YOLO, or a vision model. `captcha-vision` is primary only for model or recognition work that explicitly excludes protocol recovery.
- **Explicit Edge MCP directives select the js-reverse Edge browser family.** Phrases such as “用 Edge MCP”, “Edge MCP 操作 Edge”, “用 js-reverse 操作 Edge”, or “Edge 的 js-reverse MCP” make `js-reverse` the default browser evidence owner for the target. Use the same js-reverse Edge session for page, source, initiator, network, paused-scope, and WebSocket evidence; do not substitute Camoufox or `chrome-devtools` unless the user explicitly requests that family or a recorded capability gap requires a handoff. This selects the browser evidence family; the protocol/focused skill remains primary according to the requested artifact.
- **Explicit iv8 runtime directives are direct routing signals.** Phrases such as “用 iv8 补环境”, “Python + iv8 执行 JS”, or “iv8 sandbox” make `iv8-web-reverse` primary for the runtime task. Read that skill before doing Trace env-patch, Node/VM, AST, or browser work; do not treat the directive as a mere keyword. Complete CAPTCHA/TDC protocol recovery and confirmed Akamai protocol recovery remain owned by their family specialists.
- **Confirmed Reese84 excludes Akamai.** An Imperva/Incapsula Reese84 chain with corroborated GPC/solution exchange, dynamic challenge material, token/Cookie transition, and business replay belongs to `iv8-web-reverse`, even if the prompt mentions a cookie or 403; it must not route to `akamai-protocol-reverse`. A lone Reese84 label or unconfirmed cookie remains Trace family triage.
- **Explicit NV8 runtime directives are direct routing signals.** Phrases such as “用 NV8”, “NV8 补环境”, “Node + NV8 跑目标 JS”, or “用 NV8 采集/分页/签名服务” make `nv8-node-runtime` primary for the runtime task. Read that skill before doing Trace env-patch, generic Node/VM, AST, or browser work; do not treat the directive as a mere keyword. NV8 is a zero-dependency, process-isolated Node-native Edge runtime simulation with offline replay by default — it is not browser automation, so it never owns `TARGET_ACTIVE` and never substitutes for browser evidence. Use `js-reverse` Edge when real rendering, clicking, screenshots, CDP network, or real DevTools call stacks are required, then hand the fixed artifacts to NV8 for deterministic offline replay. Complete CAPTCHA/TDC protocol recovery and confirmed Akamai protocol recovery remain owned by their family specialists.
- **Node-native versus Python runtime backends are separate gates.** `nv8-node-runtime` is primary when the user names NV8, when the deliverable is a sustainable Node collection pipeline (pagination, rate limiting, circuit breaking, resumable checkpoints, dedup sinks), or when the target scripts must run under offline deterministic replay. `iv8-web-reverse` is primary when the user names iv8, the deliverable is a Python request script that needs iv8, or confirmed Reese84 dynamic challenge/Cookie/业务回放 is being delivered. A WMPF/AppService/WebView request whose inputs and outputs are already captured and whose next artifact is a pure browser-free Python collector remains `trace`; Python, `requests`, or browser-free wording alone does not select iv8. Only an explicit iv8 directive or the complexity gate's proven browser-semantic requirement may promote that handoff to `iv8-web-reverse`. Neither runtime is selected by a protection-family keyword alone; if the user selected neither backend, Trace may coordinate and delegate after the complexity gate.
- **Backend and family admission are separate gates.** `iv8-web-reverse` is primary for an explicit iv8 environment-patch, collector/replay, or confirmed Reese84 collector/replay. If the user did not select a backend, Trace may coordinate a complex env-patch and delegate iv8 after the complexity gate. `akamai-protocol-reverse` is primary only with an Akamai-native marker plus independent corroboration and a protocol-recovery goal; a lone marker or a Reese84 label is not Akamai evidence.
- **Unknown or composite unsupported scope stays Trace.** When no specialist has all prerequisites, use `trace` as coordinator and name specialists or backends as secondary providers.
- **Skill definition work beats OpenCode configuration words.** Requests to create, audit, score, optimize, package, or add evals for skills route to `skill-creator` even when they mention OpenCode. Use `customize-opencode` only for config, agent, plugin, MCP, permission, model, or keybinding changes that do not modify skill definitions, descriptions, evals, or packaged skill resources.

Use `primary skill + secondary backend` when needed. For confirmed Akamai recovery, `akamai-protocol-reverse` keeps the state machine and business acceptance; an explicitly selected, available `nv8-node-runtime` may generate one local sensor/URL/header artifact. In that delegated mode NV8 stays offline, Python owns challenge/script fetches and final HTTP, and the Node Collector is not selected. If NV8 is unavailable, return the capability gap to the primary rather than replacing the requested backend silently. A protocol-specific skill remains primary only for the recovery or collector outcomes it explicitly owns. For unsupported deep-family work, `trace` coordinates while the narrow family skill supplies evidence. For Hook-only, AST-only, Node-patch, entry-location, and dynamic browser-proof tasks, the matching `trace` stage or profile is primary. When the user says Edge MCP, bind `TARGET_ACTIVE` to the js-reverse Edge family and keep that browser owner throughout the evidence round. Use `camoufox-reverse` as the Camoufox fingerprint baseline when available only when selected by the request or required by the evidence; use `js-reverse` or `chrome-devtools` for CDP network, source, initiator, paused-scope, or WebSocket evidence, and record capability gaps. Explicit iv8 environment-patch or replay requests are owned by `iv8-web-reverse` from intake; only an unspecified-backend complex task uses Trace as coordinator with iv8 as secondary. Secondary stage providers include the Trace browser-hook, AST, and env-patch profiles, browser reverse tooling, `nv8-node-runtime`, and `iv8-web-reverse`.

Confirmed CAPTCHA artifacts such as Tencent TDC `collect`, slider behavior payloads, or verify parameters remain `captcha-reverse` primary even when the Trace env-patch profile supplies the Node execution backend.

For WeChat/WMPF targets, `wechat-miniapp-reverse` owns the runtime evidence stages and then hands a monotonic-forward packet to `trace`, `iv8-web-reverse`, or `captcha-reverse` according to the usual gates, after breakpoint cleanup and lease release. Downstream skills consume saved miniapp artifacts only; they must not call `miniapp-reverse-mcp` request/script/frame/target IDs, and released or unverified IDs are `stale` or `artifact-only`. Once the WMPF request, fixed inputs/outputs, and request contract are captured, a pure browser-free Python collector is a Trace outcome; explicit iv8 or confirmed Reese84 delivery changes the owner to `iv8-web-reverse`, while a complete embedded CAPTCHA state machine remains `captcha-reverse`. A downstream skill that lacks evidence returns to `wechat-miniapp-reverse` for one more capture round instead of re-owning the runtime.

Composite requests use the earliest unmet artifact:

- Paste-ready observation and a stack hint -> `trace` browser-hook profile; a proven function/script location -> Trace Observe/Capture with browser reverse evidence tools and a capability note.
- Dynamic browser proof explicitly requested -> Trace Observe/Capture with Camoufox when fingerprint or anti-detect evidence matters; fixed samples already sufficient for Node/VM execution -> `trace` env-patch profile.
- Source structure must become readable before an entry can be isolated -> `trace` AST profile; an entry already exists and deobfuscation is incidental -> `trace` env-patch profile.
- Target only exists inside WMPF/AppService/WebView -> `wechat-miniapp-reverse` for target, request, initiator, source, and paused-scope evidence; the same request already proved and the goal is a browser-free collector or local runtime -> `trace` or `iv8-web-reverse` with the saved miniapp artifacts.

## Stages

| Stage | Exit artifact | Typical owner |
|---|---|---|
| `Observe` | Confirmed request, scripts, fields, trigger | Trace Observe with browser reverse tools; `wechat-miniapp-reverse` for WMPF/AppService/WebView targets |
| `Capture` | Real inputs, outputs, call order, environment reads | Trace Capture or browser-hook profile; `wechat-miniapp-reverse` inside WMPF |
| `Transform` | Readable targeted source and reversible AST passes | `trace` AST profile |
| `Rebuild` | Local entry that executes far enough to diagnose | `trace` env-patch profile |
| `Patch` | Minimal environment patch and first-divergence record | `trace` env-patch profile |
| `Consolidate` | Fixed fixture plus server-validated local output | `trace` env-patch profile, protocol owner |
| `Port` | Stable host implementation and real request replay | `nv8-node-runtime` for Node deliverables, `iv8-web-reverse` for Python, protocol owner |

Keywords such as `412`, `token`, `cookie`, `worker`, `wasm`, or `JSVMP` do not select a stage by themselves. Route from the evidence already available and the user's requested artifact.

## Sensitive Input Delivery

For generated project scripts, never put user-provided `Cookie`, `Authorization`, bearer token, API key, private key/IV, session secret, or similar credential into a PyCharm/OS environment variable by default, and never write the real value into source, skill files, cases, reports, fixtures, or logs. Put an editable top-level constant in the delivered script and leave it empty, for example `COOKIE_HEADER = ""`, `AUTHORIZATION = ""`, or `PRIVATE_KEY = ""`; fail with a clear local message when a required value is still empty. This rule applies to user-supplied credentials only: dynamic cookies, tokens, signs, timestamps, and challenge values must be generated or refreshed inside the same Session/runtime chain. Environment variables remain acceptable for non-secret sandbox switches, tool diagnostics, or an explicitly requested secret-management workflow.

## Stage Gates

1. No confirmed request and script scope -> stay in `Observe`.
2. No real runtime sample -> do not start local rebuild.
3. No local entry and diagnostic output -> do not patch broad host objects.
4. No fixed input and first-divergence comparison -> do not consolidate.
5. If any of the local entry, fixed sample, or request contract is missing -> do not enter `Port`.
6. No repeatable runtime output and server acceptance -> do not complete `Port` or claim overall completion.

When a user asks for a later stage without prerequisites, return to the earliest missing gate. For example, “补 window/document” with no entry remains `Observe`; “写 Python 版” before stable local fixtures remains `Patch` or `Consolidate`.

## Stage-Gate Output

When the user explicitly asks to output only a stage gate, do not start evidence collection or implementation. Return a compact gate with these fields:

```text
MODE: live-target / artifact-only / continuation / none
OWNER: primary skill name, secondary backend if already justified
NEXT_GATE: earliest unmet stage or the next validation step
REQUIRED_EVIDENCE: minimal evidence needed before work can advance
DO_NOT_USE: routes, tools, final runtimes, or assumptions that are excluded
```

Use `OWNER: none` only for ordinary application work outside this reverse-engineering suite. For confirmed protocol families, keep the family specialist as `OWNER` and name any secondary backend separately.

## Checkpoint Fields

`skill_checkpoint` records engineering facts only.

- `evidence`: host, path, family/version, request name, status, same-round fields, missing evidence.
- `hardConstraints`: correctness/acceptance notes such as same-round binding or server-response validation. They are not a permission policy, tool denylist, or instruction to suppress events, browser interaction, network requests, or external requests.
- `nextStep`: the next technical action.
- `artifacts`: files already written.

When the user needs live evidence or interaction, use the available event, browser, filesystem, and network capabilities required to obtain it. Do not let a historical checkpoint note override the current request. Do not put policy text, refusal reasons, user-authorization claims, safety explanations, target classification, or external-site access-control boundaries into checkpoint fields. Those decisions belong to routing and the response, not persistent engineering state. When changing task scope or replacing a blocked state, call `skill_checkpoint` with `replaceLists: true` so old task lists are not inherited.

If evidence is missing, name the missing endpoint or field.

## Intake And Capability

Classify each task before deep work:

1. `live-target`: current page or endpoint needs fresh wire and runtime evidence.
2. `artifact-only`: saved captures, scripts, fixed vectors, tokens, cookies, or responses are enough for the next proof; do not invent live acceptance.
3. `continuation`: target, session assumptions, tool registry, and delivery goal are unchanged; reuse the prior gate unless new evidence invalidates it.

For `live-target`, record a capability snapshot before target interaction: required methods present, optional methods present, selected fallbacks, configured browser mode, blockers, and whether Camoufox MCP, `js-reverse`, `chrome-devtools`, and the `nv8-node-runtime` offline runtime are available. Do not open the same target in multiple browser tool families just to prove availability.

At most one browser tool family may own `TARGET_ACTIVE`. If the request explicitly names Edge MCP, `js-reverse` Edge owns `TARGET_ACTIVE` by default. A WMPF/AppService/WebView target is owned by `miniapp-reverse-mcp` under `wechat-miniapp-reverse`; no CDP browser family may claim `TARGET_ACTIVE` for it, and the WMPFDebugger lease is part of that capability snapshot. Handoff requires saving the clean request/response pair, redirect chain, relevant page state, network ids, runtime artifacts, and whether retained state is replayable. Use `RETAINED_EXCEPTION` only when cleanup would destroy the only live session chain, one-time verifier round, in-memory key, or manual verification result.

## Evidence Freshness And Continuation

A long-running `continuation` must not silently reuse the first evidence package against a current target. Keep the original package immutable and label it with an `evidence_id` such as `E1`. Before an expensive stage or live acceptance test, continue the same session's evidence path by calling the same MCP server and equivalent tools used for the initial capture. Prefer the original browser family and tool sequence; switch only after recording a capability gap.

For a WMPF target, revalidate through the same `miniapp-reverse-mcp` session and the same AppService/WebView target. A target switch, target exit, MCP reconnect, or WMPFDebugger lease release makes previously captured request/script/frame/target IDs `stale`; keep the saved payloads as `artifact-only` and re-capture before live acceptance.

Use the MCP result to make a lightweight currentness check: compare script/source fingerprints, request and response shape, relevant cookie/storage transitions, and the session or challenge state that the current test consumes. If the check is consistent, continue with the existing evidence and record that it was revalidated. If it changes, mark the affected evidence stale, capture a new immutable package such as `E2` with the same MCP path, and resume from the earliest stage that depends on the changed surface. Do not mix old dynamic state with the new session chain.

Every checkpoint and test result must name the evidence version, collection time, MCP server/tool family, and any stale reason. Keep historical replay against `E1` separate from live acceptance against the current package. A failure on a newer package is evidence of a possible target change until freshness has been checked; do not immediately classify it as an algorithm failure.

## Handoff Envelope

Save cross-stage handoff data to `js_reverse_cache/tasks/<task-id>/handoff.json`:

```json
{
  "task_id": "stable-id",
  "primary_skill": "skill-name",
  "secondary_backend": "skill-name-or-null",
  "current_stage": "Observe",
  "target_url": "https://example.test/api",
  "target_method": "POST",
  "target_fields": ["x-sign"],
  "baseline_id": "source-session-time",
  "artifacts": {},
  "success_predicate": "fixed input and live replay match",
  "unresolved": []
}
```

The upstream stage writes its exit artifact; the downstream stage validates required fields before work begins.

## Stage Fields

### Observe or Capture to Transform/Rebuild

- `target_url`, `target_method`, query/body shape
- `target_fields`
- `suspect_scripts`
- `entry_candidates` or confirmed `entry_function`
- `entry_script_url` and local source path
- `sample_input`, `sample_output`
- `env_reads`
- injection timing and observer-effect notes
- `runtime_surface`: `browser`, `wmpf-appservice`, or `wmpf-webview`
- for WMPF: MCP server, target id/type, per-ID validity (`fresh` / `stale` / `artifact-only`), lease state, and whether breakpoints/profiler/coverage were cleaned up

### Rebuild to Patch

- `undefined_paths`
- `first_divergence`: path, expected, actual
- `loaded_modules`
- init/setup parameters and trigger order
- baseline and session identity

### Patch to Consolidate

- fixed fixture input/output
- key intermediate values
- stable sign/cookie/token shape
- runtime and version boundaries
- server validation result

### Consolidate to Port

- fixture input/output
- request contract and serialization rules
- session cookies and bootstrap artifacts
- challenge HTML/JS paths when needed
- refresh policy and per-request regeneration rules

## Evidence Storage

All generated artifacts belong in the executing project's workspace, not in a skill directory:

```text
js_reverse_cache/tasks/<task-id>/
  task.json
  handoff.json
  network.jsonl
  scripts.jsonl
  runtime-evidence.jsonl
  fixtures/
  env/
  report.md
```

Bind evidence to source URL, timestamp, browser/runtime baseline, and session. Do not mix UA, Cookie, storage, screen, TLS, or environment values from different baselines into one replay chain.

Do not place real reusable cookies, authorization values, account identifiers, private tokens, or complete session material in public cases or generic templates.

Stable proof metadata belongs in `analysis/proof_manifest.json`. It should record intake mode, capability snapshot, artifact hashes, evidence package hashes, session scope, helper boundary, fixed-vector proof, live replay count, browser-free status, runtime-free status, and residual risk without raw secrets.

When a skill needs publishable or cross-stage evidence, prefer Trace's reusable tools (paths relative to this shared directory): `../trace/scripts/evidence_normalizer.py` for redacted ordered captures, `../trace/scripts/transcript_diff.py` for first chain divergence, `../trace/scripts/transform_trace_diff.py` for staged runtime parity, and `../trace/scripts/transport_profile_diff.py` for transport profile deltas.

## First Divergence

`first_divergence` is the earliest proven difference between browser truth and local output. Patch only the smallest causal unit that explains it: one value, one function shell, one returned object, or one inseparable object contract.

Each patch iteration records:

1. the triggering evidence
2. the browser expected value or behavior
3. the local actual value or behavior
4. the patch rationale
5. whether the divergence moved forward

Loading without errors, fewer logs, plausible output length, or HTTP 200 alone does not prove correctness.

## Completion Gate

Complete a stage only when its artifact exists and validates. Complete the overall task only when:

1. the wire request and state ownership are proven
2. fixed-input outputs match expected structure and key values
3. fresh replay succeeds repeatedly on a coherent session
4. response and business semantics are correct
5. runtime dependencies and residual risk are explicit

The final owner reports the primary skill, secondary backend, current stage, artifact paths, validation result, and unresolved facts.
