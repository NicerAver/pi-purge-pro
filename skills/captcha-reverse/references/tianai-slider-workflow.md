# TianAi 滑块验证码工作流

本参考用于 `captcha.tianai.cloud` 及同一套 TianAi 行为验证协议。它是 `captcha-reverse` 的专属分支：协议状态机、图片还原、轨迹明文、WASM 加密输入和服务端验收由本 skill 负责；明确要求 Python + iv8 时，iv8 作为执行后端交给 `iv8-web-reverse` 协同。命中 `type=JIGSAW`、`JIGSAW_`、`data.matrix` 或 2x2 乱序拼图时，另读 `references/tianai-jigsaw-workflow.md`；本文件中的 SLIDER/CURVE3/CONCAT 视觉公式不要直接套到 JIGSAW。

## 1. 触发与边界

命中以下组合时进入本分支：

```text
captcha.tianai.cloud
api.captcha.tianai.cloud
/v2/api/open/captcha/generate
/v2/api/open/captcha/verify
SLIDER_... / CURVE3_... / CONCAT_...
滑动还原 / data.randomY
data.shuffle.pos / data.attr1
backgroundImage / templateImage
__drives__ / __ki__ / __encrypt__
cw.js / cw.wasm
```

以下情况不进入本分支：

- 只要求对一张背景图做缺口识别，不请求 `generate` 或 `verify`：转 `captcha-vision` 或普通图像处理。
- 只要求写 DevTools hook、找函数入口、取 initiator 或 call stack：转 `trace`。
- 只有普通 WAF cookie、403、`a_bogus` 或泛化 sign，没有 TianAi 验证码状态机：转 `trace`、`iv8-web-reverse` 或对应 WAF skill。
- 明确要求训练 YOLO/CLIP、ONNX、批量视觉识别，而不恢复 `generate -> verify`：转 `captcha-vision`。

## 2. 已确认协议图

典型浏览器-free 链路如下：

```text
初始化当前 collector/runtime
  -> 生成本轮 drives、ki
  -> POST /v2/api/open/captcha/generate?appId=<appId>
  -> 返回同轮 id、背景图、尺寸和题型数据
  -> 普通 SLIDER 返回滑块图和 shuffle；CURVE3 返回 attr1 和 shuffle；CONCAT 返回 randomY
  -> 下载当前签名图片
  -> SLIDER/CURVE3 按当前 shuffle.pos 还原背景；CONCAT 直接解析当前错位拼接图
  -> SLIDER 定位缺口；CURVE3 搜索 sliderValue；CONCAT 估计上下图水平拼接位移
  -> 映射到页面/DOM/指针坐标并生成同轮轨迹和 preRequest 明文
  -> 当前 runtime __encrypt__(plaintext) 得到 data
  -> verify 前再次生成当前 drives、ki
  -> POST /v2/api/open/captcha/verify
  -> 只按服务端 code=200 且 success=true 判定成功
```

请求契约：

```text
POST https://api.captcha.tianai.cloud/v2/api/open/captcha/generate?appId=<appId>
JSON: {"drives": <generate_drives>, "ki": <generate_ki>}

POST https://api.captcha.tianai.cloud/v2/api/open/captcha/verify
JSON: {"id": <same_round_id>, "data": <same_round_data>,
       "drives": <verify_drives>, "ki": <verify_ki>}
```

`generate` 响应通常在 `data` 中提供：

```text
id
 type
backgroundImage
backgroundImageWidth / backgroundImageHeight
data.shuffle.x / data.shuffle.y / data.shuffle.pos
普通 SLIDER: templateImage / templateImageWidth / templateImageHeight
CURVE3: data.attr1
CONCAT: data.randomY
```

字段名称以当前响应为准，不能只凭历史文章或旧 bundle 猜测。

## 3. 同轮状态硬约束

以下字段必须来自同一 fresh round，禁止跨轮拼接：

```text
generate_drives
 generate_ki
challenge id
backgroundImage URL
普通 SLIDER 的 templateImage URL、CURVE3 的 data.attr1，或 CONCAT 的 data.randomY
SLIDER/CURVE3 的 shuffle.x / shuffle.y / shuffle.pos
SLIDER/CURVE3 的还原背景，或 CONCAT 当前原始错位拼接图
普通 SLIDER 的滑块图/缺口候选、CURVE3 的解析参数/sliderValue top-k，或 CONCAT 的 seam/anchor/NMS top-k
left / top
轨迹 startTime / stopTime / points
明文 preRequest
加密 data
verify_drives
 verify_ki
最终 verify 响应
```

重要细节：当前浏览器证据显示，`generate` 前和 `verify` 前可能分别调用 `__drives__`、`__ki__`。即使 `drives` 跨轮看起来相同，也不能复用；`ki` 不能写死。生产流程每次必须重新请求 `generate`，重新下载当前签名图片，并在提交前重新取得 verify 所属的运行时输出。

同一 challenge 失败后不要继续对它反复试坐标或轨迹。`4000` 表示 challenge 失效时，保存该轮证据并创建新 round；不要把后续自动生成的 challenge 与前一轮图片拼接。

## 4. 当前 collector 判定

较老的页面版本可能暴露 Go `main.wasm`，但当前页面动态资源可能由 `load.min.js` 加载 Rust/Wasm-bindgen 形式的：

```text
cw.js
cw.wasm
```

必须先通过网络 initiator、资源 URL、脚本内容或运行时导出确认当前 collector。不要因为保存目录里存在 `main.wasm` 就把它当成生产输入。

当前有效路径的通用加载形态是：

```text
读取 cw.js
 -> 阻止它自动从网络解析 wasm URL
 -> wasm_bindgen.initSync({module: current_cw_wasm_bytes})
 -> 在同一 browser-like runtime 中调用 __drives__/__ki__/__encrypt__
```

`main.wasm` 可以保留为 legacy 诊断材料，但不能混入当前 `cw` 生产链。旧 Go WASM 在不完整的 Node/iv8 `syscall/js` 环境中出现 `RuntimeError: unreachable`，不等于当前协议不能运行，也不应通过修改旧 wasm 来替代当前 collector。

## 5. Python + iv8 后端要求

当用户明确选择 Python + iv8：

1. `captcha-reverse` 仍负责完整 `generate -> verify` 状态机和最终服务端验收。
2. 读取并使用 `iv8-web-reverse` 的 runtime 规范；不要先改走 Node/VM 或 AST 路线。
3. collector 初始化、图片 HTTP、协议 HTTP 和结果归档保持在同一轮编排器中。
4. 用真实或已确认的浏览器 profile；至少核对 UA、语言、screen、DPR、plugins、Canvas/WebGL 和 document script collection。
5. 优先保留 iv8 原生 Canvas/WebGL 宿主对象；纯 JS stub 可能改变 `[object CanvasRenderingContext2D]`、`[object WebGLRenderingContext]` 等结果。
6. 如果目标脚本读取 `document.scripts`，确认 iv8 版本是否返回浏览器式 `HTMLCollection`；必要时以真实 script 元素和 getter 补齐。
7. 在网络请求前先做本地 smoke：`__drives__`、`__ki__`、`__encrypt__` 均非空，长度只能作为诊断，不能作为成功证明。
8. 用 fresh `generate` admission 验证 runtime 输出；只有服务端接受后，才能进入图片、轨迹和 verify 阶段。

建议的 runtime 产物摘要：

```text
backend = python-iv8
collector = cw.js + cw.wasm
profile name/version
cw.js and cw.wasm hash
__drives__ length/hash
__ki__ length/hash
__encrypt__ output length/hash
browser-like surface summary
networkRequests during isolated collector
```

不要把完整动态密文、cookie 或个人指纹写进长期 skill；它们只保存在目标项目的受控 evidence 中。

## 6. 5x2 图片还原

背景图通常是源尺寸 `600x360`，页面显示尺寸为 `300x180`。服务器给出十块排列信息，通常为 `shuffle.x=5`、`shuffle.y=2`，`pos` 是目标位置到源图块的映射。

还原算法：

1. 将下载的背景图按源图尺寸切为 5 列、2 行，共 10 块。
2. 以行优先编号源块 `0..9`。
3. 对每个目标位置 `destination`，取 `tiles[pos[destination]]` 放回目标位置。
4. 输出同源尺寸的 restored image。
5. 用当前 challenge 的 `pos`，不能用历史 round 的排列。

伪代码：

```python
for destination, source in enumerate(pos):
    row, col = divmod(destination, 5)
    restored.paste(tiles[source], (col * tile_w, row * tile_h))
```

