# cdfsunrise `md5__1803` WAF 逆向与 iv8 纯协议回放

## 1. 文档定位

配套 HTML 阅读版：`references/tutorials/cdfsunrise-md5-1803-tutorial.html`。

本文记录一个 Aliyun WAF challenge 场景的完整 iv8 复现过程。目标接口为：

```text
POST https://api.cdfsunrise.com/restapi/search/list
```

最终交付不是浏览器自动化，而是：

```text
Python requests 获取 fresh challenge
    -> iv8 执行 challenge 初始化与 WAF bundle
    -> 调用闭包内 LK 生成 md5__1803
    -> requests 使用同一 Session 回放业务 POST
```

本文中的“纯协议”指不启动 Camoufox、Playwright 或真实浏览器，只使用 HTTP 客户端和 iv8 JavaScript runtime。它不等同于“纯算”：纯算还要求完全不执行原始 WAF JavaScript，仅用 Python 重写所有算法。

本文不保存运行时 Cookie、签名 URL、Authorization、完整业务响应或个人凭证。案例中的请求字段仅用于说明结构，实际运行时动态 challenge、`acw_tc` 和 `md5__1803` 必须重新生成。

## 2. 最终结论

本案例已经达到以下验收标准：

```text
challenge_status=200
replay_status=200
replay_content_type=application/json; charset=utf-8
responseHead.isSuccess=true
responseHead.code=0
```

关键事实：

- 首次请求不带有效长 `md5__1803` 时，服务端返回约 110 KB 的 challenge HTML；
- challenge HTML 内含 `_waf_bd8ce2ce37` 初始化状态、内联 Aliyun WAF 脚本和外链 runtime；
- 长 `md5__1803` 不是业务 SDK 的短签名 `dySig`；
- 原始 WAF 入口位于闭包内，不能直接从 `window` 访问；
- 静态分析确认调用关系为 `Lf -> LK -> Lb`；
- `LK` 的调用形态为：

```javascript
LK(url, body, method, 2)
```

- 运行时通过原始源码映射保护 `Function.prototype.toString` 后，可以安全地把 `LK` 的闭包引用导出到 `window`；
- iv8 生成的 `ssxmod_*` 不需要转发给业务 `requests` 会话；
- 实际成功回放只需要沿用 challenge 响应中的 `acw_tc`。

## 3. 先明确三个层次

### 3.1 业务层

业务页面会发起搜索列表请求，body 是 JSON。body 的字段顺序和序列化方式必须稳定：

```json
{
  "filter": "",
  "pageNumber": 1,
  "pageSize": 10,
  "keys": {"7": "263"},
  "order": 1,
  "param": {},
  "sceneId": "qpol",
  "priceExp": ""
}
```

业务页面还存在一个短签名或业务 SDK 参数，但它不是 Aliyun WAF 的长 `md5__1803`。逆向时必须把两者分开。

### 3.2 WAF challenge 层

首次请求可能返回：

- HTTP 200，但 `content-type` 为 `text/html`；
- HTML 中出现 `renderData`；
- `<meta name="aliyun_waf_aa">`、`aliyun_waf_bb` 等元数据；
- 内联初始化脚本写入 `_waf_bd8ce2ce37`、`_waf_a86dfdc5f2`；
- 外链 WAF runtime；
- 内联 WAF bundle。

因此不能把“HTTP 200”当成业务成功。必须判断 content type 和 JSON 业务码。

### 3.3 最终业务回放层

业务请求必须由同一个 `requests.Session` 回放，至少保持：

- `acw_tc`；
- User-Agent；
- Referer；
- body 字节；
- method、URL path 和 query；
- `content-type` 和业务 headers。

签名 URL 不能与另一个 Session 的 Cookie、UA 或 body 混用。

## 4. 为什么先做响应分层

常见错误是看到接口返回 200 就认为请求成功，或者只观察签名长度。正确的判定矩阵是：

| 状态 | content type | 业务表现 | 解释 |
|---|---|---|---|
| 200 | `text/html` | `renderData` | WAF challenge，不是业务成功 |
| 200 | `application/json` | `code=0` | 业务成功 |
| 200 | `application/json` | 非 0 code | 业务层失败，需单独排查 |
| 405/403/412 | HTML 或空响应 | 无业务数据 | 可能是 challenge、方法或边缘拦截 |

最小验收代码：

