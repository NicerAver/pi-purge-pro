# Alibaba Baxia / NC / Fireye From Zero to One

本流程用于已获授权的安全测试、兼容性研究和协议复现。目标是把一个出现 Baxia、Alibaba NC、Fireye、`x5sec` 或类似字段的滑块站点，从“只有一个业务 URL”推进到可验证的本地协议回放。

本文不假定站点版本、字段命名、响应码或前端资源完全相同。每个站点都必须用 fresh challenge 现场确认。文中的路径全部是项目根目录下的相对路径。

## 0. 完成定义

在开始编码前先写清楚完成标准。一个完整交付至少包括：

```text
[ ] 能从 fresh 业务请求得到 punishment/challenge
[ ] 能保存同轮 cookies、headers、HTML、配置和版本资产
[ ] 能解释 slide 请求中 n、_rand、bx-et、bx-pp、ppt、ts、v、slidedata 的来源
[ ] 本地能生成非空的 Fireye/UMID/ET/pp 输出
[ ] fresh /slide 返回目标成功码，通常是 code=0
[ ] response 或后续接口产生 x5sec
[ ] 使用同轮 x5sec 重放原业务请求，得到目标业务状态
[ ] 至少用多个独立 challenge 复验
[ ] README、profile、入口命令和 artifact 路径可供别人复现
```

必须区分三个结论：

```text
本地函数返回非空       = 本地 helper smoke
slide code=0            = 验证服务接受本轮滑块
x5sec + 业务目标响应   = 完整协议交付
```

长度、正则匹配、HTTP 200、密文格式和一次性的旧 token 都不能单独证明完成。

## 1. 建立空项目和证据目录

建议先建立最小目录，不要一开始复制整个浏览器项目：

```text
project-root/
  README.md
  requirements.txt
  .env.example
  run.py
  protocol.py
  profile.json
  assets/
    fireye.js
    nc.js
    et.js
    secaptcha.js
  helpers/
    rand_helper.py
    bx_et_helper.py
    bx_pp_helper.py
  evidence/
    rounds/
    baselines/
  references/
```

每轮使用独立目录：

```text
evidence/rounds/round-001/
  request-business.json
  response-punishment.html
  cookies.json
  headers.json
  config-summary.json
  network-timeline.json
  slide-request.json
  slide-response.json
  business-replay.json
  hashes.json
  notes.md
```

完整敏感值可按项目安全要求加密或忽略；长期 artifact 至少保留长度、hash、字段名、状态码和非敏感摘要。不要在 skill、README 或提交物中写入机器绝对路径、账号密码、长期 Cookie 或真实个人数据。

## 2. Stage 0：确认是否属于这类链路

从页面、HTML、网络请求和资源名进行分类。命中一项不能直接下结论，至少需要两类独立证据。

### 2.1 页面或脚本标记

```text
bxpunish
x5secdata
bxuuid
AWSC
NCAPPKEY
NCTOKENSTR
fireyejs
et_f.js
punishpage
secaptcha
```

### 2.2 网络标记

```text
/_____tmd_____/initialize.jsonp
/_____tmd_____/slide
/_____tmd_____/report
bx-et
bx-pp
_rand
n
x5sec
```

### 2.3 先排除近似但不同的任务

- 只有图片 OCR，没有 challenge/verify 状态机：转视觉识别方向。
- 只有普通 RPC `sign`，没有验证码/风控验证闭环：不要强行归入本流程。
- 只有通用 WAF cookie challenge，且没有 slider/NC/Fireye 证据：转 WAF 专项。
- 只要求定位函数、脚本 URL 或调用栈：先做 trace 取证，不直接实现完整协议。
- 明确要求 Python + iv8：状态机仍由 captcha-reverse 负责，IV8 作为 runtime backend。

### 2.4 建立初步 family note

在 `evidence/rounds/round-001/notes.md` 写入：

```text
target: <站点或业务名称>
entry URL: <相对安全记录中的 URL 摘要>
observed markers: <HTML、script、network 三类证据>
likely family: Alibaba Baxia/NC/Fireye or unknown
unknowns: <缺失的端点、版本、字段>
authorization: <授权范围摘要>
```

