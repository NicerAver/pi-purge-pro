---
name: captcha-reverse
description: >-
  验证码协议逆向与本地复现 skill，负责滑块、点选、无感和行为验证码的
  Python/Node 协议链、同轮状态、动态加密和最终 verify/check 验收。覆盖 GT3/GT4、
  腾讯 TCaptcha/TDC、易盾、数美、云片、360 天御、CSDN、携程、百度 Passport、
  京东 JCAP、苏宁 IAR、阿里云 V2/V3、Vaptcha V4、字节 VerifyCenter、MTCaptcha v1
  和天爱 TianAi。MTCaptcha 信号：MTCaptcha、mtcaptcha2.min.js、service*.mtcaptcha.com、
  /mtcv1/api/getchallenge.json、/mtcv1/api/getimage.json、/mtcv1/api/solvechallenge.json、
  mt.v1.01、hasTextChlg、foldChlg；命中后读 references/mtcaptcha-v1-workflow.md。
  苏宁信号包括 passport.suning.com、iarVerifyCodeTicket、sncaptchaMgr、iar-web；天爱信号包括
  captcha.tianai.cloud、/v2/api/open/captcha/generate、/v2/api/open/captcha/verify、SLIDER_、
  CURVE3_、CONCAT_、JIGSAW_、data.matrix、data.shuffle.pos、__drives__、__ki__、__encrypt__、
  cw.js/cw.wasm；分别读取对应 references。完整验证码协议即使使用 Python+iv8、YOLO 或视觉模型仍由本 skill 主责；
  明确 iv8 后端交给 iv8-web-reverse，纯模型/识别交付转 captcha-vision。不要用于普通 OCR、泛化 sign/a_bogus、
  非验证码 WAF/cookie、DevTools hook、入口定位、UI 或通用 Node 补环境。
---

# 验证码协议逆向

使用本 skill 时，目标是把验证码请求链还原成本地可重复执行的 Python/Node 流程。先判断验证码家族，再固定同一轮 challenge、session、图片、token、randomKey 等状态，最后用服务端 `verify/check` 响应确认结果。

若用户明确要求“只输出阶段门”，按 `../_shared/js-reverse-workflow.md` 的 Stage-Gate Output 返回 `MODE`、`OWNER`、`NEXT_GATE`、`REQUIRED_EVIDENCE` 和 `DO_NOT_USE`，不要开始取证或实现。

验证码出现在微信小程序 / WMPF / AppService / WebView 里时，协议链仍由本 skill 主责，但 runtime 取证（target、请求、initiator、源码、paused scope）由 `wechat-miniapp-reverse` 提供；本 skill 只消费它已保存的同轮样本与 `handoff.json`，不调用 `miniapp-reverse-mcp` 的 request/script/target ID；缺同轮字段时退回该 skill 再取一轮。

## Checkpoint 字段

`skill_checkpoint` 只记工程事实。

- `evidence`：主机、路径、家族/版本、请求名、状态码、同轮字段、缺什么证据。
- `hardConstraints`：同轮绑定、服务端响应验收等正确性/验收备注；不是权限策略，也不能禁止事件、浏览器交互、网络请求或外部请求。
- `nextStep`：下一步技术动作。
- `artifacts`：已落盘路径。

缺证据就写缺哪个端点或字段。示例：

```text
evidence: www.example.com; JCAP 2.8.5 /cgi-bin/api/fp /cgi-bin/api/check; slider challenge present; same-round token fields not captured
nextStep: Capture same-round /fp and /check plus challenge image fields
```

## 分支选择

先按请求路径、响应字段、图片形态和用户目标选一级分支。分支冲突、平台细节、GT4 子题型和高频规则再读 `references/routing-quick-rules.md`。

