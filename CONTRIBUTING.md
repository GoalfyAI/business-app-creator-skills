# 参与贡献

欢迎提交问题反馈、改进建议和代码。

## 提交问题

发现 Skill 指引有误、工具契约对不上、或制作流程卡住时，请开 Issue 并附上：

- 你使用的客户端（Claude Code / Codex）与版本
- `SKILL.md` description 里的 `[skill-version:...]` 值
- 完整的复现步骤和 Agent 的实际行为
- 相关的工具返回（**移除密钥、Cookie、预签名 URL 等敏感内容**）

安全漏洞请勿公开提交，见 [SECURITY.md](SECURITY.md)。

## 目录职责

| 目录 | 说明 |
|---|---|
| `skills/business-app-creator/` | Skill 的唯一源：`SKILL.md`（红线、角色、任务识别、开工、五段表与交棒条件、工具速查）、`stages/`（五段：需求确认、方案、制作、试用验收、上线，每段交给开发者什么、开发者做什么、什么时候交棒）、`tasks/`（接续、修订、诊断、能力试用、仅讨论的入口）、`design/`（PRD、按轮问、谁来做、选择题与判断题、交接消息等沟通模板）、`reference/`（按需查阅的平台细则正本）、`checklists/`、`scripts/`、`agents/openai.yaml` |
| `scripts/` | 构建与发布工具 |
| `tests/` | 测试 |
| `claude-code/`、`codex/` | 插件安装文档手工维护；`skills/` 子目录由发布流程复制，**不要手工编辑** |
| `manus/`、`generic/` | 集成说明手工维护；Skill 副本与 `.zip` 由发布流程生成，**不要手工编辑** |
| `.claude-plugin/`、`.agents/` | 插件市场清单，版本号由发布流程更新 |

Skill 副本与压缩包由发布流程重建，手工改动会被覆盖并导致校验失败。要改 Skill 内容
请改 `skills/` 下的唯一源，然后执行 `release` 重新生成。

## 提交代码

只修改 `skills/business-app-creator/`、各平台目录下的安装文档、`scripts/`、`tests/`。

改完源文件后必须刷新发布清单，否则校验不通过——这一步会同时重建四个平台的 Skill
副本和两个压缩包：

```bash
uv run python scripts/build_platform_packages.py release \
  --version "<skill-release.json 中当前 package_version>" \
  --reason "<变更说明>"
```

版本号只能由发布流水线更新，日常提交不要改动它。

## 本地验证

```bash
uv sync --group dev
uv run ruff check scripts tests
uv run pytest -q
uv run python scripts/build_platform_packages.py check
```

四项都通过再提 PR。

## 修改 Skill 内容

`skills/business-app-creator/` 是给 Agent 读的执行指引，不是给人读的说明书。每类文件有固定写法，发布检查会校验：

- `stages/` 正好五份：`1-需求确认.md`、`2-方案.md`、`3-制作.md`、`4-试用验收.md`、`5-上线.md`；每份必须按顺序包含「进入条件」「段里怎么做」「产出与落盘」「出问题怎么办」四节，中间可以有「开发者要看、要做的」「不给开发者的」「交棒条件」等小节
- 五段与工作区阶段的对应固定为 ① = G1、G2，② = G3，③ = G4、G5，④ = G6，⑤ = G7；工作区 `workspace.json` 仍是 G1–G7 七项
- `reference/` 每份依次四节：适用场景、规则、常见错误、相关工具与契约主题
- `tasks/` 每份依次三节：识别信号、先读什么、从哪一段进
- 行数预算：`SKILL.md` ≤ 200 行，`stages/` 单文件 ≤ 160 行，`reference/` 单文件 ≤ 400 行；超了先把 AI 内部做法的细表移到已链接的 `reference/` 或 `design/`，红线、四类确认、五段表与交棒条件留在原处，不调高预算
- 正文里指向 Skill 自身文件的链接必须存在

写作时注意：

- 用**必须** / **禁止**这类明确的强调词，不要写模棱两可的建议
- 写最终规则，不写「原来怎样、现在改为怎样」这类新旧对照
- 不要出现平台内部实现细节、代码或组件名
- 同事补内容主要往 `reference/` 和 `tasks/` 里加；`SKILL.md` 只做入口和路由，`stages/` 写每段交给开发者什么、开发者做什么、交棒和退回条件
- 一个事实只放一处，别处用相对路径引用；平台参数、错误码全文、契约字段不抄，写工具 Schema 或 `get_diagnosis_doc` 的 topic 名。例如阶段记录 `business_ui_stage` 的参数写法和 ④ 的浏览器做法只写在 `reference/开发者中心与工作区.md`，段文件只写本段出口写哪几项
- 对外文案（description、keywords）是唯一源，会被注入到各平台安装文件

