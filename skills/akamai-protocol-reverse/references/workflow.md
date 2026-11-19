# Workflow

## Short path

1. Confirm two Akamai evidence surfaces.
2. Capture a clean homepage with recon browsers: prefer `js-reverse` Edge when Chrome is gated; use `chrome-devtools` or Camoufox only as needed.
3. Export the collector GET, **every** sensor/SBSD POST (count + body size + Content-Type), response `Set-Cookie`, and initiator.
4. If SBSD/CPR is present, record the live script URL, `v`/`t` query values, final POST URL, and `bm_s` / `bm_sc` / `sbsd_c` transition.
5. Record the installed `curl_cffi` version/profile inventory, then probe raw HTTP admission with newest-vs-old control profiles.
6. Keep one coherent transport/UA/Client-Hints/sensor-UA tuple and one session.
7. Fetch live HTML and dynamically extract collector, SBSD, and Pixel URLs; use captured random paths only when current discovery yields no URL.
8. For SBSD/CPR `{"body":...}` flows, read `sbsd-body-vmp.md`, recover payload/key115/body encryption, and treat `2~1` / `4~1` cookies as pass evidence only.
9. Run the collector locally only if a pure algorithm port is not already proven.
10. Bridge collector/SBSD XHR to the same Python session and mirror response cookies back into the local runtime before callbacks. Give every local execution a unique run-id input/output path.
11. Request the route, rerun route-local collector/SBSD branch when the page does so, extract server context, and replay one business endpoint.
12. Validate response shape and repeat with fresh sessions.

## Evidence checkpoints

### Checkpoint A: family

Required:

- at least one Akamai-native cookie, collector, Pixel, SBSD `{"body":...}`, `cpr_chlge`, or `sensor_data` marker
- at least one independent network, script, cookie-transition, or transport corroboration

An H2 reset, 403, or cookie name by itself is not enough.

### Checkpoint B: cookie writer

Required:

- initial server seed
- sensor/SBSD request cookie
- sensor/SBSD response `Set-Cookie`
- next sensor/SBSD or business request cookie
- for SBSD/CPR, script `v`/`t`, result cookie (`bm_s` / `bm_sc` / `sbsd_c`), and pass-shape classification

### Checkpoint C: local runtime

Required:

- multi-stage request count matching capture (not just first POST), unless repeated fresh business success proves a captured branch non-gating for the tested route
- non-empty emitted sensor/SBSD bodies with plausible size sequence
- expected 2xx collector/SBSD response (often 200/201/202)
- response cookies applied in the correct order
- host-local fingerprint cache (no foreign GPU/canvas reuse)
- SBSD dynamic-key/key115 proof when the route uses `{"body":...}` instead of classic `sensor_data`
- unique runner artifacts so concurrent collector/SBSD stages cannot be misattributed

### Checkpoint D: business API

Required:

- server context source identified
- exact method/query/body/header contract
- repeated application response, not just a plausible `_abck`

## Stop conditions

Stop and report a blocker when:

- only a real browser can issue every business request
- collector POST works but no business replay succeeds after transport, multi-stage sensor, form serialization, and context checks
- the target requires an interactive CAPTCHA outside the Akamai sensor flow
- required authorization or account state is unavailable

While blocked on pure protocol, it is valid to capture a headed Edge/Camoufox success packet and parse business HTML/JSON for immediate data, but label that output as recon-assisted, not pure-protocol completion.