```python
response = session.post(
    signed_url,
    headers=headers,
    data=body_text.encode("utf-8"),
    timeout=30,
)

content_type = response.headers.get("content-type", "")
if response.status_code != 200 or "application/json" not in content_type:
    raise RuntimeError("仍处于 WAF/网关响应，不是业务 JSON")

payload = response.json()
head = payload.get("responseHead", {})
if head.get("isSuccess") is not True or head.get("code") != 0:
    raise RuntimeError(f"业务失败: {head}")
```

## 5. 证据采集顺序

### 5.1 只保留一个 baseline

可以使用普通 Chrome、Camoufox 或 js-reverse MCP 采集，但一轮证据必须保持同一来源。不能把：

- Chrome 的 Cookie；
- Camoufox 的 UA；
- 另一个浏览器的签名；
- requests 的 TLS 指纹；

拼成一个“看起来完整”的请求。

本案例的浏览器 baseline 用于确认业务请求和成功响应；最终生产路径不再启动浏览器，而是用 iv8 的可表达环境。

### 5.2 记录完整请求契约

至少记录：

```text
method
clear URL
signed URL
body 原文
body 字节长度
headers
Set-Cookie
response content-type
responseHead.code
```

不要只保存签名后缀。签名通常依赖 URL、body、method、时间和 WAF 状态。

### 5.3 先抓 challenge，再抓签名

建议先发一次不带有效长签名的请求：

```python
challenge = session.post(
    API_URL,
    headers=HEADERS,
    data=BODY_TEXT.encode("utf-8"),
    timeout=30,
)

if "text/html" not in challenge.headers.get("content-type", ""):
    raise RuntimeError("没有拿到 challenge，先不要进入 iv8")
```

这样可以获得当轮的：

- challenge HTML；
- `acw_tc`；
- `_waf_bdce2ce37` 初始化输入；
- 当前 bundle 版本和脚本节点结构。

## 6. 区分业务短签名与 WAF 长签名

页面 bundle 中可能存在业务 SDK 的 `dySig`、`getSigKey`、`encodeQueryString` 等函数。这些通常有以下特征：

- 输出较短；
- 和业务 headers、业务参数或业务 URL 有关；
- 不一定会触发 Aliyun WAF challenge；
- 生成位置可能在 app webpack chunk 中。

Aliyun WAF 长签名的特征是：

- 位于 query 参数 `md5__1803`；
- 长度约 200 个字符；
- 前缀带 WAF 会话标识，例如 `2790552d-`；
- 生成依赖 challenge 初始化状态和 WAF 内部随机/环境数据；
- 长签名成功后才返回业务 JSON。

错误路线是把短 `dySig` 当成 `md5__1803`，或者只复现业务 SDK 而没有处理 challenge 生命周期。

## 7. 静态定位 WAF 入口

### 7.1 不要一开始就运行时 hook 原始 bundle

Aliyun WAF bundle 可能检查：

- `Function.prototype.toString()` 的源码结果；
- 闭包函数数量或源码哈希；
- 初始化调用顺序；
- 某些全局对象的原生外形；
- 同步执行时间和随机状态。

直接把 `LK` 改成：

```javascript
window.__wafLK = function () {
    return LK.apply(this, arguments);
};
```

看似只是观测，实际上会改变源码、函数外形或闭包初始化顺序，导致同步卡死或进入错误分支。

### 7.2 AST 提取目标

应先通过 Babel AST 或等价解析器提取：

```text
L2
L3
L7
LS
LU
Li
Ln
LK
Lf
```

对每个函数保存：

- 源码起止范围；
- 参数列表；
- 直接调用的函数；
- 读取的闭包变量；
- 读取的 window/document/navigator/storage 字段；
- 返回值类型。

伪代码：

```javascript
traverse(ast, {
  FunctionDeclaration(path) {
    const name = path.node.id && path.node.id.name;
    if (!TARGETS.has(name)) return;
    const deps = new Set();
    path.traverse({
      CallExpression(call) {
        if (call.node.callee.type === "Identifier") {
          deps.add(call.node.callee.name);
        }
      }
    });
    result[name] = {
      start: path.node.start,
      end: path.node.end,
      params: path.node.params.map(p => p.name || null),
      deps: [...deps]
    };
  }
});
```

### 7.3 入口调用关系

本案例恢复出的核心关系：

```text
请求包装器 Lf(LZ)
    -> 规范化 URL/body/method
    -> LK(LZ, LE, Lb, Lj)
    -> L3() 采集环境数组
    -> 伪随机与动态 alphabet
    -> MD5/LZ/编码链
    -> 返回带 md5__1803 的 URL
```