- **腾讯 EdgeOne / TCaptcha / TDC**：`cap_union_prehandle`、动态 `tdc.js`、`TDC.getData(true)`、`cap_union_new_verify` -> `references/tencent-edgeone-tdc-workflow.md`。
- **MTCaptcha v1**：`service*.mtcaptcha.com`、`/mtcv1/api/getchallenge.json`、`/mtcv1/api/getimage.json`、`/mtcv1/api/solvechallenge.json`、`hasTextChlg`、`foldChlg` -> 读取 `references/mtcaptcha-v1-workflow.md`；按同轮 `getchallenge -> getimage -> solvechallenge` 保留 `ct/ss/image/fseed/fa/kt`，可用 `ddddocr` 做文字子步骤，但最终必须以 `code=1200 && isVerified=true && verifiedToken.vt` 验收。
- **JD Passport / JCAP 2.8.5**：`/cgi-bin/api/fp`、`/cgi-bin/api/check`、`tp=30`、`b1/b2`、`tk/ct/cs`、Python + iv8 或 browser-free replay -> 读 `references/jd-jcap-v2.8.5-workflow.md`；保留同轮 session/fp/initial check/interaction/final check，成功以最终 `code=0`、无 next `tp`、非空 `vt` 为准。
- **苏宁 Passport / IAR JIGSAW**：`passport.suning.com`、`iar-web.suning.com`、`/ids/iarVerifyCodeTicket`、`sncaptchaMgr`、`gTypes/queryToken`、`/iar-web/init.json`、`/iar-web/validate.json` -> 读 `references/suning-iar-jigsaw-workflow.md`；保留同轮 HTTP Session、ticket、init param/tInfo、当前 mgr、图片/draw mapping、gap/轨迹/data/token 和登录消费，成功以 `resp_code=0` 且 token 非空为准。
- **CSDN / 携程 / 百度 Passport**：分别读 `references/csdn-point-click-workflow.md`、`references/ctrip-captcha-v4-workflow.md`、`references/baidu-passport-spin-v2-workflow.md`。
- **字节 VerifyCenter / BDMS / mssdk 验证码链**：读 `references/bytedance-verifycenter-workflow.md`。
- **阿里云 Captcha V2 / V3**：读 `references/aliyun-captcha-v2-workflow.md` 或 `references/aliyun-captcha-v3-workflow.md`；极速、完整、日更分支细节见 `references/routing-quick-rules.md`。
- **Vaptcha V4 手势轨迹**：出现 `VaptchaCore`、`/api/config`、`/api/knock`、`/api/validate`、`pow_start/salt/trajectory`、5x2 图片乱序或 `result=true/token/dfu` 时，读取 `references/vaptcha-v4-trajectory-workflow.md`。协议状态机和 fresh 服务端验收由本 skill 主责；YOLO-seg、mask、骨架和路径排序只是视觉子模块，不能替代 `validate` 响应。
- **天爱 TianAi 滑块/滑动曲线 V3/滑动还原/乱序拼图**：出现 `captcha.tianai.cloud`、`api.captcha.tianai.cloud`、`/v2/api/open/captcha/generate`、`/v2/api/open/captcha/verify`、`SLIDER_`、`CURVE3_`、`CONCAT_`、`JIGSAW_`、`data.matrix`、滑动还原、`data.randomY`、`data.shuffle.pos`、`data.attr1`、`__drives__`、`__ki__`、`__encrypt__` 或 `cw.js/cw.wasm` 时，先读 `references/tianai-slider-workflow.md`；命中 `type=JIGSAW`、`JIGSAW_` 或 2x2/矩阵乱序拼图时，再读 `references/tianai-jigsaw-workflow.md`。完整 `generate -> 当前题面/图片处理 -> SLIDER 缺口/CURVE3 双贝塞尔/CONCAT 上下拼接/JIGSAW 排列识别 -> 轨迹 -> encrypt -> verify` 由本 skill 主责；明确 Python + iv8 时，iv8 只作为 `iv8-web-reverse` 的执行后端，最终成功仍以同轮 verify 的 `code=200 && success=true` 为准。
- **mCaptcha PC 滑块**：出现 `mCaptcha.pc.min.js`、`mCaptcha.min.js`、`captchasInit`、`capTicket`、`capKey`、`/mCaptcha/key`、`/mCaptcha/info/`、`/mCaptcha/validate`、`clickCaptcha/validate`、`validData`、`UserOpListener` 或 `fp.min.js` 等组合时，先读 `references/mcaptcha-pc-workflow.md`；只恢复验证码同轮状态、图片/轨迹和最终验证码通过响应，不把验证码后的业务查询加入流程。
- **滑块、点选和通用图片验证码**：先读 `references/slide-captcha-overview.md`，再进入 `references/geetest-gt3-workflow.md`、`references/geetest-gt4-workflow.md`、`references/yidun-workflow.md`、`references/shumei-workflow.md`、`references/yunpian-workflow.md` 或 `references/tianyu360-workflow.md`；数美 `spatial_select`/空间推理题直接读 `references/shumei-workflow.md`。
- **GT4 nine/icon 识别模型训练**：协议链仍归本 skill；模型训练、YOLO/CLIP、ONNX 和 fresh 识别统计转 `captcha-vision`。
- **明确 Python + iv8 执行后端**：验证码状态机仍归本 skill；iv8 运行后端转 `iv8-web-reverse`。
- **未知验证码**：先分类；无法归类时沉淀新的 focused reference，不要把非验证码 WAF/cookie challenge 塞进本 skill。

## JD 已知案例硬门禁

当任务同时出现 JD Passport、JCAP 2.8.5、`/cgi-bin/api/fp`、`/cgi-bin/api/check`、`tp=30`，并且用户提供了已验证参考项目或本地已有可运行 baseline 时，固定执行顺序：

1. `captcha-reverse` 的 JD 分支保持 primary；`iv8-web-reverse` 只能作为 secondary runtime backend。
2. 先完整读取 `references/jd-jcap-v2.8.5-workflow.md`，再读取参考项目的入口、runtime、协议和测试；先做 baseline 对照或最小迁移。
3. 不得先另起一套通用 iv8、Node 补环境、device-info probe 或 ciphertext 重写路线。只有参考 baseline 无法运行，才进入单变量环境诊断。
4. 首个运行门只验证 fresh `/fp` -> initial `/check`；必须记录 `code`、`tp`、`b1/b2` 和非敏感字段摘要后才能进入图片或轨迹阶段。
5. 只处理 `tp=30` 时，initial `/check` 返回 `tp=3`、`tp=26` 或其他题型即停止当前轮：不调轨迹、不做点选、不继续高频重试。先诊断 account/`si`/Cookie/runtime/device-info/风险状态和参考 baseline 是否一致。
6. `fp code=0`、initial `/check code=0`、`tp=30` 只代表 bootstrap smoke test 通过；没有同轮 final `/check` 的 `code=0`、无 next `tp`、非空 `vt`，不得宣称协议或本地 solve 已完成。

## Suning IAR 专项规则

