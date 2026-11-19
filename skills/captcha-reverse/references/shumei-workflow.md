# 数美滑块流程

来源参考案例：数美滑块逆向项目。

## 文件角色

1. `数美滑块.py`：完整串联 register、OCR、轨迹、参数生成和 fverify。
2. `get_params.js`：用 DES + Base64 生成数美 `fverify` 所需参数。
3. `鼠标移动轨迹.py`：备用自然鼠标轨迹生成器。
4. `sm.js`：数美原始/参考 JS bundle。
5. `extract_final.js`：用于分析 `sm.js` 字符串数组和加密配置的辅助脚本。
6. `bg.jpg`、`fg.jpg`、`result.png`：调试图片产物。

## 请求 register

接口：`https://captcha1.fengkongcloud.cn/ca/v1/register`。

关键请求头：

1. `Origin: https://console.ishumei.com`
2. `Referer: https://console.ishumei.com/`
3. `Sec-Fetch-Dest: script`
4. `Sec-Fetch-Mode: cors`
5. `Sec-Fetch-Site: cross-site`
6. `User-Agent`、`sec-ch-ua`、`sec-ch-ua-platform` 与目标浏览器一致。

`captchaUuid` 生成方式：

```python
def generate_custom_code(random_length=16):
    time_str = datetime.now().strftime('%Y%m%d%H%M%S')
    chars = string.ascii_letters + string.digits
    return time_str + ''.join(random.choice(chars) for _ in range(random_length))
```

关键参数：

1. `organization=d6tpAY1oV0Kv5jRSgxQr`
2. `appId=default`
3. `rversion=1.0.4`
4. `data={}`
5. `callback=sm_<当前毫秒时间戳>`
6. `channel=default`
7. `lang=zh-cn`
8. `captchaUuid=<本轮生成值>`
9. `model=slide`
10. `sdkver=1.1.3`

响应是 JSONP：

```python
data = json.loads(re.findall(r'sm_\d+\((.*?)\)', response.text)[0])
bg_url = 'https://castatic.fengkongcloud.cn' + data['detail']['bg']
fg_url = 'https://castatic.fengkongcloud.cn' + data['detail']['fg']
rid = data['detail']['rid']
```

## 计算距离

数美案例中：

```python
bg = requests.get(bg_url).content
fg = requests.get(fg_url).content
det = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
result = det.slide_match(fg, bg, simple_target=True)
x = result['target'][0] / 2
```

注意：

1. `fg` 是滑块图，`bg` 是背景图。
2. 当前实现把 OCR 识别距离除以 `2`，这是图片缩放/坐标系换算点；迁移站点时要用成功样本确认是否仍需除以 `2`。
3. 图片下载后先验证内容类型和尺寸，避免 OCR 处理错误页。

## 生成轨迹

主脚本实际使用 `get_track(distance)`，不是备用的 `generate_mouse_path()`。

轨迹生成逻辑：

1. 初始 `x=[0,0]`、`y=[0,0,0]`、`z=[0]`。
2. 用 `np.linspace(-pi/2, pi/2, random.randrange(20, 30))` 生成正弦序列。
3. 加 `10-14` 像素随机超调，再回落到目标距离。
4. `y` 轴在 `0-30` 范围内上下轻微抖动。
5. 时间戳每步约增加 `100ms`，少量点增加 `1-2ms`。
6. 输出 `track = [[x, y, timestamp], ...]`，`times = track[-1][-1] + random.randint(1, 5)`。

备用轨迹 `鼠标移动轨迹.py` 使用 easeOutCubic，可在主轨迹被风控时作为替换参考。

## 生成 fverify 参数

入口：

```js
get_params(res, track, timer, rid)
```

参数含义：

1. `res`：滑动距离，当前案例为 `ocr_x / 2`。
2. `track`：轨迹数组 `[[x,y,t], ...]`。
3. `timer`：滑动总耗时。
4. `rid`：register 返回的同轮 `rid`。

`get_params.js` 主要使用 DES + Base64：

```js
_0x6ebde7(_0x4bf4de(key, value, 1, 0))
```

字段来源：

1. `ww = enc('36937571', 'default')`
2. `bb = enc('bd7d3fb7', 'default')`
3. `vj = enc('b7cdc6b2', 'zh-cn')`
4. `hq = enc('42ccd3c8', '11')`
5. `wi = enc('363f9192', String(res / 300))`
6. `gq = enc('ffd9ef14', JSON.stringify(track))`
7. `vs = enc('80fefdd1', String(timer))`
8. `lx = enc('61ad6eff', '300')`
9. `es = enc('620302a1', '150')`
10. `jq = enc('118c4021', '1')`
11. `zm = enc('da718702', '0')`
12. `tx = enc('786ef59e', '-1')`

固定明文字段：

1. `sdkver=1.1.3`
2. `organization=d6tpAY1oV0Kv5jRSgxQr`
3. `ostype=web`
4. `rid=<本轮rid>`
5. `callback=sm_<当前毫秒时间戳>`
6. `act.os=web_pc`
7. `protocol=206`
8. `rversion=1.0.4`

主脚本在 JS 返回后补：

```python
params['captchaUuid'] = captcha_uuid
```

## 请求 fverify

接口：`https://captcha1.fengkongcloud.cn/ca/v2/fverify`。

流程：

1. register 获取 `bg/fg/rid`。
2. OCR 得到 `x`。
3. 生成 `track/times`。
4. 调用 `get_params(x, track, times, rid)`。
5. 补 `captchaUuid`。
6. GET `fverify`。
7. 响应文本包含 `PASS` 才算通过。

## 空间推理 spatial_select 经验

来源参考案例：`./072-数美空间推理`，目标页面 `https://www.ishumei.com/trial/captcha.html`，实测 10/10 PASS。