实际参数顺序不能凭函数名猜测。必须结合调用点和真实网络请求确认：

```javascript
LK(url, body, "POST", 2)
```

其中第四个参数是分支标志，`2` 进入 POST 请求路径。

## 8. iv8 的正确生命周期

### 8.1 页面加载快照

WAF challenge 依赖同源 DOM、location、cookie 和脚本节点。最小 iv8 页面快照：

```python
snapshot = {
    "baseURL": API_URL,
    "html": dom_snapshot,
    "headers": [["content-type", "text/html"]],
}

ctx.eval(
    "window.__iv8__.page.load("
    + json.dumps(snapshot, ensure_ascii=False)
    + ");"
)
```

挑战 HTML 中的脚本不能简单全部执行。这里的策略是：

1. 从 HTML 中提取初始化脚本；
2. 删除可自动执行的 script 节点，避免重复触发；
3. 在 DOM 尾部保留一份原始内联 WAF 源码注释，供外链 runtime 按原页面结构读取；
4. 用 `ctx.eval(..., name=...)` 按已确认顺序执行脚本。

### 8.2 环境字段

本案例的有效最小 environment 包含：

```python
environment = {
    "location": {
        "href": API_URL,
        "origin": "https://api.cdfsunrise.com",
        "protocol": "https:",
        "host": "api.cdfsunrise.com",
        "hostname": "api.cdfsunrise.com",
        "pathname": "/restapi/search/list",
        "search": "",
        "hash": "",
    },
    "navigator": {
        "userAgent": UA,
        "platform": "Win32",
        "language": "zh-CN",
        "languages": ["zh-CN", "zh", "en"],
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "webdriver": False,
        "maxTouchPoints": 0,
    },
    "screen": {
        "width": 1536,
        "height": 864,
        "availWidth": 1536,
        "availHeight": 816,
        "colorDepth": 24,
        "pixelDepth": 24,
    },
}
```

不要无证据地堆砌 Canvas、WebGL、字体、AudioContext 等字段。先观察目标实际读取，再补最小宿主面。

### 8.3 时间和 event loop

本案例的 `LK` 直接调用在同步阶段完成，因此不需要模拟完整业务页面 timer。但 challenge 外链初始化仍必须在正确顺序执行。

如果目标 runtime 出现：

- Promise 未完成；
- timer 产生随机或时间字段；
- fetch/XHR 作为前置状态机；
- Worker/iframe 初始化；

再使用 `__iv8__.eventLoop.drainMicrotasks`、`drain` 或 `sleep`。不要在没有证据时盲目长时间 sleep。

## 9. WAF 自校验与安全暴露

### 9.1 为什么普通注入会卡死

直接修改原始内联脚本：

```javascript
window.__wafLK = LK;
```

可能让 WAF 在源码完整性检查处进入死循环。测试中甚至简单插入一个无关变量也可能让外链 runtime 在初始化后超时。

### 9.2 保留原始源码返回值

本案例使用两步策略：

1. 在原始闭包中插入最小导出语句；
2. 在执行内联脚本前，临时让 `Function.prototype.toString` 对目标外层函数返回原始源码。

注入内容：

```javascript
window.__wafLK = LK;
window.__wafL3 = L3;
window.__wafLf = Lf;
```

源码保护：

```javascript
(function () {
    var nativeToString = Function.prototype.toString;
    var originalSource = ORIGINAL_OUTER_SOURCE;
    Function.prototype.toString = function () {
        if (this && this.name === "Lblfpo") {
            return originalSource;
        }
        return nativeToString.call(this);
    };
})();
```

这里的原则是“保留原始源码观测结果”，不是关闭自校验。不要把这个补丁泛化成所有站点的固定模板：目标函数名、外层闭包和检查方式可能变化。

### 9.3 暴露后直接调用 LK

执行完 challenge 内联 WAF 后，检查：

```javascript
({
    lk: typeof window.__wafLK,
    l3: typeof window.__wafL3,
    lf: typeof window.__wafLf
})
```

期望：

```json
{"lk":"function","l3":"function","lf":"function"}
```

然后调用：

```javascript
window.__wafLK(
    "https://api.cdfsunrise.com/restapi/search/list",
    BODY_TEXT,
    "POST",
    2
)
```

返回值是带 `md5__1803` 的完整 URL，而不是只返回签名片段。保持完整 URL 可以避免 query 编码和 path 拼接被 Python 二次改变。

