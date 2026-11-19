# Case: T'way (`www.twayair.com`) IV8 protocol

Live-verified pure-protocol shape for a modern Akamai collector that uses
`bm_*` cookies more than classic `_abck` / `bm_sz`.

Project-local ops notes also live in the task repo:
`TROUBLESHOOTING.md` (egress triage + env vars). Keep **generic** lessons here;
keep **day-to-day runbook** in the project doc.

## Evidence surfaces

- Random-path collector script on the origin (path rotates; role stable)
- Multi-stage sensor POST (`application/json`, body sizes vary, e.g. ~4.5k / ~0.3k / ~1.2k)
- Cookies: `ak_bmsc`, `bm_s`, `bm_so`, `bm_ss`, `bm_sv`, `bm_mi`, `bm_lso`
- Pixel branch: `/akam/13/<id>` script + `POST /akam/13/pixel_<id>`
- Business gate: `POST /app/booking/chooseItinerary` can 403 even when homepage/main/sensor are 200
- Under bad egress: even `GET /app/main` becomes Access Denied after a correct landing sensor
- Coexisting non-Akamai queue: NetFunnel (`csnf.twayair.com/ts.wseq`)

## Architecture that worked

```text
Python curl_cffi Session
  -> GET /
  -> GET collector (+ GET /akam/13/* pixel script when present)
  -> iv8 sensor stage (landing; multi-post settle; optional multi-pass)
  -> pixel fallback POST if IV8 did not emit pixel
  -> NetFunnel enter / complete
  -> GET /app/main
  -> iv8 sensor stage (main, multi-post settle toward ~3 posts)
  -> optional pre-choose sensor
  -> POST getLowestFare (XHR, X-CSRF-TOKEN from main page)
  -> GET discountCodeRule (when default/user promo exists)
  -> GET chkSaleRoute (same serialized search payload as choose)
  -> POST chooseItinerary
  -> if SBSD soft page: solve challenge then re-POST wrapped form
  -> POST layerAvailabilityList
  -> parse fares
```

Python owns every real HTTP request and the cookie jar.
IV8 only executes the live collector and emits XHR intent through a bridge.

## Failure modes observed

| Symptom | Real cause | Wrong rabbit hole |
|---|---|---|
| Browser OK, script `chooseItinerary` 403 | first diff business warmup/form/header against current browser success; then inspect sensor confidence | immediately rewrite Akamai algorithm |
| **Same code works after proxy node switch** | **egress reputation** | “code regressed again” |
| Landing sensor + NetFunnel OK, `GET /app/main` 403 | egress / session hard gate | NetFunnel ticket format |
| CSRF refresh says missing on HTTP 200 | extract from `meta[name=_csrf]` / form with `_extract_csrf` | session dead |
| Foreign `js_reverse_cache` works on author PC only | canvas / system color / WebGL bound to another GPU | code regression |
| Chrome MCP blocked, Edge manual passes | recon browser fingerprint | pure TLS alone |
| Same proxy IP: browser 200, curl root 403 | transport/IP reputation for non-browser clients | payload serialization |
| Browser success packet replayed through curl Chrome profile still 403, but Edge/Safari/Firefox profiles 200 | `chooseItinerary` transport-profile admission | CSRF/form/cookie/sensor rewrite |
| Sensor body always ~4.5KB once then stop | settle loop exits after first post | wrong Content-Type only |
| `getLowestFare` 403 before choose | missing `X-CSRF-TOKEN` / wrong XHR header shape / missing route-local context | SBSD solve or collector rewrite |
| OW form 403 with “valid” CSRF | form fields diverge from **current** browser success capture | NetFunnel ticket |
| choose 200 ~4KB “Powered and protected by Privacy” | SBSD soft challenge, not business success | treat as tickets OK |
| IV8 floods HEAD `chrome-extension://...` | collector extension probe; bridge must drop quietly | allow_dynamic every path |

## Egress intermittency (2026-07 field note)

T'way is a textbook case where **implementation correctness and availability diverge**:

1. Correct multi-stage sensor + pixel + coherent TLS can still 403 on a dirty exit.
2. Switching to a clean residential/node exit can restore full tickets without code changes.
3. Under bad egress, even headed Edge with cleared cookies may Access Denied on `/app/main`.

Ops rule used successfully:

1. Browser-check `/app/main` on the **same exit**.
2. Access Denied in browser → **change node**, do not rewrite form fields first.
3. Browser OK, protocol only fails → inspect sensor post count, pixel, TLS/UA, form capture.

## Local fingerprint policy

Do **not** reuse another machine's:

- `cloak_canvas_profile.json` / `canvas_profile.json`
- `collector_canvas_profiles.json`
- `cloak_system_colors.json`
- hardcoded WebGL renderer strings (e.g. RTX 5070 Ti on a 3050 laptop)

Capture on the execution host:

1. canvas dataURL used by collector sizes
2. system colors
3. unmasked WebGL vendor/renderer
4. hardwareConcurrency / deviceMemory / screen / dpr

Align IV8 environment fields to that capture. Keep one baseline; do not mix
Chrome layout sample + Firefox TLS + foreign GPU strings.

## Multi-stage sensor settle

