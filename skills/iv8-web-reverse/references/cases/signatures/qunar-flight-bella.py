# ============================================================
# Disclaimer / Disclaimer
# This example is for authorized research and iv8 API reference only.
# Use only with a session and target access you are authorized to use.
# ============================================================
"""Qunar domestic flight list: Python requests + iv8 Piccolo/Bella replay.

Runtime materials are discovered from the current page and saved under the
current working directory's js_reverse_cache/qunar-flight-bella/. Fill the
empty COOKIE_HEADER constant locally; QN668, pre, Bella, __m__, and the dynamic
header are regenerated for every request.
"""

import hashlib
import json
from datetime import date as calendar_date, timedelta
import re
import time
import urllib.parse
from pathlib import Path
from typing import Mapping

import iv8
import requests


CACHE_DIR = Path.cwd() / "js_reverse_cache" / "qunar-flight-bella"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEPARTURE = "长沙"
ARRIVAL = "北京"
DATE = "2026-08-26"
DEPARTURE_CODE = "CSX"
ARRIVAL_CODE = "BJS"
COOKIE_HEADER = ""
try:
    SEARCH_ARRIVAL_TIME = (calendar_date.fromisoformat(DATE) - timedelta(days=1)).isoformat()
except ValueError:
    SEARCH_ARRIVAL_TIME = DATE
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)
PAGE_URL = (
    "https://flight.qunar.com/site/oneway_list.htm?"
    + urllib.parse.urlencode(
        {
            "searchDepartureAirport": DEPARTURE,
            "searchArrivalAirport": ARRIVAL,
            "searchDepartureTime": DATE,
            "searchArrivalTime": SEARCH_ARRIVAL_TIME,
            "nextNDays": "0",
            "startSearch": "true",
            "fromCode": DEPARTURE_CODE,
            "toCode": ARRIVAL_CODE,
            "from": "flight_dom_search",
            "lowestPrice": "null",
        }
    )
)
API_URL = "https://flight.qunar.com/touch/api/domestic/wbdflightlist"


def parse_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in raw.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name:
            cookies[name] = value
    return cookies


def encode_qn668(timestamp_ms: int | None = None) -> str:
    """Current site format: each timestamp digit's code point plus two."""
    timestamp = str(timestamp_ms or int(time.time() * 1000))
    comma_codes = ",".join(str(ord(char) + 2) for char in timestamp)
    return urllib.parse.quote(comma_codes, safe="")


def decode_qn668(value: str) -> int:
    parts = urllib.parse.unquote(value).split(",")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError("QN668 has an unexpected format")
    return int("".join(chr(int(part) - 2) for part in parts))


def replace_cookie(session: requests.Session, name: str, value: str) -> None:
    for cookie in list(session.cookies):
        if cookie.name == name:
            session.cookies.clear(cookie.domain, cookie.path, cookie.name)
    session.cookies.set(name, value, domain=".qunar.com", path="/")


def dynamic_header(cookies: Mapping[str, str]) -> tuple[str, str, int]:
    token = urllib.parse.unquote(cookies.get("QN48", ""))
    if not token:
        raise ValueError("QN48 is a required user session seed")
    timestamp = decode_qn668(cookies["QN668"])
    raw = f"{token}{timestamp}".encode("utf-8")
    sha1_hex = hashlib.sha1(raw).hexdigest()
    md5_hex = hashlib.md5(raw).hexdigest()
    value = hashlib.sha1(md5_hex.encode("ascii")).hexdigest() if timestamp % 2 else hashlib.md5(sha1_hex.encode("ascii")).hexdigest()
    key_source = "".join(str(ord(char)) for char in str(timestamp)[4:])
    name = hashlib.md5(key_source.encode("ascii")).hexdigest()[-6:]
    return name, value, timestamp


