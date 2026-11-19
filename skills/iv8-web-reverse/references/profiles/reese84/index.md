# Reese84 Profile

将明确的 Imperva/Incapsula Reese84 流程还原成可重复运行的 Python collector：Python 维护真实 HTTP 会话，iv8 本地执行每次下载的随机挑战脚本，最终请求不依赖浏览器、浏览器配置目录或固定 token。

## 启动门

激活后，在调用分析工具或写代码前先输出并填写：

```text
═══ Reese84 启动门 ═══
[1] Reese84 证据：____
[2] 目标页面：____
[3] 业务接口：____（未知可留空）
[4] 成功浏览器基线：____（尚未采集则写 missing）
[5] 最终交付：Python + iv8 + curl_cffi，无运行时浏览器
[6] 动态材料目录：<workspace>/js_reverse_cache/
```

用户或样本明确出现 `reese84`、`re84` 或明确称为 Reese84 时，一类直接证据即可进入本 skill。没有这些名称时，至少满足以下两类相关证据才深入：

- Cookie 或代码中明确出现 `reese84`。
- POST envelope 含 `solution.interrogation.p/st/sr/cr/og`。
- 挑战先发 `{"f":"gpc"}`，后发 solution。
- 响应包含 `token`、`renewInSec`、`cookieDomain`。
- 页面同时出现 Imperva/Incapsula 资源参数，如 `SWJIYLWA`、`SWKMTFSR`、`CWUDNSAI`。

证据不足时，返回 `trace` Observe/Capture 定位真实入口。用户只要求既有 JS 用 iv8 跑起来但没有 Reese84 特征时退出本 profile，返回 `iv8-web-reverse` 通用流程。

## 硬约束

1. 最终运行时不得启动 Playwright、Selenium、CDP、Camoufox、CloakBrowser 或系统浏览器。
2. 不得复用抓包中的固定 `reese84`、`incap_ses_*`、`visid_incap_*`、`nlbi_*` 或 `___utmvc` 作为成功方案。
3. 每次运行必须重新 GET 入口页、下载本轮随机 challenge、生成本轮 solution，并在同一 `curl_cffi.Session` 内回放；若存在有独立证据的 edge admission，其动态脚本、POST 和 clearance 也必须在该 Session 当轮生成。
4. 一条真实请求链只允许一个 `BROWSER_BASELINE`。UA、Client Hints、navigator、screen、Canvas、WebGL、时区和 TLS impersonation 不得跨 Firefox/Chrome 或跨设备拼接。
5. 服务端返回 Reese token 只证明 envelope 可解析，不证明已放行；必须以真实业务 HTML/API 响应为最终判据。
6. 动态下载的 HTML、JS、环境样本、运行结果统一写入工作区 `js_reverse_cache/` 或 `output/`，不得把目标 token/cookie 写入本 skill。
7. 不通过缩短等待、重复提交同一 token 或无限轮询掩盖环境不一致。循环必须有上限和相同 challenge/token 收敛条件。
8. iv8 并发不得使用 `ThreadPoolExecutor` 或多个线程同时运行 `JSContext`。并发必须采用独立进程；每个 worker 独立创建 iv8 runtime、`curl_cffi.Session`、Cookie jar 和完整 Reese 链路，不共享 token 或可变 Session。

## 成功定义

必须同时满足：

- 从无目标 Cookie 的新会话开始。
- 本轮随机 challenge 由 Python 下载并由本地 iv8 执行。
- 若存在 edge admission，先由同一 Session 动态完成，不导入浏览器 clearance。
- solution POST 返回动态 token。
- token 写回同一 Python session。
- 目标页面或业务 API 返回预期内容，而不是状态为 200 的挑战页。
- 连续至少两次全新会话成功。
- Python 编译和最小静态测试通过。

业务页面判定不能只看 `status == 200`。同时检查 `content-type`、正文长度、应用特征和以下拦截标记：

- `Pardon Our Interruption`
- `CWUDNSAI=`
- `META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW"`
- 仅包含挑战脚本或保护 iframe 的短 HTML

## Reference 路由

按当前阶段只读需要的文件：

- 初次建链、理解请求状态机：`protocol-playbook.md`
- GPC 前出现 `cf-mitigated: challenge` 且已确认 precursor：`edge-admission.md`
- 设计 Python/iv8 文件和函数：`collector-blueprint.md`
- 遇到 token 有了但仍 403：`environment-consistency.md` 和 `failure-diagnostics.md`
- 参考本次真实成功经验：`case-bangkokair.md`

