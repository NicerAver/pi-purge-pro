---
name: nv8-node-runtime
description: >-
  用户明确说“用 NV8”“NV8 补环境”“Node + NV8 跑目标 JS”“用 NV8 采集/分页/签名服务”，
  或要求把已恢复的签名落成 Node 常驻采集管线时，直接优先读取并使用本 skill；此类选择使
  nv8-node-runtime 成为 runtime task 的 primary。NV8 是零依赖、进程隔离的 Node 原生 Edge
  运行时模拟（EdgeSandbox / createNv8 / createAgentSession / Protocol / Collector），
  默认离线回放、不出网。覆盖 EdgeSandbox 装配、evaluate 结果信封、离线 replay、
  networkRequests 取签名产物、enableTrace/watchApis 定位入口、冻结指纹 profile 切换、
  Agent Session 声明式 EnvironmentPatch、Artifact→RequestPlan→Collector 三层采集链路、
  分页/限流/熔断/断点续采/去重落库。需要真实浏览器渲染、点击、截图、CDP 网络与断点证据时
  用 js-reverse Edge MCP；用户明确要 Python + iv8 时用 iv8-web-reverse；入口未定位、
  只取证或需要 AST 还原时先用 trace。完整 CAPTCHA/TDC challenge 到 verify 仍归
  captcha-reverse，Akamai 状态机仍归 akamai-protocol-reverse；Akamai 可明确委派 NV8
  生成一个离线传感器/签名 artifact，但 Python 负责最终 HTTP，不能把 NV8 Collector 当作
  Akamai 的最终交付或绕过其独立验收。
argument-hint: "[目标 URL 或站点名] [要恢复的签名字段]"
compatibility: "Node >= 18.18.0（指纹敏感场景必须 Node 22+，Window 枚举序需 Node 24 才与 Chromium 逐位一致）；NV8 零依赖，不需要安装 Edge/Chrome/Chromium"
---

# NV8 Node Runtime

## 唯一职责

用 NV8 在 Node 里重建一个与真实 Edge 无法区分的执行环境，原样运行目标站点的原始脚本，
从中恢复签名、令牌与协议行为；再把恢复出的协议接入 NV8 自带的采集调度层，交付可长期
运行的采集管线。本 skill 不负责入口定位与纯取证，也不从普通 403 猜测协议家族。

## 直接路由

用户明确说“用 NV8”“用 Node 跑这段目标 JS”“NV8 补环境”“NV8 采集”或同义表达时，
本 skill 是 runtime task 的 primary。先读取本 skill 并选定装配路径（`EdgeSandbox` /
`createNv8` / `createAgentSession`），不要先进入 Trace env-patch、通用 Node/VM 或浏览器取证。
若上游是 Akamai specialist，NV8 只作为 secondary artifact backend：确认已授权的输入/出口、
固定 sensor 入口和 acceptance test 后再运行；不接管 Akamai family routing，不把真实 HTTP 放进
Node runtime，也不替代 Python-owned business replay。

三条运行时后端的边界必须分清，不要混用：

| 后端 | 形态 | 何时选 |
|---|---|---|
| **nv8-node-runtime**（本 skill） | Node 进程内重建 Edge 表面，子进程隔离，零依赖 | 用户点名 NV8；要恢复签名并长期采集；要离线确定性回放 |
| `iv8-web-reverse` | Python + iv8 驱动 JS，交付 `.py` | 用户点名 iv8；交付物是 Python 请求脚本 |
| `js-reverse` Edge MCP | 真实 Edge 浏览器 + CDP | 需要真实渲染/点击/截图/CDP 网络与断点证据 |
| `akamai-protocol-reverse` + NV8 | Akamai specialist 保持状态机；NV8 仅返回窄 sensor artifact | 已确认 Akamai family、已固定入口和用户明确选择 NV8 secondary backend |

**NV8 不做浏览器自动化。** 它不点击、不截图、不等元素、没有排版引擎，`offsetWidth` /
`getBoundingClientRect` 只是近似模型。需要真实渲染或真实 CDP 证据时，用 js-reverse Edge MCP
取证，再把固定素材交回本 skill 做离线确定性复现。这与 `_shared/js-reverse-workflow.md` 里
“Explicit Edge MCP directives select the js-reverse Edge browser family” 不冲突：那条规则
选的是**浏览器证据家族**，本 skill 选的是**Node 执行运行时**。

