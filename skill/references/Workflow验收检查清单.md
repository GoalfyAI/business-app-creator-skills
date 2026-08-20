# Workflow 验收检查清单

> 每条 Workflow 取得终态运行轨迹后读取，**由你自己逐项执行**，没有可以代劳的验收工具。没有轨迹时**只能**裁决 `needs_bubble`。

---

## 裁决规则

- 冒泡轨迹是一手运行证据；`get_asset` 返回的脚本、Schema、依赖和 `io_table` 用于解释原因。
- 没有终态轨迹**只能**裁决 `needs_bubble`，**不得**判通过。
- `status=success` 只证明本次输入走到的路径成功；未触达工具和分支**必须**列为盲区。
- FastAgent 使用 Schema 桩，**只能**证明调用名、输入形状和下游管路，不能证明内容质量。
- 工具步骤被调用不等于循环体或分支已覆盖；FastAgent 桩返回空数组时，循环体和元素字段访问**必须**列为未覆盖。
- 数组 `_output` 只声明 `type=array`，但脚本迭代或索引后直接读元素字段时，是阻塞缺陷，**不得**因空数组未执行循环而放行。

## 检查步骤

1. 读取 bubble 的 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。
2. 用 `get_asset(asset_type="tpe")` 读取当前脚本、input/output Schema、业务事件契约、preload Toolset 和 `io_table`。
3. 证据不足时按需读取实际引用的 FastAgent、Tool Group 或工具 Schema，不凭名称猜参数。
4. 检查 input/output Schema 均为根对象，脚本为 `async def run(input, ctx)`，最终直接返回匹配对象。
5. 检查每个 `tool()` 的真实调用名、required 参数、类型、来源、最小 `_output` 和业务化 `_rationale`。“最小”仍**必须**覆盖代码实际读取的完整嵌套路径；读数组元素字段时核对 `items.type=object`、`items.properties` 和未做缺省处理的 `items.required`。
6. 检查文件只来自 input 文件字段、`ctx.skill_dir` 或本轮过程/输出目录；正式文件位于 `ctx.output_dir` 并以 `workspace-file-path` 返回。工具或 FastAgent 真正生成并返回的文件可以继续传递；仅计划使用的目标路径或目录不能冒充已经存在的交付文件。
7. 区分三种结束语义：成功产物必须真实存在且满足成功契约；技术失败必须让异常冒泡；合法无产物必须有明确业务状态并省略文件字段，成功分支仍条件化要求产物。
8. 对照轨迹逐步核对 kind、状态、错误、输出形状、字段衔接和最终输出。

## 业务事件覆盖

业务事件是面向业务界面的公开事实，不是运行日志。验收时按脚本全部可达终态分支逐项检查：

- 脚本进入业务执行后、首个业务动作前，***必须***发布一个已声明的 `stage_started`。
- 每个正常 `return` 分支，***必须***在结果真实成立后发布已声明的 `stage_result`；事件不能替代符合 `output_schema` 的最终返回对象。
- 产生文件交付物时，脚本只写入 `ctx.output_dir` 并按 `output_schema` 返回路径；Runtime 在正式 Artifact 登记后逐份自动发布 `artifact_ready`。脚本不得自行发布该平台事件，公开载荷不得出现 Workspace 路径、临时 URL 或存储密钥。
- 承担整条业务路线最终交付的 Workflow，***必须***在全部结果与交付物就绪后发布 `delivery_ready`；非最终节点不得把中间结果冒充最终交付。
- 脚本明确处理的业务失败终态，***必须***发布 `stage_failed`；未被安全解释的技术异常必须继续冒泡。
- 细分阶段、客观进度、中间结果和非表单提醒，***建议结合业务界面考虑***是否分别使用额外 `stage_started`、`stage_progress`、`stage_result` 和 `attention_required`。未设计这些可选事件不单独判失败；已经声明却在代表性路径未触达时，必须列为盲区并说明界面影响。

同时核对：脚本只通过 `emit_business_event(event_type=..., event_key=..., payload=...)` 发布资产中已声明的事件；`event_type` 与 `event_key` 都是稳定非空字符串字面量；Payload 是对象并满足对应根对象 Schema；事件契约包含版本、描述和 `additionalProperties:false` 的 Payload Schema；载荷不含内部 ID、原始工具结果、提示词、脚本、敏感数据或内部错误；`attention_required` 不复制运行中表单，`delivery_ready` 不代替最终审阅。发现脚本直接打印、发送普通消息、自造 `print_event` 或调用未公开内部接口模拟业务事件时，裁决为 `blocked`。

## 必查反模式

- 对已经结构化的结果重复 `json.loads`，或对 `parallel/pipeline` 结果二次执行。
- 从 shell 命令回显中搜索文字猜成功，而不是检查正确 action 和退出码。
- 工具参数类型不符合实时 Schema，例如把对象传给 string 字段。
- 示例不满足 input Schema，或者用测试分支绕过 FastAgent 桩值暴露的真实下游依赖。
- 返回 URL、`/tmp`、固定共享路径或并不存在的文件作为正式产出。
- 用 `""`、占位路径或虚构路径表示技术失败；或者只删除文件字段的 `required`，导致成功分支也可以无产物通过。
- 只返回最终对象而没有脚本侧开始与结束事件，或承担路线交付却没有 `delivery_ready`；文件交付还需核对 Runtime 是否成功登记 Artifact 并自动产生 `artifact_ready`。
- 在每个工具步骤后机械发送事件，或者用运行时长猜测 `stage_progress` 百分比。
- 用业务事件代替入口表单、运行中表单、Runtime 恢复或 Delivery Review。

## 输出

输出并写入工单简洁检查点：

- `裁决`：`passed`、`blocked` 或 `needs_bubble`。
- `关键问题`：步骤、期望、实际、后果和应更新的原 Workflow 字段。
- `盲区`：未触达步骤、业务事件、动态字段、FastAgent 内容质量和需要全真验证的事项。
- `证据`：Workflow ID、run_id、冒泡状态、覆盖率和读取的资产 ID。

裁决为 `blocked` 时更新原 Workflow，重新 Preview、bubble 和验收；**不得**新建资产规避问题。