如果无法确认 family，停止实现，先补充 network/source 证据。

## 3. Stage 1：获取一轮 fresh challenge

这一阶段只做取证，不急着改前端或构造 payload。

### 3.1 清理旧状态

使用新的浏览器上下文或新的 HTTP session：

```text
新 session
新 Cookie jar
新 challenge
新 round id
```

不能使用上一轮的：

```text
challenge
SECDATA
NCTOKENSTR
x5secdata
_umid_token
cna
arms_uid
tfstk
x5sec
```

### 3.2 记录首个业务请求

保存以下摘要：

```text
method
URL path/query
request headers 摘要
response status
Set-Cookie 名称和值摘要
Location
content type
body hash
```

不要只保存 punishment HTML；首个业务请求的 URL、UA、Referer、Cookie 和 Client Hints 可能参与后续 token 绑定。

### 3.3 保存 punishment 页面和资源版本

从 HTML 记录：

```text
内联配置对象
script src
资源版本号
challenge id 摘要
NCAPPKEY
NCTOKENSTR
SECDATA/x5secdata
nonce
初始化 callback 名称
```

资源下载后保存 hash：

```bash
sha256sum assets/fireye.js assets/nc.js assets/et.js
```

Windows 环境可使用等价的 SHA-256 工具。重点是保存“本轮页面引用的版本”，不要混用另一轮缓存的脚本。

### 3.4 捕获最终请求

在滑块真正提交前安装被动 network 记录，至少捕获：

```text
initialize.jsonp
secaptcha 或 rand 请求
slide
report?type=verifyFail
report?type=setCookieSuccess
原业务 replay
```

对每个请求记录：

```text
sequence
method
path/query
request headers 摘要
request body/query 字段名
response status
response body 摘要
Set-Cookie 名称
initiator URL/function（如果工具支持）
```

最终 `/slide` 请求是本轮逆向的主样本。初始化请求只能说明 bootstrap，不能说明验证已经完成。

## 4. Stage 2：建立同轮正样本

如果浏览器人工完成一次滑块，保存完整正样本。Edge/Chrome 仅用于取证时，不能自动拖动或自动提交；人工操作产生的请求可以被动记录。

正样本至少包含：

```text
同轮 request/response
Cookie jar
UA/Client Hints
slide query/body
n
_rand
bx-et
bx-pp
ppt
ts
v
slidedata 字段拓扑
x5sec
业务 replay status
```

对敏感字段生成摘要：

```text
field length
sha256
prefix/suffix（按安全要求）
JSON key order（如有意义）
encoding/base64/hex/urlencode 形态
```

建立一张字段来源表：

| 字段 | 观察位置 | 生成时机 | 绑定对象 | 是否可重算 |
|---|---|---|---|---|
| `n` | `/slide` query/body | Fireye token 阶段 | session、UMID、事件、时间 | 是，需同版本 runtime |
| `_rand` | `/slide` 或初始化参数 | rand/ET bootstrap | challenge、版本、状态 | 通常是 |
| `bx-et` | `/slide` | mobile/desktop ET 阶段 | UA、环境、配置 | 通常是 |
| `bx-pp` | `/slide` | mini/append 状态 | attempt、事件或服务端状态 | 通常是 |
| `ppt` | `/slide` | payload 组装 | 轨迹/时序 | 需现场确认 |
| `slidedata` | `/slide` | NC 轨迹阶段 | slider geometry、track、challenge | 需现场确认 |
| `x5sec` | response cookie/body | slide 成功后 | 本轮 challenge/session | 不可跨轮复用 |

表格中的“通常”不是结论；必须用单变量实验或调用链确认。

## 5. Stage 3：还原状态机

把请求按时间排序，写成状态图。典型状态如下：

```text
S0 new session
S1 business request
S2 punishment received
S3 assets/config loaded
S4 UMID/NC/ET bootstrap
S5 Fireye initialized
S6 startRecord
S7 track replay completed
S8 uid/n generated
S9 rand/bx-et/bx-pp assembled
S10 slide submitted
S11 verifyFail reported or x5sec received
S12 business replay
```

