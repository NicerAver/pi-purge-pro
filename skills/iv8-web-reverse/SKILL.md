---
name: iv8-web-reverse
description: >-
  用户明确说“用 iv8 补环境”“Python + iv8 执行 JS”或要求 Python + iv8 + requests/curl_cffi 回放时，直接优先读取并使用本 skill；此类后端选择使 iv8-web-reverse 成为 primary，不先进入 trace、Node/VM、AST 或浏览器取证。也用于 Trace 已固定入口并明确委派 iv8 的复杂浏览器语义补环境，以及已确认 Imperva/Incapsula Reese84 动态 challenge/Cookie/业务回放。覆盖 lifecycle/timer、XHR/fetch replay、Worker/iframe、canvas/WebGL/layout、native descriptor 和多阶段 bootstrap；也覆盖已确认的 Aliyun WAF HTML challenge、闭包内 `Lf/LK/Lb`、长 `md5__1803` URL 签名和 `requests + iv8` browser-free 回放。入口未固定、只取证/定位或未知多层链路转 trace；完整 CAPTCHA/TDC challenge 到 verify/post-verify 仍由 captcha-reverse 主责，Akamai 端到端链路转 akamai-protocol-reverse。普通 cookie、403、sign、Reese84 名称、已保存 WMPF 证据后的纯 browser-free Python collector，或简单 Node 补环境不能单独触发本 skill；WMPF collector 只有明确 iv8 或复杂浏览器语义委派时才进入本 skill。
argument-hint: "[目标 URL 或站点名]"
compatibility: "需要 Python 3、iv8、requests；按目标可选 curl_cffi"
---

# iv8 Web Reverse

## 唯一职责

把已经选定的 iv8 执行路线，或 Trace 根据复杂度门委派的浏览器语义执行路线，交付成可运行的 Python 请求脚本；对已确认 Reese84，使用内置协议 profile 交付完整无浏览器 collector。本 skill 不从普通 403 或未知 sign 猜测协议家族，也不负责定位普通签名入口。

## 直接路由

用户明确说“用 iv8 补环境”“用 Python + iv8 跑 JS”或同义表达时，本 skill 是 runtime task 的 primary。先读取本 skill 并选择 profile，再决定是否需要 Trace handoff；不要先进入 Trace env-patch、Node/VM、AST 或浏览器取证。只有完整 CAPTCHA/TDC、确认的 Akamai 协议恢复，或用户实际只要入口/观察证据时，才由对应 specialist 或 Trace 保持 primary。

共享阶段和 handoff 契约见 `../_shared/js-reverse-workflow.md`；本 skill 主要承担 `Port`。若用户明确要求“只输出阶段门”，按其中的 Stage-Gate Output 返回 `MODE`、`OWNER`、`NEXT_GATE`、`REQUIRED_EVIDENCE` 和 `DO_NOT_USE`，不要开始取证或实现。`skill_checkpoint` 字段规则见同文件 Checkpoint Fields。

微信小程序 / WMPF / AppService / WebView runtime 证据由 `wechat-miniapp-reverse` 拥有。本 skill 只消费它已保存的请求、源码、固定输入输出和 `handoff.json`，不调用 `miniapp-reverse-mcp` 的 request/script/frame/target ID；缺证据时按同一 `task_id` 退回该 skill 再取一轮，不自己去连 62000 或改用浏览器家族。

## 准入条件

至少满足一项：

1. 用户明确要求“用 iv8 补环境”、Python + iv8，或 Python + iv8 + requests/curl_cffi。
2. 上游已经提供入口、真实输入输出和运行素材，并指定 iv8 执行。
3. 用户要求适配本 skill 的 bundled case。
4. 用户明确要求把已验证成果回写为 iv8 案例。
5. 已有明确 Reese84/re84 证据，或至少两类相关 GPC、solution envelope、token/cookieDomain 和 Imperva 资源证据，并要求动态 Cookie 与业务回放。
6. Trace 已固定入口、真实输入输出和 baseline，并按复杂度门确认存在任一硬信号，或至少两个普通宿主信号，委派本 skill 作为 local runtime backend。

