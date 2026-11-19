# SBSD Body / VMP Branch

Use this reference when the target shows Akamai SBSD / CPR second-check behavior instead of only classic `_abck` / `sensor_data` collection.

Source basis: the WeChat tutorial supplied by the user (`mp.weixin.qq.com/s/zmPnqJyxAA1mzyCnPGVGog`) plus its eight DevTools/code screenshots. This file paraphrases the actionable workflow and screenshot observations; do not treat any sample path, cookie value, dynamic key, or hash as reusable.

## Trigger Surface

Strong SBSD signals include:

- Business or document response returns JSON like `{"cpr_chlge":"true","t":"..."}` or a Privacy / SBSD soft challenge page.
- HTML contains a same-origin, Akamai-like dynamic script whose query is `?v=...` or `?v=...&t=...`.
- Network capture shows an SBSD POST with JSON payload `{"body":"...encrypted..."}` rather than classic `sensor_data=...` form content.
- Initial cookies include `bm_so` or `sbsd_o`, and a successful SBSD POST sets `bm_s`, `bm_sc`, or `sbsd_c`.
- `bm_sc` / `sbsd_c` has a `~`-delimited pass-looking structure such as `2~1~...` or `4~1~...`.

Do not classify `2~1` / `4~1` as final business success by itself. It is SBSD pass evidence that must still be followed by business replay in the same Python session.

## URL And Cookie Model

SBSD entry scripts are usually delivered from the page HTML, not from a stable endpoint name.

Common script shapes:

```text
/<dynamic>/<path>.js?v=<uuid-or-version>
/<dynamic>/<path>.js?v=<uuid-or-version>&t=<token-or-timestamp>
```

Operational meaning:

| Script URL | Common result cookie | Notes |
|---|---|---|
| `?v=...` | `bm_s` | Older / lower-friction path. Judge by route and business replay, not cookie length. |
| `?v=...&t=...` | `bm_sc` | Common for CPR / second-check flows. `t` is usually preserved into the verification URL. |
| compatible / older naming | `sbsd_c` | Treat pass structure similarly to `bm_sc`. |

Cookie roles:

| Cookie | Role |
|---|---|
| `bm_so` / `sbsd_o` | Initial server seed/state, normally obtained from homepage or first challenge response. |
| `bm_lso` | Local support state; often derived from `bm_so` plus current time. |
| `bm_s` | Older SBSD verification result. |
| `bm_sc` | Newer SBSD verification result. |
| `sbsd_c` | Compatible SBSD verification result on some routes/versions. |

Minimal state chain:

```text
GET document -> receive bm_so/sbsd_o
extract live SBSD script URL and query v/t
GET SBSD script
build encrypted body from current runtime signals
POST {"body": encryptedBody} to live verification URL
receive bm_s/bm_sc/sbsd_c
replay original business route/API in same session
```

## DevTools Capture Path

To inspect SBSD body generation in a browser:

1. Open DevTools `Sources -> XHR/fetch Breakpoints`.
2. Add a substring from the current SBSD script or verification path.
3. Let the page trigger the SBSD POST.
4. On the paused POST, inspect:
   - request URL and whether final POST kept `t` but dropped `v`;
   - request payload wrapper `{"body":"..."}`;
   - call stack / scope variable holding the pre-encryption payload.

Screenshot notes from the tutorial:

- The network payload screenshot shows query parameter `t=185245056` and a JSON request body with an encrypted `body` string.
- The response-header screenshot shows `Set-Cookie` for `bm_s` and a highlighted `bm_sc=2~1~...`, confirming the pass-cookie shape.
- The scope screenshot shows a pre-encryption object with fields like `ver`, `signals`, `perf`, `s: "f"`, and `tid`; `signals` contains 115 dynamic keys.
- The terminal screenshot shows a practical runner resolving an SBSD URL from the page, fetching the SBSD JS, loading or computing a cached template, building `encrypted_body`, and checking that `bm_sc` starts with a pass shape such as `2~1~...`.

## Plain Payload Shape

The encrypted body is not just raw signals. Before shuffling and encryption it is a payload object:

```json
{
  "ver": "<sbsd-js-version>",
  "signals": {
    "<dynamic-key-1>": "<value-1>",
    "<dynamic-key-2>": "<value-2>"
  },
  "perf": 35,
  "s": "f",
  "tid": "<per-submit-random-or-session-id>"
}
```

Field meaning:

| Field | Meaning |
|---|---|
| `ver` | Internal SBSD JS version identifier. |
| `signals` | Usually 115 dynamic key/value pairs. |
| `perf` | Generation cost / elapsed time. |
| `s` | Status flag, commonly `f` in observed samples. |
| `tid` | Per-submission random/session identifier. |

## Body Build Pipeline

Observed body generation can be modeled as:

```text
payload = {ver, signals, perf, s, tid}
json = JSON.stringify(payload)
parts = split json on commas
shuffled = shuffle parts using script-local shuffleSeed
encryptedBody = character-substitution encrypt(shuffled, sumCharCodes(v))
POST {"body": encryptedBody}
```

