# Tencent EdgeOne / TCaptcha TDC Workflow

Use this workflow for Tencent CAPTCHA protocol chains built around a fresh
`cap_union_prehandle` response, dynamic `tdc.js`, TDC telemetry, POW, and
`cap_union_new_verify`. It covers EdgeOne `click_verify` as well as the shared
TDC stage used by interactive TCaptcha variants.

## Recognition Signals

Strong signals include:

- `captcha.eo.qq.com` or Tencent CAPTCHA static domains;
- `/cap_union_prehandle` and `/cap_union_new_verify`;
- response fields such as `sess`, `sid`, `comm_captcha_cfg`, `dyn_show_info`,
  `tdc_path`, and `pow_cfg`;
- runtime APIs `TDC.setData`, `TDC.getData(true)`, and `TDC.getInfo()`;
- verify fields `collect`, `tlg`, `eks`, `ans`, `pow_answer`, and
  `pow_calc_time`;
- a final response containing `errorCode`, `ticket`, and `randstr`.

Do not route an ordinary EdgeOne 403, 412, or JavaScript Cookie challenge here
unless the CAPTCHA endpoints or TDC state machine are present. Unknown
multi-layer protection belongs to `trace`; locating an unknown TDC entry
or browser call stack belongs to Trace Observe/Capture with the current browser reverse tools.

## Required End State

The browser-free chain is:

```text
optional protected-page first hop
  -> fresh cap_union_prehandle
  -> download that round's dynamic tdc.js
  -> construct one observed iframe environment in iv8
  -> reproduce the observed TDC.setData sequence
  -> TDC.getData(true) + TDC.getInfo().info
  -> solve that round's POW
  -> cap_union_new_verify
  -> optional ticket/Cookie business-page check
```

The browser is an evidence source, not the delivered runtime. The production
script must obtain new challenge state and dynamic JavaScript on every run.
For controlled diagnosis, it may also accept an explicitly exported
same-round `prehandle` and `tdc.js` snapshot; that mode must never mix a
snapshot with a new `sess`, image, POW, or answer.

## Same-Round State

Keep all of the following in one HTTP Session and one run directory:

- page cookies and request identity when the protected page contributes them;
- prehandle `sess`, `sid`, `pow_cfg`, `tdc_path`, and `dyn_show_info`;
- the exact dynamic TDC response downloaded from that `tdc_path`;
- iframe globals, widget-derived `ft`, tracker data, `collect`, and `eks`;
- POW answer, verify form, verify response, and optional ticket replay.

Never combine an old TDC file with a new `sess`, reuse `collect/eks`, or carry a
POW answer into another challenge. Treat a failed or consumed verify as the end
of that round unless direct evidence proves retry semantics.

An optional protected-page first hop can fail independently because of
transport admission. Record the failure and decide whether the CAPTCHA layer
actually depends on its Cookie. Do not silently create a second Session for
prehandle or verify.

## Browser Evidence Collection

Collect evidence in this order:

1. Clear network capture and trigger one fresh challenge.
2. Save prehandle request/response, final dynamic TDC URL, TDC response, verify
   form, verify response, and the request initiator.
3. Hook `TDC.setData`, `TDC.getData`, and `TDC.getInfo` before the challenge
   action. Preserve argument order, return values, and stacks.
4. Read `dyn_show_info.show_type` before deciding whether this is a slider,
   image challenge, or `click_verify`.
5. Capture the actual iframe baseline: frame URL, `document.referrer`,
   `window.name`, `TCaptchaSid`, `TCaptchaReferrer`,
   `TCaptchaIframeClientPos`, viewport, screen, UA/Client Hints, and observable
   `window.top` behavior.
6. Export one browser fingerprint baseline. Do not merge navigator from one
   browser, screen from another, and TLS identity from a third.

The most useful dynamic observation is the exact `setData` sequence. A
verified `click_verify` branch used this semantic order:

```javascript
TDC.setData({isNewEntry: 1});
TDC.setData(trackerPayload);
TDC.setData({ft});
const collect = decodeURIComponent(TDC.getData(true) || "");
const eks = (TDC.getInfo() || {}).info || "";
```

Do not assume this order for a new widget build without capturing it. Preserve
the order when it is observed because TDC keeps internal mutable state.