## 10. 外链 runtime 的两个 iv8 兼容点

本案例在 iv8 适配时遇到两个与算法本身无关的问题：

### 10.1 `Zi` 自校验常量

外链 runtime 会通过函数源码计算 `Zi`。在当前 WAF 版本中，原浏览器路径会得到一个用于后续除法/随机节奏的常量。iv8 的函数源码形状不同，会使它得到错误值并卡死。

在已确认只是 iv8 宿主源码差异的前提下，测试 harness 使用：

```javascript
function u1() {
    return Zi = 632, "5rGzyCeeHxhGk9";
}
```

这不是通用 WAF 绕过，也不是生产算法结论。每次只能在对照原始浏览器结果、确认失败点属于 iv8 兼容层后使用，并记录版本和原因。

### 10.2 `matchMedia` 高度分支

`wF` 中存在基于：

```javascript
matchMedia("(min-device-height: ...)")
```

的同步循环。在 iv8 默认媒体能力不足时可能永不收敛。测试 harness 对该循环的计时分支做了最小兼容修正，使 iv8 可以完成初始化。

原则：

- 不修改 `LK` 的算法输入；
- 不伪造服务端返回；
- 不把调试注入写入原始 frozen asset；
- 记录补丁仅属于 runtime compatibility patch；
- WAF bundle 版本变化后重新确认补丁是否仍适用。

## 11. Cookie 的关键发现

challenge 响应通常会通过 HTTP Set-Cookie 设置：

```text
acw_tc=...
```

iv8 执行 WAF 后还可能生成：

```text
ssxmod_itna=...
ssxmod_itna2=...
```

不能因为这些 Cookie 看起来像 WAF 状态就全部转发。多轮实测表明：

- `ssxmod_*` 是 iv8 环境生成的 runtime 状态；
- 将它们转给 requests 反而可能使签名状态不一致；
- 当前业务成功回放只需要沿用 challenge Session 的 `acw_tc`；
- 仍必须使用同一 Session，不能把 `acw_tc` 复制到另一个无关 Session。

安全的合并策略：

```python
def merge_acw_tc(session, cookie_header):
    for item in cookie_header.split(";"):
        if "=" not in item:
            continue
        name, value = item.strip().split("=", 1)
        if name == "acw_tc":
            session.cookies.set(
                name,
                value,
                domain="api.cdfsunrise.com",
                path="/",
            )
```

这条结论是本案例的实证结果，不代表所有 Aliyun WAF 站点都可以忽略 `ssxmod_*`。

## 12. requests 回放顺序

完整顺序必须是：

```python
session = requests.Session()

challenge = session.post(
    API_URL,
    headers=HEADERS,
    data=BODY_TEXT.encode("utf-8"),
    timeout=30,
)

signed_url, iv8_cookie_header = generate_signed_url(
    challenge.text,
    challenge.cookies.get("acw_tc", ""),
)

merge_acw_tc(session, iv8_cookie_header)

response = session.post(
    signed_url,
    headers=HEADERS,
    data=BODY_TEXT.encode("utf-8"),
    timeout=30,
)
```

注意：

- 不重新 `json.dumps` 一个可能改变字段顺序的 body；
- 不使用 `json=REQUEST_BODY` 替代已验证的 body 字节；
- 不在签名后修改 URL 的 query 编码；
- 不把浏览器抓到的旧 Cookie 与本轮 challenge 混合；
- 不以 HTTP 200 作为唯一成功条件。

## 13. 失败诊断表

### 13.1 首次响应不是 challenge HTML

检查：

- 是否用了不同的 API path；
- method 是否为 POST；
- body 是否为空或 JSON 格式改变；
- 服务端是否暂时直接返回 405/403；
- 是否需要访问页面入口先建立边缘 Cookie。

不要直接使用历史 `challenge.html` 当作长期 token。challenge 可能绑定时间、IP、UA 或 Set-Cookie。

### 13.2 iv8 执行外链后卡死

按顺序排查：

1. 是否执行了错误版本的外链脚本；
2. `Zi` 源码校验是否因为 iv8 函数源码差异失败；
3. `matchMedia` 是否进入同步死循环；
4. DOM 中是否保留了 WAF 读取的原始 script source；
5. `location`、`navigator`、`screen` 是否为空；
6. 是否重复执行初始化脚本。

不要首先给所有函数加 wrapper。包装本身可能是卡死原因。