必须校验 `pos` 是 `0..9` 的完整排列，并校验图片宽高可被 `5x2` 整除。不要在乱序图上直接做缺口识别。

普通 `SLIDER` 的 `templateImage` 通常保留源图完整高度，并通过 alpha 通道表达可见滑块。先提取 alpha bbox，再识别其对应背景位置；不要把透明画布左上角当作真实滑块坐标。

`CURVE3` 通常没有 `templateImage`；它使用 `data.attr1` 描述曲线参数。遇到 `type=CURVE3` 时不要报“缺少滑块图”，应转入本节后的 CURVE3 双贝塞尔识别流程。

## 6A. CURVE3 专项识别算法

`CURVE3`/“滑动曲线 V3”与普通 `SLIDER` 不同：当前 `generate` 响应通常只有背景图、`data.attr1` 和 `data.shuffle`，不提供普通滑块的 `templateImage`。验证码窗口中的目标曲线由 `tac.min.js` 根据 `attr1` 在 `#tianai-captcha-curve-bg-canvas` 上绘制，滑动时再根据当前位移重绘同一条曲线。识别目标不是矩形缺口，而是求一个使渲染曲线与还原背景中的白色参考线重合的水平位移参数。

### 6A.1 `attr1` 字段布局

当前 bundle 对 `attr1` 执行：

```javascript
const parts = attr1.split(".");
```

因此不能按逗号、JSON 或普通浮点数组解析。响应中的 20 个 token 两两拼接为 10 个十进制小数：

```text
v0  = parts[0]  + "." + parts[1]
v1  = parts[2]  + "." + parts[3]
v2  = parts[4]  + "." + parts[5]
v3  = parts[6]  + "." + parts[7]
v4  = parts[8]  + "." + parts[9]
v5  = parts[10] + "." + parts[11]
v6  = parts[12] + "." + parts[13]
v7  = parts[14] + "." + parts[15]
v8  = parts[16] + "." + parts[17]
v9  = parts[18] + "." + parts[19]
```

字段语义和坐标系为：

```text
v0: 左端点 x / 显示宽度
v1: 左端点 y / 显示高度
v2: 右端点 x / 显示宽度
v3: 右端点 y / 显示高度
v4: 第一段控制点 x / 源图宽度
v5: 第一段控制点 y / 源图高度
v6: 第二段控制点 x / 源图宽度
v7: 第二段控制点 y / 源图高度
v8: 两段连接点 x / 源图宽度
v9: 两段连接点 y / 源图高度
```

当前页面常见源图为 `600x360`、Canvas 显示为 `300x180`。因此应先读取响应尺寸，再换算：

```python
left_x  = v0 * display_width
left_y  = v1 * display_height
right_x = v2 * display_width
right_y = v3 * display_height
ctrl1_x = v4 * display_width / source_width
ctrl1_y = v5 * display_height / source_height
ctrl2_x = v6 * display_width / source_width
ctrl2_y = v7 * display_height / source_height
joint_x = v8 * display_width / source_width
joint_y = v9 * display_height / source_height
```

经验上，`attr1` 解析错误会导致整条曲线形状错误，后续所有 x 搜索和轨迹调参都没有意义。必须先检查 token 数量为 20、每个 token 是非空十进制片段，并保存解析后的参数摘要。

### 6A.2 当前 bundle 的双二次贝塞尔公式

`CURVE3` 的 `drawDoubleBezier(sliderValue)` 可以还原为两段二次贝塞尔曲线：

```text
P0 = (left_x, left_y)
P1 = (ctrl1_x * sliderValue / display_width,
      ctrl1_y * sliderValue / display_height)
P2 = (joint_x * sliderValue / display_width,
      joint_y * sliderValue / display_height)
P3 = (ctrl2_x * sliderValue / display_width,
      ctrl2_y * sliderValue / display_height)
P4 = (right_x, right_y)

segment_1 = quadratic(P0, P1, P2)
segment_2 = quadratic(P2, P3, P4)
```

其中：

```text
quadratic(A, C, B, t) = (1-t)^2*A + 2*(1-t)*t*C + t^2*B
0 <= t <= 1
```

两段曲线共享 `P2`。实现时用 100～300 个采样点/段离散为折线，再用 `cv2.polylines` 按当前 Canvas 的 `lineWidth=5`、抗锯齿和圆端点栅格化。`sliderValue` 是当前曲线绘制参数，实际拖动终点还要结合浏览器成功轨迹的 DOM/指针偏移校准，不能把它无条件当作源图 x 或按钮的 `left`。

### 6A.3 从还原图提取曲线证据

推荐使用可解释的传统 CV pipeline，先不要训练 YOLO：

```text
当前签名 JPEG
  -> 按当前 shuffle.pos 还原 5x2 图块
  -> resize 到当前页面显示尺寸，通常 300x180
  -> RGB 转灰度和 HSV
  -> Gaussian background subtraction / white top-hat
  -> 低饱和高亮像素图
  -> Canny 边缘图作为弱证据
  -> 对每个 sliderValue 栅格化预测曲线
  -> 计算曲线 mask 与证据图的综合分数
```

可用的白线证据：

```python
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
local = cv2.GaussianBlur(gray, (0, 0), 4.0)
top_hat = np.maximum(gray - local, 0.0)
hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
white = (gray / 255.0) * (1.0 - hsv[:, :, 1] / 255.0)
edges = cv2.Canny(gray.astype(np.uint8), 35, 100) / 255.0
evidence = 0.60 * normalise(top_hat) + 0.28 * white + 0.12 * edges
```

曲线候选分数至少保留以下分量，且保存原始分数，不能只输出 top-1：

```text
ridge_score: 预测曲线上的 top-hat 平均值
white_score: 预测曲线上的低饱和高亮平均值
contrast_score: 曲线带与周边局部 ring 的证据差
coverage_score: 曲线像素超过全图证据阈值的比例
```

当前工程使用的综合形式为：

```text
score = 0.52 * ridge
      + 0.20 * white
      + 0.20 * contrast
      + 0.08 * coverage
```

这不是平台固定公式，而是当前页面的诊断起点。必须输出：

```text
selected sliderValue
候选 top-k
每个候选的 score/ridge/white/contrast/coverage
score margin
confidence = high | medium | ambiguous
debug image
```

推荐搜索范围为当前显示宽度内的有效范围，例如 `8..242`，步长 `1`。搜索得到的候选是“曲线参数”，不是直接的 DOM `clientX`。当候选分数接近时，生产默认停止；`--allow-ambiguous` 只能作为实验开关。

### 6A.4 识别失败的具体原因

CURVE3 识别常见误差不是模型召回，而是坐标和相似曲线误配：

1. 在乱序图上直接识别。必须先按当前轮的 `pos` 还原，不能复用旧图或历史排列。
2. 把源图坐标当页面坐标。当前常见比例为 `600x360 -> 300x180`，控制点和端点的换算规则不同。
3. 把自然物边缘当白色参考线。山峰、云、星星和高亮轮廓会进入 Canny，因此要使用 top-hat、低饱和白线、局部对比度和曲线连续性共同评分。
4. 只取二维局部峰值。真实参考线可能是长脊而不是局部极大值，应保留整条 x/slider 搜索曲线；没有明显峰值时仍保留 top-k 并标记 ambiguous。
5. 只按几何形状匹配。相似的 U 形或 V 形会产生多个候选，必须记录 debug 图和 margin，并在服务端结果中做受控验证。
6. 把视觉候选值直接写成轨迹终点。实测浏览器成功轮中，视觉候选和真实水平位移可有约 3px 差异；终点应结合成功模板和明确的 x 容差处理。

当前实证中，视觉 top-1 为 `219` 而成功轨迹模板位移为 `222` 时，直接使用 `219` 会进入 `50000`；将同轮成功模板的位移保留为 `222` 后通过。另一轮视觉值为 `200`、最近模板位移为 `190` 时，盲目复用模板位移进入 `4001`。因此应采用：差值在小容差内保留成功模板位移，差值超过容差时缩放模板形状到视觉位移，并把两者都写入 sidecar；不能静默覆盖。

## 6B. CONCAT / 滑动还原专项识别算法

`CONCAT` 是上下图水平拼接题，不是缺口滑块。当前页面将同一张错位图片同时作为完整背景和顶部可移动条的 CSS background；用户拖动按钮时只水平移动顶部条，使拼接线两侧的结构连续。不要寻找透明滑块、缺口或 `shuffle.pos`，也不要把 `randomY` 当成水平答案。

### 6B.1 响应与 DOM 语义

