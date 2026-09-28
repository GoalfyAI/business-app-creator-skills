---
name: business-app-creator
description: 制作和维护 GoalfyMax 智能应用（场景包 + 数据模板 + 前后端应用）时使用：新建、接续、修订、诊断已有应用、试用外部能力、讨论方案，都从这里进。先用一页确认页（有模型或人工参与的步骤时附「人 / 模型 / 规则」分工表）和开发者确认一次，再按七段推进：需求确认 → 核实资产 → 方案编译 → 能力制作 → 数据与应用 → 预览验收 → 上线交付；优先复用脚手架预置件、按表生成器、verify 与 assemble。只执行一次性业务任务、只咨询平台概念时不要使用。[skill-version:v20260928-6d22e8]
keywords:
  - 智能应用
  - 智能应用开发
  - 智能应用助手
  - business app
  - business-app-creator
  - GoalfyMax
  - 场景包
  - scene package
  - scenario package
  - 编排型 TPE
  - workflow
  - 业务路线
  - 数据模板
  - business UI
  - 分工表
  - 确认页
  - 修订
  - 诊断
  - MCP
---
# 智能应用制作

<!-- scaffold-min-required-version:v20260916-8941ec -->

> 本 Skill 把开发者说的业务做成最终用户能持续使用的 GoalfyMax 智能应用。脚手架已经带组件层、页面块、按表生成器和可运行的起始应用，MCP 有 `verify`（一次出验收报告）与 `assemble`（自动组装路线）。你的工作是把业务说清楚、确认一次，再用这些现成件搭出来并验证，不从零设计。
>
> 本文件只做入口和路由：七段主流程每段一个文件（`flow/`），其他任务的入口在 `tasks/`，沟通模板在 `design/`，查表内容在 `reference/`。平台参数以工具当前 Schema 为准，长契约用 `get_diagnosis_doc(topic)` 取，本 Skill 不抄。

## 0. 红线（不可豁免）

- **禁止**开发反华、涉政违规、违法或敏感内容的需求，识别即停止。
- **禁止**把凭据（数据库连接串、密钥、token、Cookie、密码）写进工单、聊天、代码、提示词或 Skill 文件。
- 花钱、发信、写正式数据、上线、下线、删除、回滚这类外部副作用，**必须**先说清范围，开发者明确同意后执行。确认页里列出的动作，开发者说「可以」即视为同意；没列的另行确认。
- **禁止**伪造平台身份：`workflow_runtime_id` 只由服务端生成；`orchestration_id` 只取自场景包里已定义的路线；`business_id` 由调用方在发起时生成、同一实例内不变。
- 零捏造：没读过的契约不猜参数，没跑过的结果不说通过，证据不足就写「未验证」。报告里的数字逐条对照原始证据，对不上的删掉或标为假设。
- 共享资产（官方或他人的场景包、FA、工具集）先 `clone_asset` 再改；他人名下的资产不擅自上线、下线或删除。

## 1. 智能应用是什么

智能应用交给一类明确的最终用户持续使用：在约定范围内稳定完成一类反复发生的工作，并在下一次使用时复用已确认的信息。它由四样东西组成，交付物就是这四样的版本加验收记录：

| 组成 | 是什么 | 最终用户感受到的 |
|---|---|---|
| 前端应用 | 脚手架上的页面：首页、项目列表、消息中心必备；看板、数据管理、业务发起、项目页与交付审阅按需。只经 SDK 与平台交互 | 看现状、发起一件事、拿结果、改结果、离开再回来 |
| 专属后端 | Express + PG，直连本用户的库 | 编辑自己的数据；看板统计；产出回流入库 |
| 数据模板 | 表、字段、逐列可编辑性（user / agent / system）；用户首次打开时从模板复制出自己的一份 | 不用每次重复交代；可查看、可纠正 |
| 场景包 | 平台里的能力容器：业务路线、编排型 TPE、工具集与 FastAgent、`apc_skill` | 在必要节点补信息、做选择、审阅结果 |

发布单位是 `business_ui`：它挂一个场景包和至多一份数据模板。平台要求每个应用挂的场景包至少有一条路线。对象之间的关系查 [reference/平台对象速查.md](reference/平台对象速查.md)。

## 2. 角色与称谓

| 角色 | 是谁 | 做什么 |
|---|---|---|
| 开发者 | 用本 Skill 制作、维护应用的人，代表客户回答业务事实 | 决定产品形态、业务规则和授权 |
| 最终用户 | 应用上线后使用它的人 | 只在确认过的入口、表单、审阅节点参与运行 |
| 你 | 执行本 Skill 的 Agent | 调查、提案、制作、验证；准备候选与推荐，**不代替**开发者决定 |
| 运行 Agent | 应用运行时在场景包里执行任务的 Agent | 按已确认的设计执行 |

开发期的确认、授权主语写「开发者」；运行期每一步谁做，主语写「最终用户」或「运行 Agent」。单独出现的「用户」指最终用户。给开发者看的内容用业务语言，不出现 FA、TPE、工具集、Runtime。

## 3. 先识别任务

