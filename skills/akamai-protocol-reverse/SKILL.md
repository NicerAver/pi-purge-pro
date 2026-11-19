---
name: akamai-protocol-reverse
description: >-
  Akamai pure-protocol recovery requires an Akamai-native marker, independent network/script/cookie-transition/transport corroboration, and a browser-free goal; a lone marker, 403, Reese84 label, or evidence-only request never selects this skill. Use `_abck`/`bm_sz`/`ak_bmsc`/
  `bm_s`/`bm_sc`/`sbsd_c`/`sec_cpt`/`sensor_data`. Markers also include
  `sbsd_o`, `/akam/13/pixel_*`, `cpr_chlge`, or a confirmed random collector.
  Browser-free Python collector only. Confirmed Imperva/Incapsula Reese84 chains belong to
  `iv8-web-reverse`, never this skill; a lone Reese84 label remains Trace triage. Covers
  multi-stage sensor POSTs, SBSD/CPR
  `{"body":...}`, dynamic `v`/`t`, 115-key signals, local fingerprint
  caches, TLS/UA/Client-Hints coherence, and `sec_cpt` verifier chains.
  Do not use for unidentified 403/412, cookie name alone, generic sign tracing, DevTools hooks,
  AST, CAPTCHA, Reese84 collector work, legacy 1.7 generators, or final browser automation; route to
  trace, iv8-web-reverse, or captcha-reverse.
argument-hint: "[目标 URL/API URL] [业务接口]"
compatibility: "需要 Python 3；协议实现通常需要 curl_cffi，host-bound collector 路线需要 iv8；新目标侦察优先 js-reverse Edge，必要时 chrome-devtools / Camoufox"
---

# Akamai Protocol Reverse

## Role

把已确认的 Akamai Bot Manager Web 客户端还原成浏览器外运行的协议客户端。

最终交付必须是以下之一：

1. 纯 Python HTTP + 已还原算法
2. Python HTTP + 本地窄 JS helper
3. Python HTTP + 本地 IV8 bootstrap executor

浏览器只用于侦察和证据采样。不要把 Chrome、CDP、Playwright、Selenium、浏览器 profile 或人工 cookie 留在最终请求链中。

## Trigger Boundary

至少需要一个 Akamai 原生标记，再加一个独立佐证面：

- Cookie：`_abck`、`bm_sz`、`ak_bmsc`、`bm_s`、`bm_sc`、`sbsd_c`、`sbsd_o`、`bm_sv`、`bm_so`、`bm_ss`、`bm_mi`、`bm_lso`、`sec_cpt`
- 网络：带 `sensor_data` 或 JSON `{"body":...}` 的同源 collector/SBSD POST、`cpr_chlge`、带 `?v=` 或 `?v=&t=` 的动态 SBSD script、`/akam/13/pixel_*`、随机无扩展 collector URL、`sec-cp-challenge` descriptor、`provider=crypto` verifier
- 脚本：Akamai 2/3 collector、`bmak`、challenge descriptor、SHA-256/modulo proof-of-work
- 传输：应用响应前出现 Akamai `Server-Timing: ak_p`；HTTP/2 `INTERNAL_ERROR` 或 transport-profile 差异只能作为佐证，不能单独确认 Akamai

只有一个普通 403、单个 `_abck`/`bm_*` cookie、单个 `sec_cpt`、验证码或未知 cookie 名时，不要猜 Akamai，也不要让 marker 词面覆盖任务目标；先转 `trace` 做家族识别。

相邻任务转交：

- 未确认家族、完整协议恢复：`trace`
- 只定位函数、脚本 URL、调用栈：返回 `trace` Observe/Capture，通过当前浏览器逆向工具取证；需要反检测或指纹基线时用 Camoufox MCP
- 用户只要 DevTools hook：`trace` browser-hook profile
- 已知 JS 入口的通用 IV8 交付：`iv8-web-reverse`
- 用户明确指定 NV8，且 Akamai sensor 入口、固定输入/输出和验收边界已经由本 skill 证实：`nv8-node-runtime` 作为 secondary artifact backend；Akamai 保持 primary，Python 仍负责最终 HTTP 和业务回放
- AST 解混淆：`trace` AST profile
- Akamai 验证码或交互验证：`captcha-reverse`
- 通用 Node.js 环境补丁：`trace` env-patch profile

