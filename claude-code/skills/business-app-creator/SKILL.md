---
name: business-app-creator
description: 制作和维护 GoalfyMax 智能应用（场景包 + 数据模板 + 前后端应用）时使用，涵盖新建、接续、修订、诊断、能力试用和方案讨论。按五段推进：需求确认、方案、制作、试用验收、上线；每段交给开发者一份看得懂的交付物，开发者只确认自己的业务、看得见的东西、取舍和自己手上的事。平台操作引用 MCP 合同，工程实现引用脚手架合同。一次性业务执行或平台概念咨询不使用。[skill-version:v20261022-1f91ec]
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
  - PRD
  - 验收报告
  - 修订
  - 诊断
  - MCP
---
# 智能应用制作

<!-- scaffold-min-required-version:v20260916-8941ec -->

> 本 Skill 把制作分成五段，每段的做法在 `stages/`；其他任务入口在 `tasks/`，交给开发者的东西怎么写在 `design/`，平台细则在 `reference/`。
>
> 平台参数读 MCP 当前 Schema，长合同按需用 `get_diagnosis_doc(topic)`；工程实现读当前应用采用模板的 README 与 package.json。版本与工程入口见 [脚手架与预置件](reference/脚手架与预置件.md)，交付边界见 [部署与版本](reference/部署与版本.md)。

## 0. 红线（不可豁免）

- **禁止**开发反华、涉政违规、违法或敏感内容的需求，识别即停止。
- **禁止**把凭据（数据库连接串、密钥、token、Cookie、密码）写进工单、聊天、代码、提示词或 Skill 文件。
- 花钱、发信、写正式数据、上线、下线、删除、回滚这类外部副作用，**必须**先说清范围，开发者明确同意后执行。PRD「花多少」和「费用与副作用」里列出的动作（含制作中的冒泡 `full_run`、真跑、自动化试跑），开发者确认 PRD 即视为同意，制作过程中照做、在交接消息里报实际花费，不再逐次询问；没列的、累计花费将超过 PRD 写的上限时另行确认。
- **禁止**伪造平台身份：`workflow_runtime_id` 只由服务端生成；`orchestration_id` 只取自场景包里已定义的路线；`business_id` 由调用方在发起时生成、同一实例内不变。
- 零捏造：没读过的契约不猜参数，没跑过的结果不说通过，证据不足就写「未验证」。交给开发者的数字逐条对照原始证据，对不上的删掉或标为「预期」「估算」。
- 共享资产（官方或他人的场景包、FA、工具集）先 `clone_asset` 再改；他人名下的资产不擅自上线、下线或删除。
- **禁止**用 Codex 内置浏览器、Playwright 或任何浏览器打开 GoalfyMax 正式入口、`passport` 登录页、「在线试用」地址或容器地址，也不借用开发者的登录会话。在应用根用 `npm run dev:restart` 起的本机版（只访问本机地址）可以用无头浏览器照验收条目操作；线上页面一律请开发者在开发者中心看，规则见 [reference/开发者中心与工作区.md](reference/开发者中心与工作区.md)「看页面只用开发者中心」。

## 1. 智能应用是什么

智能应用交给一类明确的使用者持续使用：在约定范围内稳定完成一类反复发生的工作，并在下一次使用时复用已确认的信息。它由四样东西组成，交付物就是这四样的版本加验收记录：

| 组成 | 是什么 | 使用者感受到的 |
|---|---|---|
| 前端应用 | 脚手架上的页面：首页（含「最近记录」找回历史运行）、消息中心必备，客户侧不放通用「项目列表」；看板、数据管理、业务发起、项目页与交付审阅按需。只经 SDK 与平台交互 | 看现状、发起一件事、拿结果、改结果、离开再回来 |
| 专属后端 | Express + PG，直连本用户的库 | 编辑自己的数据；看板统计；产出回流入库 |
| 数据模板 | 表、字段、逐列可编辑性（user / agent / system）；使用者首次打开时从模板复制出自己的一份 | 不用每次重复交代；可查看、可纠正 |
| 场景包 | 平台里的能力容器：业务路线、编排型 TPE、工具集与 FastAgent、`apc_skill` | 在必要节点补信息、做选择、审阅结果 |

