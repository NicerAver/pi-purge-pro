# Suning IAR Jigsaw Workflow

本参考沉淀苏宁 Passport 登录中的 IAR 拼图验证码协议。它覆盖同轮 HTTP 状态、动态 `mgr`、canvas 背景还原、缺口坐标、行为轨迹、`validate.json` 和登录消费者验收。协议状态机由 `captcha-reverse` 主责；明确选择 Python + iv8 时，`iv8-web-reverse` 只提供本地 JS 执行后端。

只用于用户拥有或明确授权的账号、主机和测试流程。不要保存账号、密码、Cookie、ticket、token、完整 validate data 或可复用登录态。

## 1. 路由信号

出现以下组合时选择本分支：

```text
passport.suning.com
/ids/needVerifyCode
/ids/iarVerifyCodeTicket
iar-web.suning.com/iar-web/init.json
iar-web.suning.com/iar-web/validate.json
sncaptchaMgr
SnCaptcha
gTypes / queryToken
IAR JIGSAW 图片
```

至少应有苏宁 Passport 上下文和一个 IAR 原生信号。普通苏宁商品接口、普通 RSA 密码加密、登录错误码、Cookie 或 HTTP 403 不能单独确认 IAR 家族。

任务只要求找 `sncaptchaMgr` 入口、调用栈、脚本 URL、网络 initiator 或写 Hook 时，仍由 Trace 的观察阶段主责。任务只要求离线识别一对拼图图片、不请求 `validate.json` 时转 `captcha-vision` 或普通图像处理。只有完整 challenge 到 validate/token 或下游登录消费才由本分支主责。

## 2. 协议状态机

当前已验证链路为：

```text
GET /ids/login
  -> POST /ids/needVerifyCode
  -> POST /ids/iarVerifyCodeTicket
  -> GET iar-web/init.json (JSONP)
  -> 下载 init 返回的当前 mgr
  -> mgr 恢复题面并产生背景图、滑块图和 drawImage 映射
  -> Python 还原图片并计算 gap
  -> 同一 iv8 realm 注入 trusted pointer 轨迹
  -> mgr 产生 validate.json callback/data
  -> Python GET iar-web/validate.json
  -> resp_code=0 + non-empty token
  -> POST /ids/login
       uuid=iarVerifyCode
       iarVerifyCode=<same-round token>
```

不要把 `needVerifyCode`、ticket、init 或图片下载成功当作验证码通过。验证码服务端判据是同轮 `validate.json` 返回 `resp_code=0` 且 token 非空；若任务包括登录链路，还要证明同一 HTTP Session 的 `/ids/login` 已消费该 token。

## 3. 同轮状态

每个 fresh round 至少绑定以下状态：

```text
HTTP Session 和登录页 Cookie
当前 username 风险策略
needVerifyCode 响应
ticket
init JSONP callback
init.param / init.tInfo / init.js / init.static_server
当前 mgr 内容和版本摘要
当前背景图、滑块图和 20 个 drawImage 调用
滑块 top、gap、pointer offset 和轨迹时间
mgr 生成的 validate callback/data
validate response token
下游 login request
```

禁止跨轮拼接：

- 旧 ticket 配新 `param`；
- 新图片配旧 draw mapping；
- 一轮 gap 配另一轮轨迹或 data；
- 浏览器 token 注入新的 Python Session；
- 已消费 token 再次提交；
- 历史成功图片、ticket、data 或 token 作为生产池。

独立验收轮应重新创建 HTTP Session 和 iv8 context。单个 challenge 内，题面恢复和拖动必须留在同一个 iv8 realm，避免事件监听器、定时器、DOM 和 manager 闭包状态断裂。

## 4. 公开宿主契约

登录页验证码 wrapper 与动态 manager 的已验证边界为：

```text
iar.gOptions()    -> target、ticket、callback 等宿主选项
iar.gTypes()      -> init 返回的动态 param/tInfo/js/static_server
iar.queryStatus() -> 当前验证状态
iar.queryToken()  -> validate 成功 token
window.sncaptchaMgr(host, types)
```

登录提交使用：

```text
uuid=iarVerifyCode
iarVerifyCode=<iar.queryToken()>
```

这个窄契约用于理解 wrapper 与 manager 的所有权，不代表可以默认手写四方法 host。已验证的 iv8 0.1.4 快路径是执行真实 `SnCaptcha.js` 并调用 `SnCaptcha.init(options)`，让 wrapper 创建包含内部状态的 host；只实现 `gOptions/gTypes/queryStatus/queryToken` 的假 host 虽可能创建按钮，但点击时会因缺少内部 `env` 状态失败。只有当前 manager 已通过 trusted click 和图片生命周期证明兼容时，才缩减为手写 host。真正的 protected data writer仍属于 init 本轮下发的当前 `mgr`。