1. 先读 `references/suning-iar-jigsaw-workflow.md`，再实施或修改苏宁 `needVerifyCode -> iarVerifyCodeTicket -> init.json -> images -> validate.json -> login` 链。
2. 默认以 `assets/suning-iar/iv8-runtime-patch.js` 为 iv8 0.1.4 baseline；先证明真实 `SnCaptcha.js -> SnCaptcha.init -> current mgr -> images/draw calls`，不要重新手写假 host、动态 script loader、图片生命周期或事件目标补丁。
3. 每轮重新创建 HTTP Session、ticket、init、mgr context、图片、draw mapping、轨迹、data 和 token；禁止跨轮拼接或使用历史成功池。
4. Python 负责 HTTP、JSONP/script bridge、图片还原、验收与登录；当前 mgr 在同一 isolated iv8 realm 中完成题面生命周期和 protected data writer。iv8 不直接持有公网 Session。
5. 背景按当前 manager 的真实 `drawImage` 调用恢复；已验证版本为 20 次调用，但 count、图片尺寸和排列变化时必须停止旧算法并重新取证。
6. gap、piece final left 和 pointer/slider delta 是三套坐标。已验证版本约有 `slider_delta = gap_x + 7px`，该偏移必须由当前成功/失败对照重新校准，不能写成永久平台常量。
7. manager 初始化与 trusted pointer 拖动必须处于同一个 iv8 context；使用 `time_mode="system"`、真实时间推进和 manager 实际注册的 pointer EventTarget，不能只伪造 payload timestamp 或假设 input 自动冒泡。
8. `resp_code=0` 只有在 token 非空时才是 verifier 成功；`resp_code=1/12` 是失败或状态变化，不能用 HTTP 200、data 长度、DOM 动画或图片 score 替代。
9. 登录消费者使用 `uuid=iarVerifyCode` 与 `iarVerifyCode=<same-round token>`。密码错误但 `needVerifyCode=false` 只能证明 token 被接受，不能宣称认证成功。
10. `detect`、`dfpToken` 和设备采集先做 necessity test；当前 verifier/消费者不需要时保持独立，不把未知 MMDS/DFP 逻辑混入 IAR helper。
11. 正式交付至少做两轮独立 fresh verifier 成功；入口不得读取浏览器 Cookie、profile、历史 ticket/data/token，也不得依赖 Playwright、CDP 或 GUI 浏览器。

## Vaptcha V4 专项规则

1. 先读 `references/vaptcha-v4-trajectory-workflow.md`，再实现或改动 Vaptcha V4 手势链。
2. 每轮必须重新建立 `config -> 指纹 -> knock -> PoW -> 图片 -> validate` 状态；不要复用旧 `order`、`knock`、`dfu`、图片或 token。
3. V4 wire body 的字段数组顺序和 `trajectory/pow` 特殊数组结构必须保持不变。
4. 离线视觉模型只能输出轨迹区域候选；最终成功必须由同轮 `validate` 的 `result=true` 与非空 token/dfu 确认。
5. 对同一 challenge 只提交一次；需要多次测量时创建多个 fresh challenge，并分别保存请求、响应、图片和 overlay。
6. 人工轨迹与模型轨迹的几何距离必须同时检查方向、起终点、分支和时序；对称距离不能单独作为正确性证明。
7. 线上 A/B 失败时立即恢复最近已验证 baseline；不要把离线 oracle 或 mAP 改善直接写成线上通过率改善。
8. 所有项目文件引用使用目标项目根目录的相对路径，不把机器盘符和绝对路径写入 skill 或长期证据。

## TianAi 天爱专项规则

