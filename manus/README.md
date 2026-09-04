# 业务应用制作 — Manus 集成

> **注意：Manus 不支持把本文档丢给 Agent 自动安装。添加连接器和上传 Skill 必须由你在
> Manus 网页界面手工完成，请按下面的步骤逐步操作。**

Manus 是云端 Agent，有两部分要分别配置：**工具（MCP）** 在插件页添加为连接器，
**Skill** 以文件形式上传。

## 第 1 步：获取 API 密钥

登录 GoalfyMax，进入 [开发者工具 → API 密钥](https://goalfymax.qa.goalfyai.cn/developer/api-keys)创建
个人密钥。密钥以 `sk_` 开头，**完整内容只在创建时显示一次**，请妥善保存。

## 第 2 步：添加 MCP 连接器（工具）

左侧栏进入 **Plugins** → 右上角 **Create** → 在 Connector 区域二选一：

### 方式 A：通过 JSON 导入（推荐）

点击 **Import MCP via JSON**，粘贴下面的 JSON，把 `sk_YOUR_API_KEY_HERE` 替换成你的
密钥后保存。

```json
{
  "mcpServers": {
    "business-app-creator": {
      "url": "https://business-app-creator-mcp.qa.goalfyai.cn/mcp",
      "transport": "streamable_http",
      "headers": {
        "Authorization": "Bearer sk_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### 方式 B：自定义 MCP（逐项填写）

点击 **Custom MCP**，按下表填写：

| 字段 | 值 |
|---|---|
| **Server Name** | `SceneCreator` |
| **Transport Type** | `HTTP`（保持默认） |
| **Icon**（可选） | 留空，或粘贴 Logo 链接 |
| **Notes**（可选） | 留空，或写用途说明 |
| **Server URL** | `https://business-app-creator-mcp.qa.goalfyai.cn/mcp` |
| **Custom Headers** | 点击 "+ Add custom header" 添加 1 条 |

自定义请求头（鉴权，必填）：

- Key：`Authorization`
- Value：`Bearer sk_你的实际密钥`

填好后保存。

> Manus 的连接器配置保存在云端，密钥以明文形式存放于其中。请使用**专用密钥**，
> 不要复用于其他环境；不再使用时在 GoalfyMax 撤销该密钥。

## 第 3 步：上传 Skill

左侧栏 **Plugins** → 右上角 **Create** → Skill 区域 → **Upload Skill**。

Manus 要求上传 `.zip` 或 `.skill` 文件，且 `SKILL.md` 必须在压缩包根目录。

**下载预打包 ZIP**：直接下载本目录的 [`business-app-creator-skill.zip`](business-app-creator-skill.zip)
并上传。

**或手工打包**：

```bash
cd manus/skill && zip -r ../business-app-creator-skill.zip SKILL.md references/
```

## 第 4 步：验证

开一个新会话，确认：

1. Skill 已加载，Agent 能说明自己会制作场景包
2. `business-app-creator` 的 MCP 工具已就绪（如 `task_manager`、`list_assets`）
3. 执行一次只读请求，例如「列出我能访问的场景包」，能正常返回

## 更新

见 [UPDATE.md](UPDATE.md)。

## 故障排查

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 连接器里的密钥错误或已撤销，重新编辑连接器 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限 |
| `503` | MCP 依赖暂时不可用，等待恢复后重试 |
| Skill 已上传但工具不可用 | 连接器和 Skill 是两处配置，确认第 2 步已完成 |
| 更新后行为没变 | Skill 只在会话开始时加载，需要开新会话 |