## No-Feel `click_verify` Replay Baseline

This section records a reusable no-feel baseline from a live TCaptcha build. It
is a diagnostic profile, not a collection of protocol constants. Re-capture the
current widget when the page, bundle, response schema, or browser version
changes.

### Capture the actual no-feel branch

For a no-feel entry such as the observed `#noFeel_click` on a CAPTCHA demo page:

1. Clear the network log and trigger the entry exactly once.
2. Keep the complete same-round chain: `cap_union_prehandle`, the `tdc_path`
   response, the final `cap_union_new_verify` form, and its response.
3. Parse the prehandle JSONP before extracting `sess`, `sid`, `tdc_path`,
   `comm_captcha_cfg`, and `pow_cfg`.
4. Treat the dynamic `tdc.js` loaded by the CAPTCHA iframe as the source of
   truth. The outer frame bundle can be a high-entropy or self-decoding loader;
   failure to find `TDC.setData` text in that outer bundle does not prove that
   TDC is unused.
5. Record the final iframe URL and initiator. One observed baseline used
   `https://turing.captcha.gtimg.com/1/template/drag_ele.html` at 360x360 with
   Chrome 151, Win32, and `zh-CN`; these values are reproduction evidence, not
   stable constants.

A fresh challenge may replace `window.TDC` after an initial object was wrapped.
Install an assignment observer or setter before triggering the challenge and
wrap every newly assigned TDC object. Wrapping only the initial object can
produce an empty `setData/getData/getInfo` log even though the dynamic script
later uses TDC. Also verify that the hook is installed in the iframe that loads
`tdc.js`; an `about:blank` sibling frame is not evidence for the TDC call path.

### Static no-feel contract

In the observed no-feel build, the widget's request helper had this contract:

```text
setTdcData(value) -> TDC.setData(value)
getTdcData()      -> TDC.setData({ft})
                    -> decodeURIComponent(TDC.getData(true) || "")
getKeyInfo()      -> (TDC.getInfo() || {}).info
```

The no-feel branch set an automatic answer before entering verification:

```javascript
dataManager.setData("autoVerify", [
  {elem_id: 0, type: "DynAnswerType_TIME", data: ""}
]);
verify();
```

Do not import the generic `isNewEntry` or slider tracker payload into this
branch without current evidence. In this case the proven TDC input was the
current widget `ft`; no dense trusted pointer path or extra tracker field was
needed for the successful no-feel replay. This is a branch observation, not a
universal TCaptcha rule.

The `ft` producer came from a small webpack capability-probe module. One build
used module index `70` and encoded a feature bitmap with a URL-safe six-bit
alphabet, but both the module index and output are build-dependent. Extract and
execute the producer from the current widget bundle; never hardcode an observed
value such as `6f_7Pf__H`.

### Browser-free V8 reconstruction

Use one fresh V8 realm per challenge. Load a minimal document with the actual
iframe URL as the base URL, then set only the observed globals before evaluating
that round's dynamic script:

- `TCaptchaSid` from the current prehandle response;
- `TCaptchaReferrer` and `document.referrer` from the current page;
- `TCaptchaIframeClientPos` from the measured iframe rectangle;
- `window.name` as observed by the iframe;
- the observed UA, platform, locale, timezone, screen, viewport, and Client
  Hints baseline.

Keep V8 network requests disabled unless the runtime explicitly uses recorded
offline replay. The dynamic script must be fetched by the Python session for
the same round and then passed into V8; do not let V8 fetch a different script
or silently fall back to a cached response. Assert that `TDC.setData`,
`TDC.getData`, and `TDC.getInfo` exist before generating telemetry.

The successful local sequence was:

```text
fresh tdc.js -> current ft producer -> TDC.setData({ft})
             -> TDC.getData(true) -> TDC.getInfo().info
             -> collect, eks
```

`eks` matched the browser evidence in the observed build, while `collect` was
content- and timing-dependent. A local `collect` length of 920 in one fresh
round and 952 in another was valid even though a browser sample was 984. Do
not pad or reject `collect` to match a browser length; set `tlg` to the exact
length of the transmitted decoded `collect` string.

### Same-round HTTP and final verify

