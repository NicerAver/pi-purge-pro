# JD JCAP v2.8.5 Slider Workflow

This reference records the validated JD Passport JCAP v2.8.5 reverse-engineering workflow from an authorized CloakBrowser observation and a browser-free Python + iv8 implementation. Use it only for an owned or explicitly authorized account, host, and test workflow.

The goal is not to treat the slider as a distance-only image problem. The accepted result depends on one fresh, internally consistent round:

```text
login context
  -> session/bootstrap
  -> /cgi-bin/api/fp
  -> initial /cgi-bin/api/check (tp=30, b1/b2)
  -> interaction state and touch list
  -> final /cgi-bin/api/check
  -> code=0, no next tp, non-empty vt
```

Do not use this reference to reuse another user's state, bypass an unrelated WAF, automate an account without authorization, or persist credentials and protected values.

## 1. Routing

Use this branch when the task contains the following combination:

- JD Passport or JD login page;
- self-hosted JCAP/graphic captcha evidence;
- `/cgi-bin/api/fp` and `/cgi-bin/api/check`;
- slider challenge with `b1`/`b2` and `tp=30`;
- a browser-free replay or same-round protocol implementation is requested.

This is CAPTCHA protocol work, not Akamai Bot Manager or Imperva Reese84 work. Do not route to `akamai-protocol-reverse` because of a generic `403`, `_abck`, `bm_*`, or a JD cookie. Do not route to `captcha-vision` when the deliverable includes `/fp` to final `/check`, protected fields, touch behavior, or business replay. Use `iv8-web-reverse` only as a secondary backend when Python + iv8 is explicitly required; the CAPTCHA state machine remains owned by this branch.

Evidence needed before calling the family confirmed:

1. JD Passport or JD login page context.
2. JCAP script/version evidence, preferably the current bundle rather than an article.
3. At least one same-round `fp` and `check` sequence.
4. `tp=30` plus slider images or equivalent challenge evidence.
5. A final business response, not just HTTP 200.

If only a script URL, a cookie, or an unidentified `403` is available, stay in Trace and collect evidence first.

## 2. Evidence Rules

Treat the live SDK and same-round traffic as authoritative. Articles can suggest structure but cannot establish current field names, serialization, or algorithm behavior.

Capture only the evidence needed to reconstruct state and behavior:

- request method and path;
- non-sensitive field names and lengths;
- response business codes and challenge type;
- image dimensions and local file paths;
- script URLs, SDK version, and WASM size/hash;
- sanitized trajectory summaries;
- final success/failure verdict.

Do not persist:

- account numbers or passwords;
- Cookie values or complete sensitive headers;
- active `si`, `st`, `fp`, or JWT values;
- `vt` contents;
- full `tk`, `ct`, `cs`, or other reusable ciphertext;
- request bodies containing protected values;
- a browser profile that contains the user's login state.

Use in-memory values for live execution. Store only redacted lengths, field names, hashes of local diagnostic lists when needed, and final business metadata.

## 2.1 Known-good baseline and stage gates

当目标目录或用户提供了已经验证的 JD JCAP 参考项目时，先把它当作唯一 baseline：读取其入口脚本、runtime bridge、协议实现、画像/profile、官方资源路径和测试，再做最小迁移或差异分析。不要在 baseline 尚未运行前另起一套通用 iv8、Node 补环境或密文重写实现。

按以下门顺序推进：

```text
G0  授权、JD Passport/JCAP 版本和目标目录确认
G1  fresh /fp -> initial /check，确认 code=0、tp=30、b1/b2
G2  同一轮 runtime/WASM、图像坐标和可信手动轨迹准备
G3  官方 verify 组装 tk/ct/cs 与 final /check
G4  服务端验收：code=0、无 next tp、vt 非空
```

G1 若返回 `tp=3`、`tp=26` 或其他非目标题型，立即结束当前轮。该结果不是轨迹失败，禁止进入图片定位、轨迹调参或点选分支；优先检查 account/`si`/Cookie/session、device-info、官方资源是否同一 iv8 realm、参考画像以及服务端风险状态。连续 live 请求出现顺序性失败时停止实验并标记状态污染。

`init` 或 G1 通过只能称为 bootstrap smoke test，不能称为 final solve。只有 G3/G4 的同轮 final `/check` 满足服务端成功条件，才能把样本写入正样本池或报告为完成。

## 3. Browser Investigation

