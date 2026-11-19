# ============================================================
# 免责声明 / Disclaimer
# 本示例仅供学习 iv8 API、WAF challenge 生命周期和请求回放使用。
# 使用者应遵守目标网站服务条款及所在地区法律法规。
# ============================================================

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import iv8
import requests


API_URL = "https://api.cdfsunrise.com/restapi/search/list"
REFERER = "https://h5.cdfsunrise.com/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
REQUEST_BODY = {
    "filter": {},
    "pageNumber": 1,
    "pageSize": 10,
    "keys": {"7": "263"},
    "order": 1,
    "activityIds": [],
    "frontCateIds": [],
    "frontBrandIds": [],
    "param": {
        "category": "%20",
        "cid": "263",
        "cmsPageId": "1cd71e2661000",
        "fromSearchUrl": "1",
        "order": "1",
        "originFrom": "h5",
        "platform": "h5",
        "purchaseType": "1",
        "scene": "qpol",
        "searchField": "%E7%83%AD%E5%8C%BA%E7%BB%84%E4%BB%B6",
        "stamp": "AA",
        "status": "0",
    },
    "sceneId": 0,
    "priceExp": True,
}

CASE_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = CASE_DIR / "js_reverse_cache" / "cdfsunrise-md5-1803"
CACHE_DIR = Path.cwd() / "js_reverse_cache"
CACHE_DIR.mkdir(exist_ok=True)
INLINE_ORIGINAL = (ASSET_DIR / "01-aliyunwaf_6a6f5ea8.js").read_text(encoding="utf-8")
EXTERNAL_ORIGINAL = (ASSET_DIR / "02-psk8uqfi.decoded.js").read_text(encoding="utf-8")
BODY_TEXT = json.dumps(REQUEST_BODY, ensure_ascii=False, separators=(",", ":"))

HEADERS = {
    "User-Agent": UA,
    "Referer": REFERER,
    "Content-Type": "application/json;charset=UTF-8",
    "UserSystem": "h5platform",
    "Miniapp": "h5",
    "AppVersion": "1.60.0",
    "ClientNetwork": "unknown",
    "Mobile": "",
    "AccessToken": "",
    "Device": "",
    "Deviceid": "",
    "Openid": "",
    "AlipayOpenid": "",
    "Unionid": "",
}


def print_utf8(text: str) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        print(text)
        return
    stream.write((text + "\n").encode("utf-8", errors="replace"))
    stream.flush()


def build_environment() -> dict[str, Any]:
    return {
        "location": {
            "href": API_URL,
            "origin": "https://api.cdfsunrise.com",
            "protocol": "https:",
            "host": "api.cdfsunrise.com",
            "hostname": "api.cdfsunrise.com",
            "pathname": "/restapi/search/list",
            "search": "",
            "hash": "",
        },
        "navigator": {
            "userAgent": UA,
            "platform": "Win32",
            "language": "zh-CN",
            "languages": ["zh-CN", "zh", "en"],
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "webdriver": False,
            "maxTouchPoints": 0,
        },
        "screen": {
            "width": 1536,
            "height": 864,
            "availWidth": 1536,
            "availHeight": 816,
            "colorDepth": 24,
            "pixelDepth": 24,
        },
    }


def patch_external(source: str) -> str:
    old_zi = r"function u1(){return Zi=u0(QARDLm['toString'](),'QARDLm','\x31\x65\x30\x30\x39\x65\x61'),'5rGzyCeeHxhGk9';}"
    patched = source.replace(old_zi, "function u1(){return Zi=632,'5rGzyCeeHxhGk9';}", 1)
    patched = patched.replace(
        "):gJ-=gw;",
        "):gJ-=gw,gw=Math[z5(Tm.DZ)](gw/(0x637+0x1ffa+-0xd8d*0x3+Zi));",
        1,
    )
    return patched


def extract_initializer(html: str) -> str:
    scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html, re.IGNORECASE)
    for script in scripts:
        if "_waf_bd8ce2ce37" in script:
            return script
    raise RuntimeError("fresh WAF initializer not found")


def make_dom_snapshot(html: str) -> str:
    dom = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    return dom.replace(
        "</html>",
        '<!--<script name="aliyunwaf_6a6f5ea8">'
        + INLINE_ORIGINAL
        + "</script>--></html>",
    )