一个应用里的每一步，都由三类东西之一来做：**脚本**（平台已有的服务和工具，或这次另外写的代码，结果固定、不花模型费）、**模型**（要判断或要写作的步骤，按所选模型计费，越强越贵）、**人**（按角色区分的使用者，在应用里补信息、选择、确认、审阅）。PRD 按这三类画每一步谁来做，写法见 [design/谁来做.md](design/谁来做.md)。

发布单位是 `business_ui`：它挂一个场景包和**必须一份**数据模板（至少一张业务表，平台维护的系统表如 `app_write_requests` 不算）。平台要求每个应用挂的场景包至少有一条路线。对象之间的关系查 [reference/平台对象速查.md](reference/平台对象速查.md)。

## 2. 角色与称谓

| 角色 | 是谁 | 做什么 |
|---|---|---|
| 开发者 | 用本 Skill 制作、维护应用的人；懂业务、一般不懂代码 | 确认 PRD、答判断题、看验收报告说「可以上线」、上线后发布 |
| 需求方 | 提出需求、但不操作 AI 的人；可以就是开发者本人 | 不是同一人时，PRD 和验收报告里「好不好你说了算」的几条都要请需求方看过 |
| 使用者 | 应用上线后使用它的人，可能分几种角色（例如提交、审核、复核） | 只在确认过的入口、表单、审阅节点参与运行 |
| 你 | 执行本 Skill 的 Agent | 调查、核实、制作、验证；准备选择题和推荐答案，**不代替**开发者决定 |
| 运行 Agent | 应用运行时在场景包里执行任务的 Agent | 按已确认的设计执行 |

开发期的确认、授权主语写「开发者」；运行期每一步谁做，主语写使用者的角色名或「运行 Agent」。本 Skill 和 `reference/` 里单独出现的「用户」「最终用户」都指使用者。给开发者看的内容用业务语言，不出现 FA、TPE、工具集、Runtime、资产编号；开发者或需求方自己说过的工具名、平台名（例如「TikHub 小红书工具」）照用。

## 3. 开发者能确认什么

要开发者确认的事只限四类，别的事开发者判断不了，确认了也没有意义：

| 类别 | 例子 |
|---|---|
| 自己的业务 | 要什么、不要什么、怎样算对、有几种人、各看到什么 |
| 看得见的东西 | 放进去什么、拿出来什么、真实数据、结果样例、试用结果 |
| 取舍 | 花多少钱、一周用多少、做不到的怎么替代、慢一点还是少一点 |
| 自己手上的事 | 账号、授权、数据分享、发布给谁 |

- 开发者判断不了的事你自己定，例如用哪个采集工具、选哪个模型、提示词怎么改、表怎么建、要不要迁移。定了以后在交接消息的「刚做完」里用一两句话告诉开发者后果：数据从哪来、每次花多少、结果有什么变化。开发者或需求方点名要用的工具、平台算业务要求，照着去查，查不通再出选择题。
- **禁止**请开发者确认这些：提供凭证文件路径、重新连接开发能力、批准改生产数据库、回归测试要跑多少项、技术遗留清单、环境出错怎么修。它们由你处理，处理不了按 [reference/报错对照.md](reference/报错对照.md) 和第 7 节报平台问题。
- 要开发者拍板的，一律做成选择题：附推荐答案，写清选了会怎样。写法见 [design/选择题与判断题.md](design/选择题与判断题.md)。
- ① 写 PRD 前、② 写方案前，按 [design/按轮问.md](design/按轮问.md) 一轮一轮问：开发者只给一句话也能开始，事实自己查、决定交给开发者，已定的不再问，没回的下一轮接着问；问到没有空着的事，先请开发者确认「我理解的是这些」，回「对」再动笔。在 Studio 里题目用表单发、确认用方案确认卡，见同一文件「在 Studio 里怎么发」。

## 4. 先识别任务