当前 `generate` 的最小结构为：

```json
{
  "id": "CONCAT_...",
  "type": "CONCAT",
  "backgroundImage": "<same-round signed URL>",
  "backgroundImageWidth": 600,
  "backgroundImageHeight": 360,
  "data": {"randomY": 199}
}
```

页面常见显示尺寸为 `300x180`，但实现必须读取当前响应和 DOM。当前 bundle 中已验证：

```text
seamSourceY       = sourceHeight - randomY
stripDisplayHeight = round(seamSourceY * displayHeight / sourceHeight)
seamDisplayY       = stripDisplayHeight
```

例如源图 `600x360`、显示 `300x180` 时，缩放系数通常为 `0.5`。必须用 `#tianai-captcha-slider-concat-img-div` 的实际高度反证公式；页面版本变化、CSS 缩放或字段语义变化时，先停止提交并重新取证。

CONCAT 的 `preRequest` 尺寸使用页面显示坐标：

```text
bgWidth / bgHeight             = 当前显示背景尺寸
 templateWidth                  = 顶部条显示宽度，通常等于 bgWidth
 templateHeight                 = stripDisplayHeight
 left / top                     = 滑块按钮 DOM 起点
 track                           = client 坐标轨迹
```

`randomY`、`seamSourceY`、`stripDisplayHeight`、视觉水平位移、按钮 `left` 和指针 `clientX` 是不同变量，必须分别保存。

### 6B.2 基础一维拼接评分

先把当前签名图片缩放到显示尺寸，再在拼接线两侧取窄带。对每个候选水平位移 `dx`，比较顶部条的左侧有效区域与底图向右偏移后的区域：

```python
top    = image[seam_y-band : seam_y, 0 : width-dx]
bottom = image[seam_y : seam_y+band, dx : width]
```

当前可解释评分包含：

```text
edge:    top/bottom 水平 Sobel 的 NCC
texture: top/bottom 灰度的 NCC
color:   1 - RGB 平均绝对误差 / 255
seam:    窄带内部垂直梯度的 NCC
```

已验证的起始权重为：

```text
score = 0.38 * edge
      + 0.28 * texture
      + 0.16 * color
      + 0.18 * seam
```

这组权重是诊断起点，不是平台常量。每个候选必须保存四个原始分量、综合分、拼接线位置和有效重叠宽度。自然图像、动漫人物、几何图案和高对比线稿的最优分量不同；不要只用全块 RGB 相似度，也不要在噪声拼接线上直接做单行 MAE。

推荐搜索范围是页面允许的按钮位移，例如 `0..242`，但应由当前轨道和按钮宽度推导：

```text
maximumDx = trackWidth - effectiveButtonOrBoundaryReserve
```

### 6B.3 边界锚点

原始综合 top-1 容易被大面积同色背景或自然纹理误导。增加一个独立的极窄边界锚点：跳过拼接噪声线，在 `seam_y-3` 和 `seam_y+3` 附近各取一行 RGB，搜索 NCC 最大值。

```python
for dx in range(maximum_dx + 1):
    top_row = rgb[seam_y-3 : seam_y-2, :width-dx]
    bot_row = rgb[seam_y+3 : seam_y+4, dx:]
    anchor_score[dx] = ncc(top_row, bot_row)
anchor_x = argmax(anchor_score) + calibrated_adjust
```

当前成功样本上 `calibrated_adjust=-2` 是有效起点，但它必须由当前页面版本的人工成功轮离线评估决定，不能跨版本永久写死。

边界锚点不是直接答案，而是用于在多样化候选中选择最可信的一簇。若锚点落在搜索边界、纹理极少或与综合峰严重冲突，应降级为 `ambiguous`。

### 6B.4 候选 NMS 与选择门

原始排序常被 `x=149/150/151/152` 一组相邻峰占满，导致真实的另一簇候选被挤出 top-k。对按分数排序的候选执行一维非极大值抑制：

```python
selected = []
for candidate in sorted(all_candidates, key=score, reverse=True):
    if all(abs(candidate.x - old.x) >= nms_radius for old in selected):
        selected.append(candidate)
    if len(selected) == top_k:
        break
```

当前经验起点为 `nms_radius=2`、`top_k=8`。随后在 NMS 候选中选择距离 `anchor_x` 最近者；距离相同时取综合分高者。

每轮 locator 输出至少包含：

```text
randomY / seamSourceY / seamDisplayY
rawSelectedDisplacementX
boundaryAnchorX
anchorConflict = abs(rawSelected - anchor)
selectedDisplacementX / selectedCandidateIndex
NMS top-k 及 edge/texture/color/seam/score
scoreMargin
confidence
selectionStatus = safe | ambiguous
debug image
```

生产门建议：

```text
raw peak 与 anchor 严重冲突            -> ambiguous，不提交
selected candidate 离 anchor 仍过远    -> ambiguous，不提交
候选低于/高于成功模板覆盖且无近邻证据 -> 停止或显式实验
低 margin 但 raw/anchor/selected 一致  -> 可标 safe，仍需服务端验收
```

阈值必须由当前正样本评估。某次当前页面数据中，`anchorConflict <= 24px` 且最终候选距 anchor `<=8px` 可作为安全起点；这不是 TianAi 固定规则。

### 6B.5 离线监督评估

每个最终 `verify code=200 && success=true` 的人工轮都应固化为监督样本：

```text
challenge id
当前图片及 SHA-256
randomY / source/display size
人工 displacementX/Y
startOffsetX/Y
point count / duration
最终 verify code/success
```

评估定位器时至少输出：

```text
selected absolute error
candidate-pool nearest error
within 2px / 3px / 4px
MAE / max error
raw top-1、anchor 和 selected 的逐轮差分
```

一次已验证的数据集中，9 个服务端成功人工轮覆盖 `63..236px` 位移；边界锚点 + NMS 后 selected `9/9` 在真实位移 `3px` 内，MAE `2.11px`，候选池 `9/9` 在 `4px` 内。该统计只证明当前页面资源和样本分布，不能外推为全站稳定率。

精确 SHA-256 命中历史成功图片时，可以记录 `snapshot-driven-exact-hash` 标签用于诊断、缓存或回归；不能把精确命中伪装成泛化算法，也不能复用历史 challenge、旧图片 URL、旧 data 或旧 ki 提交当前 verify。

### 6B.6 CONCAT 轨迹模板与模板检测

只导入最终 `code=200 && success=true` 的真实手动轮。模板必须保留：

```text
displacementX / displacementY
startOffsetX / startOffsetY
pointCount / durationMs
xNorm / yNorm / tNorm / event types
最大 y 漂移
overshoot / settling / release hold
source round 和页面版本
```

重要特例：某条成功轨迹最终 `displacementY=0`，中间仍可能有 `-5px` 等真实 y 漂移。此时 `yNorm` 不能除以零后全部压成 0；应保存中间 y 的绝对像素偏移，物化时再加到当前起点。

不要用一条固定轨迹覆盖全部位移。推荐：

1. 按目标视觉位移排序成功模板。
2. 在“最近距离 + 小窗口”内保留 1～3 条候选模板。
3. 按距离倒数加权随机选择，避免固定模板序列。
4. 排除异常长轨迹；短模板只有多轮 fresh 成功后才进入默认池。
5. 目标与模板位移接近时可保留已验证模板终点；差异较大时把成功形状缩放到视觉位移。
6. 高位移超过已验证成功上界、且最近成功模板只差数像素时，优先使用成功上界而不是向外外推。
7. 低于成功模板覆盖范围时生产默认停止；只在显式受控实验中外推。

一次当前页面人工池包含 9 个成功模板，覆盖 `40..305` 点、`1196..11336ms` 和多种 start offset/y movement。生产池排除 305 点/11 秒异常长模板后，使用相近模板随机选择和视觉位移缩放，能显著减少固定模板导致的 `50000`；仍必须用 fresh 服务端批次验证。

### 6B.7 坐标和终点

设按钮 DOM 起点为 `(left, top)`，成功模板按下偏移为 `(offsetX, offsetY)`：

```text
startX = left + offsetX
startY = top  + offsetY
endX   = startX + targetDisplacementX
endY   = startY + templateDisplacementY
```

`targetDisplacementX` 是指针水平位移，不是绝对 `clientX`。视觉候选与人工真实位移在当前证据中可有约 `±3px` 偏差，必须通过成功样本校准并记录：

```text
visualDisplacementX
templateDisplacementX
targetDisplacementX
displacementSource = nearby_success_template | visual_plus_adjust | high_cap
```

