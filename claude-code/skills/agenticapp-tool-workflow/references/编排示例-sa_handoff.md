# `sa_handoff` 决策正反例

2.0 路线里某个编排型 TPE 节点成功后，需要 Agent 检查结果、处理外部状态或判断当前无环 DAG 是否仍然成立时读。诊断关键词：`sa_handoff`、`decision_criteria.resume/stop`、节点级介入、`business_interaction`、`delivery.review`、新 Runtime。对应契约：`WF-MULTI-07`。

## 不变量

- `sa_handoff` 只放在 `nodes[]` 节点层，与 `workflow_ref` 同级；不能放在顶层、`workflow_ref` 或 `delivery` 内。
- `decision_criteria.resume/stop` 是制作期给 Agent 的可验证判断标准，不是前端业务 action，也不允许 Agent 任意修改运行图。
- `resume` 只适用于后继输入、路线、已完成结果和副作用边界都不变，当前 DAG 仍成立的情况。
- `stop` 用于结果无效，或继续执行需要改变后继输入、路线、已完成节点或副作用边界的情况；Runtime 必须留下明确状态和证据，不能静默猜测完成。
- 用户需要补充当前路线的结构化下游输入时，使用 `business_interaction`；用户要改路线、改稿或重做时，让当前 Runtime 到达 Delivery，再由 `delivery.review` 启动新 orchestration 和新 Runtime。
- 最终审阅由 `delivery.review` 表达，Delivery 节点不强制再声明 `sa_handoff`。
- 节点返回阻断状态只结束本节点，下游照常派发；要停整条路线按[多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md)「业务阻断怎么写」选写法。

## 正例：只修复外部状态，输入不变

场景：`prepare_report` 已产出确定的 `report_path`，后继 `publish_report` 仍读取同一路径；Agent 只需完成发布权限授权。

```json
{
  "node_id": "prepare_report",
  "workflow_ref": {"tpe_id": 201},
  "depends_on": [],
  "input_mapping": {
    "topic": {"source": "user_input", "path": "$.topic"}
  },
  "sa_handoff": {
    "when": "after_success",
    "reason": "scripted",
    "instruction": "检查发布权限；缺少权限时完成授权，不修改 prepare_report 的结果或后继入参。",
    "decision_criteria": {
      "resume": "发布权限已具备，publish_report 仍使用既有 report_path，其他后继入参和路线均不变。",
      "stop": "授权失败，或必须更换 report_path、发布目标、后继路线或其他结构化入参。"
    }
  }
}
```

授权成功后可以继续当前 DAG，因为变化只发生在外部权限状态；若授权要求改变发布目标或文件，则必须停止当前自动续跑。

## 正例：用户回答需要成为下游输入

如果上游完成后才知道需要用户确认的 `strategy_type`，不要假设 handoff 对话会自动写回下游节点。应在上游节点声明结构化业务交互：

```json
{
  "node_id": "draft_strategy",
  "workflow_ref": {"tpe_id": 202},
  "depends_on": ["collect"],
  "input_mapping": {
    "items": {"source": "node_output", "node_id": "collect", "path": "$.items"}
  },
  "after_success": {
    "type": "business_interaction",
    "form_id": "strategy_confirm_form",
    "target_input_mapping": {
      "generate_ads.strategy_type": {
        "source": "formdata",
        "path": "$.strategy_type"
      }
    }
  }
}
```

`business_interaction` 只补充尚未派发的下游字段。若用户选择会改变整条路线、重跑已完成节点或改变副作用边界，则当前路线先形成 Delivery，再通过 `start_orchestration` 进入新 Runtime。

## 正例：最终交付由 Review 决定

```json
{
  "delivery": {
    "node_id": "write_report",
    "mapping": {
      "summary": "$.summary",
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

接受交付才完成 Business；咨询 Agent 不等于完成；改稿启动目标路线的新 Runtime，并保留原 Runtime 与 Delivery。

## 反例：把 handoff 当成隐藏的数据节点

错误写法：

```json
{
  "sa_handoff": {
    "when": "after_success",
    "reason": "scripted",
    "instruction": "询问用户最终预算",
    "decision_criteria": {
      "resume": "用户已经回答预算",
      "stop": "用户拒绝回答"
    }
  }
}
```

问题：用户回答不会自动进入路线 `user_input`、任何上游 `node_output` 或 `scene_config`，后继节点仍只能读到旧 mapping。

最小修复：

1. 预算在路线开始前可知：放进入口表单和路线 `input_schema`，后继从 `user_input` 映射。
2. 预算只有上游成功后才能确定：使用 `business_interaction` 写入尚未派发的下游字段。
3. 预算改变会导致换路线或重做：当前路线形成 Delivery 后，使用 `delivery.review` 的 `start_orchestration` 启动新 Runtime。

## 制作检查

- `instruction` 说明 Agent 具体检查或处理什么，不只写“请判断下一步”；
- `decision_criteria.resume` 明确哪些既有字段、外部条件、路线和副作用边界必须保持不变；
- `decision_criteria.stop` 覆盖结果无效、输入改变、换路线、重跑和副作用边界变化；
- 没有假设自然语言、Agent 判断或工具返回会隐式写回图；
- 结构化补参使用 `business_interaction`，路线切换使用 `delivery.review`；
- Delivery 节点没有重复声明一套强制 handoff；
- 目标环境尚未发布 2.0 Runtime 时，只记录静态契约通过与 `platform_blocked`，不把示例当成运行证据。
