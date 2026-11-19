# 网易易盾滑块与智能无感流程

来源参考案例：网易易盾滑块逆向项目，以及当前智能无感 `type=5` 的 Python + iv8 在线复现。

## 文件角色

1. `1.请求测试.py`：固定参数请求 `https://c.dun.163.com/api/v3/get`，用于观察 JSONP 响应结构。
2. `2.获取cb值.js`：补最小浏览器环境并加载 NECaptcha 源码，导出动态 `get_cb()`。
3. `3.携带动态cb值获取验证码资源.py`：用动态 `cb` 请求 `api/v3/get`，提取 `bg/front/token`。
4. `4.获取data参数.js`：基于 `token`、轨迹和滑动距离生成 `/api/v3/check` 的 `data` 参数。
5. `5.计算验证码滑动距离.py`：下载 `front/bg`，用 `ddddocr` 计算滑动距离。
6. `trace_data.py`：用贝塞尔曲线生成 `[x, y, time, 1]` 轨迹。
7. `6.网易易盾.py`：整合 get、OCR、轨迹、data 生成和 check 请求。

## 请求 get

接口：`https://c.dun.163.com/api/v3/get`。

关键请求头：

1. `Referer: https://dun.163.com/`
2. `Sec-Fetch-Dest: script`
3. `Sec-Fetch-Mode: no-cors`
4. `Sec-Fetch-Site: same-site`
5. `User-Agent` 和 `sec-ch-ua` 保持同一浏览器版本。

关键参数：

1. `referer=https://dun.163.com/trial/jigsaw`
2. `zoneId=CN31`
3. `dt`、`irToken`、`id`、`fp` 来自站点初始化材料，不能长期假设固定有效。
4. `type=2` 表示滑块。
5. `version=2.28.5`、`loadVersion=2.5.3`、`width=320`、`iv=4` 与样本保持一致。
6. `cb` 由 `2.获取cb值.js` 的 `get_cb()` 生成。
7. `callback` 由 `4.获取data参数.js` 的 `get_callback()` 生成，形如 `__JSONP_<random>_1`。

响应是 JSONP，解析时不要写死 callback：

```python
json_data = json.loads(re.findall(r'__JSONP_.*?_\d\((.*?)\)', response.text)[0])
```

提取字段：

```python
bg = json_data['data']['bg'][0]
front = json_data['data']['front'][0]
token = json_data['data']['token']
```

## 计算距离

下载 `front` 和 `bg` 后，用：

```python
ocr = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
result = ocr.slide_match(target_bytes=front_bytes, background_bytes=bg_bytes, simple_target=True)
slide_distance = int(result['target'][0])
```

注意：

1. `front` 是滑块图，`bg` 是背景图。
2. OCR 前先检查响应是否为图片，不要把错误页写入 `front.jpg/bg.jpg`。
3. check 阶段 `slide` 传原始识别距离；轨迹终点可以按案例使用 `slide_distance + 5`。

## 生成轨迹

`trace_data.py` 的 `BezierTrajectory.generate_trajectory(slider_x)`：

1. 起点 `[4, 0]`。
2. 终点 `[slider_x + 10, 2]`。
3. 点数约为 `slider_x + 25`。
4. 每个点的时间从 `132` 开始，每步增加 `50-80ms`。
5. 输出点格式：`[int(x), int(y), time, 1]`。

整合脚本中使用：

```python
trace = BezierTrajectory().generate_trajectory(slide_distance + 5)
```

## 生成 data

`4.获取data参数.js` 的核心入口：

```js
get_params_data(trace, token, slide)
```

内部逻辑：

1. 对每个轨迹点执行 `window._0x3855dc(token, point + '')`。
2. 用 `window._0x148293.sample(trace_data, 50)` 对轨迹编码结果采样。
3. `p` 使用 `slide / 320 * 100`，再做 token 相关编码。
4. `f` 使用 `window._0x148293.unique2DArray(trace, 0x2)` 去重后摘要编码。
5. `ext` 使用 `1,trace_data.length` 编码。

最终返回紧凑 JSON 字符串：

```json
{"d":"...","m":"","p":"...","f":"...","ext":"..."}
```

关键边界：

1. `token` 必须来自当前 `api/v3/get`。
2. `trace` 必须由当前滑动距离生成。
3. `slide` 用当前 OCR 识别距离。
4. 不要复用上一轮 `data`。

## 请求 check

接口：`https://c.dun.163.com/api/v3/check`。

关键参数：

1. `referer=https://dun.163.com/trial/jigsaw`
2. `zoneId=CN31`
3. `dt`、`id` 与当前站点材料一致。
4. `token` 来自同一次 get。
5. `data` 来自 `get_params_data(trace, token, slide)`。
6. `width=320`、`type=2`、`version=2.28.5`、`loadVersion=2.5.3`、`iv=4`。
7. `cb` 每次用 `get_cb()` 重新生成。
8. `callback` 每次用 `get_callback()` 重新生成。

