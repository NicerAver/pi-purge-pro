# Qunar Flight Bella Reverse Process

Read this note before using `references/cases/signatures/qunar-flight-bella.py`.

## Scope And Acceptance

This is a verified Python `requests` + iv8 replay for Qunar's domestic flight-list endpoint:

```text
POST https://flight.qunar.com/touch/api/domestic/wbdflightlist
```

It is a signature/header and browser-runtime case, not an Akamai, Reese84, CAPTCHA, or browser-automation case. The initial request needs a current authorized Qunar Cookie seed, but the request-specific protocol values are regenerated locally.

A successful replay is not merely HTTP 200. Require all of:

1. HTTP `200`.
2. JSON `ret == true`.
3. `data` is an object containing `flights` and `total`.
4. `len(data.flights) > 0` and `data.total > 0` for a route/date with known inventory.
5. The next request can rebuild all dynamic values without reusing the previous Bella, `pre`, `st`, dynamic header, or `QN668`.

The site can return HTTP `200`, `ret=true`, and an empty flight list when a protocol field is structurally plausible but not session-valid. Treat that as failure.

## Required Baseline

Keep one browser-derived baseline only while investigating. The final case keeps a top-level empty `COOKIE_HEADER` constant for the user to fill locally; do not route the Cookie through a PyCharm/OS environment variable, and do not bundle account cookies, Edge exports, response JSON, private identifiers, or a static `pre`.

The baseline must stay coherent across:

- `User-Agent` and iv8 `navigator.userAgent`.
- Page URL, Referer, and iv8 `location`.
- `QN48` and other identity/session Cookie seeds.
- HTML containing the inline `_pt_` generator.
- The current Piccolo/qlog bundle URL discovered from that same page.

Use the same Python `requests.Session` for the page GET, qlog bundle GET, and final POST. Do not mix a page or qlog file from an older session with a fresh Cookie seed.

## Protocol Inventory

The form field order used by the verified page code is:

```text
departureCity
arrivalCity
departureDate
ex_track
__m__
st
sort
Bella
_v
```

The required headers beyond normal Origin/Referer/UA are:

```text
pre: window._pt_
csht: window._st_ or empty
w: 2
<dynamic six-character name>: dynamic encrypted value
```

The page calls these in order:

```text
encrypt() -> Bella(fields) -> POST wbdflightlist
```

The business request uses form encoding, not a JSON body. Preserve field insertion order and use `requests.post(..., data=body)`.

The page URL also carries airport codes. If adapting the case to another route, update city names and `fromCode`/`toCode` together. The verified list URL uses `searchArrivalTime` as one calendar day before `searchDepartureTime`; keep this page-URL convention separate from the form's `departureDate`.

## Cookie Classification

Do not treat every Cookie as independently reproducible.

| Class | Examples | Handling |
| --- | --- | --- |
| Session/identity seed | `QN48`, `QN1`, `QN25`, `fid`, `Alina`, `QN271` | Supply a current authorized value. Some have client-side creation code, but server-side association may still matter. Do not blindly randomize them. |
| Verified client-refreshable value | `QN668` | Generate before every business request. It is a URL-encoded comma list of each current timestamp digit's character code plus `2`. Remove all old jar entries before inserting the new `.qunar.com` cookie. |
| Request-local page value | `_pt_` / `pre`, `_st_` / `csht` | Generate inside the iv8 page lifecycle. Never copy a prior request's `pre`. |
| Server response update | `QN668` may also appear in `Set-Cookie` after the POST | Let the `requests.Session` receive it, but still generate a fresh value on the next request because the client-side encoding was independently verified. |
| Generic telemetry/display | `QN205`, `QN277`, `QN300`, `QN44`, `QN602` and similar | Preserve initial seed values when present. They were not required to be regenerated for the verified endpoint. |

### QN668 Algorithm

For current `timestamp_ms` as a 13-character decimal string:

```python
encoded = ",".join(str(ord(char) + 2) for char in str(timestamp_ms))
qn668 = urllib.parse.quote(encoded, safe="")
```