Keep a single cookie-aware HTTP session from prehandle through dynamic script
and verify. In Python, use one `CookieJar` with an `HTTPCookieProcessor`; a
constructed but unattached cookie jar does not preserve the challenge session.
Keep the request identity coherent across the session: UA, Client Hints,
Origin, Referer, content type, and any page cookies that the prehandle response
sets.

For the observed MD5 POW branch, solve the current configuration rather than
copying a browser value:

```text
md5(pow_cfg.prefix + decimal_nonce) == pow_cfg.md5
```

Submit the matching concatenated `pow_answer` and measured `pow_calc_time`
with the same-round form:

```text
collect=<decoded TDC output>
tlg=<exact transmitted collect length>
eks=<TDC.getInfo().info>
sess=<fresh prehandle sess>
ans=[{"elem_id":0,"type":"DynAnswerType_TIME","data":""}]
pow_answer=<fresh solution>
pow_calc_time=<measured calculation time>
```

The final verifier, not local field shape, decides success. Require HTTP 200,
`errorCode == "0"`, and non-empty `ticket` and `randstr`. A validated
implementation passed this gate in two consecutive fresh browser-free rounds;
record each attempt in its own `js_reverse_cache/` directory and keep raw
session values in volatile run evidence only.

## Widget Data And `ft`

The outer widget can build data that is later fed into TDC. In the verified
branch, the tracker payload contained:

- `slideValue`;
- `verifyBtnPos`;
- `opAreaPos`;
- `clientSize`.

Capture these values at the `setData` boundary instead of reconstructing them
from property names alone. Positions and viewport dimensions are layout
values, not universal constants.

The `ft` value was produced by a small widget webpack module before the final
`setData`. Extract and execute the current bundle's producer in iv8. A module
index observed in one build, or one previously returned `ft` string, is only a
locator clue; neither is a stable protocol constant.

## Current Visible Slider Baseline

This baseline was recovered from the Tencent Cloud `aid=199999861` visible
slider using an ordinary Chrome positive sample and then validated by two
consecutive fresh browser-free Python + iv8 successes. Treat build names,
module indexes, geometry, and capability values as evidence for one widget
version, not constants.

### Resolve the widget layer before extracting `ft`

Do not confuse the outer `tcaptcha-frame.<hash>.js` with the iframe widget. The
outer frame creates or controls the CAPTCHA iframe but may contain no literal
TDC calls. For the observed visible slider, resolve the chain in this order:

```text
current TCaptcha/TJCaptcha loader
  -> current tcaptcha-frame.<hash>.js
  -> https://turing.captcha.gtimg.com/1/template/drag_ele.html
  -> current dy-ele.<hash>.js
  -> TDC wrapper and ft producer modules
```

In the observed `dy-ele` build, wrapper module `45` implemented this contract:

```javascript
const ft = currentFtProducer();
TDC.setData({ft});
const collect = decodeURIComponent(TDC.getData(true) || "");
const eks = (TDC.getInfo() || {}).info || "";
```

