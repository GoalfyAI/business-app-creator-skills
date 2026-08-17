# 场景包制作技能

本仓库是编码 Agent 制作 GoalfyMax 场景包所用 Skills 的唯一源码仓库。不要在 MCP
服务端仓库中维护第二份可编辑的 Skill 副本。

## Skills 列表

- [`scene-creator`](scene-creator/SKILL.md)：通过经过审计的外部 MCP，把业务流程制作成可在
  GoalfyMax 直接使用的场景包，或诊断优化已有场景包。Skill 自带场景包资产模型、信息分层和
  Workflow/普通任务点/FastAgent 选型框架，并覆盖线上资产复用、工具契约取样、依赖和辅助文件
  准备、输入输出 Schema、场景编排、预览、`bubble` 验证、所有 Workflow 场景包的业务界面同工单
  制作与部署、可选全真
  项目验证、日志诊断、交付物检查和最终发布。

`scene-creator` 负责维护外部 Agent 的制作流程和高风险操作约束。完整的 Workflow 共享契约、
正反例与诊断文档仍由服务端 MCP 知识库统一维护，运行时通过 `get_diagnosis_doc` 按需加载。

## 校验

```bash
uv run pytest -q
uv run ruff check tests scene-creator/release/build_platform_packages.py
uv run python scene-creator/release/build_platform_packages.py check
```

## 直接从本仓库安装

仓库根目录同时是 Codex 和 Claude Code 的插件市场。`codex/` 与 `claude-code/` 是自动生成并
提交到仓库的安装目录，只能编辑 `scene-creator/` 下的唯一源文件。

Codex:

```bash
codex plugin marketplace add \
  git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git \
  --ref main
codex plugin add scene-creator@scene-creator
```

Claude Code:

```bash
claude plugin marketplace add \
  git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git
claude plugin install scene-creator@scene-creator
```

两个插件连接同一个正式生产外部 MCP：`https://workflow-mcp.goalfyai.com/mcp`。个人 API 密钥
获取入口为 GoalfyMax 账号菜单 → **开发者工具** → **API 密钥**（`/developer/api-keys`）。用户
只需把完整密钥提供给执行安装的 Agent，Agent 负责将其安全配置为
`SCENE_CREATOR_API_KEY`；不得要求用户自行编辑配置文件，也不得把密钥提交到本仓库、输出到回复
或写入日志。插件会把该密钥作为 Bearer 凭证发送，不需要另行配置用户 ID 鉴权参数。

## 构建安装包

```bash
uv run python scene-creator/release/build_platform_packages.py build \
  --output-dir dist/scene-creator
```

构建命令会生成 Codex 和 Claude Code 的完整本地插件市场 ZIP，安装时会同时启用 Skill 与
外部 MCP；此外还会生成一个平台无关的 Skill ZIP。各平台的安装和更新说明位于
[`scene-creator/release/platforms`](scene-creator/release/platforms/)。

## 版本与环境策略

插件只生成正式生产安装包，不保留其他环境地址、密钥说明或环境切换逻辑。Skill 内容、参考资料、
平台模板或生产 MCP 配置发生变化时，使用大于当前版本的 `MAJOR.MINOR.PATCH` 刷新发布清单、
校验和与直接安装目录：

```bash
uv run python scene-creator/release/build_platform_packages.py release \
  --version <新的 MAJOR.MINOR.PATCH> \
  --reason "<已验证的变更说明>"
```

发布校验必须确认正式生产地址，并拒绝要求用户自行写入密钥的安装说明。

只有在不改变已发布内容、仅需恢复被删除或误改的生成文件时，才运行 `sync`：

```bash
uv run python scene-creator/release/build_platform_packages.py sync
```
