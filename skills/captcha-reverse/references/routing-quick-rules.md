# Routing Quick Rules

本文件承接 `SKILL.md` 中不适合启动即读完的平台细则。先用主文件完成一级路由；命中具体家族、分支冲突或需要高频规则时再读本文件。

## Branch Details

- **腾讯 EdgeOne / TCaptcha / `cap_union_prehandle` / 动态 `tdc.js` / `TDC.getData(true)` / `cap_union_new_verify` / `errorCode=12`**：读取 `references/tencent-edgeone-tdc-workflow.md`；验证码状态机和成功判据由本 skill 负责，明确采用 Python+iv8 时由 `iv8-web-reverse` 提供执行后端。
- **MTCaptcha v1 / `service*.mtcaptcha.com` / `getchallenge.json` / `getimage.json` / `solvechallenge.json` / `hasTextChlg` / `foldChlg`**：读取 `references/mtcaptcha-v1-workflow.md`；按同轮 `getchallenge -> getimage -> solvechallenge` 恢复 `ct/ss/image/fseed/fa/kt`，`ddddocr` 只作为文字答案子步骤，最终以 `code=1200 && isVerified=true && verifiedToken.vt` 验收。
- **苏宁 Passport / IAR JIGSAW / `iarVerifyCodeTicket` / `sncaptchaMgr` / `gTypes/queryToken` / `/iar-web/init.json` / `/iar-web/validate.json`**：读取 `references/suning-iar-jigsaw-workflow.md`；按同轮 `login Session -> ticket -> init param/tInfo/current mgr -> image draw mapping -> gap/trajectory/data -> resp_code=0 token -> login consumer` 执行。完整协议由本 skill 主责，明确 Python+iv8 时由 `iv8-web-reverse` 提供 isolated manager runtime；只找 manager 入口/调用栈留在 Trace，只做图片 gap 转视觉处理。
- **天爱 TianAi / `captcha.tianai.cloud` / `/v2/api/open/captcha/generate` / `/v2/api/open/captcha/verify` / `data.shuffle.pos` / `data.matrix` / `JIGSAW_` / `__drives__` / `__ki__` / `__encrypt__` / `cw.js` / `cw.wasm`**：先读取 `references/tianai-slider-workflow.md`；命中 `type=JIGSAW`、`JIGSAW_`、`data.matrix=[2,2]` 或 2x2 乱序拼图时，再读取 `references/tianai-jigsaw-workflow.md`。JIGSAW 按同轮 `generate -> DOM background-position/order 排列解析 -> 交换行为明文 -> encrypt -> verify` 执行，不套普通 5x2 缺口流程；Python+iv8 只是 runtime backend，不能绕过验证码 skill 的最终服务端验收。
- **CSDN 文字点选 / embedded_captcha / click_v2**：读取 `references/csdn-point-click-workflow.md`。
- **携程 captcha/v4 自研验证 / risk_inspect / verify_jigsaw / verify_icon**：读取 `references/ctrip-captcha-v4-workflow.md`。
- **百度 Passport 旋转/Spin V2 / `passport.baidu.com/cap/init` / `/cap/style` / `/cap/img` / `/cap/log` / `spin-0` / `backstr` / `ext.p` / `en_conf` / `cv=submit`**：读取 `references/baidu-passport-spin-v2-workflow.md`。
- **字节系 VerifyCenter / 抖店登录滑块 / captchaBody / cyfreso / BDMS+mssdk**：读取 `references/bytedance-verifycenter-workflow.md`。
- **阿里云 Captcha V2 / InitCaptchaV2 / VerifyCaptchaV2 / DeviceConfig / deviceToken / Log2 / Log3 / T001 / 昨日 T001 今日 F025 / FeiLin 日更或灰度发布**：读取 `references/aliyun-captcha-v2-workflow.md`。
- **阿里云 Captcha V3 / InitCaptchaV3 / VerifyCaptchaV3 / PUZZLE / pe.xxx / FeiLin 日更 / run_v3_fast / 昨日 T001 今日 F001**：读取 `references/aliyun-captcha-v3-workflow.md`；版本轮换先走其中“FeiLin 日更快速分支”，主入口是 `run_v3_fast.py`，优先目标项目内的 `auto_update_feilin_profile.py`，不要先调轨迹，也不要改 V2 项目文件。
- **mCaptcha PC 滑块**：出现 `mCaptcha.pc.min.js`、`captchasInit`、`capTicket`、`capKey`、`/mCaptcha/key`、`/mCaptcha/info/`、`/mCaptcha/validate`、`clickCaptcha/validate`、`validData`、`UserOpListener` 或 `fp.min.js` 组合时，读取 `references/mcaptcha-pc-workflow.md`。流程止于验证码服务端 `code == 0` 且 `result` 非空；不要把后续业务表单或查询逻辑带入该分支。
- **滑块类验证码**：先读取 `references/slide-captcha-overview.md` 判断平台，再按平台读取 `references/geetest-gt3-workflow.md`、`references/geetest-gt4-workflow.md`、`references/yidun-workflow.md`、`references/shumei-workflow.md`、`references/yunpian-workflow.md` 或 `references/tianyu360-workflow.md`。