为每个状态写：

```text
input
output
cookie changes
request sequence
failure meaning
```

典型成功路径：

```text
business GET
-> punishment HTML
-> initialize
-> __fycb(umid)
-> fy.init(options, callback)
-> startRecord
-> touch/mouse track
-> getUidToken
-> getFYToken({reqUrl: slide URL})
-> generate _rand / bx-et / bx-pp
-> slide
-> code=0
-> x5sec
-> original business GET
```

某些版本会在 `fy.init` 前后调用 `resetSA`，某些版本使用 NC 内部 Fireye instance，某些版本使用独立 Fireye instance。不要凭名称推断；以 initiator、断点和对象状态为准。

## 6. Stage 4：解析 punishment 配置

先实现“只解析不发送”的 parser。建议输出一个规范化对象：

```json
{
  "scene": "register_h5",
  "ncAppKey": "<redacted>",
  "ncToken": "<redacted>",
  "secData": "<redacted>",
  "challengeId": "<redacted>",
  "assetUrls": {
    "fireye": "<relative or redacted URL>",
    "nc": "<relative or redacted URL>",
    "et": "<relative or redacted URL>"
  },
  "version": {
    "punishpage": "<version>",
    "fireye": "<version>",
    "nc": "<version>",
    "et": "<version>"
  }
}
```

解析优先级：

1. JSON script/config 节点。
2. 页面中明确的配置对象。
3. 资源 URL 和 callback 参数。
4. 最后才使用 AST 或最小字符串定位。

不要用正则替代 JSON parser 解析嵌套配置。若页面是混淆脚本，先保存原始版本并建立 AST/source map 证据，再定位入口。

解析器必须拒绝以下情况：

```text
字段缺失
字段来自不同页面版本
challenge id 为空
NC token 与当前 cookie 不匹配
资源 URL 不是本轮引用版本
```

## 7. Stage 5：确定 profile，而不是先猜 Desktop

先从成功浏览器请求和页面 runtime 快照生成 profile。至少记录：

```text
UA
sec-ch-ua-mobile
sec-ch-ua-platform
navigator.platform
navigator.language/languages
maxTouchPoints
hardwareConcurrency
deviceMemory
screen geometry
window geometry
DPR
WebGL vendor/renderer
canvas/audio 摘要
slider track/button rect
track distance
```

### 7.1 Android H5 判断

以下组合才可作为 Android H5 profile 的候选：

```text
register_h5 scene
Android UA
sec-ch-ua-mobile=?1
sec-ch-ua-platform="Android"
navigator.platform 类 Android 值
maxTouchPoints > 0
mobile bx-et
TouchEvent 或 Pointer/Touch 事件
移动端 slider geometry
```

把候选值写入 `profiles/android-h5.json` 或项目根目录的同类文件。不要把“开启 DevTools 移动端预览”本身当成协议结论。

### 7.2 Desktop profile 判断

Desktop profile 需要独立记录：

```text
register scene
Windows/macOS UA
platform
maxTouchPoints
mouse/pointer event
desktop geometry
DPR/WebGL
bx-et variant
```

如果 Desktop 反复 `code=300` 而 Android H5 fresh 验收稳定，桌面主机可以运行 Android H5 profile。主机操作系统与协议画像不是一回事。

## 8. Stage 6：恢复滑块轨迹输入

轨迹属于协议输入，不等于视觉识别结果。先用人工成功轨迹建立最小模型，再决定是否需要视觉模块。

记录：

```text
button down
move count
每个 move 的 x/y
clientX/clientY
screenX/screenY
pageX/pageY
buttons
pressure（若存在）
touch identifier/radius/force（若存在）
timeStamp
up/end
```

归一化为独立结构：

```json
{
  "start": {"x": 50.9, "y": 662.3},
  "distance": 61.5,
  "steps": 96,
  "durationMs": 820,
  "points": [
    {"x": 50.9, "y": 662.3, "t": 0, "type": "down"},
    {"x": 51.5, "y": 662.5, "t": 11, "type": "move"},
    {"x": 112.4, "y": 662.8, "t": 820, "type": "up"}
  ]
}
```

