# 多编排型 TPE 制作契约（二）：入口、映射、中途交互与节点介入

手写路线入口、节点 `input_mapping`、中途表单（`business_interaction`）、跳转映射或节点级 `sa_handoff` 时读。

本文分 3 份：[多编排型TPE契约-图模型与标准对象.md](多编排型TPE契约-图模型与标准对象.md)、[多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md)、[多编排型TPE契约-交付重入与验证.md](多编排型TPE契约-交付重入与验证.md)。

## WF-MULTI-04 路线入口与 DAG

每条路线必须声明：

- 非空 `entry.form_id`；
- `entry.input_mapping` 对象，来源只能是 `formdata`；
- 根 `type=object` 的路线 `input_schema`；
- 非空、无重复的 `entry_nodes`；
- 至少一个 `nodes[]` 编排型 TPE 节点；
- 唯一 `delivery` 和最终 `review`。

入口 mapping 的 target 必须存在于路线 `input_schema.properties`，并覆盖全部 required；JSON Path 必须合法。制作期可预知的用户参数合并到入口表单，不拆成运行中问题。Hub 当前不登记业务表单 Schema，因此保存门只校验入口映射和路线 Schema；真实值在 Runtime 启动时按路线 Schema 复验。

节点字段使用 `node_id`，不是旧 1.0 的 `id`。每个 `workflow_ref.tpe_id` 必须是当前场景包已挂载的编排型 TPE，且同时有根对象 input/output Schema。入口节点 `depends_on` 必须为空；其他依赖必须存在，不得自依赖；整张路线图无环，所有节点从入口可达。

固定扇出、并行和多上游汇合继续放在同一 DAG。`depends_on` 只表达真实执行和数据依赖，不模拟用户选择、可选分支或循环。

## WF-MULTI-05 `input_mapping` 与文件

每个 target 字段对应一个 mapping rule object：

```json
{
  "target_field": {
    "source": "node_output",
    "node_id": "upstream_node",
    "path": "$.result",
    "transform": {"kind": "pick", "keys": ["id", "name"]}
  }
}
```

当前节点 mapping source 只有：

- `user_input`：路线 `input_schema` 已校验输入；
- `node_output`：当前节点依赖祖先的真实编排型 TPE `TaskPoint.output.data`；
- `scene_config`：当前路线对象中的固定配置。

mapping rule 只声明 `source/node_id/path/transform`。`node_output` 必须提供 `node_id`，且来源节点位于依赖祖先链。路径使用当前 Hub 支持的确定性 JSON Path；transform 只使用 `enum_map`、`default`、`pick`。自然语言抽取和复杂计算放入独立编排型 TPE，不发明表达式、条件 DSL 或第四种 source。

Hub 保存时校验 target 字段存在、每个下游 required 由普通 mapping 或合法中途交互提供、路径能在路线 input/上游 output/scene_config 中解析、基础类型兼容。根据 Hub 返回的路线、节点、字段和路径错误修改原对象后整体重提，不复制第二套 validator。

跨节点文件的上游 `output_schema` 与下游 `input_schema` 都使用 `format:"workspace-file-path"`，值保持真实 `/workspace` 绝对路径，不用 transform，不传 URL、base64 或构建期路径。来源型数据的每条结论都带上它的证据引用（来源编号或链接），与 [单编排型 TPE 制作契约](单编排型TPE契约-工具文件失败与验证.md) WF-SINGLE-09 一致，不能在节点接缝只保留 summary、丢失证据引用。

## WF-MULTI-06 中途 `business_interaction`

只有上游节点成功后才知道、且必须由用户补充的结构化值，才在源节点声明 `after_success`：

```json
{
  "node_id": "draft_outline",
  "workflow_ref": {"tpe_id": 104},
  "depends_on": ["collect"],
  "input_mapping": {
    "items": {"source": "node_output", "node_id": "collect", "path": "$.items"}
  },
  "after_success": {
    "type": "business_interaction",
    "form_id": "outline_confirm_form",
    "target_input_mapping": {
      "write.confirmed_outline": {
        "source": "formdata",
        "path": "$.confirmed_outline"
      }
    }
  }
}
```

- `after_success.type` 只能是 `business_interaction`，`form_id` 非空。
- target key 使用 `<下游 node_id>.<目标 Workflow input 一级字段>`。
- 目标必须属于源节点的下游、尚未派发节点，并真实存在于目标编排型 TPE input Schema。
- 同一目标字段只能由一个 interaction 提供，不能同时出现在目标节点普通 `input_mapping`。
- value 来源只能是 `formdata`，JSON Path 合法。
- rejected 表单在同一 `interaction_id/form_submit_id` 中重填，不创建新 interaction、Runtime 或 TaskPoint；accepted 后只恢复对应 Runtime。

中途表单不支持跳过规则，保存会被拒；节点业务上失败时怎么停，见「业务阻断怎么写」。

`business_interaction` 只补充当前路线继续需要的数据，不承担改路线。用户选择会改变路线、需要重跑已完成节点或改变副作用边界时，当前路线先到达 Delivery，再使用 `start_orchestration`。

`start_orchestration` 跳转默认弹目标路线的入口表单(全空)。要把当前路线的产出带过去,在动作上声明 `target_input_mapping`(来源只能是冻结 Delivery 产出):

