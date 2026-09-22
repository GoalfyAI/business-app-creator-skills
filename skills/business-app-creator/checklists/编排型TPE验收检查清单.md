# 编排型 TPE 验收检查清单

> 每条编排型 TPE 取得终态运行轨迹后读取，**由你自己逐项执行**，没有可以代劳的验收工具。没有轨迹时**只能**裁决 `needs_bubble`。本清单是**逐条执行**的验收动作：每条给出 通过 / 不适用 的判定并留下依据；整体宣称"验收通过"而没有逐条判定的，视为未验收。

---

## 裁决规则

- 冒泡轨迹是一手运行证据；`get_asset` 返回的脚本、Schema、依赖和 `io_table` 用于解释原因。
- 没有终态轨迹**只能**裁决 `needs_bubble`，**不得**判通过。
- `status=success` 只证明本次输入走到的路径成功；未触达工具和分支**必须**列为盲区。
- FastAgent 使用 Schema 桩，**只能**证明调用名、输入形状和下游管路，不能证明内容质量。
- 工具步骤被调用不等于循环体或分支已覆盖；FastAgent 桩返回空数组时，循环体和元素字段访问**必须**列为未覆盖。
- 数组 `_output` 只声明 `type=array`，但脚本迭代或索引后直接读元素字段时，是阻塞缺陷，**不得**因空数组未执行循环而放行。

## 检查步骤

1. 读取 bubble 的 `steps`、`coverage`、`unreached_tools`、`fa_stubbed`、`run_evidence.business_events`、`final_output` 和 `error`；`steps[]` 每步带 `step_key`、`kind`、`status`、`tokens`、`elapsed_ms`、`error`、`repeated_error_count`、`arguments`，取证以它为准，`run_trace` 只是文字摘要不作判据；无业务事件契约且脚本未调用 `emit_business_event` 时，把事件检查记为“不适用”，不得虚构空事件证据。
2. 用 `get_asset(asset_type="tpe")` 读取当前脚本、input/output Schema、业务事件契约、preload Toolset 和 `io_table`。
3. 证据不足时按需读取实际引用的 FastAgent、Tool Group 或工具 Schema，不凭名称猜参数。
4. 检查 input/output Schema 均为根对象，脚本为 `async def run(input, ctx)`，最终直接返回匹配对象。
5. 检查每个 `tool()` 的文件 / 路径参数形态（`file_to_url` URL、`/workspace` 路径、内容本体）与该工具实时契约一致，`_output` 有真实样本或已声明的返回结构做依据（没读过契约、没取过样的按 P2 第 5 节 补）；再检查真实调用名（FastAgent 的调用名是返回值里的 `mr_name`，克隆后的副本调用名与源不同；禁止自行拼接 `PRIVATE_FASTAGENT_` 前缀或猜 ID）、required 参数、类型、来源、最小 `_output` 和业务化 `_rationale`。“最小”仍**必须**覆盖代码实际读取的完整嵌套路径；读数组元素字段时核对 `items.type=object`、`items.properties` 和未做缺省处理的 `items.required`。
6. 检查文件只来自 input 文件字段、`ctx.skill_dir` 或本轮过程/输出目录；正式文件位于 `ctx.output_dir` 并以 `workspace-file-path` 返回。工具或 FastAgent 真正生成并返回的文件可以继续传递；作为路线交付返回的文件，须已收进最终节点 `ctx.output_dir`（G4 交付链）。仅计划使用的目标路径或目录不能冒充已经存在的交付文件。返回值由脚本按字段组装：没有把 `tool()` 或 FastAgent 的返回对象整个、或合并后写进返回值（P3 第 9.3 节按字段取用）。
7. 区分三种结束语义：成功产物必须真实存在且满足成功契约；技术失败必须让异常冒泡；合法无产物必须有明确业务状态并省略文件字段，成功分支仍条件化要求产物。 可选的第三方查询步骤用 try/except 只包住那一次调用且输出带 `degraded` / `warnings`；必需数据的调用不捕获（P3 第 9.3 节）。
   再列出每个 FastAgent `_output` 里的业务状态枚举，逐个非成功值（如 `needs_input`）在脚本里找到分支，确认它不会走到写库、发布或下游生成；Bubble 桩通常只返回成功示例，这些分支未触达时列为盲区，不当作已覆盖（P3 第 9.3 节）。
8. 对照轨迹逐步核对 kind、状态、错误、输出形状、字段衔接和最终输出。
9. 涉及文件理解的 FastAgent，按 P3 第 8.1 节检查输入来源、实际挂载的读取能力、读取提示词和失败契约；不以 `format: image` 或 URL 字符串充当读图能力。Bubble 只检查管路，真实读取与内容判断列入 P6 第 3.2 节的全真取证，不把 FA 桩判成已看图。

## 业务事件与正式运行入口

先同时反读 `business_event_contracts` 和脚本：

