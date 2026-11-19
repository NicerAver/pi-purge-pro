# Decode Action Template Project

这是目录化模板，适合已经确认要持续迭代某个混淆目标的场景。

## 目录

```text
template-project/
├── input.js
├── package.json
└── src/
    ├── main.js
    ├── lib/
    │   └── core.js
    ├── plugins/
    │   ├── awsc.js
    │   ├── common.js
    │   ├── obfuscator.js
    │   ├── sojson.js
    │   └── sojsonv7.js
    └── visitors/
        ├── awsc-conditional-to-if.js
        ├── awsc-logical-to-if.js
        ├── awsc-normalize-blocks.js
        ├── awsc-void.js
        ├── constant-if.js
        ├── delete-extra.js
        ├── fold-binary.js
        ├── fold-boolean.js
        ├── inline-dispatcher.js
        ├── merge-strings.js
        ├── normalize-member.js
        ├── remove-empty.js
        ├── split-sequence.js
        └── while-switch-unpack.js
```

## 起手

1. 把目标脚本放到 `input.js`
2. 安装依赖：

```bash
npm install
```

3. 运行并保存每个 pass：

```bash
npm run deobfuscate -- -i input.js -o output.js --steps steps
npm run metrics -- output.js metrics.json
```

如果你要自定义输入输出，也可以继续直接用：

```bash
node src/main.js -i input.js -o output.js
```

## 何时用这个模板

1. 你需要对同一个目标持续维护多个 visitor
2. 你要对某个样本持续补 visitor
3. 你想把家族策略和 visitor 分开维护

## 工作方式

1. `src/main.js` 负责插件路由
2. `src/plugins/*.js` 负责家族级 pipeline
3. `src/visitors/*.js` 负责单一 AST 变换
4. 每个 visitor pass 自动 `generate -> strict reparse`，需要时用 `--steps` 保留中间产物

## 当前内置能力

1. `sojson` / `sojsonv7`：只做保守 common 清理并保留 runtime decrypt 调用供插桩
2. `obfuscator`：带保守 dispatcher 内联和 while-switch 展开；拆散对象赋值不默认前移
3. `awsc`：带结构整形 visitor
4. `common`：带低风险通用清理 pass；默认不删除 binding，避免 direct eval/外部 API 语义漂移

## 还需要按样本继续补的地方

1. `sojson` 的 bootstrap 识别目前偏保守，只覆盖常见“前几句初始化 + 解密函数”结构
2. `inline-dispatcher` 目前只安全内联这几类常见代理：二元表达式、逻辑表达式、简单函数调用、简单成员访问、简单条件表达式
3. `while-switch` 只接受初始 cursor 为 0、未重赋值的静态数组顺序表、`order[idx++]`、无 default/动态 case、明确 `continue`/return 终点和 case 内 block
4. 复杂 VM/VMP、动态状态机仍然应转插桩

## 回归样例

新增或修改 visitor 前，先看 `test-fixtures/README.md`。模板项目建议用小 fixture 回归单个结构，不要直接用大型真实 bundle 当模板回归样本。