## Startup Gate

若用户明确要求“只输出阶段门”，按 `../_shared/js-reverse-workflow.md` 的 Stage-Gate Output 返回 `MODE`、`OWNER`、`NEXT_GATE`、`REQUIRED_EVIDENCE` 和 `DO_NOT_USE`，不要开始取证或实现。`skill_checkpoint` 字段规则见同文件 Checkpoint Fields。

第一次深度调用工具前报告：

```text
Akamai Startup Gate
- Authorization/scope:
- Evidence: cookie / network / script / transport
- recon browser: js-reverse Edge / chrome-devtools / Camoufox
- Family: verifier-gated [+ transport-gated]
- Intended delivery: pure Python / Python + JS / Python + IV8
- Local fingerprint source: host-captured / foreign-cache rejected
- Final browser dependency: rejected
```

执行：

1. 运行 `python scripts/check_akamai_env.py`。
2. 新目标优先用 `js-reverse`：
   - 普通 Chrome 被拦时切 `launch_browser({browser:"edge"})`
   - 需要更强反检测时再用 Camoufox
   - `chrome-devtools` 仅作辅助基线
3. 导出 collector GET、每次 sensor POST body/header/`Set-Cookie`、业务成功/失败请求。
4. 如果选择 NV8 secondary，先确认 `nv8-node-runtime` 可用、sensor 入口已固定、目标脚本哈希和输入/输出契约已保存；NV8 只生成窄 artifact，真实网络和最终业务回放仍走本 skill 的 Python Session。
5. 用户指定普通 Google Chrome 时只用普通 Chrome。不要为了释放 profile 锁结束不属于当前任务的浏览器进程。
6. 工具冲突时报告阻塞并顺序切换，不要并发串会话。

## Maintenance Check

边界、handoff 或 eval 修改后运行 `python scripts/validate_skill.py <skill-root>`，再运行通用 `quick_validate.py`。

## Non-Negotiables

- 用一个 fresh Python Session 串起首跳、动态脚本、sensor POST、route 和业务 API。
- 不复制侦察浏览器 cookie 到最终 session。
- 不硬编码随机 collector URL、`scid`、时间戳或服务端种子。
- stored jar、`document.cookie` 与最终出站 `Cookie` header 是三种证据，不要混为一谈。
- `_abck` / `bm_s` 长度不是成功判据。以 server response、cookie transition 和业务 replay 为准。
- TLS profile、UA、Client Hints 和 sensor 内 UA 必须同代；记录 `curl_cffi` 版本、实际可用 profile 清单与真实浏览器 major 的差距。先测试最新已安装 profile，不能因旧 profile 全部 403 就直接归因出口。
- 本地 collector 的网络 bridge 只能转发当前 HTML/CPR 中发现的同源精确 URL。捕获的随机 URL 仅在本轮完全未发现实时 URL 时作诊断 fallback，不能在动态发现成功后继续追加请求。
- **禁止直接复用他人机器的 canvas / systemColors / WebGL 指纹缓存**；必须在执行主机重采。
- 在升级 Akamai 家族、transport gate 或 specialist handoff 前，至少保留两类独立证据（例如网络 collector + cookie transition，或脚本 marker + 业务回放）；单个 `_abck`、403、`sensor_data` 或 helper 输出只能作为假设。
- sensor 可能是多阶段：不能在第一次 POST 后立刻停 event loop。某个观测阶段本地未触发时，只有至少两次独立 fresh 业务 replay 成功才能把它标为“当前路由非门禁”；失败时仍回到 lifecycle/timer/cookie mirroring 排查。
- 业务返回有效 `sec_cpt` crypto descriptor 后停止追加 collector pass，进入独立 verifier 状态机。每轮使用当前 descriptor，`count` 个 answer 必须逐项验证；中间 token、difficulty 下降或 HTTP 200 不是完成判据。
- 每次本地 JS 执行使用唯一 run-id/temp input/output；禁止 collector 1/2 共用固定文件导致并发结果串线。
- 业务 403 时先区分 **egress reputation**、transport/TLS admission、sensor confidence、CSRF/form serialization、route-local context。
- **间歇性 Access Denied 优先当出口问题**：同一实现、换节点后立刻恢复，不要先重写算法/表单。
- 先用**同一出口**做浏览器手测（首页 + 业务 document 路由）。浏览器也 Access Denied → 换节点；浏览器正常而协议失败 → 再查实现。
- 先恢复一个业务请求，再考虑分页、并发、代理池或批量任务。
- 最终失败只剩浏览器逐请求依赖时，报告 blocker；不要交付自动化 fallback。

