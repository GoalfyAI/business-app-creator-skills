---
name: agenticapp-task-revise
description: 改已上线或已收尾的智能应用：页面、接口、表、路线、提示词、能力，按使用者反馈改，或旧应用迁到新 SDK，例如「加个字段」「这里改一下」「金额要含税」。没上线的应用接着做走五段；只问或只查原因用 agenticapp-task-diagnose。
---
# 修订已上线的应用

开发者只说要改什么，其余你自己接上：修订交出的是一版改过、验过、重新上线的应用，加一份写清「改了什么、正在用的人会看到什么变化」的上线结果。他不用懂修订或工单，不用换入口。修订也走五段，只是每段只做和这次改动有关的部分。

这件事最常见的错有三种：一是把问题当成要改，直接改完上线，他问的事变成了应用的变化；二是直接在上线行上改、或改完不走 ④ ⑤，结果开发者拿到没验过的东西去发布；三是把小改动当成新应用，从头重做需求确认，覆盖掉已有的正确配置和定制。

## 开始前确认

- **他明确要改才开工**。「把第 3 条改成含税」「加一个字段」是要改；「第 3 条金额好像不对？」「这里能改吗？」是在问，只回答，查原因走 `agenticapp-task-diagnose`，不改、不部署、不上线。拿不准按问题处理，答完问一句要不要改。
- **接上这个应用**。同一对话沿用当前应用；新对话里工作目录只有一个应用，或他的话能唯一对应到一个应用，就选定它；分不清时只问是哪个应用，回答前不改任何应用。换了机器先按 `agenticapp-tool-workspace`「云端保存与换机」取回工作区。读阶段文档和上一张工单的记录，不问他走什么流程，不要他提供工单号。
- 有 write 工单（入口「开工」第 1 步）；上一张工单已结单的新建一张，工单说明写明承接自哪张工单。加载 `agenticapp-tool-workspace`，定位应用工程，核对工作区与云端。
- `business_ui_manage(action="get")` 看 `role`：
  - `viewer` 不能修订，转 `agenticapp-task-diagnose`；
  - `editor` 加载 `agenticapp-role-collab`，按它的「编辑协作者改应用」做，起点仍按下面的表；
  - 协作者的草稿基线过期（`baseline_stale=true`、提请或上线返回 `PERSONAL_VERSION_STALE_SOURCE`、站内信通知基线过期），先按 `agenticapp-role-collab`「基线过期的合并」处理。
- 按使用者反馈报告来改的，先按 `agenticapp-task-user-feedback` 校验报告，只改校验返回的 `accepted` 问题。
- 认清是哪条路：看 `frontend/goalfy-app.json` 的 `executor`。要把旧应用迁到新 SDK，或修正路线要接着上一趟改，读 [references/新SDK应用的修订.md](references/新SDK应用的修订.md)。

## 按这个顺序做

1. **看版本**。属主用 `list_asset_versions` 看场景包、应用、模板各自的现役版本，以及有没有搁浅的草稿。协作者的看法按 `agenticapp-role-collab`。
2. **取可编辑草稿**。应用用 `business_ui_manage(action="ensure_draft", change_note=…)`，`change_note` 必须写这次改了什么；场景包用 `scene_package_manage(action="ensure_draft")`；其他资产用 `ensure_editable_asset_draft`。对上线行直接 `update` 会自动派生草稿。之后一律用返回的 `draft_asset_id`。草稿、作废、回滚的规则见 `agenticapp-tool-deploy` 的版本操作。
3. **评估影响**，结论写进阶段文档：
   - 共享资产用 `get_asset_usage_impact` 看谁在用；
   - 改表结构加载 `agenticapp-tool-data-template`，按它改已上线的模板；应用有协作者时还要按 `agenticapp-role-collab` 先打招呼；
   - 改 TPE 的输入输出会波及路线映射和页面，一起列出来；
   - 改挂载（换场景包或模板版本）属于契约变更，同样在这一步评估；
   - 改到的路线还经平台数据集 FA 转手读写应用库的，顺带改成现在的写法（见 `agenticapp-tool-data-template` 的常见错误）。
4. **留下配置差异**。修订前后各用 `compare_asset_versions` 取一次配置差异，留给 ⑤ 写进上线结果。它只比配置、不比效果。
5. **定从哪一段进**，照下表，加载那一段的 Skill 读完再做。这一段之前的段不重做，之后的段只做受影响的部分。
6. **涉及文案、入口或产物时**，加载 `agenticapp-tool-frontend`，按「业务文案」只核受影响的部分；已有正确的配置和定制保留，不用默认词覆盖。
7. **要上线的修订，④ 和 ⑤ 每次都做**：④ 加载 `agenticapp-stage-4-acceptance`，改完部署、直接上线，只验受影响的条目，再加一条完整主流程，照模板交验收报告，他说「别测了」或改动很小也一样；⑤ 的上线结果写配置差异（给后续 Agent 的部分），以及「正在用的人会看到什么变化，已有数据怎么处理」（加载 `agenticapp-stage-5-launch`）。上线后使用者仍用已发布的旧版，发布由开发者定。

