---
name: business-app-creator-lite
description: 把一个业务需求快速做成最终用户能持续使用的 GoalfyMax 智能应用（场景包 + 数据模板 + 前后端应用）的加速版：先判断需求复杂度，简单需求直接从预置件与生成器搭，复杂需求先用一张「人 / 模型 / 规则」分工表对齐再编译成资产；核实资产、搭积木、verify、预览、上线。与 business-app-creator 并存，用于 A/B。[skill-version:v20260923-lite01]
keywords:
  - 智能应用
  - 智能应用开发
  - business app
  - business-app-creator-lite
  - GoalfyMax
  - 场景包
  - scene package
  - scenario package
  - workflow
  - business UI
  - 业务应用
  - 分工表
  - 加速模式
  - MCP
---
# 智能应用快速制作（lite）

<!-- scaffold-min-required-version:v20260916-8941ec -->

> 这份 Skill 的目标是**从 0.8 到 1**：脚手架已经带组件层、页面块、按表生成器和可运行的起始应用，MCP 有 `verify`（一次出验收报告）与 `assemble`（自动组装路线）。你的工作是把用户说的业务变成分工表，再把分工表编译成资产，不再从零设计。用户全程不需要知道 FA、TPE、工具集这些平台对象是什么。

## 0. 红线（不可豁免）

- 不开发反华、涉政违规、违法或敏感内容的需求，识别即停止。
- 凭据（数据库连接串、密钥、token）不进工单、不进聊天、不进代码。
- 花钱、发信、发布、写正式数据、上线这类外部副作用，先说清范围再做，用户明确同意后执行。
- 不伪造任何平台身份：`workflow_runtime_id` 只由服务端生成；`orchestration_id` 只取自场景包里已定义的路线；`business_id` 由调用方在发起时生成、同一实例内不变。
- 零捏造：没读过的契约不猜参数，没跑过的结果不说通过；证据不足就写「未验证」。

## 1. 入口：先判断复杂度，再选路

拿到需求后先回答三个问题，不用问用户：

| 问题 | 否 | 是 |
|---|---|---|
| 需要模型判断的步骤（判读、生成、诊断）？ | | 至少一条模型行 |
| 需要人在中途介入（补信息、确认、审阅结果）？ | | 至少一条人行 |
| 多于一条业务路线，或路线之间有依赖 / 重入？ | | 复杂 |

- **简单应用**（全是「否」，或只有规则行）：展示页、台账、数据管理、单次拉数落库。不做梳理，不写分工表；按 [`design/确认页.md`](./design/确认页.md) 的简版发**一次**确认（功能清单、表名与字段、选项取值与默认值、上线范围），用户说「可以」再进第 3 节加速模式。用户说过的名字、字段、选项一字照用，不自行改名或增删取值。
- 平台要求应用挂一个场景包且至少一条路线。简单应用只建一条纯规则的最小路线满足这条要求，应用界面不发起它；在确认页里如实说明。
- **复杂应用**（有模型行或人行，或多路线）：先做第 2 节沟通，产出分工表并一次确认，再进加速模式。

拿不准按复杂处理，分工表本来就短。

## 2. 沟通：一张分工表说清人、模型、规则

读 [`design/分工表.md`](./design/分工表.md)，按模板把每条路线写成一张表：每行一步，四列——**步骤、谁做（人 / 模型 / 规则）、进什么出什么、做不成怎么办**。先从三张参考分工表里挑最像的改，再和用户核对。

确认只做一次：读 [`design/确认页.md`](./design/确认页.md) 把功能清单、分工表、进出物、失败处理、费用与副作用、上线范围写成一页发给用户。用户说「可以」就进加速模式；改动只改表，改完重新编译。

不要展开访谈、样品挑选、价值论证。用户主动要求深入梳理业务时，再按 [`design/咨询模式.md`](./design/咨询模式.md) 处理。

## 3. 加速模式：核实资产 → 搭积木 → verify → 预览 → 上线

每一步一份文件，按顺序读，读完就做：

