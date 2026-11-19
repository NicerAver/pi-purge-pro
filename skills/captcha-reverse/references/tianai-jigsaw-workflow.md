# TianAi JIGSAW 2x2 工作流

本参考沉淀 TianAi `JIGSAW` 乱序拼图分支。它与普通 `SLIDER`、`CURVE3` 和 `CONCAT` 共用 `generate -> encrypt -> verify` 外层协议与 `cw.js + cw.wasm` collector，但题面答案来自 2x2 tile 排列，行为数据由点击交换产生。协议状态机和服务端验收仍由 `captcha-reverse` 主责；明确选择 Python + iv8 时，iv8 只作为执行后端。

## 1. 触发与边界

命中以下组合时读取本参考：

```text
captcha.tianai.cloud
api.captcha.tianai.cloud
/v2/api/open/captcha/generate
/v2/api/open/captcha/verify
type=JIGSAW
JIGSAW_<id>
data.matrix = [2, 2]
乱序拼图 / 交换拼图
window.__drives__ / window.__ki__ / window.__encrypt__
cw.js / cw.wasm
```

以下情况不要误入本参考：

- 只要求对一张静态拼图做排列识别，不涉及 `generate`/`verify`：转 `captcha-vision` 或普通图像处理。
- 只要求找 `__encrypt__` 调用点、打印 call stack 或写 DevTools hook：转 `trace`。
- 用户要求训练 YOLO、CLIP、ONNX 或批量图像识别，但排除协议恢复：转 `captcha-vision`。
- 只有普通 WAF cookie、403 或泛化 sign，没有 TianAi 验证码状态机：转 `trace` 或对应 WAF skill。

本分支的正式目标是：

```text
fresh generate
  -> 同轮 JIGSAW challenge
  -> 当前题面排列解析
  -> 当前轮行为明文
  -> 当前 cw runtime encrypt
  -> fresh verify drives/ki
  -> verify code=200 && success=true
```

## 2. 当前案例已确认的题面结构

本案例当前页面返回：

```json
{
  "type": "JIGSAW",
  "backgroundImageWidth": 600,
  "backgroundImageHeight": 360,
  "data": {
    "matrix": [2, 2]
  }
}
```

页面约以 `300x180` 显示四块 tile。bundle 创建四个 tile 元素：

1. 四个元素共享当前轮的 `background-image`；
2. `background-position` 表示该元素使用的源图块；
3. CSS `order` 表示元素当前显示槽位；
4. 用户依次点击两个 tile，页面交换它们；
5. 确认时把当前排列传入验证回调，再由外层 wrapper 加密和提交。

因此当前 2x2 JIGSAW 可以把题面状态表示为：

```text
permutation[destination_slot] = source_tile_index
目标排列 = [0, 1, 2, 3]
```

不要从普通滑块经验推导缺口、透明 template 或 `shuffle.pos`。当前 JIGSAW 的有效题面证据是 DOM tile 的 `background-position` 和 CSS `order`。

## 3. 同轮状态硬约束

以下字段必须来自同一 fresh round：

```text
generate_drives
generate_ki
challenge id
backgroundImage URL
backgroundImageWidth / backgroundImageHeight
matrix
当前 DOM tile background-position
当前 DOM tile order
交换计划
行为明文
加密 data
verify_drives
verify_ki
最终 verify JSON
```

生产代码禁止读取历史 `evidence/round_*`、旧 challenge、旧图片 URL、旧 ciphertext、旧 token、旧 `drives` 或旧 `ki` 作为当前请求输入。历史样本只能用于离线 codec 回归、模板池和诊断。

`generate` 和 `verify` 即使在同一个 iv8 context 中，也必须分别调用当前 runtime 的动态函数。当前浏览器证据显示两侧 `drives/ki` 的摘要不同，不能因为长度相同就复用。

正式成功条件只有：

```python
result.get("code") == 200 and result.get("success") is True
```

以下都不是成功：

