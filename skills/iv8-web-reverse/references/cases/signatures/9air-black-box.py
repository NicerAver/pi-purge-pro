# ============================================================
# 免责声明 / Disclaimer
# 本示例仅供学习 iv8 API 用法参考，不构成对任何网站的攻击或未授权访问。
# 使用者应自行遵守目标网站的服务条款及所在地区法律法规。
# 作者不对任何滥用行为承担责任。
#
# This example is for educational purposes only.
# Users must comply with all applicable laws and terms of service.
# The author assumes no responsibility for any misuse.
# ============================================================

import json
import re
import time
import urllib.parse
from pathlib import Path

import iv8
import requests


PAGE_URL = "https://www.9air.com/zh-CN/book/booking"
API_URL = "https://www.9air.com/shop/api/shopping/b2c/searchflight"
FM_BASE_URL = "https://static.trustdecision.com/tdfp/cn/4b945a90244739a2e531c8cd49bced5d/fm.js"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
COOKIE_HEADER = ""
REFRESH_FM = True

SEARCH = {
    "date": "2026-09-01",
    "from_code": "CAN",
    "to_code": "HGH",
    "from_type": "CITY",
    "to_type": "CITY",
    "adult_count": 1,
    "child_count": 0,
    "infant_count": 0,
}

CACHE_DIR = Path.cwd() / "js_reverse_cache"
CACHE_DIR.mkdir(exist_ok=True)
ASSET_DIR = Path(__file__).resolve().parents[1] / "js_reverse_cache" / "9air-black-box"
FROZEN_FM = ASSET_DIR / "trustdecision-fm.js"


BASE_HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh_CN",
    "Referer": PAGE_URL,
}


def environment():
    parsed = urllib.parse.urlparse(PAGE_URL)
    return {
        "location": {
            "href": PAGE_URL,
            "origin": f"{parsed.scheme}://{parsed.netloc}",
            "protocol": f"{parsed.scheme}:",
            "host": parsed.netloc,
            "hostname": parsed.hostname or "",
            "port": str(parsed.port or ""),
            "pathname": parsed.path or "/",
            "search": "",
            "hash": "",
        },
        "navigator": {
            "userAgent": UA,
            "platform": "Win32",
            "language": "zh-CN",
            "languages": ["zh-CN", "zh"],
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "maxTouchPoints": 0,
            "webdriver": False,
        },
        "screen": {
            "width": 1920,
            "height": 1080,
            "availWidth": 1920,
            "availHeight": 1032,
            "colorDepth": 32,
            "pixelDepth": 32,
        },
        "window": {"innerWidth": 1536, "innerHeight": 695, "devicePixelRatio": 1.25},
    }


def load_fm(session):
    hour_token = round(time.time() * 1000 / 3600000)
    url = f"{FM_BASE_URL}?t={hour_token}"
    if REFRESH_FM:
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            (CACHE_DIR / "9air-fm-latest.js").write_text(response.text, encoding="utf-8")
            return response.text, url
        except requests.RequestException as exc:
            print(f"fm.js refresh failed, use frozen asset: {exc}")
    if not FROZEN_FM.exists():
        raise FileNotFoundError(f"missing frozen asset: {FROZEN_FM}")
    return FROZEN_FM.read_text(encoding="utf-8"), str(FROZEN_FM)


def install_xhr_bridge(ctx, session):
    def real_fetch(method, url, body, headers_json):
        headers = dict(BASE_HEADERS)
        if headers_json:
            headers.update(json.loads(str(headers_json)))
        response = session.request(
            str(method).upper(),
            str(url),
            headers=headers,
            data=None if body in (None, "null", "undefined") else str(body),
            timeout=30,
        )
        session.cookies.update(response.cookies)
        print(f"iv8 XHR: {str(method).upper()} {urllib.parse.urlsplit(str(url)).path} -> {response.status_code}")
        ctx.add_resource(
            url=str(url),
            body=response.text,
            status=response.status_code,
            headers=dict(response.headers),
        )

    ctx.expose(real_fetch, "realFetch")
    ctx.eval(r"""
        (function() {
            var open = XMLHttpRequest.prototype.open;
            var send = XMLHttpRequest.prototype.send;
            var setHeader = XMLHttpRequest.prototype.setRequestHeader;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__method = method;
                this.__url = new URL(String(url), location.href).href;
                this.__headers = {};
                return open.apply(this, arguments);
            };
            XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                this.__headers[String(name)] = String(value);
                return setHeader.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function(body) {
                __iv8__.data.realFetch(this.__method, this.__url, body, JSON.stringify(this.__headers));
                return send.apply(this, arguments);
            };
        })();
    """, devtools=False)


