# 单编排型 TPE 制作契约（一）：运行形态、Schema 与业务事件

动笔写任何编排型 TPE 脚本前读；读之前先读过 [编排型TPE总契约.md](编排型TPE总契约.md)。

本文分 2 份：[单编排型TPE契约-脚本Schema与事件.md](单编排型TPE契约-脚本Schema与事件.md)、[单编排型TPE契约-工具文件失败与验证.md](单编排型TPE契约-工具文件失败与验证.md)。

> 契约版本：`1.6.2`

> 机器真值：Scene Preview、Core Restricted 编排型 TPE/Schema 契约、Max 编排型 TPE Runtime

本文依赖 [编排型 TPE 制作总契约](编排型TPE总契约.md)，定义单个编排型 TPE 的平台语义。`workflow_orchestration.schema_version="2.0"` 中的每个节点也必须先满足本契约；[多编排型 TPE 制作契约](多编排型TPE契约-图模型与标准对象.md) 只在此基础上增加多路线入口、节点接缝、中途交互、最终审阅和跨 Runtime 重入。使用 Max 还是 External MCP 创建和验证资产，由各自 Playbook 决定，不改变本契约。

## WF-SINGLE-01 运行形态

一个编排型 TPE 是一个职责明确的确定性线性阶段。Max 项目启动后由 TABuilder 构建可执行 Toolbox，编排型 TPE TaskAgent 直接执行受限脚本并通过 Toolbox 调用工具。外部编码 Agent 只获得工具描述和 Schema，不获得 Toolbox 对象。

脚本入口固定为：

```python
async def run(input, ctx):
    result = await tool(
        "demo_search",
        query=input.get("query", ""),
        _rationale="获取后续步骤需要的事实数据",
        _output={
            "type": "object",
            "required": ["items"],
            "properties": {"items": {"type": "array"}}
        }
    )
    return {"items": result["items"]}
```

`demo_search` 是文档夹具；实际脚本必须使用当前资产返回的真实 `name/mr_name`。

脚本只使用当前 Preview 允许的 Python 子集与 `tool/parallel/pipeline/emit_business_event/json`。不调用 `message_user`，不构造答题卡、授权卡、计费卡或等待用户输入。制作期可预知的值放入 `input_schema`，不可预料的交互留给 Agent。

## WF-SINGLE-02 三种 Schema

### `input_schema`

`input_schema` 定义开始执行前必须准备的输入，根必须是 `type=object`。

```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": {"type": "string"},
    "source_file": {"type": "string", "format": "file"}
  }
}
```

- 脚本只读取已声明字段；
- 用户上传文件使用 `format:"file"`，图片使用 `format:"image"`；
- description/default/examples 不写死 `/workspace` 路径；
- 编排型 TPE 自己产生的过程文件和结果文件不是用户输入。

### 工具 `input_schema` 与步骤 `_output`

工具 `input_schema` 规定调用参数；工具正式 `output_schema` 规定 Provider 声明的返回；步骤 `_output` 只规定本次 `tool()` 后续代码要消费的最小结构。三者不得混淆。

### 编排型 TPE `output_schema`

编排型 TPE `output_schema` 是整条脚本最终机器产出的静态契约，根必须是 `type=object`。脚本直接 return 匹配的 dict：

```json
{
  "type": "object",
  "required": ["summary", "report_path"],
  "properties": {
    "summary": {"type": "string"},
    "report_path": {"type": "string", "format": "workspace-file-path"}
  }
}
```

```python
return {"summary": summary, "report_path": report_path}
```

不返回人话字符串、list、`json.dumps(...)` 文本或 URL。TaskPoint `output.data` 是下游运行事实源，WorkflowRun 汇总只用于观测和调试。

#### 三种结束语义

| 结束语义 | 脚本行为 | `output_schema` 行为 |
|---|---|---|
| 成功产物 | 正常 return，并返回已经生成的真实文件路径 | 成功分支将文件字段设为必填，并声明 `format:"workspace-file-path"` |
| 技术失败 | 不捕获，或捕获后重新抛出，让 Runtime 记录编排型 TPE failure | 不返回成功对象，不用 `""`、占位路径或虚构路径满足 Schema |
| 合法无产物 | 仅在“无结果”本身是业务允许的终态时正常 return | 返回明确业务状态并省略文件字段；成功状态仍条件化要求文件字段 |

“合法无产物”不是技术失败的兜底名称。网络错误、工具异常、文件生成失败等仍属于技术失败。不能只从根级 `required` 删除文件字段，否则成功分支也会在没有产物时通过。需要同时表达“成功有文件”和“合法无产物”时，文件属性保持在根级 `properties`，再用条件约束控制分支必填：

