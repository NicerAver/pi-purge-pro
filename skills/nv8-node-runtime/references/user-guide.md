# NV8 运行手册（协议恢复实操）

本文件是实操手册：怎么跑、什么会炸、怎么验证。API 字段查 `api-reference.md`。

## 运行前提

```powershell
node --version          # 指纹敏感场景必须 >= 22；枚举序逐位一致需 24
cd <nv8-root>; npm install --ignore-scripts   # 零依赖，实际不装任何包
```

**NV8 运行不需要安装 Edge、Chrome 或 Chromium。** Windows/macOS/Linux 都用 Node 自带的
V8 与仓库内冻结 Profile。"EdgeSandbox" 是模拟环境的名称，不是真实 Edge 进程。
只有主动重采 Edge 基线（`fingerprint:*` 系列命令）时才需要真实 Edge —— 没有 Edge 的机器
直接用仓库已有基线，**不要执行这些采集命令**。

### `--experimental-vm-modules` 什么时候要加

| 场景 | 是否需要 |
|---|---|
| 宿主脚本只用 `EdgeSandbox` | **不需要**。隔离后端（child-process / worker-thread）由控制器自动带上 |
| 直接用 `createNv8`（进程内） | **需要** |
| 跑仓库测试、构建脚本、示例 | **需要** |

```bash
node --experimental-vm-modules examples/basic-eval.mjs
node --experimental-vm-modules --test tests/node-compat-test.js
```

不要用缺少该 flag 的直接 Node 命令去诊断运行时兼容性 —— 那会把 flag 缺失误判成 NV8 问题。

### Node 版本陷阱（会被能力探针抓到）

```bash
npm run capabilities
```

Node 18/20 会报：

```
- vm.global-property-order  broken  global keys are not in insertion order …
```

原因：V8 < 12 在 dictionary 模式的 global object 上把**可枚举键排在不可枚举键之前**，
违反 `[[OwnPropertyKeys]]`。实测真实 Edge 里 `window` 落在索引 **678**，Node 18/20 上
落到索引 **0**，其后 238 个全局全部错位。`enumerable` 本身是要复现的契约值，不能为了
顺序去改，所以这是宿主限制而非可绕过的实现问题。V8 12.x（Node 22）已修正该行为；
Node 24 与 Chromium 逐位一致。

**指纹敏感目标必须 Node 22+，追求枚举序完全一致必须 Node 24。**

## 第一次运行

```js
import { EdgeSandbox } from 'nv8';

const sandbox = await EdgeSandbox.create({
  page: { url: 'https://sandbox.test/', html: '<!doctype html><main id="app">Ready</main>' },
  limits: { timeoutMs: 60_000 },        // ← 必须放大，见下
});

try {
  console.log((await sandbox.evaluate('navigator.userAgent')).value);
  console.log((await sandbox.evaluate('document.getElementById("app").textContent')).value);
  console.log((await sandbox.evaluate('Function.prototype.toString.call(document.addEventListener)')).value);
} finally {
  await sandbox.close();
}
```

### ⚠️ 超时：默认 5000ms 不够首次装配

**实测数据**：`EdgeSandbox.create()` 在 Node 24 / Windows 上首次耗时 **约 20.5 秒**
（子进程启动 + 完整 Edge 表面装配）；装配完成后的单次 `evaluate` 是 **0–3ms**
（`getComputedStyle` 首次约 1s，之后走缓存）。

用默认 `limits.timeoutMs: 5000` 会直接得到：

```
SandboxTimeoutError: Sandbox evaluation exceeded the 5000ms wall-clock timeout
    at connection-base.js:53
code: 'ERR_EDGE_SANDBOX_TIMEOUT'
```

**对策**：宿主脚本显式设 `limits: { timeoutMs: 60_000 }` 起步；长任务按实际预算继续放大。
诊断脚本不要一上来就把创建和全部探针塞进一次运行 —— 先确认 `create()` 能过，再加探针。

`timeoutMs` 同时约束同步执行与返回值异步等待，默认 5000，取值 1–300000。
用户代码超时后控制器会终止当前执行单元，并为后续请求启动**干净的执行单元**：
不要依赖超时后的全局变量、DOM 对象、Promise 或 Worker 继续存在。

## 离线网络回放