```json
{
  "action_key": "continue_image",
  "kind": "start_orchestration",
  "orchestration_id": "image_route",
  "form_id": "image_entry",
  "target_input_mapping": {
    "summary": {"source": "delivery", "path": "$.summary"},
    "shop": {"source": "delivery", "path": "$.shop"}
  }
}
```

- key 是**目标路线** input_schema 的一级字段;`source` 只支持 `delivery`,path 取当前路线冻结 Delivery 的 output。
- **声明了映射就不再弹入口表单**:映射值直接作为目标路线 workflow_input 启动。因此保存门要求映射必须覆盖目标 input_schema 的全部 `required` 字段,否则拒绝保存。
- 不声明映射维持现状(弹空表单)。 [QA 1.7 一期]

## WF-MULTI-07 节点级 `sa_handoff`

节点成功后需要运行时 Agent 检查、补充或处理异常，再判断当前 DAG 是否仍成立时，在节点对象声明扁平 `sa_handoff`：

```json
{
  "node_id": "review_material",
  "workflow_ref": {"tpe_id": 105},
  "depends_on": ["collect"],
  "input_mapping": {
    "items": {"source": "node_output", "node_id": "collect", "path": "$.items"}
  },
  "sa_handoff": {
    "when": "after_success",
    "reason": "scripted",
    "instruction": "检查已提交结果中的 blocking 异常并处理；必要时使用已声明的业务交互收集信息。",
    "decision_criteria": {
      "resume": "异常已处理，后继输入和副作用边界不变，当前 DAG 仍然成立。",
      "stop": "结果无效，或处理会改变后继输入、路线、已完成节点或副作用边界。"
    }
  }
}
```

- `sa_handoff` 只放在 `nodes[]` 节点层，与 `workflow_ref` 同级；顶层、`workflow_ref` 内和 `delivery` 内都不支持。
- `when` 当前只支持 `after_success`；`reason` 如填只支持 `scripted`。
- `instruction`、`decision_criteria.resume` 和 `.stop` 都是具体非空字符串。
- `resume/stop` 是制作期判断标准字段，不是前端业务 action。
- 中途 Agent 只能继续当前 DAG、请求已声明业务表单或使 Runtime 明确失败；不能在中途完成 Business 或直接启动另一条路线。
- 需要改变路线时，当前 orchestration 到达 Delivery 后，再从 `delivery.review.allowed_actions` 选择 `start_orchestration`。
- **成功后交接先于下游入参校验**：节点配了 `sa_handoff` 且交接未处理时，下游入参校验失败不会让路线当场失败，而是先交接。交接提醒的 `input_issues` 列出这些下游节点（节点、已解析入参、错误码、原文，缺的字段写在原文里），它们不进 `next_nodes`。
- 列在 `input_issues` 里的节点只能 `take_over` 或 `continue_as_planned`（按计划继续仍按原错误失败），不放行「修改入参后继续」：`revise_and_continue` 只能改 `next_nodes` 列出的节点。需要停下时用 `take_over`。
- 映射配置错误（引用不存在的来源、`wait_for_blocks` 等）和 `enum_map`、`pick` 这类映射变换报错不等交接，路线立即失败。

2.0 不再使用旧“`continue_as_planned/revise_and_continue/take_over` 任意修改运行图”的公共语义。Agent 只处理契约声明的边界；不能自由改图、构造 TPE ID、修改已完成 output 或向任意节点写值。

## 业务阻断怎么写

节点 run 成功但业务上做不下去（证据不足、缺前置数据、合规拦截）时，先定要不要停整条路线。

共同前提：节点返回阻断状态、发阶段失败事件（`stage_failed`）都**只结束本节点**，下游照常派发。平台没有「阻断时不派下游」的条件派发；中途表单也不支持跳过规则，保存会被拒。

要停整条路线有两种写法：

| 写法 | 适用流程 | 怎么写 | 代价 |
|---|---|---|---|
| (a) 阻断状态加成功后交接 | 只有旧流程 | 节点返回明确 `status`，声明 `sa_handoff`，`decision_criteria.stop` 写明阻断时接管 | 成功后交接每次运行都触发，和节点是否阻断无关，所以每次运行都有模型费用，路线也不能被自动化发起 |
| (b) 脚本抛业务异常 | 旧流程和新流程；新流程只能用这种 | 发现阻断时先发 `stage_failed`，再 `raise` 写明原因的业务异常 | 路线按 `business_gate` 停止，不告警 |

- 节点同时配了中途表单（`after_success`）时，平台先弹表单、后交接，阻断时表单照样弹给使用者；这类节点要停下只能用 (b)。
- (b) 抛错的文字原样显示给使用者，要用业务语言写清原因。只有常规错误类型（如 `ValueError`、`RuntimeError`）算业务停止，`TypeError`、`KeyError` 这类会被判成脚本缺陷。
- 最后一个节点返回阻断时路线进入交付，由交付内容告诉使用者。
- 用 (a) 时，阻断输出直接省略下游要用的字段，不填 null 或占位值；下游映射不要对阻断时可能缺的字段用 `enum_map`、`pick`，否则映射报错、路线立即失败，不先交接。
- 路线冒泡会自动放过交接，所以 (a) 在阻断输入下冒泡终态是 failed、失败定位指向下游入参；(b) 的冒泡终态是失败类别 `business_gate`。
