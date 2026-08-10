---
name: scene-creator
description: 通过经过审计的 External MCP 创建、更新、验证并发布 GoalfyMax Workflow 资产及多 Workflow 场景包。当 Codex、Claude Code 或其他编码 Agent 需要把业务流程转换为 Workflow 脚本、发现线上工具契约、安全取样 MCP 返回、编排 workflow_orchestration 或 sa_handoff、按需在真实 Max 项目中验证、诊断失败或维护已有场景包时使用。
---

# 场景包制作

通过 External MCP 创建与 Max 实际执行一致的 Workflow 资产。以线上 MCP 工具 Schema、服务端校验和返回的资产数据为准。禁止虚构资产 ID、工具名、参数、Schema、版本或返回字段。

## 按需加载知识

1. 先读 [External MCP 工具路由](references/external-mcp-tools.md)，再用线上 `tools/list` 核对 12 个工具。
2. 读取服务端契约前，先创建 Workflow 制作工单。
3. 确认任务需要制作 Workflow 后，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_authoring")`。
4. 编写任何 Workflow 脚本前，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_single")`。只有确认场景包需要多个 Workflow 后，才调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_multi")`。
5. 使用特殊原语或契约，或者 Preview、Hub、Runtime 错误需要已知修复模式时，先读一次 `workflow_examples`，再只读取匹配的 `workflow_example_*` topic。

同一工单内不要重复读取相同 topic。MCP Knowledge 是共享 Workflow 契约和示例的完整来源。本 Skill 先于服务端知识加载，因此只重复 `apc_skill`、`_output`、文件、失败、最终契约和验证中的高风险规则；完整规则以 MCP Knowledge 为准，发生冲突时以线上 Schema 和服务端校验为准。

## 执行 External 制作流程

### 1. 创建一个可审计工单

在第一次预览、写入、真实取样、项目运行、下载或审计动作前，调用 `workflow_task_manager(action="create", task_name=..., task_description=...)`。保存返回的 `task_id`，后续所有审计操作都传入该值。

中断后用 `workflow_task_manager(action="get", task_id=<task_id>)` 恢复上下文。资产创建和验证后，用 `workflow_task_manager(action="insert", task_id=<task_id>, entry_type="checkpoint", content=...)` 写入简洁检查点；不要把完整工具输入、供应商输出、凭证或日志复制进工单。

### 2. 检查并复用线上资产

用 `list_assets` 查找候选场景包、Workflow、Toolset、Tool Group、FA 和数据集，用 `get_asset` 读取完整现状。

为每个脚本依赖收集线上调用名、所属资产 ID、input Schema、可见的正式 output Schema、当前版本和 Toolset 依赖。禁止从手册、其他项目或历史对话推断这些信息。

已完成项目中存在可复用业务经验时，用 `list_assets(asset_type="experience", ...)` 和 `get_asset(asset_type="experience"|"experience_page", ...)` 读取。经验数据只读，并继续受当前用户 Hub 权限约束。

### 3. 执行 Battle 并质疑方案

调用 `get_diagnosis_doc(task_id=<task_id>, topic="scene_package_battle")`。CC/Codex 根据返回契约和当前资产证据自行审查，不再启动历史 Beta Battle FastAgent。

创建场景包前，解决业务输入不清、多余 Workflow、Agent 判断位置错误、不安全副作用和交付物缺失问题。只把简洁结论写入工单检查点。

### 4. 选择执行形态并起草运行时 Skill

用制作总契约区分固定阶段和 Agent 判断；每个脚本都应用单 Workflow 契约，只有固定 DAG 才应用多 Workflow 契约。

创建资产前，根据确认过的业务里程碑起草 `apc_skill`，只保留运行时 Agent 必须始终知道的内容：

- 场景包解决什么问题、何时使用；
- 业务里程碑，以及每阶段目标和用户可见产出，不复述脚本步骤；
- 必需业务输入和用户预期输出；
- 哪些判断或授权保留给 Agent 或用户；
- 仅针对未被脚本固化的 Agent 控制工作，保留必要业务规则、系统边界和工具指导；
- 在明确阶段读取哪个可选场景知识文件。

禁止把制作说明、数字资产 ID、实现细节或确定性的 `workflow_orchestration` DAG 写进 `apc_skill`。长业务规则、模板、示例和详细 SOP 放入场景 Skill 文件，并且只有存在明确读取时机时才从 `apc_skill` 索引。

调用一次 `scene_package_manage(action="create", task_id=<task_id>, name=..., description=..., apc_skill=...)` 创建离线草稿，再创建 Workflow。保存 `scene_package_id`。后续配置失败时用 `action="update"` 修复同一场景包，禁止重复创建。

### 5. 只补缺失依赖

优先复用现有依赖。只有缺少或确实需要维护 Toolset、Tool Group、FA、Auth Card、普通自定义 TPE 或 Skill 文件时，才使用 `workflow_dependency_manage`。Auth Card 只使用 `create_auth_card`、`update_auth_card` 和 `link_auth_card`；禁止把返回或提供的凭证明文写入检查点和日志。普通自定义或预定义 TPE 才使用 `create_custom_tpe`，Workflow TPE 始终使用 `workflow_tpe_manage`。

可独立调用的 MCP 工具没有可信正式 output Schema 时：

1. 确认调用只读，或者已经获得相应授权。
2. 用代表性输入调用一次 `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=...)`。
3. 只为下游代码起草最小步骤 `_output`。
4. 换一组新输入，再调用 `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=<新输入>, expected_output_schema=<候选 Schema>)`。
5. 检查点只记录契约结论和资产版本。

未经明确授权，不得取样破坏性、对外发布、凭证变更、金融或其他不可逆操作。FA、`file`、`shell` 和 `send_email` 需要 Max Runtime 上下文，不能用 `test_tool` 测试。

### 6. 交付辅助文件并创建全部 Workflow

External MCP 接收完整内联脚本，不能读取客户端本地 Codex/CC 路径，也不能读取其他 Max 项目中的路径。

Workflow 引用 `ctx.skill_dir` 时，通过同一工单交付每个辅助文件、模板和静态样例：

1. 调用 `workflow_file_upload(action="prepare", task_id=<task_id>, file_name=..., relative_path=..., size_bytes=...)`。
2. 按返回的 HTTP `PUT` 请求上传准确的本地字节。
3. 调用 `workflow_file_upload(action="complete", task_id=<task_id>, file_name=..., relative_path=..., file_key=...)`，收集 `data.skill_file`。
4. 创建或更新 Workflow 时把收集结果作为 `skill_file_urls=[...]` 传入。

已有可信 HTTPS 文件时，使用 `workflow_file_upload(action="from_url", task_id=<task_id>, file_name=..., relative_path=..., source_url=...)`。更新 Workflow 前重新读取现有文件列表，并发送完整目标集合，因为 `skill_file_urls` 会替换该 Workflow 的 Skill 目录。场景知识文件使用同一交接流程，但传给 `scene_package_manage(..., skill_file_urls=[...], skill_files_mode="merge")`；只有 Workflow 辅助文件挂载到对应 `ctx.skill_dir`。

对每个 Workflow：

1. 按单 Workflow 契约起草内联脚本和根对象 input/output Schema。
2. 调用 `workflow_tpe_manage(action="preview", task_id=..., script=..., input_schema=..., output_schema=..., preload_toolset_ids=...)`。
3. 按返回的工具、字段、行、节点或路径修复全部错误，禁止压制校验。
4. Preview 通过后才能调用 `workflow_tpe_manage(action="create", task_id=..., scene_package_id=..., ...)`。
5. 保存返回的 `tpe_id`，后续修复全部使用 `action="update"`。

不得通过拆分或复制 Workflow 绕过可修复的 Preview 错误。每次创建都必须包含根对象 `output_schema`；缺失、非对象或无效 JSON Schema 都是创建错误，即使脚本能够返回值也不例外。

### 7. 保存一个完整的多 Workflow 对象

全部 Workflow ID 创建并挂载后，按多 Workflow 契约构造一个完整对象并调用：

```text
scene_package_manage(
  action="update",
  task_id=<task_id>,
  scene_package_id=<scene_package_id>,
  workflow_orchestration=<完整对象>
)
```

始终执行整对象替换。`delivery.node_id` 指向的节点必须声明节点级 `sa_handoff`：要求运行时 Agent 读取已提交结果，并通过 `message_user(type="result")` 交付面向用户的自然语言结果；Runtime 随后使用 `take_over` 阻止兼容自动交付。严格按当前 Hub Schema 编写 `decision_criteria.resume/stop`。运行时这些条件映射到 `continue_as_planned`、针对所列直接下一节点且通过 Schema 校验的 `revise_and_continue` 补丁，或剩余路径改变时的 `take_over`。不要把这些运行时动作名虚构成新的 orchestration JSON 字段。按 Hub 返回的节点、映射、交付或 `sa_handoff` 错误修复同一完整对象并重新提交。禁止把 DAG 复制进 `apc_skill`，也禁止虚构字段。

### 8. 对每个 Workflow 做 bubble 跑

对每个 Workflow 调用 `workflow_tpe_manage(action="bubble", task_id=..., tpe_id=..., workflow_input=<valid object>)`，保存返回的 `run_id`。继续用同一 action 和 `task_id + run_id` 轮询到终态，再检查 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。

开始 bubble 前，确认直连工具使用已授权的代表性输入；邮件、通知、发布、扣费、远端对象创建和正式业务状态写入只能用 `ctx.dry_run` 抑制对应外部副作用。不得用 `ctx.dry_run` 跳过普通工具、Schema 校验、Workspace pipeline 步骤或 FA 桩值引发的失败。

Bubble 是受信任的 Max 验证运行，不是本地执行。FA 步骤返回 Schema 桩值，不启动真实 FA；普通 MCP 和文件工具真实执行。只有脚本引用 `shell` 时才创建临时服务端沙箱，内部项目/沙箱 ID 和挂载路径不对外返回。把供应商副作用视为真实副作用，涉及破坏或发布时先取得授权。Bubble 和语义验收通过后，对每个 Workflow 分别询问用户是否执行 FA 全真跑并记录决定。用户跳过时继续流程；可选全真跑永远不能替代必做的 bubble 证据。

### 9. 根据契约和轨迹验收每个 Workflow

External 与 Max 制作遵循同一条 `Preview → bubble → 语义验收 → 可选全真跑` 生命周期。两者工具面可以不同，但都通过 Max Runtime 执行并使用同一证据标准。需要完整项目验证时复用检查点中的 `project_id`，不要为每次修复新建项目。

调用 `get_diagnosis_doc(task_id=<task_id>, topic="workflow_verify")`。CC/Codex 根据当前 Workflow 资产、Preview 结果和 bubble 轨迹自行执行语义验收，不再启动历史 Workflow Verify FastAgent。持续修复原 Workflow 并重跑 bubble，直到证据满足契约。

### 10. 验收完整场景包

调用 `get_diagnosis_doc(task_id=<task_id>, topic="scene_package_verify")`，把场景包 Skill、依赖闭包、每个 Workflow 契约、`workflow_orchestration`、交付映射和 Agent handoff 作为一个整体检查。不再启动历史 Scene Package Verify FastAgent。把简洁的 Battle、Workflow 和场景包验收结论写入工单。

### 11. 在归属层修复问题

- 线上工具参数或返回不匹配：重读资产，修复调用或步骤契约。
- Workflow Preview/Runtime 失败：更新原 Workflow。
- Hub orchestration 失败：更新同一个完整 `workflow_orchestration` 对象。
- 运行时工具缺失：核对调用名、Toolset 成员、在线状态和 preload 依赖。
- 输出文件缺失或不可信：检查 TaskAgent 证据，修复文件来源或生成步骤。
- 业务判断不确定：停止强行固化 Workflow，把该阶段还给 Agent。
- 基础设施错误：只有返回错误明确可重试且操作幂等时才重试。

### 12. 发布已验证场景包

发布前重读场景包，确认引用资产存在、每个 Workflow 都有当前 input/output 契约、多 Workflow 场景包已保存一个有效的 orchestration 完整对象且交付节点包含最终 `sa_handoff`、交付文件使用 Workspace 路径、工单中存在简洁验证证据。确认 `apc_skill` 仍对应最终里程碑，列出所有必需业务输入和 Agent/用户判断，不含数字资产 ID 或复制的 DAG，并且为每个上传的场景 Skill 文件提供明确读取时机。

资产变更导致草稿过期时，先调用 `scene_package_manage(action="update", task_id=<task_id>, scene_package_id=<scene_package_id>, apc_skill=...)`。随后调用 `scene_package_manage(action="online", task_id=<task_id>, scene_package_id=<scene_package_id>)` 并重读线上场景包。

### 13. 按需运行一个真实 Max 业务项目

只有用户批准所选场景路径可能执行的每个 Workflow 都做全真验证，或明确要求完整业务项目证据时，才执行本步骤。批准未覆盖完整路径时不得启动项目；记录 `full_validation_skipped` 和剩余 FA、内容、外部副作用盲区，然后继续关闭工单。

获得批准后，在发布完成后调用 `manage_goalfymax_project(action="run", task_id=<task_id>, scenario_package_ids=[...], workflow_input=<object>, ...)`。显式传入 `workflow_input={}` 会触发确定性 C2 场景包；省略该字段会启动普通 Agent 对话。对于编排场景包，Agent 可以收集顶层输入，再通过内部 orchestration 启动工具显式启动同一 C2。与 bubble 不同，这会启动真实 Max 项目及真实 FA/Runtime 行为。

用返回的 `project_id` 执行 `wait` 或 `status`。只有 Max 返回 `needs_input=true` 时才用 `reply` 或 `confirm`；资产更新后需要新尝试时才用 `send`。轮询或小修复不得反复新建项目。

### 14. 全真跑后检查真实日志和交付物

只有步骤 13 实际执行后，才用相同 `task_id` 和 `project_id` 调用 `get_project_execution_logs`：`summary/detail` 用于执行证据，`outputs/download/bundle` 用于真实交付物。临时 FA 文件和内部挂载路径不得出现。项目整体完成不代表目标 Workflow 和交付物通过。跳过全真跑时，禁止虚构 `project_id`、项目结果、日志结果或交付物结果。

### 15. 关闭工单

写入最终检查点，包含资产 ID 和 bubble 结论。检查点必须二选一：记录已批准的真实项目结果与交付摘要，或者记录 `full_validation_skipped`、用户决定和剩余盲区；不得包含凭证或原始日志。调用 `workflow_task_manager(action="complete", task_id=<task_id>)`。跳过全真跑时不得声称存在全真验证证据；缺少必做 bubble 证据或审计落库时不得声称可审计完成。