## 标准流程

### Phase 0：固定证据

保存至少一份浏览器成功链和一份新鲜纯 HTTP 失败链：

- 入口 document 请求/响应。
- 随机 challenge JS 请求/响应。
- GPC POST。
- solution POST 原始 body、headers、响应。
- token 写入后的 document/API 请求。
- 若存在，UTMVC 脚本、beacon 和第二次 replay。

成功样本是协议和环境字段的最佳事实来源。没有成功浏览器链时，保存当前最可信的单一浏览器环境样本和纯 HTTP 失败链，继续做最小复现，但将“缺少 accepted baseline”记录为验证缺口；最终未通过时不得宣称完成。不要先猜 `p` 内字段。

### Phase 1：建立纯 HTTP 骨架

先只实现：

1. 单个 `curl_cffi.requests.Session`。
2. GET 入口页并保存 cookies。
3. 从 HTML 的 `<script src>` 和动态赋值中发现 challenge。
4. 同 session 下载 challenge。
5. 保存每次 request/response 的 URL、状态、headers、body hash 和 cookies_after。

此阶段禁止硬塞浏览器 token 来伪造通过。

### Phase 1.5：可选 edge admission

只有 entry/GPC 响应提供独立 Cloudflare precursor 证据时进入。按 `edge-admission.md` 动态执行当轮 edge 脚本、记录其 XHR、由同一 Session 发送 admission POST并重新加载 entry。若是完整 Managed Challenge 或无 precursor 入口，转 `trace` 固定外层状态机；不要继续 GPC 或提前补 Canvas。

### Phase 2：建立 iv8 执行桥

使用 `iv8.JSContext`：

- `environment` 承接唯一 baseline 的 navigator/screen/window/WebGL/Canvas。
- `snapshot` 承接入口 URL、HTML、响应 headers 和可见 Cookie。
- `page.load(snapshot)` 发生在 challenge eval 之前。
- Python `pyHttp` 接收 method/url/body/headers，真实请求仍由同一个 Python session 发出。
- Promise、timer、XHR/fetch 按目标生命周期有界推进；Reese 常用 `drainMicrotasks()`、固定 `sleep()` 和受控 `drain()`，但遇到永久 interval 时不得无条件 drain。
- 记录 bridge errors，不静默吞掉异常。

### Phase 3：最小宿主修补

按证据逐项补，不建立无限 Proxy 环境：

- 在 `page.load` 前保存 lexical host bridge，再删除 `window.__iv8__`。
- 动态 iframe 创建后隐藏 iframe realm 的宿主对象。
- 对空 iframe 派发浏览器式 `load`。
- 用 `wrapNative` 保护必要 patch 的函数外观。
- 只对 challenge 实际读取的 Canvas/DOM/WebGL 路径做映射。

### Phase 4：统一环境与传输

从同一成功 baseline 同步：

- `navigator.userAgent` 和 `appVersion`。
- `sec-ch-ua`、`sec-ch-ua-mobile`、`sec-ch-ua-platform`。
- `Accept-Language` 与 `navigator.languages`。
- screen/window/devicePixelRatio。
- Canvas PNG/JPEG/WebP、关键 `getImageData` 像素和尺寸。
- WebGL vendor/renderer/parameters/extensions。
- 与 baseline 接近的 `curl_cffi` impersonate。

当成功样本明确暴露 Client Hints 时，若其与 UA 浏览器家族或主版本不一致，优先修复；这是高收益假设，不是所有 Reese84 部署的固定协议字段。

### Phase 5：动态 token 与跟进

challenge 一般先发 GPC，再发 solution。Python bridge 捕获响应中的：

- `token`
- `renewInSec`
- `cookieDomain`

将 token 以服务端给定 domain 写入 session 后 replay。若当前站点证据表明 403 页面包含 UTMVC 脚本（常见参数为 `SWJIYLWA`），执行脚本、写入 `___utmvc`、发送对应 beacon（常见为 `SWKMTFSR`），再 replay。参数名以当轮脚本为准；通用 `_Incapsula_Resource` 字样不等于存在 UTMVC。

### Phase 6：业务请求