不要只使用最终距离。服务端可能检查：

```text
方向
起点/终点
速度变化
停顿
按压持续时间
事件类型
target
时间戳单调性
```

同一个 challenge 上不要反复提交不同轨迹。需要比较轨迹时，每个变体建立 fresh challenge。

## 9. Stage 7：选择本地 runtime

### 9.1 选择 Node/jsdom

优先选择 jsdom，当：

```text
已有成品 jsdom 路线能通过服务端
Fireye 依赖 DOM/事件但不强依赖真实浏览器 descriptor
希望快速交付稳定 browser-free collector
```

### 9.2 选择 Python + IV8

优先选择 IV8，当：

```text
用户明确指定 Python + iv8
需要 Python requests/curl_cffi 发送真实 HTTP
Fireye 依赖 event loop、layout、descriptor 或多阶段 bootstrap
已有固定入口和可加载 JS 资产
```

完整验证码状态机仍然由本 skill 主责；runtime 补环境细节可以交给 `iv8-web-reverse`。

### 9.3 不要跨 runtime 复用 n

正确做法：

```text
同一 profile
同一 fresh challenge
jsdom 独立执行并生成 n_jsdom
IV8 独立执行并生成 n_iv8
分别组装其余同轮字段
分别发送 fresh slide
```

错误做法：

```text
jsdom 生成 n
IV8 生成 uid
Python 拼接两者
```

`n` 可能绑定 UMID、时间、事件 recorder、challenge、环境对象和内部随机状态。跨 runtime 复用会破坏因果关系。

## 10. Stage 8：补 Fireye 环境和生命周期

按最小缺失原则补环境。先让脚本能加载，再根据异常和 pre-token snapshot 增加 surface。

### 10.1 最小 surface

```text
window/document
location/history
navigator
screen/window/DPR
Element/HTMLCollection
getBoundingClientRect
offsetWidth/offsetHeight
addEventListener/dispatchEvent
Date/performance
setTimeout/clearTimeout
crypto
canvas/WebGL
localStorage/sessionStorage
```

### 10.2 生命周期

默认尝试以下顺序，并以现场脚本确认删减或增加：

```text
__fycb(umid)
fy.init(options, callback)
resetSA（如果版本需要）
__fycb(umid)（如果调用链显示需要）
startRecord()
track events
getUidToken()
getFYToken({reqUrl: slideUrl})
```

每个阶段都记录返回值和状态：

```text
callback fired?
uid non-empty?
FY token non-empty?
virtual elapsed?
network request count?
exception?
```

### 10.3 时间和事件

如果使用虚拟时间，必须保证以下对象一致：

```text
Date.now
performance.now
event.timeStamp
setTimeout callback order
```

不要只修改 `Date.now`。Fireye 可能同时读取 `performance.now` 和事件时间戳，时间轴不一致会产生长度正常但服务端不接受的 `n`。

## 11. Stage 9：独立恢复 `_rand`、`bx-et` 和 `bx-pp`

先把 Fireye 和协议壳分离验证。每个 helper 使用明确输入输出：

```text
rand helper:
  input: current round config/state
  output: _rand

bx-et helper:
  input: current round + mobile/desktop profile
  output: bx-et

bx-pp helper:
  input: current round + attempt + mini/append state
  output: bx-pp, ppt
```

逐项与浏览器正样本比较：

```text
是否同编码
是否同字段顺序
是否同 URL encoding
是否依赖 cookie
是否依赖时间/nonce
是否依赖 attempt
```

先做离线 shape 检查，再做 fresh 在线验证。不要因为长度接近就认为 helper 正确。

## 12. Stage 10：组装和发送 `/slide`

主程序建议保持以下职责分离：

```text
bootstrap_session()
fetch_punishment()
parse_config()
load_assets()
collect_umid_or_uid()
collect_fireye_n()
generate_rand()
generate_bx_et()
generate_bx_pp()
build_slidedata()
post_slide()
handle_verify_fail_or_x5sec()
replay_business()
write_artifact()
```

发送前做一致性检查：