## 5. Browser Evidence

浏览器用于取证和正负样本配对，不作为最终 collector。

每轮至少保留脱敏证据：

- request method、route、字段名和顺序；
- ticket/init/validate 的同轮顺序；
- init 返回的 manager URL 和脚本 hash；
- 图片 URL 形态、尺寸和本地相对路径；
- slider CSS left、piece CSS left、pointer 终点；
- validate `resp_code` 和 token 是否存在；
- 登录响应是否仍要求验证码。

已验证错误语义：

```text
resp_code=0  -> 验证通过，必须同时检查 token 非空
resp_code=1  -> 当前拖动未通过
resp_code=12 -> 多次失败、challenge 状态变化或需要刷新
```

这些码是当前案例证据，页面版本变化时重新确认。HTTP 200、data 非空、data 长度接近或页面出现成功动画都不是服务端成功证明。

正样本必须把最终成功请求与同轮 DOM/轨迹配对。失败轮可以作为坐标负控，但不能进入成功轨迹池。

## 6. Python 与 iv8 的边界

### 6.1 已验证快路径

开始新的苏宁 IAR 实现时，先读取并复用 `assets/suning-iar/iv8-runtime-patch.js`，不要重新手写 DOM、图片和事件补丁。该资产已固化 iv8 0.1.4 下最容易重复踩中的五个边界：

1. 在 `SnCaptcha.js` 和当前 manager 执行前包装动态 `<script>` 插入；
2. 同时观察 `HTMLImageElement.src` 与 `setAttribute("src", ...)`；
3. 在真实图片字节由 Python 管理时模拟 `naturalWidth/naturalHeight/load`；
4. 记录当前 manager 的真实 `drawImage` 参数和 pointer EventTarget；
5. 为苏宁组件提供最小 class-specific geometry，避免 CSS 缺失导致 `NaN`。

固定加载顺序：

```text
fresh Python Session + ticket
  -> fresh iv8 JSContext(time_mode="system")
  -> page.load(minimal host HTML)
  -> ctx.expose(pyLoadScript)
  -> eval iv8-runtime-patch.js
  -> eval real SnCaptcha.js
  -> SnCaptcha.init(options)
  -> Python bridge loads init JSONP/current mgr in the same Session
  -> trusted click -> image URLs/draw calls
```

iv8 0.1.4 对已经发出的动态 `<script src>` 请求，事后 `ctx.add_resource()` 不会重新执行脚本或可靠触发 `onload`。不要在这个症状上反复推进 event loop；在 `Node.appendChild/insertBefore` 边界同步交给同一 Python Session 获取脚本，在 iv8 主世界执行响应，并补 `onload/onreadystatechange`。这仍是 Python-owned egress：目标 JS 不能直接访问公网，bridge 只返回窄的 `{status, body}`。

推荐最终形态：

```text
Python:
  HTTP Session、Cookie、JSONP/script bridge、资源下载、图片恢复、gap、validate、登录回放

iv8:
  SnCaptcha wrapper、当前 mgr、DOM/event/timer、protected validate data writer
```

图片和 validate 必须由同一 Python Session 执行。iv8 可以通过 `netLog` 暴露请求，也可以调用窄的同步 Python bridge；不要把“必须只读 netLog”写成门禁，关键是公网 egress、Cookie 和响应所有权始终在 Python。

需要的最小 runtime surface 通常包括：

```text
window / document / navigator / screen / location
Element geometry and inline style
canvas 2D context
HTMLImageElement src/setAttribute/load lifecycle
setTimeout and system-time event loop
trusted pointer input plus exact listener targets
dynamic script/JSONP bridge
```

不要模拟整个浏览器，也不要先反编译 protected data。快路径能创建题面、捕获两张图和 20 次绘制后，再按首个分歧补当前版本的新 surface。

## 7. 两阶段同 realm 执行

建议在同一个 iv8 context 中分两阶段：

### 阶段 A: 恢复题面

