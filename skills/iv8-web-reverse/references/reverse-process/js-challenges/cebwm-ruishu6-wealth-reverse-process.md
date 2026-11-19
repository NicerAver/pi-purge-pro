# CEBWM Ruishu6 Wealth Reverse Process

## Target

- Site: 光大理财, `www.cebwm.com`
- Page: `https://www.cebwm.com/wealth/grlc/index.html`
- API: `/eportal/ui?moduleId=12073&pageId=107232499&portal.url=/app/wealthlccpFrontAction!queryWealthlccpProducts.portlet`
- Protection: Ruishu/RS6 two-stage cookie plus XHR transport wrapper.
- Transport fields: `7ibksfL8` in URL and `vgL7Kuyn=...` in POST body.

## Key Discovery

The browser XHR looked encrypted in Network, but the server returned plain JSON when the iv8-generated URL/body were replayed by Python `requests`. Therefore the stable path is not browser RPC and not pure crypto porting:

1. Use iv8 to execute the RS challenge/runtime locally.
2. Create the business XHR inside iv8.
3. Read the final rewritten URL, headers, cookie header, and `vgL7Kuyn` body from `__iv8__.netLog.entries`.
4. Replay that exact request with Python `requests`.
5. Parse the plain JSON response directly.

## Workflow

1. Request the target page with one `requests.Session`.
2. The first response is HTTP `412`; extract the `r="m"` RS script URL.
3. Download the RS script and load `{baseURL, html, headers, resources}` through `__iv8__.page.load(...)`.
4. Read `document.cookie` or the last `netLog` `cookieHeader` to obtain the first-stage `pXlaX0mT0vLDO/LDP` cookies.
5. Request the page again with the stage-1 cookie; the response is HTTP `200` with another RS runtime script.
6. Load the second-stage page/runtime in the same iv8 context to initialize the XHR wrapper.
7. Do not load the full business page resources if iv8 DOM errors appear. Only the RS runtime is required for the XHR wrapper.
8. Build the plain business form body, for example `inputQueryStr=&pageKeyStr=lccp14&currentPage=1&isGrlcStr=1&qclx=&cpFlbs=0`.
9. In iv8, create `new XMLHttpRequest()`, set the AJAX headers, and send the plain body to the clear API path.
10. Read the generated POST entry from `__iv8__.netLog.entries`; its URL contains `7ibksfL8=...` and its body is `vgL7Kuyn=...`.
11. Replay the captured POST entry with Python `requests.post(...)` in the same session/cookie chain.
12. Parse the response JSON; the response is plain text JSON, not a `vgL7Kuyn` blob in this iv8 replay path.
13. Clean runtime cache files after collection: remove temporary `*.js` and `*.html` files from `js_reverse_cache/`, while preserving final `cebwm_collect_page_*.json` outputs.

## Reusable Pattern

- Use this case when a Ruishu/RS6 target has both challenge cookies and a protected XHR body or URL wrapper.
- If full page `page.load` triggers DOM/NodeList errors, load only the RS stage pages and manually create the target XHR in iv8.
- Keep one `requests.Session` for page fetches, RS JS downloads, cookie updates, and final replay.
- Regenerate the wrapped URL/body per page; do not reuse old `7ibksfL8` or `vgL7Kuyn` values.
- Add a small cache cleanup helper for repeated runs. The RS stage HTML/JS files are runtime inputs, not long-term artifacts; delete them before/after the run unless the user asks to keep debug materials.

## Verification From The Original Run

- `cebwm_collect_iv8.py` collected pages `1-3` successfully.
- Each replay returned HTTP `200`.
- Each page returned `10` JSON rows.
- Output files were saved as `js_reverse_cache/cebwm_collect_page_1.json`, `..._2.json`, and `..._3.json`.
- The runtime cleanup removed temporary stage `.html` and `.js` files after collection, leaving only the final page JSON outputs.

## Common Pitfalls

- Replaying a stale `7ibksfL8` with an old body returns `400` or empty output.
- Hooking browser `XMLHttpRequest` after RS loads may miss calls because RS caches native references in closures.
- Trying to fully load the final business page in iv8 can trigger DOM `NodeList::CreateFromNativeCollection` errors; manual XHR is smaller and more stable.
- Do not treat this as browser RPC. No browser is needed at runtime; iv8 is the local JS runtime that generates the transport wrapper.