1. 先读 `references/tianai-slider-workflow.md`，再实施或修改 TianAi `generate -> verify` 链；该 reference 包含资源确认、iv8 初始化、5x2 图片还原、普通缺口定位、CURVE3 `attr1` 双二次贝塞尔识别、CONCAT `randomY` 上下拼接识别、codec、手动成功轨迹模板和故障矩阵。命中 `type=JIGSAW`、`JIGSAW_`、`data.matrix` 或 2x2 乱序拼图时，同时读取 `references/tianai-jigsaw-workflow.md`。
2. 先确认当前页面实际 collector。`cw.js + cw.wasm` 是已验证的当前动态路径；旧 `main.wasm` 只作为 legacy 诊断，遇到 `RuntimeError: unreachable` 不得直接修改旧 wasm 代替当前 collector。
3. 每轮必须重新生成 `drives/ki`、请求 `/generate`、下载当前签名图片；普通 SLIDER 使用当前 `data.shuffle.pos` 和滑块图，CURVE3 使用当前 `data.attr1`，CONCAT 使用当前 `data.randomY` 推导拼接线和顶部可移动条高度。随后生成当前轨迹、调用当前 `__encrypt__`，并在 verify 前再次取得 verify 所属 `drives/ki`。
4. `generate` 和 `verify` 的 `id`、图片、shuffle、明文、data、drives、ki 必须可在 sidecar 中证明属于同一 round；禁止读取历史 challenge、旧 data、固定 ki 或 `evidence/round_*` 作为生产输入。
5. 图片源坐标、页面显示坐标、slider DOM 的 `left/top` 和指针相对按钮的 start offset 必须分开记录。通常源图是 `600x360`、页面显示是 `300x180`，但实现必须读取当前响应尺寸而不是永久写死；CURVE3 不能把视觉 sliderValue、模板 displacementX 和绝对 clientX 混为同一个坐标；CONCAT 不能把拼接位移、按钮 `left` 和指针 `clientX` 混为同一个值。
6. `data.shuffle.pos` 的已验证方向是 destination-to-source 的 5x2 块重排；还原图不正确时停止定位和 verify，不要调轨迹掩盖图片错误。
7. `preRequest` 明文必须保持字段顺序、页面显示尺寸、绝对首点/差分后续点、64 字符表和可选 UTF-16 `captchaData` 编码；修改 codec 前先做 decode -> encode 逐字回归。
8. 定位器必须保留 top-k、confidence 和 debug image；`ambiguous` 不能静默当作真值。普通 SLIDER 保留同 y cluster，二维峰值缺少目标 y 时执行目标 y 邻域密集 x scan；CURVE3 保存每个 sliderValue 的 ridge/white/contrast/coverage 分数、margin 和预测曲线 overlay；CONCAT 保存 raw top-1、边界锚点、NMS 后多样化候选、锚点冲突值和最终候选索引，不能只输出一个 x。
9. 成功轨迹模板只接收最终 `verify code=200 && success=true` 的真实手动轮；模板按位移、时长、点数、startOffsetX/Y、y 漂移、overshoot 和 settling 分桶，不能把 `4000`、`4001` 或 `50000` 失败轮混入正样本。CURVE3 和 CONCAT 都不能用单条固定轨迹覆盖所有位移；CONCAT 应在相近位移的成功模板中随机选择并排除异常长轨迹。必须做 fresh repeatability，不能把单轮成功当稳定结论。绝对时间戳必须保持真实墙钟顺序：`generate < startTime < stopTime < verify`；禁止用 `stopTime-duration` 回填一个早于 generate 的 startTime，正式路径必须等待声明的轨迹时长。
10. `generate code=200`、WASM 输出非空、参数长度相同、HTTP 200、图片 score 高都不是最终成功；唯一正式验收是同轮 `verify code=200 && success=true`。
11. `4000` 先按 challenge 失效处理；`4001` 先查同轮字段、图片/坐标、`left/top`、指针 offset 和目标 x；`50000` 先查墙钟时序，再查轨迹点数/时长、终点偏移、真实 y 漂移、overshoot/settling 和模板匹配。重点检查 `startTime` 是否晚于 generate response、是否真实等待 `duration`、`stopTime-startTime` 是否等于轨迹时长、verify 是否发生在 stop 之后。禁止用 `stopTime-duration` 回填早于 generate 的 startTime；`--no-replay-sleep` 只能是诊断开关。CURVE3 的视觉值与成功模板位移在小容差内可保留模板位移，差异过大时应缩放成功形状到视觉值并记录两者；每次诊断创建 fresh challenge 且一次只替换一层变量。
12. 明确 Python + iv8 时，协议状态机仍由 `captcha-reverse` 主责，iv8 runtime 由 `iv8-web-reverse` 提供；不能因为 runtime 选择改变最终验证码成功判据。
13. CONCAT 的 `data.randomY` 不是直接拖动距离。当前 bundle 的已验证关系为 `seamSourceY = sourceHeight - randomY`，`stripDisplayHeight = round(seamSourceY * displayHeight / sourceHeight)`；页面版本变化时仍需从 DOM 高度反证该公式。
14. CONCAT 图片识别优先使用拼接线两侧多带宽结构评分、边界锚点和候选 NMS；原始峰与边界锚点冲突过大、位移落在成功模板覆盖之外或候选状态为 `ambiguous` 时，生产默认停止，不用强制 top-1 消耗 challenge。
15. CONCAT 轨迹模板必须保留真实中间 y 漂移；即使最终 `displacementY=0`，也不能把中间 y 归一化为全 0。视觉位移与成功模板位移接近时可保留已验证模板终点，差异较大时按视觉位移缩放成功形状并记录两者来源。
16. 精确图片 SHA-256 命中历史成功图只能标记为 `snapshot-driven-exact-hash` 诊断或显式缓存路径，不能冒充泛化识别算法；默认生产识别仍以当前图片的结构评分为准。
17. JIGSAW 当前 2x2 页面可通过 CSS `background-position` 映射源 tile、CSS `order` 恢复 destination-slot -> source-tile permutation；先做 DOM/source-assisted 解析，再用 24 种排列的 seam continuity 作为无 DOM fallback。图像 top-1 不是最终答案，候选不明确时停止。
18. JIGSAW 的 `matrix`、背景尺寸、当前 tile DOM、交换计划、plaintext、data、challenge id 和 verify 侧 drives/ki 必须同轮；不要把 JIGSAW 当成普通 SLIDER 去寻找透明缺口或历史 `shuffle.pos`。
19. `window.__encrypt__` hook 必须在题面交互前安装；重复相同明文要去重，并用 verify request 时间、id 和受控摘要关联。只有最终 `verify code=200 && success=true` 的明文才能进入 JIGSAW 正样本池；`4000/4001/50000` 只能作为负诊断样本。
20. JIGSAW 当前 Python codec 和自动生成轨迹如果尚未被 fresh verify 证明，只能标记为实验路径。`cw.js + cw.wasm` smoke 非空、HTTP 200 或密文长度匹配都不能证明轨迹 codec 正确。
21. JIGSAW 允许使用已验证正样本做 `snapshot-driven-positive-template` 诊断/回归路径，但必须重写当前时间、使用当前 challenge id、当前 runtime encrypt 和 verify 侧 fresh drives/ki；不得复用旧 token、旧 ciphertext、旧 challenge 或旧动态字段。该模式不能冒充通用视觉/行为求解。
22. JIGSAW 明文中的 `startTime < stopTime` 必须与真实墙钟一致：generate response 之后记录 start，等待声明的轨迹时长，再 encrypt 和 verify；禁止用过去时间回填 start 后立即提交。