不要把统一 `+3px`、统一 `+1px` 或固定按钮中心写成平台常量。不同背景、窗口和页面版本必须重新评估。

### 6B.8 CONCAT 故障矩阵

```text
4000 已失效
  -> challenge 过期、重复消费或人工拖动太晚
  -> 保存失败轮，重新 generate；不加入模板池

4001 基础校验失败
  -> 优先查 randomY/seam 高度、视觉 x、按钮 left/top、pointer offset
  -> 查是否把 source x、display x、clientX 或模板位移混用
  -> 高位移是否外推超过已验证上界

50000 check fail
  -> 基础字段通常已进入行为层
  -> 查真实墙钟、点数/时长、y 漂移、模板重复、缩放幅度和终点
  -> 查是否用单条固定轨迹覆盖多个位移
  -> 固定定位层后一次只替换模板或位移来源
```

同一 challenge 只提交一次。人工失败轮可以保留为反例，但 `4000/4001/50000` 都不能进入成功模板池。

### 6B.9 验收边界

建议按以下顺序验收：

```text
Gate A: randomY 公式与 DOM strip 高度一致
Gate B: 人工成功图片离线定位误差统计通过
Gate C: preRequest decode -> encode 逐字回归
Gate D: 一轮 fresh 本地 verify code=200 && success=true
Gate E: 多模板、多位移 fresh 批次；记录提交、成功、安全停止和错误码
Gate F: 至少 20 个独立 fresh round 后再声明稳定
```

一次当前页面的最新有界批次为 5 个 fresh round：3 个明确候选全部服务端成功，2 个因低于模板支持或锚点冲突安全停止；这说明门禁有效，但仍不足以宣称长期稳定。报告必须同时给出“提交成功率”和“总尝试覆盖率”，不能只报已提交样本的成功率。

## 7. 轨迹明文与加密输入

客户端 `preRequest` 的明文顺序为：

```text
startTime
stopTime
bgWidth
bgHeight
templateWidth
templateHeight
left
top
trackCount
encodedTrack
[captchaData]
```

已验证的关键语义：

- `startTime`、`stopTime` 是绝对毫秒时间戳。
- 第一轨迹点使用绝对 `x/y/t`。
- 后续点使用相邻点的 `x/y/t` 差分。
- 事件码通常为 `down=0`、`move=1`、`up=2`、`end=3`。
- 轨迹明文中的尺寸使用页面显示尺寸，常见为背景 `300x180`、滑块 `55x180`，不是源图 `600x360`、`110x360`。
- `left/top` 是页面滑块按钮的 DOM 几何起点字段，和图像源坐标不是一回事。
- 可选 `captchaData` 先执行紧凑 `JSON.stringify`，再按 JS UTF-16 `charCodeAt` 编成逗号分隔数字。

数值预处理和轨迹编码：

```text
alphabet = 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-~
base = 64
signed integer: sign + fixed-width base64(abs(value))
unsigned integer: fixed-width base64(value)
track point: x, y, t, eventCode
```

编码必须按当前 bundle 的实际函数回归。至少保留：

```text
plaintext -> decode fields/track -> encode again -> byte-for-byte equality
```

然后把当前明文传给当前 runtime 的 `__encrypt__`。不要拿历史密文作为当前 round 的 `data`，也不要只按 `data` 长度判断正确。

## 8. 图片定位与坐标映射

定位器必须输出 top-k 候选，而不是只返回一个不可解释的 x。建议输出：

```text
candidate x/y
shape or Chamfer score
edge/texture/contrast score
overlay score
content correlation score
alpha bbox expected y
same-y cluster
confidence
```

推荐策略：

1. 用滑块 alpha 轮廓产生候选。
2. 用边缘、纹理、对比度和滑块内部透明区域的背景内容相关性重排。
3. 用 alpha bbox 的 `y0` 作为源图 y 约束。
4. 若二维局部极值没有落入该 y 邻域，在固定 y 邻域执行密集 x 扫描；不能退回整张图的无关 y 候选。
5. 保留 shape candidates 和综合 candidates，记录 `ambiguous`、`dense-y-scan` 或 y-fallback 状态。
6. 生产默认在候选不明确时停止；只有实验开关显式允许才提交候选 index 0。

页面常将源图从 `600x360` 显示为 `300x180`，因此常用映射为：

```text
x_display = round(x_source * 300 / 600)
y_display = round(y_source * 180 / 360)
```

实际应读取当前 challenge 的尺寸后计算，不要永远写死 600/360。图像缺口的 y 只用于定位背景目标，通常不应直接把滑块按钮轨迹垂直移动到缺口 y；真实手动成功轨迹主要是水平移动，只带少量 y 漂移。

## 9. 轨迹生成

不要用一条固定的线性 48 点轨迹覆盖所有图片。优先从同平台真实成功手动轨迹建立归一化模板，保留：

```text
xNorm / yNorm / tNorm
event types
point count
durationMs
displacementX / displacementY
startOffsetX / startOffsetY
加速段
短暂停顿
末端超调
回弹/settling
释放前停留
```

每轮按目标水平位移和历史成功分布选择最近模板，再缩放到当前 `start_x/start_y` 与 `target_x/target_y`。保留小幅随机抖动时必须保持时间严格递增、终点严格落在目标、轨迹总时长与 `stopTime-startTime` 一致。

已验证的成功模板可覆盖不同点数、时长和位移；这说明“真实轨迹分桶采样”比固定模板更可靠，但不代表轨迹已经对所有背景稳定。排除 `4001`、`50000` 失败轮，不要把失败反例混入成功模板池。

## 9A. CURVE3 手动轨迹采集与模板算法

### 9A.1 采集器必须记录什么

手动轨迹的正样本不能只保存一串 x 数组。浏览器记录器应在验证码窗口 fresh 后、拖动前安装，并关联同轮 `/verify`：

```text
challenge id
source/display/DOM geometry
button getBoundingClientRect()
按下点相对 button 的 startOffsetX/startOffsetY
raw {x, y, t, type} sequence
track point count
start/stop time
verify request id/data/drives/ki 摘要
最终 verify response
```

推荐在页面主世界捕获 `mousedown/mousemove/mouseup` 和 touch 等价事件，同时 Hook XHR 的 `open/send/load`，只把请求 id 相同的 verify 响应绑定到当前拖动轮。记录器导出的 JSON 必须能区分：

```text
成功轮：verify.code == 200 && verify.success == true
4000：challenge 过期/失效
4001：基础字段、坐标或同轮状态错误
50000：进入行为检查但轨迹不被接受
```

不要只看 HTTP status；本页面上述错误都可能是 HTTP 200。

### 9A.2 四套坐标必须分开

当前 CURVE3 至少有四套坐标：

```text
source image coordinate: 还原背景图，常见 600x360
page display coordinate: Canvas，常见 300x180
slider DOM coordinate: button 的 left/top 与宽高
pointer coordinate: 鼠标按下点相对 button 的 offset
```

成功手动轨迹的 `{x,y}` 通常是页面 client 坐标。若 button 的 DOM 起点为 `(left, top)`，按下点为 `(start_x, start_y)`，则：

```text
pointer_offset_x = start_x - left
pointer_offset_y = start_y - top
start_x = left + pointer_offset_x
start_y = top + pointer_offset_y
track_target_x = start_x + displacement_x
track_target_y = start_y + displacement_y
```

本次 CloakBrowser 样本中，成功轮的 `startOffsetX` 约为 `20..36`、`startOffsetY` 约为 `12..25`；`displacementX` 约为 `149..235`，`displacementY` 约为 `5..108`。因此不能永久写死 `(31,20)`，也不能把 y 漂移假设为始终接近 0。窗口尺寸、缩放、CSS 或页面版本变化后必须重新测量。

### 9A.3 成功轨迹归一化

只对最终成功的手动轮做归一化。设第一点为 `(x0,y0,t0)`、最后一点为 `(x1,y1,t1)`：

```python
dx = x1 - x0
dy = y1 - y0
duration = t1 - t0
xNorm = (x - x0) / dx
yNorm = (y - y0) / (dy if dy else 1)
tNorm = (t - t0) / duration
```

同时保留：

```text
原始事件类型
点数
durationMs
位移 dx/dy
startOffsetX/Y
末端超调和回弹
释放前停留
```

重放时强制：

```text
第一点：start_x/start_y/t=0/type=down
中间点：时间严格递增
最后一点：target_x/target_y/t=duration/type=up
stopTime - startTime == duration
```

### 9A.3A 墙钟时序与 replay sleep

