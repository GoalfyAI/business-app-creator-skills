# 场景包制作 — Claude Code 插件

把业务流程沉淀为 GoalfyMax 场景包，诊断、优化并验证已有场景包。

本插件同时安装经过审计的 `business-app-creator` MCP 和同名 Skill，连接生产环境：

`https://workflow-mcp.qa.goalfyai.cn/mcp`

## 能做什么

- 从业务访谈出发，把一段流程沉淀成可复用的场景包
- 制作任务点、工具集、FastAgent、Workflow、多 Workflow 编排和业务界面
- 诊断已有场景包为什么效果差、绕弯多、执行失败
- 基于参考项目的执行日志复盘并优化
- 分层验收、真机验证与上线发布

## 安装前准备

- Claude Code 已安装并可执行 `claude` 命令
- 一个 GoalfyMax 账号，且有权访问目标场景包
- 一个 GoalfyMax 个人 API 密钥（见下文「配置密钥」）

## 安装

### 方式一：从公开插件市场（推荐）

```bash
claude plugin marketplace add GoalfyAI/scene-creator-skills
claude plugin install business-app-creator@business-app-creator
```

### 方式二：从本地仓库（开发与验证用）

```bash
git clone https://github.com/GoalfyAI/scene-creator-skills.git
cd scene-creator-skills
claude plugin marketplace add "$PWD"
claude plugin install business-app-creator@business-app-creator
```

本地目录添加的市场会一直复用该目录的内容，不会自动获取新版本。验证完请改回方式一。

## 配置密钥

在 GoalfyMax QA 环境的 [开发者工具 → API 密钥](https://goalfymax.qa.goalfyai.cn/developer/api-keys)创建个人密钥。

把完整密钥提供给当前 Agent，由它合并写入 `~/.claude/settings.json` 的
`env.BUSINESS_APP_CREATOR_API_KEY`，保留其他全部配置。你不需要自行编辑配置文件。

```json
{
  "env": {
    "BUSINESS_APP_CREATOR_API_KEY": "<你的个人 API 密钥>"
  }
}
```

`BUSINESS_APP_CREATOR_API_KEY` 只是本地变量名，插件会将它的值作为
`Authorization: Bearer <密钥>` 发送。

不要为鉴权配置 `user_id`、`X-User-ID` 或 `X-Project-ID`——MCP 会根据个人 API 密钥解析用户身份。

配置完成后彻底退出并重新打开 Claude Code。

## 验证

在新会话中确认：

1. `business-app-creator` 插件与 Skill 已加载
2. `business-app-creator` MCP 工具已就绪（如 `task_manager`、`list_assets`）
3. 执行一次只读请求，例如「列出我能访问的场景包」，能正常返回

## 更新

```bash
claude plugin update business-app-creator@business-app-creator
```

被服务端提示 Skill 版本过期时，按 [UPDATE.md](UPDATE.md) 执行。

## 故障排查

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 密钥缺失、已撤销，或新进程没有继承密钥。只检查变量是否存在，不要输出变量值 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限，检查 GoalfyMax 侧授权 |
| `503` | MCP 鉴权或注册中心依赖暂时不可用，等待恢复后重试，不要因此更换密钥 |
| 缺少 `task_manager` 等核心工具 | 部署尚未提供预期的外部契约。停止并记录线上工具 Schema；不要用静态工具数量代替实时清单 |
| Skill 已加载但 MCP 未连接 | 重新安装插件。只复制 Skill 目录不会安装 MCP 配置 |
| 升级后版本标记仍是旧值 | 插件市场可能绑定在本地目录，按 [UPDATE.md](UPDATE.md) 重新绑定到公开市场 |

## 密钥轮换

见 [UPDATE.md](UPDATE.md) 的「轮换个人 API 密钥」。
