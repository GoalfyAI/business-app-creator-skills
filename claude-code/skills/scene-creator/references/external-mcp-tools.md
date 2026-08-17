# 外部 MCP 工具路由

> 本文是 `SKILL.md` 的工具路由补充。进入具体场景包制作、诊断、优化或续作任务时读取；实时 MCP Schema 和服务端校验始终优先于本文。

---

## 路由原则

先用 MCP 协议 `tools/list` 确认当前工具、action、参数和必填字段。本文只维护稳定职责和调用依赖，不复制完整参数 Schema，不承诺工具数量或未来版本形状。

| 工具 | 稳定职责 | 关键边界 |
|---|---|---|
| `task_manager` | 创建、读取、追加和完成可审计工单 | 新任务的第一项业务 MCP 调用；`read/write` 模式不可混用；新建 `write` 工单传完整 `skill_version` |
| `list_assets` | 搜索可复用资产、场景包和已完成经验 | 只读，不接收 `task_id`；搜索结果不是完整资产契约 |
| `get_asset` | 反读资产完整配置、关系、Schema、版本和状态 | 只读，不接收 `task_id`；重要选择用 `task_manager(insert)` 留痕 |
| `get_diagnosis_doc` | 按 topic 读取当前服务端制作契约和示例 | 在工单 Gate 后按需读取；记录 topic 和结论，不复制整篇返回内容 |
| `dataset_read` | 读取有权限的数据集内容 | 只读，只取改变路线或参数所需的最小充分内容 |
| `workflow_file_upload` | 上传场景 Skill 文件或 Workflow 辅助文件 | 使用实时 Schema 暴露的上传闭环；临时 URL 不写入工单 |
| `workflow_dependency_manage` | 维护依赖、Auth Card、普通 TPE、Toolset 和直连 MCP 取样 | `test_tool` 可能真实调用供应商；Workflow TPE 由 `workflow_tpe_manage` 管理 |
| `scene_package_manage` | 创建、读取、更新、发布场景包及当前版本编排 | 当前 `workflow_orchestration` 是完整对象整体替换；写前反读原对象 |
| `scene_package_ui_bundle` | 下载官方 UI 模板，上传、部署和反读定制界面 | 当前除模板下载外要求目标场景包至少挂载一个 Workflow；不能为纯 SA 包绕过该门槛 |
| `workflow_tpe_manage` | Preview、创建、更新、挂载、发布和 bubble Workflow | 创建前依赖闭包已准备；bubble 轮询复用同一 `run_id` |
| `manage_goalfymax_project` | 运行和控制真实 Max 项目 | 会启动真实 Agent、FA 和工具；只有用户批准覆盖整条候选路线时执行 |
| `get_project_execution_logs` | 读取真实项目日志和最终交付物 | 复用原 `project_id`；只保留诊断和交付所需内容 |

不要虚构平行的 `list_tools`、`scene_package_task_manage` 或 `workflow_task_manager`。如果实时工具改名或 action 变化，重新读取 Schema，并以结构化错误为准更新调用。

## 工单 Gate

```text
新建制作/优化：task_manager(create, mode=write, skill_version=<完整版本标记>)
新建诊断：    task_manager(create, mode=read)
已知工单续作：task_manager(get)
未知 ID 续作：task_manager(list) → 唯一匹配时 get；无匹配才 create
诊断转修复：  新建 write 工单，并记录 continued_from_task_id
```

Gate 成功前不能读取制作契约、搜索业务资产、创建计划或写入。安装和连通性检查是例外：只做 `tools/list` 与一次只读资产查询，不建立业务工单。

`task_id` 是审计范围，不是资产 ID。只给实时 Schema 明确接受 `task_id` 的调用传入它；`list_assets/get_asset` 不接收该参数。

## 稳定调用关系

不是每个场景包都需要 Workflow、编排或业务界面。按以下依赖推进，不把可选分支当成固定流水线：

```text
task_manager(create/get)
→ get_diagnosis_doc(scene_package)                        # 当前场景包契约
→ list_assets / get_asset / dataset_read                  # 建立真实证据
→ 形成路线图、资产选择和验收蓝图
→ 方案挑战检查清单
→ scene_package_manage(create/update, offline)            # 建立或复用同一草稿
→ workflow_file_upload + skill_files_mode=merge           # 仅缺少场景知识文件
→ get_diagnosis_doc(toolset/fast_agent/...)               # 仅将要创建或诊断的资产
→ workflow_dependency_manage                              # 仅真实能力缺口

→ get_diagnosis_doc(workflow_authoring)                   # 决定使用 Workflow 后
→ get_diagnosis_doc(workflow_single)                      # 写单 Workflow 前
→ get_diagnosis_doc(workflow_examples/匹配 topic)         # 特殊原语按需
→ 依赖反读与上线 → workflow_tpe_manage(preview/create/update)
→ workflow_tpe_manage(bubble start/poll) → Workflow 单体验收

→ get_diagnosis_doc(workflow_multi)                       # 确认多 Workflow 后、编排前
→ scene_package_manage(update, workflow_orchestration)    # 当前固定 DAG 完整替换
→ orchestration_static_validated                          # Hub 保存门，不冒充运行门

→ scene_package_ui_bundle(download_template/...)          # 已挂载 Workflow 且需要定制 UI
→ 业务界面验收

→ 场景包整包验收 → scene_package_manage(online)          # 仅已获发布授权
→ manage_goalfymax_project + get_project_execution_logs   # 仅已获全真运行授权
→ task_manager(insert) → task_manager(complete)
```

如果创建场景包时依赖官方基础包克隆，创建后立即反读继承结果；后续修复始终更新同一草稿，不用新建平行资产规避错误。

## 编排版本门

当前线上工具只公开固定 DAG 时：

- 节点必须引用当前场景包已挂载的 Workflow；
- 映射、依赖、delivery 和 `sa_handoff` 使用当前 `workflow_multi` 契约；
- 更新 `workflow_orchestration` 时提交完整对象；
- Hub 保存只形成 `orchestration_static_validated`。

仓库设计稿、集成分支、旧示例或既有资产中出现的新图字段，只能作为需求背景。多入口、用户 Gate、重入、受控循环或多交付能力，必须同时满足：实时 Schema 已公开、服务端返回版本化契约、目标场景包版本兼容。否则保留业务蓝图并记录 `platform_blocked`，禁止把未来图字段混入固定 DAG，或让前端代替 Runtime 执行图。

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
| Preview | 脚本、声明工具和 IO 契约可保存 | 真实 FA 内容和外部副作用正确 |
| 依赖反读 / `test_tool` | 资产状态或代表性供应商返回 | 整条 Workflow 正确 |
| bubble | 当前 Workflow 终态轨迹和接缝行为 | FA 真实内容、未触达分支、整包编排运行 |
| Hub 编排保存 | 当前版本结构、映射和 delivery 静态合法 | 编排真实命中、顺序、handoff 或最终交付 |
| Max 项目日志与交付物 | 被批准路线的真实运行结果 | 未运行路线或未来输入都正确 |

因此分别记录 `asset_contract_validated`、`workflow_bubble_passed`、`orchestration_static_validated`、`orchestration_runtime_verified`、`ui_deployment_verified` 和 `full_validation_skipped`。没有整图运行入口或实际日志时，不能声称 `orchestration_runtime_verified`。
