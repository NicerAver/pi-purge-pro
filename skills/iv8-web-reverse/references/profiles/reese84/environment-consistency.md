# Environment Consistency

## 1. 单一基线原则

Reese84 的服务端评分可同时看到 HTTP 身份和 `p` 中的 JS 环境。局部字段“看起来像真的”不够，跨层一致性更重要。

为每条真实链声明：

```text
BROWSER_BASELINE = chrome-150-windows-zh-CN
HTTP_TRANSPORT = curl_cffi chrome142 (closest available)
ENV_SAMPLE = js_reverse_cache/browser_env.json
CANVAS_SAMPLE = js_reverse_cache/canvas_capture.json
```

其它 Firefox、Camoufox、另一台机器或旧抓包只标为 diagnostic，不写入最终 environment。

## 2. 一致性矩阵

| 维度 | HTTP 层 | JS 层 | 必须一致 |
|---|---|---|---|
| 浏览器版本 | User-Agent、sec-ch-ua、TLS profile | userAgent、appVersion、userAgentData | UA/CH/JS 同家族同主版本；TLS 取工具可用的最近同家族 profile 并记录差距 |
| OS | sec-ch-ua-platform、UA | platform、UA、字体、WebGL | Windows/macOS/Linux |
| 语言 | Accept-Language | language、languages | 顺序和主语言 |
| 时区 | 无直接 header | Date、Intl、timezone config | 地理语义合理 |
| 窗口 | 无 | screen/window/DPR | 同一显示器样本 |
| GPU | TLS 无关 | WebGL vendor/renderer/parameters | 同一设备样本 |
| Canvas | 无 | pixels、PNG/JPEG/WebP | 同一引擎/字体/尺寸 |
| Cookie | Cookie header | document.cookie | HttpOnly 可见性正确 |

## 3. UA 与 Client Hints

典型错误：

```text
HTTP UA: Chrome/150
sec-ch-ua: Chromium/124
JS UA: Chrome/150
curl impersonate: firefox135
```

即使 solution POST 返回 token，最终 replay 仍可能 403。

优先从成功浏览器请求复制 Client Hints 结构，不只复制 UA：

```python
BASE_HEADERS = {
    "User-Agent": CHROME_UA,
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Accept-Language": "zh-CN,zh;q=0.9",
}
```

品牌必须与实际 baseline 对齐。Edge 样本使用 `Microsoft Edge` 和 `Edg/...`；不要给 Google Chrome token 临时拼 Edge Client Hint。

## 4. iv8 宿主泄漏

`window.__iv8__` 是强异常信号。挑战可能通过：

- `Object.getOwnPropertyNames(window)`
- `Object.getOwnPropertyDescriptor(window, name)`
- iframe realm 对比
- 函数 source/native 外观

发现宿主对象后进入不同 `p` 分支并不一定抛异常。

推荐顺序：

```javascript
let __iv8Host = window.__iv8__;
delete window.__iv8__;
installCoreBridge(__iv8Host); // error, fetch/XHR, iframe and environment guards
__iv8Host.page.load(__iv8Host.data.snapshot);
installPostLoadPatches(__iv8Host); // only patches that require the loaded DOM
```

注意：必须在 `page.load` 前隐藏宿主并安装核心 bridge，否则页面内同步脚本可能已经观察宿主或发出未被桥接的请求。只有确实依赖已加载 DOM 的 patch 才允许放到 post-load 阶段。

动态 iframe 也要处理：

```javascript
function patchRealm(realm) {
    if (!realm || realm === window) return;
    try { delete realm.__iv8__; } catch (error) {}
}
```

不要删除正常 Chrome 特征，如 `window.chrome`、`navigator.userAgentData`、`navigator.connection`、`deviceMemory`，除非 baseline 确实没有。

## 5. iframe 生命周期

空 iframe 插入 DOM 后，浏览器会异步触发 load。iv8 可能不自动发生，导致 Reese 环境探测未完成。

修补目标：

- 观察 `appendChild`、`insertBefore` 等插入点。
- 仅对新插入的 iframe。
- patch iframe realm 后排队 dispatch `load`。
- 不重复派发。

不要同步立即 dispatch；使用 timer/microtask 模拟异步边界。

## 6. Canvas

Canvas 必须把以下内容视为一组：

- 绘制操作顺序。
- canvas width/height。
- `getImageData(x,y,w,h)` 的精确 RGBA。
- `toDataURL()` PNG。
- `toDataURL('image/jpeg')`。
- `toDataURL('image/webp')`。
- 字体可用性和 `measureText`。

高风险反模式：

- 所有尺寸都返回同一张固定 PNG。
- 600x160 canvas 返回 240x60 图片。
- pixels 来自合成噪声，PNG 来自另一浏览器。
- PNG 来自 Firefox，UA/WebGL 来自 Chrome。
- 只伪造 data URL prefix 或长度。

