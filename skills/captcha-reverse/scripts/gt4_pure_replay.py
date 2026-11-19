import argparse
import base64
import hashlib
import hmac
import json
import math
import random
import re
import secrets
import time
import zlib
from pathlib import Path
from urllib.parse import urljoin

import ddddocr
import requests
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad
from PIL import Image


LOAD_URL = "https://gcaptcha4.geetest.com/load"
VERIFY_URL = "https://gcaptcha4.geetest.com/verify"
STATIC_BASE = "https://static.geetest.com/"
RSA_N_HEX = (
    "c1e3934d1614465b33053e7f48ee4ec87b14b95ef88947713d25eecbff7e74c"
    "7977d02dc1d9451f79dd5d1c10c29acb6a9b4d6fb7d0a0279b6719e1772565f"
    "09af627715919221aef91899cae08c0d686d748b20a3603be2318ca6bc2b597"
    "06592a9219d0bf05c9f65023a21d2330807252ae0066d59ceefa5f2748ea80bab81"
)
RSA_E = 65537
GEE_GUARD = {
    "roe": {"aup": "3", "sep": "3", "egp": "3", "auh": "3",
            "rew": "3", "snh": "3", "res": "3", "cdc": "3"},
}
EM = {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0}


def callback():
    return f"geetest_{int(time.time() * 1000)}"


def parse_jsonp(text):
    match = re.fullmatch(r"\s*[^(]+\((.*)\)\s*;?\s*", text, re.S)
    if not match:
        raise ValueError(f"Invalid JSONP: {text[:160]}")
    return json.loads(match.group(1))


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def decode_uri_bytes(value):
    reserved = b";/?:@&=+$,#"
    result = bytearray()
    index = 0
    while index < len(value):
        if value[index] == "%" and index + 2 < len(value):
            decoded = int(value[index + 1:index + 3], 16)
            if decoded in reserved:
                result.extend(value[index:index + 3].encode("ascii"))
            else:
                result.append(decoded)
            index += 3
        else:
            result.extend(value[index].encode("utf-8"))
            index += 1
    return bytes(result)


def decode_string_table(source):
    encoded_match = re.search(r"decodeURI\((['\"])(.*?)\1\)", source)
    if not encoded_match:
        raise ValueError("String table was not found")
    tail = source[encoded_match.end():encoded_match.end() + 3000]
    key_match = re.search(r"\}\((['\"])(.*?)\1\)\s*\n?\s*\}", tail)
    if not key_match:
        raise ValueError("String-table XOR key was not found")
    encoded = decode_uri_bytes(encoded_match.group(2))
    key = key_match.group(2).encode("latin1")
    decoded = bytes(value ^ key[index % len(key)] for index, value in enumerate(encoded))
    return decoded.decode("latin1").split("^")


def extract_bundle_metadata(bundle_path):
    source = bundle_path.read_text(encoding="utf-8")
    strings = decode_string_table(source)
    assignments = re.finditer(
        r"(?P<resolver>[\w$]+)\((?P<index>\d+)\)\]\s*=\s*\{(?P<body>[^{}]*)\}",
        source,
    )
    fixed_fields = None
    lot_rules = None
    for assignment in assignments:
        index = int(assignment.group("index"))
        if index >= len(strings):
            continue
        body = assignment.group("body")
        decoded_name = strings[index]
        if decoded_name == "_lib":
            fixed_fields = {
                match.group(1): strings[int(match.group(2))]
                for match in re.finditer(
                    r"([A-Za-z_$][A-Za-z0-9_$]*):[\w$]+\((\d+)\)", body
                )
            }
        elif decoded_name == "_abo":
            lot_rules = {
                match.group(2): strings[int(match.group(3))]
                for match in re.finditer(
                    r"([\"'])(.*?)\1:[\w$]+\((\d+)\)", body
                )
            }
    if fixed_fields is None or lot_rules is None:
        raise ValueError("Current bundle metadata initialization was not recognized")
    return fixed_fields, lot_rules


def resolve_lot_expression(expression, lot_number):
    def replace(match):
        start, end = map(int, match.groups())
        return lot_number[start:end + 1]

    return (
        re.sub(r"n\[(\d+):(\d+)\]", replace, expression)
        .replace("+", "")
        .replace("(", "")
        .replace(")", "")
    )