运行时**默认不联网**。目标脚本里的 `fetch` / XHR / WebSocket / EventSource 全部走离线回放；
未命中就在本地失败，**绝不回落真实网络**。

实测未配置 replay 时：

```js
await sandbox.evaluate(`fetch('https://example.com/api')`);
// TypeError: Offline replay miss for fetch GET https://example.com/api: missing
```

注意：即使 miss，请求仍会进入 `networkRequests()` 记录 —— 实测计数为 1。所以
`networkRequests()` 既能拿**成功回放的 wire 产物**，也能暴露**脚本尝试发起的请求清单**，
后者正是协议恢复要看的“脚本到底想请求什么”。

配置一条 replay：

```js
const sandbox = await EdgeSandbox.create({
  page: { url: 'https://target.test/' },
  limits: { timeoutMs: 60_000 },
  replay: [
    {
      request: { method: 'GET', url: 'https://target.test/api/seed' },
      response: { status: 200, headers: { 'content-type': 'application/json' }, body: '{"k":"v"}' },
    },
  ],
});
```

- 重复 replay 记录会让 `create()` 拒绝，不被静默忽略。
- Worker 脚本 replay 也走同一机制。
- 显式启用的 `networkRelay` 外部中继是唯一例外（见 NV8 `docs/user-guide.md` 8.6），
  它**不在 Agent 补丁白名单内**，Agent 无法启用。

## 定位签名入口

标准顺序：

1. `evaluate()` 先确认目标读取的环境值正确（指纹、locale、screen、WebGL）。
2. `enableTrace()`，再跑一轮业务入口。
3. `trace()` 读兼容层 API 命中；需要断点时 `watchApis(list)` + `openInspector()`。
4. 触发目标 XHR/fetch，从 `networkRequests()` 读 wire URL、headers、body。

**实测注意**：`enableTrace()` 后跑一轮再 `trace()` 可能返回**空数组** ——
Trace 记录的是被追踪 API 的命中，不是全量执行日志。真正好用的做法是让目标脚本把中间值
挂到 `globalThis` 再 `evaluate` 读回，或用 `watchApis()` 指定关注面。需要真实 DevTools
调用栈时回 js-reverse Edge MCP 取证。

`openInspector()` 只依赖 Node inspector，**不需要 Edge**，图形调试可用 Chrome DevTools
或 VS Code。但暂停只在 **child-process** 后端可用；worker-thread 返回
`ERR_EDGE_INSPECTOR_UNSUPPORTED`。

## 指纹 profile

默认 Edge 150。可切 151 / 152。切换后**必须回读验证**：

```js
console.log((await sandbox.evaluate('navigator.userAgent')).value);
console.log((await sandbox.evaluate('navigator.userAgentData.brands.map(b=>b.brand+"/"+b.version).join(" | ")')).value);
console.log((await sandbox.evaluate('screen.width + "x" + screen.height + " dpr=" + devicePixelRatio')).value);
```

`fingerprint` 只校验顶层键；其下 navigator/screen/rendering 等深层子键与基线**合并**，
拼错会静默回退基线值，不报错。所以改完一定要读回，别以为改了。

**locale 由 profile 决定，不由宿主机决定。** 这层行为探针验证不了（探针期望值来自真实
Edge，而采集时真实 Edge 的默认 locale 就是采集机的系统 locale，拿它当基准等于把采集机
locale 写进契约），所以 NV8 用内部一致性检查兜底，并在 Realm 内接管 `Intl`。
副作用：`navigator.language` 与 `Intl.DateTimeFormat().resolvedOptions().locale` 现在一致，
同一 profile 在不同机器上给同一身份。

## 调试沙箱子进程

```js
const sandbox = await EdgeSandbox.create({
  page: { url: 'https://target.test/' },
  execution: { backend: 'child-process' },
  limits: { timeoutMs: 300_000 },   // 暂停时间也计入这个预算
});
const { url, alreadyOpen } = await sandbox.openInspector();
console.log(url);   // 默认 127.0.0.1 随机端口
```

正常重建 Realm 时端点保留，但 **execution context ID 会变化**。子进程崩溃或重启后端点失效。
运行时崩溃重启需设置 `execution.restart: 'restart'`。

## 常见问题

