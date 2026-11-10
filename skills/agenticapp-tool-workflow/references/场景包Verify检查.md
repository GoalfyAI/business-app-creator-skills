# 场景包 Verify 检查契约

场景包上线前做整体交付检查，或同一修复会话里做增量复验时读。

本契约从 Beta `csp_verify_checker` 的检查提示词整理而来，用于 CC/Codex 在场景包上线前进行整体交付检查，不启动 Max FastAgent。

## 验证模式与复用边界

- `full` 用于初次创建、最终交付，或无法完整说明本轮变更资产时；它是交付门，但不是每次文本修复后的默认动作。
- `incremental` 用于同一修复会话内的复验。调用方必须给出本轮所有 `changed_assets`（资产类型、ID、实际修改字段）以及可选的 `previous_passed_check_ids`。
- 同一修复批次的多次小改先合并变更清单，再验证一次。禁止为删除单个字符分别建立多步计划并重复整包 Verify。
- 上一轮通过项只有在其资产与依赖均未被本轮影响时才可复用；被影响项必须读取最新真实配置重跑。变更清单缺失、字段未知或影响范围无法穷尽时降级 full，并说明原因。

### 增量影响范围

- TPE 文本字段只失效该 TPE 的质量项；name、toolset_ids、preload_toolsets 变化再失效对应的 Skill 名称引用和闭包交叉项。
- Toolset 文本字段失效其描述/Skill 与成员一致性项；name、成员关系变化再失效引用它的 TPE 和场景包能力/名称引用项。
- FA 或 Tool Group 的 Prompt、Schema、工具关系变化，失效该资产及直接包含它的 Toolset/FA 一致性项。
- apc_skill 变化失效 Skill 质量、资产名称、能力与数据集引用项；场景包关系变化只扩展到新增、删除及直接引用的成员。
- 数据集或绑定关系变化失效数据集可访问性和 Skill 双向引用项。
- 多资产变更取影响范围并集；跨层不等于必须全量，只有依赖边界无法确定时才全量。

## 稳定检查项

- 检查项 ID 固定为 `<层级>.<资产ID或APC>.检查名`，例如 `TPE.2000092.TEXT_COMPLETE`、`TOOLSET.3192.GUIDE_MATCH_MEMBERS`、`APC.2000514.TPE_TOOLSET_CLOSURE`。
- 检查名只允许来自固定目录，禁止自造同义名：APC 使用 `TOOLSETS_EXIST`、`TPE_TOOLSET_CLOSURE`、`SKILL_NONEMPTY`、`DATASETS_ACCESSIBLE`、`SKILL_CAPABILITY_MATCH`、`SKILL_DATASET_REFS`、`SKILL_STRUCTURE`、`SKILL_NO_NUMERIC_IDS`、`SKILL_SCENARIO_SPECIFIC`、`DYNAMIC_TOOLSET_REFERENCED`、`SKILL_ASSET_NAMES`；TOOLSET 使用 `MEMBERS_EXIST`、`GUIDE_MATCH_MEMBERS`、`GUIDE_EFFECTIVE`；TPE 使用 `TOOLSETS_EXIST`、`TEXT_COMPLETE`、`WORKFLOW_SAVED`、`WORKFLOW_VERIFIED_ONLINE`、`PRELOAD_COVERS_TOOLS`；FAST_AGENT 使用 `PROMPT_TOOL_MATCH`、`PROMPT_QUALITY`；TOOL_GROUP 使用 `CONFIG_REASONABLE`。不适用的项省略。
- 同一语义不得因报告措辞变化生成新 ID；按维度固定顺序、资产类型、数字 ID、检查项 ID 排序，保证相同输入的检查集合稳定。
- 总数是“本轮实际执行项 + 合法复用通过项”的并集；分别记录 `executed_count` 和 `reused_count`，未执行且未复用的项不得记为通过。

## 证据与检查顺序

按“先广后深”执行：full 模式检查场景包、全部 TPE/编排型 TPE 和全部 Toolset 的描述与 Skill；incremental 模式只在上述影响范围内检查。两种模式下，FA 和 Tool Group 都只对被影响、被引用或发现异常的项下钻。

1. full 模式用 `get_asset(asset_type="scenario_package")` 读取场景包 Skill、Skill 文件、Toolset、TPE/编排型 TPE、数据集和 `workflow_orchestration` 全貌；incremental 模式只有命中场景包或跨层项时才读取，纯 TPE 文本变化不得额外读整包。
2. full 模式逐个读取全部 Toolset 和 TPE/编排型 TPE；incremental 模式只读取受影响资产，反查其直接依赖是否存在、在线且属于场景包闭包。
3. 对可疑或实际引用的 FA、Tool Group、Auth Card、长期数据集和智能应用数据集模板继续读取真实配置。
4. 汇总每个编排型 TPE 的最新冒泡证据和编排型 TPE Verify 裁决。

## 资产完整性