## Execution Flow

### 1. Capture a clean state machine

保存至少这些边界：

1. 首个 document 请求/响应和全部 `Set-Cookie`
2. collector GET
3. **每一次** sensor POST 的 body 大小、Content-Type、cookie 与响应
4. Pixel 请求及其 cookie 更新（若有）
5. route document 的 cookie 更新
6. 一个成功和一个失败的业务请求（例如 choose / API）

读取 `references/cookie-state-machine.md`。

### 2. Separate Akamai components

- 随机同源 collector 负责 sensor body 与 `bm_*` / `_abck` 更新。
- `/akam/13/*` 是 Pixel 支线，不要与主 collector 混成一个函数。
- SBSD/CPR `{"body":...}` POST 是二验分支；它常由 `bm_so` / `sbsd_o` 种子、动态 `?v=` / `?v=&t=` script、115-key `signals`、VMP 完整性 key 和 `bm_s` / `bm_sc` / `sbsd_c` 通过态串起来。读取 `references/sbsd-body-vmp.md`。
- 业务 CSRF、session id、NetFunnel ticket、route context 属于服务端业务状态。
- 站点可能叠 NetFunnel / 自建 WAF；先拆分门禁再修 Akamai。

### 2A. Handle SBSD / CPR body-VMP

触发条件：业务或 document 返回 `{"cpr_chlge":"true","t":"..."}`、HTML 下发 `?v=` / `?v=&t=` SBSD script、抓包出现 JSON `{"body":"..."}` POST，或 `bm_so` / `sbsd_o` -> `bm_s` / `bm_sc` / `sbsd_c` cookie transition。

执行要求：

1. 保存当前 HTML、SBSD script URL、`v`、`t`、最终 POST URL、请求 body 大小与 `Set-Cookie`。
2. XHR/fetch 断点暂停 POST，优先从 scope 取加密前 payload：`ver + signals + perf + s + tid`。
3. 不硬编码动态 key；建立“动态 key -> 稳定语义”模板，特别标注 `timestamp_ms`、`bm_so_hash`、`signal_integrity_hash`。
4. 按当前 script 还原 key115：Phase 1 `bm_so + timestamp -> bm_so_hash`，Phase 2 114 个 signals 的滚动 hash，Phase 3 `stage1_hash + bm_so + timestamp -> signal_integrity_hash`。
5. 记住 `v` 会参与 body 字符替换加密；最终 POST URL 可能只保留 `t`，但不能丢掉 script URL 上的 `v`。
6. `bm_sc` / `sbsd_c` 的 `2~1~...`、`4~1~...` 是 SBSD 通过证据，不是业务成功判据；仍需同一 Python Session 重放业务接口。

### 2B. Handle direct three-stage `sensor_data` collectors

Use this branch only when the live trace shows an Akamai-native `sensor_data` collector plus an independent cookie, script, or network corroboration. The article-backed pattern is a direct collector lifecycle: document GET -> current Akamai JS GET -> pre-encryption runtime object -> three sequential sensor POSTs -> business replay. It is a recovery shape, not a fixed recipe.

