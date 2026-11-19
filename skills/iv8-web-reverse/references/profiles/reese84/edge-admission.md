# Reese84 Edge Admission

## 1. 适用范围

某些已确认 Reese84 的站点在 GPC/solution 前还有独立 CDN admission。典型状态是：入口 HTML 已引用 Reese challenge，但 Reese GPC POST 被外层 Cloudflare 拦截。

只有同时满足以下条件才进入本分支：

1. Reese84 已由名称、GPC/solution envelope 或 token/cookieDomain 证据确认。
2. 外层 admission 有独立证据，例如 `cf-mitigated: challenge`、`server: cloudflare`、`window.__CF$cv$params`、`/cdn-cgi/challenge-platform/.../precursor/` 或当轮 `main.js`。

只有普通 Cloudflare 403、完整 Managed Challenge、`cf_clearance` Cookie 名或未知多层 interstitial 时，不在 Reese profile 猜解；交给 `trace` 固定外层状态机。外层入口明确并能由 iv8 承接后，再回到本 profile 完成 Reese 和业务验证。

## 2. 状态所有权

把 edge admission 放在 Reese 之前，不能把它当作 Canvas 或 solution 评分问题：

```text
BOOTSTRAP
  -> EDGE_ADMISSION (optional, independently evidenced)
  -> RELOAD_ENTRY
  -> GENERATE_REESE
  -> INSTALL_TOKEN
  -> REPLAY
  -> BUSINESS
```

状态归属：

| 层 | 状态 | 所有者 |
|---|---|---|
| Edge admission | precursor params、动态 edge JS、admission POST、clearance | Python Session + 独立 iv8 context |
| Reese protocol | GPC、solution、token、renewInSec | Reese challenge + Python bridge |

两层可以各用一个 iv8 context，但必须共享同一个 Python `curl_cffi.Session`、Cookie jar、UA、Client Hints 和 transport profile。不要把 edge context 的 JS 对象或 timer 状态带进 Reese context。

## 3. 必存证据

至少记录：

```json
{
  "entry_status": 200,
  "edge_markers": ["window.__CF$cv$params", "precursor"],
  "script_url": "dynamic current URL",
  "script_sha256": "...",
  "ray_or_request_id": "...",
  "request_url": "dynamic current URL",
  "request_body_length": 0,
  "request_body_sha256": "...",
  "status": 200,
  "response_body_prefix": "...",
  "clearance_set": true
}
```

Cookie 值只保存在授权项目的私有 evidence，不写入 skill、公开报告或 frozen case。

## 4. Precursor 恢复流程

当入口明确包含 precursor 参数和脚本时：

1. 从当轮 HTML 提取 params，不复用旧 ray、时间字段或 URL。
2. 用同一 Session 下载 HTML 当前引用的 precursor `main.js`。
3. 在独立 iv8 context 中加载当前 HTML snapshot，执行原始脚本。
4. 用 fake XHR 只记录脚本生成的 method、URL 和 body；真实 POST 仍由 Python Session 发出。
5. 按浏览器请求保持 Origin、Referer、Content-Type、UA、Client Hints 和 transport coherence。
6. admission POST 成功且 Session 收到动态 clearance 后，重新 GET entry，再进入 Reese challenge。
7. precursor 失败时不要继续 GPC；保存错误并有界重建新 Session/新 entry。

🔴 CHECKPOINT：真实 admission POST 前列出当轮 entry URL、params/request id、edge script URL/SHA、Session Cookie 来源、UA/Client Hints/impersonate、预期状态和失败 fallback。任一动态字段来自旧样本时不发送。

`cf_clearance` 出现在 jar 中不是充分条件。至少还要确认 admission response 合理、entry reload 可继续、Reese GPC/solution 200 和最终业务放行。

## 5. 动态脚本随机化

Cloudflare precursor 的闭包变量和 sender 函数名可能按响应变化。分析时暴露的 `V`、`l`、`F` 或其它短名不能进入生产实现。

优先顺序：

1. 运行原始当轮脚本和官方生命周期。
2. 通过 fake XHR/netLog 观察 wire request。
3. 只有真实 timer 延迟阻碍离线生成时，才基于当轮证据做窄 timer hook。

可接受的 timer hook 必须：

- 只命中已确认的 admission 长 timer。
- 一次性触发，后续同级 timer 只返回句柄，避免递归。
- 有执行次数和 wall-time 上限。
- 不改写请求 body、ray 或脚本内时间字段。

仅在当轮证据确认 admission 使用长 timer 后，采用类似的窄模板；阈值来自当前脚本/params，不是协议常量：

```javascript
const nativeSetTimeout = window.setTimeout;
let admissionTimerFired = false;
window.setTimeout = function(callback, delay) {
  const wait = Number(delay) || 0;
  if (wait >= evidencedAdmissionDelay) {
    if (!admissionTimerFired) {
      admissionTimerFired = true;
      callback();
    }
    return 1;
  }
  return nativeSetTimeout(callback, wait);
};
```

不要无条件 `eventLoop.drain()`：precursor 常注册永久 interval，drain 可能永不返回。优先读取首个目标 XHR后立即结束 context；确需推进时使用固定次数的 microtask/sleep，并逐轮检查目标事件。

## 6. 403 分层

遇到 GPC 403，先看 response headers/body：

| 证据 | 结论 | 动作 |
|---|---|---|
| `cf-mitigated: challenge` + Cloudflare HTML | GPC 尚未到 Reese/Imperva | 处理 edge admission，不补 Canvas |
| 完整 Managed Challenge HTML，无已确认 precursor | 外层状态机仍未知 | 转 `trace`，不伪称已有通用 solver |
| 无 Cloudflare marker，响应来自 Imperva/Reese | 已进入 Reese 层 | 回到 environment/TLS/Canvas/UTMVC 诊断 |
| GPC 200、solution 200、token 返回但 replay 403 | Reese 评分或跟进问题 | 按 environment consistency 排查 |

把浏览器成功 GPC body、完整 Cookie header 或固定 clearance 复制到 `curl_cffi` 后仍 403，只能证明 admission 与当前 Session/transport 不一致，不能证明 GPC body 错误，也不能证明 Python transport 永远不可用。

## 7. 验证门

存在 edge admission 时，fresh 验证除 Reese 证据外还要确认：

- 每轮从无目标 Cookie 的 Session 开始。
- edge script hash、request id/ray 或 body hash来自当轮动态材料。
- clearance 由同一 Session 当轮获得，不从浏览器导入。
- 至少两轮中 edge request、Reese challenge/solution 和 token 有动态差异。
- GPC/solution、replay 和业务接口均按预期通过。

业务 API 的 4xx 还要区分鉴权拦截和合法业务校验错误。检查 content-type、业务 error code 和相邻 API；不要把 `INVALID ITINERARY`、无航班或参数校验误报为 Reese/admission 失败。

## 8. 禁止项

- 固定 ray、precursor URL/body、clearance 或浏览器 Cookie。
- 只因 Cookie 名存在就宣称 Cloudflare 已识别。
- 把任意 Cloudflare Managed Challenge 都称为 precursor。
- 依赖随机闭包短变量名。
- precursor 求解失败后仍继续 Reese GPC 并堆环境 patch。
- 为等待 timer 无上限 drain event loop。
- edge 与 Reese 使用不同 Session、UA/CH 或 transport profile。
