---
name: scene-creator
description: 当用户需要把业务流程制作成可在 GoalfyMax 直接使用的场景包，或需要创建、更新、验证和发布单 Workflow 或多 Workflow 资产时使用。通过经过审计的 scene-creator 外部 MCP，完成需求澄清、线上资产复用、工具契约发现与真实取样、依赖准备、脚本及输入输出 Schema 编写、辅助文件交付、场景编排、预览、bubble 验证、可选全真项目验证、日志与交付物检查、问题修复和最终发布；也适用于根据真实项目执行日志复盘，维护、诊断和迭代已有场景包。
---

# 场景包制作

通过外部 MCP 创建与 Max 实际执行一致的 Workflow 资产。以线上 MCP 工具 Schema、服务端校验和返回的资产数据为准。禁止虚构资产 ID、工具名、参数、Schema、版本或返回字段。

## 先建立场景包认知

每个新的制作、诊断或优化任务开始时，先完整读取一次 [场景包核心模型](references/场景包核心模型.md)。该文件定义场景包是什么、各类资产如何协作、信息应该放在哪一层，以及何时使用 Workflow、普通任务点或 FastAgent。未完成这一步前，不得给出架构方案、创建资产或把用户需求直接翻译成工具调用。

不要把 Max 内部“场景包助手”的整份系统提示词复制进本 Skill。内部状态机、交互协议、Max 专属工具和运行环境只属于 Max；外部 Agent 只继承其中稳定的领域模型和设计方法，并严格使用当前外部 MCP 暴露的 12 个工具。

## 加载制作契约

