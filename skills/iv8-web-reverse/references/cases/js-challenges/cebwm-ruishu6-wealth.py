# ============================================================
# Disclaimer
# This example is for educational iv8 API usage reference only.
# Users must comply with the target site's terms and applicable laws.
# ============================================================

import json
import re
import sys
import urllib.parse
from pathlib import Path

import iv8
import requests

try:
    from loguru import logger  # pyright: ignore[reportMissingImports]
except ImportError:
    class PrintLogger:
        @staticmethod
        def info(message, *args):
            if args:
                message = message.format(*args)
            out = getattr(sys.stdout, "buffer", None)
            if out:
                out.write((message + "\n").encode("utf-8", errors="replace"))
                out.flush()
            else:
                print(message)

    logger = PrintLogger()


START_PAGE = 1
PAGE_COUNT = 3
PAGE_SIZE = 10
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
PAGE_URL = "https://www.cebwm.com/wealth/grlc/index.html"
API_PATH = "/eportal/ui?moduleId=12073&pageId=107232499&portal.url=/app/wealthlccpFrontAction!queryWealthlccpProducts.portlet"

CACHE_DIR = Path.cwd() / "js_reverse_cache"
CACHE_DIR.mkdir(exist_ok=True)


def clean_runtime_cache(patterns=("*.js", "*.html")):
    deleted = []
    for pattern in patterns:
        for path in CACHE_DIR.glob(pattern):
            if path.is_file():
                path.unlink()
                deleted.append(path)
    return deleted


def save_text(name, text):
    path = CACHE_DIR / name
    path.write_text(text or "", encoding="utf-8", errors="ignore")
    return path


def cookie_header_to_dict(cookie_header):
    cookies = {}
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key:
            cookies[key] = value
    return cookies


def update_session_cookies(session, cookie_text):
    cookies = cookie_header_to_dict(cookie_text)
    if cookies:
        session.cookies.update(cookies)
    return cookies


def build_environment(page_url):
    parsed = urllib.parse.urlparse(page_url)
    return {
        "location": {
            "ancestorOrigins": {},
            "href": page_url,
            "origin": f"{parsed.scheme}://{parsed.netloc}",
            "protocol": f"{parsed.scheme}:",
            "host": parsed.netloc,
            "hostname": parsed.hostname or "",
            "port": str(parsed.port or ""),
            "pathname": parsed.path or "/",
            "search": f"?{parsed.query}" if parsed.query else "",
            "hash": f"#{parsed.fragment}" if parsed.fragment else "",
        },
        "navigator": {
            "userAgent": UA,
            "platform": "Win32",
            "language": "zh-CN",
            "languages": ["zh-CN", "zh", "en"],
            "webdriver": False,
        },
        "screen": {"width": 1920, "height": 1080, "availWidth": 1920, "availHeight": 1040},
    }


def base_headers(referer=PAGE_URL):
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Referer": referer,
        "Upgrade-Insecure-Requests": "1",
    }


