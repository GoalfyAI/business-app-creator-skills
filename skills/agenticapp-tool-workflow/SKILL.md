---
name: agenticapp-tool-workflow
description: 调用 otpe_manage、create_fast_agent、scene_package_manage 前必须加载：模型步骤、编排脚本、路线和试跑。接外部工具用 agenticapp-tool-integration，到点自动跑用 agenticapp-tool-automation。
---
# 编排：模型步骤、脚本、路线

应用里每条业务流程由下面几样拼成，先分清各自管什么：

- **FA（FastAgent）**：一个模型步骤。挂上工具后在一次调用里多轮做完一个业务环节；没有记忆，不和使用者交互。
- **编排型 TPE**：确定性脚本 `async def run(input, ctx)`，自己不推理，要模型时调 FA；管准备、分发、汇合、幂等写库和固定收口。
- **路线**（`orchestration_id`）：把一条或几条 TPE 接成节点图，带入口表单、中途表单、最终交付与审阅。旧应用的路线在场景包的 `workflow_orchestration` 里。
- **冒泡**：在隐藏验证项目里跑一次。默认 FA 是桩（按 `_output` 造值），`full_run=true` 才真调模型；写库被跳过。实际跑见 `agenticapp-tool-deploy`「实际跑」。

原语签名和字段以 [references/编排型TPE总契约.md](references/编排型TPE总契约.md) 起的编排型 TPE 契约和工具当前 Schema 为准。单次运行时长、读取上限这类数字怎么用来定分批，见 `agenticapp-ref-platform-limits`。

**新 SDK 应用**（`frontend/goalfy-app.json` 有 `"executor": "launch_agent"`）：下面各节照用，差别全在 [references/新SDK应用的路线.md](references/新SDK应用的路线.md)，动手前先读。

下面各动作的细则读 [references/各动作细则.md](references/各动作细则.md) 同名的节。

## 选执行形态

每一步交给 SystemAgent 直接执行、FA、普通任务点还是编排型 TPE，FA 和脚本的分工，`_output` 怎么收口，见 [references/执行形态与模型档位.md](references/执行形态与模型档位.md)。

## 建 FA

前提：PRD 定了这一步用哪一档模型。

1. 每个模型步骤一个 `create_fast_agent(name, description, prompt_content, model_name, model_selection_mode="required", …)`，一个 FA 只承担一个语义责任。`model_name` 用档位对应的模型，`max_turns` 按预估步数给，取法见 [references/执行形态与模型档位.md](references/执行形态与模型档位.md)「模型档位」。
2. `input_schema` 顶层是对象，每个字段有类型和足够详细的描述。
3. 提示词写清输入字段、输出对象每个字段的含义和非成功状态；输出给部分成功留出口（[references/脚本骨架与失败出口.md](references/脚本骨架与失败出口.md)「失败出口怎么写」）。
4. 要按情况查应用库的，建时就挂应用库只读工具（[references/读写应用库与反读自查.md](references/读写应用库与反读自查.md)「要按情况查库的 FA」）。
5. **核对**：`get_asset(asset_type="fast_agent")` 反读 `mr_name`（脚本里一律用它）、`model_selection_mode`、`model_name`；挂了应用库工具的看 `actual_tool_group_ids`。做成：`model_selection_mode` 为 `required`、`model_name` 是选定的模型；`actual_tool_group_ids` 含 `query_business_app_dataset` 所在工具组（[references/读写应用库与反读自查.md](references/读写应用库与反读自查.md)「要按情况查库的 FA」）。

## 写编排脚本

前提：脚本要调的工具和 FA 已装进工具集并上线（加载 `agenticapp-tool-integration`）；读写应用库的，先按 `agenticapp-tool-data-template` 定好谁建行、写哪些列、入口放什么。

1. 写第一条脚本前读 [references/编排型TPE总契约.md](references/编排型TPE总契约.md)，再读 [references/单编排型TPE契约-脚本Schema与事件.md](references/单编排型TPE契约-脚本Schema与事件.md)（共两份）；路线要并行、扇出、中途表单或节点级接管时再读 [references/多编排型TPE契约-图模型与标准对象.md](references/多编排型TPE契约-图模型与标准对象.md)（共三份）。用到某种原语或报了某类错时按 [references/编排示例索引.md](references/编排示例索引.md) 读对应正反例。
2. 挑一种模板整段复制，只改业务词，不从零写：[拉数落库](references/模板一-拉数落库.md)、[查库判读写回](references/模板二-查库判读写回.md)、[生成写库](references/模板三-生成写库.md)。三种都读写应用库；要模型决定查什么的才交给挂了工具的业务 FA。
3. 照 [references/脚本骨架与失败出口.md](references/脚本骨架与失败出口.md) 核骨架：`_output`、`_rationale`、失败出口、`ctx.dry_run`、幂等、`shell` 退出码。
4. 要声明业务事件、产出文件、把一批数据交给 FA 时，照 [references/事件契约与文件产物.md](references/事件契约与文件产物.md)；要读长期数据集的见细则。
5. 读写应用库的，按下一节写。

## 读写应用库

用到施工单「存数据」里的表，或结果要存下来给页面看、给下次用的路线，脚本要真的读写应用库。

1. 把统一的 `db()` 复制进脚本，所有读写都经它；业务值用 `:name` 占位符放进 `params`，SQL 是固定字符串。
2. 读：读失败或查不到都按「没有数据」收口，不重试、不编数；读库不包 `dry_run`。
3. 写：写库语句包在 `if not ctx.dry_run:` 里；写失败或改到的行数不对，返回 `blocked`「未入库」，不进下游。
4. TPE 的 `preload_toolset_ids` 里要有装了工具组「query_business_app_dataset」的工具集。做成：preview 不报「无法解析到 preload_toolsets」。
5. **核对**：preview 前和 `online` 后各过一遍反读自查四项，结果记进阶段文档 G4；四项都「有」这条路线才算做好。

