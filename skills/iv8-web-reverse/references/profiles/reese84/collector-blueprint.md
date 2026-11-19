# Collector Blueprint

## 1. 推荐模块边界

保持一个主类或一组紧凑函数，不建立通用反爬框架：

```text
Reese84Collector
├── request()                 transport retry + one session
├── bootstrap()               entry GET + optional edge admission
├── solve_edge_admission()    optional precursor JS -> fresh clearance
├── discover_challenge()      HTML -> current randomized JS
├── generate_cookie()         iv8 context + pyHttp bridge
├── replay()                  install token + target GET
├── solve_utmvc_followup()    optional SWJIYLWA path
├── fetch_resource()          business URL on same session
└── run()                     bounded state machine + evidence
```

## 2. 常量

顶部只保留可解释常量：

```python
DEFAULT_URL = "https://target.example/protected"
USER_AGENT = "<baseline UA>"
IMPERSONATE = "<closest curl_cffi profile>"
CACHE_DIR = Path(__file__).parent / "js_reverse_cache"
OUTPUT_DIR = Path(__file__).parent / "output"
```

Canvas、环境等大对象放 JSON artifact，不把数万字符 base64 混进代码主体。

## 3. Session

```python
self.session = requests.Session(impersonate=IMPERSONATE)
self.base_headers = {
    "User-Agent": USER_AGENT,
    "Accept-Language": BASELINE_ACCEPT_LANGUAGE,
    "sec-ch-ua": BASELINE_SEC_CH_UA,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
```

`request()` 只对明确 transport error 重建 session；复制 cookies 后使用完全相同参数重试。

Edge admission 也必须使用 `self.session`。precursor 求解失败时 bootstrap 不得因为已经发现 Reese script 就继续 GPC；应记录失败并有界获取新的 entry/session。完整约束见 `edge-admission.md`。

## 4. HTML 解析

使用 `html.parser.HTMLParser` 收集 script src，再用 regex 补动态 `scriptElement.src`。不要用宽泛 regex 解析全部 HTML。

静态测试至少覆盖：

- 外链 script。
- 动态 script src。
- 顺序去重。
- Cookie value 中 `+`、`/`、`=` 不被破坏。

## 5. iv8 Environment

从 JSON 读取：

```python
browser_env = json.loads(BROWSER_ENV_PATH.read_text("utf-8"))
environment = browser_env["environment"]
config = browser_env.get("config", {"timezone": "UTC"})
```

推荐 schema：

```json
{
  "baseline": "chrome-150-windows",
  "environment": {
    "location": {"href": "..."},
    "navigator": {},
    "screen": {},
    "window": {},
    "webgl": {},
    "canvas": {"fingerprint": {"toDataURL": {}}}
  },
  "config": {"timezone": "Asia/Shanghai"},
  "headers": {},
  "patches": {
    "canvasCapture": "canvas_capture.json"
  }
}
```

### 通用环境采集

在唯一 baseline 页面运行一次固定采集脚本，原始结果写入 `browser_env_raw.json`，再归一为 `browser_env.json`。至少采集：

- navigator：UA/appVersion/platform/vendor/language/languages、hardwareConcurrency、deviceMemory、maxTouchPoints、doNotTrack、webdriver、userAgentData、plugins、mimeTypes。
- screen/window：width/height/avail、colorDepth/pixelDepth、inner/outer、screenX/Y、DPR。
- Intl：timezone、locale、number/date resolved options。
- WebGL：unmasked vendor/renderer、关键 getParameter、extensions。
- surfaces：`window.chrome`、connection、getBattery、mediaDevices、Worker、AudioContext、performance.memory 等只记录类型和 descriptor。
- HTTP 对照：成功请求的 UA、Client Hints、Accept-Language、入口 Cookie 属性和 transport/browser 版本。

采集和验证要求：

