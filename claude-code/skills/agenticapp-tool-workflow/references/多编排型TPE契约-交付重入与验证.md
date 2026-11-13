# 多编排型 TPE 制作契约（三）：交付审阅、跨 Runtime 重入与验证

写 `delivery` 与最终审阅、处理改稿 / 重做 / 换路线，或保存路线后核对验证责任和制作完成清单时读。

本文分 3 份：[多编排型TPE契约-图模型与标准对象.md](多编排型TPE契约-图模型与标准对象.md)、[多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md)、[多编排型TPE契约-交付重入与验证.md](多编排型TPE契约-交付重入与验证.md)。

## WF-MULTI-08 Delivery 与最终 Review

每条路线有且只有一个正式 Delivery：

```json
{
  "delivery": {
    "node_id": "write",
    "mapping": {
      "summary": "$.summary",
      "statistics": "$.statistics",
      "report_path": "$.report_path"
    },
    "review": {
      "type": "user_gate",
      "allowed_actions": [
        {"action_key": "accept", "kind": "complete_business"},
        {"action_key": "ask_agent", "kind": "agent_gate"},
        {
          "action_key": "revise",
          "kind": "start_orchestration",
          "orchestration_id": "revise_report",
          "form_id": "revise_form"
        }
      ]
    }
  }
}
```

- `delivery.node_id` 指向路线内真实节点；`mapping` 非空，每个 value 是相对该节点 output Schema 的 JSON Path 字符串。
- 正式事实源是 `TaskPoint.output.data → delivery.mapping → 核验 → 冻结 Delivery`。WorkflowRun `final_output`、Agent 自述和 COT 只用于诊断。
- output Schema、mapping、具体统计和 Workspace 文件检查未通过时，不冻结 Delivery。
- `review.type` 只能是 `user_gate` 或 `agent_gate`；`allowed_actions` 非空，`action_key` 唯一。
- 当前 Hub action kind 接受 `complete_business`、`fail_business`、`agent_gate`、`start_orchestration`。
- `complete_business`、`fail_business` 和 `agent_gate` 不携带 `orchestration_id/form_id`。
- `start_orchestration` 指向同一 2.0 对象中存在的路线，并携带与目标 `entry.form_id` 完全一致的 `form_id`。
- `fail_business` 用于最终 Gate 明确拒绝当前 Delivery：当前 Runtime 保持 `succeeded`，Business 写入结构化失败原因并进入 `failed`；它不需要再次核验已拒绝的 Delivery。
- 最终 Gate 由 `delivery.review` 统一表达；Delivery 节点不再强制声明另一套 `sa_handoff`，也不要求 Agent 先 `message_user(result)` 再 `take_over`。

## WF-MULTI-09 跨 Runtime 重入、失败与恢复

用户改稿、补充调研、换模板、重算或换路线时：

1. 当前 Runtime 正常到达并冻结 Delivery；
2. Final Review 选择 `start_orchestration`；
3. 当前 Runtime 保持 succeeded；
4. Max 为目标路线创建新 `workflow_runtime_id`；
5. 目标路线从自己的入口表单或发起方完整输入开始。

首期不假设旧 Delivery 自动映射到新 Runtime。旧 Runtime、Delivery、TaskPoint、attempt 和文件永久保留；不得把 Runtime 改回 pending，不得覆盖旧 Delivery 或复用共享输出路径。同一 Business 首期只允许一个 active Runtime；并行发生在当前路线的编排型 TPE 节点之间。

失败保持明确边界：节点创建失败不记已派发；编排型 TPE 失败不读取残缺 output；Schema、mapping、统计或文件校验失败不冻结 Delivery；表单 rejected 保持 waiting_user；非法 Gate action 被拒绝并保留等待状态。不得静默回退普通 SA 猜测完成。

允许的重试仅包括：rejected 表单原窗口重填；显式节点重试使用同一 Runtime、`attempt+1` 和新 TaskPoint；Delivery 后整条重做使用新 Runtime。后续映射只读取被选择的成功 attempt。

幂等至少覆盖入口提交、节点创建、业务交互、Delivery 冻结和 Gate 动作。重复消息返回已有结果，不重复创建 Runtime、TaskPoint、interaction 或 Delivery。重启后以持久化 Business/Runtime 索引和真实 TaskPoint 状态重算，不依赖内存游标。

## WF-MULTI-10 保存与验证责任