1. `page.load` 一个只有验证码容器的最小 HTML，并固定 location、UA、screen。
2. 创建 `JSContext(time_mode="system")`；不要用 logical time 配合 Python `sleep`，两者不会形成真实墙钟轨迹。
3. 暴露只允许 `iar-web.suning.com`、`oss.suning.com` 和经 necessity test 允许资源的 Python script loader。
4. 在执行 wrapper/manager 前加载 `assets/suning-iar/iv8-runtime-patch.js`，避免 manager 缓存未包装的原生方法。
5. 执行真实 `SnCaptcha.js`，调用 `SnCaptcha.init({id, env, type, target, ticket, width, height, callback})`。
6. 由动态 script bridge 在同一 Session 加载 init JSONP 和当前 manager；不要跨 context 重建假 host。
7. 通过 trusted click 打开 challenge。
8. 同时记录 image property setter 与 `setAttribute("src")`；只 Hook 其中一条会漏掉当前图片。
9. 图片 URL 出现后模拟尺寸与 load，包装的 `drawImage` 只记录当前 source 和 8 个数值参数，真实图片字节交给 Python 下载。
10. 读取背景 URL、滑块 URL、`element.style.top`、draw calls 和 manager 注册的 pointer EventTarget。

### 阶段 B: 生成 validate data

1. Python 下载同轮图片，按 draw calls 恢复背景并计算 gap。
2. 优先从拼图元素的 `style.top` 读取 y；外部 CSS 未加载时不要依赖 `getComputedStyle(...).top`。
3. 在原 context 中注入当前目标位移和轨迹。
4. iv8 0.1.4 的 trusted input 不保证浏览器式捕获/冒泡。加载 manager 前记录 `addEventListener`，把 pointerdown、pointermove、pointerup 分别直接派发到 manager 实际注册的 EventTarget。
5. 每个事件必须保留 `isTrusted=true`、client/page/x 坐标、pointerId、pointerType、isPrimary、buttons/pressure；用真实 sleep 推进 system time。
6. manager 插入 `/iar-web/validate.json` script 时，由同一 Python bridge 请求并在主世界执行 JSONP；也可从 netLog 读取 URL 后由 Python 请求，但不要让 iv8 原生网络持有 Session。
7. release 前后检查 `piece_left ~= gap_x`、`slider_left == slider_delta`，再依据 `resp_code/token` 验收。

如果阶段 A 后销毁 context，再创建阶段 B context，manager 闭包、DOM 节点、事件监听器和 timer 状态可能不同轮。不要用这种拆分掩盖生命周期问题。

## 8. Canvas 背景还原

当前案例中 manager 对背景执行 20 次 `drawImage`。每个有效调用具有 8 个参数：

```text
sx, sy, sw, sh, dx, dy, dw, dh
```

恢复方法：

1. 下载当前背景源图；
2. 创建当前 manager 输出尺寸的空白画布；
3. 按调用顺序裁剪 source `(sx, sy, sw, sh)`；
4. 必要时缩放到 `(dw, dh)`；
5. 粘贴到 destination `(dx, dy)`；
6. 保存恢复图和 mapping 摘要。

已验证版本的源背景约为 `340x184`，恢复画布为 `300x180`，滑块 PNG 为 `64x64`，draw count 为 20。它们是版本证据，不是永久常量。正式实现应从当前图片和 manager 调用读取尺寸；count、尺寸或参数拓扑变化时停止并重新取证，不要继续使用旧 permutation。

不要根据图片文件名猜固定 20 块排列。动态 manager 的实际 `drawImage` 调用是该轮 authoritative mapping。

## 9. 缺口定位

当前 IAR 拼图块是带 alpha 的 PNG，背景缺口在恢复图中表现为暗色遮罩。优先使用以下已通过两轮 fresh verifier 的双通道定位：

1. 从滑块 alpha 构造 mask，并适度腐蚀以排除透明边缘；
2. 从拼图元素的 `style.top` 读取当前 y，将搜索固定为一条 64px 高水平带；
3. 用 piece BGR + alpha mask 做 `TM_CCORR_NORMED`，得到 color candidate；
4. 对背景和 piece 灰度做 Sobel magnitude，再用 alpha mask 做 `TM_CCORR_NORMED`，得到 edge candidate；
5. 要求两个 x 候选在小容差内一致，并计算排除主峰邻域后的 margin；
6. 候选分裂或 margin 过低时停止，不提交 validate。

HSV V 通道 dark mask + `3x3 MORPH_GRADIENT` 保留为 fallback，并继续用多个 threshold 做一致性检查。不要把单个 `V=140` 写成固定平台参数。

固定 y 很重要。全二维颜色匹配容易命中画面中与 piece 内容相似的原始区域；只有 `style.top` 缺失时，才先用二维 edge peak 推导 y，再回到固定 y 的 color/edge 双通道验证。

生产定位器必须输出：

```text
gap x
piece top
confidence
threshold candidates
debug restored image
debug piece image
```