1. raw 文件附 `baseline`、采集时间、页面 URL、采集脚本 SHA-256 和浏览器版本。
2. normalized 文件只保留 iv8 可承接字段；不能承接的进程/TLS/真实渲染字段列入 `excluded`。
3. 对比 raw UA 与 HTTP UA/Client Hints；浏览器家族或主版本冲突时停止注入。
4. 在 iv8 用固定 probe 读回同一字段，保存 browser/iv8 diff；descriptor、类型和缺失字段也要比较。
5. Canvas 使用独立精确采集流程，不能从通用 snapshot 中用占位 data URL 代替。

## 6. Context 生命周期

```python
with iv8.JSContext(environment=environment, config=config, time_mode="system") as ctx:
    ctx.expose(snapshot, "snapshot")
    ctx.expose(py_http, "pyHttp")
    ctx.eval("let __iv8Host = window.__iv8__; delete window.__iv8__;")
    ctx.eval(host_bridge_source)
    ctx.eval("__iv8Host.page.load(__iv8Host.data.snapshot)")
    ctx.eval(challenge.body, name=challenge.url)
    drive_event_loop(ctx, token_state)
```

为什么 lexical host 和核心 bridge 在 `page.load` 前：patch 和 event loop 仍需访问 iv8 API，但页面同步脚本不能从 window 枚举发现宿主；error/fetch/iframe guards 也必须在 snapshot 中的内联脚本和生命周期执行前存在。若某个 patch 依赖 page.load 后才创建的对象，将它拆成明确的 post-load patch，不要把整个 bridge 延后。

## 7. Bridge JS 职责

Bridge JS 只做：

- error/unhandledrejection 收集。
- fetch/XHR 到 `pyHttp` 的适配。
- host 隐藏。
- iframe lifecycle。
- 已验证环境 patch。
- response 对象最小兼容。

不要把业务签名逻辑搬到 bridge；challenge 应运行原始当轮脚本。

## 8. Response 适配

JS fetch adapter 至少提供：

```javascript
{
  ok,
  status,
  statusText,
  url,
  redirected: false,
  type: 'basic',
  headers: { get(name), has(name) },
  text() { return Promise.resolve(body); },
  json() { return Promise.resolve(JSON.parse(body)); },
  clone() { return this; }
}
```

Headers 查询要大小写不敏感。

## 9. Run 状态机

```text
BOOTSTRAP
  -> EDGE_ADMISSION (optional, only with independent evidence)
  -> RELOAD_ENTRY
  -> GENERATE_REESE
  -> INSTALL_TOKEN
  -> REPLAY
     -> SUCCESS
     -> UTMVC (only if current response exposes a verified UTMVC asset) -> REPLAY
     -> RENEWAL/SECOND CHALLENGE (bounded)
     -> BLOCKED
```

每个 round 保存 challenge、exchanges、token、followup 和 replay status。最多 2-3 轮；重复 `(challenge_url, token)` 立即停止。

## 10. 业务资源 CLI

推荐参数：

```text
--url <protected entry>
--resource-url <business API>
--output <evidence JSON>
```

日期类业务参数不要默认写死为抓包日期；使用显式必填参数，或相对运行日生成未来日期并在 evidence 中记录最终值。过期行程导致的 `INVALID ITINERARY` 属于业务校验，不应误判为 Reese/admission 失败。

执行顺序固定：

```python
collector = Reese84Collector(args.url)
result = collector.run()
if args.resource_url:
    result["resource"] = collector.fetch_resource(args.resource_url)
```

绝不能先 `run()`，再创建新 collector 请求业务接口。

## 11. 输出大小

大 JSON 业务响应可以存入同一个 result 的 `resource.data`，也可以单独保存：

```text
output/run_<timestamp>.json
output/resource_<timestamp>.json
```

无论哪种方式，主 evidence 记录 resource 文件 hash、status、content type 和 bytes。

## 12. 测试

最低测试集：

```python
class StaticHelpersTest(unittest.TestCase):
    def test_discovers_dynamic_challenge_script(self): ...
    def test_cookie_value_preserves_base64_characters(self): ...
```

