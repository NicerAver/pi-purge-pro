# pi-purge-pro

[English](README.md) | 中文

> **本项目 fork 自 [@ZiChuanLan](https://github.com/ZiChuanLan) 的 [pi-purge](https://github.com/ZiChuanLan/pi-purge)，在其基础上改写而来。** 原版的破限开关、三种模式、会话级状态全部保留，1.0.0 起由 [@NicerAver](https://github.com/NicerAver) 加上逆向技能路由和随包分发的 skill 正文，并改名为 `pi-purge-pro`。原作者的 MIT 许可与署名完整保留，见 [LICENSE](LICENSE)。

[pi](https://github.com/earendil-works/pi-coding-agent) 的系统提示词实验扩展：`/purge` 用来切换一轮会话到底带哪套系统提示词 —— pi 自带的、精简过的，或者只发一份人设提示词。

它的用途是提示词工程：同一句请求在「宿主提示词完整 / 精简 / 缺失」三种条件下的行为差异；自己写的指令做回归测试；以及指令遵循、提示词注入鲁棒性这类受控实验。

关掉时什么都不变：不改提示词、不读盘，行为与没装这个扩展完全一致。

## 安装

```bash
pi install npm:pi-purge-pro
```

然后在会话里：

```text
/purge
```

就这一步。包内自带默认人设，不需要准备任何提示词文件。

想换成自己的提示词：

```text
/purge source C:/prompts/my-instructions.md
/purge mode replace
/purge on
```

`/purge source embedded` 切回内置人设。

## 命令

| 命令 | 作用 |
| --- | --- |
| `/purge` | 切换本会话开 / 关 |
| `/purge on` / `off` | 显式开关 |
| `/purge status` | 当前模式、提示词来源、已加载字符数，以及上一轮实际改了什么 |
| `/purge mode append\|replace\|strict` | 切换组合方式（默认 `strict`） |
| `/purge source <路径\|embedded>` | 换提示词文件，或回到内置人设；切换失败会自动回滚 |
| `/purge reload` | 改完外部文件后重新读取 |
| `/purge skills` | 逆向技能路由的状态：开关、根目录、扫到的 skill 数、RE 是否已锁定 |
| `/purge skills on\|off` | 显式开关技能路由（默认跟 `/purge` 一起开） |
| `/purge skills <路径>` | 换技能根目录，失败自动回滚；默认用包内自带的 `skills/`，可用 `PI_PURGE_SKILLS` 或直接给路径覆盖 |
| `/purge skills list` | 列出扫到的 skill 和它们的 frontmatter description |
| `/purge skills reload` | 目录里加了新 skill 后重新扫 |

## 模式

| 模式 | 实际发给模型的系统提示词 | 适用场景 |
| --- | --- | --- |
| `append` | 你的提示词 + pi 原提示词（一字不改） | 对照组：基线行为，加一层自己的指令 |
| `replace` | 你的提示词 + 去掉「助手身份句」和「内置文档段」的 pi 提示词，工具列表 / Guidelines / 项目上下文保留 | 想测量宿主框架措辞的影响，又不想丢工具上下文 |
| `strict` | 你的提示词 + 仅 `Current working directory: …` | 想把人设/指令当成唯一变量隔离出来。这是默认模式 |

`replace` 依赖固定文案定位那两段。pi 升级改措辞时它会原样保留提示词（退化成 `append`），而不是切错位置 —— `/purge status` 会显示 `身份段 未匹配`。`strict` 不做任何匹配，跨 pi 版本行为一致。

工具 schema 走 API 的 `tools` 参数，不依赖系统提示词，所以三种模式下工具都正常可用，包括 `strict`。

## 逆向技能路由

`/purge` 开着的时候，如果这一轮的提问判定为逆向任务（`逆向`/`脱壳`/`抓包`/`协议还原`/`验证码`/`小程序`/`apk`/`iv8`/`collector` 等触发词），扩展会把一份**技能路由块**追加到系统提示词的末尾：

- 写明 `SKILL_ROOT` 和强制顺序：定族 → 读 `SKILL_ROOT/<skill>/SKILL.md` 全文 → 按里面的阶段门执行 → 按需读 `references/`、跑 `scripts/` → 交付产物加验证证据。
- 技能根默认是包内 `skills/`（跟着扩展一起分发，装到哪都在），`PI_PURGE_SKILLS` 或 `/purge skills <路径>` 可指向别处。`/purge skills status` 显示当前生效的是哪一个。
- 一条人工写的路由表：`trace`（未知族/多层/解混淆/补环境的协调者）、`iv8-web-reverse`、`nv8-node-runtime`、`akamai-protocol-reverse`、`captcha-reverse`、`captcha-vision`、`wechat-miniapp-reverse`、`reverse-engineer-anything`、`skill-creator`。
- 磁盘上多出来的 skill 目录自动追加进路由表，不用改代码。
- 命中后本会话**锁定**：后续「继续」「接着做」这类不带触发词的轮次照样带路由；前提是请求还跟逆向相关，块里也明说无关请求就忽略本节。

为什么需要它：`strict` 模式会把 pi 自带提示词整段丢掉，其中就包括 pi 的 skills 列表。所以技能路由不能靠宿主提供，只能由本扩展自己注入。

关掉时零成本：不命中逆向、或 `/purge skills off`、或 `/purge off`，都不会往提示词里加任何东西，也不会读盘扫目录。

## 会话范围与默认值

- 作用范围是**会话**。每次 `session_start`（启动 / 新建 / `resume` / 重载）都从**关闭**开始；退出 pi 一定回到原始提示词。
- **不写任何文件**：没有状态文件、没有缓存、没有标记。两个 pi 进程互不影响。
- 默认提示词是打包在 `extensions/pi-purge-pro.ts` 里的内置人设；`/purge source <路径>` 换成自己的文件，`/purge source embedded` 切回来。
- 默认模式 `strict`。
- 技能路由默认开启，只扫根目录下的 `*/SKILL.md` frontmatter，不读正文、不执行脚本、不写任何文件。
- skill 正文随包放在 `skills/` 下，是全量副本；换一份用 `/purge skills <路径>`，不需要改包。

## 与上游 pi-purge 的差异

| 项 | 上游 `pi-purge` | 本仓库 `pi-purge-pro` |
| --- | --- | --- |
| 包名 | `pi-purge` | `pi-purge-pro` |
| 扩展文件 | `extensions/pi-purge.ts` | `extensions/pi-purge-pro.ts` |
| 版本 | 0.2.1 | 1.0.0 |
| 逆向技能路由 | 无 | 命中逆向请求时注入技能根、路由表与强制流程 |
| skill 正文 | 无 | `skills/` 随包分发，9 套，装到哪都在 |
| 人设、三种模式、`/purge` 命令 | — | 与上游一致 |

上游是纯提示词实验工具；本仓库在上游基础上加了「逆向任务自动挂技能」这一层。只想做单变量对照实验的，用上游即可，行为完全一样。

## 1.0.0：改名与内置技能

`pi-purge` 改名为 **`pi-purge-pro`**，版本跳到 **1.0.0**，因为功能上多了一整套逆向技能路由和随包分发的 skill 正文。

- 命令还是 `/purge`，参数不变；只有包名、版本、扩展文件名（`extensions/pi-purge-pro.ts`）和 footer 状态键（`pi-purge-pro`）变了。
- 用 git 源装的不用动：`pi list` 按目录解析，`git:github.com/ZiChuanLan/pi-purge@…` 这条记录照样指向同一份 checkout。从 npm 装的要重新 `pi install npm:pi-purge-pro`，旧包名不再发布。

## 从 0.1.x 升级

0.2 不再读写 `pi-purge.json`，也不再自动探测提示词文件 —— 人设内置，模式默认 `strict`。

- 删掉 `<agent dir>/pi-purge.json`，它已经不被读取。
- 开启是会话级的：重启或 `/resume` 之后需要重新 `/purge`。
- 需要时 `append` / `replace` 的行为与之前一致。

## 做实验时的注意点

- `strict` 会一并丢掉 `AGENTS.md` / 项目上下文、skills 列表、其他扩展注入的提示词。这正是它能做单变量隔离的原因，也意味着 `strict` 下的结论不能直接和普通会话对比。
- `append` 侵入最小、信号也最弱：宿主提示词后段权重仍然很大，差异可能不明显。
- `replace` 仍会残留宿主文本，而且其他扩展可能在本扩展之后追加自己的提示词段。实践上只有 `strict` 能让人设不和别的框架措辞竞争。
- 扩展加载顺序会影响 `before_agent_start` 看到的内容。要留结果的话，建议把 `/purge status` 的输出一起记录。

## 开发

```bash
npm test   # 15 组断言，跑在临时 agent 目录里，并断言全程没有写任何文件
```

实现上只注册一个 `before_agent_start` 钩子、一个 `session_start` 钩子和一个 `/purge` 命令，无其他钩子、无后台任务、无文件写入。技能扫描只在开启时做一次并按根目录缓存，`/purge skills reload` 手动刷新。

## 许可

MIT