- 每个单条编排型 TPE 先按 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md) 通过 Preview、bubble 与轨迹语义验证，并满足 WF-SINGLE-09 图节点就绪条件。
- 所有编排型 TPE 已挂载到场景包，Hub 才能解析真实 TPE、input/output Schema 和文件 format。
- Hub 保存门是 2.0 对象、多路线引用、入口、DAG、mapping、interaction、`sa_handoff` 形状、Delivery Review 和基础接缝的唯一确定性校验入口。
- Hub 严格拒绝旧 `blocks/wait_for_blocks/block_output`、未知字段、不可达节点、环、非法路线引用和非法 action。
- 保存 `workflow_orchestration` 时反读完整原对象并整体替换；按 Hub 返回的路线、节点、字段、路径精确修正同一对象。
- `orchestration_static_validated` 只证明保存期合法，不证明 Runtime 已支持或真实执行。
- `orchestration_bubble_validated` 必须来自发布范围内每条路线各自独立的路线 Bubble 终态证据，证明本次输入下图控制、表单、持久化事件、Delivery/Artifact 和 Review 接缝成立；桩跑不证明 FastAgent 真实内容（需要时以 `full_run=true` 重跑，通过即可作为证据），也不证明外部副作用或跨路线跳转。
- 路线 Bubble 默认使用 `evidence_level="summary"`，工单只保存 `run_id`、终态、节点/事件/交付/审核裁决及失败摘要；仅当这些摘要不足以定位失败时，才对同一 `run_id` 读取 `full`。完整证据不得默认复制进工单或记忆，也不得为取证重复运行路线。
- 路线 Bubble 的启动、回填和轮询都会在服务端等待（默认 45 秒，`wait_seconds` 可调到 0–45），到终态或需要回填表单时返回；返回 `pending`/`running` 说明本轮等满仍未结束，用同一 `run_id` 再调 `bubble` 继续等待，不要重新发起。
- 路线 Bubble 失败时按 `failure_stage`、`repair_target`、`repair_action` 修复；节点失败同时返回 `failed_node_id`/`failed_step_key`。修复资产后必须重新运行该路线，不能用旧的成功 `run_id` 覆盖新失败。
- 每条路线通过后，以工单检查点 `metadata={"evidence_type":"orchestration_bubble_validated","scene_package_id":<真实标识>,"orchestration_id":"<真实路线>","run_id":"<真实运行>"}` 登记。完成工单时，后端按当前业务路线和同一工单审计逐条复核，并在 `completion_evidence.route_bubbles` 返回机器确认结果。结单时每条当前路线都要有交代：以当前合同下最近一次终态冒泡为准，通过即可；最近一次失败须修好重跑，或写 `route_verification_waived`（带该失败 `run_id` 与理由）豁免；没有当前合同下的终态运行须补跑，或写不带 `run_id` 的 `route_verification_waived` 说明原因。豁免与未验证分别出现在 `completion_evidence.waived_routes` / `unverified_routes`，须写进交付说明。
- `orchestration_runtime_verified` 必须来自目标 Max 真实项目（要不要先问开发者见 [编排型TPE总契约.md](编排型TPE总契约.md) 的全真运行规则），且具有真实 Business、`orchestration_id`、`workflow_runtime_id`、TaskPoint、交互、Delivery 和 Review 日志；缺一不可。
- 单条编排型 TPE bubble 未触达的分支、Fast Agent 桩和副作用盲区必须记录；不得把多条单体证据拼接成整图证据。
- 修改节点脚本只重跑该节点 Preview、bubble 和轨迹验证；修改节点 IO、文件契约、route entry、mapping、interaction、Review 或完整业务路线时，重做 Hub 保存和整包接缝验证。
- 若 Hub 已接受 2.0 但目标 Max Runtime 尚未发布匹配控制器，只记录静态通过与 `platform_blocked`，禁止创建假项目或声称可直接使用。

制作完成前逐项确认：

- [ ] `schema_version` 为 `"2.0"`，路线非空且 ID 唯一；
- [ ] 每条路线名称、描述、入口和适用条件可被 SA/用户理解；
- [ ] 所有节点编排型 TPE 已挂载、Schema 完整且通过单体验收；
- [ ] 入口 mapping 覆盖路线 required，入口节点无依赖，图无环且全部可达；
- [ ] `node_output` 只读取依赖祖先，路径、基础类型、文件 format 和证据对象一致；
- [ ] 中途表单只写尚未派发的下游字段，不承担路线切换；
- [ ] 节点 `sa_handoff` 位置正确，指令和判断标准可验证；
- [ ] 每条路线有一个 Delivery 与合法 Review；
- [ ] 每个 `start_orchestration` 的目标路线和 `form_id` 匹配；
- [ ] 不含 1.0、Block DSL、旧 Delivery handoff 或未知字段；
- [ ] Hub 保存并反读通过，只记录静态证据层级；
- [ ] 每条发布路线已分别取得路线 Bubble `run_id`、终态和通过裁决，以结构化 metadata 记录 `orchestration_bubble_validated`，结单响应里每条发布路线要么在 `route_bubbles`（通过），要么在 `waived_routes` / `unverified_routes` 并带理由且已写进交付说明；缺少实时入口时明确记录 `platform_blocked`，没有拼接单条编排型 TPE 证据；
- [ ] 每条待验收业务路线都有全真运行证据，或记录了 `full_validation_skipped`；新 Runtime 没有覆盖旧 Delivery、TaskPoint、attempt 或文件；
- [ ] 未运行路线和目标 Runtime 能力盲区已如实记录。