轨迹中的 `t` 是相对时间，但 `preRequest` 的 `startTime`、`stopTime` 是绝对毫秒时间戳。两者不能只在内存中满足差值关系，还必须和真实请求墙钟顺序一致。

错误实现：

```python
stop_ms = int(time.time() * 1000)
start_ms = stop_ms - duration_ms
# 立即 encrypt -> verify
```

这种写法虽然满足 `stop_ms - start_ms == duration_ms`，但 `start_ms` 可能早于本轮 `/generate` 完成时间，服务端会把轨迹识别为不可能的行为，常见结果是 `code=50000`。

正式实现应采用：

```python
generate_finished_ms = now_ms()       # 仅用于 sidecar 诊断
start_ms = now_ms()                   # 生成轨迹后、等待前记录真实起点
stop_ms = start_ms + duration_ms
sleep(duration_ms / 1000.0)           # 模拟声明的拖动耗时
plaintext = encode_pre_request(
    start_ms=start_ms,
    stop_ms=stop_ms,
    track=track,
)
data = runtime.encrypt(plaintext)
verify = post_verify(data, ...)
```

必须满足以下关系：

```text
generate request start
  < generate response received
  <= startTime
  < stopTime
  < verify request start
```

`verify` 前还会有明文编码、WASM 加密和 HTTP 调度耗时，因此不要求 verify 紧贴 `stopTime`，但不能让 `startTime` 早于 generate，也不能让 `stopTime` 晚于 verify 请求完成后的历史时间。sidecar 至少记录 `generateFinishedMs`、`startMs`、`stopMs`、`verifyRequestMs`、`declaredDurationMs` 和 `wallClockSleep`。

`--no-replay-sleep` 或等价的“只改时间戳、不等待真实时长”开关只能用于诊断，不能作为正式验收路径。正式 runner 默认等待完整轨迹时长；若需要压缩耗时，应重新采集并验证更短的真实成功模板，不能删除等待直接复用长模板。

不要把所有成功轮平均成一条固定 48 点直线。按 `displacementX`、`durationMs`、点数和 y 漂移做模板分桶；同一页面版本的真实成功轨迹比人工设计的匀速曲线更可靠。

### 9A.4 模板筛选和失败样本隔离

当前一次人工采集得到 14 轮，其中 9 轮 `code=200 && success=true`，1 轮 `4000`，4 轮 `50000`。只有 9 个成功轮进入模板池。成功模板覆盖：

```text
位移：149..235px
点数：45..151
时长：1291..3709ms
```

45 点/1291ms 的短模板曾有成功轮，但在后续自动复用中出现过 `50000` 和 `4001`，因此当前生产实验默认优先使用 `>=50` 点且 `>=1500ms` 的模板；短模板保留为诊断样本，不应作为唯一 fallback。这个过滤是本次页面的经验值，不是所有版本的硬阈值，页面更新后必须重新统计。

模板导入工具必须在写入模板池前检查：

```text
verify.code == 200
verify.success == true
track 至少包含 down/move/up
x 位移 > 0
时间单调且 duration > 0
round id 与 verify request id 一致
```

失败轮必须保留在 evidence，用于故障分类，但不能作为正样本、不能参与模板平均，也不能用同一 challenge 反复试不同轨迹。

### 9A.5 轨迹问题的单变量诊断顺序

当本地链路返回 `50000` 时，按以下顺序只替换一层：

1. 冻结 collector、HTTP profile、图片还原、attr1 曲线解析和候选。
2. 先检查墙钟时序：`startTime` 是否在 generate response 之后，`stopTime-startTime` 是否等于轨迹时长，正式路径是否真实等待了声明时长，verify 是否发生在 stop 之后。
3. 再检查 `trackCount`、明文长度、首点/末点、每个 `t` 是否严格递增。
4. 固定同一个成功模板，只替换目标 x，比较 `templateDisplacementX` 与 `targetDisplacementX`。
5. 固定目标 x，只替换点数/时长模板。
6. 最后才替换 `displacementY`、起点 offset、末端 overshoot/settling。

本次实验得到的可复用诊断：

```text
旧实现：start_ms = stop_ms - duration，立即 encrypt/verify
  -> 轨迹声明可能早于 generate
  -> 50000
修复：真实 start_ms + stop_ms=start_ms+duration + 等待完整 duration
  -> fresh code=200 && success=true
固定 pointer offset + drag_dy=0
  -> 50000
恢复成功轮 startOffsetX/Y 和 displacementY
  -> 仍需检查目标 x
视觉 219 vs 成功模板位移 222
  -> 直接提交 219：50000
  -> 保留成功位移 222：fresh code=200/success=true
视觉 200 vs 最近模板位移 190
  -> 盲目复用 190：4001
  -> 差异超过容差时缩放成功形状到视觉值：进入可接受路径
```

`50000` 优先指向行为层：点数过少、时长过短、终点偏移、y 漂移、直线化、缺少末端 settling 或模板与位移不匹配。`4001` 优先指向基础层：id、图片/pos、显示坐标、left/top、pointer offset、目标 x 和同轮 drives/ki。不要看到 `50000` 就重做 WASM，也不要看到 `4001` 就先增加轨迹点数。

### 9A.6 实证稳定性边界

本次已完成至少一轮本地 fresh `verify code=200 && success=true`，说明当前 `cw` collector、同轮 generate/verify、图片还原、CURVE3 识别、轨迹 codec 和 iv8 加密已经闭环。但独立 fresh 本地重复验收累计为 `6/9`，仍有 `50000` 和 `4001` 失败，因此只能写成“协议已打通、稳定性未证明”。

后续达到稳定性门前，建议：

```text
按 20+ 个 fresh challenge 统计
按位移区间建立模板桶
保存每轮 attr1、还原图、locator top-k 和真实成功位移
比较视觉 sliderValue 与真实 displacementX 的偏差分布
把失败 4001/50000 分层统计
只在同一资源 hash、同一浏览器 profile、同一页面几何下合并模板
```

## 10. 服务端验收与错误分层

唯一正式成功条件：

```json
{
  "code": 200,
  "success": true,
  "data": {"token": "..."}
}
```

`generate code=200` 只是当前 challenge 建立成功，不是验证码通过。`verify` 的 HTTP 200 也不是成功；必须同时检查 JSON 的 `code` 和 `success`。

常见结果解释：

```text
code=200 + success=true  -> 同轮验证码通过，进入正样本池
code=4000                -> challenge 失效；创建 fresh round
code=4001                -> 基础校验失败，优先检查 id/图片还原/坐标/left/top/同轮 drives/ki
code=50000               -> check fail，优先对照轨迹时序、终点偏移、y 漂移、模板和运行时状态
HTTP 403 环境异常       -> 优先检查 collector、UA/Client Hints、Session 和 HTTP/2 指纹一致性
```

诊断时分层，不要同时改所有变量：

1. 固定当前 collector 和 HTTP profile，先检查同轮 id、图片、`pos`、drives/ki。
2. 用失败轮保存的图检查 top-k 和 y 组，确认是否误选自然物或非目标候选。
3. 只替换目标 x 偏移，观察 `4001` 是否变化。
4. 只替换轨迹模板、点数、时长和 y 漂移，观察 `50000` 是否变化。
5. 每次实验创建 fresh challenge；不要对同一个已提交 challenge 重试。

## 11. 推荐证据结构

使用相对路径保存每轮产物，例如：

```text
evidence/pure_local_runs/<round>/
  pure_local_result.json
  <id>_background.jpeg
  <id>_background_restored.png
  <id>_template.png
  locator.json
  locator_debug.png
```

结果 JSON 至少记录：

```text
source / backend
round directory
challenge id and image metadata
generate drives/ki length and controlled hash
locator candidates and selected candidate
display gap
track template, point count, duration, start/end
verify data/drives/ki length and controlled hash
full final verify response
```

生产代码可以读取固定的 runtime/profile/成功轨迹模板资源，但不能读取 `evidence/round_*`、历史 challenge、旧 `data`、旧签名图片或固定 `ki` 作为输入。历史 evidence 只能用于离线回归、模板训练和诊断。

## 12. 交付入口

推荐将目标项目根目录的 `main.py` 作为 PyCharm 入口，内部调用 `src/pure_local.py`。无参数运行应：

```text
创建 fresh runtime
请求 fresh generate
下载并还原当前图片
定位并生成当前轨迹
加密当前明文
提交同轮 verify
打印服务端结果
```

命令行等价入口：

```powershell
python src/pure_local.py --allow-ambiguous --seed <seed>
```