## MTCaptcha v1 专项规则

1. 命中 `MTCaptcha`、`mtcaptcha2.min.js`、`service*.mtcaptcha.com`、`/mtcv1/api/getchallenge.json`、`/mtcv1/api/getimage.json`、`/mtcv1/api/solvechallenge.json`、`hasTextChlg` 或 `foldChlg` 后，先读取 `references/mtcaptcha-v1-workflow.md`。
2. 固定同一轮 `getchallenge -> getimage -> solvechallenge` 状态；`ct`、`ss`、图片、`fseed`、`fa`、`kt`、`fs` 和最终 `vt` 不得跨轮拼接。一次提交后丢弃该 round，重新创建 fresh session/challenge。
3. 优先从当前 bundle 和网络证据确认 `tsh`、参数名、Referer、`fa` 分支和 `kt` 生命周期；不要把一个站点或旧 client version 的常量直接当作所有 MTCaptcha 版本的通用算法。
4. `hasFoldChlg` 时保留当前 `fseed/fslots/fdepth/preRes`。已验证分支是 `preRes=true` 在 getimage 前计算并在 solvechallenge 复用，`preRes=false` 的 getimage 使用 `$`、solvechallenge 再计算；必须用当前 challenge 的数值，不能硬编码旧 round。
5. 可用 `ddddocr>=1.6.1` 识别当前 GIF；优先尝试去除装饰的比例裁剪，再尝试原图，过滤并大写归一化后严格匹配当前 `textlen`。禁止静默截断错误长度的 OCR 结果；识别结果仍须经服务端 solvechallenge 验收。
6. 仅当服务端响应同时满足 `HTTP 200`、`code == 1200`、`result.verifyResult.isVerified == true` 和非空 `verifiedToken.vt` 时，才记录为成功。JSON 结构、图片可读、`fa` 形状、64 字符 `kt` 或 OCR 命中都不能替代最终验收。

## 硬规则

1. `get/load/convert` 输出、图片、cookies、challenge headers、randomKey 与最终 `verify/check` 必须来自同一轮会话。
2. 成功必须以服务端最终响应为准，不以图片识别、`ret == 0`、本地 `w` 形状或 token 长度单独判定；验证码接口的 gateway/verify 成功仍需由第一条下游业务请求确认是否真正放行。
3. 在把任务升级为具体厂商/家族、扩展 runtime 或转交 specialist 前，至少保留两类独立证据；单个路径、cookie、错误码、token 名称或一次 helper smoke 只能记录为假设。
4. 浏览器自动化只作为取证手段；除非用户明确要 UI 自动化，否则最终交付应是协议回放脚本与本地辅助工具。
5. 普通 OCR、泛化定位 sign 入口、DevTools hook、通用 Node.js 补环境、普通阿里云 RPC 签名、非验证码 WAF/cookie challenge 不触发本 skill；MTCaptcha OCR 只有作为同轮协议求解的子步骤时才纳入。
6. 视觉模型训练交给 `captcha-vision`；泛化入口定位或多层未知协议返回 `trace`；明确 iv8 后端交给 `iv8-web-reverse`。
7. 目标目录和参考项目同时出现时，只在目标目录写入、运行和验收；参考项目只读。
8. 分支细则、图片识别默认策略和常见成功标记见 `references/routing-quick-rules.md`。
9. `skill_checkpoint` 只记工程事实。
10. JD 专项必须遵守“已知 baseline 优先、`tp != 30` 立即停止、bootstrap 与 final acceptance 分层”三项门禁；门禁未通过时不得进入轨迹调参。

## 控制变量诊断法

当浏览器/官方客户端能通过而本地协议链失败时，默认使用正样本锚定的单变量替换法，不要同时改轨迹、token、指纹、传输和时序：

1. 先保存一轮服务端最终 `verify/check` 成功的完整正样本，请求、响应、sidecar、token、行为数据和 challenge/session 必须同轮。
2. 先证明原始成功 body 经本地 HTTP 客户端发送仍可通过，以排除 TLS、HTTP、headers、cookie 和签名传输路径；若 verify/token/nonce 只能消费一次，每个实验使用 fresh challenge。
3. 按协议所有权一次只替换一层，例如 `data/w`、token、sidecar/telemetry、主 verify 参数；其余层保持正样本原值。每轮只依据服务端最终响应判定该层是否退出嫌疑集。
4. 某层替换后首次失败，就停止扩大变量；递归解密、解压或解析该层，比较 hidden envelope、版本 marker、字段拓扑、时间和关联键，不只比较长度、Base64 外观或 HTTP 200。
5. 修复后做反向最小控制：撤掉无关实验逻辑，只保留候选根因修复；fresh 在线成功至少复验一轮，才能把结果写回正式实现/profile。

实验矩阵必须记录“保留项、唯一替换项、challenge/nonce、最终结果”。禁止把同一 challenge 成功后出现的 duplicate/已消费错误当成第二个变量结论，也禁止从多变量组合成功直接声称某一项是根因。平台具体替换顺序放在对应 reference；阿里 V2 见 `references/aliyun-captcha-v2-workflow.md`。