confidence 过低、阈值候选分裂、piece 尺寸变化或目标 x 越界时停止当前轮，不要消耗 challenge 猜 top-1。

## 10. 三套坐标与 pointer offset

必须分开记录：

```text
gap_x             恢复背景中的目标缺口 x
piece_final_left   拼图块 DOM 最终 left
slider_delta       指针或 slider 从按下点移动的水平距离
```

已验证版本满足：

```text
piece_final_left ~= gap_x
slider_delta ~= gap_x + 7px
```

`7px` 来自该版本 DOM 的按下位置和 manager 内部偏移修正，不是平台永久常量。校准方法是配对一轮服务端成功轨迹，同时记录 pointer start/end、slider left 和 piece left，再用失败轮做负控。

每次本地拖动后检查：

```text
abs(piece_final_left - gap_x) <= small_tolerance
```

若该检查失败，先修 geometry、pointer target、clientX 和 offset，不要调密文或随机轨迹。

## 11. 轨迹与时间

当前 fresh 成功实现使用带以下特征的鼠标轨迹：

- 非线性加速和减速；
- 小幅 y 漂移；
- 终点前约 2 到 4px overshoot；
- 多点回落到目标；
- release 前短 hold；
- 每轮重新生成小幅时间和位置变化。

已验证轮约 42 个 move 点，整体约 1 到 2 秒。点数和时长只是当前正样本范围，不要固定为唯一模板。

使用 iv8 trusted pointer API，不要用普通 `dispatchEvent(new PointerEvent(...))` 冒充真实输入。苏宁当前 manager 注册的是 pointer 事件，不要先发送 mouse 事件试错。iv8 0.1.4 不保证 trusted input 自动捕获/冒泡；若监听已注册但 `pieceLeft/sliderLeft` 始终为 0，直接派发到记录的 manager EventTarget，而不是继续调轨迹。使用 `time_mode="system"` 和真实 sleep，保证 `Date.now`、`performance.now`、event timestamp 与 Python validate 请求单调一致。轨迹结束时间不能晚于 Python实际发送 validate 的时间。

一次 challenge 默认只提交一次。需要 repeatability 时创建新的 ticket/init/images/context，不在同一 challenge 上扫描 offset 或轨迹参数。

## 12. Validate 请求

不要尝试从 data 外观猜算法。让当前 manager 生成完整 validate URL，再由 Python 结构化解析：

```text
_callback
ticket
data
jsCode
```

使用同一 Python Session 请求 `iar-web/validate.json`，并严格解析 JSONP。成功条件：

```text
str(resp_code) == "0" and token is not empty
```

以下只算本地 smoke：

- manager 成功加载；
- challenge DOM 出现；
- 捕获 20 个 draw calls；
- gap confidence 较高；
- validate URL/data 非空；
- data 长度与浏览器接近；
- HTTP status 为 200。

## 13. 登录消费者验收

若用户目标包含苏宁登录，验证码通过后在同一 HTTP Session 提交：

```text
POST /ids/login
uuid=iarVerifyCode
iarVerifyCode=<same-round token>
```

密码加密和普通登录字段属于业务登录层，应与 IAR verifier 分开判断。一个有用的消费者证据是：登录响应进入账号或密码校验，且 `needVerifyCode=false`。例如密码错误但不再要求验证码，说明 IAR token 已被消费者接受，但不能宣称账号登录成功。

报告时分开写：

```text
verifier gateway: pass/fail
server token: present/absent
login consumer accepted token: yes/no
authenticated login: yes/no
```

不要把 `badPassword`、账号不存在或业务登录失败误报为验证码失败，也不要把 token 被消费误报为认证成功。

## 14. Fresh 验收门

完成前至少通过：

1. 固定向量或离线 fixture 能恢复预期 draw mapping、piece top、gap 和 validate URL；
2. 至少两轮独立 fresh Python Session 获得 `resp_code=0` 和非空 token；
3. 每轮 ticket、init、图片、gap、data 和 token 均重新生成；
4. 若承诺登录链，至少一次同轮 `/ids/login` 证明 token 被消费者接受；
5. 正式入口不读取浏览器 Cookie、localStorage、profile 或历史成功 token；
6. 最终代码不使用 Playwright、CDP 或 GUI 自动化；
7. 日志和 proof manifest 不含账号、密码、Cookie、ticket、token 或完整 data。

将 fresh verifier 通过次数、失败次数和下游消费者次数分开记录。一次幸运通过不能称为稳定 collector。

## 15. 故障矩阵