- 两者都不含业务事件时，该编排型 TPE 可以按实时工具契约直接派发，本节其余事件覆盖项不适用。
- 任一方出现业务事件时，另一方也必须形成一致的完整契约，并将该编排型 TPE 标记为“正式运行必须进入 Business Runtime”。单条编排型 TPE 也必须建立单节点业务路线，禁止直接派发。
- Bubble 使用服务端分配的验证 Business/Runtime 身份；该身份不是正式业务身份，禁止复制、缓存或写入脚本。
- 出现 `Workflow business event requires persisted Runtime identity` 时，正式运行优先检查是否误走直接派发；Bubble 则检查服务端是否分配验证身份。不得让脚本、Agent、智能应用或 MCP 调用方伪造 `workflow_runtime_id`（只由服务端生成）；`business_id` 本来就由调用方在发起时给出、同一业务实例内不变，`orchestration_id` 取自场景包已定义的路线 id，两者不是伪造，缺了才是错。

业务事件是面向 Business Runtime 和智能应用的公开事实，不是运行日志。对带事件编排型 TPE，按脚本全部可达终态分支逐项检查：

- Preview 已证明事件契约和原语调用要么同时为空，要么声明—调用一致且生命周期闭合；带事件时，开始事件位于首个业务动作前，每条可达 `return` 前存在结果或受控失败事件。
- Bubble 的 `run_evidence.business_events` 已给出 `declared/emitted/missing_required/unreached_event_keys/order_valid/persistence_verified/passed`；只有数据库持久化成功的事件计入 `emitted`，实时推送不作为替代证据。
- 单条编排型 TPE Bubble 只校验脚本自有事件的生命周期。Runtime 自有的 `artifact_ready` 与 `delivery_ready` 不要求脚本声明或命中；它们分别在路线级 Bubble 的 Artifact 登记与 Delivery 冻结之后校验。

Preview 对事件生命周期采用保守的静态证明。用于满足生命周期门禁的事件发布，应当直接出现在 `run(input, ctx)` 的可达控制流中；不要依赖 Preview 无法证明的模块级函数、嵌套辅助函数或动态调用。只在循环体中发布事件不能证明事件必达，因为循环可能执行零次；条件分支、`try/except`、`match` 和提前返回中的每条可达正常结束或受控失败路径，都必须在本路径内形成对应终态事件。Preview 无法证明时，应把脚本改写为可证明的结构，而不是假定运行时会执行到。Bubble 仍只证明本次输入走过的路径，未触达分支继续列为盲区。

- 脚本进入业务执行后、首个业务动作前，***必须***发布一个已声明的 `stage_started`。
- 每个正常 `return` 分支，***必须***在结果真实成立后发布已声明的 `stage_result`；事件不能替代符合 `output_schema` 的最终返回对象。
- 产生文件交付物时，脚本只写入 `ctx.output_dir` 并按 `output_schema` 返回路径——但**只在 `output_schema` 里声明并返回，不会被登记为 Artifact**：文件登记的输入是最终节点 `delivery.mapping` 的求值结果，文件路径字段**必须同时**出现在 `output_schema` 与 `delivery.mapping` 中。最终节点正常返回后，业务路线完成 Delivery mapping、文件登记与冻结（登记来源即 mapping 求值结果）；Runtime 随后逐份自动发布 `artifact_ready`，并发布 `delivery_ready`。脚本不得声明或发布这两个平台事件，非最终节点不得把中间结果冒充最终交付。
- 脚本明确处理的业务失败终态，***必须***发布 `stage_failed`；未被安全解释的技术异常必须继续冒泡。
- 密度事件（额外 `stage_started` / 中间 `stage_result` / `attention_required`）按 G4 的规则核对：未设计不单独判失败；已声明却在代表性路径未触达时列为盲区并说明消费方影响；出现 `stage_progress` 即不通过。

同时核对：脚本只通过 `emit_business_event(event_type=..., event_key=..., payload=...)` 发布资产中已声明的脚本事件；`event_type` 与 `event_key` 都是稳定非空字符串字面量；Payload 是对象并满足对应根对象 Schema；事件契约包含版本、描述和 `additionalProperties:false` 的 Payload Schema，且 `required` 含对应事件类型的平台字段（见 G4）；载荷不含内部 ID、原始工具结果、提示词、脚本、敏感数据或内部错误；`attention_required` 不复制运行中表单。脚本若声明或调用 Runtime 自有的 `artifact_ready`/`delivery_ready`，或直接打印、发送普通消息、自造 `print_event`、调用未公开内部接口模拟业务事件，裁决为 `blocked`。Runtime 的 `delivery_ready` 仍不得代替最终审阅。

## 必查反模式

