# 9air Black Box Reverse Process

Read this before using `references/cases/signatures/9air-black-box.py`.

## Goal

Generate the dynamic TrustDecision `black_box` value in iv8, attach it to the `Anti-Headers` header, and replay the 9air `searchflight` API with one Python `requests.Session`.

## Browser Findings

- Page: `https://www.9air.com/zh-CN/book/booking`.
- The page loads `https://static.trustdecision.com/tdfp/cn/.../fm.js`.
- The page module initializes `window._fmOpt` with `partner="9air"`, `appName="9air_web"`, and `interfaceProtection=true`.
- The SDK success callback writes its result to `sessionStorage.currentBlackBox`.
- The request interceptor reads that value and builds `Anti-Headers`.
- `searchflight` is a GET request. Its route fields come from `flightCondition`; the dynamic value is only in the header.

## Reconstruction Steps

1. Create one `requests.Session` and bootstrap the booking page.
2. Fetch the current hourly TrustDecision `fm.js`; use the frozen asset only as a fallback.
3. Create an iv8 context with the 9air location, navigator, screen, window, and Asia/Shanghai timezone.
4. Load a minimal same-origin document with `__iv8__.page.load`.
5. Set `_fmOpt` before evaluating `fm.js`.
6. Route SDK XHR through a Python bridge and inject the real response with `ctx.add_resource`.
7. Advance iv8 timers and microtasks until `_fmOpt.success` stores a non-empty `black_box`.
8. Rebuild the `searchflight` query and `Anti-Headers` from the current search fields and current generated value.
9. Print the response's flight segments, adult fares, product names, prices, taxes, discounts, and remaining inventory.

## Important Details

- The useful delivery is not a hard-coded `black_box`; regenerate it for every session/request chain.
- `iv8` supplies the browser object surface used by this SDK. The custom patch is the XHR-to-Python bridge and response injection.
- Do not treat an HTTP 200 alone as acceptance; require a structured `data.flights` response and print the business payload.
- `COOKIE_HEADER` is intentionally empty. A clean `requests` bootstrap can generate the SDK value but may not create the browser-side `gdxidpyhxdE` session state required by `searchflight`; with an empty value the case prints the generated value and skips business replay.
- Fill `COOKIE_HEADER` only in a private local run with a current browser session when replaying `searchflight`. Never bundle that value.
- The bundled SDK is a frozen fallback. A changed TrustDecision bundle should be refreshed from the current page before diagnosing environment differences.

## Verified Result

The source case produced a non-empty 26-character `black_box`; two fresh runs generated different hashes. The same-session `searchflight` replay returned HTTP 200 with payload status 200 and structured flight/product/fare data.