## 推荐封装

标准类结构：

1. `__init__` 编译 `2.获取cb值.js` 和 `4.获取data参数.js`，初始化 headers/cookies/session。
2. `get_captcha_images_and_token()` 请求 get 并返回 `bg/front/token`。
3. `parse_slide(front_bytes, bg_bytes)` 返回滑动距离。
4. `send_verify(trace, slide_distance, token)` 生成 `data` 并请求 check。
5. `main()` 串联整轮流程。

## 滑块 `type=2` + Python/iv8 全量 bootstrap

当 `api/v3/get` 返回 `type=2`、图片为 `bg/front`、最终 `api/v3/check` 为 `data={d,m,p,f,ext}`，且旧教程式 `ExecJS/2.获取cb值.js/4.获取data参数.js` 反复得到 `error=0,data.result=false,validate=""` 时，优先进入本分支。不要只因为 `data` 形状对、HTTP 200、token 匹配或轨迹长度像正样本就继续微调密文；当前 core 版本可能已变，反编译出的旧加密/采样细节很容易过期。

### 推荐请求链

同一 `curl_cffi.requests.Session` 和同一 iv8 context 内按顺序执行：

```text
load.min.js / initNECaptcha({ captchaType: 'JIGSAW', captchaId })
  -> api/v2/getconf
  -> current IR guardian /v4/j/up
  -> api/v3/get (type=2, bg/front/token)
  -> local gap detector
  -> official yidun slider DOM event state machine
  -> api/v3/check
```

关键约束：

1. `dt/zoneId/core/IR` 必须从本轮 `api/v2/getconf` 获取；`get` 和 `check` 使用同一个 `dt`。不要把教程、上一轮或浏览器缓存里的 `dt/fp/irToken` 写死。
2. 若 `getconf.data.ir.enable=1`，通过当前 IR SDK 的 `createNECaptchaGuardian(...).getToken(...)` 或等价官方路径拿 `/v4/j/up` 返回的 `tk`，再作为 `api/v3/get` 的 `irToken`。实测真实 IR token 不是唯一根因，但不能因此省略同轮 IR。
3. 让官方 `load.min.js + core-optimi` 在 iv8 中完成 `get/check` 和 `data` 生成；Python 只负责 Session、脚本/XHR/JSONP bridge、图片识别和事件输入。旧 `4.获取data参数.js` 可用于定位字段语义，不应作为最终通过路径。
4. 动态 `<script src>`、JSONP、XHR、图片加载都走同一个 Python Session，并把响应注回 iv8；补齐 `onload/onreadystatechange`、`naturalWidth/naturalHeight/complete` 等生命周期。
5. 最终交付仍是 Python + iv8 协议脚本，不启动 Playwright/Selenium/CDP 页面驱动。浏览器只用于取证和正样本对照。

### `type=2` data 与关键明文

当前官方 core 可生成五字段：

```json
{"d":"...","m":"","p":"...","f":"...","ext":"..."}
```

诊断时可在本地 iv8 内临时 hook `xorEncode/AES` 的入参，但不要落盘 token、validate、Cookie、cb、fp 或完整密文。可保留的非敏感聚合：

1. `d`：采样后的轨迹编码串，轨迹点形如 `x,y,t,1`。
2. `p`：核心公式为 `parseInt($jigsaw.style.left, 10) / this.width * 100 + ''` 后再 token-bound 编码；如果明文是 `NaN`，服务端通常返回 `result=false`。
3. `f`：`unique2DArray` 后的统计摘要。
4. `ext`：常见明文为 `1,<trace_len>`。
5. `m`：当前滑块分支为空字符串；不要套无感/障碍躲避的 `m/p/ext` 语义。

### iv8 DOM 布局坑

易盾 core 会在 mousedown/move/up 中读取滑块和拼图 DOM 的样式与布局。iv8 的默认 DOM/layout 不完整，常见失败不在加密，而在 `$jigsaw.style.left` 进入 `p` 前已经错了。

必须补齐：

1. `window.getComputedStyle`：不要依赖 iv8 自带空实现或异常；返回元素 `style` 中的 `left/top/display/transform` 等已设置值，并提供 `getPropertyValue`。
2. `.yidun_bgimg/.yidun_bg-img` 返回 `320x160`，`.yidun_jigsaw` 返回真实拼图尺寸约 `60x158` 或与前景图一致，`.yidun_slider` 返回约 `40x40`。
3. `offsetLeft/offsetTop/offsetParent/getBoundingClientRect()` 需要随 `style.left/top/bottom` 动态变化；仅写固定 rect 会让 core 的 drag 状态和 `p` 偏离。
4. iv8 事件冒泡/祖先委托可能不完整。加载 core 前记录 `addEventListener/removeEventListener`，派发 mousedown/mousemove/mouseup 时沿元素祖先路径调用已注册监听器，让官方 `onMouseDown/onMouseMove/onMouseUp` 自己记录轨迹和生成 `data`。
5. 先等待 `onReady === true` 且 `.yidun_slider` 存在，再按 `challenge.waitTime` 或至少几百毫秒后拖动。只等 DOM 出现可能早于 IR/get/图片状态完成。