| 现象 | 首查层 | 动作 |
| --- | --- | --- |
| `sncaptchaMgr` 未注册 | manager URL/执行 | 核对 init.js 与 static_server，确认当前脚本完整加载 |
| init 响应已注入但 manager 不执行 | dynamic script lifecycle | iv8 0.1.4 不会事后重放动态 script；改用 append/insert Python bridge + 主世界 eval + onload |
| 按钮出现但点击报内部 `env` 为空 | fake host | 停止手写四方法 host，执行真实 `SnCaptcha.js -> SnCaptcha.init` |
| challenge DOM 未出现 | host/lifecycle | 核对真实 wrapper、trusted click、timer 和 geometry |
| 没有图片 URL | image lifecycle | 同时检查 src property、`setAttribute("src")`、load callback；不要直接伪造旧 URL |
| draw calls 不是 20 | manager/版本 | 停止旧还原算法，保存新调用拓扑并重新确认画布 |
| 恢复图错乱 | draw mapping | 检查 8 参数顺序、source crop、destination paste 和调用顺序 |
| gap 在错误 y | solver | 从 `element.style.top` 读取 y，锁定 y 后做 color/edge 双通道匹配 |
| `pieceLeft/sliderLeft` 为 `NaN` | layout | 在 manager 初始化前补 class-specific rect/offset；不要先改密文或轨迹 |
| pointer 监听存在但 left 始终为 0、无 validate | event ownership | trusted input 未冒泡；记录并直接派发到 manager 的 down/move/up EventTarget |
| piece left 与 gap 不同 | geometry | 校准容器 rect、pointer start、clientX 和 offset |
| 有 data 但 `resp_code=1` | 坐标/行为/时序 | 先查 gap、7px 映射、system time，再单变量检查轨迹 |
| `resp_code=12` | challenge/risk | 停止重试，创建 fresh round，检查是否消费或失败过多 |
| validate 成功但 login 又要验证码 | Session/token | 检查是否同一 Session、同一 token、uuid 字段和消费顺序 |
| login `badPassword` 且无需验证码 | 业务凭据 | IAR 已被接受；不要重试验证码或宣称认证成功 |
| 浏览器 data 比本地长 | runtime surface | 比较事件字段、时间、geometry、DFP sidecar；长度本身不是 oracle |

诊断时使用正样本锚定的单变量替换法。一次只替换 gap、pointer offset、轨迹、时间或 runtime surface 中的一层。每次失败后创建 fresh challenge，避免消费状态污染结论。

## 16. MMDS/DFP sidecar

登录页可能带 `detect`、`dfpToken` 或设备采集脚本。不要看到这些字段就立即把完整 DFP collector 塞进 IAR helper。

先做 sidecar necessity test：

1. IAR validate 是否在空 sidecar 时通过；
2. 下游 login 是否接受 token 并进入密码/账号校验；
3. 阻断或空值是否稳定改变 verifier 或消费者结果。

如果验证码和消费者均接受，保留空值并记录当前账号/策略范围。只有另一个 fresh 账号策略明确停在设备校验层时，才将 MMDS/DFP 作为独立 sidecar 恢复，并保持其 session/timing 与 IAR 同轮。

## 17. 推荐项目结构

```text
project/
  main.py
  collector/
    client.py          # HTTP state machine, JSONP, validate and login
    iar_runtime.py     # isolated iv8 manager lifecycle and trusted pointer
    image_solver.py    # draw restore, fixed-y gap matcher and debug artifacts
  utils/
    iv8_silent.py
  analysis/
    proof_manifest.json
  js_reverse_cache/
    live/              # current mgr, images and solver debug only
```

一次性 ticket、data、token 和账号凭据只在内存中流转。`js_reverse_cache/` 可以保存公开脚本、图片、draw mapping 和脱敏 solver 结果；`analysis/` 只保存无敏感值的 proof manifest。

## 18. 最终报告

交付报告至少说明：

1. IAR 路由证据和当前 manager provenance；
2. `needVerifyCode -> ticket -> init -> images -> validate -> login` 顺序；
3. 同轮状态边界；
4. canvas draw mapping、gap 和三套坐标；
5. iv8 helper 的 surface、trusted pointer 和 no-network 边界；
6. verifier `resp_code/token` fresh 次数；
7. 下游登录消费者与认证结果分别是否通过；
8. MMDS/DFP 是否经 necessity test；
9. 版本变化、图片 confidence 和风控频率等残余风险。

不要在 skill、报告或长期 evidence 中写机器盘符、用户目录、真实账号、密码、Cookie、ticket、token、完整 validate data 或可复用登录响应。
