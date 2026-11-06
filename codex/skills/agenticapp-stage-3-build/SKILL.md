---
name: agenticapp-stage-3-build
description: 第 ③ 段制作。方案已确认、应用还没做完时加载，包括「开始做吧」「做到哪了」「先给我看看页面」。做完要逐条试用时改用 agenticapp-stage-4-acceptance。
---
# ③ 制作

你按施工单把后台能力、数据和页面做出来。交给开发者的是：每个功能做到哪了（后台、页面、存数据三格）、后台实际跑过的功能各一份「我先跑了一遍」、页面说明、没做成的说明。开发者不用填、也不用确认，只有结果和 ② 的预期差得多时才请他拍板；环境出错、外部服务没钱、平台报错你自己处理。

这一段最常见的错是**进度说做好了，其实没做好**：把桩跑通的冒泡当成实际跑过，方案里的功能漏做，检查不过就绕过去。开发者主要靠进度判断，所以进度里的每一格都要对得上实际。错了的后果：桩跑通只证明管路通、形状对，模型的真实输出没人看过；漏做的功能到 ④ 验收才记「没通过」，要回 ③ 改。

规矩以入口 `agenticapp-creator` 为准，每一步要加载的工具 Skill 写在那一步里。写代码时最容易忘的一条：开发者看得到你调用工具之间的每一句话，这时也用他的语言，只说进展。做不到、要换做法 → 回 `agenticapp-stage-2-plan`；做完 → `agenticapp-stage-4-acceptance`。

## 开始前确认

- ② 交了棒：当前整版方案（含验收条目）已确认，施工单在阶段文档 G3 里。
- 接续时：G4 已 `passed` 的不重做，从 G5 接；要核对的几项读 [references/制作步骤细则.md](references/制作步骤细则.md)「接续时」。
- 从修订进来：按 `agenticapp-tool-deploy` 的「修订、回滚、作废」取可编辑草稿，只改受影响的资产；从哪一步开始改见 `agenticapp-task-revise`。
- 认清新旧：`frontend/goalfy-app.json` 有 `"executor": "launch_agent"` 的是新 SDK 应用，不建场景包，路线和 TPE 挂在 ① 建好的应用占位上。
- 工具参数以工具当前 Schema 为准，下面每步只写做什么。

## 按这个顺序做

每一小步的完整做法读 [references/制作步骤细则.md](references/制作步骤细则.md)。开始前把下面 6 步建成待办（宿主有待办工具就用：Claude Code 的 TodoWrite、Codex 的 update_plan），第 1 步排第一，做完一步勾一步。

1. **先存第一版制作进度**。列出方案里的全部功能，格子按实际状态写（多数是「没开始」）并保存，同时发第一条进度消息，这一条就带完整进度表。这一步之前不建任何资产、不写代码，和 ② 的确认在同一轮里接着做时也一样。做成：方案页 `status` 为 `data-stage="G4"`、`data-state="working"`；Studio 宿主下制作进度读回成功。
2. **后台能力（G4）**，先加载 `agenticapp-tool-workflow`，再按施工单的顺序：
   1. 场景包草稿（新 SDK 应用跳过）。
   2. 接入缺的工具（① 判定要接入时）。加载 `agenticapp-tool-integration`。做成：预览成功后才注册，`tool_group_id` 与 `mcp_id` 已记下。
   3. FA：每个模型步骤一个，模型用 PRD 定的档位。按 `agenticapp-tool-workflow`。做成：`get_asset` 反读的 `model_name` 是 PRD 那一档、`mr_name` 已记下；挂了应用库工具的，`actual_tool_group_ids` 含它。
   4. 工具集：测过后上线并反读。按 `agenticapp-tool-integration`。做成：`get_asset` 反读清单里每个工具集都已上线。
   5. 编排型 TPE：preview → create → online。按 `agenticapp-tool-workflow`。做成：`get_asset(asset_type="tpe")` 反读到脚本和事件契约，`tpe_id` 已记进工单。
   6. 反读自查：读写应用库的路线 online 后反读四项。做成：G4 里这条路线四项都记「有」。
   7. verify：看 `verdict` 改到交棒要求的值。做成：满足下面「交棒」里 verify 那一条。
   8. 路线：`assemble` 出草稿，处理后整份保存。按 `agenticapp-tool-workflow`。做成：`get_asset(asset_type="scenario_package")` 反读到路线和 `business_forms`；新 SDK 应用编排引用的 TPE 都在 `tpe_ids` 里。
   9. 拿真实结果：挑例子、跑、发「我先跑了一遍」，见 [references/我先跑了一遍怎么写.md](references/我先跑了一遍怎么写.md)。做成：不碰应用库的路线冒泡到终态（有模型步骤要带 `full_run`），每条 TPE 用这次的 `run_id` verify 为 `passed`，每个例子六项写全。
3. **数据和页面（G5）**。页面要调用的路线先能跑（每条 TPE verify 通过或只差运行证据）。
   1. 应用身份：在把 `current_stage` 改成 G5 之前建好并回填工作区。加载 `agenticapp-tool-data-template`。做成：执行返回的 `scaffold_bind_command` 后，`app.json` 与 `WORKSPACE.md` 的应用 ID 已回填。
   2. 数据模板：每个应用都要做，至少一张业务表。按 `agenticapp-tool-data-template`。做成：`inspect` 结果对上施工单的表清单，`extract` 给出模板 ID 和整数版本号，挂模板的 `setup` 没有返回 `success=false`。
   3. 数据页：用生成器一条命令生成。加载 `agenticapp-tool-workspace`。做成：`gen:pages` 没有被拒。
   4. 前端页面。加载 `agenticapp-tool-frontend`。做成：`npm --prefix frontend run check` 警告清零。
   5. 后端接口：按 `agenticapp-tool-workspace`。
   6. 外部平台授权、充值（加载 `agenticapp-tool-integration`）和自动化（加载 `agenticapp-tool-automation`）：PRD 列了才做。
   7. 在工作区跑：`check`、`verify` 和前端测试全绿；③ 不部署。