### 请求链路

空间推理题不要先依赖浏览器截图。优先抓包拿原始题面资源：

1. `GET https://captcha1.fengkongcloud.cn/ca/v1/conf`
2. `GET https://captcha1.fengkongcloud.cn/ca/v1/register?model=spatial_select`
3. 下载 `https://castatic.fengkongcloud.cn` + `detail.bg` 原始背景图。
4. `GET https://captcha1.fengkongcloud.cn/ca/v2/fverify?protocol=207`

`register` 关键字段：

1. `detail.bg`：空间题原图路径。
2. `detail.bg_width=600`、`detail.bg_height=300`：原始图片尺寸。
3. `detail.order[0]`：中文题目，例如“点击图中最小的红色圆柱体”。
4. `detail.rid`、`detail.k`、`detail.l`：同轮验证状态与 SDK 密钥材料。

`captchaUuid`、`rid`、图片与最终 `fverify` 必须同轮。响应是 JSONP，使用 `response.content.decode('utf-8')` 再解析，避免 Windows/requests 默认编码把中文题目解坏。

### 识别策略

空间题当前 demo 不需要复杂模型。优先使用原始 `600x300` 图片做传统 CV：

1. 从 `order` 解析颜色、形状和空间关系：如 `绿色/蓝色/红色/黄色/橙色`、`圆柱体/球体/锥体/立方体/长方体`、`最小/最大`。
2. OpenCV 转 HSV，不要用精确 RGBA；用容差色域阈值分割目标颜色。
3. 对 mask 做开闭运算，`findContours` 或连通域提候选。
4. 用 `area`、`boundingRect`、宽高比和简单形状规则过滤候选。
5. `最小` 选面积最小候选，`最大` 选面积最大候选。
6. 取候选框中心作为原图点击点。

坐标系必须分清：CV 在 `600x300` 原图上定位，但 `fverify` 提交使用展示坐标 `300x150`。换算：

```python
submit_x = round(raw_x * 300 / bg_width)
submit_y = round(raw_y * 150 / bg_height)
```

### spatial_select fverify 参数

实测 SDK 版本：`rversion=1.0.4`、`sdkver=1.1.3`、`protocol=207`。

成功包解密锚点：

```js
ox = [[0.40466654459635415, 0.3146665445963542, 1786520784534]]
sp = [[0.40466654459635415, 0.3146665445963542, 1786520784534]]
```

即 `ox` 和 `sp` 明文相同，都是归一化点击坐标与点击时间戳：

```js
selected = [[submit_x / 300, submit_y / 150, Date.now()]]
```

字段与加密 key：

1. `fr = enc('60c83964', 'default')`
2. `eg = enc('3f6a0c6f', 1)`
3. `ox = enc('b06aad3b', selected)`
4. `gt = enc('ed4576ba', endTime - startTime)`
5. `sn = enc('cfa425d6', 300)`
6. `gr = enc('3954fb84', '11')`
7. `te = enc('ef4bef0b', 'default')`
8. `sp = enc('735c85df', selected)`，注意 v1.0.4-207 里不是旧猜测 key。
9. `xb = enc('04a24a06', 150)`
10. `lo = enc('4f3dbadb', -1)`
11. `xz = enc('cfcad8db', 0)`
12. `fq = enc('5992a161', 'zh-cn')`
13. 明文字段：`rid`、`captchaUuid`、`protocol=207`、`rversion=1.0.4`、`sdkver=1.1.3`、`organization=d6tpAY1oV0Kv5jRSgxQr`、`ostype=web`、`act.os=web_pc`、`callback=sm_<毫秒时间戳>`。

数美 DES/Base64 形式同滑块分支：

```js
base64Encode(DES(key, JSON.stringify(value), 1, 0))
```

`gt` 需要和行为时间一致；纯协议可生成合理 `startTime/endTime`，但不要让轨迹时间超过请求发送时刻。

### spatial_select 排查

1. `fverify` 固定 `REJECT`：先抓一轮浏览器手动 PASS 正样本，解密对照 `ox/sp/gt/sn/xb`，不要同时改识别、行为和 headers。
2. `sn/xb` 错误：空间题原图是 `600x300`，但提交声明尺寸是 `300/150`。
3. `sp` 错误：v1.0.4-207 使用 `735c85df`；若 SDK 版本变化，重新从 `getMouseAction` 字段映射提取 key。
4. `ox/sp` 坐标错误：明文是归一化坐标，不是像素坐标，也不是 `[[x,y]]`。
5. 中文题面乱码：用 `response.content.decode('utf-8')` 解析 JSONP。
6. 识别误点：保存原图、mask、候选框和最终 submit 坐标，优先调 HSV 阈值、候选合并和形状过滤。
7. 成功必须以 `fverify` 响应 `riskLevel=PASS` 为准；本地识别命中或 HTTP 200 不算通过。

## 排查清单

1. register 返回异常：检查 `organization`、`captchaUuid`、`callback`、`Origin/Referer`。
2. 图片距离异常：检查 `fg/bg` 是否拿反、是否需要除以 `2`、图片是否被 CDN 返回错误内容。
3. fverify 不通过：检查 `rid` 和 `captchaUuid` 是否同轮，`gq/ox` 是否使用当前行为数据，`vs/gt` 是否使用当前耗时。
4. 参数缺失：滑块确认 `get_params.js` 返回的 `ww/bb/vj/hq/wi/gq/vs/lx/es/jq/zm/tx` 都存在；空间题确认 `fr/eg/ox/gt/sn/gr/te/sp/xb/lo/xz/fq` 都存在。
5. 迁移到新站点：优先确认 `organization`、`sdkver`、`rversion`、图片坐标缩放、请求头和加密 key 是否变化。
