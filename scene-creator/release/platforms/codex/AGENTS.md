# 场景包制作安装与更新指南 — Codex

严格按本指南执行。它会安装一个同时包含外部 MCP 配置和 `scene-creator` Skill 的本地插件。

## 安全规则

1. 安装包目录和个人 API 密钥只能由用户本人提供。
2. 不得编造、回显或记录密钥，也不得把密钥复制到仓库、Skill、命令、检查点或聊天回复中。
3. 必须由用户本人将密钥写入本地 `~/.codex/.env`；不要要求用户在聊天中粘贴明文密钥。
4. 验证安装期间，不要创建、更新、发布或运行任何 Goalfy 资产。
5. 只有在重启后的会话中确认插件、Skill、当前 MCP 工具清单、`bubble` 操作和一次只读资产请求
   全部正常后，才能宣布安装成功。

## 第 0 步：检查当前状态

执行以下只读检查：

```bash
codex --version
codex plugin marketplace list
codex plugin list
codex mcp get scene-creator
test -f "$HOME/.codex/.env" && grep -q '^SCENE_CREATOR_API_KEY=' "$HOME/.codex/.env"
```

不要输出匹配到的环境变量行。如果插件、MCP 和密钥标记都已存在，请按 `UPDATE.md` 更新；否则
继续安装。

## 第 1 步：校验安装包

安装包解压目录必须由用户提供。确认其中包含：

```bash
export PACKAGE_ROOT="/请替换为/scene-creator-codex/绝对路径"
test -f "$PACKAGE_ROOT/.agents/plugins/marketplace.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/.codex-plugin/plugin.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/.mcp.json"
test -f "$PACKAGE_ROOT/plugins/scene-creator/skills/scene-creator/SKILL.md"
```

如果不知道 `PACKAGE_ROOT`，询问用户解压后的绝对路径。不要搜索整个用户主目录。运行检查前，
必须替换示例路径。

## 第 2 步：安装本地插件

```bash
codex plugin marketplace add "$PACKAGE_ROOT"
codex plugin add scene-creator@scene-creator
```

如果插件市场已配置，不要重复创建。请按 `UPDATE.md` 卸载并重新安装已有插件。

## 第 3 步：请用户保存密钥

# 需要用户操作：配置 GoalfyMax 个人 API 密钥

**请在 GoalfyMax QA 打开账号菜单 → 开发者工具 → API 密钥
（`/developer/api-keys`），选择新建 API 密钥，输入 1～100 个字符的名称，并保存
只显示一次的 `sk_...` 密钥。如果没有该菜单，请停止并联系管理员开通开发者权限。不要使用他人的
密钥。**

**请将完整的 QA 个人 API 密钥以 `SCENE_CREATOR_API_KEY=<密钥>` 的形式写入
`~/.codex/.env`，再执行 `chmod 600 ~/.codex/.env`。不要把密钥发给我。**

**文件准备好后，只需告诉我已经完成，不要附带密钥。**

收到确认后，只检查密钥是否存在以及文件权限：

```bash
grep -q '^SCENE_CREATOR_API_KEY=.' "$HOME/.codex/.env"
stat -f '%Lp' "$HOME/.codex/.env" 2>/dev/null || stat -c '%a' "$HOME/.codex/.env"
```

不要显示文件内容。

不要要求或配置 `user_id`、`X-User-ID` 或 `X-Project-ID` 作为鉴权参数。插件会发送
`Authorization: Bearer <key>`，外部 MCP 会根据密钥解析用户身份。

## 第 4 步：重启

# 需要用户操作：重启 Codex

**请彻底退出 Codex CLI、Codex App 及所有 IDE 扩展进程，再打开一个新会话。只有重启后，插件
MCP 才能读取新密钥。**

**重启后请回到本任务，并让我验证连接。**

## 第 5 步：在新会话中验证

自行验证以下全部项目：

1. `scene-creator` 已安装，且可以选择对应 Skill。
2. `scene-creator` 已连接。
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