```json
{
  "type": "object",
  "properties": {
    "status": {"type": "string", "enum": ["success", "no_output"]},
    "report_path": {"type": "string", "format": "workspace-file-path"},
    "reason": {"type": "string"}
  },
  "required": ["status"],
  "allOf": [
    {
      "if": {"properties": {"status": {"const": "success"}}},
      "then": {"required": ["report_path"]}
    },
    {
      "if": {"properties": {"status": {"const": "no_output"}}},
      "then": {"required": ["reason"]}
    }
  ]
}
```

无产物分支直接省略 `report_path`，禁止返回空字符串。文件属性保留在根级 `properties`，使 Runtime 能继续发现并核验成功分支的 Workspace 文件。

## WF-SINGLE-03 业务事件契约与原语

业务事件是编排型 TPE 向智能应用发布的稳定公开事实，不是日志、表单或返回值替代品。每个编排型 TPE 资产通过 `business_event_contracts` 预先声明可发布事件：

```json
[
  {
    "event_key": "diagnosis_started",
    "event_type": "stage_started",
    "event_version": "1.0.0",
    "description": "门店经营诊断已经开始",
    "payload_schema": {
      "type": "object",
      "additionalProperties": false,
      "required": ["stage_key", "stage_name"],
      "properties": {
        "stage_key": {"type": "string", "minLength": 1},
        "stage_name": {"type": "string", "minLength": 1}
      }
    }
  }
]
```

创建或更新的业务路线运行型 TPE 时，通过 `otpe_manage.business_event_contracts` 与脚本、输入输出 Schema 一起写入；反读 `get_asset(tpe)` 必须得到同一组声明。每项必须包含非空 `event_key/event_type/event_version/description` 和根对象 `payload_schema`；Payload Schema 必须设置 `additionalProperties:false`。事件类型、字段和约束以实时编排型 TPE Tool Schema 为准。

Preview 把事件当作每条编排型 TPE 的必需静态契约：空声明直接失败；至少声明并调用 `stage_started` 和 `stage_result`；首个业务动作前必须保证已经发布 `stage_started`；每条可达 `return` 前必须保证发布 `stage_result`，受控业务失败分支可用 `stage_failed`；声明未被脚本引用、脚本引用未声明事件或类型不一致都拒绝保存。Preview 只能证明静态可达关系，不能证明事件已经持久化或被智能应用消费。

脚本使用受控原语：

```python
async def run(input, ctx):
    await emit_business_event(
        event_type="stage_started",
        event_key="diagnosis_started",
        payload={"stage_key": "diagnosis", "stage_name": "正在分析门店经营情况"},
    )
    result = await tool(
        "diagnosis_tool",
        store_name=input["store_name"],
        _rationale="形成门店经营诊断结果",
        _output={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
    )
    await emit_business_event(
        event_type="stage_result",
        event_key="diagnosis_completed",
        payload={"stage_key": "diagnosis", "summary": result["summary"]},
    )
    return {"summary": result["summary"]}
```

- `event_type` 和 `event_key` 必须是非空字符串字面量，禁止动态拼接；
- `payload` 必须显式传对象，并通过同名事件声明的 Schema；
- 脚本只能发布资产中恰好一个同名、同类型的已发布声明；
- 每条编排型 TPE 在首个业务动作前必须发布 `stage_started`，每个正常 return 前必须发布 `stage_result`，脚本明确处理的业务失败终态必须发布 `stage_failed`；
- 正式文件完成登记后，`artifact_ready` 由 Runtime 自动发布；脚本不声明、不调用该平台事件，也不自行证明文件已进入索引；
- 路线最终节点正常返回后，由业务路线完成 Delivery mapping、文件登记和冻结，再由 Runtime 唯一发布 `runtime.delivery_ready`；脚本不声明、不调用 `delivery_ready`，该事件也不替代 Delivery Review；
- 额外细分阶段、客观进度、中间结果和非表单提醒只在智能应用有明确消费理由时声明，不在每个工具调用后机械发布；
- 事件不替代编排型 TPE 最终 return、入口表单、`business_interaction`、Runtime 恢复或 Delivery Review；
- Payload 不出现 Project/TaskPoint/编排型 TPE 等内部 ID、Workspace 路径、临时 URL、原始工具返回、提示词、脚本、密钥或未脱敏错误。

Runtime 在持久化事件前核对 Business、Orchestration、编排型 TPE Runtime 和来源 TaskPoint 身份；持久化成功后再实时投递。实时通道失败不回滚权威事件，智能应用按 Runtime 查询补拉。Bubble 也必须在服务端分配的验证 Business/Runtime 上执行，禁止制作 Agent 伪造身份。