1. Capture the first document, every `Set-Cookie`, the exact current JS URL, and the exact collector POST URL. Do not assume the JS resource URL is also the POST target. Record all three stages separately, including body framing, size, Content-Type, request cookies, response cookies, and timing.
2. In a disposable reverse-execution context, preserve the native `Function.prototype.toString` fallback only where the current script's format checks require it. Remove logging and hooks from the final runtime. If function location or AST restoration is the actual task, hand it to `trace`; this branch consumes runtime evidence and does not make AST rewriting its trigger.
3. Break on `sensor_data` construction or XHR/fetch and capture the pre-encryption object. A common observed path is `dcK -> RNK -> 13b`. Build a current-script semantic map rather than copying obfuscated names, field order, or sample values from a different run.
4. Treat `din` as an ordered array. Common observed semantics include screen dimensions, UA, language, `Gecko`, availability dimensions, timing-derived fields, an environment capability string, a random field, and a JS-path-derived field. The exact keys, order, and values are version and host dependent.
5. Re-derive `ajr`, `fpt`/`fpc`, `dvc`, `nfas`, `fwd.ssh`, `ver`, and `previousValue` from the current collector. `ajr` may have several daily or script-version branches; `startTs`, `deltaTimestamp`, `totVel`, UA suffixes, random values, and mouse timing are inputs, not constants. `fwd.ssh` can depend on `speechSynthesis.getVoices()` and a current voice serialization routine.
6. Treat `mst` and mouse fields as lifecycle data. An observed sample uses 21 mouse points, with the first stage having no mouse trace and later stages carrying real points. Preserve event order, timestamps, and timer/Promise settling; do not assume that a point count alone satisfies the current policy. Compare `mc`, `mevl`, `devl`, `dmvl`, `tovl`, and `delt` across stages.
7. Treat `sww` as asynchronous runtime data when present. Observed values are collected through a `SharedWorker` message path and can include UA, GPU, network, locale, timezone, screen/runtime, and User-Agent Client Hints data. Re-sample WebGL, canvas, system colors, and related values on the execution host. A missing `SharedWorker` requires a faithful host bridge or IV8 path, not a foreign cache.
8. Use stage diffs as hypotheses, not constants. One observed collector had `ajt=0.0`, `ajt=11.1`, and `ajt=10.2` for stages zero, one, and two; the third stage added `dsi`, while `ajr`, random fields, mouse timing, and `tovl` changed. Confirm the current script and network samples before implementing any branch.
9. Prove the encryption inputs from the current JS. The observed shape derives a seed from the first HTML `bm_sz`, falls back to `previousValue`, shuffles serialized JSON, applies a printable-character transform, and wraps it with `ver` and per-run metadata. Verify the current delimiter, seed index, alphabet, arithmetic, and wrapper fields; never paste a stale `bm_sz`, token, timestamp, or `ver`.
10. Replay all stages sequentially in the same fresh Python session and then replay one business request. Use the exact observed collector endpoint and current transport headers. Do not force HTTP/3, read only `response.cookies`, use an undefined UA variable, or set `ffs`/`vev`/`inf` empty without current-script and accepted-request evidence. HTTP 200, a short `_abck`, or a completed third POST is not success; require cookie transition plus two independent business replays.

Read `references/wechat-akamai-sensor-data.md` for the article evidence and replay corrections. The article's observed `fwd.fmz="1.75"` is a field value and does not re-enable the excluded legacy 1.7/1.75 generator family.

### 3. Diff fixed inputs and framing

先比较：

- sensor POST **次数**、时序、body size 序列
- Content-Type（常见 `application/json` 包一层 `{"body":...}`）
- Cookie request -> response -> next request 连续性（尤其 `bm_s` 旋转）
- 响应状态 200/201/202
- 业务成功包与失败包的 header 集合差异（有无 Sec-Fetch / Priority）

若浏览器是多阶段而本地只有一阶段，优先修 lifecycle / timer / input settle，不要先重写算法。只有业务 endpoint 在至少两次独立 fresh session 中都返回预期结构时，才可记录缺失阶段对“当前路由/当前策略”非门禁；保留该分支实现与证据，因为策略可能轮换。

### 4. Align transport and runtime

读取 `references/transport-coherence.md`。

最小 admission matrix：