The capability producer was module `70` in that build. It evaluated 50 browser
capability probes, set bits at one-based probe indexes, grouped them into
six-bit chunks, and encoded the chunks with:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_
```

The module number and output change with the widget and environment. Extract
or faithfully port the producer from the current widget. Never hardcode a
browser-observed `ft`, and do not compute it in one environment while running
TDC in another. A short token from a sparse Node stub can be structurally valid
but semantically inconsistent with a real Chromium baseline.

### Visible slider behavior order

The current visible slider and no-feel `click_verify` branch have different
behavior contracts. For the validated visible slider:

1. Create one fresh iframe-like iv8 Realm and load the same-round dynamic
   `tdc.js`.
2. Set the observed iframe globals and geometry before evaluating TDC.
3. Dispatch trusted pointer/mouse down, move, and up events with real elapsed
   time and the current display-space drag distance.
4. Run the current widget `ft` producer in that same Realm.
5. Call `TDC.setData({ft})`, then `TDC.getData(true)`, then
   `TDC.getInfo().info` without reinitializing the Realm.
6. Submit the independently assembled raw-image `DynAnswerType_POS` answer.

Do not automatically add a generic `setData` tracker object containing
`slideValue`, `verifyBtnPos`, `opAreaPos`, or `clientSize`. Older or different
branches may expose those fields, but the validated current `dy-ele` slider
accepted trusted input followed by `{ft}` without a synthetic tracker
`setData` call. If a new build shows extra calls at the real boundary, preserve
that captured order instead.

The validated browser iframe baseline had these relationships:

- iframe URL: the current `drag_ele.html` URL;
- `window.name`: the Tencent CAPTCHA API origin used by the iframe;
- `TCaptchaReferrer`: the full embedding page URL;
- `document.referrer`: the embedding page origin/page as observed;
- a `360x360` iframe viewport with the captured DPR and screen baseline;
- verify `Origin` and `Referer`: the iframe's `gtimg.com` origin, not the outer
  business page or the `qcloud.com` request host.

These values must be measured again when the page or widget changes. Preserve
UA, Client Hints, screen, DPR, iframe geometry, HTTP headers, and iv8
fingerprint as one identity.

### AI-background coordinate recovery

Do not trust a single `ddddocr.slide_match` result on AI-generated or highly
textured backgrounds. In one server-successful positive sample, the direct
matcher was wrong by 43 raw-image pixels, which was enough to produce
`errorCode == "50"` even though TDC, POW, and serialization were valid.

For sprite-based Tencent sliders, prefer this evidence-backed coordinate
method:

1. Crop the current puzzle piece using that round's
   `sprite_pos/size_2d`.
2. Compute the non-transparent alpha bounding box inside the crop.
3. Detect closed gap contours in the raw background and filter candidates by
   the alpha shape's width, height, area, and valid movement range.
4. Convert the contour boundary to the piece's raw top-left answer:

```text
answer_x = contour_x - alpha_bbox_x
answer_y = contour_y - alpha_bbox_y
```

5. Compare a fallback matcher and reject or inspect large disagreement rather
   than silently submitting it.
6. Submit raw-image coordinates in `DynAnswerType_POS`; use display-space only
   for behavior input.

For the common `672` raw width and an observed `340` display width, the trusted
drag distance is derived separately:

```text
display_distance = (answer_x - initial_x) * display_width / raw_width
```

Never submit `display_distance` as `answer_x`, and never add a historical
border offset without deriving it from the current alpha/contour geometry.

### Token and request identity

Current browser requests can include a base64-encoded `ua` in prehandle and a
`tkid` across prehandle, image, and verify requests. Preserve an observed token
lifecycle in the same HTTP session. In the validated browser-free path, the
same-Realm TDC `getInfo().tokenid` was used as the current verify `tkid`; do not
reuse a token from another browser, Realm, or challenge.

Keep current frame hash, `subsid`, UA/Client Hints, `Origin`, `Referer`, and
content type aligned with the live browser request. A stale frame hash may
still return a challenge, but it is not evidence that the request identity is
current.

When diagnosing `errorCode == "50"`, anchor a browser success first and compare
in this order:

1. raw answer coordinates and alpha/contour mapping;
2. current `ft` producer output and probe bitmap;
3. trusted event path, elapsed time, and display distance;
4. iframe globals, geometry, DPR, and cross-origin semantics;
5. `ua`/Client Hints, `tkid`, frame hash, `subsid`, Origin/Referer, and
   transport identity.

A browser-successful answer plus two consecutive fresh browser-free successes
is sufficient to promote the profile. Keep the successful response as the
acceptance artifact, but redact one-time `sess`, `collect`, `eks`, `tkid`,
ticket, and randstr from durable documentation.

## Image Point-Click Branch

For `dyn_show_info` image point-click challenges, first confirm that the
current `click_cfg.data_type` contains `DynAnswerType_POS`. Keep the prompt,
background image, `sess`, dynamic TDC, and answer order from the same round.
The submitted points are coordinates in the raw challenge image, commonly
`672x480`; they are not coordinates in the displayed iframe. Convert from the
actual `#slideBg`/operation rectangle only after measuring its DOM rectangle,
and preserve the prompt order in the `ans` array.

A detector such as `ddddocr` can provide candidate boxes, but semantic OCR for
stylized symbols is only a localization baseline. Do not submit guessed points:
use a confirmed manual/browser answer as evidence or a reliable per-symbol
recognizer, then validate with the server response.

For a browser-free controlled replay, use a two-phase procedure:

1. Capture a fresh unconsumed `prehandle`, dynamic `tdc.js`, image assets, and
   challenge metadata.
