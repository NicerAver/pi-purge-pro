import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// 扩展不写任何状态文件；仍然隔离 agent dir，用来证明「跑完目录还是空的」
const AGENT_DIR = mkdtempSync(join(tmpdir(), "pi-purge-pro-test-"));
process.env.PI_CODING_AGENT_DIR = AGENT_DIR;

// 技能根用临时目录造，测试不依赖机器上真实存在的 skill 集合
const SKILLS_DIR = mkdtempSync(join(tmpdir(), "pi-purge-pro-skills-"));
const makeSkill = (name, description) => {
	mkdirSync(join(SKILLS_DIR, name), { recursive: true });
	writeFileSync(join(SKILLS_DIR, name, "SKILL.md"), `---\nname: ${name}\ndescription: >-\n  ${description}\n  second folded line\n---\n\n# ${name}\n`, "utf8");
};
makeSkill("trace", "unknown-family hostile web protocol recovery coordinator");
makeSkill("iv8-web-reverse", "explicit Python + iv8 browser-free replay");
makeSkill("extra-skill", "undeclared skill discovered from disk");
process.env.PI_PURGE_SKILLS = SKILLS_DIR;

// pi dist/core/system-prompt.js buildSystemPrompt() 的真实输出形态
const REAL_PI_PROMPT = `You are an expert coding assistant operating inside pi, a coding agent harness. You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
- read: Read file contents with line numbers
- bash: Run shell commands

In addition to the tools above, you may have access to other custom tools depending on the project.

Guidelines:
- Be concise in your responses

Pi documentation (read only when the user asks about pi itself, its SDK, extensions, themes, skills, or TUI):
- Main documentation: C:/pi/README.md
- Additional docs: C:/pi/docs
- Examples: C:/pi/examples (extensions, custom tools, SDK)
- When reading pi docs or examples, resolve docs/... under Additional docs and examples/... under Examples, not the current working directory
- When asked about: extensions (docs/extensions.md, examples/extensions/), themes (docs/themes.md)
- When working on pi topics, read the docs and examples
- Always read pi .md files completely and follow links to related docs (e.g., tui.md for TUI API details)

<project_context>

Project-specific instructions and guidelines:

<project_instructions path="C:/AGENTS.md">
# Rules
</project_instructions>

</project_context>

Current working directory: H:/WorkSpace`;

const events = new Map();
const commands = new Map();
const notes = [];
const statuses = [];

const pi = {
	on: (name, handler) => events.set(name, handler),
	registerCommand: (name, options) => commands.set(name, options),
};

const mod = await import(pathToFileURL(join(import.meta.dirname, "..", "extensions", "pi-purge-pro.ts")).href);
mod.default(pi);

const ctx = {
	ui: {
		setStatus: (key, text) => statuses.push(text),
		notify: (text, level) => notes.push([level ?? "info", text]),
	},
};
const cmd = commands.get("purge");
const before = events.get("before_agent_start");
const start = events.get("session_start");
const lastNote = () => notes.at(-1)?.[1] ?? "";
const inject = (prompt = REAL_PI_PROMPT, cwd = "H:\\WorkSpace") => before({ systemPrompt: prompt, systemPromptOptions: { cwd } }, ctx);
// 带真实用户提问的一轮：技能路由靠 event.prompt 判定
const injectUser = (prompt, systemPrompt = REAL_PI_PROMPT) =>
	before({ messageType: "user", prompt, systemPrompt, systemPromptOptions: { cwd: "H:\\WorkSpace" } }, ctx);

