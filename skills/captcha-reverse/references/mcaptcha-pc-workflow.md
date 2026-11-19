# mCaptcha PC 滑块流程

## Contents

- [触发信号](#触发信号)
- [验证码状态机](#验证码状态机)
- [图片与坐标](#图片与坐标)
- [加密字段](#加密字段)
- [轨迹与 JSON](#轨迹与-json)
- [指纹与响应判定](#指纹与响应判定)
- [诊断顺序](#诊断顺序)

本 reference 沉淀一个 PC 版 `mCaptcha` 验证码案例。它只覆盖验证码本身，不覆盖验证码通过后的业务接口。该案例尚未满足跨两个独立任务的 promoted experience-card 门槛，因此所有常量都必须用当前 bundle、当前图片和当前服务端响应复核。

## 触发信号

同时出现以下任意两组信号时进入本 reference：

- `mCaptcha.pc.min.js`、`mCaptcha.min.js`、`new MCaptcha`、`UserOpListener`
- `captchasInit`、`capTicket`、`capKey`
- `/mCaptcha/key`、`/mCaptcha/info/`、`/mCaptcha/validate`
- `clickCaptcha/validate`、`validData`、`CryptoJS.AES.encrypt`
- `fp.min.js`、`Fingerprint`、canvas 指纹、40 个 `13x60` tile

不要因为普通 `mCaptcha` 文本就跳过家族确认；先用当前网络、源码和响应三类证据确认是 PC 版滑块。

## 验证码状态机

每轮都创建新状态，按以下顺序执行：

```text
页面首跳/页面会话
  -> 页面侧 captcha 初始化，取得 capTicket
  -> /mCaptcha/key，取得 capKey
  -> /mCaptcha/info/<capKey>，取得 loc 和 img
  -> 下载当前 img，按 loc 还原题面
  -> clickCaptcha/validate（按下时的行为前置调用，可为空响应）
  -> /mCaptcha/validate，取得通过结果和 rand
```

`capTicket`、`capKey`、`loc`、图片、轨迹明文、加密 key 和最终响应必须属于同一轮。验证码服务端可能在约一分钟量级的等待后使本轮失效；不要在抓完图后长时间停留，也不要跨轮拼接字段。

## 图片与坐标

当前案例的 bundle 固定值为背景 `260x120`、20 列、2 行、每块 `13x60`，并在原图右侧放置一个约 61px 宽的带 alpha 拼图块。`loc` 是 destination tile 到 source tile 的映射：

```python
for dst_index, source_index in enumerate(loc):
    sx = (source_index % 20) * 13
    sy = 0 if source_index < 20 else 60
    dx = (dst_index % 20) * 13
    dy = 0 if dst_index < 20 else 60
    paste(src.crop((sx, sy, sx + 13, sy + 60)), (dx, dy))
```

不要把乱序原图直接交给定位器。先校验图片确实是带 alpha 的验证码图片，再还原背景。拼图块显示时使用 `background-position: -260px 0`；定位时应使用拼图可见轮廓与还原背景的结构边界，而不是透明画布左上角。

本案例确认了三套坐标：

- `D`：还原图中缺口主矩形的左坐标，也是 `validData.length`。
- `e`：页面 slider/cubic 的 CSS 水平位移，当前关系为 `D = e + 9`。
- 行为点坐标：`UserOpListener` 记录的页面 `clientX/clientY`，不等同于 `D` 或 `e`。

`+9` 是当前 bundle 的已验证指针修正，不是所有 mCaptcha 版本的永久常量。若图片尺寸、拼图块位置或 CSS 常量变化，停止旧定位器并用一轮成功/失败对照重新校准。

## 加密字段

`X(capTicket)` 按 JavaScript 的 0 基 `substring` 精确切片：

```python
key = (
    ticket[1:3] + ticket[10:13] + ticket[20:22]
    + ticket[26:31] + ticket[21:25]
)
```

`Encrypt(plaintext, key)` 为：

```text
UTF-8 plaintext
  -> AES-CBC-PKCS7
  -> key = IV = X(capTicket)
  -> Base64(ciphertext only)
```

不要使用 CryptoJS 默认 OpenSSL salted string；页面取的是 `ciphertext` 再单独 Base64。`validData` 的明文字段为紧凑 JSON，当前案例为 `length=D` 和 `validateTimeMilSec`。`op` 是紧凑 JSON 的事件数组后再用同一 `Encrypt` 包装。

## 轨迹与 JSON

事件四元组是：

```text
[clientX, clientY, eventType, elapsedMilliseconds]
```

当前类型码为 `mousedown=1`、`mouseup=2`、`mousemove=3`、`scroll=4`、`mouseenter=5`、`mouseleave=6`。`mousemove` 只有相邻记录间隔超过约 100ms 才会采样。

注意 SDK 的处理顺序：滑块按下会先清理旧事件并发出 `clickCaptcha/validate`；释放时外层处理器先移除 listener，再读取事件列表，所以当前观察到的 `mCaptcha/validate` 的 `op` 通常只有起始 `mousedown` 和 `mousemove`，没有最终 `mouseup`。这必须以当前源码和明文解密结果复核。

行为 JSON 的数字格式也属于协议字节。JavaScript `JSON.stringify(441)` 输出 `441`，Python `json.dumps(441.0)` 输出 `441.0`；服务端对该字段存在格式敏感性，移植时要保持整数/浮点字面量与页面一致。不要只比较解析后的 JSON 对象。

当前案例的一个可复验轨迹 profile 是约 3200ms、最多 24 个采样点、每点间隔超过 100ms，并带少量垂直扰动。它是当前观察 profile，不是通用固定模板；优先从成功手动轮或当前 SDK 事件采样生成。

## 指纹与响应判定

`fp.min.js` 参与字段包括 UA、语言、色深、屏幕分辨率、时区、storage/indexedDB 能力、插件列表、平台、DNT 和 canvas data URL，最后使用 MurmurHash3 seed `31`。浏览器环境变化会改变 `fp`；不得把一个浏览器的数值当成所有客户端的永久常量。纯协议实现可以把已证明的指纹作为显式 profile 输入，但要标记为 `snapshot-driven`，并保留重新计算路径。

验证码最终成功只认 `/mCaptcha/validate` 响应同时满足：

```text
HTTP 成功
JSONP 已正确解析
code == 0
result 非空
```

`clickCaptcha/validate` 的空 JSONP、HTTP 200、密文长度、图片定位分数和 `rand` 字符串长度都不能单独作为成功判据。失败后丢弃当前轮并重新取得 challenge，不要在同一个 `capKey` 上连续扫描大量坐标。

## 诊断顺序

1. 先检查 `capTicket/capKey/loc/image` 是否同轮，验证码是否已过期。
2. 解密 `validData/op`，确认 `D`、`e=D-9`、整数格式、采样间隔和事件数量。
3. 再检查 `Referer`、UA、JSONP callback framing、AES key/IV、Base64 层级和 `fp` profile。
4. 服务端返回失败时，一次只替换一个变量；不要同时改图片定位、轨迹、指纹和 headers。
5. 若 bundle 的图片尺寸、tile 数、`X()` 切片、字段集合或成功响应结构改变，停止本 reference 的旧公式，重新走 Observe/Capture。

本 reference 的交付边界止于验证码服务端通过响应和动态 `rand`；验证码之后的业务表单、卡号/密码格式校验和业务查询不属于本流程。