谁什么时候读写、SQL 写法和连接纪律、`db()` 原文、四项定义：[references/读写应用库与反读自查.md](references/读写应用库与反读自查.md)。

## 建、校验和上线 TPE

1. `otpe_manage(action="preview", task_id, script, input_schema, output_schema, business_event_contracts, preload_toolset_ids)`。
2. 通过后 `create`（同一组参数加 `scene_package_id`、`name`、`description`），再 `online`。建、改、挂 TPE 都传 `publish_mode="staged"`（原因见 `agenticapp-tool-deploy`「场景包上线」）。
3. `otpe_manage(action="verify", task_id, tpe_id)` 看 `verdict`：`blocked` 按 `failed` 项改后重来；`needs_bubble` 说明静态项都过了，只差运行证据。做成：`failed` 为空、没有 `toolsets_online` / `tpe_online` 失败；读写应用库的路线到 `needs_bubble` 为止，运行证据到 ④ 实际跑补。
4. 需要时单条冒泡，什么时候用见 [references/冒泡与实际跑能证明什么.md](references/冒泡与实际跑能证明什么.md)「verify 收哪种证据」。
5. **核对**：`get_asset(asset_type="tpe")` 反读脚本和事件契约；`tpe_id` 记进工单。

## 组装路线

前提：各节点 TPE 已 verify 通过或只差运行证据，并挂进场景包（新 SDK 应用挂在应用版本上）。

1. 场景包草稿：新建、续用自己的草稿，官方或他人的包先 `clone_asset`；写好 `apc_skill`。
2. `scene_package_manage(action="assemble", …)` 出路线草稿，先处理 `unresolved` 与 `notes`，再把 `workflow_orchestration` **整份**传给 `update` 保存。做成：`unresolved` 都处理完、`update` 保存成功，反读时其他路线还在。
3. 定交付与审阅：要交付的文件进 `delivery.mapping`。做成：冒泡后交付里这些文件是附件，没有显示成「内部资料：文件名」。
4. 每个 `form_id` 落一份场景 Skill 文件 `forms/<form_id>.json` 写展示信息。
5. **核对**：`get_asset(asset_type="scenario_package")` 反读路线和 `business_forms`。

什么时候用路线、用哪种，`assemble` 的局限，交付、审阅、跳转、入口映射的写法：[references/业务路线与assemble.md](references/业务路线与assemble.md)。

## 路线冒泡

1. `scene_package_manage(action="bubble", task_id, scene_package_id, orchestration_id, workflow_input=<例子>)`；要模型真的跑出内容时加 `full_run=true`。做成：回执到终态（没到就用同一 `run_id` 续等）；FA 是桩时只算「只用模拟数据试过」。
2. 到终态后，对路线里每条 TPE 用这次的 `run_id` 调 `otpe_manage(action="verify", tpe_id, run_id)`。
3. 一条路线一条工单 checkpoint，各带自己的 `run_id`。做成：`task_manager(insert)` 返回不带 `format_warning`。
4. 跑太久、积分一直涨就 cancel 止损。冒泡能证明什么、哪种 `run_id` 能给 verify、多久后读不到：[references/冒泡与实际跑能证明什么.md](references/冒泡与实际跑能证明什么.md)。

## 配置写法与自审

- 场景包名称、描述、工具集加载模式、Skill 文本与 Skill 文件：[references/场景包配置-名称描述工具集.md](references/场景包配置-名称描述工具集.md)（共四份）。
- 普通任务点（TPE）配置：[references/TPE配置-定位与输入输出.md](references/TPE配置-定位与输入输出.md)（共两份）；FA 配置：[references/FastAgent配置-定位名称描述.md](references/FastAgent配置-定位名称描述.md)（共三份）；提示词深度优化：[references/Agent提示词最佳实践.md](references/Agent提示词最佳实践.md)。
- 写脚本、拆 FA、设计数据面、交付验证前对照 [references/制作反例集.md](references/制作反例集.md)。
- 自审：建场景包前按 [references/场景包Battle检查.md](references/场景包Battle检查.md)；单条冒泡后按 [references/编排型TPE-Verify检查.md](references/编排型TPE-Verify检查.md)；上线前按 [references/场景包Verify检查.md](references/场景包Verify检查.md)。

## 自动化

要给路线加自动发起，加载 `agenticapp-tool-automation`。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 冒泡跑通了，就说读写库的功能做好了，其实库里有没有写进数据都没验过 | 冒泡里读空、写被跳过；读写应用库的路线要 ④ `workspace` 实际跑后 verify |
| 为了让冒泡通过，把读库包进 `dry_run`、从入口塞数据、加 `fallback_*` 或删掉读写；后三种让反读自查记「没有」，路线不算做好 | 读库不包 `dry_run`，只把写库包进去；入口只放业务键 |
| 按步骤拆 FA，或脚本写成 tool → FA → tool → FA 长链 | 拆 FA 只看职责边界；「看结果再决定查什么」交给一个 FA |
| FA 只允许成功态（模型会编数据去满足 schema）；FA 返回 `needs_input` 仍继续写库 | `status` 留 `partial`、`blocked` 出口；非成功态不进写库和下游 |
| 自己给 FA 拼调用名或用数字 ID | 用反读到的 `mr_name` |
| 改路线只传改动的那条，其他路线被覆盖掉 | 反读原值，整份传回 |

其他常见错误在上面各节指向的 references 的「常见错误」里；报错码见 [references/编排报错对照.md](references/编排报错对照.md)。