已验证失败模式：iv8 `getComputedStyle` 返回异常或空值时，core 在 mousedown 读取 `$slider` CSS `left` 得到 `NaN`，进而 `drag.startLeft=NaN`，最终 `p` 明文为 `NaN`，`check` 返回 `error=0,result=false,validate=""`。修复 `getComputedStyle` 和 layout 后，`p` 应变成类似 `37.8125` 的百分比字符串。

### 缺口识别与拖动坐标映射

`type=2` 至少分清三套坐标：

1. 模型识别出的背景缺口左边界 `gap_x1`，坐标系是 `320x160` 背景图。
2. 鼠标/滑块相对位移 `dragX`，官方 trace 中常记录为 `clientX - startX`。
3. `$jigsaw.style.left`，这是 `p` 的直接来源，服务端拿它与真实 `gap_x1` 对比。

当 `ddddocr(simple_target=True/False)` 对同一图差几十像素，或本地 `check` 始终 `result=false` 但官方 data 结构正常时，先换独立滑块模型/边缘方法验证缺口。已验证可用的泛化策略：用 ONNX 滑块检测模型识别背景缺口 box，按前景图左侧透明边距约 `3px` 得到旧式距离 `distance = gap_x1 - 3`。

在官方 iv8 bootstrap 中，不能默认把 `distance` 直接作为拖动终点。一次已验证的当前布局关系：

```text
jigsawEnd = dragX + 23
23 = (jigsawOW 60 - sliderOW 40) + piece_left_margin 3
目标 jigsawEnd = gap_x1 = distance + 3
所以 dragX = gap_x1 - 23 = distance - 20
```

验收时打印或 hook 聚合值验证公式，而不是盲扫坐标：

```text
distance=118, gap_x1≈121, dragX=98, jigsawEnd=121,
p明文='37.8125' == 121/320*100
```

这个 `-20` 不是平台永久常量；它来自当前 DOM 尺寸和前景透明边距。若 `jigsawOW/sliderOW/piece_margin` 变化，重新用公式或正样本聚合校准。不要用大随机偏移掩盖坐标系错误，修复后轨迹终点只做小范围抖动。

### 单变量诊断顺序

1. 固定同轮 `getconf -> IR -> get -> check`，确认 `get.token == check.token`。
2. 若旧反编译 JS 失败，先切官方 `load.min.js + core` iv8 bootstrap；不要同时改 fp、轨迹、TLS、IR 和识别。
3. 若官方 core 也 `result=false`，hook pre-AES 明文看 `p` 是否 `NaN`、`ext` 是否为 `1,<trace_len>`、轨迹点是否真实增长。
4. 若 `p=NaN`，先修 iv8 `getComputedStyle`、`offset*`、`getBoundingClientRect()`。
5. 若 `p` 有值但与缺口不一致，计算 `jigsawEnd = p * width / 100`，与模型 `gap_x1`、trace `dragX` 做差，校准 `dragX -> jigsawEnd` 映射。
6. 若 `p` 与缺口一致仍失败，再比较 `d/f/ext` 聚合、等待时间、事件 flag 和传输/headers。禁止从多变量组合成功直接声称某一项是根因。

### 成功判据

必须同时满足：

1. `/v4/j/up` HTTP `200` 且业务 `code=200`，返回本轮可用 `tk`（若当前配置启用 IR）。
2. `/api/v3/get` HTTP `200`、`error=0`、`type=2`，返回本轮 token、bg/front。
3. 缺口识别得到可信 `gap_x1`，`p` 明文对应的 `jigsawEnd` 与 `gap_x1` 在容差内。
4. `/api/v3/check` HTTP `200`，JSONP 内 `error=0` 且 `data.result=true`。
5. `check.data.token == get.data.token`。
6. `validate` 非空才算滑块 demo 通过；至少再跑一轮 fresh browser-free 本地验证。不要用 HTTP 200、token 匹配、`data` 五字段形状、轨迹点数或 validate 长度单独声称成功。

## 文字点选 `type=3` + Python/iv8

用于 `https://dun.163.com/trial/picture-click`、`api/v3/get` 返回 `type=3`、`bg` 为单张 `320x160` JPEG、`front` 为按点击顺序排列的目标字、最终 `api/v3/check` 的 `data` 为 `d/m/p/ext` 的嵌入式文字点选分支。这个分支看起来像普通图片点选，但同样依赖官方 core 的同轮状态、动态 `cb`、`token` 绑定和事件状态机，不要把它当成纯 OCR 题。

### 当前请求链

