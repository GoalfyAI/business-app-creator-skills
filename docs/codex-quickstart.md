# Codex 快速上手

从零把场景包制作能力接进 Codex，约 5 分钟。

平台专属的完整说明见 [`codex/README.md`](../codex/README.md)，
Agent 可直接执行的安装流程见 [`codex/AGENTS.md`](../codex/AGENTS.md)。

> **想省事的话**：把 [codex/AGENTS.md](https://raw.githubusercontent.com/GoalfyAI/scene-creator-skills/main/codex/AGENTS.md) 直接发给你的 Agent，
> 它会自己完成下面全部步骤并验证结果，你只需要在它要密钥时提供一次。

## 第 1 步 — 获取 API 密钥

登录 GoalfyMax 线上环境，进入 [开发者工具 → API 密钥](https://goalfymax.goalfyai.cn/developer/api-keys)。
点击 **新建 API 密钥**，输入 1～100 个字符的名称。

密钥以 `sk_` 开头，**完整内容只显示一次**，创建后立即保存。

菜单里没有该入口说明账号尚未获得开发者权限，联系管理员开通，不要借用他人密钥。

## 第 2 步 — 安装插件

```bash
codex plugin marketplace add GoalfyAI/scene-creator-skills
codex plugin add scene-creator@scene-creator
```

## 第 3 步 — 配置密钥

把完整密钥交给当前 Agent，让它写入 `~/.codex/.env`：

```bash
SCENE_CREATOR_API_KEY=<你的个人 API 密钥>
```

Agent 会保留其他环境变量，并把文件权限设为 `600`，你不需要自己编辑文件。

## 第 4 步 — 重启

彻底退出 Codex 后重新打开——Codex 没有会话内重载命令。

## 第 5 步 — 验证

新会话里让 Agent 做一次只读请求：

> 列出我能访问的场景包

能正常返回即安装成功。

## 开始使用

### 从零做一个场景包

> 我们每周要给 20 家门店做朋友圈广告投放复盘，把这个流程做成场景包。

Agent 会先访谈业务目标和验收标准、摸清现有能力，再决定用普通任务点还是 Workflow，
逐层制作并验证。**它会在动手前先给你方案**，你确认后才开始。

### 诊断已有场景包

> 这个场景包执行时总绕弯，你看下哪里配置有问题。

Agent 会建一个只读工单，逐层检查提示词、工具契约、编排配置和执行日志。
确认要改时再新建写工单进入修复——诊断和修改在审计上是分开的。

### 基于执行日志优化

> 参考项目 xxx 的执行日志，把这个场景包优化一版。

## 更新

```bash
codex plugin marketplace upgrade scene-creator
codex plugin remove scene-creator@scene-creator
codex plugin add scene-creator@scene-creator
```

被提示 Skill 版本过期时，按 [`codex/UPDATE.md`](../codex/UPDATE.md) 执行。

## 常见问题

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 密钥缺失、已撤销，或新进程没继承密钥 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限 |
| 工具没加载 | 确认已重启；只装 Skill 不装插件不会带上 MCP 配置 |
| 升级后版本标记没变 | 插件市场可能绑在本地目录，按 UPDATE.md 重新绑定 |

更多见 [FAQ](../FAQ.md)。