- Chrome vs Edge recon
- 当前安装的 `curl_cffi` 版本与 `BrowserType` profile 清单
- 最新可用 profile + 一个旧 profile 对照（例如 chrome146 vs chrome136；不要把示例版本当永久常量）
- profile-matched UA / Client Hints / sensor UA
- 直连 vs 显式代理
- 首页 / main route / collector POST / 业务 POST

若同出口浏览器 200、旧 profiles 403，而更新 `curl_cffi` 后的新 profiles 200，这是 profile 代际 admission，不是 egress reputation。读取 `references/case-vueling-sbsd.md`。

系统代理必须显式记录。交付物优先 `trust_env=False` + 单一 `AKAMAI_PROXY`。

### 5. Host-local fingerprint cache

读取 `references/iv8-live-collector.md` 与 `references/case-twayair-iv8.md`。

在任务目录 `js_reverse_cache/` 用**本机**浏览器采集：

- canvas dataURL / multi-size profiles
- system colors
- WebGL unmasked vendor/renderer
- hardwareConcurrency / deviceMemory / screen / dpr

他人仓库里的 `cloak_*` / `collector_canvas_*` 只可作对照，不可直接当运行时输入。

### 6. Choose the smallest offline shape

优先级：

1. 已证明的纯 Python port
2. 下载当前 collector 后用本地 JS/IV8 执行
3. IV8 `page.load` + 最小环境 + Python XHR bridge + multi-stage settle

### 7. Handle `sec_cpt` crypto challenges

业务响应包含已确认的 `sec-cp-challenge` / `provider=crypto` descriptor 时，读取 `references/crypto-challenge.md`。

最小完成链：

1. 保存业务 challenge、`sec_cpt` flag 1、challenge HTML 和动态 verifier script。
2. 从浏览器 accepted requests 或暂停帧恢复 hash framing；不要猜 nonce/token 拼接。
3. 每轮按当前 `timestamp`、`nonce`、difficulty、count、token 和动态 `verify_url` 生成全部 proof，并匹配浏览器 worker cadence。
4. 最终 verifier success 后证明 `sec_cpt` flag 2，再完成 cp verification 到 flag 3。
5. 在同一 Python Session 重放原业务请求；不要回到 collector 重试。

若 fresh 浏览器与协议在多个 API endpoint 同时 H2 protocol error，而 document/CDN 正常，先按上游/API 事件或 shared fresh-session admission 记录并暂停；持久浏览器成功不能替代 fresh 对照。

### 8. Recover the business contract

从**浏览器成功包**还原 form/API serialization：

- 字段集合与空字段是否仍发送
- radio/default promo 行为
- choose 前的业务 warmup XHR 顺序、CSRF header 与响应 cookie 旋转
- Referer / Origin / Accept / Client Hints
- 二次 XHR（如 availability layer）是否依赖 choose 页 CSRF

业务 403 时的诊断顺序：

1. **出口信誉**（同一代理节点下浏览器能否打开业务 document 路由）
2. TLS/UA/Client-Hints admission（同出口 curl 根页/route 是否 200；profile 是否过时）
   - 先记录 `curl_cffi.__version__` 并枚举实际 `BrowserType`；升级到允许的最新版本后测试最新 profile，再判断出口。
   - 当浏览器业务成功而 Python 业务 POST 403 时，先把浏览器成功包的原始 `headers + Cookie + body` 用不同 `curl_cffi` profile 原样回放。
   - 若同一成功包在 Chrome profiles 403、但 Edge/Safari/Firefox profile 200，则根因是 transport-profile admission，不是 CSRF、form、cookie 或 sensor body。
   - 这种情况下优先切可用 `CURL_PROFILE`，保留可工作的 UA/Client-Hints 表面；不要为追求浏览器 major 一致而先重写 Akamai 或业务表单。
3. sensor/SBSD 阶段数、body size 序列与 `_abck` / `bm_s` / `bm_sc` / `sbsd_c` / `ak_bmsc` 是否旋转；pixel 是否发出
4. choose 前业务 warmup 是否与**当前**浏览器成功包一致；中间 XHR 403 先修 header/CSRF/route-local cookies
5. form/API 字段是否与**当前**浏览器成功包一致（空字段、默认促销码、数组重复字段都要保留）
6. CSRF 提取是否覆盖 `meta` + `input`，且区分 main 页 CSRF 与 choose 页 CSRF
7. 才回头加深环境补丁 / SBSD 软挑战

