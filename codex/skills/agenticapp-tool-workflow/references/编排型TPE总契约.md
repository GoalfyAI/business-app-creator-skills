# 编排型 TPE 制作总契约

确认要做编排型 TPE 后、写第一条脚本前读一次，同一任务里不重复通读；它只管共享术语、边界、真值优先级和阅读路由，脚本细节在单编排型、多编排型两份契约里。

> 契约版本：`2.1.0`

本文是编排型 TPE 制作知识的根契约，只定义共享术语、边界、真值优先级和阅读路由。单条编排型 TPE 细节由 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md) 细化，多条编排型 TPE 接缝由 [多编排型 TPE 制作契约](多编排型TPE契约-图模型与标准对象.md) 继续细化；具体工具调用顺序由 Max Playbook 或 External Authoring Skill 定义。

## 契约关系

```text
编排型TPE总契约.md（根契约，每个编排型 TPE 制作任务必读）
└── 单编排型TPE契约-脚本Schema与事件.md（单体契约，写任何编排型 TPE 前必读）
    └── 多编排型TPE契约-图模型与标准对象.md（组合契约，多条编排型 TPE 或多路线图业务路线时读取）
```

- [编排型 TPE 制作总契约](编排型TPE总契约.md) 管所有制作入口共同遵守的定义、边界、证据优先级和阅读路由。
- [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md) 依赖总契约，定义每个编排型 TPE 自身的脚本、Schema、工具返回、文件、失败和验证语义。多条编排型 TPE 中的每个节点也必须先满足它。
- [多编排型 TPE 制作契约](多编排型TPE契约-图模型与标准对象.md) 同时依赖总契约和单体契约，只增加 2.0 多路线入口、节点依赖、输入映射、中途业务交互、`sa_handoff`、Delivery Review、跨 Runtime 重入和整包接缝规则，不重新定义单条编排型 TPE 语义。
- 子契约只能在自己的适用范围内细化上层契约，不能覆盖上层契约。若三份契约彼此矛盾，停止按冲突条款制作并以实时 Schema、Preview、Hub Validator 和 Max Runtime 核对、修订知识源。
- Max Playbook 与 External Authoring Skill 是流程，不是第四份平台契约；它们只负责在各自工具面上落实同一组契约。

## WF-AUTH-01 真值优先级

出现冲突时按以下顺序处理：

```text
实时 MCP Tool Schema / Scene Preview / Hub Validator / Max Runtime
> 本契约与两份详细契约
> Max 或 External 制作 Playbook
> 正反例
> 历史文档、旧资产和旧对话
```

- 工具名、参数、Schema、ID、版本和权限必须从当前资产与实时 Tool Schema 获取，不从示例复制。
- Preview 负责可确定的创建期规则；Hub 负责多条编排型 TPE 保存门；Runtime 负责真实执行和最终契约。
- 示例只说明已有契约，不能增加或改写机器语义。

## WF-AUTH-02 统一产物

无论由哪个 Agent 制作，最终都是同一类平台资产：

1. 一个或多个线性编排型 TPE；
2. 每个编排型 TPE 的 `script`、`input_schema`、`output_schema`、`business_event_contracts` 和工具依赖；
3. 多条编排型 TPE 场景包的 2.0 `workflow_orchestration` 多路线对象；
4. 可选的节点级 `sa_handoff`；
5. 由 TaskPoint `output.data` 提供的结构化运行事实。

制作入口只改变「Agent 如何发现、创建和验证资产」，不改变脚本语义、文件路径、业务路线格式或运行结果。

场景包要从智能应用发起或要在页面上展示进度时，智能应用是同一工单的必交付资产；只在聊天里使用的场景包可以不带应用。智能应用分两阶段：编排型 TPE 脚本编写前先完成用户旅程、模块决策、状态—行动和业务节点—事件—界面响应预设计；全部编排型 TPE、Schema、事件和顶层业务路线稳定后，再冻结最终契约、下载模板、编码、部署。平台能力不完整时记录 `platform_blocked`，不得改记为“不需要”。

## WF-AUTH-03 Agent、编排型 TPE 与 Fast Agent 边界

- 编排型 TPE：制作期已知步骤、依赖和参数映射的确定性业务路线。
- Fast Agent：一个自包含的推理子任务；编排型 TPE 可在某一步调用它。
- 运行时 Agent：需要理解自然语言、临场选择路线、补充搜索、与用户交互或根据上下文恢复失败的环节。

一条稳定线性阶段使用单条编排型 TPE；一条路线内的固定扇出、扇入和跨阶段依赖使用无环 DAG；不同候选路线、改稿和重做使用 2.0 多路线对象以及新的 Runtime。制作期可知的用户值放路线入口；上游成功后才需要的结构化用户补参使用 `business_interaction`；明确的节点成功边界需要 Agent 检查或处理时使用节点 `sa_handoff`；最终接受、请 Agent 审阅或启动另一条路线由 `delivery.review.allowed_actions` 表达。

`sa_handoff` 不是数据节点，`decision_criteria.resume/stop` 是制作期判断标准，不是前端业务 action。Agent 不自由修改图或已完成结果。需要临场规划的整条路径交给普通 Task Agent；会改变路线的判断等待当前 Delivery 后使用 `start_orchestration` 创建新 Runtime，不在 DAG 内画回边。

## WF-AUTH-04 阅读路由

