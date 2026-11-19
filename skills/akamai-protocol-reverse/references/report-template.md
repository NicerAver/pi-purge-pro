# Report Template

```markdown
## Startup Gate
- Authorization/scope:
- Akamai evidence:
- Family (`_abck` / `bm_*` / mixed):
- Recon browser (Edge / Chrome / Camoufox):
- Local fingerprint source (host-captured / foreign rejected):
- Delivery intent:

## Recon
- Final page URL:
- Collector URL discovery rule:
- Pixel URL discovery rule:
- Sensor/SBSD POST count and body-size sequence:
- SBSD script URL / `v` / `t` / final POST URL:
- SBSD payload fields (`ver`, `signals`, `perf`, `s`, `tid`):
- Mutation initiator:
- Observer effect:

## Cookie Provenance
- Initial server seeds:
- Sensor/SBSD stage transitions (`_abck` / `bm_s` / `bm_sc` / `sbsd_c` / `ak_bmsc` rotate?):
- SBSD pass-cookie shape (`2~1`, `4~1`, other):
- Pixel transition:
- Route-local transition:
- Final outbound authority:

## SBSD / CPR
- Trigger evidence (`cpr_chlge`, `{"body":...}`, script URL, cookies):
- Dynamic key template source:
- Timestamp / `bm_so_hash` / integrity-key dynamic names:
- Key115 trace evidence:
- Body encryption proof (`v` seed, shuffle, reverse-decrypt/parity):
- Result cookie and business replay status:

## Transport
- curl_cffi profile:
- UA / Client Hints / sensor major:
- HTTP version:
- Proxy policy and exit IP:
- Reset/rate behavior:

## Business Contract
- Endpoint/method:
- Server context / CSRF / queue sources:
- Required headers:
- Query/body serialization vs browser success pack:
- Response envelope / parser output:

## Delivery
- Collector path:
- Dynamic cache path:
- Output path:
- Pure Python or Python + IV8:
- Browser dependency: none

## Verification
- Fresh successful runs:
- Multi-stage sensor/SBSD checks:
- SBSD key115/body parity checks:
- Host-local fingerprint checks:
- Unit/syntax tests:
- Known instability:
```
