# Case: Vueling Akamai Bot Manager + SBSD/CPR

Use this case as transport and state-machine evidence, not as a source of reusable cookies, collector URLs, profile guarantees, or fingerprints.

## Confirmed protection surfaces

The target exposed both classic Bot Manager and SBSD/CPR surfaces:

```text
_abck / bm_sz / sensor_data
bm_s / bm_so / bm_lso
random same-origin collector scripts
/_sec/cpr/params
JSON {"body": ...} collector traffic in browser capture
```

The business chain was:

```text
POST /asm/v1/Auth
GET  /asm/v1/Session
POST /avy/v3/AvailabilityServices/allFlights
```

The final client used one fresh Python HTTP/cookie session plus a local Node VM for captured collector execution. It did not start a browser or import browser cookies.

## Transport profile generation cliff

The first Python attempts failed at the document request before sensor execution:

```text
GET /booking/flightSearch -> 403 Access Denied
```

A real Chrome on the same machine and URL returned 200. Header changes, non-Akamai preference cookies, HTTP/2 setting variants, HTTP/3, and older browser profiles did not change the result.

The decisive matrix was the installed `curl_cffi` profile generation:

```text
curl_cffi 0.15.0
chrome101 through chrome136 -> document 403
chrome142 / chrome145 / chrome146 -> document 200
```

General lesson:

1. Record the installed `curl_cffi` version and enumerate its actual `BrowserType` values.
2. Test the newest available profiles with profile-matched UA and Client Hints before labeling a same-exit browser/protocol difference as egress reputation.
3. A sharp old/new profile cutoff on the same exit is transport-profile admission evidence.
4. Do not assume the reconnaissance browser major is the only usable impersonation major. Use a coherent working tuple and record the difference.
5. Pin the minimum dependency version that supplies the proven profile.

Example profile inventory:

```python
import curl_cffi
from curl_cffi.requests import BrowserType

print(curl_cffi.__version__)
print([profile.value for profile in BrowserType])
```

## Successful fresh state machine

With a coherent recent profile, two independent fresh sessions produced:

```text
GET  flightSearch document     -> 200
GET  collector 1              -> 200
POST collector 1 sensor_data  -> 201, refresh _abck
GET  /_sec/cpr/params          -> 200, refresh bm_s
GET  dynamic collector 2      -> 200
POST Auth                     -> 200
GET  Session                  -> 200
POST allFlights               -> 200, structured rows
```

The local collector 2 execution completed without a missing-runtime error but emitted zero JSON POSTs. The same-session entry, collector-1, and CPR state was nevertheless sufficient for Auth, Session, and the business API to succeed repeatedly.

General lesson: browser capture defines candidate branches, not an unconditional requirement that every local run emit every observed request. If a stage is absent locally:

- do not call it optional merely because its script returned without error;
- first prove the business response in at least two independent fresh sessions;
- record the missing observed branch and the successful cookie/state path;
- classify it as non-gating only for the tested route and current policy;
- keep support for the branch because policy or route conditions can change.

If business replay fails, return to lifecycle, timers, cookie mirroring, and branch predicates rather than skipping the stage.

## Dynamic collector URL rule

CPR returned a fresh second collector URL. An early implementation also appended and fetched an old captured fallback URL. That extra stale request produced a connection close and made a healthy chain appear unstable.

Use this rule:

1. Prefer exact same-origin URLs parsed from the current document or CPR response.
2. Deduplicate current URLs.
3. Use a captured fallback only when no runtime URL was discovered.
4. Do not append a captured random path after current discovery succeeds.
5. Treat a stale collector path as evidence only, never a production constant.

## Runner artifact isolation

Collector 1 and collector 2 initially shared fixed runner input/output files. Parallel diagnostics could read the other collector's output and falsely attribute a POST.

Use a unique run id or temporary directory for every local JS execution:

```text
runner_runs/input_<run-id>.json
runner_runs/output_<run-id>.json
```

Return those paths in diagnostics. Run-id isolation is required even if production calls are currently serial, because probes and tests may run concurrently.

## Minimum failure diagnostics

Record each network boundary with:

```text
method / URL / status / elapsed
akamai-grn / server-timing / x_req_id
Set-Cookie names
cookie names after response
curl_cffi version and profile
UA and sec-ch-ua
explicit proxy configured or not
text body preview for failures
```

These fields made it possible to distinguish old-profile admission 403 from collector, CPR, Auth, or business failures without copying sensitive cookie values into reports.