Important rules:

- `v` is not only a script version marker. It seeds the final character-substitution encryption.
- The final POST URL may drop `v` and keep only `?t=...`; still retain the original script `v` for body encryption.
- A body copied from one `v` will not validate under another `v`.
- `shuffleSeed` is script-local; recover it from the current SBSD JS version, not from a stale sample.
- The character substitution uses a rolling LCG-like seed update observed as `seed = seed * 65793 + 4282663` before deriving per-character offsets. Verify the exact table and modulo behavior in the current script.

Reverse-validation path:

```text
encryptedBody
-> decrypt characters with sumCharCodes(current v)
-> unshuffle comma-separated parts with the current shuffleSeed
-> recover JSON payload
-> verify ver/signals/perf/s/tid shape
```

If the reverse path cannot recover a valid payload, fix body framing before debugging business headers.

## Signals And Dynamic Keys

SBSD signals commonly contain 115 keys. The key names are dynamic shells; their semantics are comparatively stable.

Do not hardcode `tv123` / `LV281` / similar names as stable fields. Build a per-script mapping:

```text
dynamic key -> stable semantic
```

Typical semantic buckets:

| Bucket | Examples |
|---|---|
| Browser basics | user agent, platform, language, timezone, `navigator.productSub`. |
| Screen/display | width, height, colorDepth, pixelDepth, DPR, orientation, availTop. |
| WebGL/GPU | vendor, renderer, ANGLE renderer, repeated GPU consistency checks. |
| Canvas/audio | canvas hash, AudioContext / OfflineAudioContext behavior, codec support. |
| Capability checks | browser family, desktop/mobile, feature availability. |
| Automation/tamper | webdriver/headless traces, patched APIs, hook indicators. |
| Page runtime | `location.href`, host/origin lengths, `history.length`, `performance.memory`, resource fingerprint, timestamp. |
| Computed fields | `timestamp_ms`, `bm_so_hash`, `signal_integrity_hash`, version/VMP placeholders. |

Boolean signals are high-risk to map by value. Many unrelated semantics may all be `false`; only replace booleans whose semantics are proved by code location or controlled browser diffs. Otherwise preserve the observed current value.

## Key 115 / Integrity Hash

The so-called 115th key is not guaranteed to be lexically last. It is the dynamic field inserted as the final signal-integrity value.

Stable interpretation:

```text
first 114 keys = browser environment + page context + timestamp + bm_so-derived values
key 115 = integrity result computed from the prior 114 keys, bm_so, timestamp, and the current VMP formula
```

Three-phase model:

```text
Phase 1: bm_so + timestamp -> VMP formula chain with cv=1 -> bm_so_hash
write bm_so_hash into its dynamic signal key
Phase 2: sorted 114-signal values -> rolling hash -> stage1_hash
Phase 3: stage1_hash + bm_so + timestamp -> VMP formula chain -> signal_integrity_hash
write signal_integrity_hash into the final dynamic key
```

Recover these dynamic semantics before porting:

| Stable semantic | Role |
|---|---|
| `timestamp_ms` | 13-digit millisecond timestamp used in Phase 1 and Phase 3. |
| `bm_so_hash` | Phase 1 output written back into the 114-signal set. |
| `signal_integrity_hash` | Final integrity field, often described as key 115. |

Phase 2 usually sorts dynamic key names, skips null-like values, and rolls every character of each string value. The tutorial shows a simplified accumulator with multiplication by `31` and modulo, but the live script remains authoritative.

Any change to UA, screen, canvas, WebGL, location, timestamp, `bm_so`, `bm_so_hash`, key mapping, or JS version requires recomputing the final integrity key.

## VMP Trace Strategy

The goal of VMP tracing is not to understand the whole obfuscated program. The goal is to extract enough execution evidence to reproduce key115.

Trace targets:

1. Where `bm_so` is read.
2. Where timestamp is read.
3. Every `cv` write.
4. The arithmetic formula chain from `bm_so` / timestamp / `stage1_hash` to final integrity key.

Recommended instrumentation classes:

| Area | Typical count | Purpose |
|---|---:|---|
| IIFE entry | 1 | Create `traceArray` and `window.downloadTrace()`. |
| Context methods | 4 | Log `getCc`, `getCgs`, `getCv`, `setCv`. |
| VMP loops | 2 | Log main loop and inner L2 loop PC/opcode/stack. |
| Arithmetic handlers | 5 | Log `+`, `-`, `*`, `%`, `<<`. |

The tutorial screenshot shows the IIFE entry patch creating:

```text
traceArray = []
window.traceArray = traceArray
window.downloadTrace = function() { Blob(traceArray.join('\n')) -> trace.log }
```

Context-method logging:

| Method | Log label | Meaning |
|---|---|---|
| `getCc()` | `[getCc]` | `bm_so` / context cookie source; record the first 64 hex chars when that is what the live script uses. |
| `getCgs()` | `[getCgs]` | Current 13-digit timestamp source. |
| `getCv()` | `[getCv]` | Current accumulator. |
| `setCv()` | `[setCv]` | Every `cv` / hash result write. |

