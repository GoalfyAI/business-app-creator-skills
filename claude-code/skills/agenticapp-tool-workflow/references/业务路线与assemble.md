# 业务路线与 assemble

建场景包草稿、决定用不用路线、组装或修改路线、设计交付与审阅、加中途表单、处理「改稿 / 重做 / 换路线」时读。多节点、并行、扇出、中途表单、Agent 接管的字段写法读 [多编排型TPE契约-图模型与标准对象.md](多编排型TPE契约-图模型与标准对象.md)（共三份）；新 SDK 应用的差别见 [新SDK应用的路线.md](新SDK应用的路线.md)。

## 场景包草稿（旧应用）

- 新建：`scene_package_manage(action="create", task_id, name, description, apc_skill)`；开发者自己已有的包用 `scene_package_manage(action="ensure_draft")` 续用草稿；官方或他人的包先 `clone_asset` 再改。
- `apc_skill` 用开发者的词写「这个包能做哪几件事、各自什么时候用、发起前要收齐什么」，不超过 4k 字，不写资产 ID。有路线时写发起路线，不写派发任务点，写法见 [场景包配置-Skill文本.md](场景包配置-Skill文本.md)。
- 编排型 TPE 建好后挂进这个场景包，再组装路线。
- 建、改、挂 TPE 和改场景包都传 `publish_mode="staged"`（原因，以及返回里提示上线场景包时怎么办，见 `agenticapp-tool-deploy`「场景包上线」）。
- 业务工具面（list / get / clone / update）的 `asset_type` 写 `scenario_package`；版本工具面写 `scenario_pack`，两套拼法没有别名。

## 路线对象

- 场景包上的 `workflow_orchestration` 是整体业务路线（一包一份），里面 `orchestrations[]` 每一项是一条路线，`orchestration_id` 是它的标识；路线冒泡、结单核对、Runtime 绑定都以它为单位。
- 一条路线包含：入口表单标识、路线级输入定义、节点依赖图（节点引用已挂载的编排型 TPE，无环且全部可达）、节点输入映射、可选的运行中交互与节点级 Agent 介入、唯一的最终交付与审阅。
- 写入是**整体替换**：写前反读原值，改完整份传回；只传改动的那条会覆盖掉其他路线。保存成功只证明静态结构合法，不能代替冒泡。
- 路线只调度已存在且 verify 通过的编排型 TPE；场景包还没有编排型 TPE 时先建 TPE，不放空节点或空图。
- 平台要求应用挂的场景包至少有一条路线；只有规则步骤的应用也建一条最小的单节点路线。

## 什么时候用路线、用哪种

| 情况 | 做法 |
|---|---|
| 单条 TPE 声明或调用了业务事件、需要表单握手或交付审阅、要从应用发起 | 单节点路线 |
| 多条 TPE 有固定依赖、扇出、汇合 | 多节点路线；一条路线通常一条编排型 TPE 就够，要中途表单、并行或节点级接管时才拆成多个节点 |
| 普通任务点（不带业务事件）、不需要握手 | 可以直接派发，不需要路线 |
| 整条路径要临场规划，或 Agent 介入产生的新值要成为后续输入 | 普通任务点，不画固定图 |
| 使用者改稿、重做、改走另一条路线 | 冻结当前交付，开启新的运行实例；不画回边模拟循环，不覆盖旧交付 |
| 制作期就能预知的使用者输入 | 全部放入口表单 |
| 只有上游成功后才知道、且要喂给未派发下游的输入 | 节点级运行中交互（中途表单） |
| 节点成功后需要 Agent 检查或处理异常 | 该节点声明 Agent 介入，写清指令与可验证的继续或接管标准 |
| 节点业务上失败、要停整条路线 | 旧流程用成功后交接或脚本抛错，新 SDK 应用只能脚本抛错；按[多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md)「业务阻断怎么写」选写法 |

## assemble 怎么用

1. 各节点 TPE 已建好并挂进场景包后，按执行顺序调 `scene_package_manage(action="assemble", task_id, scene_package_id, tpe_ids=[…], orchestration_id, title, entry_form_id)`。
2. 它读各 TPE 的输入输出 Schema：同名字段接上游输出，并把被读的节点列为直接依赖；其余字段进入口表单；交付覆盖末节点输出；审阅缺省 `user_gate`；旧应用的草稿会带 `ask_agent`（`kind:"agent_gate"`）动作，保存前换成 `{"action_key":"reject","kind":"fail_business"}`，也不要传 `review_type="agent_gate"`。返回合并进现有编排的 `workflow_orchestration` 草稿，不写库。入口映射、节点映射、交付映射都由它生成，你只审 `unresolved` 与 `notes`。
3. 先处理 `unresolved`（类型不一致、输出为空）与 `notes`（需改名的字段），再把 `workflow_orchestration` 整份传给 `scene_package_manage(action="update", scene_package_id, workflow_orchestration)` 保存（整体替换的规则见「路线对象」）。
4. 局限：只做线性和「读谁就依赖谁」的接线；分支、并行、扇出、中途表单、Agent 接管、跳转到另一条路线仍按 [多编排型TPE契约-图模型与标准对象.md](多编排型TPE契约-图模型与标准对象.md) 手写。节点只能从直接依赖的上游读 `node_output`，读了非直接依赖的上游，保存被拒。

