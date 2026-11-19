# Vaptcha V4 手势轨迹协议与离线识别工作流

本参考记录 Vaptcha V4 一类“按图片中的发光轨迹手绘”的验证码。目标是把当前轮的 `config -> knock -> PoW -> image -> validate` 变成可重复的 browser-free Python 流程，同时保留图片识别、人工采集、服务端验收和失败诊断的边界。

适用时，将本文件中的路径理解为目标项目根目录下的相对路径，例如：

```text
vaptcha_v4_protocol.py
iv8_vaptcha_env.py
trajectory_vision.py
trajectory_collector.py
trajectory_segmentation.py
trajectory_live_validate.py
js_reverse_cache/
evidence/
```

不要把本机盘符、用户目录、临时目录、历史 token、cookie、`knock`、`dfu` 或完整 wire body 写入 skill、参考文档或长期日志。

## 1. 识别信号与路由

出现以下组合时，优先按 Vaptcha V4 手势轨迹分支处理：

- 站点页面或脚本出现 `VaptchaCore`、`verify.html`、`pow.js`、`core.js`。
- 请求路径包含 `/api/config`、`/api/knock`、`/api/validate`。
- wire body 是 `{v: 1, d: <URL-safe base64>}`，解码后是按字段数组排列的对象。
- `knock` 响应含 `pow_start`、`salt`、`result`、`trajectory`。
- `trajectory` 在 `knock` 响应里是图片地址，在 `validate` 请求里是编码后的用户轨迹。
- 验证图片是 5x2 分块乱序图，PoW 命中一个 10 位数字顺序字符串后才能恢复。
- 最终响应使用 `result=true`、非空 `token` 和通常非空 `dfu` 表示通过；`verification_failed` 表示协议到达服务端但轨迹没有通过。

只要目标包括完整 `knock` 到 `validate` 或通过后的业务回放，主责是 `captcha-reverse`。如果用户只要求 YOLO、分割模型、离线识别或推理速度，并明确排除协议恢复，才把模型部分交给 `captcha-vision`；模型交付不替代服务端验收。

## 2. 当前轮状态机

每一轮必须建立新的状态容器，不能把相邻轮或历史抓包字段混合：

```text
页面/站点配置
  -> config
  -> 同一 Session 的环境指纹与 knock 参数
  -> knock
  -> pow_start + salt + target
  -> solve_pow
  -> 下载 trajectory 图片
  -> 按 order 恢复 5x2 图片
  -> 生成有序 {x, y, t} 轨迹
  -> validate
  -> 检查 result/token/dfu
```

必须同轮绑定的字段：

- `tag`、初始 config、`knock` 实例值。
- `cachedKnockParams` 或等价环境对象。
- 指纹字段、`fingerprint_version`、`canvas_fingerprint`、WebGL 字段、屏幕字段和语言时区。
- `pow_start`、`salt`、PoW target、命中的 `order`、`nonce` 和 `pow_actual_ms`。
- 图片下载地址和恢复图片。
- `trajectory.encoded`、`trajectory.totalDuration`、`knock`、`vid`、`tag`、`dfu`。
- 最终 `validate` 响应和 token/dfu。

`validate` 是一次性状态操作。对同一个 `knock` 重复提交，出现 `knock_invalid` 或已消费错误时，不要把它当成轨迹实验结果；重新创建完整 fresh round。

## 3. Wire 编码与字段顺序

V4 wire 层不是普通 JSON 参数拼接。当前形态是：

```python
{"v": 1, "d": urlsafe_base64(json.dumps(field_array))}
```

字段数组的位置比 JSON 对象键名更重要。目标项目应保留明确的字段列表，例如：