通过页面后，业务 API 必须复用 collector 的同一个 session。动态 cookie、UA、Client Hints、Referer 和 TLS profile 一起继承，不要把用户抓包中的整段 Cookie 粘回去。

将业务响应保存为：

```json
{
  "url": "...",
  "status": 200,
  "content_type": "application/json",
  "content_length": 12345,
  "request_headers": {},
  "response_headers": {},
  "data": {}
}
```

### Phase 7：验证门

依次执行：

1. `python -m py_compile <collector.py>`
2. `python -m unittest discover -s tests -v`
3. 新会话运行一次，保存完整证据。
4. 新会话再运行一次，确认 challenge URL、solution hash 和 token 都发生变化。
5. 请求真实业务 API，确认数据结构与浏览器样本一致。

### Phase 8：并发验证

只有串行链连续成功后才增加并发：

1. 先用 2 个任务验证，不直接压高并发。
2. 使用 `ProcessPoolExecutor` 和 `multiprocessing.get_context("spawn")`。
3. 每个进程内部新建 `Reese84Collector`，完整执行 bootstrap、challenge、token、replay 和可选业务请求。
4. 不在线程间或进程间共享 iv8 Context、Session、Cookie、token、challenge response 或 Canvas 可变对象。
5. 汇总结果只保留 worker id、耗时、challenge hash、round count、token 长度、replay/resource 状态和响应长度，不打印 token/Cookie。
6. 分别验证“只过 Reese”和“Reese + 业务 API”两种模式。
7. 记录 wall time、通过数和失败类型；任一 worker 失败时退出码非 0。

线程并发出现 `EventTarget.addEventListener: Illegal invocation` 时，不继续给线程加锁或重试；它说明 iv8 进程内运行时存在共享状态，应切换到进程隔离。详细模板见 `collector-blueprint.md`。

## 诊断优先级

GPC 尚未 200 时先分层：若响应含 `cf-mitigated: challenge` 或明确 Cloudflare challenge HTML，说明请求尚未到 Reese/Imperva，先处理 `edge-admission.md` 或转 `trace`，不要进入 Canvas 诊断。

token 已返回但最终 403 时，按顺序检查：

1. HTTP UA、Client Hints、TLS impersonate 是否同代。
2. JS UA/appVersion/userAgentData 是否与 HTTP 一致。
3. `window.__iv8__` 是否在主 realm 和 iframe realm 可见。
4. Canvas 是否按真实尺寸返回同源 PNG/JPEG/WebP 和像素，而不是所有画布返回同一张图片。
5. iframe `load`、Promise、timer 是否真正推进。
6. document 可见 Cookie 与 Python HttpOnly Cookie 是否混淆。
7. UTMVC 是否真的存在且 beacon 是否成功。
8. 最后才扩大字体、DOM layout、Audio、WebRTC 等 patch 面。

详细症状矩阵见 `failure-diagnostics.md`。

## 交付结构

默认在用户工作区交付：

```text
project/
├── collector.py
├── requirements.txt
├── README.md
├── tests/
│   └── test_static.py
├── js_reverse_cache/
│   ├── browser_env.json
│   ├── canvas_capture.json
│   └── challenge.js
└── output/
    └── run_<timestamp>.json
```

`requirements.txt` 至少包含明确版本范围的 `curl_cffi` 和 `iv8`。README 必须写出动态运行命令、成功判据、业务 URL 参数和静态分析素材的来源。

## 边界与转交

- 未定位到 Reese84 入口：返回 `trace` Observe/Capture。
- 已确认 Reese 但外层只有完整 Cloudflare Managed Challenge、没有 precursor 状态机证据：由 `trace` primary 固定外层，明确后返回本 profile。
- 已有非 Reese84 浏览器 JS，只要求 Python + iv8 执行：退出本 profile，返回本 skill 通用流程。
- 要纯 AST 还原 challenge：转 `trace` AST profile。
- 只要 DevTools Hook 观察 fetch/cookie：转 `trace` browser-hook profile。
- 明确瑞数 `$_ts`、`r2mKa`、Cookie S/T/P：退出本 profile；已明确选择 iv8 时走通用 challenge 路线，否则返回 `trace`。
- 验证码轨迹、点选、滑块：转 `captcha-reverse`。
- 非 Reese84 的完整多层协议恢复：转 `trace` 或对应协议 skill。
