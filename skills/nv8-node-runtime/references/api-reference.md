# NV8 API 参考（协议恢复视角）

只列协议恢复与采集实际会用到的入口。本节所有“实测”值来自在
`Edge 150 profile / Node 24 / Windows` 上的真实运行，不是文档转述。

## 导入方式

**仓库内部**（未装依赖）用相对路径：

```js
import { EdgeSandbox } from './src/public/edge-sandbox.js';
```

**作为项目依赖**时在 `package.json` 声明 `"nv8": "file:<nv8-root>"` 并 `npm install`，
之后按包名导入：

```js
import { EdgeSandbox, createNv8, nv8Eval } from 'nv8';
import { createAgentSession } from 'nv8/agent';
import { createRuntimeArtifact, ArtifactKind } from 'nv8/protocol';
import { createCollector, createFetchTransport } from 'nv8/collector';
```

> 包自引用只在**仓库目录内**的脚本里生效。把 runner 放到仓库外又没装依赖，会得到
> `ERR_MODULE_NOT_FOUND: Cannot find package 'nv8'`。这也是为什么 runner 模板要写在
> 目标项目里并先声明依赖。

## 结果信封（最高频的坑）

`sandbox.evaluate()` 返回的是**结构化信封**，不是裸值：

```js
const r = await sandbox.evaluate('navigator.userAgent');
// { type: 'string', value: 'Mozilla/5.0 ... Edg/150.0.0.0' }
r.value;   // ← 必须解包
```

实测各类型：

| 表达式 | type | 备注 |
|---|---|---|
| `navigator.userAgent` | `string` | |
| `1 + 2` | `number` | |
| `fetch(...)` 未命中 replay | 抛 `TypeError` | 不是信封，直接 reject |
| 返回 `undefined` 的表达式 | `undefined` | |
| 非上述可序列化类型 | `other` | 见 user-guide 常见问题 18.4 |

复杂值用 `JSON.stringify(...)` 在 Realm 内序列化后按 string 取回，最省事。

## EdgeSandbox

### 创建

```js
const sandbox = await EdgeSandbox.create({
  page: { url: 'https://target.test/', html: '<!doctype html><main id="app">Ready</main>' },
  limits: { timeoutMs: 60_000 },
});
```

- **实测首次创建约 20 秒**（子进程启动 + 完整表面装配）。默认 `timeoutMs` 为 5000，
  初次装配必定超时，宿主必须显式放大。
- 未知配置键、类型错误、越界值、重复 replay 记录都会让 `create()` 拒绝，不被静默忽略。
  （`fingerprint` 只校验顶层键；其下深层子键与基线合并，拼错会静默回退基线值 —— 所以
  改指纹后必须回读验证，别假设生效。）

### 执行

| 方法 | 说明 |
|---|---|
| `evaluate(source)` | 执行脚本，返回结果信封 |
| `evaluateWithPayload(source, payload)` | 带命名二进制载荷，Realm 内经 `globalThis.__nv8Payload` 读，字节走原生类型不经 base64 |
| `batchEvaluate(sources)` | 批量执行，共享同一 Realm |
| `evaluateModule(source, url)` | 以 ES 模块方式执行 |

### 页面与请求

| 方法 | 说明 |
|---|---|
| `setPage(page)` | 换页。保存可持久化的 Cookie/Storage，终止旧执行单元，旧闭包/定时器/Worker 不再存活。**始终传完整页面对象**，不要依赖继承 |
| `networkRequests()` | **协议恢复主产出**。返回冻结快照，按请求到达离线网络边界的顺序排列 |
| `clearNetworkRequests()` | 清空请求记录 |

### 观察与调试

| 方法 | 说明 |
|---|---|
| `enableTrace()` / `trace()` | 记录兼容层 API 的属性访问与函数调用，用于定位签名入口 |
| `disableTrace()` / `clearTrace()` | 关闭 / 清空 |
| `watchApis(list)` | API 访问断点；需先 `enableTrace()`；命中时若已附 inspector 则在访问处暂停；传空数组清除 |
| `openInspector({port, host})` | 打开子进程 V8 调试端点，返回 `{url, alreadyOpen}`；默认 `127.0.0.1` 随机端口。**仅 child-process 后端支持暂停**，worker-thread 报 `ERR_EDGE_INSPECTOR_UNSUPPORTED` |
| `resources()` | 当前 Realm / Worker / 定时器占用与 graph 指纹 |
| `diagnose()` | 诊断摘要 |

`trace()` 只观察兼容层 API 调用，**不代表真实 Chromium DevTools 调用栈**。需要真实调用栈
时用 js-reverse Edge MCP 取证。实测：`enableTrace()` 后跑一轮再 `trace()` 仍可能得到
空数组 —— 它记录的是被追踪 API 的命中，不是全量执行日志；要定位入口优先用
`watchApis()` 或让目标脚本自己把中间值挂到 `globalThis` 再读回。

