# 场景包制作技能

本仓库是编码 Agent 制作 GoalfyMax 场景包所用 Skills 的唯一源码仓库。不要在 MCP
服务端仓库中维护第二份可编辑的 Skill 副本。

## Skills 列表

- [`scene-creator`](scene-creator/SKILL.md)：通过经过审计的外部 MCP，把业务流程制作成可在
  GoalfyMax 直接使用的场景包，或诊断优化已有场景包。Skill 自带场景包资产模型、信息分层和
  Workflow/普通任务点/FastAgent 选型框架，并覆盖线上资产复用、工具契约取样、依赖和辅助文件
  准备、输入输出 Schema、场景编排、预览、`bubble` 验证、可选全真项目验证、日志诊断、
  交付物检查和最终发布。

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

两个插件连接同一个外部 MCP。请将 GoalfyMax 个人 API 密钥配置到
`SCENE_CREATOR_API_KEY`，严禁把密钥提交到本仓库。密钥获取入口为 GoalfyMax QA 账号菜单 →
**开发者工具** → **API 密钥**（`/developer/api-keys`）。插件会把该密钥作为
Bearer 凭证发送，不需要另行配置用户 ID 鉴权参数。

## 构建安装包

```bash
uv run python scene-creator/release/build_platform_packages.py build \
  --output-dir dist/scene-creator
```

构建命令会生成 Codex 和 Claude Code 的完整本地插件市场 ZIP，安装时会同时启用 Skill 与
外部 MCP；此外还会生成一个平台无关的 Skill ZIP。各平台的安装和更新说明位于
[`scene-creator/release/platforms`](scene-creator/release/platforms/)。

## 版本与环境策略

全部功能正式上线前，插件版本固定为 `1.0.0`。QA 阶段修改 Skill 内容、参考资料或平台模板后，
仍需刷新发布清单、校验和与直接安装目录，但不得增加版本号：

```bash
uv run python scene-creator/release/build_platform_packages.py release \
  --version 1.0.0 \
  --reason "<已验证的变更说明>"
```

正式上线时必须作为一次完整变更同时完成：

1. 将 Codex 和 Claude Code 的 MCP 配置切换到正式环境地址；
2. 将全部安装说明中的 API 密钥获取入口由 GoalfyMax QA 改为 GoalfyMax 线上环境；
3. 更新发布工具中的审核地址，解除 QA 版本冻结，再从 `1.0.0` 推动后续版本。

禁止只升级版本而继续连接 QA，或者在正式安装包中保留 QA API 密钥获取说明。

只有在不改变已发布内容、仅需恢复被删除或误改的生成文件时，才运行 `sync`：

```bash
uv run python scene-creator/release/build_platform_packages.py sync
```