Use one active CloakBrowser page and one capture family. Do not mix state from separate browser tools during a single conclusion.

### 3.1 Page and frame

The login flow uses a Passport popup/iframe. Page-level automation may not reach the login frame reliably. For authorized observation, select the frame and inspect the DOM there. A frame-local click on the login submit button can prepare the next challenge, but the assistant must not drag the slider when the user is the trusted interaction source.

### 3.2 Network capture

Before each sampling round:

1. Clear network capture.
2. Ensure the page is at the current login challenge.
3. Record the next `fp` and `check` requests in order.
4. Keep the final response paired with the exact challenge and interaction.
5. Clear or close the round before starting another.

Do not infer success from a 200 response, a ciphertext length, or a page transition. Pair the final request with its business JSON.

### 3.3 Passive trajectory recorder

For manual slider evidence, install a passive in-memory recorder on the current challenge element, such as `.move-img`. The recorder may observe trusted `mousedown`, `mousemove`, and `mouseup` events, but it must not block, rewrite, synthesize, or dispatch the events.

Normalize each track relative to the initial press:

```text
[x, y, elapsed_ms]
```

Keep the event trust flag and the final business verdict in memory until the round is paired. A track is a positive sample only when all of the following hold:

- trusted events were observed;
- the final `/cgi-bin/api/check` returned `code=0`;
- no next `tp` was issued;
- `vt` was non-empty;
- the track belongs to the same challenge round.

A failed track can be retained as a negative diagnostic sample, but it must never enter the positive sampler.

## 4. Confirmed JD Family

The validated observation identified:

```text
SDK: JCAP 2.8.5
protocol: version=3
client: pc
slider type: tp=30
fp: POST /cgi-bin/api/fp
check: POST /cgi-bin/api/check
```

The current page loaded a JCAP bundle similar to `jcap_*.js` through the JD Passport captcha loader. The exact URL/build may change; re-confirm it from the current page on each case.

The images observed in the validated case were:

```text
b1: JPEG, source size 275x170
b2: transparent PNG canvas 65x170
rendered background: about 289.975x179.25
source-to-rendered x scale: 289.975 / 275 = 1.0544545676491477
```

The payload assembled by the page component had the following logical shape:

```json
{
  "ht": 0,
  "wt": 0,
  "bw": 0,
  "sw": 0,
  "mw": 0,
  "list": [[0, 0, 0]],
  "ii": 0
}
```

`list` is the interaction sequence `[x, y, delta_ms]`; `ii` is associated with the active WebAssembly/runtime instance. Do not assume that a different JCAP build uses the same shape without checking the current bundle.

## 5. State Machine

Keep the following state in one fresh round:

```text
login/session context
  -> fp request and fp response
  -> initial check request and challenge response
  -> b1/b2 files from that response
  -> active iv8 runtime and WASM instance
  -> interaction list
  -> tk/ct/cs generated for that interaction
  -> final check response
```

The critical invariant is not merely the same account. It is the same challenge/session/runtime state. Never combine:

- an old `si` with a new image;
- an old `st` with a new initial check;
- a track from one challenge with another challenge's images;
- `tk`, `ct`, or `cs` from a different round;
- a browser Cookie value with an unrelated HTTP session;
- a `vt` from a previous successful challenge.

A new challenge requires a new round object, HTTP session, iv8 context/storage, recorder state, and WASM state unless the current SDK explicitly proves that a state can be safely reused within that same challenge.

## 6. Protected Field Boundaries

The validated JCAP bundle exposed these logical input boundaries:

```text
tk = getTKData([
  si,
  st,
  encodeURI(JSON.stringify(payload)),
  JSON.stringify({touchList})
])

ct = getCTData([si, sensorInfo])

cs = getCSData([si, JSON.stringify({rec, fpt})])
```

The exact implementation remains owned by the official JCAP bundle and its Emscripten/WASM runtime. The safe engineering approach is to execute the official code in a narrow browser-compatible runtime rather than rewrite protected algorithms from ciphertext samples.

Use the final response as the semantic oracle:

```text
success := code == 0 AND no next tp AND vt is non-empty
```

The following are diagnostics only:

- HTTP 200;
- `tk`/`ct`/`cs` length;
- ciphertext alphabet or Base64 appearance;
- local image score;
- a non-empty intermediate state;
- a page that happens to return to the login form.

## 7. Python + iv8 Runtime