## Aliyun Fast/Full Split

- **V2 极速分支（用户说“走极速分支”等时强制进入）**：只读 `references/aliyun-captcha-v2-workflow.md` 的“极速分支（固化定值）”。核心是 skill 内已验证的固定密钥/公式/协议骨架直接落盘到目标目录，再用本目录 capture 生成动态 `t001_profile` 并跑 T001。**不是**默认去抄参考项目；参考项目仅在用户给出且含大体量 `vm_codec` 字节码时可只读复用该文件。禁止从零重解已固化层、禁止 jsdom、禁止拖滑块主路径。
- **V2 完整分支（用户显式要求或极速硬停）**：用户说“走完整分支”“从零恢复”“完整协议分析”，或极速定值与当前 capture 冲突（AES/token 布局/stream key/field21 全挂）时，走同文件完整协议恢复章节。
- **V2 版本轮换**：昨日 T001 今日 F025 且目标目录已有 runner 时，先走“FeiLin/sg 日更快速分支”。
- **V3 日更**：V3 主入口是 `run_v3_fast.py`，动态脚本是 `pe.xxx` 不是 `sg.xxx`；出现昨日 `T001`、今日 `F001/F025` 时先比 `DeviceConfig.version` 与 `profile.feilinVersion`，优先跑目标项目内的 `update_t001_profile.py`（完整日更，支持 `--resume-artifact`）或 `auto_update_feilin_profile.py --apply` / `python run_v3_fast.py --auto-update`。禁止用 V2 会话/画像覆盖 V3，禁止只改 field21 不换完整 Log2 画像；CloakBrowser 解析失败不得静默换 Chrome/Edge，画像未稳定（`varyingFields=[...]`）必须拒绝更新，sidecar marker 必须动态取 `fullDeviceFields[0]`。

## GT4 Variant Notes