共享阶段和 handoff 契约见 `../_shared/js-reverse-workflow.md`；本 skill 主要承担
`Rebuild` / `Patch` / `Consolidate` / `Port`。若用户明确要求“只输出阶段门”，按其中的
Stage-Gate Output 返回 `MODE`、`OWNER`、`NEXT_GATE`、`REQUIRED_EVIDENCE` 和 `DO_NOT_USE`，
不要开始取证或实现。`skill_checkpoint` 字段规则见同文件 Checkpoint Fields。

微信小程序 / WMPF / AppService / WebView runtime 证据由 `wechat-miniapp-reverse` 拥有。
本 skill 只消费它已保存的请求、源码、固定输入输出和 `handoff.json`，不调用
`miniapp-reverse-mcp` 的 request/script/frame/target ID；缺证据时按同一 `task_id` 退回该
skill 再取一轮，不自己去连 62000 或改用浏览器家族。

## 准入条件

至少满足一项：

1. 用户明确要求使用 NV8，或明确要求用 Node 运行目标站点脚本。
2. 上游已提供入口、真实输入输出和运行素材，并要求交付 Node 侧可复现执行。
3. 用户要求把已恢复的协议落成可持续运行的采集管线（分页、限流、断点续采、去重落库）。
4. 用户要求在本机复现浏览器指纹读取结果，或需要离线、确定性的回放环境。
5. 需要 `Agent Session` 的声明式 `EnvironmentPatch` 做受控、可回滚、有审计的环境试探。

不满足准入的典型情况：只想找函数位置或拿 hook（转 `trace` Observe/Capture）；需要真实
浏览器渲染证据（转 js-reverse Edge MCP）；明确要 Python 交付（转 `iv8-web-reverse`）；
完整验证码挑战链（转 `captcha-reverse`）。

## 硬约束

1. **Node 版本是硬门。** 指纹敏感场景必须 **Node 22+**；要让
   `Object.getOwnPropertyNames(window)` 的枚举序与 Chromium 逐位一致必须 **Node 24**。
   Node 18/20 的 V8 < 12 把可枚举键排在不可枚举键之前，`npm run capabilities` 会报
   `vm.global-property-order  broken`。不要在这两档上声称指纹对齐。
2. **首次 `EdgeSandbox.create()` 实测约 20 秒**（子进程启动 + 页面装配）。默认
   `limits.timeoutMs` 是 5000，**初次装配必然超时**。宿主脚本必须显式放大，
   例如 `limits: { timeoutMs: 60_000 }`。长任务按实际预算继续放大。
3. **`evaluate()` 返回结果信封，不是裸值。** 一律读 `.value`：
   `(await sandbox.evaluate('navigator.userAgent')).value`。忘记解包会拿到
   `{type, value, byteLength}` 对象，是最高频的低级错误。
4. **运行时默认不联网。** 目标脚本里的 `fetch`/XHR/WebSocket 走离线回放，未命中即
   `TypeError: Offline replay miss ...`，**绝不回落真实网络**。需要联网时只能走
   Collector 层并显式配置 `policy.allowedOrigins`。
5. **不要直接 `node target-bundle.js`。** 宿主负责读文件，源码交给 `evaluate()` 或
   `evaluateModule()`；沙箱内 `process`/`require`/`Buffer` 均为 `undefined`。
6. **动态 JS、fixture、环境快照和运行报告写入当前项目 `js_reverse_cache/`**，不写入
   skill 目录，也不写入 NV8 仓库目录。
7. 用户提供的 Cookie、Authorization、token、API key、私密 key/iv、session secret 不得
   写入源码、skill、案例、报告或日志；Collector 凭据通过 origin-bound 配置注入，
   脚本顶部保留可编辑空常量并在为空时给出清晰本地提示。动态 cookie/token/sign 必须在
   同一 Session/runtime 链中生成或刷新。

🔴 CHECKPOINT：写脚本前声明目标 URL、是否已有固定输入输出、选定的装配路径、Node 版本、
是否真实出网和是否回写案例。来源冲突时先停。

## 装配路径选择