def generate_black_box(session, source, source_name):
    with iv8.JSContext(
        environment=environment(),
        config={"timezone": "Asia/Shanghai", "time": {"mode": "system"}},
        time_mode="system",
    ) as ctx:
        ctx.eval("window.__blackBox=''; window.__fmErrors=[]; window.__iv8__.page.load({baseURL:" + json.dumps(PAGE_URL) + ",html:'<!doctype html><html><body></body></html>'});", devtools=False)
        ctx.eval("window._fmOpt={partner:'9air',appName:'9air_web',interfaceProtection:true,success:function(v){window.__blackBox=String(v);sessionStorage.setItem('currentBlackBox',String(v));},fail:function(e){window.__fmErrors.push(String(e));}};", devtools=False)
        for cookie in session.cookies:
            ctx.eval("document.cookie=" + json.dumps(f"{cookie.name}={cookie.value}; path=/"), devtools=False)
        install_xhr_bridge(ctx, session)
        ctx.eval(source, name=source_name, devtools=False)
        for _ in range(12):
            ctx.eval("window.__iv8__.eventLoop.advance(500)", devtools=False)
            ctx.eval("window.__iv8__.eventLoop.drainMicrotasks()", devtools=False)
            if ctx.eval("window.__blackBox.length > 0", devtools=False):
                break
        result = ctx.eval("({value:window.__blackBox,errors:window.__fmErrors})", to_py=True, devtools=False)
    if not result["value"]:
        raise RuntimeError(f"black_box generation failed: {result['errors']}")
    return result["value"]


def build_query():
    condition = (
        f"index:0;depCode:{SEARCH['from_code']};arrCode:{SEARCH['to_code']};"
        f"depDate:{SEARCH['date']};depCodeType:{SEARCH['from_type']};arrCodeType:{SEARCH['to_type']};"
    )
    return {
        "language": "zh_CN",
        "currency": "CNY",
        "flightCondition": condition,
        "channelNo": "B2C",
        "tripType": "OW",
        "groupIndicator": "I",
        "adultCount": str(SEARCH["adult_count"]),
        "childCount": str(SEARCH["child_count"]),
        "infantCount": str(SEARCH["infant_count"]),
        "airlineCode": "",
        "directType": "",
        "cabinClass": "",
        "taxFee": "",
        "taxCurrency": "",
        "promotionCode": "",
    }


def product_for_fare(fare, products):
    raw = str(fare.get("productNo") or "")
    product_map = {str(item.get("code")): item for item in products if item.get("code")}
    for candidate in [raw, *re.split(r"[/|:]", raw)]:
        if candidate in product_map:
            return product_map[candidate]
    return next((item for code, item in product_map.items() if code in raw), {})


def print_flights(payload):
    data = payload.get("data") or {}
    groups = data.get("flights") or []
    products = data.get("products") or []
    count = sum(len(group) for group in groups if isinstance(group, list))
    print(f"查询状态: status={payload.get('status')} code={payload.get('code')}")
    print(f"航班数量: {count}")
    number = 0
    for group in groups:
        for flight in group:
            number += 1
            segments = flight.get("segments") or []
            first = segments[0] if segments else {}
            print(f"\\n航班 {number}: {first.get('marketAirlineName', '-')} AQ{first.get('marketFlightNo', '-')} 机型={first.get('model', '-')}")
            for segment in segments:
                print(
                    f"  {segment.get('departCityName', '-')} {segment.get('departAirportName', '-')}"
                    f"({segment.get('departAirportCode', '-')}) {segment.get('departTerminal', '-') }"
                    f" {segment.get('departDate', '')} {segment.get('departTime', '')}"
                    f" -> {segment.get('arrivalCityName', '-')} {segment.get('arrivalAirportName', '-')}"
                    f"({segment.get('arrivalAirportCode', '-')}) {segment.get('arrivalTerminal', '-') }"
                    f" {segment.get('arrivalDate', '')} {segment.get('arrivalTime', '')}"
                )
            fares = [fare for fare in flight.get("fares", []) if fare.get("paxType", "ADT") == "ADT"]
            for index, fare in enumerate(fares, 1):
                product = product_for_fare(fare, products)
                print(
                    f"  舱位{index}: {fare.get('cabinClass', '-')}/{fare.get('subClass', '-')} "
                    f"{product.get('name') or fare.get('productNo') or '-'} "
                    f"总价={fare.get('currency', 'CNY')} {fare.get('price', '-')} "
                    f"票面={fare.get('ticketPrice', '-')} 税费={fare.get('taxPrice', '-')} "
                    f"折扣={fare.get('discount', '-')} 余票={fare.get('ticketLack', '-') }"
                )


def main():
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    if COOKIE_HEADER:
        session.headers["Cookie"] = COOKIE_HEADER
    session.get(PAGE_URL, timeout=30).raise_for_status()
    source, source_name = load_fm(session)
    black_box = generate_black_box(session, source, source_name)
    print(f"black_box generated: length={len(black_box)}")
    if not COOKIE_HEADER:
        print("COOKIE_HEADER is empty; skip searchflight replay.")
        print("Use a private browser session Cookie header when the target requires gdxidpyhxdE session state.")
        return

    anti_headers = json.dumps(
        {
            "takeoff_place": SEARCH["from_code"],
            "arrive_place": SEARCH["to_code"],
            "is_roundtrip": 1,
            "departure_date": SEARCH["date"],
            "black_box": black_box,
            "channel": "9air_web",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    response = session.get(
        API_URL,
        params=build_query(),
        headers={"Accept": "application/json, text/plain, */*", "Anti-Headers": anti_headers},
        timeout=30,
    )
    print(f"searchflight HTTP status: {response.status_code}")
    if response.status_code >= 400:
        print(response.text[:2000])
        response.raise_for_status()
    print_flights(response.json())


if __name__ == "__main__":
    main()