- **极验 GT4 且用户明确要求纯 Python / 纯算**：读取 `references/geetest-gt4-workflow.md` 的“纯 Python 极速路径”和“GT4 slide 纯 Python 识别与协议回放”小节，优先复用 `scripts/gt4_pure_replay.py`；不要先搭 Node helper、浏览器环境或全量解混淆。滑块识别默认保留 non-simple/simple 双结果和置信度，低置信度只能走明确回退或 fresh 换题，不能在同一 lot 扫坐标。
- **无感 / 一键通过 / `risk_type=ai` / `captcha_type=ai`**：读取“无感（ai）”章节，优先复用 `scripts/gt4_ai_pure.py`。该分支没有图片、滑动距离、轨迹、`passtime` 或 `userresponse`；不要套滑块或文字点选流程。
- **文字点选 / `risk_type=word` / `captcha_type=word` / `imgs+ques`**：读取“文字点选（word）”章节，优先复用 `scripts/gt4_word_pure.py`（可选 `scripts/gt4_word_run.py` 做多轮验收）。加密壳与滑块同源，但 `userresponse` 编码完全不同；不要套滑块的 `setLeft` 公式。
- **九宫格 / `risk_type=nine` / `captcha_type=nine` / `imgs+ques+nine_nums`**：协议答案是 0 基九宫格索引转 1 基 `[row,col]` 对，例如索引 `0,3,8 -> [[1,1],[2,1],[3,3]]`；图片识别模型训练交给 `captcha-vision`，本 skill 只负责同轮状态、`w`、PoW/GCT、verify 回放和服务端判据。
- **普通图标点选 / `risk_type=icon` / `captcha_type=icon` / `imgs+ques`**：word/icon 共用 `round(x/w*10000), round(y/h*10000)` 坐标编码，但目标来自提示图标，必须按 `ques_0/1/2` 顺序输出三个背景中心点；检测模型、YOLO/CLIP/排序器训练交给 `captcha-vision`。
- **SVG 图标点选 / `risk_type=svg_seed` / `captcha_type=svg_seed` / `question_path+answer_path`**：不是九宫格图片题，也不是普通 icon 点选；`question_path` 是 3 帧循环 SVG，每帧 3x3 候选，`answer_path` 是目标 PNG base64。`userresponse` 只提交 1 基 `[row,col]`，目标帧必须通过 `passtime` 落在 SVG keyframes 的可见区间表达。
- **消消乐 / `risk_type=match` / `captcha_type=match` / `ques` 为 3x3 数字矩阵**：不需要 OCR 或滑块缺口识别；`userresponse` 是两格相邻交换坐标 `[[x,y],[x,y]]`，坐标直接对应 `ques[x][y]` 与前端 `dataId`。
- **五子棋 / `risk_type=winlinze` / `captcha_type=winlinze` / `ques` 为 5x5 数字棋盘**：优先复用 `scripts/gt4_winlinze_replay.py` 和 `scripts/gt4_winlinze_helper.js`。该分支不需要 OCR；`userresponse` 是先点非空棋子、再点空格的 0 基 `[row,col]` 坐标对，例如 `[[3,0],[1,2]]`。

## High-Frequency Rules

MTCaptcha v1 的文字图默认优先使用 `ddddocr>=1.6.1`，先尝试去除两侧装饰的比例裁剪，再尝试原始 GIF；过滤字符并按当前 `textlen` 校验，不能把错误长度结果静默截断。详细流程见 `references/mtcaptcha-v1-workflow.md`。

