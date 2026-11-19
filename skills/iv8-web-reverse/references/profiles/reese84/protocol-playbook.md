# Reese84 Protocol Playbook

## 1. 识别协议

Reese84 通常不是一个可脱离上下文直接调用的短签名函数，而是一个随机化 challenge runtime。每次入口页可能引用不同 query 的大型脚本，脚本执行后收集环境并向自身路径回传。

常见链路：

```text
GET protected document
  -> Set-Cookie: visid_incap_*, incap_ses_*
  -> optional independently evidenced edge admission
     (for example dynamic Cloudflare precursor -> fresh clearance -> reload)
  -> HTML references randomized challenge JS

GET challenge JS
  -> randomized/obfuscated Reese runtime

POST challenge-path?d=<hostname>
  body: {"f":"gpc"}
  -> seed/config response

POST challenge-path?d=<hostname>
  body: {
    "solution": {
      "interrogation": {"p":"...","st":...,"sr":...,"cr":...,"og":...},
      "version":"..."
    },
    "old_token": null or "...",
    "error": null,
    "performance": {...}
  }
  -> {"token":"...","renewInSec":...,"cookieDomain":"..."}

GET protected document with reese84
  -> application HTML, or another Imperva follow-up
```

不要假设所有站点字段顺序、challenge 路径或版本固定。事实必须来自当前运行的 script-built envelope。

## 2. 状态与所有权

把状态分成五层：

| 层 | 状态 | 所有者 |
|---|---|---|
| HTTP | TLS、HTTP/2、headers、Cookie jar、重定向 | Python `curl_cffi.Session` |
| Edge admission（可选） | precursor params/JS、admission POST、clearance | 独立 iv8 context + 同一 Python Session |
| 页面 | URL、HTML、响应 headers、document.cookie、DOM 生命周期 | iv8 `page.load` snapshot |
| 环境 | navigator、screen、Canvas、WebGL、时区、函数外观 | iv8 environment + 最小 patch |
| 协议 | GPC seed、solution envelope、token、renewInSec | challenge JS + Python bridge |

真实网络只由 Python 发出。iv8 内的 fetch/XHR 是请求计划器和 challenge 执行器，不应创建第二套独立 Cookie 状态。Edge 与 Reese 可以使用独立 JSContext，但不得使用不同 Python Session、Cookie jar 或 HTTP 身份。具体分层见 `edge-admission.md`。

## 3. 必存证据

每次运行至少保存：

```json
{
  "generated_at": "ISO-8601",
  "target_url": "...",
  "challenge_url": "...",
  "challenge_sha256": "...",
  "challenge_size": 0,
  "initial_status": 200,
  "initial_cookies": {},
  "edge_admission": null,
  "exchanges": [
    {
      "method": "POST",
      "url": "...",
      "request_body_sha256": "...",
      "request_headers": {},
      "status": 200,
      "response_headers": {},
      "response_body": "...",
      "cookies_after": {}
    }
  ],
  "replay": {
    "status": 200,
    "content_type": "text/html",
    "content_length": 0,
    "blocked": false,
    "body_prefix": "..."
  },
  "verified": true
}
```

Cookie/token 可以在本地授权项目中原样保存；写入 skill、公开报告或共享仓库前必须移除。

## 4. Challenge 发现

不要只写死某个随机路径。解析：

1. HTML `<script src="...">`。
2. 内联脚本中的 `scriptElement.src = "..."`。
3. 同源候选脚本。
4. 脚本正文中 `reese84` 或 `initializeProtection` 等特征。

伪代码：

```python
def discover_challenge(response, session):
    allowed_origins = build_challenge_allowlist(response, accepted_sample=None)
    for source in discover_script_sources(response.text):
        script_url = urljoin(response.url, source)
        if origin(script_url) not in allowed_origins:
            continue
        script_response = session.get(script_url, headers={"Referer": response.url})
        if "reese84" in script_response.text or "initializeProtection" in script_response.text:
            return script_url, script_response.text
    raise RuntimeError("Reese84 challenge not found")
```

## 5. Snapshot 构造

`page.load` snapshot 建议包含：

```python
snapshot = {
    "baseURL": entry_response.url,
    "html": entry_response.text,
    "headers": visible_response_headers,
    "resources": optional_resource_map,
}
```

注意：

- Python session 中 HttpOnly Cookie 不应伪装成 JavaScript 可读 Cookie。
- `Set-Cookie` snapshot 仅用于页面应当可见的 Cookie。
- `baseURL` 必须是当前 document URL，保证 challenge 相对路径和 origin 判断正确。
- challenge eval 必须在 `page.load` 之后。

## 6. Python HTTP Bridge

桥接函数接收 JS 请求并返回可 JSON 序列化的 response：

