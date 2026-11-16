# 多编排型 TPE 制作契约（一）：图模型、标识与标准对象

确认需要多条编排型 TPE、多条候选路线、中途业务交互或跨 Runtime 重入时读；每个节点先满足 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md)。

本文分 3 份：[多编排型TPE契约-图模型与标准对象.md](多编排型TPE契约-图模型与标准对象.md)、[多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md)、[多编排型TPE契约-交付重入与验证.md](多编排型TPE契约-交付重入与验证.md)。

> 契约版本：`2.1.0`

> 机器真值：Hub `workflow_orchestration` 2.0 保存校验、Core TaskPoint 契约、目标环境 Max Runtime

本文依赖 [编排型 TPE 制作总契约](编排型TPE总契约.md) 和 [单编排型 TPE 制作契约](单编排型TPE契约-脚本Schema与事件.md)，定义 2.0 多路线图业务路线的共享机器契约。每个节点先满足单编排型 TPE 契约，本契约再约束路线入口、节点依赖、字段映射、中途业务交互、节点级 Agent 介入、最终 Delivery Review 和跨 Runtime 重入。各入口如何创建编排型 TPE、挂载场景包并提交完整对象，由各自 Playbook 定义。

Hub 当前保存门只接受 `schema_version:"2.0"`。目标环境实时 MCP Schema、Hub 返回错误和 Max Runtime 仍高于本文；若目标环境尚未发布匹配的 2.0 Runtime，只能完成静态保存与验收，必须记录 `platform_blocked`，不能把静态通过称为运行可用。

## WF-MULTI-01 图模型与拆分边界

图业务路线不是任意有环流程引擎：

```text
Business：从业务入口到用户最终接受交付
├── Runtime 1：执行 orchestration A 的固定无环 DAG → Delivery A
└── Runtime 2：Final Review 选择新路线后执行 orchestration B → Delivery B
```

- 一个场景包版本可以声明多条 `orchestration`；每条路线代表一条公开、稳定、可独立验证的业务路径。
- 一个 Runtime 只绑定一个 `orchestration_id`，只执行该路线的无环 DAG，只形成一个正式 Delivery。
- 固定扇出、扇入、多上游 join、中间产物复用，以及职责、权限、副作用、验证或恢复边界变化，可以拆成多个编排型 TPE 节点。
- 单条确定性直线不按步数机械拆分。单条编排型 TPE 在 2.0 Runtime 中是一条只有一个节点的路线。
- 制作期无法确定后继、需要临场规划的路径交给 SA 或普通任务点；不把任意分支塞入 DAG。
- 用户选择会改变后续路线时，让当前 Runtime 到达 Delivery，再通过最终 Review 启动新 Runtime；不在当前 DAG 画回边、`condition` 或动态节点。
- 没有编排型 TPE 的场景包不创建空图，继续走现有 SA/普通任务点能力。

## WF-MULTI-02 标识与 Runtime 边界

| 标识 | 含义 | 稳定范围 |
|---|---|---|
| `business_id` | 一次完整业务过程 | 从首次入口到最终接受 Delivery |
| `orchestration_id` | 场景包开发者声明的公开路线 | 场景包版本内唯一 |
| `workflow_runtime_id` | 某条路线的一次执行实例 | 单个 Runtime 全程不变 |
| `form_id` | 入口或中途业务表单定义 | 制作期固定 |
| `form_submit_id` | 一次表单提交记录 | rejected 重填时复用 |
| `taskpoint_event_id` | 某节点某次 attempt 的真实执行 | 单次节点执行 |
| `delivery_id` | 核验后冻结的交付引用 | 不可覆盖 |

`workflow_runtime_id` 统一由 GoalfyMax 服务端生成。智能应用首次启动只提交 `orchestration_id` 和入口表单，不得生成或传入 Runtime ID；Backend 完成请求、项目、幂等与配额校验后生成，Max 真正启动编排型 TPE 后通过 `business_interaction_result(status=accepted)` 回传。聊天框、Agent Gate 或路线重入同样由 Max 生成。TaskPoint、交互、查询和 Delivery 全程携带同一 Runtime ID。

