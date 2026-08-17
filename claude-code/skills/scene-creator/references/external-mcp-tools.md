# 外部 MCP 工具路由

> 本文是 `SKILL.md` 的工具路由补充。进入具体场景包制作、诊断、优化或续作任务时读取；实时 MCP Schema 和服务端校验始终优先于本文。

---

## 路由原则

先用 MCP 协议 `tools/list` 确认当前工具、action、参数和必填字段。本文只维护稳定职责和调用依赖，不复制完整参数 Schema，不承诺工具数量或未来版本形状。

| 工具 | 稳定职责 | 关键边界 |
|---|---|---|
| `task_manager` | 创建、读取、追加和完成可审计工单 | 新任务的第一项业务 MCP 调用；`read/write` 模式不可混用；新建 `write` 工单传完整 `skill_version` |
| `list_assets` | 搜索可复用资产、场景包和已完成经验 | 只读；可选接收 `task_id` 但不强制，不改变资产权限；搜索结果不是完整资产契约 |
| `get_asset` | 反读资产完整配置、关系、Schema、版本和状态 | 只读；可选接收 `task_id` 但不强制，不改变资产权限；重要选择用 `task_manager(insert)` 留痕 |
| `get_diagnosis_doc` | 按 topic 读取当前服务端制作契约和示例 | 在工单 Gate 后按需读取；记录 topic 和结论，不复制整篇返回内容 |
| `dataset_read` | 读取有权限的数据集内容 | 只读；可选接收 `task_id` 但不强制，不改变数据集权限；只取改变路线或参数所需的最小充分内容 |
| `file_to_url` | 将本地文件或可信 HTTPS Skill 文件准备为受控引用 | `purpose` 区分 Skill 文件、Skill 包、MCP 包和 Logo；Skill 文件支持 `prepare/complete/from_url` 并返回 `data.skill_file` |
| `preview_tool_group` | 预览新的 MCP 连接并发现工具 | 只做新连接预览；刷新已有工具组使用 `register_and_refresh_tool_group` |
| `register_and_refresh_tool_group` | 注册新的工具组或刷新已有工具组 | 创建与刷新共用原工具的两种参数模式，以实时 Schema 为准 |
| `upload_and_register_tool_group` | 上传并注册私有工具包 | 仅用于实时 Schema 支持的包类型和上传来源 |
| `create_fast_agent` | 创建 FastAgent | 使用独立原工具，不经过聚合 action；创建后立即反读 |
| `create_toolset` | 创建 Toolset | 使用独立原工具，不经过聚合 action；创建后验证能力和状态 |
| `create_tpe` | 创建普通任务点 | 仅编排需要模型临场判断或自然语言交互的任务点 |
| `online_toolsets` | 发布本轮已验证的 Toolset | 只发布已完成运行验证且属于本工单范围的 Toolset |
| `import_skill_package` | 从标准 Skill 包导入 Toolset | 导入结果仍需反读、验证和按需发布 |
| `clone_asset` | 克隆允许复制的已有资产 | 修改共享资产前先克隆；创建后立即反读克隆结果 |
| `update_asset_field` | 修改资产文本或标量字段 | 先反读旧值并按实时确认门执行，不与关系更新混用 |
| `update_asset_relations` | 修改资产关联关系 | 先确认真实 ID 和当前关系；受限资产按实时确认门执行 |
| `upload_skill_files` | 上传或更新已有资产的 Skill 文件 | 使用实时合并/替换语义；临时上传 URL 不写入工单 |
| `delete_asset` | 删除当前用户有权删除的资产，或按 Hub 规则移除分享授权 | `task_id` 只用于工单审计，实际删除权限和资产边界由 Hub 原工具判断 |
| `create_auth_card` | 为 MCP 创建授权卡 | 密钥和认证配置不写入工单；按实时认证契约执行 |
| `update_auth_card` | 更新已绑定授权卡 | 可能使既有授权失效，按实时确认门执行 |
| `link_auth_card` | 绑定已有授权卡 | 替换现有绑定前按实时确认门执行 |
| `update_scenario_package_logo` | 将已上传的 PNG 设置为场景包 Logo | 使用 `file_to_url` 返回的受控文件引用，不传本地路径或任意 URL |
| `workflow_tool_test` | 为 Workflow 开发对已有 MCP 工具做真实调用取样 | 直接传取样参数，不使用 action；可能真实调用供应商，不创建、修改或删除资产 |
| `scene_package_manage` | 创建、读取、更新、发布场景包及当前版本编排 | 当前 `workflow_orchestration` 是完整对象整体替换；写前反读原对象 |
| `scene_package_ui_bundle` | 下载官方 UI 模板，上传、部署和反读定制界面 | 当前除模板下载外要求目标场景包至少挂载一个 Workflow；不能为纯 SA 包绕过该门槛 |
| `workflow_tpe_manage` | Preview、创建、更新、挂载、发布和 bubble Workflow | 创建前依赖闭包已准备；bubble 轮询复用同一 `run_id` |
| `manage_goalfymax_project` | 运行和控制真实 Max 项目 | 会启动真实 Agent、FastAgent 和工具；只有用户批准覆盖整条候选路线时执行 |
| `get_project_execution_logs` | 读取真实项目日志和最终交付物 | 复用原 `project_id`；只保留诊断和交付所需内容 |

不要虚构平行的 `list_tools`、`scene_package_task_manage` 或旧工单别名。正常制作统一使用 `task_manager`。如果实时工具改名或 action 变化，重新读取 Schema，并以结构化错误为准更新调用。

## 工单 Gate

