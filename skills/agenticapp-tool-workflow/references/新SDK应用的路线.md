# 新 SDK 应用的路线

应用工程 `frontend/goalfy-app.json` 写了 `"executor": "launch_agent"` 时读。这里只写路线和编排脚本与旧应用不同的地方，其余照本 Skill 各节做；部署、实际跑、结单的差别见 `agenticapp-tool-deploy`。

要点：不建场景包，路线和 TPE 挂在应用版本上；编排不能有需要运行 Agent 的写法（`agent_gate`、`sa_handoff`）；`assemble`、保存、冒泡改传 `business_ui_id`；修正路线读 `ctx.previous_delivery`。

新 SDK 应用的一次运行叫「执行」，标识是 `business_id`（`BIZ-…`，**服务端生成**，调用方不自填）。执行里没有运行 Agent（助手），没有对话；每个使用者实例一个隐藏项目，多次执行在里面并行。

## 路线挂在应用版本上

| 环节 | 旧应用 | 新 SDK 应用 |
|---|---|---|
| 路线和 TPE 挂在哪 | 场景包 | 应用版本：`workflow_orchestration`（格式与场景包里的完全相同）+ `tpe_ids`；不建场景包 |
| 保存路线 | `scene_package_manage(action="update", workflow_orchestration)` | `business_ui_manage(action="update", business_ui_id, workflow_orchestration, tpe_ids)`；两者都是**整体替换**，编排里引用的每个 TPE 都要在 `tpe_ids` 里（漏了报 `references unmounted tpe_id`）；`tpe_ids` 写 TPE 资源组 ID 加具体版本号，不要写某个版本行的 ID（写错时部署会一直停在构建中）；路线实际跑哪一版看节点的 `workflow_ref.tpe_id`，换 TPE 版本时一起改，只改 `tpe_ids` 不报错但仍跑旧版本 |
| 节点能用的工具 | 节点只用它的 TPE 自己挂的工具集（加上 FastAgent 自己的工具）；场景包工具箱是给主控 Agent 用的 | 相同：节点脚本调用的工具要挂在该节点 TPE 上（`update_asset_relations(asset_type="tpe", asset_id, add_toolset_ids)`）；没有主控 Agent，场景包工具箱不再需要。挂在别处时运行报 `invalid tool call name` |
| 组装路线 | `assemble` 传 `scene_package_id` | `scene_package_manage(action="assemble", business_ui_id, tpe_ids, orchestration_id, …)`：并入应用版本原有路线与 TPE，返回的 `workflow_orchestration` 与 `tpe_ids` 原样交给上一行保存 |
| 路线冒泡 | `scene_package_manage(action="bubble", scene_package_id, …)` | 传应用家族 `business_ui_id` 代替 `scene_package_id`，对你最新的草稿发起一次预览执行；`run_id` 就是 `business_id`（`BIZ-` 开头），verify 也用它；交付审阅用 `run_id + formdata={"action_key": …}` 回填；不接受 `review_action_key`、`workspace_files`；止损用 `action="cancel", run_id` |
| 查轨迹 | `get_project_execution_logs(action="workflow_trace", project_id)` | 再带上 `business_id`，只看这一次执行（一个隐藏项目里有多次执行） |
| 表单展示定义 | 场景 Skill 文件 `forms/<form_id>.json` | 前端工程 `frontend/schema/packs/<pack>/forms/` 与 `orchestrations/`，构建时收集；`goalfy-app.json` 的 `packs` 列出用到的目录 |

改过编排后要重新部署一次再上线（`agenticapp-tool-deploy`「上线」）；发布由开发者在上线之后自己做。

## 编排不能用需要运行 Agent 的写法

新 SDK 应用没有运行 Agent 接手，Hub 保存时拒收（400，`workflow orchestration invalid` 带具体位置），改编排即可：

- **禁止**交付审阅 `review.type = "agent_gate"`，**禁止**审阅动作 `kind = "agent_gate"`（交由 Agent 处理），**禁止**节点 `sa_handoff`。
- 审阅只用 `user_gate`：停下来等使用者（`message_type: "ask"`），或直接交付（`message_type: "result"`）。动作只在 `complete_business`、`fail_business`、`start_orchestration` 里选。
- 结果好不好由使用者审阅，平台不替你判断。能用规则判断的写进 TPE：输出校验、`business_gate`。脚本抛错（`business_gate`）是新 SDK 应用唯一的业务停止写法：返回阻断状态只结束本节点，下游照常派发。
- 自动化路线同样只能 `user_gate`（`agenticapp-tool-automation`「收尾方式」）。