Observed `setCv` interpretation for one complete key115 run:

```text
setCv[0:10]  -> Phase 1 chain ending in bm_so_hash
setCv[10]    -> Phase 2 stage1_hash
setCv[11:14] -> Phase 3 chain
setCv[13]    -> final signal_integrity_hash / key115
```

Do not freeze those indexes as universal. Use them as a sanity pattern and verify with current logs.

## Locating VMP Loops And Handlers

Find the main loop by structure, not by old variable names:

```text
while (this[PC_REG][PC_KEY] < this[BYTECODE].length) {
  var op = this[OPCODE]();
  this[op](this);
}
```

Extract from the current script:

| Variable | Source structure |
|---|---|
| `STACK` | arithmetic handler `this[STACK].push(...)` |
| `POP` | arithmetic handler `this[POP]()` |
| `PC_REG` / `PC_KEY` | main-loop `this[PC_REG][PC_KEY]` |
| `BYTECODE` | main-loop `this[BYTECODE].length` |
| `OPCODE` | main-loop `var op = this[OPCODE]()` |
| `SENTINEL` | inner L2 loop `while (op != SENTINEL)` |

Log the main loop as `[VMP]` with counter, PC, and stack length. If there is an inner loop like `while (op != SENTINEL)`, log `[L2]` with PC, opcode, and stack tail before dispatch.

Arithmetic handlers are often found by searching for push/pop expressions using `+`, `-`, `*`, `%`, or `<<`.

Critical operand rule from the screenshots:

```text
_a = POP(); _b = POP(); result = _a OP _b
```

Use first-pop operator second-pop. Reversing operands breaks subtraction, modulo, shifts, and can produce `NaN` or mismatched `setCv` chains.

## Static And Runtime Checks

After patching the current decoded SBSD JS:

```text
grep traceArray source_decode.js
```

Expected rough shape:

- 2 initialization/download references.
- About 11 `traceArray.push` call sites.
- About 13 total `traceArray` references.

At runtime, `trace.log` should contain:

```text
[getCc] <bm_so-context>
[getCgs] <timestamp>
[setCv] <phase values>
[VMP] <pc/stack trace>
[L2] <inner op/stack trace, if present>
[M+] / [M-] / [M*] / [M%] / [M<<] arithmetic lines
```

Use values only from the same run. Do not mix `bm_so`, timestamp, `setCv`, or arithmetic logs across different executions.

## Porting Order

1. Save current HTML, SBSD script URL, query `v` and `t`, and response cookies.
2. Pause the SBSD POST and recover the plaintext payload object from scope if possible.
3. Establish dynamic-key semantic mapping for all fields required by the current route.
4. Identify timestamp, `bm_so_hash`, and final integrity dynamic keys.
5. Instrument the current SBSD JS and download `trace.log`.
6. Reproduce Phase 1 `bm_so_hash` against `[setCv]` values from the same log.
7. Reproduce Phase 2 `stage1_hash` over the 114-signal set.
8. Reproduce Phase 3 final integrity key.
9. Rebuild payload, shuffle comma parts, encrypt with current `v`, and POST `{"body": encryptedBody}`.
10. Confirm `bm_s` / `bm_sc` / `sbsd_c` transition, then replay the business request.

## Failure Diagnostics

| Symptom | First check |
|---|---|
| POST `{"body":...}` returns 200 but no pass cookie | Body shape, current `v`, shuffle seed, key115 recompute, and cookie jar order. |
| `bm_sc` / `sbsd_c` not `2~1` or `4~1` | Pass-state not reached; do not proceed as solved. |
| Reverse decryption cannot recover payload JSON | Wrong `v`, wrong char table/modulo, wrong rolling seed, or wrong shuffle reversal. |
| `setCv` contains `NaN` | Arithmetic operand order or numeric coercion in a VMP handler is wrong. |
| Recomputed key115 differs only after changing UA/screen/GPU | Recalculate Phase 2 and Phase 3; do not patch the final key as a literal. |
| Works in browser but protocol fails at document/API | Run the normal Akamai transport/egress matrix before rewriting SBSD body logic. |

## Reporting Addendum

When this branch is used, include in the final report:

- SBSD trigger evidence: `cpr_chlge`, script URL shape, JSON body POST, and cookie transition.
- Script URL and query handling: source `v`, source/final `t`, final POST URL.
- Result cookie: `bm_s`, `bm_sc`, or `sbsd_c`, with pass-shape classification.
- Payload fields: `ver`, signal count, `perf`, `s`, `tid` handling.
- Dynamic-key template source and the treatment of ambiguous booleans.
- Key115 recovery: timestamp key, `bm_so_hash` key, final integrity key, trace log path, and same-run proof.
- Body encryption proof: reverse-decryption payload check or browser/body parity check.
- Business replay result in the same Python session.