```text
新建制作/优化：task_manager(create, mode=write, skill_version=<完整版本标记>)
新建诊断：    task_manager(create, mode=read)
已知工单续作：task_manager(get)
未知 ID 续作：task_manager(list) → 唯一匹配时 get；无匹配才 create
诊断转修复：  新建 write 工单，并记录 continued_from_task_id
```

Gate 成功前不能读取制作契约、搜索业务资产、创建计划或写入。安装和连通性检查是例外：只做 `tools/list` 与一次只读资产查询，不建立业务工单。

`task_id` 是审计范围，不是资产 ID。`list_assets/get_asset/dataset_read/task_manager` 的 Schema 接受该字段但不全局强制：前三者只读且不改变权限，`task_manager` 的 `get/insert/complete` 按 action 要求。

## 稳定调用关系

不是每个场景包都需要 Workflow 或编排；但只要选择了任意 Workflow，业务界面就是同一场景包的强制交付。按以下依赖推进，不把其他可选分支当成固定流水线：

```text
task_manager(create/get)
→ get_diagnosis_doc(scene_package)                        # 当前场景包契约
→ list_assets / get_asset / dataset_read                  # 建立真实证据
→ 完整材料/项目深读 → 里程碑、路线图、理想态和验收蓝图
→ 能力覆盖矩阵 → 方案挑战检查清单 → 用户确认
→ get_diagnosis_doc(toolset/fast_agent/...)               # 仅将要创建或诊断的资产
→ preview/register/upload/create/update/... 独立资产工具  # 按真实能力缺口选择原工具
→ workflow_tool_test(...)                                 # 仅需要真实 MCP 返回取样时
→ scene_package_manage(create/update, offline)            # 建立或复用同一草稿
→ file_to_url(purpose=skill_file) + skill_files_mode=merge # 仅缺少场景知识文件

→ get_diagnosis_doc(workflow_authoring)                   # 决定使用 Workflow 后
→ get_diagnosis_doc(workflow_single)                      # 写单 Workflow 前
→ get_diagnosis_doc(workflow_examples/匹配 topic)         # 特殊原语按需
→ 依赖反读与上线 → workflow_tpe_manage(preview/create/update)
→ workflow_tpe_manage(bubble start/poll) → Workflow 单体验收

→ get_diagnosis_doc(workflow_multi)                       # 确认多 Workflow、多路线或运行中 Gate 后
→ scene_package_manage(update, workflow_orchestration)    # 当前 2.0 多路线对象完整替换
→ orchestration_static_validated                          # Hub 保存门，不冒充运行门

→ scene_package_ui_bundle(download_template/...)          # 已挂载任意 Workflow 时强制执行
→ 业务界面验收

→ 场景包整包验收 → scene_package_manage(online)          # 仅已获发布授权
→ manage_goalfymax_project + get_project_execution_logs   # 仅已获全真运行授权
→ task_manager(insert) → task_manager(complete)
```

如果创建场景包时依赖官方基础包克隆，创建后立即反读继承结果；后续修复始终更新同一草稿，不用新建平行资产规避错误。

## 编排版本门

当前 Hub 保存契约只接受 `schema_version:"2.0"` 的多路线对象：

- 完整对象包含 `orchestrations[]`，每条路线有入口表单、路线 input Schema、无环 Workflow DAG、唯一 Delivery 和最终 Review；
- 节点必须引用当前场景包已挂载且已完成单体验收的 Workflow；
- 路线内映射、`business_interaction`、节点级 `sa_handoff` 和 `delivery.review` 使用当前 `workflow_multi` 契约；
- 路线切换、改稿和重做创建新 Runtime，不在同一 DAG 画回边或覆盖旧 Delivery；
- 更新 `workflow_orchestration` 时反读原值并提交完整 2.0 对象；
- Hub 保存只形成 `orchestration_static_validated`。

实时 MCP、Hub 与目标 Max Runtime 必须同时支持匹配的 2.0 契约。若 Hub 可保存但目标 Runtime 尚未发布，只能记录静态通过和 `platform_blocked`；禁止把旧 1.0、Block DSL、delivery 强制 handoff 或设计稿未落地 action 混入 2.0，也禁止让前端代替 Runtime 执行图。

## 标识纪律

- `task_id`：工单审计范围。
- `scene_package_id`：场景包资产标识。
- `tpe_id`：Workflow 或普通任务点资产标识。
- `tool_group_id`、`tool_id`、`toolset_id`：依赖资产标识。
- 脚本工具名：使用当前线上 `name/mr_name`，不用资产 ID。
- `run_id`：bubble 运行标识，轮询时复用。
- `project_id`：真实 Max 项目标识，查询、回复和日志读取时复用。

## 验证职责

| 证据 | 能证明 | 不能证明 |
|---|---|---|
| MCP JSON Schema | 调用参数形状 | 业务方案正确 |
| Preview | 脚本、声明工具和 IO 契约可保存 | 真实 FastAgent 内容和外部副作用正确 |
| 依赖反读 / `workflow_tool_test` | 资产状态或代表性供应商返回 | 整条 Workflow 正确 |
| bubble | 当前 Workflow 终态轨迹和接缝行为 | FastAgent 真实内容、未触达分支、整包编排运行 |
| Hub 编排保存 | 当前版本结构、映射和 delivery 静态合法 | 编排真实命中、顺序、handoff 或最终交付 |
| Max 项目日志与交付物 | 被批准路线的真实运行结果 | 未运行路线或未来输入都正确 |

因此分别记录 `asset_contract_validated`、`workflow_bubble_passed`、`orchestration_static_validated`、`orchestration_runtime_verified`、`ui_deployment_verified` 和 `full_validation_skipped`。没有整图运行入口或实际日志时，不能声称 `orchestration_runtime_verified`。