`--allow-ambiguous` 只能作为实验开关。正式部署默认应在候选不明确时停止，或要求上层人工/模型选择 `candidate-index`，不能静默把 top-1 当作绝对真值。

## 13. 结论边界

以下结论可以写入正样本记录：

```text
本轮 generate code=200
当前 cw collector 输出被服务端接受
同轮 verify code=200 且 success=true
```

以下结论不能单独作为协议已恢复：

```text
drives/ki 长度正确
data 长度与历史样本相近
图片定位器 confidence=high
本地 __encrypt__ 不报错
HTTP status=200
一次浏览器手动通过但本地没有同轮请求证据
```

出现新页面版本、资源 URL、WASM hash、响应字段或状态码变化时，先重新做当前 collector 和同轮字段取证，再更新本分支；不要直接沿用旧文章中的 WASM 偏移、固定密钥或固定轨迹。

## 14. 快速复刻 SOP

以下顺序适合从空目录重新建立浏览器-free 实现。每个阶段都有停止条件；前一阶段未通过时不要继续调下一层。

### Stage 0：建立目标目录和依赖

使用一个独立目标目录，建议结构如下：

```text
project-root/
  main.py
  requirements.txt
  src/
    pure_local.py
    pure_protocol.py
    iv8_wasm_runner.py
    image_restore.py
    slider_locator.py
    curve3_model.py
    track_codec.py
    trajectory_store.py
    collect_trajectory.py
    browser_track_recorder.js
  js_reverse_cache/
    tianai/
      cw.js
      cw.wasm
      browser_env.json
      trajectory_templates.json
  evidence/
    tianai_capture/
    pure_local_runs/
```

安装依赖并立即做 import smoke：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import PIL,numpy,cv2,iv8; from curl_cffi import requests; print('deps: ok')"
```

本次已验证的最低依赖族：

```text
Python 3.10+
iv8 >= 0.1.4
curl_cffi >= 0.15.0
Pillow >= 11.0
numpy >= 1.26
opencv-python-headless >= 4.8
```

停止条件：依赖 import 不完整、iv8 初始化失败或 `curl_cffi` 不支持目标 impersonate 时，不进入协议调试。先固定 Python、iv8、curl_cffi 版本。

### Stage 1：重新确认页面版本和资源

在浏览器中打开目标页面，只做被动取证：

1. 清空 Network 和 Console 记录。
2. 打开验证码并点击生成，记录页面脚本版本、请求 URL 和当前 challenge。
3. 找到 `POST /v2/api/open/captcha/generate`，保存 query、JSON body、响应 JSON 的字段名。
4. 从 initiator 或资源请求中确认 collector 是旧 `main.wasm` 还是当前动态 `cw.js + cw.wasm`。
5. 下载当前页面实际使用的 `cw.js` 和 `cw.wasm` 到 `js_reverse_cache/tianai/`。
6. 保存 UA、Client Hints、语言、screen、DPR、plugins、Canvas/WebGL 和 script URL 列表到 `browser_env.json`。
7. 记录资源 SHA-256、页面脚本版本、capture 时间和 URL 到 `tianai_capture/version_manifest.json`。

当前已验证 baseline 的诊断信息如下，仅用于识别版本是否漂移：

```text
collector: cw.js + cw.wasm
cw.js SHA-256: 72026cde4b98da4f5a252ad5af7d46cdb82b3879fb5aa7442f88c76f496c2560
cw.wasm SHA-256: 7df8708d9ec305b6de15f433e75aabb8b2d26e3b6611def9e01a8d4187660d25
iv8: 0.1.4
HTTP impersonate: chrome146
observed source background size: 600x360
observed page display size: 300x180
observed drives diagnostic length: 1068
observed ki diagnostic length: 172
```

这些 hash 和长度不能替代当前取证，也不能单独证明 collector 正确。资源 hash 变化时，停止复用旧 `browser_env.json`、旧轨迹成功率和旧 WASM 结论，重新完成 Stage 1。

最小版本清单示例：

```json
{
  "origin": "https://captcha.tianai.cloud",
  "apiBase": "https://api.captcha.tianai.cloud",
  "generatePath": "/v2/api/open/captcha/generate",
  "verifyPath": "/v2/api/open/captcha/verify",
  "collector": "cw",
  "cwJsSha256": "<current hash>",
  "cwWasmSha256": "<current hash>",
  "python": "<version>",
  "iv8": "<version>",
  "curlCffi": "<version>",
  "impersonate": "chrome146"
}
```

### Stage 2：先打通 collector，不要马上做图片识别

在 isolated iv8 runtime 中按下面顺序处理：

```text
创建 JSContext(environment=browser_env)
 -> 加载含真实 script 标签的空页面
 -> 确认 document.scripts 是 HTMLCollection
 -> 暴露 Canvas/WebGL profile
 -> 读取 cw.js
 -> 禁止 cw.js 自动从网络加载 wasm
 -> 以当前 cw.wasm bytes 调用 wasm_bindgen.initSync
 -> 调用 __drives__()
 -> 调用 __ki__()
 -> 用固定测试明文调用 __encrypt__()
```

建议保留以下初始化检查：

```javascript
typeof window
window.__status__ === true
typeof window.__drives__ === 'function'
typeof window.__ki__ === 'function'
typeof window.__encrypt__ === 'function'
document.scripts && document.scripts.length
Object.prototype.toString.call(document.createElement('canvas').getContext('2d'))
```

iv8 0.1.4 的常见缺口是 `document.scripts` 返回 `null`。补环境时不要直接把它设成普通数组；创建与页面脚本数量一致的原生 `HTMLScriptElement`，并用 `document.getElementsByTagName('script')` 返回 collection。Canvas/WebGL 也优先使用 iv8 原生对象，只覆盖真实 profile 需要的指纹值。

collector smoke 的输出只保存摘要：

```json
{
  "status": true,
  "backend": "python-iv8",
  "collector": "cw",
  "drivesLength": 1068,
  "kiLength": 172,
  "encryptNonEmpty": true,
  "networkRequests": 0
}
```

停止条件：`cw.js` marker 不匹配、`initSync` 报错、`__drives__`/`__ki__` 为空、或者 runtime 在页面 API 访问处异常。不要先修改协议字段，也不要先调轨迹。

### Stage 3：用 collector 输出做 `/generate` admission

使用和浏览器一致的 HTTP profile。最低检查：

```text
curl_cffi.requests.Session(impersonate="chrome146")
Origin: https://captcha.tianai.cloud
Referer: https://captcha.tianai.cloud/
sec-ch-ua
sec-ch-ua-mobile
sec-ch-ua-platform
Content-Type: application/json;charset=UTF-8
```

用当前 `drives`、`ki` 发送：

```python
session = curl_requests.Session(impersonate="chrome146")
protocol = TianaiProtocol(
    api_base="https://api.captcha.tianai.cloud",
    origin="https://captcha.tianai.cloud",
    session=session,
)
challenge = protocol.generate(app_id, runtime.drives(), runtime.ki())
```

`generate` admission 必须同时满足：

```text
HTTP request succeeds
JSON code == 200
data is present
id/backgroundImage are present
SLIDER/CURVE3 的 data.shuffle.pos 是合法排列，或 CONCAT 的 data.randomY 落在当前源图高度内
普通 SLIDER 的 templateImage 存在、CURVE3 的 data.attr1 可解析为 20 个 token，或 CONCAT 的 type/randomY/背景尺寸完整
```

如果用本地 iv8 输出请求 `generate` 得到 `403 环境异常`，先检查 collector、profile、UA/Client Hints、Session 和 HTTP/2；不要先改轨迹。只有 admission 通过，才说明底层动态参数和传输画像进入可用状态。

### Stage 4：下载和还原当前图片

必须在同一 `curl_cffi.Session` 中下载当前响应提供的签名图片，不要重新拼 URL 或使用过期签名 URL。普通 `SLIDER` 下载 `backgroundImage + templateImage`；`CURVE3` 下载并按 shuffle 还原 `backgroundImage`；`CONCAT` 只下载当前原始错位 `backgroundImage`，不做 5x2 restore：

```python
if challenge.type == "CURVE3":
    background, restored = protocol.download_curve_assets(challenge, run_dir)
elif challenge.type == "CONCAT":
    background = protocol.download_concat_asset(challenge, run_dir)
else:
    background, template, restored = protocol.download_slider_assets(challenge, run_dir)
