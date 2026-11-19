# MTCaptcha v1 Workflow

This reference covers browser-free recovery of the MTCaptcha v1 text challenge flow. It is based on a verified `service2.mtcaptcha.com` implementation and should be rechecked against the current client bundle and fresh server responses before reuse.

## Route Signals

Use this branch when the page or network evidence contains one or more of:

```text
MTCaptcha
mtcaptcha2.min.js
service*.mtcaptcha.com
/mtcv1/api/getchallenge.json
/mtcv1/api/getimage.json
/mtcv1/api/solvechallenge.json
mt.v1.01
hasTextChlg
foldChlg
```

A lone image or a request to use generic OCR does not trigger this protocol branch. OCR is a substep only when the requested result includes the MTCaptcha verifier response.

## Verified State Machine

The observed protocol is:

```text
fresh session id
  -> GET /mtcv1/api/getchallenge.json
  -> GET /mtcv1/api/getimage.json
  -> recognize or supply the current text answer
  -> GET /mtcv1/api/solvechallenge.json
  -> inspect verifyResult
```

The three requests must share the same fresh round state. Never combine a current image with an old `ct`, `ss`, `fseed`, `fa`, `kt`, `fs`, or token. A successful or failed solve consumes the round; create a new session and challenge for another attempt.

A useful sidecar records non-secret metadata such as:

```text
round id / session id
sitekey / hostname / service origin
client bundle version
ct and fseed hashes, not necessarily full values
textlen / fslots / fdepth / preRes
image dimensions and image hash
request order and timestamps
final service code / isVerified / vt-present
```

Do not put full verified tokens, machine-specific absolute paths, browser profile data, or historical one-time challenge values into a reusable skill or report.

## Request Inputs

The observed challenge request uses the following conceptual fields:

```text
sk   sitekey
bd   hostname
rt   current request time in milliseconds
tsh  transaction signature
act  action marker, observed as $
ss   fresh S-prefixed session id
lf   low-friction marker
 tl  text/language marker, observed as $
lg   language, observed as en
tp   challenge type, observed as s
```

The image request binds the current `sk`, `ct`, `fa`, and `ss`. The solve request binds the same `ct`, `sk`, `ss`, answer, current `rt`, `tsh`, fold fields, and telemetry. Preserve the exact parameter names, URL encoding, Referer shape, and request order from the current bundle capture.

For the observed site, the transaction signature is an MD5 digest of the fixed operation string concatenated with the sitekey, wrapped as:

```text
TH[md5(operation + sitekey)]
```

Treat the operation string and formula as bundle-derived facts, not universal MTCaptcha constants. Reconfirm them after a client version change.

## `fa` and FoldChlg

When `hasFoldChlg` is true, retain the current `fseed`, `fslots`, `fdepth`, and `preRes` values. The URL-safe alphabet is:

```text
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_ 
```

For the verified v1 client, `fseed` is decoded to six-bit integers. The fold operation reverses a copy of the array and repeatedly updates each position using the corresponding offset value, the previous two rolling values, multiplication by 73, integer division by 8, and modulo 64. The implementation must match JavaScript integer behavior, including signed 32-bit hashing where the bundle uses it.

The observed `preRes` behavior is:

```text
preRes=true:
  calculate the folded value before getimage
  submit the same image fa in solvechallenge

preRes=false:
  use $ for getimage
  calculate the folded solve value immediately before solvechallenge
```

The exact fold depth and slot count come from the current challenge. Do not hardcode the values from a captured round. Validate the implementation against a captured `preRes=true` image response and a separate fresh `preRes=false` solve response.

## `kt` Telemetry

The observed text challenge includes a short 64-character key-history field derived from `fseed`. It records the first changed character, elapsed time before the first key, inter-key intervals, and a fixed tail marker. The browser quantizes elapsed values into the bundle's time buckets and caps each bucket.

For a local implementation:

1. Initialize the telemetry clock when the image round becomes available.
2. Emit cumulative answer prefixes, for example `A`, `AM`, `AMW`, `AMWY`.
3. Use real increasing timestamps or a controlled delay model consistent with the accepted browser sample.
4. Keep `kt`, `fseed`, answer, `ct`, and `ss` from the same round.
5. Treat the server response, not the 64-character shape, as proof that telemetry is correct.

A failed solve followed by a success after changing timing is only a single-variable clue. Repeat on a fresh round and retain the accepted timing as a hypothesis until independently confirmed.

## OCR Substep

For the current four-character image style, `ddddocr` can recognize the returned GIF bytes directly, but decorative clouds and backgrounds can create an extra leading character. A practical recognition path is:

1. Instantiate `ddddocr.DdddOcr(show_ad=False)` lazily so protocol-only users do not need the dependency.
2. Try proportional crops that remove the left and right decoration, encoding each crop as PNG.
3. Keep the original GIF as a fallback.
4. Strip characters outside `[A-Za-z0-9$]`.
5. Normalize the OCR candidate to uppercase for the observed case-insensitive text style.
6. Accept a candidate only when its length equals the current `textlen`.
7. Raise a diagnostic error with all raw candidates when no candidate has the required length.

Never silently truncate a five-character OCR result to four characters. A wrong-length result should stop the round or enter an explicit candidate-review path. OCR success is not verifier success; submit the selected answer through `solvechallenge` and inspect the response.

If the challenge changes image dimensions or text length, re-evaluate crop geometry, model behavior, and character normalization. Keep OCR/vision logic separated from protocol parameter generation.

## Acceptance

The formal success condition for this branch is all of:

```text
HTTP 200
payload code == 1200
result.verifyResult.isVerified == true
result.verifyResult.verifiedToken.vt is a non-empty string
```

`HTTP 200`, a valid JSON shape, a plausible `fa`, a 64-character `kt`, or an OCR result alone is not enough. Save a redacted sidecar for at least one fresh accepted round, including the final code, verification flag, token-present boolean, and the round binding metadata.

## Failure Diagnosis

```text
missing challenge/image field
  -> inspect current bundle version and endpoint response shape

service code is not 1200
  -> inspect sitekey, hostname, tsh, Referer, request order, and fresh state

isVerified=false with code=1200
  -> first verify the answer and text normalization
  -> then compare same-round fa/preRes behavior
  -> then compare kt timing and prefix sequence

OCR returns the wrong length
  -> try the decoration-removing crops and inspect all candidates
  -> do not consume the round with a guessed truncation

second attempt on the same ct/ss fails unexpectedly
  -> discard the round; duplicate or consumed state is not a telemetry conclusion
```

Use one changed layer per experiment: answer/OCR, `fa`, telemetry, or transport headers. Each experiment needs a fresh challenge when the previous solve may have consumed state.

## Deliverable Shape

A complete implementation should provide:

```text
fresh challenge/image fetch
same-round state persistence and restore
optional OCR with explicit length validation
fa and tsh helpers
kt generation or a documented telemetry limitation
solvechallenge request
final verifier response parsing
redacted evidence sidecar
```

Browser automation may supply initial request and bundle evidence, but the delivered runner should be able to execute the protocol without Chrome, CDP, browser cookies, or a browser profile.