```text
[ ] 所有字段来自同一 round object
[ ] URL path/query 与浏览器正样本一致
[ ] Cookie jar 未被替换
[ ] UA/profile 与 bx-et variant 一致
[ ] n 是当前 runtime 当前 round 新生成
[ ] _rand 是当前 challenge 新生成
[ ] bx-pp 与 attempt 状态一致
[ ] slidedata 几何与 profile 一致
[ ] ts/ppt/v 不是旧样本复制
```

若请求失败，保存原始 response 和字段摘要后再改代码。不要先增加重试次数。

## 13. Stage 11：处理 response、`verifyFail` 和 `x5sec`

### 13.1 `code=0`

继续检查：

```text
response body 是否有 token
Set-Cookie 是否有 x5sec/BX-X5SEC
cookie domain/path/secure/samesite
是否需要 setCookieSuccess report
```

不要只看 JSON body；有些站点将 `x5sec` 放在 response cookie。

### 13.2 `code=300`

先记录本轮所有变量，再判断：

```text
是否 profile/scene 不一致
是否 Fireye n 来源错误
是否 slider input 不完整
是否 bx-et/rand/bx-pp 混用
是否 challenge 已消费
```

如果协议明确要求失败上报，只发送同轮对应的 `verifyFail` report，然后按现场观察进入下一 attempt。不要把失败上报当成成功，也不要无限重试。

### 13.3 `code=8778` 或其他深校验码

将它当作状态转移或更深 payload 校验信号，而不是“加大轨迹数量”的提示。保存：

```text
response fields
next token/challenge
report request
cookie changes
attempt state
```

根据新状态重新构造下一轮同轮字段。

## 14. Stage 12：重放原业务请求

拿到 x5sec 后，用同一个 HTTP session 重放原业务请求。只替换明确需要替换的 cookie/header：

```text
保留原 URL、query、UA、必要 headers
保留当前 session cookies
加入当前 response 的 x5sec
不要加入旧轮 cookie
不要从浏览器和本地请求混拼不明字段
```

业务回放结果保存：

```json
{
  "slideCode": 0,
  "x5secPresent": true,
  "businessStatus": 419,
  "businessBodyHash": "<sha256>",
  "accepted": true
}
```

`419` 只是某个站点的实测目标，不要把它写成所有站点的通用成功码。交付文档应写目标站点的实际业务验收条件。

## 15. Stage 13：单变量诊断

如果本地失败，先保留一份浏览器 fresh 正样本。实验矩阵必须有唯一变化项：

| 实验 | 保留项 | 唯一变化 | 结论依据 |
|---|---|---|---|
| A | 浏览器全部字段 | 只换 HTTP 客户端 | 排除传输差异 |
| B | 同轮 profile/cookie | 只换 `bx-et` | 最终 slide/业务结果 |
| C | 同轮 profile/cookie | 只换 `_rand` | 最终 slide/业务结果 |
| D | 同轮 profile/cookie | 只换 `bx-pp` | 最终 slide/业务结果 |
| E | 同轮协议壳 | 只换 Fireye `n` | 最终 slide/业务结果 |

每个实验必须使用 fresh challenge，除非只是离线解析或不发送的本地比较。一次实验失败后先分析唯一替换层，不要同时改轨迹、UA、cookie、时间和密文。

如果只替换 Fireye `n` 就从 `code=0` 变为 `300`，优先检查：

```text
Fireye 版本
profile
生命周期
UMID 绑定
事件 target/type/timeStamp
recorder bucket
Date/performance
canvas/WebGL/layout
```

## 16. Stage 14：多轮验收

单次通过只能说明“存在一条通过路径”。正式 backend 选择至少运行多个独立 fresh challenge：

```text
每轮新 session 或明确新 challenge
每轮新 challenge/token/cookie
每轮最多固定 attempts
每轮保存 artifact
```

统计：

```text
独立轮数
code=0 轮数
x5sec 轮数
业务成功轮数
平均 attempts
最大 attempts
失败码分布
失败阶段分布
```

建议把成功率和稳定性分开：

```text
slide acceptance rate = code=0 的轮数 / 总轮数
business acceptance rate = 业务目标响应轮数 / 总轮数
first-attempt rate = 第 1 次通过轮数 / 总轮数
```