复杂度硬信号包括生命周期/定时器、XHR/fetch replay、Worker/iframe、canvas/WebGL/layout/style、native descriptor/`Function.prototype.toString` 和多阶段 bootstrap。普通信号包括 cookie+storage、多个 DOM 对象族、动态资源、事件监听和 navigator/screen 指纹读取。满足第 6 条时直接使用 iv8，不要求先做 Node.js 失败实验；若用户明确指定 iv8，本 skill 是 runtime task 的 primary，Trace 只提供已经存在的入口、证据和 handoff；只有用户未指定后端时，Trace 才保留协议 coordinator 身份，本 skill 作为执行 backend。

普通 403/412、未知 sign、入口未固定或只想找函数位置不满足准入条件。简单同步入口、固定输入且最多一个窄宿主补丁仍交给 Trace env-patch；完整多层协议恢复交给 `trace`。

协议专项仍优先：确认 Reese84 后进入本 skill 的 Reese84 profile；确认 Akamai `_abck`/`sensor_data` 端到端链路后转 `akamai-protocol-reverse`；完整 CAPTCHA 的 challenge、图像/轨迹和 verify 状态机由 `captcha-reverse` primary，本 skill 只在用户明确指定时提供 iv8 可信输入或运行后端。

## Profile 路由

已确认 Reese84 时先读 `references/profiles/reese84/index.md`。该 profile 拥有 challenge 状态机、GPC/solution POST、token/Cookie domain、UTMVC、环境与 TLS 一致性、业务放行和进程隔离；若 GPC 前有独立 Cloudflare precursor 证据，再读 `references/profiles/reese84/edge-admission.md`。通用流程只提供 iv8/HTTP 基础，不得用普通 cookie challenge 捷径替代 profile 验证门。只有完整 Managed Challenge 或外层状态机仍未知时才由 `trace` primary 固定入口，admission 明确后返回 Reese profile 完成 collector。

## 硬约束

1. 动态 JS、HTML、环境快照和运行报告写入当前项目 `js_reverse_cache/`，不写入 skill 目录。
2. 首跳、动态 JS、Cookie、签名、时间戳和业务请求保持在同一个 Python Session 和同一 baseline 链路。
3. 每次请求相关的签名、URL 后缀和时间字段必须在请求循环内重建。
4. 通用任务默认交付一个短主 `.py`，以及按需使用的 `utils/iv8_silent.py` 和 `utils/logger.py`；Reese84 按 profile 的 collector/tests 结构交付。两者都不扩成无关框架或 CLI。
5. 没有用户明确要求时，不回写 `references/cases/`。
6. 用户提供的 Cookie、Authorization、token、API key、私密 key/iv、session secret 等不得默认放入 PyCharm/OS 环境变量，也不得写入源码、skill、案例、报告或日志。
7. 交付脚本在顶部保留可编辑空常量，例如 `COOKIE_HEADER = ""`、`AUTHORIZATION = ""`、`PRIVATE_KEY = ""`；必填值为空时给出清晰的本地提示。动态 Cookie、token、sign、时间戳和 challenge 值必须在同一 Session/runtime 链中生成或刷新。

🔴 CHECKPOINT：写脚本前声明入口来源、唯一 baseline、动态材料目录、是否真实请求和是否回写案例。来源冲突时先停。

## Maintenance Check

修改 iv8 准入、Reese84 边界、handoff 或 eval 后运行 `python scripts/validate_skill.py <skill-root>`，再运行通用 `quick_validate.py`。

## 选择参考

已确认 Reese84 直接读取 profile；其它任务先读 `references/example-taxonomy.md` 选择最近案例，再只打开相关文件：

对于“首跳返回 Aliyun WAF HTML、最终 POST URL 带长 `md5__1803`、签名入口位于闭包内”的目标，先读：

- `references/reverse-process/js-challenges/cdfsunrise-md5-1803-reverse-process.md`
- `references/cases/js-challenges/cdfsunrise-md5-1803.py`

该案例强调：先区分业务短签名与 WAF 长签名；通过 AST 固定 `Lf -> LK -> Lb`；不要直接包装原始函数；用 `__iv8__.page.load` 承接 fresh challenge；保留 `Function.prototype.toString` 原始源码结果；最后只将已验证需要的 Cookie 回写同一 `requests.Session`。