按调用尺寸映射：

```javascript
if (format === 'image/png' && width === 600 && height === 160) return baseline.png;
if (format === 'image/png' && width === 4 && height === 4) return baseline.transparent4;
if (format === 'image/png' && width === 5 && height === 5) return baseline.pattern5;
```

`getImageData` 仅覆盖已采集的精确坐标，其它调用尽量走 iv8 native fallback。

### 采集步骤

在唯一 baseline 浏览器中执行与 challenge 相同的绘制顺序，不使用另一段“相似 demo”：

1. 从运行日志或断点记录 canvas 尺寸、字体、fillStyle、globalAlpha、composite、path 和调用顺序。
2. 在 baseline 页面创建相同尺寸 canvas，逐条重放。
3. 导出 PNG/JPEG/WebP 完整 data URL、关键 `getImageData` RGBA、`measureText` 和 `document.fonts.check`。
4. 保存为 `js_reverse_cache/canvas_capture.json`，附 baseline 名称、UA、时间和绘制脚本 hash。
5. 解码 PNG/JPEG header 验证实际宽高，不只比较 base64 长度。
6. 用固定输入在浏览器和 iv8 各执行一次，逐项比较 hash/像素/尺寸。

建议 schema：

```json
{
  "baseline": "chrome-150-windows",
  "captureScriptSha256": "...",
  "png": "data:image/png;base64,...",
  "jpeg": "data:image/jpeg;base64,...",
  "webp": "data:image/webp;base64,...",
  "transparent4": "data:image/png;base64,...",
  "pattern5": "data:image/png;base64,...",
  "firstPixels": [],
  "secondPixels": []
}
```

## 7. WebGL

最少采集：

- unmasked vendor/renderer。
- `VENDOR`、`RENDERER`、`VERSION`、`SHADING_LANGUAGE_VERSION`。
- texture/renderbuffer limits。
- uniform/vector limits。
- supported extensions。

不要只改 vendor/renderer，却保留与 GPU 不可能共存的 limits/extensions。

## 8. DOM Geometry

iv8 没有完整 layout engine。只在调用日志证明 Reese 使用时补：

- `offsetWidth/Height`
- `clientWidth/Height`
- `getBoundingClientRect`
- font metrics

用 CSS width/height、style 和元素属性计算可解释值，不用随机值。随机 layout 会让同一 payload 内部自相矛盾。

## 9. Function Native 外观

通过 `host.wrapNative` 包装关键 patch。不要全局把任意函数 `toString` 都强制成同一个 native 字符串；保留函数名和基础 source 结构。

检查：

```javascript
Function.prototype.toString.call(patchedFunction)
Object.getOwnPropertyDescriptor(prototype, 'patchedName')
patchedFunction.name
patchedFunction.length
```

## 10. Cookie 可见性

Python session 可以持有 HttpOnly：

- `visid_incap_*`
- `incap_ses_*`
- `nlbi_*`

但页面 `document.cookie` 通常不能读取 HttpOnly。snapshot 不应把所有 session Cookie 伪造成普通 Set-Cookie 注入页面。

`reese84` 是否可见以实际 Set-Cookie 属性和浏览器样本为准。`old_token` 必须由 challenge 自己读取/构造，不要手工改 envelope。

## 11. 最小差分实验

每轮只改变一个维度：

1. UA + Client Hints + transport。
2. 宿主对象可见性。
3. iframe lifecycle。
4. Canvas 同源映射。
5. WebGL。
6. DOM/font。

保存每轮：challenge hash、`p` 长度、`p` decoded prefix、token 长度、最终 replay 状态。`p` 长度变化用于证明分支变化，不作为正确性标准。

### `p` 的安全观察

`p` 通常是 Base64。先做无损外层解码，不假设内部 schema：

```python
p = envelope["solution"]["interrogation"]["p"].strip()
padded = p + "=" * (-len(p) % 4)
if re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", p):
    raw = base64.b64decode(padded, validate=True)
elif re.fullmatch(r"[A-Za-z0-9_-]+", p):
    raw = base64.urlsafe_b64decode(padded)
else:
    raise ValueError("p is neither strict Base64 nor Base64URL")
summary = {
    "encoded_length": len(p),
    "decoded_length": len(raw),
    "prefix_hex": raw[:64].hex(),
    "prefix_repr": repr(raw[:64]),
    "ascii_strings": [
        item.decode("latin1")
        for item in re.findall(rb"[ -~]{4,}", raw[:4096])[:30]
    ],
}
```

保存 summary，不修改 `p` 后提交。看到 `bin1` 只记录容器特征；没有字段级证据时不要声称已解密或知道内部含义。