同一 `curl_cffi.requests.Session` 和同一 iv8 context 内按顺序执行：

```text
load.min.js / initNECaptcha({ captchaType: 'POINT_CLICK', captchaId })
  -> api/v2/getconf
  -> current IR guardian /v4/j/up
  -> api/v3/get (type=3, bg/front/token)
  -> 按 front 顺序派发 3 次点击
  -> official yidun point-click event state machine
  -> api/v3/check
```

关键约束：

1. `getconf` 的 `dt/zoneId/ir`、`/v4/j/up` 返回的 `tk`、`api/v3/get` 的 challenge token、图片、官方 core 生成的 `cb/data` 和最终 `check` 必须同一轮。
2. `api/v3/get` 要求动态 `cb`；复用固定 `cb` 会返回 `error=100, msg=param check error`。
3. `front` 为目标字串，顺序即点击顺序，常见长度与字数一致；必须点满对应次数后才会触发 `check`。
4. `type=3` 的 `check.data` 不是 OCR 结果本身，而是官方 core 采样、加密/随机封装后的 `d/m/p/ext`。
5. `get/check` 的 `token` 必须完全相同；失败后服务端会自动刷新到下一轮 `get`，不要把新轮 `token` 混回旧轮实验。

### `type=3` 的 data 与点击状态机

当前官方 core `2.28.5` 的文字点选数据形状：

```json
{"d":"","m":"...","p":"...","ext":"..."}
```

已验证的语义边界：

1. `d` 在当前分支为空字符串。
2. `m` 是采样后的轨迹/行为编码，来自点击与移动过程的聚合，不要手写固定密文。
3. `p` 由每个点击点的坐标与时间经 token 绑定编码后再封装；服务端更关心同轮点击序列和点击落点，而不是单个点的外观。
4. `ext` 与点击次数、轨迹长度绑定，当前样本中常见为点击计数和轨迹长度的组合编码。
5. `pointsStack.length === MAX_POINTS` 时才触发 verify，`MAX_POINTS` 与 `front` 字数一致。

已确认的点击行为：

1. 必须按 `front` 顺序点击，点错顺序会直接进入失败分支。
2. 连续 3 个不同坐标点击后触发 `/api/v3/check`。
3. 易盾不依赖 `isTrusted` 作为硬门槛，`dispatchEvent` 事件也会被核心记录为点击点。
4. 记录点位时，核心使用图片容器的 `getBoundingClientRect()` 做 `clientX-bgRect.left` 一类的相对坐标计算。
5. 失败响应通常是 `error=0, msg="ok", data.result=false, validate=""`，这说明协议链路正常但坐标/顺序不对。
6. 失败后会自动刷新到新一轮 `get` 和新图片，前一轮 `token` 立即失效。

### iv8 运行后端

推荐让当前官方 `load.min.js`、core 和 IR SDK 在 iv8 中运行，而不是把旧教程的大段混淆函数复制成固定 ExecJS 文件：

1. 用一个 `curl_cffi.requests.Session` 下载 `load.min.js` 和动态资源，并发送 `up/get/check`。
2. 动态 `<script src>`/JSONP 通过 Python bridge 获取，在 iv8 主世界执行；执行后补齐对应 `onload/onreadystatechange` 生命周期。
3. XHR 的 `open/setRequestHeader/send` 桥接到同一个 Python Session，真实响应通过 `ctx.add_resource` 注回 iv8。
4. IR SDK 依赖 `MessageChannel`。iv8 缺失时用 `__iv8__.wrapNative` 补最小双端口调度器，保持 `port1/port2/onmessage/postMessage` 语义。
5. iv8 事件冒泡/祖先委托可能不完整。加载 core 前记录 `addEventListener/removeEventListener` 注册，把同坐标事件沿元素祖先路径交给易盾已经注册的监听器；仍由官方 `handleControlClick -> verifyCaptcha` 生成 `data`，不要直接伪造最终密文。
   - **事件对象必须手工构造**（`new MouseEvent` 派发后 `target` 为空，core `onClick` 不认，点击后 `pointsStack` 不增长、`check` 不发）。已验证做法：手工构造含 `type/target/srcElement/currentTarget/clientX/clientY/pageX/pageY/button/buttons/isTrusted/preventDefault/stopPropagation/stopImmediatePropagation` 的普通对象，从 `.yidun_bgimg` 起沿 `parentNode` 链（最后到 `window`）逐级调用注册表里 `active && type 匹配 && target 相同` 的监听器，并用 `__iv8__.input.dispatchMouseEvent` 双发（可信事件 + 注册表冒泡各一次）。
   - 点选组件 `onClick` 逻辑：读 `$bgImg.getBoundingClientRect()` 的 `left/top` → `addPoint({left: clientX-left, top: clientY-top})` → 创建 `yidun_icon-point yidun_point-N` 元素 append 到 bgimg → `pointsStack.push({el, coord: xorEncode(token, [round(x), round(y), now-beginTime])})` → `shouldVerifyCaptcha()`。`pointsStack.length === MAX_POINTS` 时触发 `data={d:'', m:sample(traceData).join(':'), p:coords.join(':'), ext:xorEncode(token, clickCounts+','+traceData.length)}`。`MAX_POINTS` 初始 0，`get` 响应后设为 `front` 字数。