def extract_page_material(html: str) -> tuple[str, list[str], str]:
    script_urls = [
        urllib.parse.urljoin(PAGE_URL, url)
        for url in re.findall(r"<script\b[^>]+\bsrc=[\"']([^\"']+)", html, flags=re.I)
    ]
    script_urls = list(dict.fromkeys(script_urls))
    bundle_url = next((url for url in script_urls if "qlogTemp" in url and "piccolo" in url), "")
    if not bundle_url:
        raise RuntimeError("Current page does not expose a Piccolo qlog bundle URL")
    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, flags=re.I | re.S)
    def looks_like_pt_generator(script: str) -> bool:
        compact = re.sub(r"\s+", "", script)
        return bool(
            re.search(
                r"=['\"]_['\"];var_0x[0-9a-f]+=['\"]p['\"];var_0x[0-9a-f]+=['\"]t['\"]",
                compact,
                flags=re.I,
            )
        )

    pt_script = next((script for script in inline_scripts if looks_like_pt_generator(script)), "")
    if not pt_script:
        raise RuntimeError(
            "Could not identify the current inline _pt_ generator. Use an Edge property setter on "
            "window._pt_ before page scripts run, record the assignment stack, then update the "
            "structural extractor."
        )
    return pt_script, script_urls, bundle_url


def build_environment() -> dict:
    parsed = urllib.parse.urlparse(PAGE_URL)
    return {
        "location": {
            "href": PAGE_URL,
            "origin": f"{parsed.scheme}://{parsed.netloc}",
            "protocol": f"{parsed.scheme}:",
            "host": parsed.netloc,
            "hostname": parsed.hostname or "",
            "port": str(parsed.port or ""),
            "pathname": parsed.path,
            "search": f"?{parsed.query}",
            "hash": "",
        },
        "navigator": {
            "userAgent": UA,
            "appVersion": UA,
            "platform": "Win32",
            "vendor": "Google Inc.",
            "productSub": "20030107",
            "appName": "Netscape",
            "language": "zh-CN",
            "languages": ["zh-CN", "en", "en-GB", "en-US"],
            "hardwareConcurrency": 16,
            "deviceMemory": 16,
            "maxTouchPoints": 0,
            "webdriver": False,
            "userAgentData": {"platform": "Windows", "mobile": False},
        },
        "window": {
            "innerWidth": 1528,
            "innerHeight": 732,
            "outerWidth": 1536,
            "outerHeight": 816,
            "devicePixelRatio": 1.25,
            "screenX": 0,
            "screenY": 0,
            "isSecureContext": True,
        },
        "screen": {
            "width": 1536,
            "height": 864,
            "availWidth": 1536,
            "availHeight": 816,
            "colorDepth": 24,
            "pixelDepth": 24,
        },
        "document": {
            "referrer": "https://flight.qunar.com/site/oneway_list.htm",
            "readyState": "complete",
            "visibilityState": "visible",
            "domain": "flight.qunar.com",
            "characterSet": "UTF-8",
            "bodyWidth": 1513,
            "bodyHeight": 2791,
        },
    }