```python
KNOCK_FIELDS = [
    "vid", "knock", "tag", "dfu", "pow_test", "pow_plan_ms", "attack_code",
    "fingerprint_version", "fingerprint_collect_ms", "fingerprint_wait_ms",
    "fingerprint_from_cache", "webgl_vendor", "webgl_renderer",
    "canvas_fingerprint", "dfa_components", "screen_width", "screen_height",
    "screen_refresh_rate", "device_pixel_ratio", "color_depth",
    "hardware_concurrency", "device_memory", "timezone", "language",
    "webgl_extensions_hash", "capabilities", "dfb_components", "dfc_webdriver",
    "dfc_is_headless", "dfc_bad_gpu", "dfc_components", "dfc_score", "dfc_level",
    "dfc_reasons", "sr", "dpr", "sw", "sh", "lang", "tz", "dfa", "dfb", "dfc",
    "ja3", "uid",
]
```

`trajectory` 和 `pow` 在 wire 数组中有特殊压缩形态：

```text
trajectory -> [points, encoded, totalDuration]
pow        -> [nonce, order]
```

当前页面的 `validate` 通常只填 `encoded` 和 `totalDuration`，`points` 位置由 wire helper 表示为空值。不要把 Python 字典直接发给接口，也不要改变字段数组顺序。

## 4. 指纹与 Python/iv8 边界

推荐边界：

- Python `requests.Session` 或项目指定的 HTTP Session 负责 config、knock、图片和 validate。
- iv8 只负责执行当前站点的 `core.js`、`pow.js` 和指纹采集逻辑。
- 浏览器或 Cloak 只用于取证、校准和保存正样本，不作为最终识别器。
- 同一轮中的 `cachedKnockParams`、`knock` 和 `validate` 必须复用同一个状态对象。

已有项目通常可从以下入口复用：

```text
iv8_vaptcha_env.py
utils/iv8_silent.py
vaptcha_v4_protocol.py
```

如果 iv8 原始指纹与已验收浏览器环境不一致，先区分两种问题：

1. `knock` 阶段就失败：优先检查指纹、canvas、WebGL、UA、Client Hints、Origin/Referer 和 Session。
2. `knock` 成功而 `validate` 返回 `result=false`：协议状态已经到达服务端，优先检查图片恢复、轨迹方向、端点、采样节奏和轨迹内容。

不要同时修改指纹、轨迹、TLS、headers 和时序。每轮只替换一个变量，并保存最终业务响应。

## 5. PoW 与图片恢复

PoW 使用当前 `knock` 响应的三个值：

```text
candidate 从 pow_start 开始递增
sha256(str(candidate) + salt).hexdigest() == result
命中值作为 order 和 nonce
```

不要使用旧抓包中的 `order`。成功求解后，`order` 是 10 位数字字符串，每个数字表示原始 5x2 tile 的索引排列。

恢复流程：

1. 下载 `challenge["trajectory"]` 的原始 PNG。
2. 按宽度等分 5 列、按高度等分 2 行。
3. 使用当前 PoW `order` 做逆置换，把 10 个 tile 放回原始位置。
4. 保存 shuffled 原图和 restored 图片，便于回溯。
5. 确认恢复图片尺寸、颜色模式和内容不是错误页。

常见错误：

- 把 `order` 当正置换使用，导致图片内容错位。
- 使用上一轮的 PoW 顺序恢复当前图片。
- 下载响应不是图片却继续交给视觉模型。
- 只保存恢复图，不保存 shuffled 图和当前轮 state，后续无法诊断。

## 6. 轨迹编码与时序

轨迹点使用：

```python
{"x": int, "y": int, "t": int}
```

当前 V4 编码按每个点写入：

```text
x: 4 位十六进制
 y: 4 位十六进制
t: 首点为 00000，后续点写相邻时间差的 5 位十六进制
```

页面还会先过滤小移动，再编码。复现时必须保持：

- 起点和终点保留。
- 只有小于页面阈值的微小移动才被过滤。
- 时间单调递增，不能让平滑或随机抖动产生负时间。
- `totalDuration` 等于最终过滤轨迹的末点时间。
- 点数、采样间隔和时长来自真实样本 profile，而不是随便写固定值。

本次经验：