## Alibaba Baxia / NC / Fireye 可迁移工作流

本节沉淀一类常见的阿里系滑块链路：Baxia punishment page + AWSC/ET + NC slider + Fireye `n` + `_rand` + `bx-et` + `bx-pp` + `x5sec`。需要从空项目开始实现完整链路时，先读取 `references/alibaba-baxia-nc-fireye-from-zero.md`；该 SOP 按 Stage 0 到 Stage 15 给出输入、动作、产物、停止条件、验收矩阵和主程序骨架。本节保留通用判断与关键约束。它适用于出现以下组合的站点：

```text
bxpunish / bxuuid / x5secdata
AWSC NC slider
fireyejs / et_f.js / punishpage
/_____tmd_____/slide
/_____tmd_____/report?type=verifyFail
x5sec / bx-x5sec
```

### 1. 先确认协议边界

不要把这类链路误判成普通图片验证码或单独的签名函数。最小协议图通常是：

```text
业务 GET
  -> Baxia 返回 punishment HTML
  -> 解析 _config_ / SECDATA / NCAPPKEY / NCTOKENSTR / nonce / pp
  -> 加载或报告 rand、AWSC/ET、NC、UMID、DSS、secaptcha
  -> initialize.jsonp
  -> 生成 Fireye n、_rand、bx-et、bx-pp
  -> GET /_____tmd_____/slide
  -> slide code=0 + Set-Cookie/BX-X5SEC: x5sec
  -> 可选 setCookieSuccess report
  -> 携带 x5sec 重放原业务 GET
  -> 最终业务响应
```

必须把三个层次分开：

1. **challenge bootstrap**：首次业务请求、punishment HTML、`x5secdata`、`bxuuid`、`_config_`、页面版本和资源状态。
2. **slide verification**：`slidedata`、`n`、`_rand`、`bx-et`、`bx-pp`、`ppt`、`ts`、`v` 与同轮 cookies。
3. **post-verify business replay**：服务端下发的 `x5sec` 是否真的能让原业务请求得到预期结果。

`HTTP 200` 不是成功标记。以下结果必须分类：

```text
slide HTTP 200 + result.code=300  -> challenge/Fireye/状态未被接受
slide HTTP 200 + result.code=8778 -> 请求进入更深校验，但 payload/状态仍不匹配
slide HTTP 200 + result.code=0   -> 继续检查 x5sec 和业务回放
business HTTP 419                 -> 本站点上通常表示 x5sec 已被业务层接受
```

只有 `code=0 + x5sec + 预期业务响应` 才能进入成功样本池。不同站点的业务成功码可能不同，必须以目标站点实测为准。

### 2. 同轮状态是硬约束

每次测试必须重新建立完整 fresh round。以下字段不得跨轮拼接：

```text
challenge HTML
SECDATA / x5secdata
bxuuid / NCTOKENSTR
NCAPPKEY
nonce / secaptcha asset
umidToken
cna / arms_uid / tfstk / cbc
Fireye n
_rand
bx-et / bx-pp
slide ts / v / ppt
x5sec
```

尤其注意：`n`、`_rand` 和 `x5sec` 经常是一次性或强关联材料。一个 challenge 被本地替换实验、精确重放或失败重试消费后，浏览器中剩余请求不能继续当作同轮成功样本。

每个实验 sidecar 至少记录：

```text
round id
challenge token 摘要
page/slide URL
Fireye/NC/ET 版本
UA 和 profile 名称
n / rand / bx-et / bx-pp 的长度和 hash
request order
attempt number
verifyFail report 是否发送
最终 slide code
最终 x5sec 是否存在
最终业务 status
```

不要在长期 skill 或报告中写机器盘符、用户目录或绝对路径。使用项目相对路径，例如：

```text
evidence/round-001/slide.json
js_reverse_cache/fireyejs_1.234.20.js
android_h5_fireye_profile.json
```

### 3. 取证优先于猜参数

浏览器只用于被动取证时，推荐顺序：

1. 清理旧 network queue，建立新页面和新 challenge。
2. 在最终 `/slide` 发送前捕获完整请求，而不是只盯着初始化请求。
3. 保存 query 参数和请求头中的 `n`、`_rand`、`bx-et`、`bx-pp`、`ppt`、`ts`、`v`、`slidedata.p`。
4. 捕获 `/slide` response body、`Set-Cookie`、`bx-x5sec`。
5. 获取 `/report?type=verifyFail` 或 `setCookieSuccess` 的 initiator 和参数。
6. 获取原业务回放的 status 与 response headers。
7. 若需要事件证据，在页面最早阶段安装被动 recorder，把事件写入 session storage，成功导航后再读取。

最终 `/slide` 的 initiator 往往比初始化断点更有价值。典型调用链是：

```text
ET signer
  -> punishpage callback
  -> NC callback
  -> XHR/fetch send
```

这能确认 `n` 是哪个 runtime、哪个 callback 阶段生成的，也能避免误把 preflight `n` 当作最终 `n`。

### 4. 识别 Android H5 与 Desktop Web

“浏览器页面切成移动端预览”不等于完整 Android H5 协议 profile。设备模拟只可能改变 viewport、部分 UA 或触摸能力；协议层还要同时检查：

```text
scene=register_h5
sec-ch-ua-mobile=?1
sec-ch-ua-platform="Android"
Android UA
navigator.platform
navigator.maxTouchPoints
screen / availWidth / availHeight / DPR
WebGL vendor/renderer
NC slider geometry
touch event semantics
mobile bx-et
rand backend
```

