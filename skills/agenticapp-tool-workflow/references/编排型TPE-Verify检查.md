# 编排型 TPE Verify 检查契约

单条编排型 TPE 冒泡后，结合 TPE 配置与真实冒泡轨迹自审时读。

本契约从 Beta `workflow_verify_fa` 的检查提示词整理而来，用于 CC/Codex 在 `otpe_manage(action="bubble")` 后，结合编排型 TPE 配置与真实冒泡轨迹自行检查。

## 裁决规则

- 冒泡轨迹是一手运行证据，`get_asset` 返回的 `io_table` 和脚本是解释原因与补充静态检查的证据。
- 未提供终态轨迹时只能给静态预检，裁决必须为 `needs_bubble`，不得判通过。
- `status=success` 只说明本次走到的路径成功；`unreached_tools` 和未触达分支必须列为盲区。
- FA 是 Schema 桩，只能证明调用名、输入形状和下游管路，不能证明内容质量。

## 建立检查视图

1. 读取冒泡的 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。
2. `get_asset(asset_type="tpe")` 读取当前脚本、input/output schema、preload Toolset 和 `io_table`。
3. 仅在 `io_table` 证据不足时，按需读取被引用的 FA、Tool Group 或工具真实 Schema；不得凭名称猜参数。

## 静态契约

- `input_schema` 与 `output_schema` 根节点均为 object，字段类型、必填项、示例/default 和描述明确且互相一致。
- 脚本入口为 `async def run(input, ctx)`，最终返回符合 `output_schema` 的对象。
- 每个 `tool()` 使用真实 `mr_name`，参数覆盖工具/FA 的 required 且类型正确，来源字段真实存在。
- 每个 FA 步骤必须声明最小 `_output`；下游读取的字段必须存在于上游 `_output.properties` 且类型一致。
- 每步必须有业务化 `_rationale`；不能复制工具描述或只写“调用某工具”。
- 文件只来自 input 文件字段、`ctx.skill_dir` 或本轮 `ctx.process_dir/ctx.output_dir`。
- 正式交付文件落在 `ctx.output_dir`，返回字段声明 `format=workspace-file-path`；不得返回 URL、`/tmp` 或固定共享路径。
- 返回的 `workspace-file-path` 只能来自 `ctx.output_dir`、input 文件字段或工具/FastAgent 的结构化返回；返回 `ctx.process_dir` 下由 `file` / `shell` 写出的文件判不通过（Runtime 会报 `WORKSPACE_PATH_UNTRUSTED`，`file` 写入回执是说明文字，不算来源）。
- 成功产物、技术失败和合法无产物必须分开建模：技术失败让异常冒泡；合法无产物返回明确业务状态并省略文件字段；成功分支仍条件化要求真实文件。
- `""`、占位路径和虚构路径不能表示失败；也不能只删除文件字段 `required`，让成功分支在无产物时通过。
- 文本/CSV/JSON 用 file；PDF/Word/PPT 按现有文档工具契约读取；Excel 用 shell + Python 库读取。

## 反模式检查

- 不得对已结构化 FA 结果重复 `json.loads`，也不得对 parallel/pipeline 结果二次执行。
- shell 必须使用正确 action，并以退出码判断失败；不能从包含命令回显的文本里搜索 `OK/MISSING` 猜结果。
- send_email 等工具参数必须符合真实 Schema，不能把 dict 传入要求 string 的字段。
- input 示例必须真的满足 input_schema；复杂面板字段若不稳定，应使用清晰字符串格式并在脚本解析。

## 冒泡轨迹

- 检查每个已执行步骤的 kind、状态、错误、输出形状和参数衔接；失败位置与静态 IO 表应能互相解释。
- `unreached_tools` 非空表示本次输入未覆盖相应分支，不能宣称全路径通过。
- FA 步骤为 Schema 桩值，只能证明接口形状和管路，不能证明内容质量。
- file、普通 MCP 工具和 shell 为真实执行；shell 仅在脚本引用时创建临时服务端沙盒。
- 因 FA 空桩导致的下游值依赖失败，应记录为冒泡边界，不得在生产脚本中加入绕过真实步骤的测试分支。
- 多条编排型 TPE 时只检查本编排型 TPE 的内部契约；顶层节点、DAG、JSON Path 和 delivery 由 Hub 保存校验，整体业务语义放到场景包 Verify。

## 输出格式

输出并写入工单摘要：

- `裁决`：`passed` / `blocked` / `needs_bubble`。
- `关键问题`：维度、编排型 TPE 步骤、期望与实际、后果、精确修复办法。
- `改进建议`：不阻断但影响面板友好性、可观测性或质量的项。
- `盲区`：未触达步骤、动态字段、FA 内容质量和需要全真项目验证的点。
- `证据`：编排型 TPE ID、run_id、冒泡状态、覆盖率及被读取的资产 ID。
