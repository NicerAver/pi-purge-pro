# Protocol → Collector 采集链路

NV8 把“算签名”和“发请求”拆成两层，这是框架的核心安全边界：目标脚本不可信，
它需要足够真实的浏览器环境才能算出签名，但**绝不应该因此获得访问真实网络的能力**。

```
Evidence Bundle (离线证据)
  → Runtime        执行目标 JS，产出 Artifact        ← EdgeSandbox
  → Protocol       Artifact → RequestPlan（纯变换，无 IO）
  → Collector      执行 RequestPlan（唯一网络出口，受策略约束）
```

每层只能**向下传递数据**，不能向上索取能力。

## 四种数据契约

| 契约 | 生产者 | 消费者 | 特性 |
|---|---|---|---|
| `RuntimeArtifact` | Runtime | Protocol | 只读、canonical JSON、带 schema 版本与摘要 |
| `RequestTransform` | Protocol adapter | Protocol registry | 声明式、可审计、可检测冲突 |
| `RequestPlan` | Protocol | Collector | 只读、已归一化、含摘要 |
| `CollectorResult` | Collector | 调用方 | 含响应、尝试记录、脱敏审计 |

## 1. Runtime Artifact

```js
import { createRuntimeArtifact, ArtifactKind } from 'nv8/protocol';

const signature = createRuntimeArtifact({
  id: 'target.signature',
  kind: ArtifactKind.SIGNATURE,
  value: 'a1b2c3d4',
  producer: 'target-signer-script',
  expiresAt: Date.now() + 60_000,
});
```

约束：

- `value` 必须是 **canonical JSON 可表示**的。函数、Symbol、`NaN`、循环引用在创建时抛错，
  **而不是**在摘要阶段静默产生不确定结果。
- `id` 是稳定标识，供 adapter 引用。
- `expiresAt` 过期后禁止参与请求变换 —— 宁可失败也不发出错误签名。
- 创建后被 `Object.freeze`，附带 `digest` 与 `byteLength`。

`ArtifactSet` 提供有界集合：超过 `maxArtifacts` / `maxArtifactBytes` / `maxTotalBytes`
抛结构化错误，**不静默丢弃**。

### schema 兼容规则

`schemaVersion` 形如 `major.minor`：

- major 不同 → 拒绝消费
- 工件 minor 高于消费者 minor → 拒绝消费
- 工件 minor 低于或等于消费者 → 接受

Protocol schema 当前为 `1.0`；不同 major 返回 `PROTOCOL_SCHEMA_UNSUPPORTED`。
它与 Artifact schema、Frame Protocol 和 Core SemVer **相互独立**。

## 2. Protocol Adapter

```js
import { defineProtocolAdapter, createTransform } from 'nv8/protocol';

const adapter = defineProtocolAdapter({
  id: 'target-signer',
  version: '1.0.0',
  consumes: [{ id: 'target.signature' }],
  plan: ({ request, artifacts, now }) => [
    createTransform('set-header', {
      name: 'X-Signature',
      value: artifacts.require('target.signature').value,
    }),
  ],
});
```

`plan(context)` 的 context **只有三个键**：`request`、`artifacts`、`now`。
适配器拿不到 socket、`fs`、凭据或 Collector 句柄 —— 这一点由测试
（`tests/gate5-end-to-end-test.js`）断言，而不是仅靠约定。

用声明式 transform 而不是让 adapter 直接构造请求，是为了让“改了哪些字段”可审计、
可检测跨 adapter 冲突。完整流程：

1. `createRuntimeArtifact()` 建不可变 Artifact；
2. `createArtifactSet()` 设数量与字节上限；
3. `defineProtocolAdapter()` 声明所需 Artifact 与纯函数 `plan()`；
4. `createTransform()` 建声明式 header/query/body/cookie 变换；
5. `createProtocolRegistry()` 应用 adapter，检测冲突并输出 Result；
6. 把 Result 的 `plan` 交给 Collector，**不要在 adapter 内发请求**。

Protocol 不接受相对 URL、危险 header 值、非法 cookie 或安全方法 body；所有输出都应
可序列化并带稳定摘要。

## 3. Collector

```js
import { createCollector, createFetchTransport } from 'nv8/collector';

const collector = createCollector({
  transport: createFetchTransport(),
  policy: { enabled: true, allowedOrigins: ['https://target.test'] },
  credentials: {
    origins: {
      'https://target.test': { headers: { authorization: 'Bearer configured-secret' } },
    },
  },
  retry: { maxAttempts: 3, baseDelayMs: 200 },
});

try {
  const response = await collector.send(plan);
  console.log(response.response.status, response.attempts);
} finally {
  await collector.dispose();
}
```

### 安全默认值