1. 读完核心模型后，再读 [外部 MCP 工具路由](references/external-mcp-tools.md)，并用线上 `tools/list` 核对 12 个工具。
2. 读取服务端契约前，先创建 Workflow 制作工单。
3. 确认任务需要制作 Workflow 后，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_authoring")`。
4. 编写任何 Workflow 脚本前，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_single")`。只有确认场景包需要多个 Workflow 后，才调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_multi")`。
5. 使用特殊原语或契约，或者预览、Hub、运行时错误需要已知修复模式时，先读一次 `workflow_examples`，再只读取匹配的 `workflow_example_*` topic。
6. 方案创建前读取 [方案挑战检查清单](references/方案挑战检查清单.md)；每条 Workflow 冒泡后读取 [Workflow 验收检查清单](references/Workflow验收检查清单.md)；发布前读取 [场景包验收检查清单](references/场景包验收检查清单.md)。三份检查清单承接 Max 内 Battle/Verify FA 的审查职责，由外部 Agent 自行执行，不调用或虚构不存在的 FA。

同一工单内不要重复读取相同 topic。MCP 知识库是共享 Workflow 契约和正反例的完整来源；本 Skill 内三份检查清单是外部制作入口的方案挑战与验收执行提示。发生冲突时以线上 Schema、Preview、Hub Validator 和 Max Runtime 为准。

## 判断任务模式和授权边界

在创建工单、查询资产或提出方案前，先完成意图路由。模式决定证据来源、允许的写操作和交付物：

| 用户表达或已有上下文 | 模式 | 首要动作 |
|---|---|---|
| “创建场景包”“把这套流程固化”“基于项目/经验做一个场景包” | 创建模式 | 提炼业务场景、里程碑、输入、产出和授权边界 |
| “看看这个场景包有什么问题”“为什么效果不好”“检查配置” | 诊断模式 | 只读获取目标场景包全貌，沿真实引用关系逐层诊断 |
| “分析这个项目的执行日志”且目的是沉淀或改进场景能力 | 诊断模式 | 从真实项目执行证据反推瓶颈，再关联目标场景包或待建方案 |
| “修复/优化/更新这个场景包” | 优化模式 | 先诊断并明确修改范围，再更新原资产和受影响链路 |
| 已有 `task_id`，用户说“继续”或补充上一轮信息 | 续作模式 | 恢复工单、资产状态和最近有效检查点 |
| 只要求创建或修改某条 Workflow，目标和输入输出明确 | Workflow 资产任务 | 保持用户范围，不擅自扩展成新场景包 |
| 无法判断是创建、诊断、优化还是普通业务执行 | 未明确 | 只询问模式或目标，不启动工单 |

创建完成后的试运行暴露问题时，自然转入诊断或优化；诊断发现必须补建资产时，在用户授权的修复范围内进入创建。模式转换不代表新建工单或重建场景包，优先沿用同一工单和原资产。

### 区分信息缺口

不要把所有未知都变成用户问题：

| 缺口 | 例子 | 处理 |
|---|---|---|
| **意图缺失** | “帮我弄一下”“做个东西” | 询问要创建、诊断还是优化，以及最终业务目标 |
| **关键业务参数缺失** | 创建但没有业务场景；诊断但没有目标场景包或项目 | 只询问无法从上下文或线上资产获得的必要信息，得到后再启动 |
| **知识缺失** | 用户不知道需要哪些工具、资产或 Workflow | 不反问用户；读取核心模型、搜索线上资产和服务端契约后自行设计 |
| **可选偏好缺失** | 未指定命名、Focus/泛化倾向或是否需要额外报告 | 采用保守且可逆的默认值，并在方案中说明 |
| **授权缺失** | 对外发布、收费、写正式业务状态、删除或替换重要资产 | 在真正执行该动作前单独请求授权，不用它阻塞前面的只读分析和方案设计 |

### 收集最小充分上下文

按需从对话、已选资料、线上资产和工单中提取以下信息，不要一次性把整张问卷抛给用户：

- **对象**：新场景包、已有场景包、某条 Workflow，还是一个参考项目；
- **业务目标**：谁在什么情况下使用，成功结果是什么；
- **业务里程碑**：关键阶段及其依赖；
- **输入与产出**：启动前必须提供什么，最终交付什么；
- **参考证据**：真实项目、经验体、文件、已有资产或失败日志；
- **权限和副作用**：哪些动作可以自主完成，哪些必须确认；
- **验收标准**：用户怎样判断场景包真的变好或可以使用。

已有信息不要重复询问。一次只问最影响下一步的一至三个问题；用户只给业务语言时，由外部 Agent 负责翻译成资产方案，不要求用户理解 Toolset、FastAgent、TPE、Schema 或资产 ID。

## 执行外部制作流程

### 1. 创建一个可审计工单

在第一次预览、写入、真实取样、项目运行、下载或审计动作前，调用 `workflow_task_manager(action="create", task_name=..., task_description=...)`。`task_description` 应写明当前模式、业务目标、预期交付物和验收边界。保存返回的 `task_id`，后续所有审计操作都传入该值。

中断后用 `workflow_task_manager(action="get", task_id=<task_id>)` 恢复上下文。资产创建和验证后，用 `workflow_task_manager(action="insert", task_id=<task_id>, entry_type="checkpoint", content=...)` 写入简洁检查点；不要把完整工具输入、供应商输出、凭证或日志复制进工单。

### 2. 检查并复用线上资产

用 `list_assets` 查找候选场景包、Workflow、Toolset、Tool Group、FA 和数据集，用 `get_asset` 读取完整现状。

创建模式先寻找可复用资产再决定新建；诊断和优化模式先读取目标场景包全貌，再沿真实引用关系下钻，不能跳过上层结构直接凭某个子资产下结论。用户提供参考项目时，真实项目日志是业务流程和瓶颈的主要证据，不得只看场景包文案。

为每个脚本依赖收集线上调用名、所属资产 ID、input Schema、可见的正式 output Schema、当前版本和 Toolset 依赖。禁止从手册、其他项目或历史对话推断这些信息。

已完成项目中存在可复用业务经验时，用 `list_assets(asset_type="experience", ...)` 和 `get_asset(asset_type="experience"|"experience_page", ...)` 读取。经验数据只读，并继续受当前用户 Hub 权限约束。

### 3. 执行方案挑战并质疑方案

读取 [方案挑战检查清单](references/方案挑战检查清单.md)。CC/Codex 根据清单和当前资产证据自行审查，不启动或假设存在方案挑战 FastAgent。

创建场景包前，先形成一份业务蓝图：目标用户和触发场景、业务里程碑、每阶段输入与用户可见产出、需要 Agent/用户判断的边界、能力覆盖与缺口、验收证据。再解决业务输入不清、多余 Workflow、Agent 判断位置错误、不安全副作用和交付物缺失问题。面向用户使用业务语言展示蓝图，不展示资产 ID、参数名或技术调用链；工单中只写简洁结论。

### 4. 选择执行形态并起草运行时 Skill

按核心模型先决定哪些业务阶段应由场景 Skill、普通任务点、FastAgent 或 Workflow 承担，再用制作总契约区分固定阶段和 Agent 判断。每个脚本都应用单 Workflow 契约，只有固定 DAG 才应用多 Workflow 契约。不得因为外部 MCP 以 Workflow 制作为主，就把所有场景强行改造成 Workflow。

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

未经明确授权，不得取样破坏性、对外发布、凭证变更、金融或其他不可逆操作。FA、`file`、`shell` 和 `send_email` 需要 Max 运行时上下文，不能用 `test_tool` 测试。

任何 Workflow create 前都必须完成依赖 Toolset 上线硬门：

1. 根据脚本确定完整 `preload_toolset_ids`，用 `get_asset(asset_type="toolset")` 检查成员、契约和 `is_online`。
2. 对本任务新建的 Toolset，先验证关联完整；其中可独立安全调用的 MCP 工具完成上述 `test_tool` 取样和复验。
3. 无 FAIL 后调用 `workflow_dependency_manage(action="online_toolsets", task_id=<task_id>, toolset_ids=[...])`，再用 `get_asset` 反读确认每个 Toolset 的 `is_online=true`。
4. 任一依赖仍离线就阻断 Workflow create。对任务开始前已存在的离线 Toolset，告知用户并等待处理，不擅自上线。

### 6. 交付辅助文件并创建全部 Workflow

外部 MCP 接收完整内联脚本，不能读取客户端本地 Codex/CC 路径，也不能读取其他 Max 项目中的路径。

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
4. 预览通过后，再次确认本 Workflow 的所有 `preload_toolset_ids` 已通过上线硬门。
5. 只有依赖全部 `is_online=true` 才能调用 `workflow_tpe_manage(action="create", task_id=..., scene_package_id=..., ...)`。
6. 保存返回的 `tpe_id`，后续修复全部使用 `action="update"`。

不得通过拆分或复制 Workflow 绕过可修复的预览错误。每次创建都必须包含根对象 `output_schema`；缺失、非对象或无效 JSON Schema 都是创建错误，即使脚本能够返回值也不例外。

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

始终执行整对象替换。`delivery.node_id` 指向的节点必须声明节点级 `sa_handoff`：要求运行时 Agent 读取已提交结果，并通过 `message_user(type="result")` 交付面向用户的自然语言结果；运行时随后使用 `take_over` 阻止兼容自动交付。严格按当前 Hub Schema 编写 `decision_criteria.resume/stop`；这两个名称只是制作期判断条件字段，不是运行时 action。运行时只有 `continue_as_planned`、对紧邻待执行节点提交并通过 Schema 校验的 `revise_and_continue`、以及接管剩余流程的 `take_over` 三种 action，不存在名为 `resume` 或 `stop` 的 action。不要把运行时 action 虚构成新的 orchestration JSON 字段。按 Hub 返回的节点、映射、交付或 `sa_handoff` 错误修复同一完整对象并重新提交。禁止把 DAG 复制进 `apc_skill`，也禁止虚构字段。

### 8. 对每个 Workflow 做 bubble 跑

对每个 Workflow 调用 `workflow_tpe_manage(action="bubble", task_id=..., tpe_id=..., workflow_input=<valid object>)`，保存返回的 `run_id`。继续用同一 action 和 `task_id + run_id` 轮询到终态，再检查 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。

开始 bubble 前，确认直连工具使用已授权的代表性输入；邮件、通知、发布、扣费、远端对象创建和正式业务状态写入只能用 `ctx.dry_run` 抑制对应外部副作用。不得用 `ctx.dry_run` 跳过普通工具、Schema 校验、Workspace pipeline 步骤或 FA 桩值引发的失败。

`bubble` 是受信任的 Max 验证运行，不是本地执行。FA 步骤返回 Schema 桩值，不启动真实 FA；普通 MCP 和文件工具真实执行。只有脚本引用 `shell` 时才创建临时服务端沙箱，内部项目/沙箱 ID 和挂载路径不对外返回。把供应商副作用视为真实副作用，涉及破坏或发布时先取得授权。可选全真跑永远不能替代必做的 `bubble` 证据。

### 9. 根据契约和轨迹验收每个 Workflow

外部制作与 Max 制作遵循同一条“预览 → `bubble` → 语义验收 → 可选全真跑”生命周期。两者工具面可以不同，但都通过 Max 运行时执行并使用同一证据标准。需要完整项目验证时复用检查点中的 `project_id`，不要为每次修复新建项目。

读取 [Workflow 验收检查清单](references/Workflow验收检查清单.md)。CC/Codex 根据当前 Workflow 资产、预览结果和 `bubble` 轨迹自行执行语义验收，不启动或假设存在 Workflow 验收 FastAgent。持续修复原 Workflow 并重跑 `bubble`，直到证据满足契约。

### 10. 验收完整场景包

读取 [场景包验收检查清单](references/场景包验收检查清单.md)，把场景包 Skill、依赖闭包、每个 Workflow 契约、`workflow_orchestration`、交付映射和 Agent 交接作为一个整体检查，不启动或假设存在场景包验收 FastAgent。多 Workflow 先确认每条 Workflow 已完成 bubble 和单体验收，再做整包接缝与业务语义验收。把简洁的方案挑战、Workflow 和场景包验收结论写入工单。

场景包验收通过后，对每个 Workflow 分别询问用户是否执行 FA 全真跑并记录决定。用户跳过时继续流程；只有用户批准覆盖所选场景路径可能执行的全部 Workflow，步骤 13 才能启动真实 Max 项目。

### 11. 在归属层修复问题

- 线上工具参数或返回不匹配：重读资产，修复调用或步骤契约。
- Workflow 预览或运行时失败：更新原 Workflow。
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

获得批准后，在发布完成后调用 `manage_goalfymax_project(action="run", task_id=<task_id>, scenario_package_ids=[...], workflow_input=<object>, ...)`。显式传入 `workflow_input={}` 会触发确定性 C2 场景包；省略该字段会启动普通 Agent 对话。对于编排场景包，Agent 可以收集顶层输入，再通过内部 orchestration 启动工具显式启动同一 C2。与 `bubble` 不同，这会启动真实 Max 项目及真实 FA 和运行时行为。

用返回的 `project_id` 执行 `wait` 或 `status`。只有 Max 返回 `needs_input=true` 时才用 `reply` 或 `confirm`；资产更新后需要新尝试时才用 `send`。轮询或小修复不得反复新建项目。

### 14. 全真跑后检查真实日志和交付物

只有步骤 13 实际执行后，才用相同 `task_id` 和 `project_id` 调用 `get_project_execution_logs`：`summary/detail` 用于执行证据，`outputs/download/bundle` 用于真实交付物。临时 FA 文件和内部挂载路径不得出现。项目整体完成不代表目标 Workflow 和交付物通过。跳过全真跑时，禁止虚构 `project_id`、项目结果、日志结果或交付物结果。

### 15. 关闭工单

写入最终检查点，包含资产 ID 和 `bubble` 结论。检查点必须二选一：记录已批准的真实项目结果与交付摘要，或者记录 `full_validation_skipped`、用户决定和剩余盲区；不得包含凭证或原始日志。调用 `workflow_task_manager(action="complete", task_id=<task_id>)`。跳过全真跑时不得声称存在全真验证证据；缺少必做 `bubble` 证据或审计落库时不得声称可审计完成。
