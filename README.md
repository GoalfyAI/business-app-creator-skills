# Scene Creator Skills

把业务流程沉淀为 GoalfyMax 场景包，诊断、优化并验证已有场景包。

这个仓库提供一个 Skill 和一套外部 MCP 工具，让 Claude Code、Codex 这类编码 Agent 直接为你
制作场景包——从业务访谈、能力摸底、资产制作，到分层验收和上线发布。

## 场景包是什么

场景包是 GoalfyMax 上一套可复用的执行能力：把一段原本靠人重复执行的业务流程，连同它需要的
工具、提示词、编排和验收标准打包起来，之后同类任务交给 Agent 就能跑。

一个场景包通常包含这些资产：

| 资产 | 作用 |
|---|---|
| 普通任务点 | 一个可执行的业务动作 |
| 工具集 | 完成动作所需的一组工具 |
| FastAgent | 处理确定性子任务的轻量智能体 |
| Workflow | 把多个步骤编排成固定路径 |
| 业务界面 | 面向业务用户的操作入口 |
| 长期数据集 | 跨任务沉淀的业务数据 |

## 支持的平台

| 平台 | 安装方式 | 快速上手 |
|---|---|---|
| **Claude Code** | 插件市场 | [Claude Code 快速上手](docs/claude-code-quickstart.md) |
| **Codex** | 插件市场 | [Codex 快速上手](docs/codex-quickstart.md) |
| **Manus** | 网页添加连接器 + 上传 Skill | [Manus 快速上手](docs/manus-quickstart.md) |
| **其他 MCP 客户端** | 手工配置 MCP + 加载 Skill | [通用集成指南](generic/README.md) |

## 快速开始

### Claude Code

```bash
claude plugin marketplace add GoalfyAI/scene-creator-skills
claude plugin install scene-creator@scene-creator
```

### Codex

```bash
codex plugin marketplace add GoalfyAI/scene-creator-skills
codex plugin add scene-creator@scene-creator
```

Manus 与其他客户端请看上表对应的指南。

### 配置访问密钥

在 GoalfyMax 的**开发者工具 → API 密钥**创建个人密钥，然后写进客户端配置：

```bash
# Claude Code：~/.claude/settings.json 的 env
"SCENE_CREATOR_API_KEY": "<你的密钥>"

# Codex：~/.codex/.env
SCENE_CREATOR_API_KEY=<你的密钥>
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
skill/          Skill 内容唯一源：SKILL.md、Agent 元数据、参考资料
claude-code/    Claude Code 插件目录：安装文档 + Skill 副本
codex/          Codex 插件目录：安装文档 + Skill 副本
manus/          Manus 集成说明 + 可上传的 Skill 压缩包
generic/        通用集成指南 + MCP 配置 + Skill 文件
docs/           各平台快速上手
scripts/        构建与发布工具
```

`skill/` 是 Skill 内容的唯一源，发布时复制到四个平台，各平台拿到的 Skill 逐字节相同；
平台安装文档在各自目录里手工维护。

## 版本与升级

Skill 版本写在 `SKILL.md` 的 description 里（`[skill-version:...]`），服务端据此判断
你的 Skill 是否需要升级。插件版本走语义化递增，供插件管理器判断有无新版。

日常升级：

```bash
claude plugin update scene-creator@scene-creator     # Claude Code
```

被提示版本过期时，按 [`claude-code/UPDATE.md`](claude-code/UPDATE.md)
或 [`codex/UPDATE.md`](codex/UPDATE.md) 执行。

## 文档

| 文档 | 用途 |
|---|---|
| [Claude Code 快速上手](docs/claude-code-quickstart.md) | 安装、验证、更新与排障 |
| [Codex 快速上手](docs/codex-quickstart.md) | 同上 |
| [Manus 快速上手](docs/manus-quickstart.md) | 连接器与 Skill 上传 |
| [通用集成指南](generic/README.md) | 其他 MCP 客户端 |
| [常见问题](FAQ.md) | 产品与使用问题 |
| [参与贡献](CONTRIBUTING.md) | 目录职责、本地验证、版本机制 |
| [安全策略](SECURITY.md) | 漏洞报告与安全约定 |

## 这个仓库不做什么

- 不替你执行一次性业务任务——那是场景包做好之后的事
- 不是 GoalfyMax 平台本身，只是制作场景包的工具链
- 不存储任何业务数据、凭证或密钥

## 许可

[Apache License 2.0](LICENSE)。使用 GoalfyMax 服务另受其服务条款约束。