- 300 轮本地手绘轨迹的点数中位数约 146，但服务端最终编码前的 profile 点数中位数约 77。
- 直接把 YOLO 路径当最终点序列提交不稳定；使用真实 profile 做重采样、轻微抖动和端点保持更接近页面行为。
- 轨迹几何距离小不代表通过。方向反了、起终点反了、时序不自然或服务端需要的轨迹区域未覆盖，都可能返回 `verification_failed`。

## 7. 离线图片识别路线

目标不是让模型直接预测一串点，而是：

```text
图片
  -> 轨迹区域 mask
  -> 最大/相关连通区域
  -> skeletonize
  -> 端点与分支
  -> 路径候选
  -> 保留端点顺序
  -> 重采样与 B-spline
  -> 轨迹点
```

当前可复用入口：

```text
trajectory_vision.py
trajectory_segmentation.py
```

模型标签应表示服务端可能接受的轨迹走廊，而不是人工鼠标中心线的唯一像素：

```text
人工中心线
  -> 按半宽 radius 膨胀
  -> 轨迹区域 mask
  -> YOLO-seg polygon
```

本次使用约 300 轮本地图像，训练集/验证集按完整轮次切分为 240/60，标签半宽使用 10 像素以吸收手滑偏差。这个半宽只是监督策略，不是服务端真实阈值的证明。

看不清、无法确定路径的图片：

- 可以保留作困难样本或 hard negative。
- 不要把随意猜的线当作高质量正标签。
- 如果无法人工确定起点、终点或路径分支，应在 manifest 中标记质量，而不是静默混入精确训练集。
- 训练前统计空轨迹、异常短轨迹、异常长轨迹和未验收样本。

YOLO detection 框不能表达环线、交叉和线头线尾。若采用 YOLO，优先使用 YOLO-seg；但它仍然只是 mask 候选器，必须由现有骨架/路径后处理生成有序轨迹。

## 8. 本地人工采集

当需要扩大样本，不要让用户在浏览器验证码组件中操作并试图从页面截图恢复轨迹。更稳定的采集方式是：

```text
直接 API 获取 fresh config/knock/image/PoW
  -> 本地恢复图片
  -> OpenCV 窗口采集鼠标轨迹
  -> 保存 image/state/points/manifest
```

推荐项目入口：

```text
trajectory_collector.py
```

采集器应做到：

- 每轮重新请求 config、指纹、knock、PoW 和图片。
- 每轮保存 shuffled 图、restored 图、原始鼠标点、state 和 manifest。
- `S` 保存当前轮，`R` 重画，`Q/Esc` 停止。
- 支持只采集不 validate；未在线验收样本要用明确字段标记。
- 不因为 validate 失败而丢弃人工轨迹；失败响应和轨迹必须分开保存。
- 批量采集目标可以是约 300 轮，但仍按轮次切分 train/val，不能把同一轮增强图拆到两边。

如果目标是研究视觉识别而不是协议验收，可以不提交每一轮 validate。此时构建训练集时必须显式允许未验收样本，例如项目脚本的 `--include-unverified`，并在报告中写明 `unverified` 数量。

## 9. Fresh 服务端验收

在线验收必须使用新的 challenge 批量统计，不要用一轮结果下结论。推荐每轮记录：

```text
trial id
fresh challenge 是否成功
PoW order
模型置信度
原始点数/提交点数
图片和轨迹 overlay
validate 请求摘要
最终 response.result
response.token 是否非空
response.dfu 是否非空
错误类型
```

成功判据：

```text
HTTP 请求成功
并且业务响应 result == true
并且 token 非空
并且通常 dfu 非空
```

下列情况都不能单独算成功：

- HTTP 200。
- 返回 JSON。
- `verification_failed` 以外没有异常。
- 模型置信度高。
- 离线 mask mAP 高。
- 轨迹和人工线的对称距离小。
- token 字段存在但 `result` 为 false。

推荐验证入口：

```text
trajectory_live_validate.py
```

每个 fresh challenge 只提交一次。要比较两个算法，使用两个独立批次，或者在同一批次设计明确的 fresh A/B；不要对同一个 knock 先后提交两条轨迹。

