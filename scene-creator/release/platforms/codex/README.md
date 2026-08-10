# 场景包制作 — Codex

本安装包会同时安装经过审计的 `scene-creator` MCP 和同名 Skill，当前连接美国 QA 环境：

`https://workflow-mcp.qa.goalfyai.com/mcp`

## 安装前准备

1. 登录 GoalfyMax QA，打开账号菜单 → **开发者工具** → **API 密钥**
   （`/developer/api-keys`）。选择 **新建 API 密钥**，输入 1～100 个字符的名称。
   完整密钥只显示一次，并会自动复制；关闭弹窗前务必妥善保存。如果菜单中没有该入口，说明
   当前账号尚未获得开发者权限，请联系管理员开通，不要借用他人的密钥。
2. 将本 ZIP 解压到一个稳定的本地目录。
3. 使用支持插件和 Streamable HTTP MCP 的新版 Codex。

GoalfyMax 个人 API 密钥以 `sk_` 开头，其完整内容就是 Bearer 凭证。GoalfyMax 当前最多允许
10 个有效密钥。前端支持命名、重命名和撤销密钥，不要求设置过期时间，也不会再次显示明文。
严禁将密钥粘贴到仓库、Skill、`AGENTS.md`、命令历史或聊天记录中。

## 安装

进入解压后包含 `.agents/plugins/marketplace.json` 的目录并执行：

```bash
codex plugin marketplace add "$PWD"
codex plugin add scene-creator@scene-creator
```

将完整的个人 API 密钥写入 `~/.codex/.env`。变量名不要加引号。
`SCENE_CREATOR_API_KEY` 只是本地变量名，插件会将它的值作为
`Authorization: Bearer <GoalfyMax 个人 API 密钥>` 发送：

```text
SCENE_CREATOR_API_KEY=<请填入完整的个人 API 密钥>
```

确保该文件只有本人可读，然后彻底退出并重新打开 Codex：

```bash
chmod 600 "$HOME/.codex/.env"
```

Codex CLI 用户也可以在启动 Codex 的 Shell 中导出同名变量。桌面端和 IDE 用户应优先使用
`~/.codex/.env`，因为这些进程可能不会继承终端环境变量。

不要为鉴权配置 `user_id`、`X-User-ID` 或 `X-Project-ID`。外部 MCP 会根据个人 API 密钥
解析用户身份；只有线上工具 Schema 明确要求时，Workflow 工具才携带项目或工单标识。

## 验证

在新的 Codex 会话中完成以下检查：

1. 确认 `scene-creator` 插件和 Skill 已加载。
2. 确认 MCP 服务 `scene-creator` 已连接。
3. 确认 `tools/list` 恰好暴露 12 个外部工具。
4. 确认 `workflow_tpe_manage` 包含 `bubble` 操作。
5. 执行一次只读的 `list_assets` 请求。不要为了测试安装而创建或修改资产。

五项全部通过后才能宣布安装完成。知识库主题要求先打开 Workflow 制作工单，应在首次真实
制作任务中验证。

如需 Agent 协助安装，请把解压后的安装包路径和 `AGENTS.md` 的内容交给 Codex。更新插件或轮换
密钥时请阅读 `UPDATE.md`。

## 故障排查

- `401 Unauthorized`：密钥缺失、已撤销，或新 Codex 进程没有继承密钥。只检查变量是否存在，
  不要输出变量值。
- `503`：MCP 鉴权或注册中心依赖暂时不可用。等待服务恢复后重试，不要因此更换密钥。
- 工具数不是 12，或没有 `bubble`：QA 部署尚未提供预期的外部契约。停止测试并记录线上
  工具 Schema。
- Skill 已加载但 MCP 未连接：重新安装插件。只复制 Skill 目录不会安装 MCP 配置。