1. `get/load/convert` 输出、图片、cookies、challenge headers、randomKey 与最终 `verify/check` 必须来自同一轮会话。
2. 不要只凭图片识别结果判断成功，必须以服务端最终响应为准。
3. 点选验证码要分清三件事：目标文字识别、坐标识别、协议复现。
4. 滑块验证码要分清三套坐标：原图/还原图缺口距离、页面显示或提交距离、行为轨迹与耗时。GT4 的 `gap_x -> setLeft` 偏移必须按当前页面成功样本校准；`passtime`、`td` 轨迹时长和轨迹 endpoint 不能互相替代。
5. 动态材料尽量归档到项目 `js_reverse_cache/`：原始响应、解码 payload、图片、form body、请求头、服务端响应。
6. 浏览器自动化只作为取证手段；除非用户明确要 UI 自动化，否则最终交付应是协议回放脚本与本地辅助工具。
7. 行为轨迹中的时间戳、声明耗时与真实请求时序必须一致：轨迹不能延伸到请求发送之后，纯协议回放不能只伪造时长而省略实际等待。
8. 开始重写算法前先在当前工作区搜索同平台实现和已验证常量，例如 `gt4_pure.py`、`gt4_protocol.py`、`RSA_N_HEX`、`PKCS1_v1_5`；复用时必须重新核对当前 bundle 元数据和服务端结果，不能直接相信旧脚本。
9. 用户同时给出“目标目录”和“参考项目/参考文档”时，所有写入、运行、验收默认只允许发生在目标目录；参考项目只读。
10. 阿里 V2/V3 进入 `Window`、`Element`、`Range`、`navigator`、`document`、`canvas` 等 Node/jsdom 补环境时，必须立即停止并回到 profile/field21/DOM-free `vm_codec` 路线。FeiLin 画像更新不是浏览器环境补丁任务。
11. 字节系 VerifyCenter 要同时检查挑战新鲜度和服务端时钟：用 `/captcha/get` 的 `x-tt-timestamp` 对齐 `tmp`、轨迹声明耗时和真实发送时刻；“立即提交”和“弹出过久”都可能返回同一个 `VerifyErr`。
12. 对 verifier-gated 验证码，不要只盯最终 verify：先枚举同 session 的设备日志、预热、sidecar 和 telemetry 请求；用阻断/放行做控制变量实验，避免把 `F001` 一类风险拒绝武断归因于轨迹。
13. 遇到“完整设备画像 + 稀疏增量 token”模型时，必须共享 session、采集基线、counter、关键时间字段和动态指纹；单包能解密、checksum 正确不等于跨包状态一致。
14. 用户明确只做验证层时，不得把验证码通过后的业务回放加入运行入口或成功条件；最终证据停在验证码服务端的通过码。
15. 阿里 V2 出现“刚才还能 `T001`、现在固定 `F025`”时，不要用单次 Init 判定版本。先多样本统计 `DeviceConfig.version`，按频次选择主流 rollout cohort；采集时归档并跳过其他 cohort。
16. 阿里 V2 候选画像必须先在内存中完成 Log2/Log3 `200 / true` 和 Verify `T001 / true`，再加锁原子替换正式 profile。结构、加密或 field21 公式变化时必须停止并保留旧画像。
17. 阿里 V2/V3 field21：先试 classic `source/mask`（如 106-112 族）；多样本 classic 穷举无解时视为算法换代，禁止硬凑歧义常量。
18. 腾讯 TDC 的 `sess/sid/pow_cfg/tdc_path/动态 tdc.js/collect/eks/POW/verify` 必须同轮；先抓真实 `TDC.setData` 顺序和 iframe baseline，再做 iv8 环境差分。
19. 天爱 `generate` admission 通过后，仍必须重新下载当前签名图片并绑定当前 `shuffle.pos`、id、轨迹、data、verify drives/ki；`drives/ki` 长度、图片 score、`__encrypt__` 不报错或 HTTP 200 都不能替代 `verify code=200 && success=true`。
20. 苏宁 IAR 的 Session/ticket/init param+tInfo/current mgr/图片/draw mapping/gap/轨迹/data/token/login consumer 必须同轮；`resp_code=0` 还要检查 token 非空，登录密码错误且 `needVerifyCode=false` 只证明验证码 token 被接受。

## Image Recognition Defaults

- 中文提示图 OCR：优先用 PaddleOCR。
- 滑块缺口识别：先按平台还原图片，再用 OCR/OpenCV/识别服务。
- 点选坐标：可以使用云端点选服务，但必须校验返回点数与最终服务端响应；保留手动坐标兜底路径。
- 通用图标点选若使用云码/打码接口，必须把返回坐标映射回验证码背景图坐标，并保存打码响应、拼接图、偏移 meta 与 `verify/check` 响应。
- 极验 GT4 `svg_seed`：优先离线解析 `question_path` 的 SVG 三帧和 `answer_path` PNG；可用 Node `sharp` 或浏览器 canvas 渲染 27 个候选，再按 SAD/MSE/alpha IoU 排序。
- 极验 GT4 普通 `icon`：不要和 `svg_seed` 混淆。`icon` 是 `imgs` 背景 + `ques[]` 提示 PNG，答案是三个原图中心点按提示顺序编码为 `round(ratio*10000)`。
- 极验 GT4 文字点选：`ddddocr>=1.6.1`，用 `default+beta` 双模型多预处理投票；ques 白底图通常比背景艺术字稳。识别后必须按 ques 顺序匹配背景框，再用匈牙利一对一分配。

## Success Markers

有 JSONP 时必须先解析 JSONP。不要把 `ret == 0` 单独视为成功，因为很多失败响应也会带 `ret: 0`。

常见成功标记：

- `result == "success"`
- `code == 200`
- `X-CAPTCHA-VERIFY: 1`
- 腾讯 TDC：`errorCode == "0"` 且 `ticket`、`randstr` 均非空
- 苏宁 IAR：`str(resp_code) == "0"` 且 token 非空；含登录目标时再检查同轮 consumer 不再要求验证码
- 百度 Passport Spin V2：`code == 0 && data.op == 1`
- 阿里云 Captcha V2 / V3：`VerifyCode == "T001" && VerifyResult == true`
- 平台特定的 `PASS`、`validate`、`token`
- 验证码通过后的业务接口回放成功