## 从哪一段进

| 改什么 | 从哪一段开始，加载 | PRD |
|---|---|---|
| 要的东西变了：业务规则、功能范围、谁来用、每一步谁来做 | ① `agenticapp-stage-1-requirements` | 出差异版，请开发者确认 |
| 换工具或模型、接新能力 | ① `agenticapp-stage-1-requirements`，只核实受影响的步骤 | 出差异版，写清对能不能做和花费的影响，请开发者确认 |
| 做法变了，要开发者重新判断 | ② `agenticapp-stage-2-plan`，只澄清受影响的取舍，更新后确认一次整版 | 不变 |
| 只改做法：脚本、提示词、路线、表结构、页面、后端接口 | ③ `agenticapp-stage-3-build` | 不变；他说的改动就是这次改动的确认，直接开始 |
| 只改文案或样式 | ③ `agenticapp-stage-3-build`，在工作区跑 verify 后直接 ④ | 不出；确认同上 |

**破坏性改动**（删字段、删数据、改表破坏已有数据），不论从哪一段进都先确认：开工前用业务话列出删掉什么、哪些已有数据受影响、正在用的人会看到什么变化，他明确同意才开工。他同意在先，上线在后，看不到差异就上线的改动收不回来。

**PRD 差异版只列五件事**：这次改什么；影响哪些功能；谁来用和每一步谁来做有没有变；费用与用量有没有变；正在用的人会看到什么变化。改动处按 `agenticapp-tool-workspace` 的「方案页」标出。

Studio 宿主下，先读 PRD 和方案当前的确认状态，再决定要不要出新一版，做法按 `agenticapp-host-studio`。

## 这件事要做对的判断

| 判断什么 | 依据 | 判错的表现 |
|---|---|---|
| 从哪一段进 | 上表：改的是「要什么」还是「怎么做」 | 业务规则变了却从 ③ 直接改代码，开发者没确认过新规则；只改文案却重走 ① |
| 改动影响到哪 | 第 3 步的影响面：谁在用这份资产、TPE 输入输出、表结构、挂载 | 只改了一处，用同一份数据或同一个判断的页面和路线没跟着改 |
| 改页面时碰没碰已确认的样子 | `agenticapp-tool-frontend`「确认过的样子是基线」：只改点名的地方，改完逐项核对，几条修改逐条回 | 改 A 时动了 B，确认过的页面又变回去；说改完了，其实只改了其中一条 |
| ④ 测哪些 | 受影响的条目加一条完整主流程 | 只测改动那一条，主流程被带坏没发现 |

## 你可能会这么想 → 实际

| 想法 | 实际 |
|---|---|
| 直接 update 上线行就行 | 会自动派生草稿，之后要用返回的 `draft_asset_id`；按上线行 ID 反读会以为没改上 |
| 开发者按报告采纳了问题，就是同意我提交和上线 | `accepted` 只表示同意处理这个问题；他明确要求按报告执行，才算这次改动确认过，改完部署直接上线，破坏性改动和要的东西变了的仍要确认 |
| 迁到新 SDK 只是改个配置 | 编排要去掉需要运行 Agent 的写法、页面要改成以执行为单位，重新部署并上线，再试用验收（[references/新SDK应用的修订.md](references/新SDK应用的修订.md)） |
| 建应用草稿时 `change_note` 写「更新」 | 写清这次改了什么，它会带给协作者和属主 |

## 记下来

- 工单 checkpoint：这次从哪一段进及理由、影响评估、取到的草稿 `draft_asset_id`、修订前后的配置差异。
- 各段照那一段 Skill 的「记下来」写；阶段文档里写「依据 PRD 第 N 版」，只记这次变化的部分。

## 交棒

进入的那一段做完后按那一段 Skill 的交棒条件往下走，直到 ⑤ 收尾（编辑协作者在报告交出后提请属主上线）。只改文案或样式的，在工作区跑 verify 通过后加载 `agenticapp-stage-4-acceptance`。

## 出问题

| 现象 | 处理 |
|---|---|
| `CHANGE_NOTE_REQUIRED` | 建应用草稿没带变更说明：写清改了什么，带 `change_note` 重调 |
| `PERSONAL_VERSION_STALE_SOURCE`、`BUSINESS_UI_COLLABORATION_*` | `agenticapp-role-collab` |
| 新 SDK 迁移报 `BUSINESS_UI_NO_SCENARIO_PACK` | [references/新SDK应用的修订.md](references/新SDK应用的修订.md)「和修订有关的报错」 |
| 新 SDK 迁移或修正路线报 `APP_VERSION_*`、`EXECUTION_*` | `agenticapp-tool-workflow`「冒泡和执行里可能遇到的错误码」 |
| 改表结构、抽模板被拒 | `agenticapp-tool-data-template` |
| 部署、上线、回滚、作废草稿出错 | `agenticapp-tool-deploy`「常见错误」 |
| 改着改着发现要的东西本身变了 | 回 ①，出 PRD 差异版 |
