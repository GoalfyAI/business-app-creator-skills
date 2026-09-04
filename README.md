# Business App Creator Skills

把一段业务流程做成 GoalfyMax 上可以直接交给用户用的**业务应用**，并诊断、优化、迭代已有的业务应用。

这个仓库提供两个 Skill 和一套外部 MCP 工具（`business-app-creator-mcp`），让 Claude Code、Codex 这类编码 Agent 直接为你制作业务应用——从业务访谈、界面与数据设计、资产制作，到分层验收、上线发布和配套前后端应用的部署。

**业务应用是这套工具的主要产物，场景包只是业务应用下面的一个资产。**

## 业务应用是什么

业务应用是 GoalfyMax 上交付给最终用户的一个完整产品：用户在里面发起一次生产、跟进进度、审阅交付、记载和查看自己的业务数据。它由三部分组成：

| 组成 | 是什么 | 由哪个 Skill 制作 |
|---|---|---|
| **场景包（编排形）** | 业务应用的能力资产：业务路线编排 + Workflow + FastAgent + 工具集 + 任务点，定义了每个入口背后怎么跑 | `business-app-creator` |
| **业务应用数据集模板** | 每个用户各得一份的业务数据库结构（实体 / 情境 / 历史事件三类表） | `app-creator`（A2） |
| **前后端应用** | 用户看到的页面与专属后端：看板、数据管理、业务发起、项目页；预填、回流、编辑都在这里 | `app-creator`（A1–A5） |

三个概念不要混：**有业务路线编排的场景包才能有业务应用**；一个业务应用恰好挂载一个场景包，入口表单、中途表单、交付字段、事件全部来自这个包的契约；对用户说"业务应用"，对工具和资产关系说"场景包"。没有配套前后端应用的场景包也能在聊天里被调用，那是文件交付型，不是本仓库的主线。

## 支持的平台