- 对已经结构化的结果重复 `json.loads`，或对 `parallel/pipeline` 结果二次执行。
- 从 shell 命令回显中搜索文字猜成功，而不是检查正确 action 和退出码。
- 工具参数类型不符合实时 Schema，例如把对象传给 string 字段。
- 示例不满足 input Schema，或者用测试分支绕过 FastAgent 桩值暴露的真实下游依赖。
- 返回 URL、`/tmp`、固定共享路径或并不存在的文件作为正式产出。
- 用 `""`、占位路径或虚构路径表示技术失败；或者只删除文件字段的 `required`，导致成功分支也可以无产物通过。
- 已声明脚本业务事件，却只返回最终对象而没有脚本侧开始与结束事件；路线交付还需核对 Runtime 是否成功登记 Artifact、冻结 Delivery，并自动产生 `artifact_ready` 与 `delivery_ready`。核对以路线证据中的 `artifacts[].output_paths` 为准：其中的 mapping 表达式**必须**覆盖 `output_schema` 声明的全部文件路径字段，缺失即漏映射。
- 在每个工具步骤后机械发送事件，或为智能应用声明、发送 `stage_progress`。
- 用业务事件代替入口表单、运行中表单、Runtime 恢复或 Delivery Review。
- 带业务事件的单条编排型 TPE 在正式运行时直接派发，随后通过补写或猜测 Runtime ID 绕过持久化身份门。
- 上游已判定的结论（如素材可用性）没有随数据一起传给**所有据此做决策的下游环节**——只传数据不传判断即数据流断链。检查方式：画一遍环节间数据流，逐个确认下游拿到的信息足够做它要做的决定。
- 表示集合或可能为空的字段在 `_output` 中声明为 string：模型会用文字表达"没有"，***任何非空判断都会失效***。这类字段声明为 array，用长度判断有无。
- 用目录约定拼接读取先前运行的产物（如 `{当前目录}/v{n}.json`）——运行产物目录逐次不同，跨运行引用必须传绝对 workspace 路径（见 G4）。
- 门禁只查形状不裁业务状态：`_output` 声明了 `needs_input` 等非成功值，门禁却只核对数量、顺序、文件名，非成功结果照样进写库或下游；或对非成功状态原样重试；或最终 `status` 写死成功值。FastAgent 缺输入时照样会把形状填满，形状全过不代表结果可用。
- 写库依赖的前置记录没有前置：写库调用只给自然语言、候选 JSON 和幂等键，没有后端预建的父记录 id、目标表与只写的列；或脚本没在入口门禁按齐全 / 全部缺失 / 部分缺失核验这组 id，要等写库 FastAgent 执行中才发现父记录不存在（P3 第 9.3 节）。
- 把 `tool()` 或 FastAgent 的返回整包写进节点输出：返回里 `_output` 之外的字段（如 FastAgent 顺带的会话目录路径 `output_file`）随之进入交付——旧实现可能因未声明路径以 `ORCH_DELIVERY_FILE_UNVERIFIED` 拒收，已部署 T3415 配套实现的环境替换成「内部资料：文件名」（P3 第 12.1 节规则三）。冒泡中 FastAgent 是 Schema 桩，带不出这类字段，**必须**读脚本判定；`_output` 不是返回对象的自动裁剪器。
- 混淆附件、出处引用与意外路径：要交付的文件漏复制、文件声明或 mapping；把「内部资料：文件名」当成附件；或把新实现对未声明路径的处理扩大成“已声明但不在产物目录的文件也不报错”。按 P3 第 12.1 节规则三逐字段判定用途与目标环境行为，保留有意的出处语义，去掉无用途的 FA 内部路径。
- 写库 FastAgent 被要求建行：`context_hint` 让它"追加""新增"一条记录，或需要它填主键、父记录 id、`version_no` 等身份列；新行应由路线返回产出、后端生产回流接口建行，FastAgent 只 UPDATE 已建行的 agent 列，并在同一条更新里带 `updated_by='agent'`、`last_run_id`、`row_version+1`（P4 第 3 节「行由谁建」）。
- 被下游节点 `input_mapping` 引用、且在下游 `input_schema` 中 required 的字段，未在本节点**所有 `return` 分支**返回：`after_success` 派发不看业务成败，blocked 分支同样被取字段，缺失即路线中断（与 G4 的 schema 裁决同一原理）。

## 输出

输出并写入工单简洁检查点：

- `裁决`：`passed`、`blocked` 或 `needs_bubble`。
- `关键问题`：步骤、期望、实际、后果和应更新的原编排型 TPE 字段。
- `盲区`：未触达步骤、业务事件、动态字段、FastAgent 内容质量和需要全真验证的事项。
- `证据`：编排型 TPE ID、run_id、冒泡状态、工具覆盖率、业务事件适用性与覆盖、正式运行入口裁决，以及读取的资产 ID。

裁决为 `blocked` 时更新原编排型 TPE，重新 Preview、bubble 和验收；**不得**新建资产规避问题。
