# AST Deobfuscation Profile

## Contents

- [唯一职责](#唯一职责)
- [触发边界](#触发边界)
- [交付模式](#交付模式)
- [工作流](#工作流)
- [脚手架选择](#脚手架选择)
- [Failure Modes](#failure-modes)
- [完成标准](#完成标准)

## 唯一职责

把目标源码恢复成可读、可验证、可继续迭代的结构。Profile 入口负责识别家族和路由，plugin 负责家族 pipeline，visitor 只做一种 AST 变换。

本 profile 不替代请求观察和入口定位。跨阶段约定见 `../../../../_shared/js-reverse-workflow.md`。

本文件中的 `scripts/` 和 `references/` 均相对于 `$AST_PROFILE=$SKILL_DIR/references/profiles/ast-deobfuscate`。

## 触发边界

应该触发：

1. 用户明确要求解混淆、还原源码或展开控制流。
2. 用户要 Babel pass、plugin/visitor 工程或中间产物。
3. 用户区分阅读版与调用版输出。

不应触发：

| 当前结果 | 转交 |
|---|---|
| 函数位置、脚本 URL、调用链 | 返回 Trace Observe/Capture，使用浏览器逆向取证工具定位 |
| DevTools 可粘贴 Hook | `trace` browser-hook profile |
| 入口已知，需要本地补环境 | 先过 Runtime Selection Gate；若用户明确指定 iv8 且 capability snapshot 可用，直接转 `iv8-web-reverse`，否则简单同步入口转 `trace` env-patch，复杂浏览器语义转 iv8 backend |
| 明确“用 iv8 补环境”或 Python + iv8 | capability snapshot 可用时，`iv8-web-reverse` 是 primary，先读取该 skill；不可用时返回 Trace local-helper/env-patch fallback |
| 多层协议与最终 collector | 退出本 profile，返回 Trace core loop |

如果请求参数链尚未确认，只对已经命中的关键脚本做定向还原，不默认处理整站 bundle。

## 交付模式

默认先交付阅读版：不额外添加 `require`、`module.exports` 或调用包装。用户明确需要调用入口时，再从已验证阅读版派生调用版。

标准产物：

```text
project/
  source/original/target.js
  source/deobfuscated/target_deobf.js
  intermediate/target_stepN.js
  scripts/template-project/src/main.js
  decode-action-workspace/        # 可选，长期维护时使用
```

临时源码和日志写到执行项目的 `js_reverse_cache/`；原始输入永不覆盖。

🔴 CHECKPOINT：创建脚手架或复制模板前，声明目标项目、输入、输出和阅读版/调用版。用户只要分析时不创建工程。

🔴 CHECKPOINT：升级调用版前，先通过语法检查并确认关键逻辑未被激进内联破坏；未确认时不加模块包装。

## 工作流

### 1. 输入体检

保存原文件，检查编码、BOM、零宽字符、不可见 Unicode 和 parse 错误。无法 parse 时先产生字符级清理结果，不直接套 AST pass。

### 2. 家族识别

判断字符串数组/解密函数、预处理 IIFE、dispatcher、while-switch、自卫代码和库型 runtime。按 `references/decode-action-pipelines.md` 选择家族 pipeline；混合样本先用低风险 common pass。

### 3. 最小 pipeline

按需组合：

1. 字面量清理和常量折叠
2. 字符串数组与解密调用恢复
3. 对象/dispatcher 收敛
4. 控制流展开
5. 死代码和自卫代码清理
6. 可读性整理和确定性重命名

一个 visitor 只处理一个模式。高风险内联默认关闭。

### 4. 多轮执行

每轮固定执行 `transform -> generate -> reparse -> validate -> next pass`，并保留 `stepN` 中间文件。某轮失败只回退到上一轮，不覆盖最终输出。

### 5. 验证与收敛

1. 语法重新解析通过。
2. 对受信任的小型 fixture 做固定输入输出或 `--reference` canonical AST 比较；不在主进程执行不可信目标 bootstrap。
3. 使用 residue metrics 记录剩余字符串数组、dispatcher、while-switch 和动态 eval。
4. 将运行时依赖明确标为残留，不声称静态还原完成。

## 脚手架选择

- 所有任务统一从 `scripts/template-project/` 起步，使用 `src/plugins/`、`src/visitors/`、`--steps` 和自带 metrics 工具。不要维护第二份单文件 visitor 实现。
- 控制流细节：读取 `references/control-flow-patterns.md`。
- 静态变换到达边界：读取 `references/instrumentation-patterns.md`，生成插桩版而不是继续激进替换。

Bundled 模板永不把 `node:vm` 当安全边界。必须执行目标解密 bootstrap 时，只输出最小候选代码并转外部 OS/container sandbox；没有该隔离能力就停在插桩版。

## Failure Modes

| 触发条件 | 处理动作 | 兜底 |
|---|---|---|
| 源码缺失或 URL 下载失败 | 停止落地 | 只列所需输入 |
| Babel parse 失败 | 保存 step0 并清理编码/不可见字符 | 仍失败则输出字符级报告 |
| 家族不明确 | 只运行低风险 common pass | 不套专属 pipeline |
| 某轮语法或语义失败 | 回退上一中间文件并定位该 pass | 禁用对应高风险 visitor |
| 依赖真实运行时状态 | 停在阅读版或插桩版 | 返回 Trace Observe/Capture，或在入口和固定输出已知后进入 `trace` env-patch fallback |
| 用户真正要协议链 | 固定已还原的关键源码 | 退出 profile，返回 Trace core loop |

## 完成标准

报告命中家族、执行顺序、产出路径、语法/fixture 结果、仍有的残留结构和故意未执行的激进变换。

参考入口：

- `references/decode-action-pipelines.md`
- `references/control-flow-patterns.md`
- `references/instrumentation-patterns.md`
- `references/template-usage.md`
- `references/residue-metrics.md`
- `scripts/template-project/`
