# 维护者手册

面向仓库维护者：校验、发版、版本策略与流水线。使用者请看 [README](../README.md)。

本仓库是编码 Agent 制作 GoalfyMax 场景包所用 Skills 的唯一源码仓库。不要在 MCP
服务端仓库中维护第二份可编辑的 Skill 副本。

## Skills 列表

- [`scene-creator`](../skill/SKILL.md)：通过经过审计的外部 MCP，把业务流程制作成可在
  GoalfyMax 直接使用的场景包，或诊断优化已有场景包。Skill 自带场景包资产模型、信息分层和
  Workflow/普通任务点/FastAgent 选型框架，并覆盖线上资产复用、工具契约取样、依赖和辅助文件
  准备、输入输出 Schema、场景编排、预览、`bubble` 验证、业务界面同工单制作与部署、可选全真
  项目验证、日志诊断、交付物检查和最终发布。

`scene-creator` 负责维护外部 Agent 的制作流程和高风险操作约束。完整的 Workflow 共享契约、
正反例与诊断文档仍由服务端 MCP 知识库统一维护，运行时通过 `get_diagnosis_doc` 按需加载。

## 校验

```bash
uv run pytest -q
uv run ruff check tests scripts/build_platform_packages.py
uv run python scripts/build_platform_packages.py check
```

## 从仓库当前分支验证

仓库根目录同时是 Codex 和 Claude Code 的插件市场。`codex/` 与 `claude-code/` 是自动生成并
提交到仓库的安装目录，只能编辑 `scene-creator/` 下的唯一源文件。下面从 `main` 添加市场只用于
当前 QA/开发分支验证；正式安装和升级由各平台的插件管理器完成，见下文。

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

正式安装和升级不构建、不上传 ZIP，也不克隆仓库：客户端各自的插件管理器从内网插件市场比较
`plugin.json` 版本并完成更新。各平台的安装和更新说明位于
[`platforms`](../platforms/)。

## 版本与环境策略

QA 阶段修改 Skill 内容、参考资料或平台模板后，仍需刷新发布清单、校验和与直接安装目录，
但不得修改 description 中的 `skill-version`：

```bash
uv run python scripts/build_platform_packages.py release \
  --version "<skill-release.json 中当前 package_version>" \
  --reason "<已验证的变更说明>"
```

正式上线时必须作为一次完整变更同时完成。版本号仅由 PROD 流水线执行
`scripts/prod-release-skill.py` 自动生成，格式与 GoalfyData 一致，为
`vYYYYMMDD-<6 位随机 hex>`；QA、PRE、
普通合并和手工构建都不得更新版本号。脚本在 `DEPLOY_ENV` 不是 `prod` 时会直接拒绝执行。

1. 在 PROD 流水线注入 `SCENE_SKILL_RELEASE_REGISTRY_TARGETS`，并在手工 PROD job 执行该脚本；

2. 将 Codex 和 Claude Code 的 MCP 配置切换到正式环境地址；
3. 将全部安装说明中的 API 密钥获取入口由 GoalfyMax QA 改为 GoalfyMax 线上环境；
4. PROD job 更新仓库中的 Skill 版本标记，统一提升两份 marketplace、两份插件 manifest、
   `pyproject.toml` 与 `uv.lock` 的 package patch，刷新发布清单和直接安装副本，提交并 tag；
   推送成功后由脚本幂等登记 Skill 版本。该流程不生成、不上传任何 ZIP 或其他制品。

Codeup Flow 的受控配置源位于 `.yunxiao/scene-creator-skills.yml`。`QA校验` 自动执行且只校验
当前版本；`PROD发布` 必须人工触发，并强制要求源分支为 `main`。PROD prepare 会把唯一源、OpenAI
元数据和两套插件模板统一渲染为国内生产 MCP `https://workflow-mcp.goalfyai.cn/mcp`，拒绝任何残留
QA URL 或 QA 密钥说明，并验证该路由已进入鉴权层；未部署或仍返回 404/5xx 时禁止切版。PROD job
更新仓库版本并推回 Codeup 后，才通过 HMAC 向各环境 Max Hub 登记版本。

Skill 只有一份、版本号只有一条线，但 Hub 分环境各自持有 registry。只登记生产会让其他环境的
registry 恒空，闸门在那些环境既不生效也无法验证，因此 `SCENE_SKILL_RELEASE_REGISTRY_TARGETS`
按行配置全部目标，每行一个 `<url>|<secret>`，脚本逐个登记并在结尾汇总失败：

```text
<QA Hub 登记接口 URL>|<QA secret>
<生产 Hub 登记接口 URL>|<生产 secret>
```

实际 URL 与密钥由流水线变量下发，不写进仓库。

各环境使用各自的 S2S 密钥，不得复用 GoalfyData Hub 的地址或密钥。未配置该变量时，脚本回退到
单目标的 `SCENE_SKILL_RELEASE_REGISTER_URL` 与 `SCENE_SKILL_RELEASE_S2S_SECRET`。

禁止只升级版本而继续连接 QA，或者在正式安装内容中保留 QA API 密钥获取说明。该流程不打包或
分发制品；升级由插件管理器从内网插件市场完成，仓库内 `codex/`、`claude-code/` 目录即市场内容。
`skill/<version>` tag 只用于把每个版本定位到一次提交，不作为客户端升级入口。required 策略
只能在生产 MCP 路由和平台更新说明都可用后开启。

只有在不改变已发布内容、仅需恢复被删除或误改的生成文件时，才运行 `sync`：

```bash
uv run python scripts/build_platform_packages.py sync
```