应把这些字段固化为一个相对路径 profile，例如：

```text
android_h5_fireye_profile.json
```

推荐 profile 至少包含：

```json
{
  "scene": "register_h5",
  "navigator": {
    "platform": "Linux armv81",
    "maxTouchPoints": 5,
    "hardwareConcurrency": 8,
    "deviceMemory": 8
  },
  "screen": {
    "width": 412,
    "height": 915,
    "availWidth": 412,
    "availHeight": 915,
    "devicePixelRatio": 2.625
  },
  "webgl": {
    "vendor": "Qualcomm",
    "renderer": "Adreno (TM) 750"
  },
  "geometry": {
    "left": 50,
    "top": 663.5,
    "width": 62,
    "height": 47,
    "distanceRange": [60.5, 63.2]
  },
  "trajectory": {
    "steps": [96, 104],
    "mainDragMs": [820, 900, 980, 1060, 1180],
    "holdStartMs": [60, 90, 130, 170],
    "holdEndMs": [80, 120, 160, 220],
    "yJitter": [0.8, 1.0, 1.25, 1.6],
    "delayMs": [350],
    "dispatchTouch": true
  },
  "fireyeInit": {
    "MaxMTLog": 300,
    "MTInterval": 4,
    "MinMTDwnLog": 30,
    "MaxKSLog": 14,
    "MaxFocusLog": 6,
    "MaxNGPLog": 200,
    "NGPInterval": 4,
    "Enable": 3,
    "location": "cn",
    "_umopt_npfp": 1
  }
}
```

jsdom、IV8 或其他 backend 都应读取同一份 profile，只在 runtime 适配层处理对象模型差异。禁止维护两套“看起来相同但实际数值不同”的移动端默认值。

### 5. Fireye backend 选择

Fireye `n` 是整个链路的主要风险点。可采用两类本地 backend：

#### 5.1 Node/jsdom backend

适合以下情况：

- 成品或历史项目已经用 jsdom 取得服务端成功。
- Fireye 主要依赖可控 DOM、navigator、canvas/WebGL、时间和事件对象。
- 目标是优先恢复一个可交付的 browser-free collector。

jsdom 需要补齐：

```text
location / history / currentScript
navigator / screen / languages / platform
canvas 2D / WebGL / toDataURL
audio 最小对象
crypto / indexedDB / permissions / mediaDevices
Date.now / performance.now / Event.timeStamp
getBoundingClientRect / offsetWidth / offsetHeight
mouse + touch dispatch
```

成品成功样本通常比“单纯长度匹配”更重要。若成品 jsdom 的 `n` 长度、p 字段、生命周期和服务端结果稳定，应优先把它作为 formal backend。

#### 5.2 IV8 backend

适合以下情况：

- 用户明确要求 Python + IV8。
- 需要更接近浏览器 descriptor、event loop、DOM/layout 或多阶段脚本生命周期。
- 已经有固定的 Fireye 入口，并且 IV8 runtime 能加载目标脚本。

IV8 不应只补一个 `window` 就直接调用最终函数。至少要显式验证：

```text
__fycb(umid)
-> fy.init(options, callback)
-> resetSA（若该版本需要）
-> __fycb(umid)
-> startRecord
-> touch/mouse event replay
-> __fycb(umid)
-> getUidToken
-> getFYToken({reqUrl: slideUrl})
```

必须记录：

```text
uid length
n length / hash
virtual elapsed
event counts
listener hits
surface snapshot
pre-token snapshot（若启用诊断）
networkRequests == 0（isolated collector）
```

成功的 IV8 smoke 不自动证明它比 jsdom 更稳定。formal backend 仍应由 fresh challenge 多轮服务端验收决定。

### 6. jsdom 与 IV8 的对照方法

当两种 backend 使用相同 Android H5 profile 时，不要比较最终 `n` 是否相等。`n` 通常由 runtime 对象、随机数、时间、事件和 session 状态共同决定，两个正确实现也可能得到不同密文。

推荐分层比较：

```text
第一层：profile
  UA、platform、screen、DPR、WebGL、几何、scene

第二层：lifecycle
  __fycb/init/resetSA/startRecord/getUidToken/getFYToken 顺序

第三层：event input
  count、type、buttons、touch fields、target、client/screen coordinates、timeStamp

第四层：runtime state
  listener hits、recorder bucket 数量/宽度、pre-token snapshot、virtual elapsed

第五层：output
  uid length、n length、n hash、HTTP slide code、x5sec、业务 status
```

输出长度和 hash 只能是诊断证据，不能作为成功证明。最小差分表必须写明：

```text
same challenge?
same UMID/cna/cookies?
same profile?
same lifecycle?
same event sequence?
only backend changed?
server final result?
```

### 7. `code=300` / `8778` 的诊断顺序

遇到 Desktop 或 H5 本地 replay 连续 `300`，按以下顺序排查：

1. 确认是否真的使用了 fresh challenge，是否复用了已消费的 token。
2. 确认 `scene`、UA、Client Hints、`p.ncbtn` 与 Fireye 几何一致。
3. 用已验证 backend 组合做二分：`mobile bx-et + node rand + mini/append`。
4. 确认 `/report?type=verifyFail` 在失败后、下一次 slide 前发送，并且没有把 retry report 当成成功。
5. 用同轮成功浏览器请求做单字段替换，先排除 HTTP/TLS、cookie、bx-et、bx-pp、rand。
6. 只剩 Fireye `n` 时，比较 lifecycle、event recorder 和 pre-token state，不要继续调 ppt、header 长度或随机重试。