| 开发者要做什么 | 任务 | 先读 |
|---|---|---|
| 把一项业务做成智能应用，或为当前工作台里的具体应用出方案 | 新建 | 从 [stages/1-需求确认.md](stages/1-需求确认.md) 开始 |
| 继续此前没做完的应用 | 接续 | [tasks/接续.md](tasks/接续.md) |
| 改已上线应用的页面、接口、表、路线或能力 | 修订 | [tasks/修订.md](tasks/修订.md) |
| 效果差、报错、数据不对、页面异常 | 诊断 | [tasks/诊断.md](tasks/诊断.md) |
| 验证一个外部能力值不值得做进来 | 能力试用 | [tasks/能力试用.md](tasks/能力试用.md) |
| 纯概念咨询、没指向具体应用、或明确只在聊天里回答 | 仅讨论 | [tasks/仅讨论.md](tasks/仅讨论.md) |
| 查用户反馈、整理反馈报告、按报告改应用 | 用户反馈 | [reference/用户反馈.md](reference/用户反馈.md) |

意图或关键参数缺失时先问；工程上的小取舍按可逆默认做，写进开发记录。

## 5. 开工（每个应用只做一次，接续时核对）

1. **建工单**：`task_manager(action="create", mode="write")`，标题写应用名；之后所有制作、部署、运行工具都带这个 `task_id`。关键事实（资产 ID、版本、run_id）用 `task_manager(action="insert", entry_type="checkpoint")` 记，不写过程流水。工单被拒按 [reference/报错对照.md](reference/报错对照.md) 的「工单闸门」处理。
2. **定位应用工程并核脚手架版本**：在开发者中心分配的 `apps/<应用目录>/` 下工作；读应用根的 `scaffold-release.json`，调用 `business_ui_bundle(action="download_template")` 核版本。规则见 [reference/脚手架与预置件.md](reference/脚手架与预置件.md)。
3. **初始化或接续工作区**：新建用 `npm run scaffold:init -- --environment <环境> --app-name "<应用名>"`，接续时补齐缺失文件用 `npm run scaffold:repair -- --app-name "<应用名>"`；然后 `npm run setup`、`npm run doctor`。三件套、方案页、阶段标记的规则见 [reference/开发者中心与工作区.md](reference/开发者中心与工作区.md)。
4. **读一次开发者偏好**：`dev_preferences(action="pull")`，按需阅读；写过的照做，其余用可逆默认，当前指令优先。

开工后在第一次实质答复结束前，把已知的业务目标、范围和待明确事项写进 `docs/proposal/index.html`，未知的标「未知」。开发者只给了一句话、方向还不清楚（[design/按轮问.md](design/按轮问.md)「从开发者给的东西开始」第三行）时，先不开工：直接发方向那一轮，这一轮不调制作工具、不算实质答复。方向定了，用选定方向起一个暂定应用名（例如「小红书商家诊断报告」），做开工四步，再发下一轮；应用名以后可以改，在 PRD 里定稿。

## 6. 五段

| 段 | 交给开发者 | 开发者要做的 | 包含的工作区阶段 | 读 |
|---|---|---|---|---|
| ① 需求确认 | PRD：要什么、不要什么、谁来用、每一步谁来做、能不能做（已真查真调）、做不到的怎么替代、花多少和用多少 | 写 PRD 前按轮答问题（一句话起步也行）；看懂 PRD、批注、补账号授权，回「确认这一版」 | G1、G2 | [stages/1-需求确认.md](stages/1-需求确认.md) |
| ② 方案 | 每个功能完成什么业务、怎么完成，每个功能一道判断题，验收条目定稿 | 先按轮答做法上的取舍题；再逐题答「对 / 不对」，确认验收条目 | G3 | [stages/2-方案.md](stages/2-方案.md) |
| ③ 制作 | 每个功能做到哪了（后台、页面、存数据）、后台做好的你挑例子先跑一遍的结果、页面说明 | 看；只在三种情况下拍板 | G4、G5 | [stages/3-制作.md](stages/3-制作.md) |
| ④ 试用验收 | 验收报告：每条验收条目你怎么验的、结果，「好不好你说了算」的几条附实际结果，「我试不了的」几条 | 看报告，说「可以上线」或哪一条还要改 | G6 | [stages/4-试用验收.md](stages/4-试用验收.md) |
| ⑤ 上线 | 上线结果：正式版里你跑一次的结果、实际花费、开发者要做的 | 试「我试不了的」几条、发布、分享 | G7 | [stages/5-上线.md](stages/5-上线.md) |

守住这几条：

