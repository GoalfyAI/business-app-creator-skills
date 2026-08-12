# 场景包制作技能

本仓库是编码 Agent 制作 GoalfyMax 场景包所用 Skills 的唯一源码仓库。不要在 MCP
服务端仓库中维护第二份可编辑的 Skill 副本。

## Skills 列表

- [`scene-creator`](scene-creator/SKILL.md)：通过经过审计的外部 MCP，把业务流程制作成可在
  GoalfyMax 直接使用的场景包，或诊断优化已有场景包。Skill 自带场景包资产模型、信息分层和
  Workflow/普通任务点/FastAgent 选型框架，并覆盖线上资产复用、工具契约取样、依赖和辅助文件
  准备、输入输出 Schema、场景编排、预览、`bubble` 验证、业务界面同工单制作与部署、可选全真
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

QA 阶段修改 Skill 内容、参考资料或平台模板后，仍需刷新发布清单、校验和与直接安装目录，
但不得修改 description 中的 `skill-version`：

```bash
uv run python scene-creator/release/build_platform_packages.py release \
  --version 1.0.0 \
  --reason "<已验证的变更说明>"
```

正式上线时必须作为一次完整变更同时完成。版本号仅由 PROD 流水线执行
`scripts/prod-release-skill.py` 自动生成，格式为 `vYYYYMMDD-<Git SHA 前 6 位>`；QA、PRE、
普通合并和手工构建都不得更新版本号。脚本在 `DEPLOY_ENV` 不是 `prod` 时会直接拒绝执行。

1. 在 PROD 流水线注入 `CI_COMMIT_SHA`、`SCENE_SKILL_RELEASE_S2S_SECRET`、
   `SCENE_SKILL_RELEASE_REGISTER_URL`，并在手工 PROD job 执行该脚本；

2. 将 Codex 和 Claude Code 的 MCP 配置切换到正式环境地址；
3. 将全部安装说明中的 API 密钥获取入口由 GoalfyMax QA 改为 GoalfyMax 线上环境；
4. PROD job 更新仓库中的 Skill 版本标记、发布清单和直接安装副本，提交并 tag；推送成功后由脚本幂等登记版本。该流程不生成、不上传任何 ZIP 或其他制品。

Codeup Flow 的受控配置源位于 `.yunxiao/scene-creator-skills.yml`。`QA校验` 自动执行且只校验
当前版本；`PROD发布` 必须人工触发，并强制要求源分支为 `main`。PROD job 更新仓库版本并推回
Codeup 后，才通过 HMAC 向 CN Max Hub 登记版本。`SCENE_SKILL_RELEASE_REGISTER_URL` 当前固定指向
`https://goalfyhub.goalfyai.cn/api/internal/workflow/scene-skill-versions/releases/register`；流水线必须
单独配置 `SCENE_SKILL_RELEASE_S2S_SECRET`，不得复用 GoalfyData Hub 的地址或密钥。

禁止只升级版本而继续连接 QA，或者在正式安装包中保留 QA API 密钥获取说明。

只有在不改变已发布内容、仅需恢复被删除或误改的生成文件时，才运行 `sync`：

```bash
uv run python scene-creator/release/build_platform_packages.py sync
```
