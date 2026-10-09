# Business App Creator Skills

本仓库提供制作和维护 GoalfyMax 智能应用的统一 Skill `business-app-creator` 与 MCP 连接配置。

制作入口、对象关系和合同来源见 [Skill](skills/business-app-creator/SKILL.md)，贡献与生成规则见 [CONTRIBUTING](CONTRIBUTING.md)。

## 支持的平台

先在 [开发者工具 → API 密钥](https://goalfymax.goalfyai.cn/developer/api-keys) 创建个人密钥，密钥以 `sk_` 开头且只显示一次。
然后按下表选择你的平台。

| 平台 | 最快上手 | 详细指南 | 状态 |
|---|---|---|---|
| **Claude Code** | 把 [安装指南](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/claude-code/AGENTS.md) 发给 Agent，它会自己装完并验证 | [Claude Code 快速上手](docs/claude-code-quickstart.md) | 可用 |
| **Codex** | 把 [安装指南](https://raw.githubusercontent.com/GoalfyAI/business-app-creator-skills/main/codex/AGENTS.md) 发给 Agent，它会自己装完并验证 | [Codex 快速上手](docs/codex-quickstart.md) | 可用 |
| **Manus** | 在网页添加 MCP 连接器，上传 Skill 压缩包 | [Manus 快速上手](docs/manus-quickstart.md) | 可用，需手工操作 |
| **其他 MCP 客户端** | 手工配置远端 MCP，加载通用 Skill | [通用集成指南](generic/README.md) | 可用，步骤因客户端而异 |

## 怎么用

装好之后直接用自然语言描述你的业务目标，Agent 会按 Skill 里的流程推进：

**从零创建**

> 我们每周要给 20 家门店做一次朋友圈广告投放复盘，把这个流程做成智能应用。

Agent 会先访谈业务目标和验收标准，摸清现有能力，再决定用普通任务点还是 Workflow，
逐层制作并验证。

**诊断已有智能应用**

> 这个智能应用执行时总是绕弯，你看下哪里配置有问题。

Agent 会创建只读工单，逐层检查提示词、工具契约、编排配置和执行日志，给出定位结论。
确认要改时再新建写工单进入修复。

**基于执行日志优化**

> 参考项目 xxx 的执行日志，把这个智能应用优化一版。

## 这个仓库包含什么

```
skills/         business-app-creator/ 是唯一源：入口、七个制作 flow、任务路由与按需参考
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

按对应客户端的更新指南执行：

| 平台 | 更新方式 | 详细步骤 |
|---|---|---|
| **Claude Code** | `claude plugin update business-app-creator@business-app-creator` | [claude-code/UPDATE.md](claude-code/UPDATE.md) |
| **Codex** | `codex plugin marketplace upgrade business-app-creator` 后 remove + add | [codex/UPDATE.md](codex/UPDATE.md) |
| **Manus** | 重新下载 zip，在 Skills 页删旧传新，然后开新对话 | [manus/UPDATE.md](manus/UPDATE.md) |
| **其他 MCP 客户端** | 重新获取 `SKILL.md` 与各内容目录并重新载入 | [generic/UPDATE.md](generic/UPDATE.md) |

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