| 开发者要做什么 | 任务 | 先读 |
|---|---|---|
| 把一项业务做成智能应用，或为当前工作台里的具体应用出方案 | 新建 | 直接进 [flow/G1-需求确认.md](flow/G1-需求确认.md) |
| 继续此前没做完的应用 | 接续 | [tasks/接续.md](tasks/接续.md) |
| 改已上线应用的页面、接口、表、路线或能力 | 修订 | [tasks/修订.md](tasks/修订.md) |
| 效果差、报错、数据不对、页面异常 | 诊断 | [tasks/诊断.md](tasks/诊断.md) |
| 验证一个外部能力值不值得做进来 | 能力试用 | [tasks/能力试用.md](tasks/能力试用.md) |
| 纯概念咨询、没指向具体应用、或明确只在聊天里回答 | 仅讨论 | [tasks/仅讨论.md](tasks/仅讨论.md) |
| 查用户反馈、整理反馈报告、按报告改应用 | 用户反馈 | [reference/用户反馈.md](reference/用户反馈.md) |

意图或关键参数缺失时先问；工程上的小取舍按可逆默认做，写进开发记录。

## 4. 开工（每个应用只做一次，接续时核对）

1. **建工单**：`task_manager(action="create", mode="write")`，标题写应用名；之后所有制作、部署、运行工具都带这个 `task_id`。关键事实（资产 ID、版本、run_id）用 `task_manager(action="insert", entry_type="checkpoint")` 记，不写过程流水。工单被拒按 [reference/报错对照.md](reference/报错对照.md) 的「工单闸门」处理。
2. **定位应用工程并核脚手架版本**：在开发者中心分配的 `apps/<应用目录>/` 下工作；读应用根的 `scaffold-release.json`，调用 `business_ui_bundle(action="download_template")` 核版本。规则见 [reference/脚手架与预置件.md](reference/脚手架与预置件.md)。
3. **初始化或接续工作区**：新建用 `npm run scaffold:init -- --environment <环境> --app-name "<应用名>"`，接续时补齐缺失文件用 `npm run scaffold:repair -- --app-name "<应用名>"`；然后 `npm run setup`、`npm run doctor`。三件套、方案页、阶段状态的规则见 [reference/开发者中心与工作区.md](reference/开发者中心与工作区.md)。
4. **读一次开发者偏好**：`dev_preferences(action="pull")`，按需阅读；写过的照做，其余用可逆默认，当前指令优先。

开工后在第一次实质答复结束前，把已知的业务目标、范围和待明确事项写进 `docs/proposal/index.html`，未知的标「未知」。

## 5. 七段主流程

段号就是开发者中心左栏的阶段位。进入一段先完整读该段文件，一次只读一份；出口满足后更新阶段状态再进下一段。从 `tasks/` 进来时按入口文件说的段接上，**禁止**机械从 G1 重做。

| 段 | 做什么 | 出口 | 读 |
|---|---|---|---|
| G1 需求确认 | 复述需求；有模型或人工参与的步骤时写分工表；一页确认页确认一次 | 开发者对确认页说「可以」 | [flow/G1-需求确认.md](flow/G1-需求确认.md) |
| G2 核实资产 | 已有工具、FA、场景包、模板、预置件能不能直接用；真调取样；缺口处置 | 确认页每一步都有可用能力或明确处置 | [flow/G2-核实资产.md](flow/G2-核实资产.md) |
| G3 方案编译 | 确认页编译成资产清单、路线草图、表与页面清单 | 编译结果与确认页一致 | [flow/G3-方案编译.md](flow/G3-方案编译.md) |
| G4 能力制作 | 工具集、FA、编排型 TPE、场景包与路线 | 每条 TPE `verify` passed；每条路线冒泡到终态 | [flow/G4-能力制作.md](flow/G4-能力制作.md) |
| G5 数据与应用 | 数据模板、`gen:pages`、页面块、后端通用层 | 本地 `npm run verify` 全绿 | [flow/G5-数据与应用.md](flow/G5-数据与应用.md) |
| G6 预览验收 | 部署预览、必要时真跑一次、开发者在在线预览验收 | 开发者确认预览；未验证项已记录 | [flow/G6-预览验收.md](flow/G6-预览验收.md) |
| G7 上线交付 | 定版、结单门、交付报告、目录发布提示 | 结单门通过；交付报告已写入工单与方案页 | [flow/G7-上线交付.md](flow/G7-上线交付.md) |

**阶段状态怎么写**：`workspace.json` 的 `targets[n].status`、对应 `docs/stages/` 文档 front matter 的 `status`、`WORKSPACE.md` 的 `current_stage` 在同一动作里更新；状态只有 `not_started / in_progress / passed / failed`。阶段显示名以工作区里已有的为准（旧应用可能是旧名），只改状态，不改名。

**平台对象什么时候建**：G1–G3 不建任何平台资产（G2 的能力试用包除外）；G4 建场景包与能力；G5 建 `business_ui` 与数据模板；G6 部署；G7 定版。**禁止**提前建空容器。

## 6. 工具速查