The validated implementation used:

- Python for orchestration and HTTP;
- `curl_cffi` for the same-round HTTP session;
- `iv8` for browser JavaScript semantics;
- the official current `pc-tk.js` and JCAP bundle;
- Emscripten glue and the embedded WASM module;
- in-memory storage/cookies and a per-round recorder.

The extracted WASM in the validated case was 138480 bytes with SHA-256:

```text
e21c66f3c44a81eb0aa4959a4b91f8e29c448c3b7af44efbd56a98b135f842c6
```

Treat this hash as evidence for that case, not as a permanent version contract. Re-extract and compare the current module when the bundle changes.

Important runtime checks:

1. Load the official bundle before calling its exports.
2. Keep the browser-like globals and storage in the same iv8 realm.
3. Keep the active WASM instance with the challenge that created it.
4. Verify device-info field count/shape against the current browser observation, not just total length.
5. Keep account context in process memory only.
6. Recreate the HTTP session and runtime per independent acceptance round.

A previous mismatch in the `uo` device-info value caused browser/runtime divergence. The fix was to compare parsed device-info fields, not only the total JSON length. Field count depends on account context: an empty-account bootstrap may contain 31 fields, while a solve round with the account field contains 32; the validated `uo` length was 44 and the account-bearing browser/runtime sample had total JSON length 1167. Treat these numbers as evidence for that profile, not a universal contract.

## 8. Image Localization

Image matching is a coordinate diagnostic. It is not the success oracle.

### 8.1 Initial matcher failure

A full 2D Canny `TM_CCOEFF_NORMED` search sometimes selected a visually strong but impossible candidate at a different y. Two examples showed:

```text
alpha y=75, selected y=52
alpha y=68, selected y=0
```

The resulting boxes were visibly outside the puzzle slot. This produced valid-looking payloads but final `16807/16130` failures.

### 8.2 Validated slider matcher

The JD slider moves horizontally. The transparent piece's source y is fixed for the challenge. The production diagnostic matcher therefore:

1. extracts the alpha bounding box from `b2`;
2. locks candidate search to the alpha source y;
3. uses a lower background Canny threshold `40/120` for low-contrast images;
4. uses `TM_CCORR_NORMED` for the slider edge match;
5. converts the selected source x to rendered distance with the current image scale;
6. saves the top candidates and annotated image for review.

The selected candidate must still be visually reviewed in diagnostics for a new build. A high score is not proof of success, and a low score is not a final failure by itself.

### 8.3 Coordinate calculation

For the validated image geometry:

```text
scale = rendered_width / source_width
distance_rendered = (candidate_x - alpha_bbox_left) * scale
```

Keep source and rendered coordinates explicit. Do not silently apply the scale twice. The final track endpoint is rounded to the rendered distance used by the payload builder, while the original source image dimensions remain in the payload geometry fields.

## 9. Trusted Manual Trajectories

The fixed 39-point template was a poor baseline: an early ten-round browser-free run passed only 1/10. It repeated identical timing and movement structure, which made it a weak behavioral model.

The validated CloakBrowser collection produced eight sanitized tracks:

```text
samples 1-6: successful
sample 7: failed and excluded
sample 8: successful
```

Observed positive variation included:

- move points roughly 38-52;
- move duration roughly 768-1707 ms;
- release hold roughly 78-402 ms;
- y movement including small negative offsets;
- pauses near the end or during the move;
- small and large end retraces;
- different initial acceleration profiles.

Store only normalized cumulative points, timing summaries, source distance, trust state, and paired business verdict. Do not store request state alongside the track.

The default sampler should:

1. load only `verdict=success` samples;
2. choose a sample from that positive pool;
3. scale the horizontal endpoint to the current recognized distance;
4. preserve the selected sample's timing, y, retrace, and release hold;
5. force the final x to the current rendered distance;
6. generate fresh official protected fields for the same round.

Do not automatically add generic jitter. A later experiment adding x/y, delta, and hold noise reduced a live batch from the restored 7/10 baseline to 2/10. That experiment is not a valid improvement. Distance-nearest selection also produced a contaminated 3/10 batch and should not be combined with jitter.

## 10. Controlled Experiments

When a browser-backed positive exists but browser-free success is unstable, use a controlled experiment matrix.

Record for every round:

```text
sample id
source distance
rendered target distance
scale ratio
track point count
track duration
release hold
track digest
candidate score and top candidates
final code/s_code/vt presence
```

