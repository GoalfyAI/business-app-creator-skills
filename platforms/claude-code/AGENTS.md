# 场景包制作安装指南 — Claude Code（Agent 版）

本文供 Agent 直接执行。升级已安装的插件请改用 [UPDATE.md](UPDATE.md)。

执行本指南时必须遵守：

1. 只运行本文列出的命令；只写入 `~/.claude/settings.json`（合并写入，保留其他配置）和
   Claude Code 的插件目录
2. 所有安装与配置命令由你自己执行，**禁止**把 shell 命令丢给用户、或让用户自己开终端
3. 需要用户提供东西或采取行动时，输出对应的「需要用户操作」模板：作为正文输出，
   **禁止**放进代码块或引用块，一级标题与加粗必须保留
4. **禁止**回显密钥、在命令输出或 diff 中暴露密钥，也不得把密钥写入仓库、Skill、
   本文档、检查点或日志
5. 每一步都以检查命令开始：已完成的步骤跳过，任何一步重复执行都是安全的
6. 在插件已启用、Claude Code 已重启、`scene-creator` MCP 工具已加载、且一次只读请求
   成功返回之前，**禁止**宣告安装成功

## 第 0 步：判断当前状态

```bash
claude plugin list 2>/dev/null | grep -i scene-creator || echo "NOT_INSTALLED"
```

- 输出 `NOT_INSTALLED`：按本文继续安装
- 已列出插件：这是升级场景，改用 [UPDATE.md](UPDATE.md)

## 第 1 步：添加插件市场并安装

```bash
claude plugin marketplace add GoalfyAI/scene-creator-skills
claude plugin install scene-creator@scene-creator
```

市场已存在时不要重复添加。若提示市场已绑定到本地目录，按 [UPDATE.md](UPDATE.md) 的兜底
步骤重新绑定到公开仓库。

## 第 2 步：取得并配置 API 密钥

先检查是否已配置：

```bash
grep -q "SCENE_CREATOR_API_KEY" ~/.claude/settings.json 2>/dev/null && echo "KEY_PRESENT" || echo "KEY_MISSING"
```

输出 `KEY_PRESENT` 时跳到第 3 步。否则用用户当前对话使用的语言输出下面的模板
（用户不使用中文时翻译内容，保留标题与加粗结构）：

# 需要用户操作：提供 GoalfyMax 个人 API 密钥

**1. 打开 GoalfyMax 线上环境，进入 开发者工具 → API 密钥（`/developer/api-keys`）。**

**2. 创建一个个人 API 密钥，把完整密钥粘贴到本对话中。**

**3. 我会替你写入本地配置，你不需要自己编辑任何文件。**

拿到密钥后，合并写入 `~/.claude/settings.json` 的 `env.SCENE_CREATOR_API_KEY`，
保留文件中其他全部配置。写入后不要回显密钥内容。

## 第 3 步：重启

输出下面的模板（同样作为正文，翻译时保留结构）：

# 需要用户操作：重启 Claude Code

**执行 `/reload-plugins`，或彻底退出 Claude Code 后重新打开——插件与密钥配置在重启后才生效。**

## 第 4 步：在新会话中验证

依次确认，全部通过才算安装成功：

1. `scene-creator` 插件与 Skill 已加载
2. 你的工具列表里有 `scene-creator` 的 MCP 工具（如 `task_manager`、`list_assets`）
3. 执行一次只读请求（如列出可访问的场景包）能正常返回

任何一项不通过时，按下表处理，**禁止**在未通过的情况下宣告成功：

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 密钥缺失、已撤销，或新进程未继承密钥。只检查变量是否存在，不要输出其值 |
| `403 Forbidden` | 该账号无目标场景包权限，告知用户在 GoalfyMax 侧确认授权 |
| `503` | 依赖暂时不可用，等待恢复后重试，不要更换密钥 |
| 缺少核心工具 | 部署未提供预期的外部契约。停止并记录线上工具 Schema；不要用静态工具数量代替实时清单 |
| Skill 已加载但 MCP 未连接 | 重新安装插件；只复制 Skill 目录不会安装 MCP 配置 |

## 完成报告

向用户报告时说明：插件与 Skill 版本、MCP 连接状态、验证用的只读请求及其结果。
**禁止**报告密钥内容或其片段。
