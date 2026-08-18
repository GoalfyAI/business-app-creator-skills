# Manus 快速上手

Manus 是云端 Agent，配置分两部分：**MCP 连接器**（工具）和 **Skill**（上传文件），
都需要你在网页界面手工完成。

> **Manus 不支持把安装文档丢给 Agent 自动执行**，请按步骤自己操作。

完整说明见 [`manus/README.md`](../manus/README.md)。

## 第 1 步 — 获取 API 密钥

登录 GoalfyMax 线上环境，进入 [开发者工具 → API 密钥](https://goalfymax.goalfyai.cn/developer/api-keys)创建
个人密钥。密钥以 `sk_` 开头，**完整内容只显示一次**。

## 第 2 步 — 添加 MCP 连接器

左侧栏 **Plugins** → 右上角 **Create** → Connector 区域 → **Import MCP via JSON**，
粘贴下面的内容并把 `sk_YOUR_API_KEY_HERE` 换成你的密钥：

```json
{
  "mcpServers": {
    "scene-creator": {
      "url": "https://workflow-mcp.goalfyai.cn/mcp",
      "transport": "streamable_http",
      "headers": {
        "Authorization": "Bearer sk_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

> 连接器配置保存在 Manus 云端，密钥以明文存放。请使用**专用密钥**，不要复用于其他环境；
> 不再使用时在 GoalfyMax 撤销。

## 第 3 步 — 上传 Skill

左侧栏 **Plugins** → 右上角 **Create** → Skill 区域 → **Upload Skill**。

下载 [`manus/scene-creator-skill.zip`](../manus/scene-creator-skill.zip) 直接上传。
Manus 要求 `SKILL.md` 位于压缩包根目录，这个包已经符合要求。

## 第 4 步 — 验证

开一个新对话，让 Agent 做一次只读请求：

> 列出我能访问的场景包

能正常返回即配置成功。

## 开始使用

### 从零做一个场景包

> 我们每周要给 20 家门店做朋友圈广告投放复盘，把这个流程做成场景包。

Agent 会先访谈业务目标和验收标准，给出方案，你确认后才动手。

### 诊断已有场景包

> 这个场景包执行时总绕弯，你看下哪里配置有问题。

## 更新

Skill 更新需要重新下载 zip、在 Skills 页删除旧的再上传新的，然后**开新对话**——
Skill 只在会话开始时加载。详见 [`manus/UPDATE.md`](../manus/UPDATE.md)。

## 常见问题

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 连接器里的密钥错误或已撤销，重新编辑连接器 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限 |
| Skill 已上传但工具不可用 | 连接器和 Skill 是两处配置，确认第 2 步已完成 |
| 更新后行为没变 | 需要开新对话，Skill 不会在会话中途重载 |

更多见 [FAQ](../FAQ.md)。