Browser success often emits **more than one** collector POST before business submit.

Implementation rules:

- do not stop the event loop after the first `postCount >= 1`
- keep advancing timers and emit light mouse/input events so later stages fire
- accept collector HTTP 200 and 202
- track post count growth; reset settle window when a new POST appears
- log body sizes; varied sizes (large then short) are a good signal
- landing may need **multi-pass** when the gate is elevated
- if pixel is present in HTML but IV8 never posts it, add a same-origin pixel fallback

## Business contract notes

- Prefer the real browser form serialization from a **fresh** successful capture
- For OW (2026-07 live Chrome capture): only `availabilitySearches[0]` is filled;
  segments `1..4` stay **empty** (do not invent reverse airports unless the live
  capture shows them)
- `promoCode` may equal `defaultPromoCode` even when user promo is empty; a blank
  promo can desync the server-side search state
- Do not jump straight from `/app/main` to `chooseItinerary` when the browser did
  business warmup. A 2026-07 successful Chrome path required
  `getLowestFare -> discountCodeRule -> chkSaleRoute -> chooseItinerary`.
- `getLowestFare` is a POST XHR and must carry `X-CSRF-TOKEN` from the main page;
  if this request 403s, fix XHR header shape/CSRF/route-local cookies before
  touching Akamai sensor logic.
- `chkSaleRoute` query must use the same serialized search payload that choose
  will submit, including empty fields and repeated `pax` values.
- `chooseItinerary` is a document navigation POST; match Accept / Origin / Referer / UA / Client Hints
- After choose 200, availability is a separate XHR (`layerAvailabilityList`) with CSRF from the choose page
- TLS/UA coherence is still the default bias, but T'way may gate a business document POST by `curl_cffi` transport profile more than visible UA. Validate with same-packet replay before changing sensor/form logic.
- Edge profile with Chrome UA/Client-Hints passed a 2026-07 `chooseItinerary` hard gate after all Chrome profiles (`chrome131` through `chrome146`) failed 403. Keep `AKAMAI_CURL_PROFILE` overrideable and record the admission matrix.

## 2026-07 root-cause lesson

One session looked like an Akamai/SBSD failure until a headed Chrome success packet
was captured on a clean exit. The final root cause split in two:

1. Before switching proxy nodes, headed/incognito browser also 403ed. Treat this as
   **egress-gated** and change node before changing code.
2. After Chrome succeeded, Python still failed because the business contract was
   stale: no `getLowestFare` / `discountCodeRule` warmup, no `X-CSRF-TOKEN` on
   `getLowestFare`, blank `promoCode`, and an invented reverse OW segment.

After aligning that chain, the same Python + local IV8 fresh session reached
`layerAvailabilityList` 200 and parsed `TW301/TW303/TW305/TW307`. Use this as the
default diagnostic bias for T'way-style failures: **browser success first proves
egress; then diff warmup XHR and form serialization before deepening Akamai logic**.

## 2026-07 transport-profile lesson

Another failure presented as `chooseItinerary retry could not refresh main page CSRF:
HTTP 200`, but the real first failure was a 404B Akamai `Access Denied` on
`POST /app/booking/chooseItinerary`. Browser Chrome 150 could submit the same route
and reach `layerAvailabilityList` 200.

The decisive test was same-packet replay:

1. Export a fresh browser-success `chooseItinerary` request including raw headers,
   Cookie, CSRF, and body.
2. POST that exact packet with `curl_cffi` profiles.
3. Chrome-family profiles (`chrome`, `chrome131`, `chrome136`, `chrome142`,
   `chrome145`, `chrome146`) all returned 403.
4. `edge`, `safari260`, and `firefox147` returned 200 with the same application
   packet.

This proves the blocker was transport-profile admission (TLS/H2/client behavior),
not form serialization, CSRF extraction, browser cookies, or IV8 sensor generation.
For this case, switching the Python default `CURL_PROFILE` to `edge` while keeping
the proven Chrome UA/Client-Hints surface restored full protocol replay.

## Body-size taxonomy (quick)

| Body | Meaning |
|---|---|
| ~400–550B Access Denied | hard egress/session gate |
| ~4KB Privacy / `sec-if-cpt-container` | SBSD soft challenge |
| ~1MB choose HTML | business document success |
| ~300KB+ `layerAvailabilityList` | fare/list success |

## Recon browser preference

When ordinary Chrome automation is transport-gated:

1. Prefer `js-reverse` with **Microsoft Edge** (`launch_browser({browser:"edge"})`)
2. Use Camoufox only as anti-detect recon if Edge is insufficient
3. If automation still cannot submit business forms, open headed Edge/Camoufox and let the user operate while the MCP captures sensor/choose/layer packets

Never seed the final Python jar from those reconnaissance cookies. Use the capture only as shape evidence.

## Acceptance

A pure-protocol run is accepted only when:

- landing and main sensor posts succeed and rotate `bm_s`
- `chooseItinerary` returns 200 without Access Denied **and** without SBSD soft page
- availability parse returns flight/fare objects
- summary is written under task `js_reverse_cache/last_run_summary.json`

If success requires a specific proxy exit, document it as **egress-gated residual risk**, not as “implementation flaky”.