body 体型快速分类：

- ~400–550B + `Access Denied` → 硬门（出口/会话）
- ~4KB + Privacy / `sec-if-cpt-container` / `sec_sbsd_chlge_form` → SBSD 软挑战，**不是业务成功**
- 业务 document 约 MB 级、后续 XHR 含业务数据 → 真成功

### 9. Prove repeatability

完成标准：

- 完整 collector + 业务链至少两次独立 fresh session 成功
- 实际发出的 sensor POST 体型与 cookie transition 接近实时样本；未触发的观测分支必须记录，且只能由重复业务成功证明对当前路径非门禁
- 业务 API/表单返回预期 envelope 并解析出结构化数据
- 每次 runner 使用唯一 artifact 路径；成功输出单独保存，失败诊断不覆盖成功结果

## Public Project Rule

开源 Akamai 项目只作为事实来源，不作为可用性证明：

- 1.7/1.75 generator 默认视为 legacy
- 没有 license 的仓库不得复制代码
- README 的“支持 v3”必须由 live replay 验证

读取 `references/public-project-triage.md`。

## Output Contract

最终报告必须包含：

- Akamai 证据与 cookie 族（`_abck` 系或 `bm_*` 系）
- recon 浏览器路径（Edge / Chrome / Camoufox）
- collector 与 Pixel 职责
- sensor/SBSD POST 次数、body size 序列、cookie transition
- TLS/UA/Client-Hints profile 与 curl_cffi 可用 profile 差距
- 本机指纹缓存来源
- 业务 endpoint、method、序列化与成功解析结果
- 若触发 SBSD/CPR：script URL 形态、`v`/`t` 处理、payload 字段、动态 key 语义模板、key115/VMP 还原证据、`bm_s`/`bm_sc`/`sbsd_c` 通过态与业务 replay
- 若触发 crypto challenge：动态 verifier 来源、逐项 proof 规则、轮数/节奏、最终 verifier、`sec_cpt` 1 -> 2 -> 3 与业务 replay
- 若触发直接三阶段 `sensor_data`：当前 JS/collector URL、三个 stage 的 body size 与字段差分、`din` 顺序、mouse lifecycle、`sww`/SharedWorker 来源、`bm_sz`/`previousValue`/`ver` provenance、加密 framing、cookie transition 与业务 replay
- 纯 Python 或 Python + IV8 边界
- 输出路径与仍不稳定的 transport/IP / egress 风险
- 若失败可被“换节点”复现为成功，必须写明 **egress-gated**，避免误报实现回归

使用 `references/report-template.md`。

## References

- `references/workflow.md`: 最短端到端执行图
- `references/cookie-state-machine.md`: cookie provenance 与阶段模型
- `references/transport-coherence.md`: TLS/UA/H2/代理一致性
- `references/iv8-live-collector.md`: 本地运行实时 collector 的实现约束
- `references/crypto-challenge.md`: `sec_cpt` verifier 状态机、动态多 proof PoW 与完成判据
- `references/sbsd-body-vmp.md`: SBSD/CPR `{"body":...}`、`v`/`t`、115-key signals、key115/VMP 与 `bm_sc`/`sbsd_c` 通过态
- `references/case-twayair-iv8.md`: 德威/T'way 多阶段 sensor 实战案例
- `references/case-vueling-sbsd.md`: Vueling profile 代际、CPR 动态 URL 与可选 sensor 分支案例
- NV8 secondary 的通用装配、离线回放和 Node 版本门见 `nv8-node-runtime`；只有在本 skill 已固定 Akamai sensor acceptance 后才委派，不从 NV8 反向推断 Akamai 家族
- `references/public-project-triage.md`: 开源项目评估规则
- `references/report-template.md`: 阶段报告和最终交付格式
- `references/wechat-akamai-sensor-data.md`: 直接三阶段 `sensor_data` 文章证据、字段差分和 Python 回放校正