Desktop Web 形态尤其要谨慎。真实 Edge 成功不代表 browser-free Desktop collector 可复制；Desktop `scene=register`、Win32 surface、desktop geometry、mouse-only 事件和不同 `n` 可能长期返回 `300`。若成品证明 Android H5 profile 更稳定，应把“桌面主机运行”与“Desktop Web 协议画像”分开：

```text
桌面主机 + Android H5 protocol profile = 可交付路径
真实 Desktop Web profile = 取证/差分路径，除非有 fresh 稳定验收
```

不要用增加重试次数掩盖 backend 差异。`300` 连续多轮时，先确认 retry 控制变量是否真的生效：入口可能固定了旧变量，例如 launcher 设置 `ALI234_SLIDE_ATTEMPTS=8`，而用户传入的 `ALI234_MAX_ATTEMPTS=20` 没有被读取。重试配置应有明确优先级，并在 artifact 中记录实际 attempts 数量。

### 8. 重试与 `bx-pp` 状态

常见的移动 H5 retry 形态是：

```text
attempt 1: bx-pp mini -> code=300
report verifyFail
attempt 2: bx-pp append -> code=0 或继续 300
```

但不能假定每个站点一定在第 2 次通过。重试时必须：

- 同一 challenge/session 内重新生成新的 `n` 和 `_rand`。
- 每次失败后只发送一次对应 `verifyFail` report。
- `bx-pp` 的 mini/append 由 profile 或明确状态机控制。
- `ppt` 使用真实生成/请求时序，不能把固定长度或固定值当作根因。
- 记录实际 attempt 数，不要只记录配置的 max attempts。

如果成品成功样本第 1 次或第 2 次就通过，而当前实现需要 15 次，优先检查 Fireye backend、profile、生命周期和时间状态；不要把 15 次设置成“正式解决方案”。

### 9. 统一验收门

每个 backend 至少要有独立 fresh challenge 的验收 artifact。artifact 不需要保存敏感完整 token，可保存受控摘要，但必须足以复核：

```text
backend
profile name/version
fireye version
attempt sequence
nLen / randLen / bx-et length / bx-pp length
slide response code
x5sec present
final business status
```

推荐 smoke 分层：

```text
Stage 1: 本地 helper 可生成非空 uid/n，isolated networkRequests=0
Stage 2: fresh /slide code=0 + x5sec
Stage 3: fresh x5sec business replay 达到目标 status
Stage 4: 多个独立 challenge 统计成功轮次和失败类型
```

只有 Stage 3 才能称为完成。Stage 4 用于选择 formal backend，不要求两个 backend 生成相同的 `n`。

### 10. 清理与可复现性

逆向项目很容易被探针、旧浏览器抓包和中间日志淹没。清理时先建立运行依赖白名单，再删除历史材料。

正式依赖通常包括：

```text
协议主编排脚本
选定 backend 的 helper
profile / state / WASM
Fireye、NC、ET、secaptcha 运行资产
正式 launcher
```

可删除候选通常包括：

```text
probe_*.py
旧 cv prepare 脚本
撤回的 Desktop 实验结果
旧 Edge/chrome round 目录
大体积 ET instrumentation dump
__pycache__ / *.pyc
旧 profile 备份
```

删除前必须做三项检查：

1. `rg` 查找正式入口和 helper 是否引用该文件。
2. 做一次 Python import/compile 和 Node syntax check。
3. 用 fresh challenge 跑一次 Stage 2 或 Stage 3 验收。

不要删除正在被 fallback backend、profile loader、rand state、WASM 或 Node helper 使用的文件。README 和分析文档中的旧路径也要同步更新，避免清理后留下失效运行说明。

## Maintenance Check

修改平台路由、触发边界、handoff 或 eval 后运行 `python scripts/validate_skill.py <skill-root>`，再运行通用 `quick_validate.py`。修改苏宁 fast path、runtime asset 或 iv8 生命周期说明后，额外运行 `python scripts/validate_suning_iar_fastpath.py <skill-root>`。

## JD 分支补充

确认 JD JCAP 后，先完整读取 `references/jd-jcap-v2.8.5-workflow.md`。该参考覆盖：CloakBrowser 被动取证、JD JCAP 2.8.5 状态机、Python + iv8 + curl_cffi 后端、嵌入式 WASM、`tk/ct/cs` 输入边界、图片坐标映射、固定 y 的 `TM_CCORR_NORMED` 诊断、可信手动轨迹样本、受控 A/B 和账号/设备风控污染判定。

执行时必须先建立同轮证据，再实现；不要把文章字段、HTTP 200、密文长度、图片 score 或单次轨迹结果当作最终成功。手动轨迹只有在最终业务响应 `code=0`、无 next `tp`、`vt` 非空时才能进入正样本池。连续 live 请求导致的失败批次必须标记为风险状态污染，不能据此继续调轨迹或要求用户补采样本。

## 交付内容

交付时说明：

- 请求顺序与同轮状态约束。
- 主 verify 之外必须存在的 sidecar/telemetry 及其关联键。
- 已还原的动态字段与本地生成 helper。
- 图片识别路径与坐标系映射。
- 最终 `verify/check` 响应证据。
- 可运行命令序列或脚本路径。