| 类型 | 目录 |
|---|---|
| 业务签名 header | `references/cases/signatures/` |
| Qunar/Piccolo: `QN668` + inline `_pt_` + native Bella | `references/reverse-process/signatures/qunar-flight-bella-reverse-process.md` |
| Challenge Cookie | `references/cases/js-challenges/` |
| 浏览器 Token | `references/cases/browser-tokens/` |
| XHR/fetch 改写 URL | `references/cases/network-hook-signing/` |
| 已明确采用 iv8 的可信输入/TDC backend | `references/cases/captcha/` |
| Reese84 动态 Cookie collector | `references/profiles/reese84/` |

API 用法查 `references/api-inventory.md` 和 `references/api-examples/`；脚本结构查 `references/script-writing-rules.md`；不要盲目复制整站案例。

## 生成流程

### 1. 固定输入契约

确认页面/API URL、method、params/body、headers、Cookie、入口函数或页面生命周期、预期输出和 Session 更新顺序。Reese84 按 profile 启动门固定协议证据和业务成功判据；其它任务缺入口时，返回 `trace` Observe/Capture 取证。

### 2. 保存运行素材

用同一 Session 获取 HTML、外链 JS、seed/challenge 和 Cookie，原样保存到 `js_reverse_cache/<target>/`，记录 URL 和时间。不要混用旧缓存与新 Session。

### 3. 构造最小 iv8 环境

1. 选择最接近的 `environment` 和 timezone/config。
2. 生命周期、外链脚本、timer、XHR 或 promise 重要时使用 `page.load` 与 event loop。
3. 只补目标实际读取的最小 patch；优先使用 `wrapNative` 保持函数外形。
4. 调用已知入口，或在 iv8 中触发目标 XHR/fetch 后从 `netLog` 读取 wire URL、headers、cookieHeader 和 body。

### 4. Python 请求回放

把 iv8 输出合并回同一 Session。默认 `requests`；只有证据显示 TLS/HTTP2 admission 参与校验时才改用 `curl_cffi.requests`，并保持 UA/Client Hints 一致。

### 5. 验证

1. `python -m py_compile` 验证主脚本和实际存在的 utils。
2. 固定输入验证 iv8 输出的结构、长度和关键字段；若不一致，记录第一处差异，不用长度或非空值替代 parity。
3. 条件允许时真实请求，检查状态码、业务码、字段完整性、响应类型和下一轮状态；中间 challenge/verify 200 不等于业务成功。
4. 至少重复一次新鲜生成；一次成功不算稳定。
5. 连续调用同一 helper 前做 persistent-world、fresh-world、explicit-state 三项 continuity 对照；若 helper 自失效，不把同一实例用于分页或长期采集。

🔴 CHECKPOINT：真实请求前列出 Session Cookie 来源、动态 JS 来源、签名重建时机和预期状态码。若有来源来自过期样本，标记证据陈旧并优先刷新或确认；仍可按用户要求发请求，但不能把该请求直接当作当前验收证据。

## Aliyun WAF Closure-Signer Profile

当目标符合以下组合时，按 `cdfsunrise-md5-1803` 案例处理，不要把它当作普通 header sign：

- 首跳返回 HTML challenge，而不是业务 JSON；
- challenge 页面初始化 WAF 状态，例如 `_waf_bd8ce2ce37`；
- 最终 POST URL 增加长 `md5__1803`；
- WAF 入口函数不在 `window`，而在内联闭包中；
- 直接 wrapper/export 会触发源码自校验或同步卡死。

执行顺序：

1. 用同一 `requests.Session` 获取 fresh challenge 和 `acw_tc`。
2. 保存当前项目的 HTML/JS 证据，不把动态 Cookie、签名 URL 或完整响应写入 skill 案例。
3. 用 AST 提取 `Lf/LK/L3` 及直接依赖，确认真实参数顺序。
4. 在 iv8 中用 `page.load` 恢复同源 DOM、location、navigator、screen 和脚本节点形状。
5. 先执行初始化脚本和外链 runtime，再执行内联 bundle。
6. 如果必须导出闭包引用，最小化注入，并让 `Function.prototype.toString` 对被检查的外层函数返回原始源码；不要关闭自校验。
7. 调用已确认的 `LK(url, body, method, 2)`，要求返回非空完整 URL。
8. 只回写已验证需要的 Cookie；不要因为 Cookie 名称包含 `waf` 就把所有 iv8 Cookie 转给 requests。
9. 用同一 Session 回放原始 body 字节和 headers。
10. 最终必须同时满足 JSON content type、业务 `isSuccess` 和业务 `code`。