def resolve_lot_fields(lot_number, rules):
    result = {}
    for key_expression, value_expression in rules.items():
        path = resolve_lot_expression(key_expression, lot_number).split(".")
        value = resolve_lot_expression(value_expression, lot_number)
        target = result
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = value
    return result


def extract_function(source, start):
    brace = source.find("{", start)
    if brace < 0:
        raise ValueError("Function opening brace was not found")
    depth = 0
    quote = None
    escaped = False
    for index in range(brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("Function closing brace was not found")


def int32(value):
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def js_5381_hash(value):
    state = 5381
    utf16 = value.encode("utf-16-le", "surrogatepass")
    for index in range(0, len(utf16), 2):
        code_unit = int.from_bytes(utf16[index:index + 2], "little")
        state = int32(state) * 33 + code_unit
    return int32(state) & 0x7FFFFFFF


def calculate_biht(gct_source):
    marker = gct_source.find("=5381;")
    if marker < 0:
        raise ValueError("GCT 5381 hash function was not found")
    hash_start = gct_source.rfind("function ", 0, marker)
    if hash_start < 0:
        raise ValueError("GCT hash function start was not found")
    hash_source = extract_function(gct_source, hash_start)
    hash_end = hash_start + len(hash_source)
    guard_match = re.search(r"function\s+\w+\(\w+\)\{", gct_source[hash_end:])
    if not guard_match:
        raise ValueError("GCT guard function was not found")
    guard_source = extract_function(gct_source, hash_end + guard_match.start())
    suffix = decode_string_table(gct_source)[78]
    return str(js_5381_hash(guard_source + str(js_5381_hash(hash_source)))) + suffix


def solve_pow(captcha_id, lot_number, detail):
    hashfunc = detail["hashfunc"].lower()
    if hashfunc != "sha256":
        raise ValueError(f"Unsupported PoW hash: {hashfunc}")
    prefix = "|".join([
        str(detail["version"]), str(detail["bits"]), hashfunc,
        detail["datetime"], captcha_id, lot_number, "",
    ]) + "|"
    target = 1 << (256 - int(detail["bits"]))
    while True:
        message = prefix + secrets.token_hex(8)
        digest = hashlib.sha256(message.encode()).hexdigest()
        if int(digest, 16) < target:
            return {"pow_msg": message, "pow_sign": digest}


def generate_trace(distance, duration_ms):
    count = max(28, min(60, duration_ms // 24))
    points = [[0, 0, 0]]
    last_x = 0
    for index in range(1, count):
        progress = index / (count - 1)
        x = max(last_x, min(distance, round(distance * (1 - (1 - progress) ** 3))))
        y = round(math.sin(progress * math.pi * 2) * 1.4 + random.uniform(-0.7, 0.7))
        if x != last_x or index == count - 1:
            points.append([x, y, round(duration_ms * progress)])
            last_x = x
    points[-1] = [distance, 0, duration_ms]
    return points


def replay_trace_timing(trace):
    started = time.perf_counter()
    for _, _, timestamp in trace[1:]:
        remaining = timestamp / 1000 - (time.perf_counter() - started)
        if remaining > 0:
            time.sleep(remaining)


def load_reference_trace(template_path, duration_ms, final_x):
    """Translate a same-version successful td template to this endpoint."""
    if template_path is None:
        return None
    try:
        captured = json.loads(template_path.read_text(encoding="utf-8"))
        source_points = captured["p"]
        source_duration = source_points[-1][0]
        if len(source_points) < 10 or source_duration <= 0:
            return None
        width = float(captured["w"])
        shift_x = final_x - source_points[-1][1] * width
        start_x = source_points[0][1] * width + shift_x
        time_scale = duration_ms / source_duration
        trace = [[0, 0, 0, 0]]
        for point in source_points[1:-1]:
            trace.append([
                round(point[1] * width + shift_x - start_x),
                round((point[2] - source_points[0][2]) * 300),
                round(point[0] * time_scale),
                point[3],
            ])
        trace.append([round(final_x - start_x), 0, duration_ms, 2])
        return trace, start_x, source_points[0][2], source_points[-1][2]
    except (OSError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def encode_td(trace, set_left, duration_ms, start_ms, cursor_offset,
              start_x=40.25, base_y=None, end_y=None):
    width = 300.03125
    height = 261.53125
    if base_y is None:
        base_y = round(random.uniform(0.875, 0.91), 4)
    points = [[0, round(start_x / width, 4), base_y, 0]]
    for item in trace[1:-1]:
        x, y, timestamp = item[:3]
        action = item[3] if len(item) > 3 else 1
        points.append([
            int(timestamp),
            max(0, min(1, round((start_x + x) / width, 4))),
            max(0, min(1, round(base_y + y / 300, 4))),
            action,
        ])
    if len(points) > 6 and not any(point[3] == 3 for point in points):
        marker_index = random.randint(max(2, len(points) // 3), max(3, len(points) // 2))
        points[marker_index][3] = 3
    points.append([
        int(duration_ms),
        max(0, min(1, round((set_left + cursor_offset) / width, 4))),
        base_y if end_y is None else end_y,
        2,
    ])
    track = {"m": 1, "w": width, "h": height,
             "s": int(start_ms), "e": int(start_ms + duration_ms), "p": points}
    raw = json.dumps(track, ensure_ascii=False, separators=(",", ":")).encode()
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    header = b"\x1f\x8b\x08\x00" + int(time.time()).to_bytes(4, "little") + b"\x00\x03"
    trailer = zlib.crc32(raw).to_bytes(4, "little") + (len(raw) & 0xFFFFFFFF).to_bytes(4, "little")
    encoded = base64.urlsafe_b64encode(header + compressed + trailer).rstrip(b"=").decode()
    return encoded, track


def encrypt_w(payload, pt):
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if str(pt) != "1":
        raise ValueError(f"Pure Python implementation supports pt=1, got {pt}")
    aes_key = secrets.token_hex(8).encode()
    aes_hex = AES.new(aes_key, AES.MODE_CBC, b"0000000000000000").encrypt(
        pad(compact.encode(), AES.block_size)
    ).hex()
    public_key = RSA.construct((int(RSA_N_HEX, 16), RSA_E))
    rsa_hex = PKCS1_v1_5.new(public_key).encrypt(aes_key).hex()
    return aes_hex + rsa_hex, compact


def download(session, url):
    response = session.get(urljoin(STATIC_BASE, url), timeout=30)
    response.raise_for_status()
    return response


def main():
    parser = argparse.ArgumentParser(description="Pure Python Geetest GT4 protocol replay")
    parser.add_argument("--captcha-id", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--cache-root", type=Path, default=Path.cwd() / "js_reverse_cache_pure")
    parser.add_argument("--gap-x", type=int)
    parser.add_argument("--td-template", type=Path,
                        help="Optional decoded td JSON from a same-version successful round")
    parser.add_argument("--captcha-user", help="Optional captcha_v4_user from the same profile")
    parser.add_argument("--use-env-proxy", action="store_true")
    args = parser.parse_args()

    fixed_fields, lot_rules = extract_bundle_metadata(args.bundle)
    session = requests.Session()
    session.trust_env = args.use_env_proxy
    session.headers.update({
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://gt4.geetest.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
        ),
    })
    if args.captcha_user:
        session.cookies.set("captcha_v4_user", args.captcha_user, domain=".geetest.com")
    started_at = time.perf_counter()
    load_response = session.get(LOAD_URL, params={
        "callback": callback(), "captcha_id": args.captcha_id,
        "client_type": "web", "risk_type": "slide", "pt": "1", "lang": "zh",
    }, timeout=30)
    load_response.raise_for_status()
    load_json = parse_jsonp(load_response.text)
    if load_json.get("status") != "success":
        raise RuntimeError(f"Load failed: {load_json}")
    data = load_json["data"]
    cache = args.cache_root / data["lot_number"]
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "load.jsonp").write_text(load_response.text, encoding="utf-8")
    save_json(cache / "load.json", load_json)
    save_json(cache / "cookies.json", requests.utils.dict_from_cookiejar(session.cookies))

    slice_response = download(session, data["slice"])
    bg_response = download(session, data["bg"])
    if not slice_response.headers.get("content-type", "").startswith("image/"):
        raise ValueError("Slice response is not an image")
    if not bg_response.headers.get("content-type", "").startswith("image/"):
        raise ValueError("Background response is not an image")
    (cache / "slice.png").write_bytes(slice_response.content)
    (cache / "bg.png").write_bytes(bg_response.content)
    detected = ddddocr.DdddOcr(show_ad=False).slide_match(
        slice_response.content, bg_response.content, simple_target=True
    )
    target = detected.get("target")
    detected_x = int(target[0]) if target and int(target[0]) > 0 else int(detected["target_x"])
    gap_x = args.gap_x if args.gap_x is not None else detected_x
    with Image.open(cache / "bg.png") as image:
        bg_width = image.width
    scale = 0.8876 * min(bg_width, 340) / bg_width
    set_left = round((gap_x - 2) * scale)
    userresponse = set_left / scale + 2
    passtime = random.randint(950, 1650)
    track_duration = random.randint(1200, 2500)
    cursor_offset = 54
    track_distance = set_left + cursor_offset - 40.25

    gct_response = download(session, data["gct_path"])
    gct_source = gct_response.text
    (cache / "gct.raw.js").write_text(gct_source, encoding="utf-8")
    biht = calculate_biht(gct_source)
    pow_data = solve_pow(args.captcha_id, data["lot_number"], data["pow_detail"])
    reference = load_reference_trace(args.td_template, track_duration, set_left + cursor_offset)
    if reference is None:
        trace = generate_trace(track_distance, track_duration)
        trace_start_x, trace_base_y, trace_end_y = 40.25, None, None
        trace_source = "generated-fallback"
    else:
        trace, trace_start_x, trace_base_y, trace_end_y = reference
        trace_source = "same-version-template"
    track_start_ms = int(time.time() * 1000)
    td, td_payload = encode_td(
        trace, set_left, track_duration, track_start_ms, cursor_offset,
        trace_start_x, trace_base_y, trace_end_y,
    )
    w_payload = {
        "setLeft": set_left, "passtime": passtime, "userresponse": userresponse,
        "device_id": "", "lot_number": data["lot_number"], **pow_data,
        "geetest": "captcha", "lang": "zh", "ep": "123", "biht": biht,
        "gee_guard": GEE_GUARD, **fixed_fields,
        **resolve_lot_fields(data["lot_number"], lot_rules), "em": EM,
    }
    w_payload["td_sign"] = hmac.new(
        data["lot_number"].encode(), td.encode(), hashlib.sha256
    ).hexdigest()
    w, compact = encrypt_w(w_payload, str(data["pt"]))
    save_json(cache / "trace.json", trace)
    save_json(cache / "image_meta.json", {
        "ocr": detected, "gap_x": gap_x, "bg_width": bg_width,
        "scale": scale, "setLeft": set_left, "userresponse": userresponse,
        "passtime": passtime, "track_duration": track_duration,
        "trace_points": len(trace), "trace_source": trace_source,
        "td_start_ms": td_payload["s"], "td_end_ms": td_payload["e"],
        "td_length": len(td),
    })
    save_json(cache / "pure_output.json", {
        "w": w, "wPayload": w_payload, "compact": compact, "td": td,
        "fixedFields": fixed_fields, "lotRules": lot_rules,
    })
    remaining = passtime / 1000 - (time.perf_counter() - started_at)
    if remaining > 0:
        time.sleep(remaining)

    verify_response = session.get(VERIFY_URL, params={
        "callback": callback(), "captcha_id": args.captcha_id,
        "client_type": "web", "lot_number": data["lot_number"],
        "risk_type": data["captcha_type"], "payload": data["payload"],
        "process_token": data["process_token"],
        "payload_protocol": data["payload_protocol"], "pt": data["pt"],
        "w": w, "td": td,
    }, timeout=30)
    verify_response.raise_for_status()
    verify_json = parse_jsonp(verify_response.text)
    (cache / "verify.jsonp").write_text(verify_response.text, encoding="utf-8")
    save_json(cache / "verify.json", verify_json)
    result = verify_json.get("data", {}).get("result")
    print(json.dumps({
        "runtime": "pure-python", "cache": str(cache.resolve()),
        "lot_number": data["lot_number"], "gap_x": gap_x, "setLeft": set_left,
        "passtime": passtime, "trace_points": len(trace), "biht": biht,
        "fixed_fields": fixed_fields, "lot_rules": lot_rules,
        "w_length": len(w), "status": verify_json.get("status"),
        "result": result, "fail_count": verify_json.get("data", {}).get("fail_count"),
    }, ensure_ascii=False, indent=2))
    return 0 if verify_json.get("status") == "success" and result == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