建议新增：

- blocked marker 判定。
- edge marker 分类：precursor、完整 Managed Challenge、非 Cloudflare Reese 403。
- precursor 生成不依赖随机闭包短变量名。
- 长 timer 一次性触发且永久 interval 不进入无界 drain。
- UTMVC 资源按当前站点证据识别，并覆盖常见 `SWJIYLWA` 样本。
- 相同 challenge/token 收敛。
- Canvas capture schema 完整性。
- business response JSON/HTML 区分。

## 13. 并发执行模型

### 为什么不能用线程池

iv8 的 JS runtime/DOM/EventTarget 在同一 Python 进程内可能共享全局状态。两个线程同时创建和推进 `JSContext` 时，真实案例出现：

```text
TypeError: Failed to execute 'addEventListener' on 'EventTarget': Illegal invocation
```

这不是普通业务异常，也不是增加锁住某一行就能可靠修复的问题。不要使用：

```python
ThreadPoolExecutor
threading.Thread
共享 Reese84Collector
共享 curl_cffi.Session
共享 iv8.JSContext
```

### 正确模型：独立进程

每个 worker 在自己的 Python 进程中导入 iv8，并创建独立 collector：

```python
from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed


def run_worker(worker_id, target_url, resource_url=None):
    collector = Reese84Collector(target_url)
    result = collector.run()
    resource = None
    if resource_url and result["verified"]:
        resource = collector.fetch_resource(resource_url)
    return {
        "worker_id": worker_id,
        "ok": bool(result["verified"]),
        "challenge_sha256": result["challenge_sha256"],
        "round_count": len(result["rounds"]),
        "reese84_length": result["reese84_length"],
        "replay_status": result["replay"]["status"],
        "replay_content_length": result["replay"]["content_length"],
        "resource_status": resource["status"] if resource else None,
        "resource_content_length": resource["content_length"] if resource else None,
    }


if __name__ == "__main__":
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as executor:
        futures = [
            executor.submit(run_worker, worker_id, TARGET_URL, RESOURCE_URL)
            for worker_id in range(1, 3)
        ]
        results = [future.result() for future in as_completed(futures)]
```

Windows 必须保留 `if __name__ == "__main__"`，否则 spawn 子进程会递归创建进程。

### 隔离要求

- 每个 worker 独立 `Reese84Collector`。
- 每个 worker 独立 `curl_cffi.Session` 和 Cookie jar。
- 每个 worker 独立 iv8 Context/runtime。
- 每个 worker 自己下载/执行 challenge 并获取 token。
- 不把一个 worker 的 `reese84` 复制给另一个 worker。
- 静态只读 Canvas JSON 可以由各进程分别读取；不要共享可变 JS 对象。
- 不在父进程返回完整 token、Cookie、solution 或大业务 JSON，只返回脱敏摘要。

### 测试梯度

1. 串行运行至少两次，确认基础链稳定。
2. `concurrency=2,total=2`，只验证 Reese replay。
3. `concurrency=2,total=2`，再验证业务 API。
4. 需要更多任务时先固定 `concurrency=2` 增加 `total`，确认排队模型稳定。
5. 再逐级提高并发；每级保存 wall time、成功率和错误类型。

不要把 `(28) Connection timed out` 自动视为 token 算法错误。先区分目标限流、网络瞬态和单 worker 逻辑；并发测试不应修改已经串行成功的 collector 来迁就一次压力失败。

## 14. 不应进入最终代码的内容

- 浏览器 storage state。
- 用户抓包完整 Cookie 字符串。
- 固定 `reese84`。
- 某次 edge precursor 或 Reese challenge 的固定 POST body。
- 固定 `cf_clearance`、ray 或 precursor URL。
- 随机化 edge 脚本中的闭包函数短名。
- Playwright/CDP 连接。
- 分析期间的 Proxy hook。
- 未证明参与校验的数百个环境属性。