```text
generate code=200
data 非空
HTTP 200
密文长度与历史样本相同
图片排列看起来正确
token 字段存在
```

## 4. 浏览器取证顺序

### 4.1 先清理并获取请求

在授权 CloakBrowser 会话中：

1. 清理旧 Network 记录；
2. 打开验证码入口；
3. 触发一轮 JIGSAW；
4. 捕获 `POST /v2/api/open/captcha/generate?appId=...`；
5. 捕获最终 `POST /v2/api/open/captcha/verify`；
6. 记录两者 request id、challenge id、HTTP 状态和 JSON 结果；
7. 只用同一 challenge 关联 generate 与 verify。

generate 的最小形态：

```text
POST https://api.captcha.tianai.cloud/v2/api/open/captcha/generate?appId=<current app id>
Content-Type: application/json

{"drives":"<current generate drives>","ki":"<current generate ki>"}
```

verify 的最小形态：

```text
POST https://api.captcha.tianai.cloud/v2/api/open/captcha/verify
Content-Type: application/json

{
  "id": "<same round id>",
  "data": "<same round encrypted data>",
  "drives": "<fresh verify drives>",
  "ki": "<fresh verify ki>"
}
```

### 4.2 再取 DOM，不要先猜图像答案

页面弹出 JIGSAW 后执行观察脚本，至少保存：

```json
{
  "matrix": [2, 2],
  "displayWidth": 300,
  "displayHeight": 180,
  "items": [
    {
      "order": 0,
      "backgroundPosition": "0px 0px"
    }
  ]
}
```

实际项目对应：

```text
src/page_probe.js
src/jigsaw_solver.py
```

观察脚本只读取 DOM，不提交点击，不生成 verify 数据。它可以作为入口定位和排列证据，不应被当作自动化浏览器方案。

### 4.3 捕获 `__encrypt__` 入参

必须在页面很早阶段安装被动 hook，避免点击完成后才安装：

```javascript
(() => {
  const original = window.__encrypt__;
  if (typeof original !== "function") return;
  window.__mcpCapture = window.__mcpCapture || {inputs: []};
  window.__encrypt__ = function (value) {
    window.__mcpCapture.inputs.push({
      value: String(value),
      length: String(value).length,
    });
    return original.apply(this, arguments);
  };
})();
```

本案例出现过同一明文被连续调用两次的情况。采集器应按值和长度去重，并用调用顺序、verify request 时间、challenge id、data 长度和摘要进行关联。不能看到一个 plaintext 就直接认定它属于某个 verify。

动态明文、完整密文和 token 不进入长期 skill。项目证据可保留脱敏 plaintext 回归材料，但公开教程和 skill 只记录长度、字段结构、SHA-256 或受控摘要。

## 5. DOM 排列解析

### 5.1 CSS background-position 到源块

当前显示尺寸为 `300x180`，2x2 每块显示尺寸为 `150x90`。CSS 背景偏移使用显示尺寸比例：

```python
source_col = round(abs(background_x) / (display_width / cols))
source_row = round(abs(background_y) / (display_height / rows))
source_index = source_row * cols + source_col
```

实现必须读取当前响应尺寸和 DOM 显示尺寸，不要永久写死 `600x360` 或 `300x180`。如果页面存在 CSS transform、device scale 或非整数宽高，先把实际 `getBoundingClientRect()` 写入 sidecar。

### 5.2 CSS order 到 destination slot

每个 tile 的 `order` 是它当前显示槽位。按 `order` 升序排列后，得到：

```python
permutation = [source_index_for_each_visible_slot]
```

必须检查：

```python
len(permutation) == cols * rows
sorted(permutation) == list(range(cols * rows))
```

如果不是完整排列，停止交换计划生成。不要用不完整 DOM 结果提交 verify。

### 5.3 生成 pair-swap 计划

从当前排列变成 `[0, 1, 2, 3]`：