try {
	// 1. 内嵌人设：不需要任何外部文件就能开
	await start({ reason: "startup" }, ctx);
	assert.equal(await inject(), undefined, "默认关闭，不碰系统提示词");
	await cmd.handler("status", ctx);
	assert.match(lastNote(), /人设: 内嵌/, "默认人设来自内嵌常量");
	assert.match(lastNote(), /状态: 关闭/);
	assert.match(lastNote(), /仅本会话/);

	await cmd.handler("on", ctx);
	assert.equal(statuses.at(-1), "PURGE ON", "footer 显示 PURGE ON");
	const sp = (await inject()).systemPrompt;
	assert.ok(sp.length > 5000, `内嵌人设已注入（${sp.length} 字符）`);
	assert.ok(sp.endsWith("Current working directory: H:/WorkSpace"), "strict 保留工作目录");
	assert.ok(!sp.includes("You are an expert coding assistant"), "strict 丢掉宿主身份句");
	assert.ok(!sp.includes("Available tools:"), "strict 丢掉宿主结构");

	// 2. ★ 会话级独立：新会话必须归零
	await start({ reason: "new" }, ctx);
	assert.equal(statuses.at(-1), undefined, "新会话 footer 清空状态");
	assert.equal(await inject(), undefined, "新会话不继承上一会话的开启状态");

	// 3. ★ resume 同样归零：状态不落盘，退出即失
	await cmd.handler("on", ctx);
	await start({ reason: "resume" }, ctx);
	assert.equal(await inject(), undefined, "resume 也不继承");

	// 4. 三种模式
	await cmd.handler("on", ctx);

	await cmd.handler("mode replace", ctx);
	const replaced = (await inject()).systemPrompt;
	assert.ok(!replaced.includes("You are an expert coding assistant"), "replace 切除身份句");
	assert.ok(!replaced.includes("Pi documentation (read only"), "replace 切除文档段");
	for (const keep of ["Available tools:", "- Be concise in your responses", "<project_context>", "<project_instructions"]) {
		assert.ok(replaced.includes(keep), `replace 保留宿主结构: ${keep}`);
	}
	await cmd.handler("status", ctx);
	assert.match(lastNote(), /身份段 已切除 \/ pi 文档段 已切除/, "status 反映切除实况");

	await cmd.handler("mode append", ctx);
	const appended = (await inject()).systemPrompt;
	assert.ok(appended.includes("You are an expert coding assistant"), "append 不动宿主身份句");
	assert.ok(appended.includes("Pi documentation (read only"), "append 不动文档段");
	assert.ok(appended.includes("<project_context>"), "append 不动项目上下文");

	await cmd.handler("mode strict", ctx);
	const strict = (await inject()).systemPrompt;
	for (const gone of ["Available tools:", "Guidelines:", "<project_context>", "Pi documentation"]) {
		assert.ok(!strict.includes(gone), `strict 丢掉宿主段: ${gone}`);
	}
	assert.ok(strict.endsWith("Current working directory: H:/WorkSpace"), "strict 只留 cwd");

	// 5. 换源失败：报错带原因 + 回滚到内嵌
	await cmd.handler("source C:/definitely/not/here.md", ctx);
	assert.equal(notes.at(-1)[0], "error", "不存在的源报 error");
	assert.match(lastNote(), /文件不存在/, "错误信息带具体原因");
	const afterFail = (await inject()).systemPrompt;
	assert.ok(afterFail.length > 5000, "回滚后仍注入完整内嵌人设");

	// 6. 显式切回内嵌
	await cmd.handler("source embedded", ctx);
	assert.match(lastNote(), /人设: 内嵌/, "source embedded 切回内嵌");

	// 7. 自定义 SYSTEM.md（没有身份句/文档段）不能切坏
	const custom = "You are my own assistant.\n\nCurrent working directory: H:/WorkSpace";
	await cmd.handler("mode append", ctx);
	const customOut = (await inject(custom)).systemPrompt;
	assert.ok(customOut.includes("You are my own assistant."), "无身份句时原样保留");

	// 8. off
	await cmd.handler("off", ctx);
	assert.equal(await inject(), undefined, "关闭后不再注入");
	assert.equal(statuses.at(-1), undefined, "footer 清空");

	// 9. ★ 无盘副作用：全程没写状态文件
	assert.deepEqual(readdirSync(AGENT_DIR), [], "不写任何状态文件");

	// 10. ★ 逆向请求：purge on 时挂上 skill 路由
	await start({ reason: "new" }, ctx);
	await cmd.handler("on", ctx);
	await cmd.handler("skills status", ctx);
	assert.match(lastNote(), /逆向技能路由: 开启/, "技能路由默认开启");
	assert.match(lastNote(), /已发现: [1-9]\d* 个/, "扫到 SKILL_ROOT 下的 skill");

	const normalPrompt = "帮我把这个 React 组件改成两列布局";
	assert.ok(!(await injectUser(normalPrompt)).systemPrompt.includes("SKILL ARSENAL"), "非逆向请求不注入技能路由");

	const reOut = (await injectUser("帮我逆向这个站点的 sign 参数，做个采集器")).systemPrompt;
	assert.ok(reOut.includes("REVERSE-ENGINEERING SKILL ARSENAL"), "逆向请求注入技能路由");
	assert.match(reOut, /SKILL_ROOT = .+pi-purge-pro-skills-/, "路由块写明技能根目录");
	for (const skill of ["trace", "iv8-web-reverse"]) {
		assert.ok(reOut.includes(skill), `路由表含 ${skill}`);
	}
	assert.ok(reOut.includes("extra-skill"), "磁盘上多出来的 skill 也进路由表");
	assert.ok(reOut.includes("read SKILL_ROOT/<skill>/SKILL.md 全文"), "强制先读 SKILL.md");

	// 11. ★ 命中后本会话锁定：后续"继续"也带路由
	const followUp = (await injectUser("继续")).systemPrompt;
	assert.ok(followUp.includes("SKILL ARSENAL"), "锁定后后续轮次仍注入");

	// 12. ★ 新会话归零
	await start({ reason: "new" }, ctx);
	await cmd.handler("on", ctx);
	assert.ok(!(await injectUser("继续")).systemPrompt.includes("SKILL ARSENAL"), "新会话不继承 RE 锁定");

	// 13. 关掉技能路由 / 换根失败回滚
	await cmd.handler("skills off", ctx);
	assert.ok(!(await injectUser("逆向这个 APK")).systemPrompt.includes("SKILL ARSENAL"), "skills off 后不注入");
	await cmd.handler("skills on", ctx);
	await cmd.handler("skills C:/definitely/not/a/skill/root", ctx);
	assert.equal(notes.at(-1)[0], "error", "不存在的根报 error");
	assert.match(lastNote(), /未在 .* 下找到任何 SKILL.md/, "错误带具体原因");
	await cmd.handler("skills status", ctx);
	assert.match(lastNote(), /已发现: [1-9]\d* 个/, "失败后回滚到原根目录");

	// 14. list 输出完整 description
	await cmd.handler("skills list", ctx);
	assert.match(lastNote(), /trace/, "list 列出 skill 名");
	assert.match(lastNote(), /second folded line/, "折叠式 description 被拼成一行");

	await cmd.handler("off", ctx);

	// 15. 包内自带的军火库能被直接切过去并扫到整套 skill（没打包就跳过）
	const REAL_SKILLS = join(import.meta.dirname, "..", "skills");
	if (existsSync(REAL_SKILLS)) {
		await cmd.handler("on", ctx);
		await cmd.handler(`skills ${REAL_SKILLS}`, ctx);
		assert.equal(notes.at(-1)[0], "info", "切到真实技能根成功");
		const realOut = (await injectUser("帮我抓包还原这个站的加密参数")).systemPrompt;
		for (const skill of ["trace", "iv8-web-reverse", "akamai-protocol-reverse", "captcha-reverse", "wechat-miniapp-reverse"]) {
			assert.ok(realOut.includes(skill), `真实军火库含 ${skill}`);
		}
		await cmd.handler("off", ctx);
	}

	assert.deepEqual(readdirSync(AGENT_DIR), [], "加完技能路由仍然不写状态文件");

	console.log("OK — 15 组断言全部通过");
	console.log("内嵌人设注入后:", sp.length, "字符");
} finally {
	rmSync(AGENT_DIR, { recursive: true, force: true });
	rmSync(SKILLS_DIR, { recursive: true, force: true });
}