## 修正上次交付

使用者审阅不满意、要在上一趟基础上改时：

1. 审阅加一个 `start_orchestration` 动作，指向修正路线。要使用者写修改意见时，不声明 `target_input_mapping`，跳转后展示修正路线的入口表单，表单里放反馈字段；也可以在审阅页面上直接带反馈字段：回复审阅时 `formdata` 里 `action_key` 以外的字段都算反馈。
2. 修正路线的脚本从 `ctx.previous_delivery` 读上一趟：`previous_runtime_id`、`file_paths`（上一趟交付文件路径）、`action_key`、`feedback`、`summary`（交付内容摘要，最多 2000 字，`summary_truncated` 标是否截断）。要全文就读 `file_paths` 里的文件，在它基础上改，**禁止**从头重做。第一趟时它是 `None`。
3. 交付文件在同一使用者的隐藏项目里，按普通 workspace 路径读；要随本次交付的文件照常复制进本节点 `ctx.output_dir`。

## 编排脚本的额外约定

- 中间文件写在 `ctx.process_dir` 下：同一隐藏项目里多次执行并行，写到固定路径会互相覆盖。
- 平台不自动重跑失败节点；派发超时、派发中断也判失败，等使用者点重试。重试会重跑失败节点的全部步骤：含外部发送（发信、发消息、下单）的步骤在 TPE 描述里写明会不会重复发送，用幂等键或先查后发防重复。幂等键由三段拼成：`ctx.business_id`（本次执行编号，重试时不变）、本步标识（脚本里写死的步骤名或消息类型，同一应用内不重复）、本步要发送的对象。缺了本步标识，同一次执行里两步给同一个人发不同消息（先「请审批」后「已通过」）时，第二条会被当成重复跳过。同一步里给同一对象发多条（例如逐条提醒同一负责人处理 3 张逾期单）时，再拼上这条消息对应的业务记录编号（如订单号），否则后几条会被当成重复跳过。修正路线与上一趟同属一次执行，再拼上 `ctx.previous_delivery` 的 `previous_runtime_id`。单条冒泡里 `ctx.business_id` 是 `None`，幂等键写在 `if not ctx.dry_run:` 里拼；旧应用里它也是 `None`，不能用它作幂等键。
- 多个执行可能同时改同一条业务数据，平台只保证同一执行内部串行。会冲突的写库用数据集唯一约束或幂等键兜住；不同执行的 `ctx.business_id` 不同，跨执行的冲突不能只靠它。
- 数据只来自应用自身的实例数据（数据模板）和官方、公开数据集；**禁止**依赖开发者个人的普通数据集，使用者运行时没有权限。
- 执行路径优先读写数据集，少调应用后端：应用后端无人访问时会休眠，冷启动会拖慢执行。

## 冒泡和执行里可能遇到的错误码

| 错误码 | 意思 | 怎么做 |
|---|---|---|
| `APP_VERSION_NOT_LAUNCH_AGENT` | 按新路发起，但该版本不是新 SDK 部署 | 核对 `goalfy-app.json` 的 `executor` 与部署记录；旧应用按原做法传场景包 |
| `APP_VERSION_OUTDATED` | 页面版本落后，或执行属于旧版本（看 `details.reason`） | 页面让使用者刷新；旧版本的执行不能再回复，重新发起 |
| `EXECUTION_LIMIT_REACHED` | 运行中的执行已达上限 | 等已有执行结束，或取消不需要的再发起 |
| `EXECUTION_START_DISABLED` | 平台暂停了新路发起 | 不重试，告诉开发者；已有执行不受影响 |
| `EXECUTION_NOT_RETRYABLE` | 重试了不可重试的执行 | 看执行失败原因，修好后重新发起 |
| `EXECUTION_ALREADY_STARTED` | 同一提交号带了不同输入 | 换新的 `idempotency_key` / 提交号 |
| `EXECUTION_STATE_LIMIT` | 执行的状态记录超出上限 | 减少同一执行里的重试、修正次数，改成新开执行 |
| `WORKFLOW_INTERACTION_REJECTED` | 回复的表单已被处理、不可回答或执行已结束 | 重新 `status` 取当前待答表单 |