6. iv8 没有完整布局计算。对文字点选，需要至少补齐 `.yidun`、`.yidun_panel`、`.yidun_bgimg`、`.yidun_bg-img` 的尺寸和 `getBoundingClientRect()`，否则点击坐标会偏移，check 往往只返回 false。
   - **必须实例级 `Object.defineProperty`**（在具体元素上定义 `offsetWidth/offsetHeight/offsetLeft/offsetTop/getBoundingClientRect`），不能改 `Element.prototype`——prototype 级补丁在 iv8 中不生效，`$el.offsetWidth` 仍为 0。
   - **`check.width` 来自 `.yidun` 根元素 `$el.offsetWidth`**（core `getWidth()` 来源）：根元素补 `offsetWidth=320`、`offsetHeight=200`；`.yidun_bgimg`/`.yidun_bg-img` 补 `offsetWidth=320`、`offsetHeight=160`、`offsetLeft=0`、`offsetTop=0`、`getBoundingClientRect() → {left:0,top:0,right:320,bottom:160,width:320,height:160}`。漏补根元素 → `check.width=0` → `error=100 param check error`（skill 已记录此坑，但根元素来源此前未写明）。
7. 先等待 `onReady === true` 且点选面板已存在，再发送行为事件。只等 DOM 出现会早于 IR/get 回填，导致不发 `check`。

### 单变量诊断结论

已验证的最小控制实验：

| 保留项 | 唯一替换项 | 服务端结果 |
| --- | --- | --- |
| 同轮 Session、IR、get token、core data、点击序列、传输 | 固定错误坐标 | `error=0, result=false` |
| 其它项不变 | 使用官方 core 生成的动态 `cb` 和点击序列 | `error=0, result=true` |

因此文字点选分支遇到 `result=false` 时，优先检查点击顺序、点击次数、`front` 是否同轮、`check.width` 是否为 `320`、以及点位是否真正落在图片容器内，不要同时改指纹、IR、TLS 和轨迹。

### 成功判据

必须同时满足：

1. `/v4/j/up` 业务 `code=200` 并返回非空 `tk`。
2. `api/v3/get` 返回 `error=0`、`type=3` 和本轮 token。
3. `front` 对应的点击序列按顺序输入，且点击点数达到 `MAX_POINTS`。
4. `api/v3/check` 返回 `error=0` 且 `data.result=true`。
5. `check.data.token == get.data.token`。
6. `validate` 非空。不要用 HTTP `200`、`error=0`、token 匹配或 `data` 五字段形状单独声称成功。

## 智能无感 `type=5` + Python/iv8

用于 `https://dun.163.com/trial/sense`、`api/v3/get` 返回 `type=5`、`bg=[null,null]`，且最终 `api/v3/check` 的 `data` 为 `d/m/p/ext` 的智能无感分支。验证码状态机和成功判据仍由本 skill 负责；用户明确指定 Python + iv8 时，由 `iv8-web-reverse` 提供 JS 执行后端。

### 当前请求链

同一 Python Session 和同一 iv8 context 内按顺序执行：

```text
load.min.js
  -> api/v2/getconf
  -> ir.<current>.js / createNECaptchaGuardian(...).getToken(...)
  -> ir-sdk /v4/j/up
  -> api/v3/get (type=5)
  -> mouseover/mousemove/click telemetry
  -> api/v3/check
```

1. 每轮重新下载或确认当前 `load.min.js`，不要长期写死 core/IR 资源版本。
2. `api/v2/getconf` 返回 `dt`、`zoneId`、API 地址、core 资源和 IR 配置。已验证样本为 `loadVersion=2.5.4`、core `2.28.5`、IR `2.0.13`，但运行时仍以 `getconf` 为准。
3. 当前 IR UMD 全局入口是 `createNECaptchaGuardian`。它根据 `getconf.data.ir` 创建实例，动态生成 `/v4/j/up` 的 `{p,v,vk,n,d}`；`n` 是本轮 UUID，`d` 是环境/行为收集密文。
4. `/v4/j/up` 返回的 `tk` 才是当前 `api/v3/get` 的 `irToken`。禁止复用教程或上一轮的 `irToken/d`。
5. `api/v3/get` 必须携带同轮 `dt/fp/cb/irToken`；成功响应包含 `type=5` 和 verify token。
6. 当前 core 基于该 verify token 生成 `check.data`，随后请求 `api/v3/check`。`get/check` 的 token 必须完全相同。