### 可信输入

```js
await sandbox.dispatchTrustedInput('click');
await sandbox.dispatchTrustedInput('keydown', { key: 'Enter', code: 'Enter' });
```

支持 `click` / `dblclick` / `mousedown` / `mouseup` / `mousemove`（PointerEvent）、
`keydown` / `keyup`（KeyboardEvent）、`input` / `change`（Event）。
其余类型抛 `RemoteSandboxError: Failed to dispatch trusted input: unsupported input type "..."`（实测 `scroll` 即如此）。
事件目标是文档当前活动元素，沿正常冒泡路径到达 window 监听器。

### 关闭

```js
await sandbox.close();   // 幂等；关闭后不能再执行、换页或读 Trace/请求日志
```

## 隔离边界（实测）

```js
await sandbox.evaluate('typeof process');   // "undefined"
await sandbox.evaluate('typeof require');   // "undefined"
await sandbox.evaluate('typeof Buffer');    // "undefined"
```

沙箱执行单元不能导入 Node 内置模块、npm 包、本地文件或网络模块。**宿主负责读文件**，
再把源码交给 `evaluate()`：

```js
const source = await readFile('./target-bundle.js', 'utf8');
const result = await sandbox.evaluate(source);
```

## 身份表面（Edge 150 profile 实测）

| 探针 | 实测值 |
|---|---|
| `navigator.userAgent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0` |
| `navigator.platform` | `Win32` |
| `navigator.language` | `zh-CN`（跟随 profile，不跟随宿主机） |
| `screen` | `1920x1080`，`devicePixelRatio = 1` |
| `navigator.webdriver` | `false` |
| `navigator.userAgentData.brands` | `Not=A?Brand/99 \| Microsoft Edge/150 \| Chromium/150` |
| `Function.prototype.toString.call(document.addEventListener)` | `function addEventListener() { [native code] }` |
| `Function.prototype.toString.call(window.fetch)` | `function fetch() { [native code] }` |
| `Function.prototype.toString.call(Function.prototype.toString)` | `function toString() { [native code] }` |
| `Document.prototype.querySelector.call({}, 'a')` | `TypeError: Illegal invocation` |
| `getComputedStyle(document.body).display` | `block` |
| WebGL `UNMASKED_VENDOR_WEBGL` | `Google Inc. (NVIDIA)`（随 profile 的渲染基线） |
| `document.createElement('canvas').toDataURL()` | 稳定 PNG（`data:image/png;base64,...`） |

`canvas` 与 `WebGL` 分离 masked / unmasked 两组，改指纹时不要只改一组。

## 指纹与 Profile

内置 Profile：

| Profile | 内容 |
|---|---|
| `minimal` | WebIDL、错误、内建对象、Console |
| `minimal-fetch` | 增加离线 Fetch |
| `dom-replay` | DOM、Storage、Fetch/XHR 离线回放 |
| `legacy-full` | 迁移期全量入口，experimental |
| `browser-profile-edge-v150` | Edge 150 指纹 Profile（默认） |

冻结指纹子路径入口：`nv8/fingerprint/edge-150`、`edge-151`、`edge-152`。

**locale 由 profile 决定，不由宿主机决定。** NV8 在 Realm 内接管 9 个 `Intl` 构造器与
8 个 `toLocale*` 方法，仅在调用方未传 locales 时填入 profile 的 `navigator.language`。
UA 默认字体族也跟着 locale 切（`zh-CN` → `Noto Sans SC`，`ja-JP` → `Yu Gothic`，
`zh-TW` 走通用默认 `Times New Roman`，所以**不能按 `zh` 前缀一刀切**）。

## createNv8 / nv8Eval

`createNv8()` 是**进程内** API，用于可信插件开发与表面验证，**不提供 child-process 安全边界**。
不可信目标代码不要用它。

```js
const nv8 = await createNv8({ profile: 'minimal-fetch', limits: { timeoutMs: 3000 } });
try {
  const global = await nv8.createRealm({ type: 'root' });
  console.log(await nv8.eval('1 + 2'));
} finally {
  await nv8.destroy();
}
```

返回值含 `sandbox`、`lockPlan`、`hostCapabilities`、`capabilityResolution`、`runtimeMode`、
`createRealm()`、`eval()`、`destroy()`、`inspect()`。

`nv8Eval(code, options)` 是 `createNv8()` + 临时求值 + `destroy()` 的便捷封装，适合
一次性无状态计算。Realm `type` 支持 `root` / `iframe` / `worker` / `worklet`。
临时 `eval()` 的超时同时限制同步执行与返回值异步等待，超时以
`ERR_SCRIPT_EXECUTION_TIMEOUT` 拒绝。