```python
def swap_plan(current):
    work = list(current)
    plan = []
    target = list(range(len(work)))
    for slot in range(len(work)):
        if work[slot] == target[slot]:
            continue
        other = work.index(target[slot], slot + 1)
        work[slot], work[other] = work[other], work[slot]
        plan.append((slot, other))
    return plan
```

这个计划只描述要点击的两个显示槽位，不是协议密文，也不是服务端直接接受的答案字段。点击交互仍然需要生成与当前 bundle 一致的行为轨迹。

### 5.4 图像枚举作为 fallback

没有 DOM 时，2x2 只有 `4! = 24` 个候选排列，可以做离线 seam continuity 排序：

```text
切成 2x2 四块
 -> 枚举 24 个 permutation
 -> 比较相邻块的水平/垂直边缘连续性
 -> 输出 top-k 和分数
```

图像 top-1 只能是候选，不能替代 DOM 证据或服务端验收。复杂纹理、重复背景和边界内容会产生错误 top-1。生产默认保留 top-k、margin、confidence 和 debug image；候选不明确时停止。

## 6. `cw.js + cw.wasm` 本地 runtime

### 6.1 当前 collector 判定

当前页面有效 collector 是：

```text
cw.js + cw.wasm
```

不要把旧 `main.wasm`、旧 Go runtime 或历史 `load.js` 当作当前生产输入。资源切换时重新保存 URL、版本和 SHA-256，并重新做 smoke。

### 6.2 iv8 初始化顺序

本案例的 browser-free runtime 顺序：

```text
创建 fresh iv8 JSContext
 -> page.load 一个本地空页面
 -> 补 document.scripts
 -> eval 当前 cw.js（阻止自动网络 wasm 初始化）
 -> initSync 当前本地 cw.wasm bytes
 -> drain microtasks
 -> 检查 __drives__/__ki__/__encrypt__
```

`document.scripts` 是实际缺口之一。不能只把它设置成普通 Python list；当前代码使用真实 script collection 作为 getter 返回值，让 bundle 看到浏览器式 collection。

本地实现对应：

```text
src/runtime_iv8.py
utils/iv8_silent.py
```

核心形态：

```python
cw_source = cw_js.read_text(encoding="utf-8")
cw_source = cw_source.split("/* captcha-wasm auto-init */", 1)[0]
wasm_bytes = cw_wasm.read_bytes()
ctx.eval(cw_source)
ctx.eval("wasm_bindgen.initSync({module: ...})")
```

只替换已经确认的 auto-init marker。marker 出现 0 次或多次时，说明资源版本变化，应回到浏览器取证，不要盲目切字符串。

### 6.3 isolated smoke

先不访问验证码 API，验证：

```python
smoke = {
    "drives": runtime.drives(),
    "ki": runtime.ki(),
    "encrypted": runtime.encrypt("local-smoke"),
}
```

只输出摘要：

```json
{
  "status": true,
  "backend": "python-iv8",
  "collector": "cw.js + cw.wasm",
  "drivesLength": 1068,
  "kiLength": 172,
  "encryptLength": 44,
  "networkRequests": 0
}
```

`networkRequests=0` 应排除 iv8 的页面 navigation 记录，只统计 collector 运行期间的外部请求。长度是诊断信息，不是验收条件。

## 7. JIGSAW 明文与 codec 状态

### 7.1 已观察到的字段顺序

当前 hook 捕获的 plaintext 前缀符合以下 preRequest 组织顺序：

```text
startTime
stopTime
bgImageWidth
bgImageHeight
templateImageWidth
templateImageHeight
left
top
trackList.length
track encoding
optional custom data
```

本案例当前常见前缀对应：

```text
startTime / stopTime: 7 字符无符号 base64-like 字段
背景显示尺寸: 300, 180
template 尺寸: 当前 JIGSAW 观察为 0, 0
left / top: 当前观察为 0, 0
```

这部分只能作为当前 bundle 的实证结构。修改 bundle、题型或页面版本时必须重新 hook 并做 decode -> encode 回归。

### 7.2 数值表和差分轨迹

当前工程实现了候选 codec：