- **网络未显式开启时全部拒绝。** 必须 `policy.enabled: true` 并配 `allowedOrigins`。
- allowlist 检查**先于**凭据注入和 Transport IO。
- 凭据按**精确 origin** 绑定，在 `describe()`、审计和错误中显示为 `[redacted]`。
- **Protocol / 策略错误永不重试**（`ERR_NV8_*_POLICY`、`ORIGIN_NOT_ALLOWED`、
  `CREDENTIAL_NOT_FOUND`）。
- 非幂等方法默认不重试。
- WebSocket 业务消息已经写出后，失败默认**不可重放**。
- Collector 会话 Cookie 与 Realm 内 `document.cookie` **完全隔离**。
- `dispose()` 是终止边界；发送中的请求、审计和会话 Cookie 不应在销毁后继续使用。

## 4. 采集调度

```js
import {
  Collector, createPaginationScheduler,
  createNdjsonResultSink, createMemoryCheckpointStore,
} from 'nv8/collector';

const collector = new Collector({
  policy: { allowedOrigins: ['https://api.example.com'] },
  rateLimit: { requestsPerSecond: 5, burst: 10, maxConcurrent: 3 },
  circuitBreaker: { failureThreshold: 5, resetTimeoutMs: 30_000 },
});

const sink = createNdjsonResultSink({
  filePath: './out/items.ndjson',
  keyOf: (item) => item.id,          // 去重主键，必须由你指定
});

const scheduler = createPaginationScheduler({
  collector,
  nextRequest: ({ index, previous, resumeContext }) => {
    const cursor = previous ? previous.response.body.next : (resumeContext?.cursor ?? null);
    if (index === 0 && cursor === null) return { url: 'https://api.example.com/items', method: 'GET' };
    return cursor ? { url: `https://api.example.com/items?cursor=${cursor}`, method: 'GET' } : null;
  },
  extractItems: (result) => result.response.body.items,
  checkpoint: {
    store: createMemoryCheckpointStore(),
    jobId: 'items',
    job: { target: 'items', query: {} },      // 指纹，查询变了就不会错续
    contextOf: (page) => ({ cursor: page.response.body.next }),
  },
  limits: { maxPages: 500, maxEmptyPages: 2 },
});

for await (const page of scheduler.pages()) {
  if (page.stop !== null) { console.log('结束：', page.stop.reason, page.stop.totalItems); break; }
  await sink.write(page.items);
}
await sink.close();
```

### 不猜业务语义

**分页游标怎么取、条目主键是哪个字段，都必须由调用方指定。** 猜错的代价是静默少采或
静默丢数据，比报错严重得多。这也是 `nextRequest` 必须自己回答的原因。

### 可用组件

| 组件 | 用途 |
|---|---|
| `PaginationScheduler` | cursor 增量分页；检测重复 cursor、空页、页数和条目上限 |
| `createBatchingResultSink({persist})` | 为 Postgres/SQLite 等外部存储提供统一批量 `write`/`flush`/`close`；**只有持久化成功后才提交去重 key**，失败可安全重试 |
| `createMemoryResultSink()` / `createNdjsonResultSink()` | 批量写入、显式 key 去重、`close()` 冲干；NDJSON 损坏末行可跳过并计数 |
| `createMemoryCheckpointStore()` / `createFileCheckpointStore()` | 任务指纹绑定、原子文件写、损坏检查点回退为重新开始 |
| `createProxyTransport()` | 显式代理池、HTTP CONNECT/SOCKS5、代理健康与限流 |
| `createWebSocketTransport()` | 有界 RFC 6455 请求/响应交换，**不承担后台订阅重连** |

不内置数据库驱动：落地定义为接口，接 Postgres/SQLite 由调用方提供 `persist`，
且应具备事务性或幂等性。

## 错误码

| 错误码 | 含义 | 可重试 |
|---|---|---|
| `ERR_NV8_*_POLICY` | 策略拒绝 | 永不 |
| `ORIGIN_NOT_ALLOWED` | origin 不在 allowlist | 永不 |
| `CREDENTIAL_NOT_FOUND` | 该 origin 无绑定凭据 | 永不 |
| `PROTOCOL_SCHEMA_UNSUPPORTED` | schema major 不兼容 | 永不 |
| `REQUEST_FAILED` | 请求失败，看 `retryable` | 视标记 |
| `REQUEST_TIMEOUT` | 超时，看 `retryable` | 视标记 |
| `RETRY_EXHAUSTED` | 重试耗尽，保留 attempts 与审计 | 由上层决定重排 |

## 不属于本层的职责

- Collector 不做签名、不做业务语义解析、不做分页决策。
- Protocol adapter 不做 IO、拿不到凭据。
- Runtime 拿不到真实网络。`networkRelay` 是唯一例外且不由 Agent 启用。
- 真实网络、凭据、代理和数据库驱动**不应从页面脚本或 Protocol adapter 透传到 Realm**。