`getconf` 请求和后续 `get/check` 的 `iv` 值可能不同，例如已验证链中 `getconf` 使用 `iv=5`，而 `get/check` 使用 `iv=4`；不要因为字段同名而强制统一。

### `type=5` 的 data

当前 core `2.28.5` 的无感数据形状：

```json
{"d":"","m":"...","p":"...","ext":"..."}
```

生成职责：

1. `mouseover` 记录 `beginTime`。
2. `mousemove` 记录控件内相对坐标与相对耗时，形成 `"x,y,time"` 点。
3. 每个点先执行 token 绑定的 `xorEncode(token, point)`。
4. `m` 对编码轨迹按当前 `SAMPLE_NUM` 采样后用 `:` 拼接，再经随机封装算法处理；当前 `SAMPLE_NUM=50`。
5. `p` 对点击点 `[x,y,elapsed,eventFlag]` 的 token 编码结果再做随机封装。
6. `ext` 对 `"1,<encoded_trace_length>"` 做 token 编码和随机封装。
7. 已验证无感样本的 `d` 为空字符串；不要套滑块的 `d/p/f/ext` 五字段结构。

随机封装意味着同一输入的 `cb/m/p/ext` 外观也可以变化。判断正确性看当前 core 的调用链和服务端最终响应，不比较固定密文。

### iv8 运行后端

推荐让当前官方 `load.min.js`、core 和 IR SDK 在 iv8 中运行，而不是把旧教程的大段混淆函数复制成固定 ExecJS 文件：

1. 用一个 `curl_cffi.requests.Session` 下载 `load.min.js` 和动态资源，并发送 `up/get/check`。
2. 动态 `<script src>`/JSONP 通过 Python bridge 获取，在 iv8 主世界执行；执行后补齐对应 `onload/onreadystatechange` 生命周期。
3. XHR 的 `open/setRequestHeader/send` 桥接到同一个 Python Session，真实响应通过 `ctx.add_resource` 注回 iv8。
4. IR SDK 依赖 `MessageChannel`。iv8 缺失时用 `__iv8__.wrapNative` 补最小双端口调度器，保持 `port1/port2/onmessage/postMessage` 语义。
5. iv8 `0.1.3` 的可信输入和普通 `dispatchEvent` 都不会向祖先冒泡，而易盾组件采用祖先事件委托。可在 core 加载前记录 `addEventListener/removeEventListener` 注册，把同坐标事件沿元素祖先路径交给易盾已经注册的监听器；仍由官方 `handleControlClick -> verifyIntelliCaptcha` 生成 `data`，不要直接伪造最终密文。
6. iv8 没有完整布局计算。点击前只给 `.yidun_intellisense` 实例补 `offsetWidth=320`；不要全局伪造所有元素尺寸。
7. 先等待 `onReady === true` 且 `.yidun_intelli-control` 已存在，再发送行为事件。只等待 DOM 出现会早于 IR/get 回填，导致不发 `check`。

最终交付应是 Python + iv8 协议脚本，不启动浏览器进程。浏览器样本只用于确认请求链和做正样本对照。

### 单变量诊断结论

已验证的最小控制实验：

| 保留项 | 唯一替换项 | 服务端结果 |
| --- | --- | --- |
| 同轮 Session、IR、get token、core data、轨迹、传输 | `check.width=0` | `error=100, msg=param check error` |
| 其它项不变 | `.yidun_intellisense.offsetWidth=320`，使 `check.width=320` | `error=0, data.result=true` |

因此 iv8 分支遇到 `error=100` 时，先检查 `check.width`，不要同时修改指纹、IR、轨迹和 TLS。失败的无感 `check` 可能触发官方 core 自动降级并再次 `get type=2` 滑块；这个后续 token 属于新 fallback 轮，不能拿来与刚才的 `type=5 check` 做同轮比较。

### 成功判据

必须同时满足：

1. `/v4/j/up` 业务 `code=200` 并返回非空 `tk`。
2. `api/v3/get` 返回 `error=0`、`type=5` 和本轮 token。
3. `api/v3/check` 返回 `error=0` 且 `data.result=true`。
4. `get.data.token == check.data.token`。
5. `validate` 允许为空或非空，不能把“非空 validate”单独作为成功条件。
6. 至少再跑一轮 fresh challenge；当前流程已用两个独立 token 连续在线成功。

建议保存最近一轮的 `up/get/check` 原始 URL、响应和 `onVerify` 结果，但每次运行覆盖或按轮隔离，避免把 fallback 或旧 challenge 混入成功证据。

## 障碍躲避 `type=6` + Python/iv8

用于 `https://dun.163.com/trial/avoid`、`api/v3/get` 返回 `type=6`、背景为 `320x240` JPEG、前景/目标条为 PNG，最终 `api/v3/check` 的 `data` 为 `d/m/p/ext` 的障碍躲避分支。该分支看起来像滑块，但不能套普通 `type=2` 的缺口距离、`d/f` 结构或线性轨迹。