Change one variable at a time. A useful diagnostic mode is `--manual-sample-id N`, which forces one verified positive track while keeping the rest of the protocol unchanged.

Do not interpret a high-volume A/B batch as trajectory evidence if the same account/device has already performed many CAPTCHA rounds. In the validated case, after multiple ten-round runs, 14 forced-sample requests produced 4/14 and several groups showed first-attempt pass followed by second-attempt failure. That batch was marked contaminated by likely frequency/risk state and was not used to reject samples.

Stop live requests when:

- failures become nearly monotonic with request order;
- the same track passes and fails without a stable technical difference;
- a fresh browser manual challenge also begins returning failures;
- the account/device has accumulated repeated automated challenges;
- the experiment would require more traffic merely to overcome noisy results.

Let the account/device state cool down before resuming. Do not collect more manual tracks while the server-side state is contaminated; new samples would not be trustworthy positives.

## 11. Project Layout

A reusable implementation can be organized as:

```text
project/
  main.py                         # direct runner, account only in memory
  src/pure_protocol.py            # fresh-round state machine and acceptance loop
  src/iv8_runtime.py              # official bundle and browser runtime bridge
  src/wasm_bridge.py              # active WASM instance and protected helpers
  src/protocol.py                 # payload/state validation helpers
  src/analyze_capture.py          # image matching and sanitized diagnostics
  artifacts/manual_track_samples.json
  artifacts/pure_protocol/round_N/
    b1.jpg
    b2.png
    candidates.png
    analysis.json
  tests/test_protocol.py
```

Per-round directories may contain images and candidate metadata, but must not contain protected request bodies, cookies, account values, active session IDs, `vt`, or reusable ciphertext.

## 12. Acceptance Checklist

Before calling the implementation complete:

- [ ] Current JD JCAP version and endpoints were observed from the live page.
- [ ] If a validated reference implementation exists, it was read and used as the first baseline before exploratory runtime work.
- [ ] `/fp`, initial `/check`, interaction, and final `/check` are paired in one round.
- [ ] `tp=30` and `b1/b2` are confirmed for the slider branch.
- [ ] Official JS and current embedded WASM execute in the same iv8 realm.
- [ ] Device-info shape matches the current browser observation.
- [ ] New cookies/storage/runtime/WASM state are created per fresh round.
- [ ] Image coordinates use one explicit source-to-rendered scale.
- [ ] Candidate y is constrained to the slider's fixed source y.
- [ ] Positive trajectories are accepted only with final `code=0`, no next `tp`, and non-empty `vt`.
- [ ] Failed samples are excluded from the positive sampler.
- [ ] Diagnostics contain no account, Cookie, active session, `vt`, or reusable protected value.
- [ ] Bootstrap smoke test is reported separately from final solve acceptance.
- [ ] Tests pass and a low-volume fresh acceptance batch is recorded.
- [ ] The result is not claimed as stable when account/device risk state is contaminated.
- [ ] A non-target initial `tp` stopped the round before any track tuning or point-select attempt.

## 13. Common Misdiagnoses

| Observation | Do not conclude | Correct next action |
| --- | --- | --- |
| HTTP 200 | CAPTCHA passed | Read final business JSON |
| High image score | Coordinate is correct | Inspect candidate image and fixed-y relation |
| Long `tk`/`ct`/`cs` | Protected fields are valid | Verify final `code`, `tp`, and `vt` |
| One failed sample | Sample is intrinsically bad | Repeat after clean state with a controlled matrix |
| Same sample passes and fails | Track shape is the only cause | Check image, ratio, request order, and risk state |
| A batch drops after many rounds | New trajectory is worse | Stop and mark account/device state as contaminated |
| Point-select appeared in the browser | Local slider run used point-select | Inspect the local `tp` and final branch independently |
| Login page says password error | CAPTCHA failed | Separate captcha final response from business login response |

## 14. Final Reporting

A concise engineering report should include:

1. family/version and routing evidence;
2. state-machine order and same-round constraints;
3. runtime backend and official assets used;
4. image dimensions and coordinate mapping;
5. trajectory source and positive-sample rule;
6. final business response evidence;
7. test command and result;
8. known instability, risk-state contamination, and what was deliberately not concluded.

Never report a captured `vt`, protected ciphertext, account value, or active cookie as a reusable success artifact.