本次经验的基线统计：

```text
原始模型路径 + profile 时序
批次 1：2/10
批次 2：1/10
合计：3/20
```

这只是当前数据、版本、指纹和账号状态下的实验基线，不是站点永久通过率。

## 10. 失败分类与诊断顺序

### A. `knock_invalid` 或状态错误

优先判断是否重复使用了同一 challenge。检查：

- 是否复用了旧 `knock`。
- 是否重复调用 validate。
- 是否混用了不同轮的 `dfu`、PoW、图片或 tag。
- 是否多个测试进程共享了同一个缓存 state。

### B. `verification_failed` 且轨迹明显错误

优先处理视觉路径：

- 分割区域是否覆盖真实发光带。
- 是否只取了最长路径而漏掉前后段。
- 是否把主体纹理当成轨迹。
- 是否选错交叉分支。
- 是否起点或终点落在主体上，而不是轨迹线头。

### C. 几何路径接近但服务端拒绝

不要立刻继续训练。检查：

- 起点/终点方向是否反了。
- 轨迹的第一点和最后一点是否落在正确线头/线尾。
- 过滤后是否意外删除了关键端点。
- 时长、点数和采样间隔是否接近真实 profile。
- 提交坐标是否在服务端实际容忍走廊内。
- 请求中 `order`、`knock`、`trajectory` 是否同轮。

本次失败复核显示：一批失败样本中，4 轮几何形状接近但方向反了；另一批主要是路径被截短或选错分支。对称距离指标会掩盖方向问题，因此必须额外计算直接端点距离和反向端点距离。

### D. 模型实验线上变差

如果离线候选 oracle 变好但 fresh 通过率变差：

1. 立即停止把实验排序器作为默认路径。
2. 保留实验批次、请求、overlay 和响应。
3. 恢复最后一个已验证基线。
4. 把候选排序作为离线分析，不把离线 oracle 当作服务端成功证明。
5. 下一次只改变一个变量重新 fresh 测试。

本次候选路径排序器的离线验证略有改善，但独立 fresh A/B 为 `0/10`，因此已回退到原始基线。这是一个必须保留的工程规则：线上验收优先于离线指标，失败实验不能污染默认路径。

## 11. 推荐项目文件布局

所有路径均相对于目标项目根目录：

```text
vaptcha_v4_protocol.py
iv8_vaptcha_env.py
trajectory_vision.py
trajectory_collector.py
trajectory_segmentation.py
trajectory_live_validate.py
trajectory_endpoint_ranker.py       # 可选实验
trajectory_route_ranker.py          # 可选实验
js_reverse_cache/
  trajectory-collection/
  trajectory-seg-dataset/
  live-model-validation/
evidence/
```

建议每次 live 试验使用独立目录：

```text
js_reverse_cache/live-model-validation-r1/
js_reverse_cache/live-model-validation-r2/
```

不要覆盖上一批 fresh 结果；否则无法比较基线、A/B 和回滚效果。

## 12. 快速复用清单

遇到同一站点或同一 Vaptcha V4 版本时，按下面顺序执行：

1. 检查 `config/knock/validate` URL、wire 版本和字段数量。
2. 读取当前页面资源，确认 `core.js`、`pow.js` 和版本变化。
3. 用同一 Session 建立 fresh config、指纹、knock。
4. 解码本轮 `pow_start/salt/result`，求出本轮 `order`。
5. 下载并恢复图片，保存 shuffled/restored/state。
6. 先用现有视觉基线生成路径，不立即引入新排序器。
7. 使用真实 profile 重采样轨迹，保留端点和单调时间。
8. 对一个 fresh challenge 只提交一次 validate。
9. 以 `result=true + token/dfu` 作为成功证据。
10. 至少跑两批独立 fresh 轮次，再报告通过率。
11. 失败时先分类状态复用、方向、端点、分支、时序和指纹，不要同时改多层。
12. 任何线上变差的视觉实验都回滚到最近一次已验证 baseline。