先在 [开发者工具 → API 密钥](https://goalfymax.qa.goalfyai.cn/developer/api-keys) 创建个人密钥，密钥以 `sk_` 开头且只显示一次。
然后按下表选择你的平台。

| 平台 | 最快上手 | 详细指南 | 状态 |
|---|---|---|---|
| **Claude Code** | 把 [安装指南](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/claude-code/AGENTS.md) 发给 Agent，它会自己装完并验证 | [Claude Code 快速上手](docs/claude-code-quickstart.md) | 可用 |
| **Codex** | 把 [安装指南](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/codex/AGENTS.md) 发给 Agent，它会自己装完并验证 | [Codex 快速上手](docs/codex-quickstart.md) | 可用 |
| **Manus** | 在网页添加 MCP 连接器，上传 Skill 压缩包 | [Manus 快速上手](docs/manus-quickstart.md) | 可用，需手工操作 |
| **其他 MCP 客户端** | 手工配置远端 MCP，加载通用 Skill | [通用集成指南](generic/README.md) | 可用，步骤因客户端而异 |

**最省事的装法**：把上表「最快上手」里的安装指南链接直接发给你的 Agent，让它照着执行——
它会自己添加插件市场、安装插件、引导你提供密钥、写入配置，并在重启后验证工具是否可用。
你不需要自己敲任何命令。

> Manus 目前只能在其网页界面手工配置，无法把安装说明丢给 Agent 自动完成。

## 快速开始

### Claude Code

```bash
claude plugin marketplace add GoalfyAI/business-app-creator-skills
claude plugin install business-app-creator@business-app-creator
```

### Codex

```bash
codex plugin marketplace add GoalfyAI/business-app-creator-skills
codex plugin add business-app-creator@business-app-creator
```

不想自己敲命令的话，把对应平台的安装指南链接发给 Agent 即可（见上表）。
Manus 与其他客户端请看上表对应的指南。

### 配置访问密钥

在 GoalfyMax 的 [开发者工具 → API 密钥](https://goalfymax.qa.goalfyai.cn/developer/api-keys) 创建个人密钥，然后写进客户端配置：

```bash
# Claude Code：~/.claude/settings.json 的 env
"BUSINESS_APP_CREATOR_API_KEY": "<你的密钥>"

# Codex：~/.codex/.env
BUSINESS_APP_CREATOR_API_KEY=<你的密钥>
```

重启客户端，然后让 Agent 做一次只读验证，例如「列出我能访问的场景包」。

各平台完整安装说明见 [`claude-code/`](claude-code/README.md) 与 [`codex/`](codex/README.md)。

## 怎么用

装好之后直接用自然语言描述你的业务目标，Agent 会按 Skill 里的流程推进：

**从零创建**

> 我们每周要给 20 家门店做一次朋友圈广告投放复盘，把这个流程做成场景包。

Agent 会先访谈业务目标和验收标准，摸清现有能力，再决定用普通任务点还是 Workflow，
逐层制作并验证。

**诊断已有场景包**

> 这个场景包执行时总是绕弯，你看下哪里配置有问题。

Agent 会创建只读工单，逐层检查提示词、工具契约、编排配置和执行日志，给出定位结论。
确认要改时再新建写工单进入修复。

**基于执行日志优化**

> 参考项目 xxx 的执行日志，把这个场景包优化一版。

## 这个仓库包含什么

```
skills/         两个 Skill 的唯一源：business-app-creator/（业务应用的能力资产：场景包与编排）、app-creator/（业务应用的数据面与前后端应用）
claude-code/    Claude Code 插件目录：安装文档 + Skill 副本
codex/          Codex 插件目录：安装文档 + Skill 副本
manus/          Manus 集成说明 + 可上传的 Skill 压缩包
generic/        通用集成指南 + MCP 配置 + Skill 文件
docs/           各平台快速上手
scripts/        构建与发布工具
```

`skills/` 是 Skill 内容的唯一源，发布时复制到各平台，各平台拿到的 Skill 逐字节相同；
平台安装文档在各自目录里手工维护。

## 更新

Skill 版本写在 `SKILL.md` 的 description 里（`[skill-version:...]`），服务端据此判断你的
Skill 是否需要升级；版本过期时写操作会被拒绝。插件版本另走语义化递增，供插件管理器判断有无新版。

| 平台 | 更新方式 | 详细步骤 |
|---|---|---|
| **Claude Code** | `claude plugin update business-app-creator@business-app-creator` | [claude-code/UPDATE.md](claude-code/UPDATE.md) |
| **Codex** | `codex plugin marketplace upgrade business-app-creator` 后 remove + add | [codex/UPDATE.md](codex/UPDATE.md) |
| **Manus** | 重新下载 zip，在 Skills 页删旧传新，然后开新对话 | [manus/UPDATE.md](manus/UPDATE.md) |
| **其他 MCP 客户端** | 重新获取 `SKILL.md` 与 `references/` 并重新载入 | [generic/UPDATE.md](generic/UPDATE.md) |

被服务端提示版本过期时，按上表对应的 `UPDATE.md` 执行——那些文档是写给 Agent 直接照做的，
包含读取新版本标记、当前会话内重试、以及何时该提示你重启。

**升级后要重启**（Claude Code 可用 `/reload-plugins`）：版本闸门只校验版本串，读到新标记就能
继续工作，但 Agent 上下文里加载的 Skill 内容仍是旧版，重启后才真正生效。

## 文档

| 文档 | 用途 |
|---|---|
| [Claude Code 快速上手](docs/claude-code-quickstart.md) | 安装、验证、更新与排障 |
| [Codex 快速上手](docs/codex-quickstart.md) | 同上 |
| [Manus 快速上手](docs/manus-quickstart.md) | 连接器与 Skill 上传 |
| [通用集成指南](generic/README.md) | 其他 MCP 客户端 |
| 各平台 AGENTS.md | 交给 Agent 直接执行的安装流程：[Claude Code](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/claude-code/AGENTS.md) · [Codex](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/codex/AGENTS.md) |
| 各平台 UPDATE.md | 升级步骤，写给 Agent 直接执行：[Claude Code](claude-code/UPDATE.md) · [Codex](codex/UPDATE.md) · [Manus](manus/UPDATE.md) · [通用](generic/UPDATE.md) |
| [常见问题](FAQ.md) | 产品与使用问题 |
| [参与贡献](CONTRIBUTING.md) | 目录职责、本地验证、版本机制 |
| [安全策略](SECURITY.md) | 漏洞报告与安全约定 |

## 这个仓库不做什么

- 不替你执行一次性业务任务——那是场景包做好之后的事
- 不是 GoalfyMax 平台本身，只是制作场景包的工具链
- 不存储任何业务数据、凭证或密钥

## 许可

[Apache License 2.0](LICENSE)。使用 GoalfyMax 服务另受其服务条款约束。