| 现象 | 原因 / 对策 |
|---|---|
| `vm.SourceTextModule is not a constructor` | 缺 `--experimental-vm-modules`（仅进程内 `createNv8`/测试/构建需要） |
| `Sandbox evaluation exceeded the 5000ms wall-clock timeout` | 首次装配约 20s；把 `limits.timeoutMs` 放大到 60000+ |
| `fetch()` 返回 `TypeError` | 正常：离线回放未命中。要么配 replay，要么把这当作“脚本想请求什么”的证据 |
| 返回结果是 `{ type: "other" }` | 该值不可直接序列化；在 Realm 内 `JSON.stringify` 后按 string 取回 |
| `Worker 无法加载` | Worker 脚本也要 replay；检查 `maxWorkerRealms` / `maxWorkerConnections` / `maxWorkerDepth` 配额 |
| `getUserMedia()` 返回 `NotFoundError` | 未配置媒体设备；见 NV8 `docs/user-guide.md` §11.3 |
| Sensor 返回 `NotReadableError` | 未配置传感器；见 §11.4 |
| baseline 报出 surface 差异 | 先 `npm run capabilities` 确认是不是 Node 版本导致的宿主限制 |
| 运行很慢或超时 | 查 `timeoutMs` 是否过小；首次装配固定有 ~20s 一次性成本 |
| `ERR_MODULE_NOT_FOUND: Cannot find package 'nv8'` | 包自引用只在仓库目录内生效；外部项目先在 `package.json` 声明 `"nv8": "file:<nv8-root>"` 并 `npm install` |

## 能力边界（不要过度宣称）

**可以依赖**：DOM/事件/生命周期/CSSOM 表面、原生函数 `[native code]` 伪装、Realm 与
Worker 隔离、确定性时钟、离线 replay、指纹 profile、Protocol/Collector 分层。

**不应宣称**：

- **不是浏览器自动化**。不点击（`dispatchTrustedInput` 只是派发可信事件，不是真实用户
  交互）、不截图、不等元素出现。
- **没有排版引擎**。`offsetWidth`、`getBoundingClientRect` 是近似模型（显式尺寸 →
  内联文本字体度量 → 后代最大值；`documentElement`/`body` 按视口，其余为 0），
  不是浏览器真值。
- **`Intl` 有天花板**。Node 与 Chromium 各自打包 ICU，语言**显示名**不同：
  `Intl.DisplayNames('en-US',{type:'language'}).of('zh-Hant')` 真实 Edge 是
  `Chinese (Traditional)`，Node 18–24 都是 `Traditional Chinese`。这是 ICU 数据版本
  差异，宿主升级修不掉，已登记。
- **时区不进探针**。实测 Chromium 在 Windows 上不理 `TZ` 环境变量、只跟随操作系统时区，
  所以采集器锁不住它，写进 fixture 就是烙一个采集机的时区。（NV8 自己能锁 —— 子进程
  env 会设 `TZ`，Node 认这个变量。）
- 三层对齐（全局名存在性 / 原型成员与描述符 / 运行时行为）的**具体数字**与已登记缺口
  查 NV8 `docs/edge-parity.md`，不要凭记忆引用。

## 官方文档索引

NV8 仓库内（`<nv8-root>/docs/`）：

| 文件 | 内容 |
|---|---|
| `user-guide.md` | 完整操作说明书（本文的原始来源，1600+ 行） |
| `api-reference.md` | 公共 API 权威清单 |
| `protocol-collector.md` | Protocol 与 Collector 边界、错误码 |
| `agent-bridge.md` | Agent Session 与 stdio JSON-RPC |
| `evidence-contract.md` | Evidence Bundle、签名验证、脚本策略 |
| `edge-parity.md` | 三层对齐数字与已登记差异 |
| `node-compatibility.md` | 各 Node 版本兼容矩阵 |
| `security-boundaries.md` | 安全边界 |
| `sign-server-protocol.md` | 常驻签名服务协议 |
| `state-scope.md` | 状态作用域 |
| `backend-benchmark.md` | 两种后端性能对比 |
| `target-playbooks/` | **站点手册**：阿里云 V2、Cloudflare Turnstile、抖音 bdms、小红书 x-s、Akamai、cqvip rs6、ouyeel rs6、gdtv wasm-sign、jsl clearance、10jqka、adidas hk |