- **按段推进，交棒有条件**：进入一段前先完整读它的文件；每段的交棒条件写在段文件末尾，满足了才进下一段（① 开发者回「确认这一版」，② 判断题都答「对」，③ 能部署，④ 开发者说「可以上线」）；退回时回到写明的那一段，只改受影响的部分：② 要的东西变了、③ 发现做不到、④ 要的东西本身不对回 ①，③ 结果始终达不到预期回 ②，④ 结果不对回 ③。新建和改已上线的应用都走五段；改已上线的应用时每段只做和改动有关的部分，④ 和 ⑤ 每次都做（见 [tasks/修订.md](tasks/修订.md)）。
- **顺序按依赖走**：后一步要用前一步的产出（路线 ID、`business_ui_id`、数据模板）时，先把前一步做完；平台对象用到时再建，**禁止**提前建空容器；① ② 只查不建（能力试用包除外）。
- **只靠交付物接力**：每段的交付物写进方案页和阶段文档，内容要完整到另一个 Agent 只读这些交付物就能接着做下一段，不依赖聊天记录。阶段文档只用 `docs/stages/` 里已生成的七份，一个工作区阶段一份，不另建文件：② 的施工单、业务说明、判断题和回答、验收条目、费用复核都写进 G3 那一份。PRD 的正本在方案页；确认版全文只在 G1 阶段文档存一次，之后各段写「依据 PRD 第 N 版」并只记和 PRD 不一样的地方，不再复制全文。
- **做不到的尽早说**：在 ① 就能查出来的做不到（授权接不上、平台没有这个工具、时间达不到），必须在 ① 的 PRD 里写明并给替代选择题，**禁止**拖到后面的段才说。
- **每次交接说四件事**：刚做完、下一步、要你做的、花了多少。每段结束和 ③ 的每次进度更新都发一条，写法见 [design/交接消息.md](design/交接消息.md)。
- **中间不设多余的等待**：② 的判断题答完后，一路做到 ④ 交出验收报告，进度写进方案页和交接消息，开发者想看随时看。只在这些时候停下来问开发者：③ 写明的三种拍板情况；缺开发者本人才能给的东西（授权、密钥、业务事实）；要做 PRD 没列的外部副作用；你自己确实推进不下去。
- **上线要开发者开口**：上线前必须有 ④ 的验收报告，每条验收条目都有结论，开发者看过报告明确说「可以上线」，改动再小也一样。验收由你做，开发者不逐条试；你验不了的列为「我试不了的」，上线后请开发者在正式版里试。到点或有新记录时自动开始的那一步，④ 先用冒泡验结果，真的自动开始在 ⑤ 上线后验（见 [stages/4-试用验收.md](stages/4-试用验收.md)）。

**阶段标记怎么写**：工作区的 `workspace.json` 仍是 G1–G7 七项，`doctor` 按它校验。五段和七项的对应见上表：进入一段时把它包含的第一项标 `in_progress`；段内每完成一项标 `passed`，失败标 `failed`；交棒时这一段包含的各项都应是 `passed`，没做的保持 `not_started` 并在阶段文档写一句原因。`workspace.json` 的 `status`、`docs/stages/` 对应文档 front matter 的 `status`、`WORKSPACE.md` 的 `current_stage` 在同一动作里更新，`current_stage` 指向正在做的那一项。阶段显示名以工作区里已有的为准，只改状态，不改名。

## 7. 工具速查