```

立即做文件检查：

```text
background: 当前服务器返回的 JPEG/PNG
普通 SLIDER template: 当前服务器返回的带 alpha 图片
CURVE3 attr1: 当前响应的 20-token 小数字段
SLIDER/CURVE3 restored: 使用当前 challenge.shuffle_pos 生成的 PNG
CONCAT randomY/seam: 当前响应字段和推导后的 source/display 拼接线
```

检查项：

```text
背景尺寸 == challenge.backgroundImageWidth/Height
普通 SLIDER 的滑块文件存在 alpha 通道、CURVE3 attr1 可按两两 token 解析，或 CONCAT randomY 合法
SLIDER/CURVE3 的 shuffle.pos 长度 == shuffle.x * shuffle.y 且是完整排列
SLIDER/CURVE3 restored 尺寸与原背景相同
CONCAT 的 stripDisplayHeight 与当前 DOM 实测高度一致
```

如果还原图明显是拼接错位，先检查 `pos` 的方向：当前结论是 `destination -> source`，不是 `source -> destination`。不要继续做定位或 verify。

### Stage 5：离线定位并保留不确定性

先按 `challenge.type` 分支：

```text
SLIDER -> template alpha/缺口定位，使用本节普通滑块流程
CURVE3 -> attr1 双二次贝塞尔 + sliderValue 全范围评分，使用 6A
CONCAT -> randomY 拼接线 + 多带宽结构评分 + 边界锚点 + NMS top-k，使用 6B
```

普通 SLIDER 从 template alpha 提取 bbox：

```text
bbox = (x0, y0, x1, y1)
mask = alpha[bbox] > threshold
expected_y = y0
```

先运行候选生成，再保存 JSON 和 debug image：

```powershell
python src\slider_locator.py `
  --background <round>\*_background_restored.png `
  --piece <round>\*_template.png `
  --output <round>\locator.json `
  --debug-image <round>\locator_debug.png `
  --top-k 8
```

候选排序至少使用：

```text
轮廓 Chamfer/shape
边缘结构
局部纹理
对比度
黑色/自然物 overlay 抑制
滑块内部背景 RGB/灰度低频相关
alpha bbox y 约束
```

二维局部峰值在目标 y 行不存在时，必须在 `expected_y ± tolerance` 上做密集 x scan。不能因为找不到二维峰值就回退到整张图的其他 y。对复杂背景保存：

```text
used_y_fallback or dense-y-scan
expected_y / y_tolerance
primary y cluster
candidates top-k
confidence
```

默认策略：

```text
confidence=high/medium -> 仍保存 top-k 并检查
confidence=ambiguous -> 停止生产提交
实验运行 -> 显式 --allow-ambiguous 或 --candidate-index
```

`--allow-ambiguous` 不是视觉正确证明。它只允许实验继续，以便通过服务端结果和保存的图片回溯候选质量。

### Stage 6：将源图坐标映射到页面几何

先分别定义三套坐标：

```text
source image coordinate: restored image, commonly 600x360
page display coordinate: commonly 300x180
slider DOM coordinate: left/top plus pointer offset
```

缺口源坐标转换：

```python
display_x = round(candidate_x * display_width / background_width)
display_y = round(candidate_y * display_height / background_height)
```

轨迹按钮起点不是 `(candidate_x, candidate_y)`。要从真实 DOM 或成功浏览器 trace 得到：

```text
left, top                  # tac.min.js preRequest 字段
pointer_offset_x/y         # 鼠标按下相对 slider button 的偏移
start_x = left + pointer_offset_x
start_y = top + pointer_offset_y
target_x = left + display_gap_x + pointer_offset_x + target_x_adjust
target_y = start_y + human_displacement_y
```

当前项目 baseline 使用了可配置的 `left/top`、pointer offset、`target_x_adjust` 和小幅 `drag_dy`，但这些不是平台永久常量。页面 CSS、缩放、窗口尺寸或版本变化时必须重新从真实成功轨迹校准。

特别注意：缺口图像 y 通常只用于找目标行，不能把 `candidate_y` 直接填入轨迹 y。真实成功手动轨迹的 y 漂移应来自人工轨迹数据，通常远小于图片源坐标的 y。

### Stage 7：建立成功轨迹模板

采集真实手动成功轮时，每轮保存：

```text
same-round challenge id
source/display geometry
raw x/y/t/type sequence
startOffsetX/startOffsetY
displacementX/displacementY
pointCount
durationMs
verify code/success
```

只把 `verify code=200 && success=true` 的轮次加入成功模板池。模板归一化：

```python
xNorm = (x - start_x) / displacement_x
yNorm = (y - start_y) / displacement_y
tNorm = t / duration_ms
```

保留原始事件类型和末端行为，不要只保留一条直线：

```text
按 displacementX 分桶
按 durationMs 分桶
按 pointCount 分桶
保留加速、停顿、overshoot、回弹、release hold
```

每轮选择模板：

```python
template = min(
    templates,
    key=lambda item: abs(item["displacementX"] - desired_display_dx),
)
```

缩放时强制：

```text
第一点 = start_x/start_y/t=0/type=down
中间点时间严格递增
最后一点 = target_x/target_y/t=duration/type=up
stopTime - startTime == duration
```

如果模板缺失，才使用 fallback 手工模板；fallback 只能作为诊断，不应成为长期唯一生产轨迹。

### Stage 8：生成 preRequest 明文

推荐直接复用经过逐字回归的 `track_codec.py`。如果从零重写，顺序和宽度必须固定：

```text
startTime       unsigned width=7
stopTime        unsigned width=7
bgWidth         unsigned width=3
bgHeight        unsigned width=3
templateWidth   unsigned width=3
templateHeight  unsigned width=3
left            unsigned width=3
top             unsigned width=3
trackCount      unsigned width=3
encodedTrack
captchaData    optional
```

每个轨迹点编码为 13 个字符：

```text
x field: signed, sign + 3-char base64 magnitude = 4 chars
y field: signed, sign + 3-char base64 magnitude = 4 chars
t field: unsigned 4-char base64 magnitude = 4 chars
type: 1 decimal event code
```

第一点编码绝对值；其余点先做相对前一点的 delta。编码表必须是：

```text
0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-~
```

编码方向是高位在前。signed 预处理的 sign 语义、固定宽度补零和负数处理要用正样本逐字回归，不要根据常见 base64 习惯改成另一套表。

可选 captchaData 的兼容实现：

```python
json_text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
char_codes = ",".join(str(ord(unit)) for unit in utf16_code_units(json_text))
plaintext += char_codes
```

Python 不能直接用 Unicode code point 替代 JS `charCodeAt`；非 BMP 字符必须拆成两个 UTF-16 code unit。每次修改 codec 都执行：

```text
decode(success_plaintext) -> encode -> exact equal
```

再执行固定 plaintext -> `__encrypt__` 的本地回归。密文每轮可以不同，不要求和历史密文逐字相同。

### Stage 9：当前 runtime 加密和同轮 verify

完整编排伪代码：

```python
run_dir = make_unique_run_dir()
runtime = Iv8TianAiRuntime(
    profile_path=Path("js_reverse_cache/tianai/browser_env.json"),
    fingerprint_path=Path("js_reverse_cache/tianai/browser_env.json"),
    backend="cw",
)
try:
    generate_drives = runtime.drives()
    generate_ki = runtime.ki()
    session = curl_requests.Session(impersonate="chrome146")
    protocol = TianaiProtocol(api_base=API, origin=ORIGIN, session=session)

    challenge = protocol.generate(APP_ID, generate_drives, generate_ki)
    assets = protocol.download_assets(challenge, run_dir)
    if challenge.type == "CURVE3":
        params = parse_curve3_attr1(challenge.attr1, challenge, display_geometry)
        locator = locate_curve3(assets.restored, params, top_k=8)
        candidate = select_slider_value(locator)  # stop when ambiguous in production
    else:
        locator = locate_slider(assets.restored, assets.template, top_k=8)
        candidate = select_candidate(locator)
    track = build_same_round_track(challenge, candidate, template_pool)
    plaintext = encode_plain_fields(..., track=track)
    data = runtime.encrypt(plaintext)

    verify_drives = runtime.drives()
    verify_ki = runtime.ki()
    response = protocol.verify(
        challenge, data, verify_drives, verify_ki,
    )
    assert response.get("code") == 200
    assert response.get("success") is True
finally:
    runtime.close()
```

注意：`generate_drives/generate_ki` 只能进入 generate 请求；`verify_drives/verify_ki` 只能进入 verify 请求。`data` 的 challenge id 不在加密明文中，必须由外层 verify JSON 绑定当前 `challenge.id`。

### Stage 10：PyCharm 交付入口

目标项目根目录放置 `main.py`，负责：