| 要做的事 | 工具与动作 |
|---|---|
| 工单 | `task_manager(action=create / get / insert / complete)` |
| 找可复用资产 | `list_assets(asset_type=…, keyword=…)` → `get_asset(asset_type=…, asset_ids=[…])`；复制用 `clone_asset` |
| 真调一次工具看返回 | `otpe_tool_test(tool_group_id, tool_id, input)` |
| 接入新工具 | `preview_tool_group` → `register_and_refresh_tool_group`；私有包 `file_to_url` → `upload_and_register_tool_group`；授权卡 `create_auth_card / update_auth_card / link_auth_card` |
| 工具集与 FA | `create_toolset`、`online_toolsets`、`create_fast_agent`、`import_skill_package` |
| 编排型 TPE | `otpe_manage(action=preview / create / update / attach / online / bubble / verify)` |
| 场景包与路线 | `scene_package_manage(action=create / get / ensure_draft / update / assemble / bubble / finalize / online)` |
| 数据模板 | `dataset_template_workspace(action=open / connect / bind / create_table / set_relations / inspect / extract / close)` |
| 应用身份与部署 | `business_ui_manage`、`business_ui_manage(action=setup)`、`business_ui_bundle(action=download_template / ship)`；单步兜底 `prepare_upload / complete_upload / deploy / status` |
| 自动化、用户反馈 | `business_ui_automation`、`business_ui_feedback` |
| 真跑与日志 | `manage_goalfymax_project(action=run / wait / status / reply / stop)`，`get_project_execution_logs` |
| 版本 | `list_asset_versions`、`ensure_editable_asset_draft`、`finalize_asset_version_online`、`compare_asset_versions`、`rollback_asset_version`、`get_asset_usage_impact` |
| 工作区云端保存 | `workspace_remote_status / workspace_pull / workspace_push` |
| 平台问题 | `submit_dev_feedback`、`query_dev_feedback` |

用某个工具前先确认它在你当前的工具列表里；找不到就如实说该能力当前不可用，**禁止**虚构平行工具。调用被拒时按返回的提示改，不猜、不自造兼容字段。

**撞到平台问题就报上去**：疑似平台缺陷或需要平台处理的诉求，用 `submit_dev_feedback` 提一条，不必先查清根因，已经绕过去的也照提；同一问题补证据带上 `feedback_id` 追加。提交成功不等于问题已确认或已解决，不能据此放行验收。

## 7. 什么时候读 reference 与长契约

`reference/` 是按需查阅的正本，每份开头写了适用场景：

| 情况 | 读 |
|---|---|
| 分不清对象、执行形态、`*_id` 指什么、版本术语、积分怎么算 | [reference/平台对象速查.md](reference/平台对象速查.md) |
| 工作区三件套、方案页、阶段状态、在线预览、换机接续 | [reference/开发者中心与工作区.md](reference/开发者中心与工作区.md) |
| 脚手架版本闸门、升级迁移、预置件、生成器、verify | [reference/脚手架与预置件.md](reference/脚手架与预置件.md) |
| 写编排脚本、`_output`、失败出口、事件契约、冒泡里的 FA 桩 | [reference/编排脚本.md](reference/编排脚本.md) |
| 路线对象、assemble、中途表单、交付审阅、重入 | [reference/业务路线.md](reference/业务路线.md) |
| 建表、列可编辑性、谁建行、模板版本与迁移 | [reference/数据模板.md](reference/数据模板.md) |
| SDK、必备页面、业务页面、表单与文件纪律 | [reference/前端页面.md](reference/前端页面.md) |
| 部署、定版、修订、回滚、下线、删除、三道门 | [reference/部署与版本.md](reference/部署与版本.md) |
| 外部平台授权、充值 | [reference/授权与充值.md](reference/授权与充值.md) |
| 到点或数据变化自动发起路线 | [reference/自动化.md](reference/自动化.md) |
| 接入新 MCP、私有包、Skill 包、授权卡、工具集上线 | [reference/依赖与MCP接入.md](reference/依赖与MCP接入.md) |
| 报错码怎么处置 | [reference/报错对照.md](reference/报错对照.md) |

长契约只在报错或要做不常见的事时读，按 topic 用 `get_diagnosis_doc(topic=…)`，同一主题一个任务只通读一次：

| 情况 | topic |
|---|---|
| 写第一条编排脚本前 | `otpe_authoring` → `otpe_single` |
| 路线要并行、扇出、中途表单、节点级接管 | `otpe_multi` |
| 工具返回要按字段用、`_output` 报形状错 | `otpe_example_tool` |
| 脚本有文件输入输出 | `otpe_example_file` |
| 有真正可选的步骤或部分成功 | `otpe_example_failure` |
| 交付审阅、Agent 接管 | `otpe_example_handoff` |
| 写第一条脚本、拆 FA、设计数据前看错例 | `counter_examples` |

## 8. 汇报

每完成一步给开发者一句话：做了什么、结果怎样、下一步、需要他决定什么。verify 报告直接贴 `verdict` 与 `failed` 项。上线后给交付报告，格式见 [flow/G7-上线交付.md](flow/G7-上线交付.md)。