每个制作任务按需读取：

1. 确认要制作编排型 TPE 后，读一次 [编排型 TPE 制作总契约](编排型TPE总契约.md)；
2. 动笔写任何编排型 TPE 脚本前，读一次 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md)；
3. 确认需要多条编排型 TPE、多候选路线、中途业务交互或跨 Runtime 重入时，再读一次 [多编排型 TPE 制作契约](多编排型TPE契约-图模型与标准对象.md)；
4. 任务涉及 `parallel`、`pipeline`、文件产物、handoff 或降级时，制作前按 [编排示例索引.md](编排示例索引.md) 读对应示例；
5. Preview、Hub 或 Runtime 报错时，按 [编排示例索引.md](编排示例索引.md) 的诊断类型读取对应反例，并对照 [制作反例集.md](制作反例集.md)。

同一份契约或案例在同一任务中不重复通读。普通线性编排型 TPE 不读无关案例。

## WF-AUTH-05 制作入口边界

- Max Playbook 只定义 Max 内部资产制作、编辑、验证和用户确认顺序。
- External Authoring Skill 只定义审计工单、External MCP 调用、直接取样、冒泡验证和全真运行分流。
- 两个入口遵守同一套四层验证，层级不得互相替代：
  1. Preview：静态验证脚本、输入输出 Schema、工具引用和业务事件生命周期契约；
  2. 工具取样：对安全、低副作用依赖做真实调用，确认输入输出边界；
  3. 制作期 Bubble：先用单条编排型 TPE bubble 验证本次路径的数据管路、Workspace 文件和已持久化业务事件，再用路线 Bubble 验证真实图控制、表单、Delivery/Artifact 和终态 Review 接缝；
  4. 业务路线端到端全真运行：验证 FastAgent 真实内容、外部副作用、Agent 介入、智能应用事件消费、跨路线跳转和最终业务闭环。
- 业务路线保存反读属于第一层静态契约证据；单条编排型 TPE bubble 不能拼成路线证据，路线 Bubble 也不能冒充第四层全真运行。第四层只能由真实项目证明。
- 路线 Bubble 默认只读取精简证据：路线终态、节点/步骤摘要、失败错误、输出字段、事件覆盖、Artifact、Delivery 验证和 Review。完整步骤输出、最终输出值与事件 Payload 留在 Runtime；只有精简证据不足以定位失败时，才对同一 `run_id` 请求 `evidence_level="full"`，不得通过重跑路线获取同一证据。
- 路线 Bubble 失败时先按响应中的 `failure_stage`、`repair_target`、`repair_action` 定位责任层；存在 `failed_node_id` 或 `failed_step_key` 时只修对应节点/步骤。只有 `repair_target=platform_runtime` 才按平台阻断处理，禁止把资产错误笼统记为平台问题。
- 每条路线通过后，用结构化工单检查点保存 `evidence_type=orchestration_bubble_validated`、真实场景包标识、`orchestration_id` 和 `run_id`。工单完成接口会结合当前业务路线和同一工单的工具调用审计做机器核验。结单时每条当前路线都要有交代：以当前合同下最近一次终态冒泡为准，通过即可；最近一次失败须修好重跑，或写 `route_verification_waived`（带该失败 `run_id` 与理由）豁免；没有当前合同下的终态运行须补跑，或写不带 `run_id` 的 `route_verification_waived` 说明原因。豁免与未验证分别出现在 `completion_evidence.waived_routes` / `unverified_routes`，须写进交付说明。
- 全真运行（`full_run=true` 的冒泡、`manage_goalfymax_project` 真跑）要不要问开发者，只按入口「红线」的「花钱和对外动作」判断：方案「运行条件」列过的直接跑，不再问；没列过的先说清范围、Fast Agent 费用与外部副作用，他同意后再跑。不在单条编排型 TPE 制作循环中逐条询问。真跑从业务表单入口启动整条路线，运行中表单继续使用同一 Business/Runtime 回填；他不同意时记录 `full_validation_skipped` 和剩余盲区，不得伪造 project_id、项目日志或全真产物证据。
- 冒泡不需要为了节省 FA 成本而询问用户，但不是“所有工具都为桩”：FA 使用桩，`shell`、`file` 和直连工具按当前 Runtime 语义真实执行。制作入口必须在冒泡前落实 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md) 的 `ctx.dry_run` 副作用隔离和授权边界。
- External Agent 不在本地获得或模拟 Max Toolbox；它通过 External MCP 的运行适配调用真实 Max Runtime。具体 action 和参数以实时 MCP Tool Schema 为准，不把 Max 内部工具原样复制进 External Skill。
- 两个入口不把对方专属的工具名、参数或操作顺序复制进自己的 Playbook。
- 两个入口都不重复本契约或详细契约的长教程。

## WF-AUTH-06 场景包 `apc_skill` 的位置

`apc_skill` 是制作完成后给运行时 Agent 的场景包使用说明，不是编排型 TPE 制作手册。它说明场景包解决什么、何时使用、业务里程碑及各阶段目标、需要哪些业务输入、哪些权限或判断留给 Agent/用户，以及何时按名称读取场景知识文件。只有尚未固化进编排型 TPE 的 Agent 操作才写必要指引；不写 Preview、`_output`、External MCP 等制作知识，不写数字资产 ID，也不复制已在 `workflow_orchestration` 中的确定性 DAG。
