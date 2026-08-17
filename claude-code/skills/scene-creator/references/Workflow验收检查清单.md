# Workflow 验收检查清单

> 本文是 `SKILL.md` 的单 Workflow 验收指南。每条 Workflow 完成 bubble 并取得终态轨迹后读取；没有轨迹时只能裁决 `needs_bubble`。

---

本清单承接 Max `workflow_verify_fa` 的职责。外部 Agent 在每条 Workflow 完成 `bubble` 后直接执行，不调用 FastAgent。

## 裁决规则

- 冒泡轨迹是一手运行证据；`get_asset` 返回的脚本、Schema、依赖和 `io_table` 用于解释原因。
- 没有终态轨迹只能裁决 `needs_bubble`，不得判通过。
- `status=success` 只证明本次输入走到的路径成功；未触达工具和分支必须列为盲区。
- FastAgent 使用 Schema 桩，只能证明调用名、输入形状和下游管路，不能证明内容质量。
- 工具步骤被调用不等于循环体或分支已覆盖；FastAgent 桩返回空数组时，循环体和元素字段访问必须列为未覆盖。
- 数组 `_output` 只声明 `type=array`，但脚本迭代或索引后直接读元素字段时，是阻塞缺陷，不得因空数组未执行循环而放行。

## 检查步骤

1. 读取 bubble 的 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。
2. 用 `get_asset(asset_type="tpe")` 读取当前脚本、input/output Schema、preload Toolset 和 `io_table`。
3. 证据不足时按需读取实际引用的 FastAgent、Tool Group 或工具 Schema，不凭名称猜参数。
4. 检查 input/output Schema 均为根对象，脚本为 `async def run(input, ctx)`，最终直接返回匹配对象。
5. 检查每个 `tool()` 的真实调用名、required 参数、类型、来源、最小 `_output` 和业务化 `_rationale`。“最小”仍必须覆盖代码实际读取的完整嵌套路径；读数组元素字段时核对 `items.type=object`、`items.properties` 和未做缺省处理的 `items.required`。
6. 检查文件只来自 input 文件字段、`ctx.skill_dir` 或本轮过程/输出目录；正式文件位于 `ctx.output_dir` 并以 `workspace-file-path` 返回。
7. 对照轨迹逐步核对 kind、状态、错误、输出形状、字段衔接和最终输出。

## 必查反模式

- 对已经结构化的结果重复 `json.loads`，或对 `parallel/pipeline` 结果二次执行。
- 从 shell 命令回显中搜索文字猜成功，而不是检查正确 action 和退出码。
- 工具参数类型不符合实时 Schema，例如把对象传给 string 字段。
- 示例不满足 input Schema，或者用测试分支绕过 FastAgent 桩值暴露的真实下游依赖。
- 返回 URL、`/tmp`、固定共享路径或并不存在的文件作为正式产出。

## 输出

输出并写入工单简洁检查点：

- `裁决`：`passed`、`blocked` 或 `needs_bubble`。
- `关键问题`：步骤、期望、实际、后果和应更新的原 Workflow 字段。
- `盲区`：未触达步骤、动态字段、FastAgent 内容质量和需要全真验证的事项。
- `证据`：Workflow ID、run_id、冒泡状态、覆盖率和读取的资产 ID。

裁决为 `blocked` 时更新原 Workflow，重新 Preview、bubble 和验收；不得新建资产规避问题。
