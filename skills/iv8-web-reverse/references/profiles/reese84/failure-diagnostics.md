# Failure Diagnostics

## 总原则

诊断按“外层 admission 是否通过、Reese 协议是否执行、环境是否一致、传输是否一致、跟进是否完成”分层。不要看到 403 就继续堆浏览器 API。

## 症状矩阵

| 症状 | 高概率原因 | 首个验证 | 正确动作 |
|---|---|---|---|
| 入口 200，但短 HTML 只有挑战脚本 | 200 是 interstitial | 比较 content length/doctype/app marker | 继续发现 challenge，不判成功 |
| 找不到 challenge | 动态赋值、路径随机或受信 CDN 跨域 | 搜 `<script src>`、`scriptElement.src` 和 accepted sample | 按受限 origin allowlist 下载候选并查 Reese 特征 |
| GPC 403 且 `cf-mitigated: challenge` | 请求被 Cloudflare 外层截获，尚未到 Reese | 看 entry 是否有 `__CF$cv$params`/precursor | 有独立 precursor 证据则先解 admission；完整 Managed Challenge 转 `trace` |
| precursor eval 报短变量未定义 | 生产代码依赖随机闭包符号 | 比较多份在线脚本的闭包名 | 执行原始生命周期，以 fake XHR 取 wire request |
| precursor event loop 永不返回 | 永久 interval 被无条件 drain | faulthandler/最后 timer | 目标 XHR 到达即退出，或固定次数 microtask/sleep |
| 已有新 clearance 但 GPC 仍被 Cloudflare 拦截 | admission payload/Session/transport 未被完整接受 | 同 Session reload、检查动态 hash 和响应层 | 不复制浏览器 clearance；重建 fresh admission 并保留证据 |
| challenge eval 无网络 | page/load/event loop 不完整 | 查 bridge errors、netLog | 先修生命周期，不补指纹 |
| 只发 GPC 不发 solution | Promise/timer/iframe 未推进 | 查看最后事件和错误 | drain microtasks/sleep/drain，补 iframe load |
| solution POST 400/解析失败 | envelope/body/header 被改写 | 与浏览器原始 body 比较 | 由 challenge 原样构建，Python 不重排字段 |
| 返回 token，replay 仍 403 | 环境评分不足或跨层不一致 | 对照 UA/CH/TLS/JS/Canvas | 按一致性优先级修复 |
| `p` 从高熵变 structured | 环境探测进入另一分支 | 检查 `window.__iv8__` 可见性 | 主/iframe realm 隐藏宿主 |
| `p` 长度接近成功样本但仍失败 | 长度不是语义 | 比较最终 replay | 停止按长度调参 |
| UTMVC beacon 返回 `1` 仍 403 | Reese token 本身评分不足 | 用已知成功 Reese token走同 UTMVC | 回到首轮环境，不重复 beacon |
| 后续脚本 POST token string | 续期/确认，不是新 solution | 看 body 是否有 `solution` | 相同 token 收敛停止 |
| 每轮 token 完全相同 | 重复续期或旧 Cookie 回退 | 比较 challenge URL/token | 阻止无限循环，检查首轮 |
| `curl: (16)` | HTTP/2 session 状态错误 | 新 session 复制 cookies 重试 | 有界重建 session |
| `curl: (35)` | TLS 握手瞬态/库状态 | 新 session 单次重试 | 仍失败则报告网络/TLS blocker |
| 线程并发出现 `EventTarget.addEventListener: Illegal invocation` | iv8 同进程 runtime/DOM 全局状态冲突 | 单线程成功、两个线程同时失败 | 禁用线程池，改用 spawn 多进程隔离 |
| 并发 worker 出现 `curl: (28)` | 连接超时、目标限流或并发瞬态 | 同 worker 串行是否稳定、其它进程是否成功 | 先降低进程并发并记录，不修改签名算法或共享 Session |
| Reese 成功但业务 API 403 | 新建了 Session 或 header 身份改变 | 比较 Cookie jar/UA/CH | 复用 collector session |
| JSON API 200 但解析失败 | 返回的是 challenge HTML | 看 content-type/body prefix | 判 blocked，不把 HTML 当 JSON |
| 业务 API 400 且有明确业务 error code | 行程/参数校验，不一定是鉴权 | 看 JSON error、相邻 API 和 blocked markers | 调整动态业务输入，不回退修改 Reese/admission |

## 0. GPC 前的 edge admission

若 GPC 响应来自 Cloudflare，当前最早失败层是 edge admission。此时 solution 尚未执行，Canvas/WebGL/`p` 长度都不是首要变量。按 `edge-admission.md` 保存 entry、动态 edge script、request body hash、响应和 Cookie transition；只有同一 Session reload 后 GPC 进入 Reese 层，才继续环境诊断。

复制浏览器成功 GPC body、完整 Cookie header 或固定 clearance 后仍 403，是“上下文不一致”的反证，不是 Reese body 错误的证据。反过来，precursor 200 和 jar 中出现 clearance 也不是完成判据，必须继续验证 GPC、solution、replay 和业务。