Runtime `succeeded` 只表示当前路线已生成并冻结 Delivery，不代表 Business 完成。Business 只有在最终 Review 选择 `complete_business` 后才 completed。改稿、补充、重算或改走路线时保留当前 Runtime 与 Delivery，创建新 Runtime。

## WF-MULTI-03 标准 `workflow_orchestration`

以下是 Hub 当前接受的标准形状。示例 ID 只说明字段关系，实际提交必须使用当前场景包已挂载编排型 TPE 的真实 TPE ID。

```json
{
  "schema_version": "2.0",
  "orchestrations": [
    {
      "orchestration_id": "research_and_report",
      "title": "调研并生成报告",
      "description": "收集资料、形成报告并提交审核",
      "entry": {
        "form_id": "research_form",
        "input_mapping": {
          "topic": {"source": "formdata", "path": "$.topic"},
          "max_items": {"source": "formdata", "path": "$.max_items"}
        }
      },
      "input_schema": {
        "type": "object",
        "required": ["topic", "max_items"],
        "properties": {
          "topic": {"type": "string"},
          "max_items": {"type": "integer", "minimum": 1}
        },
        "additionalProperties": false
      },
      "entry_nodes": ["collect"],
      "nodes": [
        {
          "node_id": "collect",
          "workflow_ref": {"tpe_id": 101},
          "depends_on": [],
          "input_mapping": {
            "topic": {"source": "user_input", "path": "$.topic"},
            "max_items": {"source": "user_input", "path": "$.max_items"}
          }
        },
        {
          "node_id": "write",
          "workflow_ref": {"tpe_id": 102},
          "depends_on": ["collect"],
          "input_mapping": {
            "topic": {"source": "user_input", "path": "$.topic"},
            "items": {"source": "node_output", "node_id": "collect", "path": "$.items"}
          }
        }
      ],
      "scene_config": {},
      "delivery": {
        "node_id": "write",
        "mapping": {
          "summary": "$.summary",
          "report_path": "$.report_path"
        },
        "review": {
          "type": "user_gate",
          "allowed_actions": [
            {"action_key": "accept", "kind": "complete_business"},
            {"action_key": "reject", "kind": "fail_business"},
            {
              "action_key": "revise",
              "kind": "start_orchestration",
              "orchestration_id": "revise_report",
              "form_id": "revise_form"
            }
          ]
        }
      }
    },
    {
      "orchestration_id": "revise_report",
      "title": "根据意见改写报告",
      "description": "根据原报告和修改意见生成新的可审核版本",
      "entry": {
        "form_id": "revise_form",
        "input_mapping": {
          "source_report_path": {"source": "formdata", "path": "$.source_report_path"},
          "revision_notes": {"source": "formdata", "path": "$.revision_notes"}
        }
      },
      "input_schema": {
        "type": "object",
        "required": ["source_report_path", "revision_notes"],
        "properties": {
          "source_report_path": {"type": "string", "format": "workspace-file-path"},
          "revision_notes": {"type": "string"}
        },
        "additionalProperties": false
      },
      "entry_nodes": ["revise"],
      "nodes": [
        {
          "node_id": "revise",
          "workflow_ref": {"tpe_id": 103},
          "depends_on": [],
          "input_mapping": {
            "source_report_path": {"source": "user_input", "path": "$.source_report_path"},
            "revision_notes": {"source": "user_input", "path": "$.revision_notes"}
          }
        }
      ],
      "scene_config": {},
      "delivery": {
        "node_id": "revise",
        "mapping": {
          "summary": "$.summary",
          "report_path": "$.report_path"
        },
        "review": {
          "type": "user_gate",
          "allowed_actions": [
            {"action_key": "accept", "kind": "complete_business"},
            {"action_key": "reject", "kind": "fail_business"}
          ]
        }
      }
    }
  ]
}
```

`workflow_orchestration` 是独立机器契约，使用完整对象整体替换。不把同一图复制到 `apc_skill`、Toolset 指南或智能应用，不用字段级 JSON merge 修补旧对象。

Hub 严格解码 2.0 对象：`schema_version` 必须为字符串 `"2.0"`，`orchestrations` 非空，`orchestration_id` 唯一，未知字段失败。旧顶层单路线 1.0 对象不迁移、不兼容，不能与 2.0 混写。