def generate_protocol_values(
    page_html: str,
    bundle: str,
    cookies: Mapping[str, str],
    fields: Mapping[str, str],
) -> tuple[str, str]:
    pt_script, script_urls, _ = extract_page_material(page_html)
    dom_html = re.sub(r"<script\b[^>]*>.*?</script>", "", page_html, flags=re.I | re.S)
    with iv8.JSContext(
        environment=build_environment(),
        config={"timezone": "Asia/Shanghai", "time": {"mode": "logical"}},
        time_mode="logical",
    ) as ctx:
        ctx.eval(
            "window.__iv8__.page.load(" + json.dumps({"baseURL": PAGE_URL, "html": dom_html}) + ");",
            name="qunar-page-load.js",
        )
        # The inline generator checks page script src values before writing window._pt_.
        ctx.eval(
            "(function(urls){var root=document.head||document.documentElement;urls.forEach(function(src){var s=document.createElement('script');s.src=src;root.appendChild(s);});document.title='\\u7f51Qunar.com';var k=document.querySelector('meta[name=keywords]');if(k)k.content=',Qunar.com';var d=document.querySelector('meta[name=description]');if(d)d.content='\\u53bb\\u54ea\\u513f(Qunar.com)\\u4f5c\\u4e3a\\u5168\\u7403\\u6700\\u5927';})(" + json.dumps(script_urls) + ");",
            name="qunar-script-nodes.js",
            devtools=False,
        )
        ctx.eval(
            "Object.defineProperty(document,'children',{configurable:true,value:{length:1,item:function(i){return i===0?document.documentElement:null;}}});Object.defineProperty(document,'referrer',{configurable:true,get:function(){return 'https://flight.qunar.com/site/oneway_list.htm';}});",
            name="qunar-wasm-dom-patch.js",
            devtools=False,
        )
        for name, value in cookies.items():
            ctx.eval("document.cookie=" + json.dumps(f"{name}={value}; path=/") + ";", devtools=False)
        ctx.eval(
            "window.__ptWrites=[];let __ptValue='';Object.defineProperty(window,'_pt_',{configurable:false,get:function(){return __ptValue;},set:function(next){window.__ptWrites.push(String(next));__ptValue=String(next);}});",
            name="qunar-pt-setter.js",
            devtools=False,
        )
        ctx.eval(pt_script, name="qunar-inline-pt.js", devtools=False)
        pre = str(ctx.eval("window._pt_ || ''", devtools=False) or "")
        if len(pre) != 46:
            raise RuntimeError("Expected a 46-character page-bound pre value")
        # Bella's environment captures the two Piccolo device script sources, not page scripts.
        ctx.eval(
            "(function(){Array.from(document.getElementsByTagName('script')).forEach(function(s){s.removeAttribute('src');});['https://rmcsdf.qunar.com/a.js','https://rmcsdf.qunar.com/b.js'].forEach(function(src){var s=document.createElement('script');s.src=src;document.head.appendChild(s);});window._st_='';window.piccoloT='default';})();",
            name="qunar-bella-script-shape.js",
            devtools=False,
        )
        ctx.eval(bundle, name="qunar-piccolo-qlog.js", devtools=False)
        for _ in range(60):
            ctx.eval("window.__iv8__.eventLoop.drainMicrotasks();", devtools=False)
            ctx.eval("window.__iv8__.eventLoop.drain();", devtools=False)
            ctx.eval("window.__iv8__.eventLoop.sleep(50);", devtools=False)
            ctx.eval("window.__iv8__.eventLoop.drainMicrotasks();", devtools=False)
            ctx.eval("window.__iv8__.eventLoop.drain();", devtools=False)
        bella = str(ctx.eval("window.Bella(" + json.dumps(dict(fields), ensure_ascii=False) + ")", devtools=False))
        if len(bella.split("##")) != 6:
            raise RuntimeError("Expected native Piccolo WASM Bella with six segments")
        return pre, bella


def main() -> None:
    if not COOKIE_HEADER:
        raise SystemExit("Fill COOKIE_HEADER with a current authorized Qunar session Cookie header")
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    session.cookies.update(parse_cookie_header(COOKIE_HEADER))
    page = session.get(PAGE_URL, timeout=30)
    page.raise_for_status()
    (CACHE_DIR / "page.html").write_text(page.text, encoding="utf-8")
    _, _, bundle_url = extract_page_material(page.text)
    bundle_response = session.get(bundle_url, timeout=30)
    bundle_response.raise_for_status()
    (CACHE_DIR / "piccolo-qlog.js").write_text(bundle_response.text, encoding="utf-8")

    replace_cookie(session, "QN668", encode_qn668())
    cookies = session.cookies.get_dict()
    header_name, header_value, qt_time = dynamic_header(cookies)
    fields = {
        "departureCity": DEPARTURE,
        "arrivalCity": ARRIVAL,
        "departureDate": DATE,
        "ex_track": "",
        "__m__": hashlib.md5(header_value.encode("ascii")).hexdigest(),
        "st": str(int(time.time() * 1000)),
        "sort": "",
    }
    pre, bella = generate_protocol_values(page.text, bundle_response.text, cookies, fields)
    body = {**fields, "Bella": bella, "_v": "4"}
    headers = {
        "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://flight.qunar.com",
        "Referer": PAGE_URL,
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "pre": pre,
        "csht": "",
        "w": "2",
        header_name: header_value,
    }
    response = session.post(API_URL, data=body, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    print(
        json.dumps(
            {
                "http_status": response.status_code,
                "ret": payload.get("ret"),
                "qt_time": qt_time,
                "bella_parts": len(bella.split("##")),
                "flight_count": len(data.get("flights") or []),
                "total": data.get("total"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