2. Determine the ordered raw points and run the iv8 verifier before any browser
   click consumes that round. Exported `prehandle`/`tdc.js` snapshots are useful
   for this exact same-round test, but a consumed verify response cannot be
   reused as a second acceptance result.

The widget may produce `ft` through a webpack module before calling
`TDC.setData({ft})`. Extract the producer from the current widget bundle and
execute it in iv8; a module number such as `68` is evidence for one bundle, not
an eternal protocol constant. The verified point-click runner used Python
requests plus iv8, injected `ft`, generated non-empty `collect`/`eks`, solved
POW, and submitted `DynAnswerType_POS` answers successfully.

## iv8 Reconstruction

Use `iv8-web-reverse` as the execution backend while this skill remains the
owner of the CAPTCHA state machine and success criteria.

1. Load a minimal HTML document using the observed iframe URL as `baseURL`.
2. Apply one exported browser baseline and only evidence-backed environment
   patches.
3. Set challenge globals before evaluating dynamic TDC. Important examples are
   `TCaptchaSid`, `TCaptchaReferrer`, `TCaptchaIframeClientPos`, and
   `window.name`.
4. Evaluate the fresh TDC source and assert that `getData` and `getInfo` exist.
5. Execute the current widget `ft` producer.
6. Reproduce the captured `setData` calls in order.
7. Drain required timers/microtasks, then read `collect` and `eks`.
8. Reject empty output before sending verify.

Keep UA, `sec-ch-ua`, platform, timezone, screen, and the HTTP impersonation
profile coherent. When `curl_cffi` is needed for transport admission, use the
same identity as the iv8 baseline rather than changing only the TLS profile.

### Environment Differential

When TDC initializes but verify returns a generic risk code, do not add random
DOM stubs. Instrument safe property reads in the current TDC build and compare
the browser and iv8 property sets.

Prioritize evidence-backed differences in:

- navigator and UAData;
- screen, viewport, DOM geometry, and frame hierarchy;
- performance/resource timing;
- Permissions, WebGPU, network information, Audio, WebGL, and WebRTC;
- referrer, frame URL, `window.name`, and cross-origin `window.top` semantics.

Use selective AST rewriting or engine-level tracing and cap the rewrite set.
Record browser-only and iv8-only properties separately. Similar access counts
do not prove equivalent values or exception behavior. `window.top` can remain
a hard residual because a real CAPTCHA iframe observes a cross-origin parent
while a local runtime often aliases the current Window; isolate that mismatch
instead of rewriting the whole environment around it.

## Passive And Active Behavior

Do not import slider assumptions into `click_verify`.

- Start from the smallest behavior model observed at the real `setData`
  boundary. A verified EdgeOne `click_verify` branch passed with passive
  tracker data and no dense trusted pointer path.
- Keep a diagnostic active mode that emits trusted iv8 pointer/mouse events
  when browser evidence shows those events are consumed.
- For a real slider, follow the slider branch: solve the image, keep coordinate
  systems separate, use trusted input, and align path duration with wall time.
- In either branch, let real time elapse before verify when the browser does.
  Do not write a long duration into telemetry and submit immediately.

Collect length is not a quality target. Fresh successful runs can legitimately
produce different lengths, and an iv8 run may be much shorter than a browser
run while still passing. `tlg` must describe the exact transmitted `collect`
for that request, but its value must not be compared to a browser sample as a
hard failure condition. Tune state and semantics, not padding; judge the
attempt by the final Tencent response.

### Runtime Compression

Optimize wait time only after a stable same-round implementation passes. For a
`click_verify` passive branch, do not preserve a long browser dwell as a fixed
sleep without proving that the server requires it.

Use fresh challenges to probe a descending ladder such as:

```text
known passing wait -> 2.0 -> 1.5 -> 1.0 -> 0.5 -> 0 seconds
```

For every point, download a new TDC, solve a new POW, and require final Tencent
success. Record requested wait, local behavior elapsed time, process wall time,
POW time, collect length, and the final business fields. A verified passive
EdgeOne branch continued to pass at zero additional wait; this is evidence for
that `click_verify` branch, not a global TCaptcha constant.

Keep mode-aware defaults:

