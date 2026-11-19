# Akamai `sec_cpt` Crypto Challenge

Use this reference only after Akamai has independent corroboration and a business response exposes a crypto challenge descriptor. A lone `sec_cpt` cookie, `428`, or HTTP/2 reset is not enough to identify this family.

The formulas below describe a verifier family observed in live traffic. Reconfirm them against the current verifier script and accepted browser requests; do not assume every Akamai policy uses the same framing.

## State Machine

Capture and preserve one Python HTTP session through this sequence:

```text
business 428 + challenge descriptor + sec_cpt flag 1
  -> challenge HTML and dynamic verifier script
  -> token-linked proof rounds
  -> final verifier success + sec_cpt flag 2
  -> cp_challenge verification
  -> sec_cpt flag 3
  -> replay the original business request
```

Stop collector retries once the business endpoint returns a valid crypto descriptor. The collector and crypto verifier are separate state machines; extra collector passes can degrade an already admitted `_abck`.

Do not report completion from an intermediate HTTP 200 or `{"success":true,"token":...}`. Completion requires the final verifier response, the expected cookie transition, cp verification, and successful business replay.

## Evidence To Capture

Save these boundaries from one accepted browser chain:

1. The business `428` response body and `Set-Cookie: sec_cpt=...~1~...`.
2. Challenge HTML, dynamic verifier URL, and verifier script.
3. The first, one middle, penultimate, and final verifier request/response.
4. Each request's ordered `answers`, current token, descriptor `timestamp`, `nonce`, `difficulty`, `count`, `timeout`, and `verify_url`.
5. `sec_cpt` before the rounds, after final verifier success, and after cp verification.
6. The original business request replay and parsed success data.

Use an XHR breakpoint on the verifier POST when static obfuscation hides the proof predicate. Inspect the worker/candidate loop's live scope rather than guessing hash concatenations.

## Recover The Proof Predicate

For the observed SHA-256/modulo family, derive and verify all of the following:

```text
sec_prefix = sec_cpt.split("~", 1)[0]
context = sec_prefix + str(current.timestamp) + current.nonce
candidate = Math.random().toString(16)
answer_difficulty = current.difficulty + answer_index
digest = SHA256(context + str(answer_difficulty) + candidate)
valid = int.from_bytes(digest, "big") % answer_difficulty == 0
```

Important invariants:

- Rebuild `context` from the **current round descriptor**. Every successful verifier response can rotate `timestamp`, `nonce`, token, difficulty, count, and verifier URL.
- `count=N` means generate N valid proofs. It does not mean one valid proof plus N-1 random decoys.
- Proof index `i` can use `difficulty + i`; verify this from the live dispatcher or by checking every accepted browser answer. Testing all answers only against the base difficulty creates a false decoy conclusion.
- Preserve answer order.
- Follow the descriptor's current HTTPS `verify_url`; validate same-origin/allowlisted-host constraints before sending. Do not hardcode a captured random verifier path.

Confirm the predicate by replaying accepted browser evidence offline: every answer must produce remainder zero under its indexed difficulty. Also confirm a neighboring random value fails. Only then implement the solver.

## Canonical Candidate Generation

If the verifier uses V8 `Math.random().toString(16)`, arbitrary hexadecimal strings are not equivalent. Generate a 53-bit fraction with canonical base-16 formatting:

```python
def random_answer(rng) -> str:
    digits = f"{rng.getrandbits(53) << 3:014x}".rstrip("0")
    return "0." + (digits or "0")
```

This naturally yields many 14-digit values ending in `8`, while values with removable low zero bits become shorter. Validate the distribution against captured browser answers.

## Timing And Token Chaining

Treat descriptor `timeout` as a per-round worker window unless live evidence disproves it. A local solver may find proofs in milliseconds; submitting immediately can consume token/request limits much faster than the browser.

For each round:

1. Read the current token, descriptor, `count`, and `verify_url`.
2. Generate all indexed valid proofs.
3. Wait out the remaining worker window when browser cadence shows that behavior.
4. POST once in the same cookie-owning Python session.
5. Replace the current descriptor only with the successful response's new values.
6. Stop immediately on final success, explicit failure, missing token, cookie flag transition, duration expiry, or the configured round cap.

Log proof attempts and solve time per index, total round duration, response status, next difficulty/count, and cookie flag. Avoid logging full long-lived cookies in normal output.

## Final Verification

After final verifier success:

1. Require `sec_cpt` flag 2 or the target's independently proven equivalent.
2. Reproduce the browser's cp verification method, host, Origin, Referer, and headers in the same session.
3. Require `sec_cpt` flag 3 or the target's proven final state.
4. Replay the original business request without rerunning collector passes.
5. Parse real business data; a challenge page or generic HTTP 200 is not success.

## Failure Classification

| Evidence | Classification | Action |
|---|---|---|
| Verifier HTTP 200 with next token, difficulty decreases, final `success:false` | Proof framing, indexed answers, rotating context, canonical candidate, or cadence still wrong | Compare every submitted proof against current-round browser evidence |
| `sec_cpt` reaches flag 2 but not flag 3 | cp verification contract mismatch | Capture method/host/headers/cookie transition |
| `sec_cpt` reaches flag 3 but business still fails | Business contract or another gate | Diff current successful business packet; do not rerun collector blindly |
| Fresh browser and protocol both get HTTP/2 protocol errors across several API endpoints while documents/CDN work | Upstream/API incident or shared fresh-session admission issue | Pause, retain evidence, and retest; do not label the PoW implementation broken |
| Persistent daily browser works but fresh browser and fresh protocol fail | Browser state differs; this does not by itself prove or disprove IP reputation | Compare with a fresh browser on the same exit and endpoint |
| Only an unidentified HTTP/2 reset or lone `sec_cpt` cookie exists | Family unconfirmed | Route to `trace` for identification |

## Completion Evidence

A completed report records:

- initial challenge descriptor and `sec_cpt` flag 1
- verifier script provenance and recovered predicate
- round count, indexed proof rule, timing window, and final verifier response
- `sec_cpt` transition 1 -> 2 -> 3
- cp verification response
- original business replay status and parsed business fields
- confirmation that the final runner uses Python HTTP plus local code/IV8 only, with no browser cookies or browser runtime dependency