## Agent Session

```js
import { createAgentSession } from 'nv8/agent';

const session = await createAgentSession({
  agent: { agentId: 'pi', agentVersion: '1.0', agentCapabilities: ['evaluate', 'observe', 'patch'] },
  sandbox: { page: { url: 'https://target.test/' }, proxyTrace: { enabled: true } },
});
```

方法：`evaluate()`、`compareEnvironment()`、`observe()`、`applyEnvironmentPatch()`、
`rollback()`、`watchApis()`、`openInspector()`、`setPage()`、`enableTrace()` /
`disableTrace()` / `clearTrace()`、`close()`。

### EnvironmentPatch

必须含 `baseVersion`（必须等于当前 `environmentVersion`）、非空 `reason`、
`changes`（**只允许 `page` / `fingerprint` / `replay`**），可选 `auditId`、`expiresAt`。

`fingerprint` 是对已归一化指纹的已知字段**合并**，未知路径 fail closed。
以下字段不能通过补丁改变：`limits`、`execution`、Evidence、Collector 凭据、真实网络策略、
脚本策略。每次成功变更生成新版本与审计记录，失败不推进版本；最近 64 个版本可 `rollback(version)`。

`agentCapabilities` **只是审计元数据，不参与鉴权**。声明 `['observe']` 不会禁止你调用
`applyEnvironmentPatch`；真正的边界是 patchable 字段白名单。

### compareEnvironment（逆向侦察首选验证入口）

```js
await session.compareEnvironment('screen.width', {
  baseVersion: 0,
  reason: 'match captured desktop geometry',
  changes: { fingerprint: { screen: { width: 1440 } } },
});
```

它在两个**新鲜、隔离**的 Sandbox 中执行同一脚本，返回 `before` / `after` / `diff`，
比较求值结果、Trace、网络请求和资源摘要。**不改变当前会话版本，也不继承当前 Realm 的
Cookie/Storage 状态** —— 所以它是安全的假设验证入口：先 `compareEnvironment` 验证，
确认后再 `applyEnvironmentPatch` 落地。

## Stdio JSON-RPC 桥

单会话、无依赖的 stdio 入口。会话在进程启动时按 `NV8_SANDBOX_OPTIONS_FILE`（优先）或
`NV8_SANDBOX_OPTIONS` 创建；两者都未设置则用默认 Sandbox 配置。
**大 replay/evidence 配置会撞 Windows 32KB 环境变量上限，必须走文件形式。**

```bash
NV8_AGENT_ID=pi NV8_AGENT_VERSION=1.0 NV8_AGENT_CAPABILITIES=evaluate,observe,patch \
  npm run agent:bridge
```

每行一个 JSON-RPC 2.0 请求，响应写 stdout：

```json
{"id":1,"method":"session.evaluate","params":{"source":"screen.width"}}
{"id":2,"method":"session.observe","params":{}}
{"id":3,"method":"session.describe","params":{}}
```

支持的方法：`session.describe` / `evaluate` / `compareEnvironment` / `observe` /
`applyEnvironmentPatch` / `rollback` / `enableTrace` / `disableTrace` / `clearTrace` /
`watchApis` / `openInspector` / `close`。

## 错误层级

按错误**层级**处理，不要用错误消息猜是否可重试：

| 错误 | 含义 | 可重试 |
|---|---|---|
| Profile / Plugin / 能力错误 | 配置或宿主不满足，修正后重建实例 | 否 |
| `ERR_NV8_*_POLICY`、`ORIGIN_NOT_ALLOWED`、`CREDENTIAL_NOT_FOUND` | 策略拒绝 | **永不** |
| `REQUEST_FAILED`、`REQUEST_TIMEOUT` | 看 `retryable` 与 attempts | 视标记 |
| `RETRY_EXHAUSTED` | 保留 attempts 与审计，上层决定是否重排 | 由上层 |
| `ERR_NV8_MODULE_EVALUATION_CANCELLED` | Realm 已销毁或 generation 失效，旧 Promise 不得重注入资源 | 否 |
| `ERR_SCRIPT_EXECUTION_TIMEOUT` | 超出 `limits.timeoutMs`，执行单元被终止重建 | 重新执行 |
| `LIMIT_REALM_CAPACITY` | Realm 容量超限 | 释放后重试 |
| `SandboxTimeoutError` / `ERR_EDGE_SANDBOX_TIMEOUT` | 同上，装配期最常见的是 timeoutMs 太小 | 放大预算 |

所有 `destroy()` / `close()` / Collector `dispose()` 都设计为幂等。
