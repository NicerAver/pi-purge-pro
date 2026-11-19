# Case: Bangkok Airways Reese84

此案例记录可迁移经验，不保存任何有效 token、Cookie 或完整 challenge。

## 目标

保护页面：

```text
https://digital.bangkokair.com/booking/availability/0
```

业务资源示例：

```text
https://digital.bangkokair.com/pg/statics/booking/content/1.0.16/en-GB.json
```

最终交付约束：Python + `curl_cffi` + 本地 `iv8`；运行时无浏览器。

## 已确认协议

1. 入口响应设置 `visid_incap_*` 和 `incap_ses_*`。
2. HTML 引用随机 query 的大型 Reese challenge。
3. challenge 先 POST `{"f":"gpc"}`。
4. 第二次 POST 发送 `solution/interrogation`。
5. 响应字段为 `token`、`renewInSec`、`cookieDomain`。
6. Python 写入 `reese84` 后 replay。
7. 某些 403 包含 `SWJIYLWA`，需要 UTMVC 和 `SWKMTFSR` beacon。
8. 通过后同 session 可请求约 1.9 MB 的 `en-GB.json`。

## 关键实验时间线

### 1. 传输可用性证明

将浏览器已接受的 solution body 放到新鲜 Python HTTP session 回放，最终得到真实应用文档。这证明：

- `curl_cffi` 能承接目标传输。
- Cookie/session/replay 代码基本正确。
- 阻塞核心在 iv8 生成的环境 payload，而不是 Python 不会请求。

### 2. 宿主对象泄漏

运行日志显示 challenge 使用 `Object.getOwnPropertyNames(Window)`。iv8 默认暴露 `window.__iv8__`。

处理：

- 在 `page.load` 前保存 lexical host 并删除 window 属性。
- 动态 iframe realm 同样删除。

结果：`p` 从一种高熵前缀切换到更接近浏览器样本的 `bin1` structured 分支，但最终仍 403。这说明修复有效但不是唯一条件。

### 3. Firefox 路线失败

曾尝试 Firefox 135/Camoufox 环境，但 iv8 realm 本身暴露大量 Chromium API。删除一部分 Chrome 特征仍无法形成完整 Firefox realm。

结论：不要逆着 iv8 的引擎家族硬伪装 Firefox；选择 Chromium baseline。

### 4. Canvas 不一致

初版环境出现：

- challenge 实际画布 600x160。
- 固定 PNG 是 240x60。
- `getImageData` 使用合成噪声。
- 所有画布可能返回同一 data URL。

后续采集并映射：

- 600x160 PNG/JPEG。
- 1x1 WebP。
- 4x4 transparent PNG。
- 5x5 pattern PNG。
- `getImageData(595,155,4,4)`。
- `getImageData(0,0,5,5)`。

切换为 coherent Canvas 后 token 内容变化，但仍 403，说明 Canvas 是必要一致性项但不是最后根因。

### 5. `old_token` 误判

成功浏览器样本的 envelope 带非空 `old_token`，新会话 iv8 为 null。尝试执行后续 challenge 后发现其 request body 只是已有 token JSON string，响应返回相同 token；这是 renewal，不是第二份完整 solution。

结论：不要把 `old_token` 当成可手工补的必要参数，也不要无限重复后续 token echo。

### 6. 决定性修复

成功浏览器抓包实际身份：

- UA：Chrome 150 Windows。
- Client Hints：Chromium 150 + Chrome/Edge 对应品牌。
- 页面环境：Chrome 150。

失败 collector 当时使用：

- UA/JS：Chrome 124。
- `curl_cffi`：chrome124。
- 请求头缺少或不匹配成功样本 Client Hints。

改为同一 Chrome 150 JS/HTTP 身份，并选择 `curl_cffi` 可用的最接近 Chrome 142 transport，同时发送匹配的 Client Hints 后：

- 第一轮 solution 即通过。
- replay HTTP 200。
- 返回约 132 KB 真实应用 HTML。
- 连续两次新会话成功。

这是本案例最重要经验：服务端返回 token 后仍 403 时，先检查跨层版本一致性，不要继续盲补低权重 API。

## 最终业务验证

通过 collector 后，在同一个 session 请求 `en-GB.json`：

- HTTP 200。
- `content-type: application/json`。
- 响应约 1,994,402 bytes。
- JSON 顶层为大量本地化 key/value。

没有复用用户抓包中的固定 Cookie。

## 并发验证

### 线程模式反证

首次使用 `ThreadPoolExecutor(max_workers=2)`，每个线程虽然各自创建 collector，但两个任务均失败：

- 一个 worker 在 iv8 challenge 中触发 `EventTarget.addEventListener: Illegal invocation`。
- 一个 worker出现 `curl: (28)` 30 秒连接超时。
- 通过数 `0/2`。

这证明“collector 对象不共享”仍不足以保证线程安全；iv8 同一进程内的 runtime/DOM 状态可能冲突。

### 多进程模式

切换为：

```text
ProcessPoolExecutor
multiprocessing.get_context("spawn")
每个进程独立 Reese84Collector
每个进程独立 iv8 runtime
每个进程独立 curl_cffi Session/Cookie jar
```

测试一：两个进程只执行 Reese 链：

```text
concurrency = 2
total = 2
passed = 2
failed = 0
all_passed = true
wall_time = 14.211 秒
两个 replay 均 HTTP 200
两个应用 HTML 均约 132,668 bytes
```

测试二：两个进程执行 Reese + `en-GB.json`：

```text
concurrency = 2
total = 2
passed = 2
failed = 0
all_passed = true
wall_time = 11.927 秒
两个 resource status 均为 200
两个 resource length 均为 1,994,402 bytes
```

结论：该案例支持进程级并发，不支持同进程线程级 iv8 并发。并发脚本不输出 token/Cookie，只输出 challenge hash、token 长度、状态、内容长度和耗时。

## 可迁移结论

1. 先用接受的浏览器 solution 证明 Python transport，再调 iv8 环境。
2. token endpoint 200 不是成功判据。
3. `Object.getOwnPropertyNames(window)` 是发现 host 泄漏的重要线索。
4. iv8 Chromium realm 不适合硬伪装 Firefox。
5. Canvas 必须按尺寸、像素和编码 coherent。
6. `old_token` 必须由协议自然产生，不能猜。
7. UTMVC beacon 成功不代表 Reese 评分成功。
8. UA、Client Hints、JS environment 和 TLS profile 同代是高优先级。
9. 业务 API 必须复用通过挑战的同一 session。
10. 连续两次新会话成功才可交付。
11. iv8 并发使用 spawn 多进程，每个 worker 独立 Session/runtime；不要使用线程池。

## 不应复制的站点特定值

- challenge 随机路径/query。
- session shard 编号。
- Cookie domain 之外的具体 Cookie value。
- token 长度。
- `renewInSec`。
- Canvas base64。
- GPU 名称。
- screen 尺寸。

新目标必须重新采样这些值。