```text
把 src 加入 sys.path
无参数时注入 --allow-ambiguous
调用 pure_local.parser()
调用 pure_local.run()
返回服务端验收退出码
```

PyCharm 配置：

```text
Script path: <project-root>/main.py
Working directory: <project-root>
Python interpreter: 安装了 requirements.txt 的解释器
Parameters: 留空即可
```

右键运行后，结果应写入：

```text
evidence/pure_local_runs/<timestamp>/pure_local_result.json
```

命令行等价检查：

```powershell
python -m compileall -q src main.py
python src\iv8_wasm_runner.py
python main.py
```

`main.py` 的默认 `--allow-ambiguous` 只适合当前实验和验收。需要生产保护时，应删除默认注入，改为候选不明确直接退出，或由上层传入人工确认的 `--candidate-index`。

## 15. 阶段门与最小验收矩阵

每次复刻都应把结果按 gate 保存，不要把“代码能运行”写成“协议成功”：

```text
Gate 0: compile/import
  Python compileall、iv8 import、curl_cffi import 通过

Gate 1: collector smoke
  cw.js/cw.wasm 可离线加载，__drives__/__ki__/__encrypt__ 非空

Gate 2: generate admission
  当前 drives/ki 发送 fresh /generate 返回 code=200 和完整图片字段

Gate 3: image restore
  当前 pos 还原出正确尺寸，视觉样本可检查

Gate 4: codec regression
  已知成功 plaintext decode/encode 逐字相等

Gate 5: one-round verify
  fresh generate、当前图片、当前轨迹、当前 data、当前 verify 参数严格同轮
  verify code=200 && success=true

Gate 6: repeatability
  多个独立 fresh round 统计 code=200/success=true、4000、4001、50000
```

Gate 2 通过而 Gate 5 失败：优先查图片、坐标、轨迹和时间，不要回滚已通过 admission 的 collector。Gate 1 失败：不要调视觉。Gate 3 失败：不要生成轨迹。Gate 5 只成功一次：标记为“已实现但稳定性未证明”，继续做 fresh 多轮统计。

## 16. 故障排查矩阵

### `ModuleNotFoundError: iv8_wasm_runner`

原因通常是从项目根目录以包方式导入 `src`，而脚本入口预期 `src` 在 `sys.path`。解决：

```text
用 python src/pure_local.py
或运行根目录 main.py
或在测试命令临时设置 PYTHONPATH=src
```

不要为了这个错误复制第二套 runtime。

### iv8 导入时打印 native banner

这是 iv8 原生扩展的 stdout/stderr 输出，不是协议失败。需要 JSON 机器输出时，只在 import 阶段临时重定向 stdout/stderr，不要吞掉后续异常。

### `RuntimeError: unreachable` 来自 `main.wasm`

确认是否误走 legacy Go backend。当前生产 collector 是 `cw.js + cw.wasm`；先切换到 `backend="cw"` 并确认 `wasm_bindgen.initSync`。只有专门做旧页面诊断时才处理 `main.wasm`。

### `cw.js` 自动加载 wasm 失败

不要让 iv8 访问网络加载 wasm。读取 `cw.js` 后只替换已确认的 auto-start 调用，把当前本地 `cw.wasm` bytes 传给 `wasm_bindgen.initSync({module: ...})`。替换前检查 marker 出现次数必须为 1；出现 0 或多次说明资源版本变了，应回到 Stage 1。

### `/generate` 返回 403 环境异常

按以下顺序排查：

```text
1. cw.js/cw.wasm 是否来自当前页面
2. browser_env 是否对应当前 Chrome profile
3. document.scripts 数量和 script URL 是否合理
4. Canvas/WebGL 是否使用了原生宿主对象
5. UA、sec-ch-ua、语言、DPR 是否一致
6. curl_cffi 是否使用正确 chrome impersonate
7. 是否把浏览器 drives/ki 和本地 Session 混用了
```

不要先改 `left/top`、轨迹或图片候选；这些字段还没有进入 generate admission。

### `/verify` 返回 `4000`

这是 challenge 生命周期问题的第一嫌疑：

```text
generate 到 verify 等待过久
图片签名 URL 过期
使用了旧 challenge.json
verify id 与当前图片不一致
同一 challenge 已经提交过
```

每次创建新目录和新 Session，确认结果 JSON 中 `challenge.id`、图片文件名前缀和 verify body 的 `id` 相同。

### `/verify` 返回 `4001`

优先检查基础字段：

```text
verify id 是否同轮
data 是否由同轮明文加密
verify drives/ki 是否是 verify 前重新取的
图片是否按当前 pos 还原
candidate 的 x/y 是否误选
页面显示坐标是否误用源图坐标
left/top/pointer offset/target_x_adjust 是否过期
```

保存并比较 `selected_candidate`、`display_gap`、track start/end 和 verify JSON。不要先增加轨迹点数。

### `/verify` 返回 `50000 check fail`

基础请求已进入检查层，优先检查行为数据和墙钟时序：

```text
startTime 是否晚于 generate response
是否真的等待了 declaredDuration
stopTime - startTime 是否等于轨迹 duration
verify request 是否发生在 stopTime 之后
trackCount
每个 t 是否严格递增
最后一点是否精确等于目标
轨迹是否过短或过直
x 是否有合理加速、停顿、overshoot/settling
真实 y 漂移是否被固定值覆盖
模板点数/时长是否与成功样本分布一致
```

特别注意：`startTime = now - duration` 只是数学上补齐时长，不是有效的浏览器行为模拟；如果它让 startTime 早于本轮 generate，服务端可能直接返回 `50000`。正式路径应在生成轨迹后记录 startTime，设置 stopTime，再等待完整 duration 后加密提交。`--no-replay-sleep` 只能用于单变量诊断。

一次只替换轨迹模板或目标 x，保持 collector、图片、HTTP profile 不变。不要把 `50000` 直接归因于 WASM。

### 定位器选到黑色自然物或错误 y

检查：

```text
alpha bbox expected_y
候选是否属于同一 y cluster
content_score 是否参与排序
overlay_score 是否抑制黑色区域
是否触发 dense-y-scan
```

如果目标 y 没有二维局部峰值，固定 y 邻域做全 x 扫描。保留 top-k 和 debug image，不能静默采用全图 shape top-1。

### 轨迹模板越改越不稳定

回到最近一个已验证成功模板，冻结 collector、HTTP、图片算法和坐标参数。只建立一组实验矩阵：

```text
round id
candidate index
target x adjustment
template id
point count
track duration
Y displacement
server response
```

失败反例不能进入成功模板池；同一 challenge 不重复提交不同轨迹。

## 17. 版本更新与回归策略

当页面更新时，先做差分清单：

```text
页面脚本版本
generate/verify URL 和 method
响应字段和 shuffle 结构
cw.js/cw.wasm URL 与 hash
__drives__/__ki__/__encrypt__ 是否仍存在
document.scripts 数量
UA/Client Hints
图片尺寸、tile 数量、显示缩放
preRequest 字段顺序和 alphabet
verify 成功码和失败码
```

更新原则：

1. 保存旧版本资源和旧成功 bundle，只用于离线回归。
2. 新版本建立独立 `version_manifest.json` 和 fresh evidence 目录。
3. 先通过 Gate 1/2，再比较 codec、图片和轨迹。
4. 新版本资源变更时，不把旧 `ki`、旧 data、旧轨迹时间或旧模板当作当前输入。
5. 至少一轮 fresh verify 成功后才能更新正式 profile；多轮统计后才能宣称稳定。

## 18. 可复制的交付清单

交付给下一个逆向任务时，至少包含：

```text
[ ] target origin / api base / appId 来源
[ ] generate 和 verify 的 method、URL、body schema
[ ] 一轮 fresh challenge 的非敏感字段摘要
[ ] 当前 cw.js/cw.wasm URL、hash、版本时间
[ ] browser_env/profile 和完整 HTTP headers 摘要
[ ] collector smoke 输出摘要
[ ] generate admission 响应摘要
[ ] 图片 restore 算法和 pos 方向
[ ] source/display/DOM 三套坐标说明
[ ] plaintext 字段顺序、宽度、alphabet、event code
[ ] 成功轨迹模板格式和筛选条件
[ ] verify code=200 && success=true 正样本
[ ] 4000/4001/50000 失败样本分类
[ ] main.py/PyCharm 运行方法
[ ] 当前未解决的稳定性问题
```

如果以上清单缺少 collector 版本、同轮字段或最终成功响应，只能称为“取证片段”，不能称为可快速复刻的协议实现。
