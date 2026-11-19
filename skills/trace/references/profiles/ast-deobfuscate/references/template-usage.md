# Template Project Usage

profile 只维护 `scripts/template-project/` 这一份可执行 Babel pipeline，避免单文件脚手架和 visitor 实现漂移。

## 起步

将模板复制到目标项目的 `js_reverse_cache/ast/`，原始源码只读保存为 `input.js`。依赖安装在执行项目，不写回 skill 目录。

```bash
npm install
npm run deobfuscate -- -i input.js -o output.js --steps steps
npm run metrics -- output.js metrics.json
```

先查看 `metrics.json`、`steps/` 和最终 `output.js`，再决定是否增加家族 visitor。`steps/` 由每个 visitor pass 写出，且每步已经 strict reparse；metrics 需要显式运行上面的命令。不要因为 detector 命中某个家族就默认启用所有高风险 pass。

## 目录职责

```text
template-project/
├── src/main.js
├── src/lib/
├── src/plugins/
├── src/visitors/
├── src/tools/
└── tests/
```

- `src/main.js`：参数、家族路由、产物写入和 reference comparison。
- `src/lib/core.js`：parse、strict reparse、generate 和 visitor 执行。
- `src/plugins/`：家族 pipeline，只编排 visitor。
- `src/visitors/`：一个文件处理一个结构模式。
- `src/tools/`：残留指标和辅助检查。
- `tests/`：可信 fixture、负向语义探针和安全契约。

## Pass 规则

每轮固定执行：

1. 从上一轮生成的源码重新 parse。
2. 运行一个低风险 pass 或一个已经有 fixture 的专项 pass。
3. generate 到新的 `stepN` 文件。
4. 使用严格 parser 重新解析，不使用 `errorRecovery` 掩盖无效输出。
5. 对可信小 fixture 比较语义或运行 `--reference` canonical AST comparison。
6. 指标改善且验证通过后才进入下一轮。

任何 visitor 都必须保留副作用、参数求值次数、参数求值顺序和仍在使用的 binding。无法静态证明时保持原节点，不做“看起来更干净”的替换。

## Dispatcher

默认 dispatcher visitor 只内联字面量或 constant binding 参数；调用、更新、赋值、member getter、缺参和多余参数都保持原调用。目标专项如果需要更激进的内联，先新增能覆盖求值顺序、短路和异常行为的 fixture。

## While-switch

展开前必须确认顺序数组、索引 binding 和 case 映射都是静态的，并且顺序数组/索引没有 loop 外引用。任何外部引用都会让 visitor 保持原结构，避免删除仍被业务代码使用的声明。

## 动态 Bootstrap

模板不在 Node 主进程或 `node:vm` 中执行不可信 bootstrap。`node:vm` 不是安全边界。

确实必须求值解密 bootstrap 时：

1. 只提取最小 bootstrap 和固定字面量调用。
2. 保存待执行代码和输入摘要。
3. 转到无凭据、最小挂载、默认断网的外部 OS/container sandbox。
4. 没有该隔离能力时停在静态或插桩产物，不声称已完成动态解密。

## 验证

```bash
npm test
npm run deobfuscate -- -i input.js -o output.js --steps steps --reference reference.js
npm run metrics -- output.js metrics.json
```

`--reference` 只用于用户提供或人工确认的可信 canonical fixture。它不是在主进程执行目标源码，而是比较严格 parse 后的 canonical AST 结构。

完成报告应列出 detector、visitor 顺序、每轮产物、strict reparse、fixture/reference 结果、剩余混淆指标和所有故意保留的动态结构。