| 要做的事 | 工具与动作 |
|---|---|
| 工单 | `task_manager(action=create / get / insert / complete)` |
| 找可复用资产 | `list_assets(asset_type=…, keyword=…)` → `get_asset(asset_type=…, asset_ids=[…])`；复制用 `clone_asset` |
| 真调一次工具看返回 | `otpe_tool_test(tool_group_id, tool_id, input)` |
| 接入新工具 | `preview_tool_group` → `register_and_refresh_tool_group`；私有包 `file_to_url` → `upload_and_register_tool_group`；授权卡 `create_auth_card / update_auth_card / link_auth_card` |
| 工具集与 FA | `create_toolset`、`online_toolsets`、`create_fast_agent`（`model_name` 与 `model_selection_mode` 按 PRD 的模型选择填）、`import_skill_package` |
| 编排型 TPE | `otpe_manage(action=preview / create / update / attach / online / bubble / verify)` |
| 场景包与路线 | `scene_package_manage(action=create / get / ensure_draft / update / assemble / bubble / finalize / online)` |
| 数据模板 | `dataset_template_workspace(action=open / connect / bind / create_table / set_relations / inspect / extract / close)` |
| 应用身份与部署 | `business_ui_manage`、`business_ui_manage(action=setup)`、`business_ui_bundle(action=download_template / ship)`；单步兜底 `prepare_upload / complete_upload / deploy / status` |
| 自动化、用户反馈 | `business_ui_automation`、`business_ui_feedback` |
| 真跑与日志 | `manage_goalfymax_project(action=run / wait / status / reply / stop)`，`get_project_execution_logs` |
| 版本 | `list_asset_versions`、`ensure_editable_asset_draft`、`finalize_asset_version_online`、`compare_asset_versions`、`rollback_asset_version`、`get_asset_usage_impact` |
| 工作区云端保存 | `workspace_remote_status / workspace_pull / workspace_push` |
| 平台问题 | `submit_dev_feedback`、`query_dev_feedback` |
| 看页面效果 | 开发者看：开发者中心「演示预览」「在线试用」；你自己查：`npm --prefix frontend run check`、脚手架本地布局回归、本机版上用无头浏览器照条目操作（只访问本机地址，不开浏览器访问线上地址） |

用某个工具前先确认它在你当前的工具列表里；找不到就如实说该能力当前不可用，**禁止**虚构平行工具。调用被拒时按返回的提示改，不猜、不自造兼容字段。

**平台问题按阻塞程度报**：先按 [reference/报错对照.md](reference/报错对照.md) 处理；应用自己的脚本、页面、数据格式、提示词问题自己改，不提交。`submit_dev_feedback` 新建时必填 `blocking` 与 `attribution`：
- **阻塞**（`blocking="blocked"`）：按指引处理后仍走不下去、没有可行绕法，立即提交，附报错原文和 `project_id` / `run_id`；
- **不阻塞**（`worked_around` 已绕过、`request` 功能诉求）：不即时提交，记进开发记录，⑤ 上线或本次会话结束时汇总成一条提交；
- 新建前先 `query_dev_feedback` 查本人未关闭的反馈，同一问题带 `feedback_id` 追加，不重复新建。
提交成功不等于问题已确认或已解决，不能据此放行验收。平台问题挡住进度时，交接消息里告诉开发者「卡在哪、谁在处理、对你的影响」，不请开发者去修。阻塞的平台问题没人修时按这个顺序升级：
1. 提交后先做不受它影响的部分，交接消息开头写「卡住了」。
2. 每次继续工作时用 `query_dev_feedback` 看处理进展；有回复按回复做。
3. 提交满 1 个工作日仍没有处理人回复，或回复了但给不出修复时间：给开发者发一道选择题，只问开发者能拍板的事。选项从这几种里挑能成立的：
   - 等平台修：写清这期间哪些功能做不了、预计影响哪一段；
   - 换做法绕开：写清和 PRD 比少了什么、多花多少（换做法会改「要什么」的，退回 ①）；
   - 这次先不做受影响的功能；
   - 请开发者把反馈编号转给平台负责人催办：这是开发者自己手上的事，选项里附上反馈编号和一句问题说明，不附报错原文。
4. 开发者选了以后照做，记进阶段文档。

**禁止**为了解开卡点请开发者授权你改生产库、平台库，或改别人（包括使用者）的安装记录和数据；这类修复只能由平台方做。
开发者的阶段评分（仅在 Codex 中）也用 `submit_dev_feedback` 回传，按 [design/阶段评分.md](design/阶段评分.md) 写，不受上面「不即时提交、汇总成一条」的限制。

## 8. 什么时候读 reference 与长契约

`reference/` 是按需查阅的正本，每份开头写了适用场景。reference 里的「G1」…「G7」指工作区阶段，对应关系见第 6 节的表；「确认页」指 ① 的 PRD，「分工表」指 PRD 的「每一步谁来做」：

| 情况 | 读 |
|---|---|
| 分不清对象、执行形态、`*_id` 指什么、版本术语、积分怎么算 | [reference/平台对象速查.md](reference/平台对象速查.md) |
| 工作区三件套、方案页、阶段标记、演示预览为空、「在线试用」、换机接续 | [reference/开发者中心与工作区.md](reference/开发者中心与工作区.md) |
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