The decoder is the inverse: URL-decode, split on commas, subtract two from each decimal value, and join the resulting characters. The decoded value becomes the timestamp input to the dynamic header algorithm.

This was tested by replacing an older valid `QN668` only in memory with a newly generated value. The final replay returned HTTP 200, `ret=true`, and a non-empty flight list. Do not infer from this that `QN48` or device/identity cookies can also be replaced with random values.

## Dynamic Header And __m__

Let `token = URLDecode(QN48)` and `timestamp = DecodeQN668(QN668)`.

```text
raw       = UTF8(token + decimal(timestamp))
sha1_hex  = SHA1(raw).hexdigest()
md5_hex   = MD5(raw).hexdigest()
value     = SHA1(md5_hex) when timestamp is odd
            MD5(sha1_hex) when timestamp is even
name      = MD5(concatenate(ord(c) for c in decimal(timestamp)[4:]))[-6:]
__m__     = MD5(value).hexdigest()
```

Validation before the POST:

- Header name length is `6`.
- Header value length can be `32` or `40`, depending on the timestamp parity branch.
- `__m__` length is `32`.
- Do not accidentally classify fixed headers such as `Origin` or `Referer` as the dynamic header.

## Locating The Page `_pt_` Generator

The page's business bundle only reads:

```js
headers: { w: a.w, pre: window._pt_ || "", csht: window._st_ || "" }
```

The current page creates `_pt_` in a large inline obfuscated script, not in the business bundle and not in the Piccolo qlog bundle. The generator resolves the `_pt_` property name by joining literal `_`, `p`, `t`, and `_` fragments, then assigns a UUID-like 46-character value with group sizes `8-6-8-8-12`.

The bundled extractor deliberately matches that literal-fragment structure instead of obfuscated variable names. It then installs an iv8 setter and accepts the candidate only when it actually writes a 46-character `window._pt_`. If the structural matcher stops finding a candidate, do not replace `pre` with a random same-format string. Instrument Edge before page scripts execute:

```js
window.__ptWrites = [];
let value = "";
Object.defineProperty(window, "_pt_", {
  configurable: false,
  get() { return value; },
  set(next) {
    window.__ptWrites.push({ value: String(next), stack: new Error().stack });
    value = String(next);
  },
});
```

Pause on an early page script, install the setter, resume, then use the recorded assignment stack to identify the new inline script. A non-configurable setter is deliberate: a top-level `var` declaration can otherwise replace a configurable accessor before its assignment is observed.

## iv8 Lifecycle

The inline `_pt_` script inspects page script `src` values. Execute in this order:

1. Fetch the current list page with the same `requests.Session` and save it under the current project `js_reverse_cache/`.
2. Parse all page script URLs and discover the current qlog/Piccolo URL.
3. Strip scripts from the DOM HTML passed to `__iv8__.page.load`; do not automatically execute the full site application.
4. Call `page.load({baseURL, html})` to establish URL and DOM.
5. Create inert `<script src>` nodes for the original page script URLs. They provide the source shape observed by the inline `_pt_` code without loading the whole site bundle graph.
6. Set the exact title, keywords, description, referrer, Cookie seed values, and browser environment fields that the target reads.
7. Apply the documented `document.children` patch before evaluating Piccolo.
8. Evaluate the inline `_pt_` script and require a 46-character `window._pt_`.
9. Replace the page script sources with the two Piccolo device-source placeholders used by the verified Bella environment:

   ```text
   https://rmcsdf.qunar.com/a.js
   https://rmcsdf.qunar.com/b.js
   ```

10. Set `window._st_ = ""` and `window.piccoloT = "default"`.
11. Evaluate the current qlog bundle, drain microtasks/timers, then call `window.Bella(fields)`.
12. Require native Bella to have six `##`-separated segments before replay.

The script-node switch is intentional. The `_pt_` generator and Bella inspect different script-source shapes. Keeping the page script list for Bella changed the third Bella segment and produced a structurally valid but non-equivalent value.

## Native WASM Compatibility Patch

The current Piccolo bundle has a JS fallback and a native WebAssembly branch. The fallback generated a five-segment Bella and the server returned an empty list. The Edge page used the native path and generated six segments.