4. **边做边发进度**。什么时候发、怎么写见 [references/制作进度怎么写.md](references/制作进度怎么写.md)，模板见 [assets/进度消息.md](assets/进度消息.md)。发完在同一条回复里接着做。页面做好时告诉开发者演示预览能看了，不等他回话。
5. **偏离方案时按下面的判断处理**，要开发者拍板的停下来问，其余自己改完继续。
6. **发最后一条进度**，写阶段记录，按「交棒」进 ④。

## 这一段要做对的判断

下面八件，每件怎么判、判错是什么表现，读 [references/判断的依据.md](references/判断的依据.md)：

- 结果和 ② 的预期差多少：自己能改的偏差，还是要开发者拍板
- 要换收费工具、换更贵的档，或资料要新发往外部服务
- 做的时候发现做不到
- 报错是应用自己的问题还是平台问题
- 复用还是新建
- 方案里的功能是不是都做了
- 检查不过时守住检查
- 起始件清干净

此外只在入口「五段」的「不多等」列出的情况停下来问。

## 你可能会这么想 → 实际

| 想法 | 实际 |
|---|---|
| 冒泡跑通了，后台算「实际跑过」 | 没有桩才算；FA 是桩的冒泡只算「只用模拟数据试过」，写法见 [references/制作进度怎么写.md](references/制作进度怎么写.md)「进度表」 |
| 读写应用库的路线冒泡跑通，就做好了 | ③ 只标「做好了，等在线预览时实际跑」，④ 真跑后补发「我先跑了一遍」（`agenticapp-tool-workflow`「冒泡与真跑能证明什么」） |
| 例子请开发者挑一下、确认一下 | 例子由你从 ① ② 已有的东西里挑，不请他填也不请他确认 |
| 先建几个资产，有了东西再发第一条进度 | 第一条进度在第一个建资产的动作之前发，开发者从这时起就看得到全部功能的状态 |
| 进度攒到最后和验收报告一起发 | 在做的过程中发，每条单独发，不和 ② 的确认回复或 ④ 的报告合成一条 |
| 先部署一下，让开发者在在线预览里看 | ③ 不部署，他想看页面用演示预览；部署在 ④ 做 |
| 页面做好了，等他看完再往下做 | 告诉他能看了就接着做。他有意见就改，他没回话不是停下的理由 |
| 页面要的数据路线不给，页面先少显示一块 | 改 TPE 的 `output_schema`，或回 ② 改施工单的页面清单 |

## 记下来

工单 checkpoint、阶段文档 G4 与 G5、交付物各写什么，写之前读 [references/记下来写什么.md](references/记下来写什么.md)。

## 交棒

全部满足，用 `business_ui_stage` 写 G4、G5 各一条（G5 带上 `business_ui_id`，写法见 `agenticapp-tool-workspace`「阶段记录」），`workspace.json` 的 G4、G5 标 `passed`，再加载 `agenticapp-stage-4-acceptance`：

- 每个功能的后台、页面、存数据都是「做好了」或「不需要」（后台是三种「做好了」之一），或标明没做成及原因，开发者已就没做成的选过；
- 第一版制作进度在第一个建资产、写代码的动作之前就已保存；③ 的最后一条进度已单独发出；每个后台「做好了，实际跑过」的功能都发过「我先跑了一遍」；
- 每条读写应用库的路线，反读自查四项都是「有」，已记进 G4；
- 每条编排型 TPE 最近一次 `verify` 为 `passed`（带路线冒泡或单条冒泡的 `run_id`）；读写应用库的路线只差运行证据（`needs_bubble`、`failed` 为空），`passed` 由 ④ 真跑补上；
- 每条不碰应用库的路线：当前合同下最近一次冒泡到终态 `success` 的 `run_id` 已记入工单；失败的已修好重跑，或已按 `agenticapp-tool-deploy`「结单」的豁免说明原因；
- `business_ui_id` 已建、数据模板版本已挂到应用、开发工作集已绑定；新 SDK 应用的编排与 `tpe_ids` 已挂到应用草稿（没挂的占位草稿不能部署）；
- 应用根 `npm run verify` 全绿，业务文案已由实际页面和动作使用；
- 累计花费没超过上限，或超出部分开发者已选过。

## 出问题

| 现象 | 处理 |
|---|---|
| 工具报错、校验或冒泡失败、建表被拒、连接串过期 | 查对应工具 Skill 的「常见错误」，改完回本段对应的一步 |
| 冒泡异常长跑，步数或积分一直涨 | 先止损再排查，按 `agenticapp-tool-workflow` |
| 同类事实错误、引用错误或无产物连续两轮 | 停止加字段、不原样重跑，按 `agenticapp-tool-workflow` 重划 FA 与脚本的职责；要改施工单的回 ② |
| 设计做不了（SDK 拿不到的数据、路线不发的事件） | 回 ② 改页面清单，或在第 2 步改路线契约；不静默改设计 |
| 真实结果始终达不到预期，要换做法 | 回 ②：问清变化的取舍，改方案并请开发者确认新的整版 |
| 处理不了的平台问题 | 按入口「报错和平台问题」报，先做不受影响的部分，进度消息写「卡住了」和对开发者的影响 |