## 交付与审阅

- **交付映射**：要交付的文件，路径字段必须进 `delivery.mapping`，否则不会登记为附件（只在 `output_schema` 里声明，界面显示无产出文件）；映射引用的字段本次缺失时跳过，必填由 `output_schema` 的 `required` 决定。文件必须真实存在、声明为 `workspace-file-path`、在最终节点的 `ctx.output_dir` 里。
- 未声明为文件的 workspace 路径不会成为附件，交付里显示为「内部资料：文件名」。本来要交付的文件没成为附件时，补齐复制、声明和映射，不以引用文字代替。
- **审阅动作**：结束业务、以结构化原因拒绝并结束、跳转到另一条路线。存量旧路线里可能有 `kind:"agent_gate"`（交由 Agent 处理）；新写或修订时不用，换成 `complete_business` / `fail_business`。每个动作只写 `action_key` 与 `kind`，跳转另加 `orchestration_id` 与可选 `target_input_mapping`；按钮文案由 Runtime 生成，动作里不写 `label`、`description`（保存门拒收未知字段）。
- **跳转两种形态**：不需要使用者新输入时声明 `target_input_mapping`（每项 `source='delivery'`，覆盖目标路线全部必填字段），使用者点了直接启动；需要新输入（如写修改意见）时不声明映射，跳转后展示目标路线的入口表单。
- **审阅形态**：`user_gate` 停在审阅等使用者确认（缺省，`message_type` 为 `ask`）；`user_gate` 加 `message_type:"result"` 是直接交付，平台把 `delivery.mapping.text` 作为结果消息发给使用者并结束项目、不唤醒 Agent，要求 `delivery.mapping.text` 存在且只声明一个 `complete_business` 动作；存量旧路线可能是 `agent_gate`（由 Agent 收尾）；新写或修订时不用——结果不需要判断就用直接交付，需要人判断就用等使用者确认。自动化路线怎么选见 `agenticapp-tool-automation`「收尾方式」。
- 审阅应答只提交 `{ action_key }`；要改数据用中途表单或带表单的审阅动作。

## 表单定义放哪

平台不登记表单 Schema，路线里只有 `form_id` 和映射；`get_asset(asset_type="scenario_package")` 返回的 `business_forms` 是字段清单的权威来源。标题、字段说明、控件提示、顺序这些展示信息，写路线时同步为每个 `form_id` 落一份场景 Skill 文件 `forms/<form_id>.json`。

- **入口映射**：`entry.input_mapping` 的规则只声明 `source/node_id/path/transform`，来源只能是 `formdata`；默认值不直接写成 `default` 字段，按下一条用变换声明。完整写法以 [多编排型TPE契约-入口映射交互与介入.md](多编排型TPE契约-入口映射交互与介入.md) 为准。
- **入口默认值**：写成 `{"source":"formdata","path":"$.x","transform":{"kind":"default","value":…}}`；表单没填这个字段时，运行时自动补上 `value`，入口表单也不再把它列为必填。Schema 的 `default` 只是声明，不会自动填值。字段如果在 Schema 里是必填，定时自动化发起时仍要传值。

## 路线冒泡

发起、续等、verify 和 checkpoint 按 SKILL.md「路线冒泡」与 [各动作细则.md](各动作细则.md)「路线冒泡」；这里只补交付审阅。

- 交付审阅在冒泡里怎么收尾：`agent_gate` 和直接交付（`user_gate` 加 `message_type:"result"`）冒泡里没人确认，平台自动走路线唯一的终态动作并结束；`agent_gate` 声明了多个终态动作时，首次发起用 `review_action_key` 指定走哪个。`review_action_key` 只有场景包路线接受（新 SDK 应用不收），传了就按路线声明校验，不符会让冒泡失败。等使用者确认的 `user_gate`（`message_type` 为 `ask`）冒泡停在审阅，用 `run_id + formdata={"action_key": …}` 回填。
- 能证明什么、止损和时限见 [冒泡与实际跑能证明什么.md](冒泡与实际跑能证明什么.md)。