def extract_rs_script_url(html, base_url):
    patterns = [
        r"<script[^>]+src=[\"']([^\"']+\.js[^\"']*)[\"'][^>]*\br=[\"']m[\"']",
        r"<script[^>]+\br=[\"']m[\"'][^>]+src=[\"']([^\"']+\.js[^\"']*)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return urllib.parse.urljoin(base_url, match.group(1))
    srcs = re.findall(r"<script[^>]+src=[\"']([^\"']+\.js[^\"']*)[\"']", html, re.I)
    if srcs:
        return urllib.parse.urljoin(base_url, srcs[-1])
    raise RuntimeError("challenge page did not contain a Ruishu JS URL")


def fetch_rs_stage(session, page_url, index, cookie_text=""):
    headers = base_headers(page_url)
    if cookie_text:
        headers["Cookie"] = cookie_text
    response = session.get(page_url, headers=headers, timeout=30, allow_redirects=False)
    html_path = save_text(f"cebwm_stage{index}_page.html", response.text)
    logger.info("stage{} page status={} saved={}", index, response.status_code, html_path)

    js_url = extract_rs_script_url(response.text, page_url)
    js_headers = {**base_headers(page_url), "Accept": "*/*"}
    if cookie_text:
        js_headers["Cookie"] = cookie_text
    js_response = session.get(js_url, headers=js_headers, timeout=30)
    js_path = save_text(f"cebwm_stage{index}_rs.js", js_response.text)
    logger.info("stage{} rs js status={} url={} saved={}", index, js_response.status_code, js_url, js_path)
    return response, js_url, js_response.text


def load_rs_page(ctx, name, page_url, html, js_url, js_code, response):
    snapshot = {
        "baseURL": page_url,
        "html": html,
        "headers": [[key, value] for key, value in response.headers.items()],
        "resources": {js_url: js_code},
    }
    ctx.expose(snapshot, name)
    ctx.eval(f"window.__iv8__.page.load(window.__iv8__.data.{name})")
    ctx.eval("window.__iv8__.eventLoop.sleep(500)")
    return ctx.eval(
        """
        (function() {
            var entries = window.__iv8__.netLog.entries;
            var last = entries.length ? entries[entries.length - 1] : null;
            return {cookie: document.cookie || (last && last.cookieHeader) || '', href: location.href};
        })();
        """,
        to_py=True,
    )


def build_body(page):
    return f"inputQueryStr=&pageKeyStr=lccp14&currentPage={page}&isGrlcStr=1&qclx=&cpFlbs=0"


def capture_wrapped_request(ctx, page):
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "request-by": "ajax-request-tag",
        "response-type": "text",
        "X-Requested-With": "XMLHttpRequest",
    }
    ctx.expose({"url": API_PATH, "body": build_body(page), "headers": headers}, "directXhr")
    before = ctx.eval("window.__iv8__.netLog.entries.length")
    ctx.eval(
        """
        (function() {
          var input = window.__iv8__.data.directXhr;
          var xhr = new XMLHttpRequest();
          xhr.open('POST', input.url, true);
          for (var key in input.headers) {
            try { xhr.setRequestHeader(key, input.headers[key]); } catch (e) {}
          }
          xhr.send(input.body);
          window.__iv8__.eventLoop.sleep(1200);
        })();
        """
    )
    entries = ctx.eval(
        """
        (function(start) {
          var entries = window.__iv8__.netLog.entries;
          return entries.slice(start).map(function(e) {
            return {method: e.method, url: e.url, headers: e.headers || [], body: e.body || '', cookieHeader: e.cookieHeader || ''};
          });
        })(%d);
        """ % before,
        to_py=True,
    )
    return next(entry for entry in entries if entry.get("method") == "POST" and "/eportal/ui" in entry.get("url", ""))


def replay_entry(session, entry, cookie_text):
    headers = {key: value for key, value in entry.get("headers") or []}
    headers["Referer"] = PAGE_URL
    headers["Origin"] = "https://www.cebwm.com"
    headers["Cookie"] = entry.get("cookieHeader") or cookie_text
    return session.post(entry["url"], headers=headers, data=entry.get("body") or "", timeout=30)


def main():
    clean_runtime_cache()
    session = requests.Session()
    try:
        with iv8.JSContext(environment=build_environment(PAGE_URL), config={"timezone": "Asia/Shanghai"}) as ctx:
            response1, js_url1, js_code1 = fetch_rs_stage(session, PAGE_URL, 1)
            stage1 = load_rs_page(ctx, "stage1", PAGE_URL, response1.text, js_url1, js_code1, response1)
            cookie1 = stage1.get("cookie") or ""
            update_session_cookies(session, cookie1)

            response2, js_url2, js_code2 = fetch_rs_stage(session, PAGE_URL, 2, cookie1)
            stage2 = load_rs_page(ctx, "stage2", PAGE_URL, response2.text, js_url2, js_code2, response2)
            cookie2 = stage2.get("cookie") or cookie1
            update_session_cookies(session, cookie2)

            for page in range(START_PAGE, START_PAGE + PAGE_COUNT):
                entry = capture_wrapped_request(ctx, page)
                response = replay_entry(session, entry, cookie2)
                data = response.json()
                out = CACHE_DIR / f"cebwm_collect_page_{page}.json"
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("page={} status={} rows={} saved={}", page, response.status_code, len(data.get("resultList") or []), out)
    finally:
        deleted = clean_runtime_cache()
        if deleted:
            logger.info("cleaned runtime cache files={}", len(deleted))


if __name__ == "__main__":
    main()