## 1. Token 返回不等于成功

服务端可能对任何结构合法的 envelope 返回 `reese84`，但 token 内含风险评分或环境判断，最终 document 仍返回 403。

必须记录：

- token endpoint status。
- token length 仅作观察。
- replay status。
- replay content-type/length/prefix。
- blocked markers。

最终判据永远是业务页面/API。

## 2. `old_token` 误区

浏览器成功抓包可能带非空 `old_token`，新会话 iv8 payload 为 null。这不自动证明失败原因就是 `old_token`。

验证步骤：

1. 确认成功样本是否来自已运行一段时间的浏览器。
2. 查看后续 challenge 是完整 solution 还是仅 token renewal。
3. 不要把刚返回的 token 手工塞进旧 envelope 再发。
4. 新会话能够成功时，`old_token=null` 是合法路径。

## 3. `__iv8__` 泄漏

典型证据：

- `Object.getOwnPropertyNames(window)` 被频繁调用。
- 删除 `__iv8__` 后 `p` 的 decoded prefix/结构显著变化。
- 主窗口已隐藏，但 iframe 仍暴露。

排查脚本应同时报告：

```javascript
({
  main: Object.getOwnPropertyNames(window).filter(x => /iv8/i.test(x)),
  iframe: Object.getOwnPropertyNames(iframe.contentWindow).filter(x => /iv8/i.test(x)),
  chromeType: typeof window.chrome,
  uaDataType: typeof navigator.userAgentData
})
```

不要为隐藏 iv8 顺便删除正常 Chrome API。

## 4. Canvas 自相矛盾

按 challenge 运行日志列出每个调用：

```text
canvas size | operation | args | returned type/length/hash
```

重点查：

- `getImageData(595,155,4,4)` 是否超出 600x160 末端且应为透明。
- `getImageData(0,0,5,5)` 是否来自真实 5x5 pattern。
- 4x4 transparent PNG 与 5x5 pattern PNG 是否不同。
- data URL 内 PNG IHDR 尺寸是否与 canvas 一致。
- JPEG/WebP 是否来自同一 Chromium runtime。

如果只是把一个固定 data URL 填进 iv8 environment，challenge 的多个尺寸调用很可能全部得到同一图，必须在 prototype patch 按尺寸分流。

## 5. 浏览器家族混拼

失败例：

- Firefox Canvas + Chrome UA。
- Camoufox Firefox navigator + Chromium iv8 globals。
- Chrome GPU + Firefox extension list。
- Chrome 124 UA + Chrome 150 Client Hints。

修复不是“把两边都补全”，而是选一边作为唯一 baseline，重采同一套数据。

## 6. Client Hints/TLS

当以下都已成立但仍 403：

- challenge 正常执行。
- host 已隐藏。
- iframe load 正常。
- Canvas coherent。

当成功样本包含这些字段时，立刻对比：

- User-Agent。
- `sec-ch-ua` 品牌和版本。
- `sec-ch-ua-platform`。
- `curl_cffi` impersonate。

这是高收益检查，不是所有部署都固定要求 Client Hints。一次真实案例中，从 Chrome 124 改为成功样本的 Chrome 150 UA/Client Hints，并使用工具可用的最近同家族 Chrome 142 transport 后，单轮从稳定 403 变为真实 132 KB 应用 HTML。

## 7. HTTP 重试

只重试明确传输错误，不重试业务 403：

```python
RETRYABLE = ("curl: (16)", "curl: (35)")
```

重建 session 时复制当前动态 cookies，并保持 impersonate/base headers。最多重试一次或有限次数，记录发生原因。

## 8. 最小报告格式

每轮诊断输出：

```text
run_id=
challenge_sha256=
baseline=
ua=
sec_ch_ua=
impersonate=
host_hidden_main=
host_hidden_iframe=
canvas_profile_hash=
p_length=
edge_layer=
edge_script_sha256=
edge_request_sha256=
edge_status=
token_received=
replay_status=
replay_length=
blocked_markers=
single_change=
conclusion=
```

## 9. 并发诊断

Reese84 并发必须把“iv8 隔离”和“HTTP Session 隔离”同时满足：

1. 如果线程模式出现 `Illegal invocation`，停止线程实验；不要把异常截断后当作随机 challenge 失败。
2. 使用 `ProcessPoolExecutor`，Windows 显式指定 `spawn`。
3. 每个进程从无目标 Cookie 的新 Session 开始。
4. 父进程只聚合脱敏摘要，不接收完整 `result`，避免大 JSON 和 token 跨进程序列化。
5. 两个进程得到相同 challenge hash 不代表共享 Session；目标在同一时间窗口可能下发同一脚本。应同时确认各 worker 独立完成 replay，且 token/Cookie 不跨 worker 复制。
6. 先测试保护页面，再测试业务 API。后者成功才证明每个进程的 Session 生命周期完整。
7. 并发结果至少记录 `passed/failed/all_passed/wall_time_seconds` 和每个 worker 的耗时、状态、内容长度、错误类型。

没有 `single_change` 的多项混改无法归因，不作为可靠经验写回 skill。