## 环境约定

仓库里的安装物料**始终是生产配置**，`.mcp.json` 指向生产 MCP。发布流程不做环境渲染。

需要连测试环境时，改**本地已安装插件**的配置，不要动仓库源文件：

```
~/.claude/plugins/marketplaces/business-app-creator/claude-code/.mcp.json
```

改仓库源文件会让 `check` 因校验和不匹配而失败，也有把测试地址发进正式包的风险。

## 版本机制

两个版本号各自独立，一次发布同时更新：

| | 用途 | 格式 |
|---|---|---|
| `version` | Skill 版本，服务端据此判断是否需要升级 | `vYYYYMMDD-<6 位小写 hex>` |
| `package_version` | 插件版本，插件管理器据此判断有无新版 | `MAJOR.MINOR.PATCH` |

Skill 版本必须不可预测，插件版本必须可比大小，两个要求冲突，所以分成两个号。

**版本号只由发版脚本更新**，日常提交不要手工改动。原因是 `main` 本身就是插件市场：版本号
一进 `main` 就分发给所有用户，若服务端未登记该版本，用户会被判定过期且升级无解。

## 发版

发版跟随 Codeup 的环境部署，GitHub 只作为安装源，由流水线推送，不在 GitHub 上手工改分支。
入口都是 `scripts/deploy_env.py`，有两类云效流水线：

- **发版流水线**（模板 `scripts/flow/skill-release.yaml`，只跑 main，走 OA 发车）：
  准备发版（发版或沿用，发布提交写进 `USER_COMMIT`）→ 部署pre（回调 OA 生成发版审查）→
  PRE审批（OA 发车放行）→ 部署prod（回调 OA 核验生产并对账）。PRE 与 prod 部署的是同一个发布提交，
  审批期间 main 上新合入的提交不会被带进 prod。OA 规范服务 scene-creator-skills 登记的就是这条流水线。
- **QA 环境流水线**（模板 `scripts/flow/skill-env-deploy.yaml`，运行时选分支）：功能分支与 main 在 QA 测试用。PRE 只由发版流水线部署 main。

| 环境 | GitHub 安装分支 | 部署 main | 部署其他分支 |
|---|---|---|---|
| qa | `business-qa` | 发版（或沿用）→ 推分支 → 登记 → 强制线与建议线设为该版本 | 生成新版本 → 推分支 → 登记，不动版本线 |
| pre | `business-pre` | 只经发版流水线的部署pre | 不部署 |
| prod | `main` | 只经发版流水线，OA 发车放行后执行 | 不允许 |

部署 main 时，main 最新提交上已有 `skill/<version>` tag 就沿用该版本；否则流水线运行
`release-skill.sh` 切新版本，把发布提交与 tag 推回 Codeup main。同一份 main 先后部署到三个
环境用的是同一个版本。qa / pre 的安装物料由 `build_env_branch.py` 按环境渠道生成（MCP 地址、
密钥变量名、升级链接都换成该环境），`package_version` 为源码版本加 `-<环境>.<构建号>`。
版本线按登记 ID 只升不降，应急开关保持原值。

每条流水线需要的变量见流水线模板注释（发版流水线另需 PRE 的 `SKILL_REGISTRY_SECRET_PRE`、`HUB_API_KEY_PRE`）：`SKILL_ENV`，以及加密的 `CODEUP_PUSH_URL`、
`GITHUB_PUSH_URL`、`SKILL_REGISTRY_SECRET`、`HUB_API_KEY`、`HUB_OPERATOR_EMAIL`、`HUB_OPERATOR_ID`。
任何一项缺失都在写入前失败。

本地仍可用 `./scripts/release-skill.sh "变更说明"` 切版本并推送 main 与 tag；之后运行对应环境
流水线时会沿用这个版本。

GitHub Actions：

| Workflow | 触发 | 作用 |
|---|---|---|
| `publish-skill-release` | `skill/v*` tag | 从发布清单创建 GitHub Release |
| `build-platform-zips` | Skill 内容变更 | 重新打包 Manus 与通用集成的压缩包 |
| `register-skill-release` / `register-skill-qa` | 仅手动 | 应急补登记，日常不用 |

两条流水线各自串行，跨环境不加锁；现有策略接口是整体 PUT，人工编辑策略须避开部署写窗口。

## 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat(skill): 新增业务界面制作流程
fix(release): 修正平台模板校验和比对
docs: 补充 Codex 安装说明
```

## 行为准则

参与本项目即表示同意遵守 [行为准则](CODE_OF_CONDUCT.md)。

## 许可

提交的贡献将按 [Apache License 2.0](LICENSE) 授权。