| 路径 | 用途 | 安全边界 |
|---|---|---|
| `EdgeSandbox.create()` | **协议恢复首选**。跑不可信目标脚本，完整 Edge 表面 | 独立子进程 |
| `createNv8()` | 按插件/Profile 裁剪装配，进程内 | **无** child-process 边界，仅可信代码 |
| `createAgentSession()` | 受控环境试探与 `compareEnvironment` 验证 | 复用 Sandbox 边界 + 补丁白名单 |
| `nv8Eval()` | 一次性无状态求值 | 同 `createNv8` |

不可信目标代码一律走 `EdgeSandbox`；`createNv8` 只用于可信插件开发、表面验证或结构实验。

## 生成流程

### 1. 固定输入契约

确认目标 URL、method、params/body、headers、入口函数或页面生命周期、预期输出和
Session 更新顺序。缺入口时返回 `trace` Observe/Capture 取证，不要盲猜。

### 2. 保存运行素材

用同一 Session 获取 HTML、外链 JS、seed/challenge 和 Cookie，原样保存到
`js_reverse_cache/<target>/` 并记录 URL 与时间。不要混用旧缓存与新 Session。

### 3. 装配 Sandbox 并跑通入口

1. 选最接近的指纹 profile（默认 Edge 150；可选 151 / 152）。
2. 页面字段传完整对象，不依赖上一页继承。
3. `limits.timeoutMs` 放大到 60000 起。
4. 用 `evaluate()` 读回目标实际读取的环境值，先确认环境对不对，再谈签名。
5. 调用已知入口，或触发目标 XHR/fetch 后从 `networkRequests()` 读 wire URL、headers
   与 body —— 这是协议恢复的主要产出。

### 4. 定位签名入口

`enableTrace()` 后再跑一轮，用 `trace()` 读属性访问与函数调用；需要断点时
`watchApis(list)` + `openInspector()`（仅 child-process 后端支持暂停）。
Trace 只观察兼容层 API 调用，不代表真实 Chromium 调用栈；需要真实调用栈时回
js-reverse Edge MCP 取证。

### 5. 接入 Protocol 与 Collector

按 `references/protocol-pipeline.md` 把签名产物做成 `RuntimeArtifact`，用声明式
`ProtocolAdapter` 产出 `RequestPlan`，最后交给 Collector 执行。真实网络只在 Collector 层，
且必须先过 `NetworkPolicy` allowlist。

### 6. 验证

1. 固定输入验证输出结构、长度和关键字段；不一致时记录第一处环境/变换差异，不用结果信封或非空输出代替 parity。
2. 至少重复一次新鲜生成；一次成功不算稳定。
3. 出网时检查状态码、业务码、字段完整性、目标业务 schema 和下一轮状态；bootstrap、challenge 或 verifier 200 不是业务通过。
4. 同一签名/采集 helper 先做 persistent-world、fresh-world、explicit-state continuity 对照；自失效实例不能承担分页。
5. 采集管线验证分页终止条件、去重主键和断点续采恢复，并把 Artifact、RequestPlan、Collector 三层的失败分别记录。

🔴 CHECKPOINT：真实请求前列出 Cookie 来源、动态 JS 来源、签名重建时机和预期状态码。
若证据来自过期样本，标记陈旧并优先刷新；仍可按用户要求发请求，但不能把该请求直接
当作当前验收证据。

## 选择参考

| 需求 | 读取 |
|---|---|
| API 字段、结果信封、方法清单 | `references/api-reference.md` |
| 跑法、坑、超时、指纹、调试 | `references/user-guide.md` |
| Artifact→Protocol→Collector 三层 | `references/protocol-pipeline.md` |
| Agent Session 补丁与验证 | `references/api-reference.md` 的 Agent Session 节 |
| 可运行骨架 | `scripts/nv8_runner_template.mjs` |

NV8 自带站点手册（阿里云 V2、Cloudflare Turnstile、抖音 bdms、小红书 x-s、Akamai 等）在
NV8 仓库 `docs/target-playbooks/`，命中同类目标时先读对应手册再动手。

## Maintenance Check

修改准入、路由边界、装配路径或 eval 后，运行
`python scripts/validate_skill.py <skill-root>` 校验结构和引用路径。