### 13.3 `window.__wafLK` 是 undefined

检查：

- 导出语句是否插入了正确的闭包；
- 是否执行的是 instrumented source；
- 是否在外层自调用之前插入；
- 目标函数名称是否真的是 `LK`；
- 是否因为 inline 脚本执行异常提前退出。

### 13.4 生成 URL 但服务端仍返回 HTML

检查优先级：

1. challenge `bd` 是否来自同一轮；
2. body 字节是否和传给 `LK` 的字符串一致；
3. URL 是否经过二次编码；
4. method 是否是大写 `POST`；
5. `acw_tc` 是否仍在同一个 Session；
6. 是否误传了 iv8 的 `ssxmod_*`；
7. UA 和 `navigator.userAgent` 是否一致；
8. WAF bundle 是否已更新。

### 13.5 返回 JSON 但 `code` 非 0

这通常已经越过 WAF，转为业务层问题。检查：

- body 字段；
- `pageNumber/pageSize`；
- `keys` 和 `sceneId`；
- 业务 headers；
- access token 或站点业务状态。

不要继续盲目修改 WAF 签名。

## 14. 为什么不直接做纯 Python 纯算

纯算需要移植：

- `L3()` 环境数组；
- challenge 初始化状态；
- `LS/LU/Li/Ln` 编码依赖；
- 动态 alphabet；
- 伪随机消耗顺序；
- body/URL/method 规范化；
- 版本变化后的兼容层。

MD5 本身不是难点。难点是所有输入必须和原始 WAF runtime 在同一轮一致。

当前 iv8 方案的价值是：

- 保留原始 WAF 算法，减少静态移植错误；
- 不依赖真实浏览器；
- challenge 每轮从服务端刷新；
- Python 只负责 HTTP Session 和业务回放；
- WAF bundle 更新时可以替换或重新提取资产。

只有在部署环境不能安装 iv8、需要极小运行时或必须审计全部算法时，才值得继续做纯 Python 纯算。

## 15. 可复用模板

未来遇到类似“首次 HTML challenge，成功后 URL 多一个长签名”的站点，可以按下面的顺序处理：

```text
A. 先确认 response content-type 和业务码
B. 保存 fresh challenge HTML 和 Set-Cookie
C. 区分业务 sign 与 WAF sign
D. 静态 AST 定位 wrapper -> signer -> encoder
E. 确定脚本执行顺序和同源 DOM 需求
F. 用 iv8 page.load 构造最小环境
G. 对外链 runtime 单独做宿主兼容诊断
H. 保护 Function.prototype.toString 原文，避免自校验误判
I. 从闭包导出已确认的 signer 入口
J. 将真实 URL/body/method 传给入口
K. 只合并已验证需要的 Cookie
L. requests 同 Session 回放
M. 用 content-type、业务 code、结构化数据验收
N. 至少用两个 fresh challenge 重复验证
```

## 16. 案例文件

本案例对应：

- 案例脚本：`references/cases/js-challenges/cdfsunrise-md5-1803.py`
- frozen inline WAF：`references/cases/js_reverse_cache/cdfsunrise-md5-1803/01-aliyunwaf_6a6f5ea8.js`
- frozen external WAF：`references/cases/js_reverse_cache/cdfsunrise-md5-1803/02-psk8uqfi.decoded.js`
- 当前项目正式入口：`pure_main.py`
- 当前项目 iv8 封装：`iv8_signer.py`

案例脚本运行时产生的 challenge HTML 写入当前工作目录的 `js_reverse_cache/`，不会写入 skill 目录。动态 URL、Cookie、签名和业务响应也不会作为 frozen asset 保存。

## 17. 验收清单

- [ ] 只有一个 Session 负责 challenge 和业务回放；
- [ ] challenge HTML 是本轮 fresh 响应；
- [ ] 外链和内联 WAF 版本匹配；
- [ ] `LK` 入口和参数顺序已经证据确认；
- [ ] body 字节在签名和回放之间不变；
- [ ] `acw_tc` 来源明确；
- [ ] 没有混入旧 Cookie 或另一个浏览器 baseline；
- [ ] iv8 输出的签名 URL 非空；
- [ ] 最终 content type 是 JSON；
- [ ] `responseHead.isSuccess=true`；
- [ ] `responseHead.code=0`；
- [ ] 至少第二轮 fresh challenge 也成功；
- [ ] 没有把动态凭证写入源码、skill 或公开报告。