### 请求链与同轮状态

同一 `curl_cffi.requests.Session` 内按顺序执行：

```text
load.min.js / initNECaptcha
  -> api/v2/getconf
  -> current IR guardian /v4/j/up
  -> api/v3/get (type=6)
  -> background JPEG + front PNG
  -> local target/obstacle detection
  -> A* avoid route + official type=6 event state machine
  -> api/v3/check
```

关键约束：

1. `getconf` 的 `dt/zoneId/ir`、`/v4/j/up` 返回的 `tk`、`api/v3/get` 的 challenge token、图片、官方 core 生成的 `cb/data` 和最终 `check` 必须同一轮。
2. 首轮 `/api/v3/get` 的 `token` 为空；刷新下一轮时携带上一轮 challenge token。每轮 `/get` 后清空本地 `irToken`，下一轮重新 `/v4/j/up`。
3. `/get` 在公开 demo 上可用空 `fp` 拿到 `error=0,type=6`，但这不证明 `/check` 能过。若浏览器正样本有非空 `fp`，只作为同轮证据，不要写入稳定代码。
4. `getconf` 常见 `iv=5`，`get/check` 常见 `iv=4`；同名字段不要强制统一。
5. `loadVersion/core/IR` 都以当前 `getconf/load` 为准。已见组合为 `loadVersion=2.5.4`、IR `2.0.13`、core `2.28.5`，但不能长期硬编码为协议事实。

### 图片识别与坐标系

`type=6` 背景是 `320x240`：上半部分 `320x160` 是活动画布，底部区域携带目标小图/目标条。页面提示通常是“拖动左下白色球/图标，躲避障碍击中”。

推荐识别流程：

1. 背景按场景建立参考图，先做同场景差分，再在上半区提取多个图标候选框。跨场景直接取中值会污染参考。
2. 底部目标小图与上半区候选做旋转不变匹配；目标可能旋转，不能只做未旋转模板匹配。
3. 目标框之外的候选是障碍框。规划时按球半径膨胀障碍，球心边界限制在画布内，禁止对角穿角。
4. 默认活动球尺寸约 `20x20`，起始球心约在左下 `(10,150)` 附近。路径终点应击中目标图标内部，而不是普通滑块缺口距离。
5. A* 生成后可做 obstacle-aware line-of-sight shortcut/resample；每条捷径都必须逐点检查“障碍框 + 球半径”碰撞，不能为了降点数让直线穿障碍。

### `type=6` 的 data 语义

当前 core 障碍组件在 `onMouseUp` 附近提交：

```json
{"d":"","m":"<aes(xorEncode(token, sampled ballTraceData joined by :))>","p":"<aes(xorEncode(token, finalCenterAndElapsed))>","ext":"<aes(xorEncode(token, mouseDownCountAndTraceLength))>"}
```

字段边界：

1. `d` 在当前分支为空字符串。
2. `m` 是关键字段，来自 `ballTraceData`，点形如 `[ballCenterX, ballCenterY, elapsedMs, isTrustedFlag]`，每个点先 `xorEncode(token, point + '')`，再按 core 采样并用 `:` 拼接后 AES/随机封装。
3. `p` 是最终球心和耗时，不是 `slide / width * 100`。
4. `ext` 常见为 `mouseDownCount,ballTraceData.length` 的 token-bound 编码。
5. `isTrusted` 映射需按 core 当前逻辑确认；已见 `null -> 0`、`true -> 1`、`false -> 2`，但服务端更看重完整事件状态机和球心坐标语义。
6. 随机封装导致同输入的 `cb/m/p/ext` 外观可变化。不要比较密文固定值，要比较最终服务端响应和非敏感聚合形状。

### iv8 运行后端与 DOM 布局坑

该分支建议让当前官方 `load.min.js`、IR 和 core 在受限本地 iv8 runtime 内运行；Python 负责 Session、图片、视觉、路径，官方 core 负责动态 `cb/xorEncode/aes` 和 type=6 事件状态机。

必须补齐的本地浏览器能力：

