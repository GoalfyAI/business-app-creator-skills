# 场景包制作技能

本仓库是编码 Agent 制作 GoalfyMax 场景包所用 Skills 的唯一源码仓库。不要在 MCP
服务端仓库中维护第二份可编辑的 Skill 副本。

## Skills 列表

- [`scene-creator`](scene-creator/SKILL.md)：通过经过审计的外部 MCP 制作、验证并发布
  Workflow 场景包。

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

修改 Skill 内容、参考资料或平台模板后，必须先发布新版本再提交。发布命令也会重新生成可直接
安装的插件市场目录：

```bash
uv run python scene-creator/release/build_platform_packages.py release \
  --version <MAJOR.MINOR.PATCH> \
  --reason "<已验证的变更说明>"
```

只有在不改变已发布内容、仅需恢复被删除或误改的生成文件时，才运行 `sync`：

```bash
uv run python scene-creator/release/build_platform_packages.py sync
```