不要为了提高统计成功率而把同一 challenge 重试很多次；同一轮重试只能用于验证已观察到的状态机，稳定性统计应以独立 challenge 为单位。

## 17. Stage 15：固化 profile、入口和回归

完成后固定：

```text
profile 文件
Fireye/NC/ET 资产 hash
backend 选择
环境变量默认值
attempt 上限
bx-pp 状态转换
最终业务验收字段
```

README 至少包含：

```text
安装依赖
运行命令
环境变量
输出 artifact
成功判定
失败码含义
fresh challenge 要求
formal backend
```

建议保留两个入口：

```text
正式入口：默认使用已验收 backend
研究入口：允许切换 jsdom/IV8、记录诊断中间态
```

研究开关必须显式启用，不能让实验参数悄悄改变正式基线。

## 18. 最小主程序伪代码

```python

def solve_once(client, profile, backend):
    round_id = new_round_id()
    session = client.new_session()

    business = session.get(BUSINESS_URL)
    punishment = ensure_punishment_or_fail(business)
    config = parse_punishment(punishment.text)
    assets = load_round_assets(config)

    round_state = RoundState(
        round_id=round_id,
        config=config,
        profile=profile,
        cookies=session.cookies.snapshot(),
        assets=assets,
    )

    umid = collect_umid(session, round_state)
    uid = backend.get_uid_token(umid, round_state)
    n = backend.get_fy_token(
        umid=umid,
        uid=uid,
        req_url=slide_url(config),
        track=make_track(profile, round_state),
        round_state=round_state,
    )
    rand = generate_rand(round_state)
    bx_et = generate_bx_et(round_state)
    bx_pp = generate_bx_pp(round_state, attempt=1, mode="mini")
    slide_data = build_slide_data(profile, round_state)

    response = session.get(
        slide_url(config),
        params=build_slide_params(
            round_state, n, rand, bx_et, bx_pp, slide_data
        ),
    )
    save_artifact(round_state, response, session)

    if slide_code(response) != 0:
        send_verify_fail_if_observed(session, round_state, response)
        return retry_or_fail(round_state, session)

    x5sec = extract_x5sec(response, session.cookies)
    if not x5sec:
        return fail("slide accepted but x5sec missing", round_state)

    replay = session.get(BUSINESS_URL)
    save_business_artifact(round_state, replay)
    return evaluate_final_result(round_state, response, replay)
```

这段伪代码不是站点专用实现。实际项目必须根据 captured request 的 method、字段位置、编码、callback 和 cookie 行为调整。

## 19. 失败时的停止条件

立即停止当前路线并重新取证的情况：

```text
连续失败但没有保存 fresh response
不同 challenge 的字段被混用
无法证明 n/rand/bx-et/bx-pp 的来源
只能依靠大量重试
浏览器成功样本本身不是同轮完整样本
业务回放没有带当前 x5sec
Desktop profile 连续 300 且没有独立正样本
```

不要用以下方式掩盖问题：

```text
复制旧 n
复制旧 x5sec
随机增加事件数量
只改密文长度
固定 ppt/ts
无限 retry
把移动端预览当成 Android H5 证明
```

## 20. 交付检查清单

```text
[ ] family 判断有 HTML/script/network 两类证据
[ ] fresh challenge 获取方式写明
[ ] 同轮字段和 cookie 约束写明
[ ] punishment parser 可运行
[ ] Fireye/NC/ET 版本 hash 已记录
[ ] profile 与 backend 分离
[ ] lifecycle 已记录
[ ] 轨迹字段和坐标系已记录
[ ] n/rand/bx-et/bx-pp 独立生成
[ ] slide code=0 有 fresh artifact
[ ] x5sec 来源和 cookie 属性已确认
[ ] 原业务回放使用同轮 x5sec
[ ] 多个独立 challenge 已验收
[ ] 正式入口和研究入口分离
[ ] 失败码和重试状态机有说明
[ ] skill、README、代码没有绝对路径
[ ] 删除探针前完成依赖搜索和回归
```
