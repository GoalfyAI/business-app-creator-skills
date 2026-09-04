# 业务应用制作 — 通用集成指南

适用于 Claude Code、Codex、Manus 之外的 AI 编码工具，或需要手工集成的场景。

使用上述平台请改用对应目录下的 README。

---

## 集成步骤

### 第 1 步：获取 API 密钥

登录 GoalfyMax QA 环境，进入 [开发者工具 → API 密钥](https://goalfymax.qa.goalfyai.cn/developer/api-keys)创建
个人密钥。密钥以 `sk_` 开头，**完整内容只在创建时显示一次**，请妥善保存。

### 第 2 步：配置 MCP

把本目录的 [`.mcp.json`](.mcp.json) 加入你的客户端 MCP 配置，或按其内容手工填写：

```json
{
  "mcpServers": {
    "business-app-creator": {
      "type": "streamable-http",
      "url": "https://business-app-creator-mcp.qa.goalfyai.cn/mcp",
      "headers": {
        "Authorization": "Bearer ${BUSINESS_APP_CREATOR_API_KEY}"
      }
    }
  }
}
```

把密钥放进环境变量 `BUSINESS_APP_CREATOR_API_KEY`。客户端不支持环境变量占位符时，直接把
`${BUSINESS_APP_CREATOR_API_KEY}` 替换为密钥本身，但**不要**把替换后的文件提交到任何仓库。

不要为鉴权配置 `user_id`、`X-User-ID` 或 `X-Project-ID`——MCP 会根据个人 API 密钥解析
用户身份。

### 第 3 步：加载 Skill

把本目录的 [`SKILL.md`](SKILL.md) 与 [`references/`](references/) 一并提供给你的 Agent。

- 客户端支持 Skill 机制：按其规范放入 Skill 目录
- 不支持：把 `SKILL.md` 全文作为系统提示或长期上下文提供，Agent 需要引用时再读
  `references/` 下的对应文件

`SKILL.md` 与其他平台完全一致，逐字节相同。

### 第 4 步：验证

重启客户端后确认：

1. `business-app-creator` 的 MCP 工具已加载（如 `task_manager`、`list_assets`）
2. 执行一次只读请求，例如「列出我能访问的场景包」，能正常返回

## 更新

见 [UPDATE.md](UPDATE.md)。

## 故障排查

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 密钥缺失、已撤销，或进程未继承环境变量 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限 |
| `503` | MCP 依赖暂时不可用，等待恢复后重试，不要更换密钥 |
| 工具未加载 | 确认客户端支持 Streamable HTTP MCP，并已重启 |
| 缺少 `task_manager` 等核心工具 | 部署尚未提供预期的外部契约。记录线上工具 Schema；不要用静态工具数量代替实时清单 |