```text
alphabet = 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-~
base = 64
signed value   = sign + fixed-width base64(abs(value))
unsigned value = fixed-width base64(value)
first point   = absolute x/y/t
later points  = x/y/t delta from previous point
```

对应文件：

```text
src/jigsaw_codec.py
```

回归至少应检查：

```text
已捕获 plaintext 的头字段长度
时间字段替换后总长度不变
track count 与解析结果一致
编码函数不产生 NaN、负时间或非单调时间
```

### 7.3 不要提前宣称通用轨迹 codec 已完成

本案例中直接用 Python 生成的实验性点击/移动轨迹提交后返回过 `HTTP 200 + code=4001 + success=false`。因此：

- `jigsaw_codec.py` 是当前明文结构和算法轨迹的研究实现；
- 它不能因为本地加密成功就被称为服务端已验证 codec；
- 失败轮只能作为负诊断样本；
- 只有 fresh `verify code=200 && success=true` 才能把某种轨迹编码和模板写入正式正样本池。

如果新 bundle 的明文尾部与当前观察不同，先捕获一条新的成功轮，再修改 codec；不要凭长度猜字段。

## 8. 成功正样本采集

### 8.1 正样本资格

只有以下条件全部满足，人工轮才可以进入正样本池：

```text
generate 与 verify 的 id 相同
verify HTTP 200
verify JSON code == 200
verify JSON success == true
token/动态密文只保留受控摘要
```

当前案例在同一 CloakBrowser session 中取得了 5 个成功轮和 1 个 `4001` 失败轮。失败轮只保留用于诊断，不混入正样本。

### 8.2 每轮保存什么

项目相对 evidence sidecar 可以保存：

```text
round/request id
challenge id 的脱敏标识或 hash
type/matrix/source size/display size
plaintext length/hash
ciphertext length/hash
generate drives/ki length/hash
verify drives/ki length/hash
HTTP status
verify code/success
track count/duration 摘要
```

不要保存：

```text
真实 token
完整 Cookie
完整 signed image URL
完整 ciphertext
完整 drives/ki
可直接复用的旧 challenge
```

### 8.3 采集时序

hook 必须在题面交互前安装，随后按以下顺序关联：

```text
hook __encrypt__
 -> generate request/response
 -> 用户完成当前 JIGSAW
 -> verify request
 -> hook plaintext 与 verify data 按时间和调用次序配对
 -> 读取 verify JSON
 -> 只把 success=true 的向量加入 positive pool
```

如果 hook 安装晚了，成功轮没有明文，不能用失败轮猜测成功格式。应在同一个尚未污染的浏览器 session 中重新采集 fresh success rounds。

## 9. Snapshot-driven 与通用求解的边界

### 9.1 当前可验证的本地路径

本案例已验证 browser-free 路径：

```text
fresh local iv8 runtime
 -> fresh generate
 -> 读取一个已验证正样本的行为模板尾部
 -> 只重写当前 round 的 startTime/stopTime
 -> 等待声明的轨迹时长
 -> 当前 runtime.__encrypt__
 -> 当前 verify drives/ki
 -> fresh verify
```

对应入口：

```text
src/pure_local.py
src/jigsaw_templates.json
```

该模式输出的 mode 必须明确写成：

```text
snapshot-driven-positive-template
```

它证明协议外层、cw runtime、动态字段和服务端 verify 已闭环；它不证明已经实现对任意新拼图排列的通用视觉和行为求解。

### 9.2 模板的安全边界

模板只能包含行为结构和脱敏回归材料。物化当前 round 时必须：

1. 重新生成当前 challenge；
2. 用当前时间替换绝对时间字段；
3. 用当前 runtime 生成 encrypt 结果；
4. 重新获取 verify 侧 drives/ki；
5. 使用当前 challenge id；
6. 等待声明的轨迹时长；
7. 用服务端 verify 做最终判定。

禁止直接复用：

```text
旧 challenge id
旧 token
旧 encrypted data
旧 drives / ki
旧图片 URL
```