- 场景包名称、描述、Skill 和 Skill 文件与目标业务一致；Skill 包含里程碑、权限边界、操作策略和必要系统认知。
- Skill 不能过度泛化、包含数字资产 ID 或复制一份 DAG；Skill 文件必须有明确读取时机。
- 编排型 TPE、custom TPE、Toolset、FA、Tool Group、长期数据集关系均可由真实资产结果反查，智能应用数据集模板关系由 business_ui_manage(get) 反查。
- 每个 Toolset 至少包含 FA 或 Tool Group 之一，Toolset Skill 与实际工具一致。
- custom/predefined TPE 的 Prompt、Query 和输出约束完整；编排型 TPE 的这些文本字段为空是正常的，检查其脚本与 Schema。
- 编排型 TPE 使用的 `mr_name` 均来自已挂载 Toolset 闭包。
- 需要授权的 Tool Group 已正确绑定 Auth Card，工单日志中没有凭证明文。
- 数据源名称与绑定的长期数据集 / 智能应用数据集一致，不存在引用缺失或从未使用的冗余绑定。

## 一致性与质量

- 场景包里程碑需要的能力被真实资产覆盖，资产名称与 Skill 引用完全一致。
- TPE/编排型 TPE 引用的 Toolset 必须在场景包中；编排型 TPE preload 闭包覆盖脚本所有普通工具和 FA（Runtime 默认 file/shell 等除外）。
- FA Prompt 要求的能力应由其工具支持，Tool Group Schema 与编排型 TPE 调用参数一致。
- 失败路径、数据缺失、格式变化和外部系统错误有明确处置；高风险动作有用户确认和 dry-run 边界。

## 多条编排型 TPE

- DAG 节点引用当前场景包已挂载且在线的编排型 TPE。
- 节点输入映射符合目标编排型 TPE 的 `input_schema`，上游输出符合下游消费字段，且业务含义正确而不仅是类型碰巧相同。
- 分支、并行、交付节点和 `sa_handoff` 均有明确业务含义，不存在孤立或循环节点。
- Hub 保存成功是节点存在、环/孤儿、JSON Path、required、基础类型和 delivery 路径的唯一静态结论；不要再猜第二套规则。

## 验证证据

- 每个编排型 TPE 都有当前版本对应的冒泡 `run_id`、终态轨迹和编排型 TPE Verify 裁决。
- 已记录未触达分支与 FA 桩边界；不得把冒泡当成内容质量或外部副作用的全真验证。
- 单条编排型 TPE 自动完成 Preview、冒泡与语义验证。业务路线保存后，目标环境支持时还要取得业务路线的图业务路线冒泡证据；不支持时保留整图运行盲区。端到端全真运行按业务路线做，要不要先问开发者见 [编排型TPE总契约.md](编排型TPE总契约.md) 的全真运行规则。使用 `manage_goalfymax_project` 的业务表单入口创建真实项目，并用同一 Business/Runtime 的日志核对 SystemAgent、TaskAgent、FastAgent、工具调用、运行中表单、业务事件、Delivery、Review 和交付产物。
- 每条路线通过后必须把真实场景包标识、`orchestration_id`、`run_id` 写入 `orchestration_bubble_validated` 结构化工单检查点；完成工单时通过的路线出现在 `completion_evidence.route_bubbles`。结单时每条当前路线都要有交代：以当前合同下最近一次终态冒泡为准，通过即可；最近一次失败须修好重跑，或写 `route_verification_waived`（带该失败 `run_id` 与理由）豁免；没有当前合同下的终态运行须补跑，或写不带 `run_id` 的 `route_verification_waived` 说明原因。豁免与未验证分别出现在 `completion_evidence.waived_routes` / `unverified_routes`，须写进交付说明。
- 路线 Bubble 失败报告必须保留 `failure_stage`、`repair_target`、`repair_action`，以及存在时的 `failed_node_id`/`failed_step_key`，据此修复最小责任层后重跑同一路线。
- 用户跳过全真验证时仍可以交付；记录 `full_validation_skipped`、用户决定、FA 内容/未触达分支/副作用等剩余盲区，不得伪造 `project_id`、项目日志或全真产物证据。

## 输出格式

按以下结构输出并写入工单摘要：

- `验证摘要`：场景包名称/ID、检查项总数、通过数、未通过数、裁决 `ready/blocked`。
- `验证范围`：full/incremental、本轮变更资产、实际读取资产、降级原因（如有）、`executed_count` 与 `reused_count`。
- `未通过项`：稳定检查项 ID、维度、问题、涉及资产与 ID、后果、应使用哪个现有工具修复什么字段。
- `通过项`：按稳定检查项 ID 列出已核证范围，并区分本轮执行与复用，不能只给笼统“通过”。
- `运行证据与盲区`：编排型 TPE / run_id / 覆盖率、未触达分支、FA 桩边界，以及已批准的真实项目结果或 `full_validation_skipped` 与剩余风险。