```python
def py_http(method, url, body, headers_json):
    request_url = urljoin(entry_url, str(url))
    extra_headers = json.loads(str(headers_json)) if headers_json else {}
    response = session.request(
        str(method),
        request_url,
        data=None if body is None else str(body),
        headers={**challenge_headers, **extra_headers},
        timeout=30,
    )
    capture_exchange(response)
    return json.dumps({
        "url": request_url,
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": response.text,
    })
```

服务端 token 只能从响应 JSON 的 `token` 字段取；不要从不相关 header 或旧 Cookie 猜测。

## 7. Event Loop

Reese runtime 通常依赖 Promise、timer、iframe load 和 fetch。一个稳妥的推进循环：

```python
for _ in range(MAX_TICKS):
    ctx.eval("__host.eventLoop.drainMicrotasks()")
    ctx.eval("__host.eventLoop.sleep(500)")
    ctx.eval("__host.eventLoop.drain()")
    if token_state.get("token"):
        break
```

要求：

- 有明确最大 tick。
- token 到达立即停止。
- 保存 `error` 和 `unhandledrejection`。
- 超时报告 bridge errors、netLog、最后 exchange，不只报告“失败”。
- 不把这个循环机械复用于 precursor；edge 脚本若注册永久 interval，无条件 `drain()` 可能挂死，应读取首个目标 XHR 后退出或做固定次数推进。

## 8. Token 安装与 replay

使用服务端 `cookieDomain`：

```python
domain = cookie_domain if cookie_domain.startswith(".") else f".{cookie_domain}"
session.cookies.set("reese84", token, domain=domain, path="/")
```

若 GPC 返回 `cf-mitigated: challenge`，先按 `edge-admission.md` 判断请求是否被外层 CDN 截获；此时不要根据 solution/Canvas 调参。

Replay 保持：

- 同一个 session。
- 同一 UA/Client Hints。
- 同一 Accept-Language。
- 同一 transport impersonate。
- 合理 Referer。

## 9. UTMVC 跟进

只有发现经当前响应和脚本行为验证的 UTMVC 资源才进入该阶段。`SWJIYLWA` 是常见标记，不是唯一协议常量：

```text
GET /_Incapsula_Resource?SWJIYLWA=...
  -> execute script in page snapshot
  -> document.cookie contains ___utmvc
  -> GET/POST /_Incapsula_Resource?SWKMTFSR=1&e=<random>
  -> response body commonly "1"
  -> replay document
```

`SWKMTFSR` 返回 `1` 仅证明 beacon 被接收，不证明 Reese token 评分合格。

## 10. 续期路径

某些后续脚本把已有 token 作为 JSON 字符串 POST，并返回相同 `token/renewInSec/cookieDomain`。这是续期/确认路径，不是新的完整 `solution.interrogation`。

识别方法：

- request body 是 JSON string token，而非 `solution` object。
- response token 与现有 token 相同。
- 没有新的 `p`。

相同 challenge URL + 相同 token 再次出现时停止循环，回到首轮环境诊断。

同源是默认安全策略，不是协议不变量。构造 allowlist：

1. 始终允许入口 document origin。
2. 有 accepted sample 时，加入样本中实际成功加载 challenge 的 HTTPS origin。
3. 没有 accepted sample 时，只 provisional 允许入口 HTML 明确通过 `<script src>` 或动态 src 引用的 HTTPS origin；下载后还必须验证正文包含 Reese84/initializeProtection/solution 相关特征。
4. provisional origin、引用位置和脚本 hash 写入证据；最终业务未放行时仍标记 baseline 缺口。
5. 不允许用户输入或 challenge 内容把任意第三方 origin 动态扩展进 allowlist。

跨域时保持浏览器样本或页面语义中的 Origin/Referer/CORS，不要简单伪造成同源。

## 11. 长期运行与续期

短任务可以每次创建新会话并完整解 challenge。长期 collector 记录 `renewInSec`，但不要假设它是精确过期时间：

1. 保存 token 获取时间和 `renewInSec`。
2. 在 `renewInSec` 前留有界安全余量：`margin = min(max(renewInSec * 0.1, 5), renewInSec * 0.5)`，调度时间至少为获取后 1 秒，避免短 TTL 出现负数。
3. 优先执行当前页面下发的 renewal 路径；没有可验证 renewal 时重新 bootstrap 完整 challenge。
4. 续期后必须 replay 一个轻量受保护资源验证，而不是只看 token response。
5. renewal 返回相同 token 时更新观测时间，但连续失败立即丢弃 session 并全量重建。
6. 多 worker 不共享可变 Cookie jar；每个 session 独立 bootstrap。

## 12. 业务 API 回放

不要重新创建 Session。通过后直接：

```python
response = collector_session.get(
    api_url,
    headers={
        **baseline_headers,
        "Accept": "*/*",
        "Referer": business_referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    },
)
```

保存完整 JSON 或二进制响应，并记录 status/content-type/content-length。不要把抓包中的整段 Cookie 作为 `-b` 参数复制进最终脚本。