该 profile 的“纯协议”含义是 browser-free `requests + iv8`。如果用户进一步要求完全不执行原始 WAF JS 的纯 Python 算法移植，应明确切换为纯算子任务，并重新验证 `L3`、伪随机、编码和 challenge 状态映射，不要把 iv8 runtime 复现误称为纯算。

## 浏览器环境桥接

仅在目标有环境分支、iv8 复现出现环境差异，或用户提供浏览器样本时启用：

1. 读取 `references/browser-iv8-bridge.md`。
2. 选择一个 `BROWSER_BASELINE`，保存原始快照到 `js_reverse_cache/browser_env_raw.json`。
3. 生成 `browser_env.json` 时只承接 iv8 能表达的 environment、config、headers、cookies、storage 和 patches。
4. 其它来源只作诊断对照，不混拼 UA、Cookie、screen、storage 或 TLS。
5. 明确 iv8 不能完整继承真实渲染、字体栈、进程级指纹、TLS 和全部事件模型。

被普通浏览器风控阻断且必须取得可信基线时，返回 `trace` Observe/Capture；需要反检测或指纹基线时使用 Camoufox MCP 采证后交回本 skill。

🔴 CHECKPOINT：生成 `browser_env.json` 前展示 baseline、原始快照、承接字段和排除字段。

## 输出规则

- 顶部放可编辑常量，如 PAGE/API URL、UA、分页和关键词；用户凭证使用空的 `COOKIE_HEADER`、`AUTHORIZATION` 或私密 key 常量，不使用 PyCharm 环境变量作为默认输入。
- 只有 helper 能减少真实重复时，主脚本才通过 `utils.iv8_silent` 导入 iv8、通过 `utils.logger` 输出；清晰的单文件实现可以直接导入并使用轻量日志。
- 业务流程附近只写必要中文注释。
- 打印真实状态码和响应；不把成功等同于 HTTP 200。
- 任务现场值默认留在私有工作区，不复制到公共案例；用户提供的 Cookie、Authorization、token、私密 key/iv 和 session secret 不写入代码、日志或报告。
- 避免大型 wrapper、无用类和预置全部 API 的通用框架。

## 案例回写

只在用户明确要求时执行：

1. 先完成普通脚本、编译和运行验证。
2. 读取 `references/case-ingestion-rules.md`。
3. 列出新增案例、必要 frozen 素材、taxonomy 修改和脱敏策略。
4. 只复制最小可复用素材，不把整份缓存、运行日志或一次性响应入库。Qunar/Piccolo 类案例优先回写实时发现和 iv8 生命周期步骤；除非页面契约明确稳定，不把会过期的 qlog、HTML、Cookie 或完整响应作为 frozen 资产。

🔴 CHECKPOINT：未收到明确回写要求时，只交付当前项目脚本和缓存。

## Failure Modes

| 触发条件 | 处理动作 | 兜底 |
|---|---|---|
| 入口或目标类型不明确 | 停止写脚本 | 返回 `trace` Observe/Capture |
| baseline 来源冲突 | 只保留一个来源 | 其它样本标为诊断对照 |
| iv8 生成失败 | 保存最小 HTML/JS/runtime 和错误 | 若任务需要真实请求，改用当前可用的 requests/curl_cffi/浏览器能力；不要声称 iv8 已生成有效值 |
| 编译失败 | 只修语法、导入和路径 | 不进入网络验证 |
| 请求状态或业务字段异常 | 保存生成值、请求和响应 | 查 Session、时间、序列化和 TLS |
| 用户未要求案例回写 | 保持任务资产在工作区 | 不修改 skill 案例库 |
| Reese84 证据不足或只是通用 Imperva | 停止 profile collector | 返回 `trace` Observe/Capture 固定入口和协议证据 |
| Reese GPC 被 `cf-mitigated: challenge` 拦截 | 不把它归因于 Canvas/solution | 有 precursor 证据则先解 edge admission；完整 Managed Challenge 转 `trace` |
| Reese token 返回但业务仍被拦截 | 不把 token 200 当成功 | 按 Reese profile 做单 baseline 跨层诊断 |

## 完成报告

报告主脚本和实际生成的 utils 路径（如有）、采用的案例、baseline、缓存位置、iv8 输出验证、真实请求结果、分页/刷新状态和仍无法由 iv8 承接的环境差异。