def generate_signed_url(challenge_html: str, acw_tc: str) -> tuple[str, str]:
    marker = INLINE_ORIGINAL.find("var Lt=")
    if marker < 0:
        raise RuntimeError("inline WAF closure marker not found")
    exposed_inline = (
        INLINE_ORIGINAL[:marker]
        + "\nwindow.__wafLK = LK; window.__wafL3 = L3; window.__wafLf = Lf;\n"
        + INLINE_ORIGINAL[marker:]
    )
    outer_end = INLINE_ORIGINAL.rfind("}());")
    if outer_end < 0:
        raise RuntimeError("inline WAF outer closure marker not found")
    outer_source = INLINE_ORIGINAL[1 : outer_end + 1]

    with iv8.JSContext(environment=build_environment(), time_mode="system") as ctx:
        snapshot = {
            "baseURL": API_URL,
            "html": make_dom_snapshot(challenge_html),
            "headers": [["content-type", "text/html"]],
        }
        ctx.eval("window.__iv8__.page.load(" + json.dumps(snapshot, ensure_ascii=False) + ");")
        if acw_tc:
            ctx.eval("document.cookie=" + json.dumps("acw_tc=" + acw_tc + "; path=/"))
        ctx.eval(extract_initializer(challenge_html), name="https://api.cdfsunrise.com/challenge-init.js")
        ctx.eval(patch_external(EXTERNAL_ORIGINAL), name="https://api.cdfsunrise.com/u21pn7x6/r8lw5pzu/psk8uqfi")
        to_string_patch = (
            "(function(){var n=Function.prototype.toString;var s="
            + json.dumps(outer_source, ensure_ascii=False)
            + ";Function.prototype.toString=function(){if(this&&this.name==='Lblfpo')return s;return n.call(this);};})();"
        )
        ctx.eval(to_string_patch)
        ctx.eval(exposed_inline, name="https://api.cdfsunrise.com/challenge-inline.js")
        result = ctx.eval(
            "(function(){var u=window.__wafLK("
            + json.dumps(API_URL)
            + ","
            + json.dumps(BODY_TEXT, ensure_ascii=False)
            + ",'POST',2);return {url:String(u),cookie:document.cookie};})()",
            to_py=True,
        )
    if not result or not result.get("url"):
        raise RuntimeError("LK returned an empty URL")
    return str(result["url"]), str(result.get("cookie", ""))


def merge_acw_tc(session: requests.Session, cookie_header: str) -> None:
    for item in cookie_header.split(";"):
        if "=" not in item:
            continue
        name, value = item.strip().split("=", 1)
        if name == "acw_tc":
            session.cookies.set(name, value, domain="api.cdfsunrise.com", path="/")


def main() -> int:
    body = BODY_TEXT.encode("utf-8")
    session = requests.Session()
    challenge = session.post(API_URL, headers=HEADERS, data=body, timeout=30)
    (CACHE_DIR / "cdfsunrise-md5-1803-challenge.html").write_text(
        challenge.text, encoding="utf-8"
    )
    if challenge.status_code != 200 or "text/html" not in challenge.headers.get("content-type", ""):
        raise RuntimeError("API did not return a WAF challenge page")

    start = time.time()
    signed_url, iv8_cookie_header = generate_signed_url(
        challenge.text, challenge.cookies.get("acw_tc", "")
    )
    merge_acw_tc(session, iv8_cookie_header)
    response = session.post(signed_url, headers=HEADERS, data=body, timeout=30)
    print(f"challenge_status={challenge.status_code}")
    print(f"replay_status={response.status_code}")
    print(f"replay_content_type={response.headers.get('content-type', '')}")
    print(f"iv8_seconds={time.time() - start:.2f}")

    try:
        payload = response.json()
    except ValueError:
        print_utf8(response.text[:1000])
        return 1
    head = payload.get("responseHead", {})
    print(f"responseHead.isSuccess={head.get('isSuccess')}")
    print(f"responseHead.code={head.get('code')}")
    print(f"totalCount={payload.get('totalCount')}")
    print_utf8(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if response.status_code == 200 and head.get("code") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