| 步 | 做什么 | 读 |
|---|---|---|
| 3.0 | 建工单、初始化应用工程（一次） | 本节下方 |
| 3.1 | 核实资产能力：已有工具、FA、模板表、组件与页面块能不能直接用 | [`build/核实资产.md`](./build/核实资产.md) |
| 3.2 | 把分工表编译成场景包资产：工具集、FA、编排型 TPE、路线 | [`build/编译规则.md`](./build/编译规则.md)，脚本照 [`build/脚本模板.md`](./build/脚本模板.md) |
| 3.3 | 数据模板与应用：建表、`gen:pages` 生成数据页、用页面块搭业务页 | [`build/应用.md`](./build/应用.md) |
| 3.4 | verify 出报告、真跑一次、部署预览给用户看、上线 | [`build/验收.md`](./build/验收.md)，人判项按 [`checklists/验收清单.md`](./checklists/验收清单.md) |

**3.0 建工单与工程**（每个应用只做一次）：

1. `task_manager(action="create", mode="write")`，标题写应用名；之后所有制作、部署、运行工具都带这个 `task_id`。用 `task_manager(action="insert", entry_type="checkpoint")` 记关键事实（资产 ID、版本、run_id），不写过程流水。
2. 应用工程：在桌面工作台分配的目录下 `npm run scaffold:init -- --environment <环境> --app-name "<应用名>"`，然后 `npm run setup`、`npm run doctor`。已有工程就接续，不重跑 init。
3. 开工前读一次 `dev_preferences(action="pull")` 拿开发者偏好，按需读，不塞进对话。

不写 proposal HTML、计划书、制作书、承诺清单；给用户看的只有确认页和跑起来的预览。

## 4. 工具速查

| 要做的事 | 工具与动作 |
|---|---|
| 找可复用资产 | `list_assets(asset_type=…, keyword=…)` → `get_asset(asset_type=…, asset_ids=[…])` |
| 真调一次工具看返回 | `otpe_tool_test(tool_group_id, tool_id, input)` |
| 场景包 | `scene_package_manage(action=create / update / assemble / bubble / finalize / online)` |
| 工具集 / FA / 工具组 | `create_toolset`、`create_fast_agent`、`preview_tool_group` → `register_and_refresh_tool_group`、`create_auth_card` |
| 编排型 TPE | `otpe_manage(action=preview / create / update / online / bubble / verify)` |
| 数据模板 | `dataset_template_workspace(action=open / bind / create_table / inspect / extract)` |
| 应用与部署 | `business_ui_manage(action=create / get / update / finalize)`，`business_ui_bundle(action=prepare_upload / complete_upload / deploy / status)` |
| 真跑 | `manage_goalfymax_project(action=run / wait / status / reply / stop)`，`get_project_execution_logs(action=workflow_trace / summary)` |
| 上线 | `finalize_asset_version_online(asset_type="scenario_pack")`，`business_ui_manage(action="finalize")` |
| 平台问题 | `submit_dev_feedback` |

参数以工具当前的 schema 为准；本 Skill 不抄参数表。调用被拒时按返回的提示改，不猜。

## 5. 什么时候读长契约

只在报错或要做不常见的事时读，按 topic 用 `get_diagnosis_doc(topic=…)`：

| 情况 | topic |
|---|---|
| 写第一条编排脚本前 | `otpe_authoring` → `otpe_single` |
| 路线要并行、扇出、中途表单、节点级接管 | `otpe_multi` |
| 工具返回要按字段用、`_output` 报形状错 | `otpe_example_tool` |
| 脚本有文件输入输出 | `otpe_example_file` |
| 有真正可选的步骤或部分成功 | `otpe_example_failure` |
| 交付审阅、Agent 接管 | `otpe_example_handoff` |

## 6. 汇报

每完成一步给用户一句话：做了什么、结果怎样、下一步。verify 报告直接贴 `verdict` 与 `failed` 项。上线后给交付报告：应用名与版本、`entry_url`、场景包版本、数据模板版本、已验证的路线与一次真跑的 run_id、已知未验证项。
