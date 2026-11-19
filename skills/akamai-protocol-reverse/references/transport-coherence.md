# Transport Coherence

Akamai can reject before application semantics. Treat transport as a separate gate.

## Coherence tuple

Keep these fields consistent:

```text
TLS/HTTP2 impersonation version
User-Agent major version
sec-ch-ua brands and versions
sec-ch-ua-platform / mobile
sensor navigator.userAgent / platform
language and timezone
proxy exit and session cadence
```

Example mistake: `curl_cffi` impersonates Chrome 142 while sensor and Client Hints claim Chrome 150. A homepage may still pass while a route or business API is reset.

## Profile inventory before admission triage

Before attributing a browser-200/protocol-403 split to the exit:

1. Record `curl_cffi.__version__`.
2. Enumerate the installed `curl_cffi.requests.BrowserType` values; do not rely on a remembered profile list.
3. Upgrade within the project's allowed dependency range when the installed build lacks current profiles.
4. Test the newest available profile and one older control with profile-matched UA, Client Hints, and sensor UA.
5. Pin the minimum proven `curl_cffi` version in the deliverable.

A sharp cutoff where older profiles 403 and newer profiles 200 on the same exit is a transport-profile generation gate, not egress reputation. See `case-vueling-sbsd.md`.

## Admission matrix

Test only enough cells to isolate the gate:

| Route | Client | HTTP | Proxy | Result |
|---|---|---|---|---|
| `/` | Chrome/Edge profile | h2 | explicit/direct | status/body |
| business route | same | h2 | same | status/reset |
| collector POST | same | h2 | same | status |
| business form/API | same | h2 then h1 fallback | same | status/reset |

Do not multiply routes, profiles, and proxies at once.

When ordinary Chrome automation is blocked but the user can browse manually:

1. Switch recon to Edge (`js-reverse` `browser:"edge"`) before blaming the algorithm.
2. Compare same-exit curl_cffi root status vs browser root status.
3. If curl root is 403 while browser is 200, inventory and test current profiles first; then fix transport or exit based on the matrix.

## Proxy rules

- Print `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` during startup.
- Decide whether to honor them. Prefer `trust_env=False` and one explicit proxy setting in deliverables.
- A local proxy address is not the server-visible exit. Repeated tests may degrade one shared exit.
- Do not silently rotate IPs to hide a failing sensor implementation.
- **Do** change exit when the same implementation fails with Access Denied on the business document route **and** a real browser on that same exit also fails. That is egress reputation, not an algorithm regression.

## Intermittent Access Denied triage

When a previously green pure-protocol client suddenly 403s:

1. Browser-check the business document route on the **same exit**.
2. If browser is also Access Denied → switch node/IP first; re-run full chain.
3. If browser works but protocol fails → compare TLS/UA coherence, sensor post count/body sizes, pixel branch, then form serialization.
4. Do not thrash form fields or CSRF extractors while the exit itself is blocked.

Success that only returns after a node change must be reported as **egress-gated**, even when the code is correct.

## Coherent working profile

The working impersonation profile does not have to equal the reconnaissance browser major. It does have to be coherent across TLS, HTTP headers, and sensor runtime. Record both majors and why the selected tuple passed admission.

Do not preserve a stale UA merely because it appeared in an older browser capture. Derive UA and `sec-ch-ua` from the selected profile unless live evidence requires an explicit exception.

## Retry rules

- Retry only transport errors that are plausibly transient.
- Limit retries and add backoff; repeated H2 resets can worsen exit reputation.
- Keep the same logical session cookie state across a transport reconnect.
- Do not call a reset a successful response.
- Save the last successful output separately from failure diagnostics.