### 9.3 通用 JIGSAW solver 的未完成项

当前仍需 fresh 成功样本证明的内容：

```text
不同交换计划对应的点击顺序是否被服务端严格检查
trackList 真实事件类型与尾部编码的全部语义
页面 clientX/clientY 与 plaintext x/y 的精确相对坐标
成功行为模板按排列/交换次数的分桶策略
算法生成轨迹在新 challenge 上的稳定通过率
```

在这些问题证明前，生产默认应使用显式 snapshot-driven 模式或停止提交，不应把实验性 `--algorithmic-track` 伪装成稳定自动求解器。

## 10. 时间与 verify 调度

`startTime`、`stopTime` 是明文中的绝对时间字段，不能只在字符串里满足差值关系。正式流程必须满足：

```text
generate response received
  <= startTime
  < stopTime
  < verify request start
```

正确结构：

```python
start_ms = int(time.time() * 1000)
stop_ms = start_ms + duration_ms
plaintext = build_or_adapt_plaintext(start_ms, stop_ms)
time.sleep(duration_ms / 1000.0)
data = runtime.encrypt(plaintext)
verify_drives = runtime.drives()
verify_ki = runtime.ki()
post_verify(challenge.id, data, verify_drives, verify_ki)
```

错误结构：

```python
stop_ms = now_ms()
start_ms = stop_ms - duration_ms
# 立即 encrypt 和 verify
```

后者可能产生早于 generate response 的 `startTime`，即使本地看起来时间差正确，服务端也可能拒绝行为数据。`--no-replay-sleep` 只能作为诊断开关，不能作为正式成功路径。

## 11. 错误分层

```text
HTTP 200 + code=200 + success=true
  -> 正样本，闭环通过

HTTP 200 + code=4000
  -> 优先按 challenge 失效、重复消费或状态过期处理
  -> 保存失败轮，重新 generate，不对旧轮继续扫轨迹

HTTP 200 + code=4001
  -> 优先查同轮 id、图片/排列、明文结构、坐标、轨迹、verify drives/ki
  -> 本案例实验性算法轨迹曾落入此类

HTTP 200 + 其他 code / success=false
  -> 保留服务端 msg 和 sidecar，按当前 bundle 重新分类

HTTP 403 或非 JSON
  -> 优先查 collector、UA、Session、Origin/Referer 和请求时序
```

诊断使用单变量替换：

1. 冻结 fresh collector 和 HTTP profile；
2. 固定当前 challenge 只做离线解析，不重复提交已消费轮；
3. 新建 fresh challenge，只替换一种轨迹/时间/坐标变量；
4. 只按最终 verify JSON 判断；
5. 成功后做反向最小控制，确认不是多变量组合偶然通过。

## 12. 推荐项目结构和交付检查

```text
project-root/
  main.py
  src/
    pure_local.py
    runtime_iv8.py
    jigsaw_codec.py
    jigsaw_solver.py
    page_probe.js
    protocol_model.py
    jigsaw_templates.json
  js_reverse_cache/tianai/
    cw.js
    cw.wasm
    load.js
  evidence/
    current_dom_state.json
    jigsaw_positive_vectors.json
    pure_local_success.json
```

运行检查：

```powershell
python -m py_compile main.py src/*.py utils/*.py
python -m src.pure_local --runtime-smoke
python -m src.pure_local
```

验收记录至少包含：

```text
backend=python-iv8
collector=cw.js + cw.wasm
runtime networkRequests=0
fresh challenge matrix=[2,2]
verify HTTP=200
verify code=200
verify success=true
```

最终交付时必须明确写出：

```text
协议外层已通过 fresh browser-free verify
当前默认是 snapshot-driven-positive-template
实验性 algorithmic-track 尚未证明通用成功
```

出现新的 `cw.js/cw.wasm` hash、JIGSAW 字段、matrix 形状、页面尺寸或 verify 错误码时，先回到浏览器取证和 positive sample collection，不要直接沿用本参考的固定字段或模板。