1. 动态 script/JSONP/XHR 走同一个 Python Session。`/v4/j/up` 的 IR source/body 必须在同一次 iv8 runtime 调用中生成并发送。
2. `MessageChannel`、script `onload/onreadystatechange`、图片 `naturalWidth/naturalHeight/complete/onload` 要有最小实现，确保 core onReady 和图片 ready 真正完成。
3. iv8 事件冒泡/祖先委托可能不完整。加载 core 前记录 `addEventListener/removeEventListener`，派发拖动事件时沿元素祖先路径调用已注册监听器，让官方 `onMouseDown/onMouseMove/onMouseUp` 自己生成 `data`。
4. 布局不能只补可见图片。当前 core 读取 `$bgImg` 时可能取 `.yidun_bgimg` 容器而不是 `.yidun_bg-img` 图片；必须给 `.yidun_bgimg`、`.yidun_bg-img`、`.yidun_avoid-canvas` 返回 `320x160` 的 `offsetWidth/offsetHeight/getBoundingClientRect()`。
5. `.yidun_avoid-front` 需要根据 `style.left` 和 `style.bottom` 返回动态 rect。若该 rect 或 `$bgImg` rect 为 0，`getActualDragCoordinate()` 会把 `ballTraceData` clamp 到无效坐标，常见现象是本地 `m` 长度/点数看似接近，但服务端 `error=100/result=false`。
6. 遇到 `m` 外形已对齐仍失败时，优先用手动正样本在 `onMouseUp` pre-AES 位置做聚合 diff：只记录条数、冒号数、编码长度桶、坐标/耗时范围、flag 分布，不落盘 token、validate、Cookie、cb、fp 或密文。

### 轨迹诊断经验

已验证的有效排查顺序：

1. 先证明负控制能到达 `/api/v3/check` 且服务端返回 `result=false`，确认 check 边界存在。
2. 再采一轮手动正样本，只保留非敏感聚合形状和服务端布尔结果。成功样本需满足 `/check error=0,result=true,token matched,validate present`。
3. 本地失败时不要同时调 IR、fp、轨迹、TLS 和时序。先对齐请求链和同轮 token，再对齐 `m/p/ext` 形状，最后看 `ballTraceData` 内容语义。
4. 如果本地 `m` 点数、冒号数和 AES 长度接近正样本仍失败，检查坐标范围是否真实落在 `0..320 x 0..160` 活动画布内。`-10,-10`、全 0、超边界或 y 轴方向反了都可能被服务端拒绝。
5. 点数不是唯一变量。曾见本地和正样本同为 100 条 `ballTraceData`、`d=0,p/ext` 长度正常，但因 `$bgImg` layout 错误导致服务端拒绝；修正 `.yidun_bgimg` rect 后 fresh 本地链路通过。
6. 轨迹可使用低左侧短 prefix + A* tail + 安全重采样，让官方 core 采样后的 `m` 长度桶接近真人样本；但不得穿越障碍，也不能只追求密文长度。

### 成功判据

必须同时满足：

1. `/v4/j/up` HTTP `200` 且业务 `code=200`，返回本轮可用 `tk`。
2. `/api/v3/get` HTTP `200`、`error=0`、`type=6`，并返回本轮 token 和图片。
3. 图片识别得到目标框和障碍框，规划路径在球半径膨胀后可达。
4. `/api/v3/check` HTTP `200`，JSONP 内 `error=0` 且 `data.result=true`。
5. `check.data.token == get.data.token`。
6. `validate` 非空。不要用 HTTP `200`、`error=0`、token 匹配、`m` 长度或页面文案单独声称成功。
7. 至少再跑一轮 fresh browser-free 本地验证；命令输出建议只打印真实 `/api/v3/check` 响应，调试聚合另走 debug flag 或内部日志。

## 排查清单

1. 障碍躲避 `check` 返回 `error=100/result=false`：先检查 `get/check` token 是否同轮、IR token 是否每轮 fresh，再检查 `$bgImg`/`.yidun_bgimg` 的 rect 是否为 `320x160`。
2. 障碍躲避 `m` 点数和长度像正样本但仍失败：看 pre-AES `ballTraceData` 坐标范围、y 轴方向、最终命中点、flag 和耗时，不要只看密文长度。
3. 障碍躲避本地球坐标全是 `-10,-10` 或常量：通常是 iv8 DOM layout/`getBoundingClientRect()` 未补到官方实际读取的容器。
4. 障碍躲避路径不可达：减小额外 clearance，保留球半径膨胀；确认目标不是障碍候选，目标匹配需考虑旋转。
5. 障碍躲避通过浏览器但本地失败：按正样本锚定的单变量替换法做聚合 diff，禁止把同一 consumed challenge 的 duplicate 当第二次实验结论。
6. 无感链没有发 `check`：确认已等待 `onReady`，并检查 iv8 的祖先事件委托是否收到 `mouseover/mousemove/click`。
2. 无感 `check` 返回 `error=100`：优先检查 `width` 是否为 `320`，再检查 token/data 是否同轮。
3. 无感失败后出现 `type=2` 和 `front/bg`：这是 fallback 新轮，不是原 `type=5` 响应被改写。
4. get 没有返回图片：检查 `cb/callback/fp/irToken/dt/id` 是否过期。
5. JSONP 解析失败：检查 callback 正则是否过窄。
6. OCR 距离异常：检查 `front/bg` 是否拿反或图片响应是否损坏。
7. check 失败：检查 `token/data/trace/slide` 是否同轮。
8. data 异常：确认 `2.获取cb值.js` 已先加载，`window._0x3855dc`、`window._0x3ebd00`、`window._0x6e07ce` 已挂到全局。
