# Direct sensor_data Branch: Article Evidence

Source reviewed: `https://mp.weixin.qq.com/s/Sy5GLlnNpR4LQljfhfljGg?scene=1`

The source is a tutorial titled `Akamai sensor_data 全参数拆解与工程实现`. Its useful contribution is a direct, three-stage sensor collector branch. It is evidence for a recovery workflow, not proof that any fixed value or sample algorithm is current on a target.

## Evidence Set

The article was loaded in Edge. The document, visible text, and all 42 downloaded image resources were retained under `<workspace>/akamai_article_assets/`. The screenshots were read directly as images. The screenshots show:

- `toString` preservation logic with a native fallback and selected long function-name cases.
- An XHR breakpoint around `sensor_data`, with the path `dcK -> RNK -> 13b` and a pre-encryption `13b` object.
- `ajr`, `fpt`, `fpc`, ordered `din`, `fwd.ssh`, `mst`, `ver`, and `previousValue` as distinct inputs.
- Three JSON samples compared side by side. The observed stage markers are `ajt=0.0`, `ajt=11.1`, and `ajt=10.2`; the second and third samples carry mouse timing changes, and the third adds `dsi`.
- `sww` assembled asynchronously through `SharedWorker`, including UA, GPU, network, locale, timezone, screen/runtime and User-Agent Client Hints data.
- Random-looking fields such as `s148`, `s151`, `s153`, and `s150`; the screenshots do not justify hardcoding them.
- The final wrapper using `bm_sz`, a script-derived `previousValue`, and `ver` before the encrypted JSON is sent.

The article's own examples also show `fwd.fmz="1.75"`. This is a field value in one observed collector and must not be confused with the excluded legacy 1.7/1.75 generator family.

## Recovery Procedure

1. Capture the first document, every `Set-Cookie`, the exact Akamai script URL, and the exact collector POST URL. Do not assume that the script URL is also the POST destination.
2. Keep one fresh HTTP session for the document, script, all collector stages, and the business replay. Record request cookies separately from the stored jar and from response cookie updates.
3. In a disposable reverse-execution context, preserve the native `Function.prototype.toString` fallback only where the current collector's format checks require it. Remove logging and hooks from the final runtime.
4. Break on the request body or its construction and capture the pre-encryption object. If function location or AST restoration is required, hand that work to `trace`; this branch consumes the resulting runtime evidence and does not turn AST rewriting into its trigger.
5. Build a semantic field map from the current script and run, rather than copying names or order from the article. Preserve `din` array order exactly as produced by the current script.
6. Capture stage zero, one, and two independently. The tutorial's field differences are useful hypotheses: `ajr` and `ran` rotate, `tovl` grows with mouse data, `dme`/`doe` carry timing, `ajt` changes by stage, `mc` moves from zero to the observed mouse count, and `dsi` may appear only in the third stage.
7. Treat `mouse_finger` as lifecycle data. The article observed 21 points as sufficient for one sample, but the count, timestamps, and last timestamp are target/runtime dependent. Preserve event ordering and allow timers and Promise/worker work to settle before each POST.
8. Treat `sww` as asynchronous runtime data. Its fields can include `av`, `dm`, `ext`, `gpu`, `hc`, `la`, `las`, `net`, `pl`, `ts`, `tz`, `ua`, and `uad`, with paired `s024`-style fields in some scripts. A host runtime that lacks `SharedWorker` may need IV8 or a faithful port/message bridge; do not replace the data with a foreign fingerprint cache.
9. Re-derive `fpt`/`fpc`, `ajr`, `dvc`, `nfas`, `fwd.ssh`, `ver`, and `previousValue` from the current collector. `fpt`/`fpc` and the `ajr` divisor/hash branches are especially version-sensitive. `startTs`, `deltaTimestamp`, `totVel`, UA suffixes, random values, and mouse timing must be captured per fresh run.
10. For encryption, prove the current script's equivalent of the article's `bm_sz -> seed`, `Ng` token shuffle, `P7` printable-character transform, and wrapper metadata. The article shows a `bm_sz` decoded `~`-field seed with a `previousValue` fallback, but the delimiter, index, alphabet, and arithmetic must be checked against the live script. Never use a stale sample token or `bm_sz` from another machine.
11. POST sequentially to the exact observed collector URL with the current body framing and headers. A successful POST, a short `_abck`, or HTTP 200 is not completion; prove cookie transitions and a successful business replay twice in independent fresh sessions.

## Replay Corrections

The tutorial's Python sketch is a useful shape but requires these corrections before use:

- `http_version=3` is an observation to test, not a default. Record the actual HTTP version and compare current `curl_cffi` profiles.
- `js_url` is only the script URL until the network trace proves it is the collector endpoint.
- Read the session jar plus response `Set-Cookie` flow; do not assume the first response object contains the authoritative `bm_sz` or later `_abck` update.
- Define the actual UA/header set from the selected transport profile. Do not reference an undefined `headers` variable.
- `ffs`, `vev`, and `inf` are optional only after the current script and accepted request prove they are absent; an empty placeholder is not evidence.
- A script that appears reusable for minutes still needs a content/hash and cookie/session validity check. Never reuse dynamic URLs, `scid`, timestamps, or foreign fingerprint material.
- Save each collector run under a unique run-id and keep successful output separate from failure diagnostics.

## Boundary

This branch is valid only when an Akamai-native marker and independent network/script/cookie corroboration are present. It does not expand the skill to unidentified 403/412 responses, generic sign tracing, DevTools-only hooks, CAPTCHA, or legacy generator ports. SBSD/CPR, Pixel, and `sec_cpt` branches retain their separate state machines and completion criteria.