iv8 initially failed in the native WASM `asDOM` imports because its `document.children.length` was `2`, while the browser contract observed by the module expected `1`. Before evaluating qlog, apply:

```js
Object.defineProperty(document, "children", {
  configurable: true,
  value: {
    length: 1,
    item: function (index) {
      return index === 0 ? document.documentElement : null;
    },
  },
});
```

Do not use this patch as a generic iv8 workaround. First instrument `WebAssembly.instantiate` or the import calls and verify that the failure follows the document-child path. For this case, the important evidence was a sequence ending in document child access, a length of `2`, then an `env.abort` import failure. With the patch, `window.Bella` became a function and native output had six segments.

Drain the iv8 event loop after bundle evaluation. The verified loop uses repeated `drainMicrotasks`, `drain`, `sleep(50)`, `drainMicrotasks`, and `drain` calls. Do not call Bella immediately after evaluating qlog.

## Environment Contract

The known relevant fields included:

- `document.referrer`: list-page URL.
- `document.title`: `网Qunar.com`.
- Meta keywords: `,Qunar.com`.
- Meta description: `去哪儿(Qunar.com)作为全球最大`.
- Browser platform `Win32`, non-webdriver Edge/Chrome UA, screen/window dimensions, language list, and page location.
- The script-source shape described above.

Capture one fresh browser baseline when the current bundle changes. Compare environment field lengths and Unicode code points, not terminal rendering alone, because Chinese text can display incorrectly in logs while still having correct JavaScript code points.

A difference of a few Bella characters is not sufficient proof of failure by itself; compression/randomness can vary. Validate the segment count, expected field dependencies, and final business data.

## Failure Diagnosis

| Symptom | Likely cause | Correct response |
| --- | --- | --- |
| `window.Bella` is undefined | qlog failed to initialize or event loop was not drained | Capture errors/import calls, verify script source and timer drain. |
| Bella has five segments | JS fallback path ran | Investigate native WASM imports; do not call the empty-list response success. |
| WASM aborts in an `asDOM` import | DOM shape mismatch | Compare actual property access. Apply only the required patch; in this case `document.children` must contain one root. |
| `_pt_` is empty | Inline extractor changed or script nodes/Cookies were absent | Use Edge property setter stack evidence and restore original script-source shape. |
| `pre` has UUID-like shape but `flights=[]` | Random/unbound `pre` was used | Execute the page's real inline `_pt_` generator in the current iv8 context. |
| HTTP 200 and `ret=true`, but `total=0` | Any one of fallback Bella, wrong `pre`, stale mixed baseline, or serialization mismatch | Compare Bella segment count, `_pt_` provenance, Cookie source, body order, and dynamic header reconstruction. |
| Dynamic header has wrong length/name | `QN668` decode or odd/even branch is wrong | Regenerate QN668, verify decoded 13-digit timestamp, then recompute all dependent values. |
| A formerly working script breaks after a site update | qlog URL, inline `_pt_` marker, or environment contract changed | Re-fetch page and bundle in one session. Do not reuse frozen runtime materials as production inputs. |

## Safe Artifact Policy

For ordinary future target work, save the live page HTML, qlog bundle, browser environment snapshot, and diagnostics in that project's `js_reverse_cache/`. Do not write them into this skill directory.

This bundled case intentionally stores no frozen HTML or qlog because both are dynamic and a frozen version is more likely to cause a stale-session failure than help reproduction. It contains the discovery and execution pattern instead.

## Final Checklist

Before calling the business POST, assert:

```text
- Current page HTML and qlog were fetched through one requests.Session.
- COOKIE_HEADER contains a current authorized session seed including QN48.
- QN668 was regenerated in memory immediately before header construction.
- pre length is 46 and comes from the inline page script.
- Bella is a non-empty six-segment string.
- __m__ is 32 hex characters.
- Dynamic header name is six hex characters; dynamic header value is 32 or 40 hex characters.
- Form field order and form encoding match the page request.
```

After the POST, report HTTP status, `ret`, `flight_count`, and `total`. Do not claim success from transport status alone.
