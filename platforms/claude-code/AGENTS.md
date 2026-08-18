# 场景包制作安装与更新指南 — Claude Code

严格按本指南执行。它会安装一个同时包含外部 MCP 配置和 `scene-creator` Skill 的本地插件。

## 安全规则

1. 安装包目录和个人 API 密钥由用户提供；密钥只用于本次本地插件配置。
2. 不得编造、回显或记录密钥，也不得把密钥复制到仓库、Skill、命令、检查点或聊天回复中。
3. 用户提供完整密钥后，由 Agent 更新本地 `~/.claude/settings.json`；不得要求用户自行编辑配置文件。
4. 添加环境变量时，保留 Claude Code 的全部已有配置。
5. 验证安装期间，不要创建、更新、发布或运行任何 Goalfy 资产。
6. 只有在重启后的会话中确认插件、Skill、当前 MCP 工具清单、`bubble` 操作和一次只读资产请求
   全部正常后，才能宣布安装成功。

## 第 0 步：检查当前状态

执行以下只读检查：

```bash
claude --version
claude plugin list
claude mcp get scene-creator
test -f "$HOME/.claude/settings.json" && grep -q 'SCENE_CREATOR_API_KEY' "$HOME/.claude/settings.json"
```

不要输出匹配到的 JSON 行。如果插件、MCP 和密钥标记都已存在，请按 `UPDATE.md` 更新；否则
继续安装。

## 第 1 步：校验安装包

安装包解压目录必须由用户提供。确认其中包含：

```bash
export PACKAGE_ROOT="/请替换为/scene-creator-claude-code/绝对路径"
test -f "$PACKAGE_ROOT/.claude-plugin/marketplace.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/.claude-plugin/plugin.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/.mcp.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/skills/scene-creator/SKILL.md"
```

如果不知道 `PACKAGE_ROOT`，询问用户解压后的绝对路径。不要搜索整个用户主目录。运行检查前，
必须替换示例路径。

## 第 2 步：安装本地插件

```bash
claude plugin marketplace add "$PACKAGE_ROOT"
claude plugin install scene-creator@scene-creator
```

如果插件市场已配置，不要重复创建。请按 `UPDATE.md` 更新已有插件。

## 第 3 步：获取密钥并由 Agent 配置

# 需要用户操作：提供 GoalfyMax 个人 API 密钥

**请在 GoalfyMax 打开账号菜单 → 开发者工具 → API 密钥
（`/developer/api-keys`），选择新建 API 密钥，输入 1～100 个字符的名称，并保存
只显示一次的 `sk_...` 密钥。如果没有该菜单，请停止并联系管理员开通开发者权限。不要使用他人的
密钥。**

**请把完整个人 API 密钥提供给我。我会负责配置，用户不需要自行编辑
`~/.claude/settings.json`。**

收到密钥后，由 Agent 保留 `~/.claude/settings.json` 的其他全部配置，只新增或替换
`env.SCENE_CREATOR_API_KEY`。配置过程不得在执行说明、命令回显、差异、检查点或最终回复中展示
密钥，也不得显示该配置文件中的其他值。

配置完成后，只校验 JSON 结构和密钥是否存在，不输出密钥值：

```bash
python3 -c 'import json, pathlib; p=pathlib.Path.home()/".claude/settings.json"; d=json.loads(p.read_text()); assert isinstance(d.get("env"), dict) and d["env"].get("SCENE_CREATOR_API_KEY")'
```

不要显示配置文件内容。

不要要求或配置 `user_id`、`X-User-ID` 或 `X-Project-ID` 作为鉴权参数。插件会发送
`Authorization: Bearer <key>`，外部 MCP 会根据密钥解析用户身份。

## 第 4 步：重启

# 需要用户操作：重启 Claude Code

**请彻底退出 Claude Code、其桌面端或 IDE 宿主以及所有现有会话，再打开一个新会话。只有重启后，
插件 MCP 才能读取新密钥。**

**重启后请回到本任务，并让我验证连接。**

## 第 5 步：在新会话中验证

自行验证以下全部项目：

1. `scene-creator` 已安装，且可以选择对应 Skill。
2. `/mcp` 显示 `scene-creator` 已连接。
3. 线上 `tools/list` 包含安装文档要求的核心工具，且没有使用 Skill 中的静态数量替代实时清单。
4. 线上 `workflow_tpe_manage` Schema 包含 `bubble`。
5. 使用只读查询调用 `list_assets` 成功。

不要为了测试安装而打开场景包制作工单。验证失败时，只报告未通过的具体检查项，不得暴露
密钥或完整资产数据。

## 完成报告

只报告以下内容：

- 平台和插件版本；
- MCP 已连接或未连接；
- Skill 已加载或未加载；
- 工具数量以及是否存在 `bubble`；
- 只读请求通过或失败；
- 如仍需用户操作，说明具体事项。