- passive `click_verify` may default to zero extra wait only after at least two
  consecutive fresh successes;
- active/trusted-event mode keeps the minimum wall time established by its
  event path and rejects an explicitly shorter value;
- image sliders preserve real recognition, drag, and track duration even when
  a passive branch can run immediately;
- retain an explicit wait override for conservative replay and version-change
  diagnosis.

Separate performance layers before changing code. If local TDC behavior takes
about a few hundred milliseconds but the command is slow, inspect first-hop,
prehandle, dynamic-TDC download, verify, page-check, TLS, and POW separately.
A TLS failure before prehandle never reached the CAPTCHA timing gate and must
not be counted as evidence that a tested wait value failed. Do not cache old
`sess`, TDC, telemetry, or POW to reduce network time.

## POW And Verify Form

Use the algorithm named by the current `pow_cfg`. For the observed MD5 branch,
find a nonce such that:

```text
md5(prefix + decimal_nonce) == pow_cfg.md5
```

Send the matching concatenated answer and measured calculation time. Do not
copy either from a browser sample.

The common verify form is:

```text
collect=<decoded TDC.getData(true) output>
tlg=<exact length of the transmitted collect string>
eks=<TDC.getInfo().info>
sess=<fresh prehandle sess>
ans=<answer object for the current show_type>
pow_answer=<fresh solved value>
pow_calc_time=<measured calculation time>
```

For an observed `click_verify` branch, `ans` used
`DynAnswerType_TIME`. Derive this from the current widget/prehandle branch; do
not reuse it for a slider or image challenge.

Preserve the browser's content type, Origin, Referer, and form serialization.
Save a redacted request manifest plus exact local `collect` and `eks` files.

## Success And Failure Diagnosis

Prehandle `state == 1` only means challenge setup succeeded. Verify HTTP 200 is
also insufficient.

Tencent verification is successful only when all are true:

```text
HTTP response is received
errorCode == "0"
ticket is non-empty
randstr is non-empty
```

HTTP 200 alone, `state == 1`, non-empty `collect`/`eks`, POW completion, or
matching `tlg` length is insufficient. Save the final response as the primary
acceptance artifact and keep the exact same-round request materials beside it.

Treat `errorCode == "12"` as a broad risk rejection, not proof that one named
field is wrong. Diagnose it in this order:

1. stale or cross-round `sess/tdc.js/collect/eks/POW`;
2. wrong `show_type`, answer shape, `setData` values, call order, or `ft`;
3. fake elapsed time or events that finish after the request is sent;
4. iframe/global/environment first divergence;
5. UA, Client Hints, Cookie, Origin/Referer, TLS/HTTP2, proxy, or source-IP
   incoherence;
6. hard residuals such as cross-origin `window.top` or WebGL branches.

If an exact locally generated request succeeds when replayed from the browser,
the cryptographic and serialization layers are likely correct; focus on
Session, timing, transport, and environment admission. If browser and local
both fail, refresh the challenge before changing the model.

## Artifacts To Retain

Create one immutable directory per attempt under project `js_reverse_cache/`:

- initial protected page or first-hop error;
- prehandle response and exact request URL;
- dynamic `tdc.js` and its source URL;
- browser baseline and TDC environment-diff summary;
- captured `setData/getData/getInfo` sequence;
- current widget `ft` producer;
- `collect`, `eks`, tracker summary, and POW metadata;
- redacted verify request, raw verify response, and final summary;
- optional ticket replay result kept separate from CAPTCHA success.

Do not copy one-time `sess`, ticket, cookies, full fingerprint dumps, or target
secrets into this skill.

## Acceptance Criteria

The implementation is complete only when:

1. each run obtains a fresh prehandle response and its dynamic TDC;
2. final execution is Python + iv8 with no browser process;
3. challenge globals, widget data, POW, telemetry, and verify remain same-round;
4. success uses `errorCode == "0"` plus non-empty ticket and randstr;
5. at least two consecutive fresh runs pass;
6. optional business-page replay is reported separately from CAPTCHA success;
7. Python files pass `py_compile` and reconnaissance hooks/routes are removed.
8. For an image point-click implementation, at least one unconsumed fresh
   round passes through browser-free iv8 execution with the server-side success
   markers above; browser-only success is supporting evidence, not the final
   implementation proof.
