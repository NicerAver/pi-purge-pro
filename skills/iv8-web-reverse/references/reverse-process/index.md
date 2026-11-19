# Reverse Process Index

Read the matching reverse-process note before opening the case script.

| Case | Reverse Process Doc | Core Pattern |
| --- | --- | --- |
| `signatures/jd-h5st.py` | `references/reverse-process/signatures/jd-h5st-reverse-process.md` | Local HTML + local bundle + `MessageChannel` patch + `h5st` |
| `signatures/nmpa-md5-cookie.py` | `references/reverse-process/signatures/nmpa-md5-cookie-reverse-process.md` | Python MD5 sign + challenge cookie retry |
| `signatures/pdd-anti-content.py` | `references/reverse-process/signatures/pdd-anti-content-reverse-process.md` | Webpack chunk discovery + module call |
| `signatures/9air-black-box.py` | `references/reverse-process/signatures/9air-black-box-reverse-process.md` | TrustDecision `fm.js` + XHR bridge + `Anti-Headers.black_box` |
| `signatures/qunar-flight-bella.py` | `references/reverse-process/signatures/qunar-flight-bella-reverse-process.md` | QN668 refresh + inline `_pt_` + native-WASM Bella |
| `signatures/xhs-homefeed.py` | `references/reverse-process/signatures/xhs-homefeed-reverse-process.md` | `signV2Init()` + `window.mnsv2` + `X-S-Common` |
| `js-challenges/chinatax-ruishu.py` | `references/reverse-process/js-challenges/chinatax-ruishu-reverse-process.md` | Two-stage cookie then XHR suffix |
| `js-challenges/customs-ruishu.py` | `references/reverse-process/js-challenges/customs-ruishu-reverse-process.md` | Two-stage cookie then XHR header/url replay |
| `js-challenges/cebwm-ruishu6-wealth.py` | `references/reverse-process/js-challenges/cebwm-ruishu6-wealth-reverse-process.md` | CEBWM RS6 cookie then `7ibksfL8`/`vgL7Kuyn` XHR replay |
| `js-challenges/chng-ruishu-announcement.py` | `references/reverse-process/js-challenges/chng-ruishu-announcement-reverse-process.md` | CHNG 412 two-stage cookie then announcement XHR suffix |
| `js-challenges/ouyeel-202-cookie-url.py` | `references/reverse-process/js-challenges/ouyeel-202-cookie-url-reverse-process.md` | 202 challenge + manual script order + suffix |
| `js-challenges/cdfsunrise-md5-1803.py` | `references/reverse-process/js-challenges/cdfsunrise-md5-1803-reverse-process.md` | Aliyun WAF HTML challenge + closure-scoped `Lf -> LK` + `md5__1803` URL replay |
| `browser-tokens/zhipin-stoken.py` | `references/reverse-process/browser-tokens/zhipin-stoken-reverse-process.md` | Seed/name/ts to `__zp_stoken__` |
| `network-hook-signing/douyin-bdms.py` | `references/reverse-process/network-hook-signing/douyin-bdms-reverse-process.md` | Runtime hook + rewritten URL from `netLog` |
| `captcha/tencent-tdc-slider.py` | `references/reverse-process/captcha/tencent-tdc-slider-reverse-process.md` | Trusted input + POW + telemetry |
