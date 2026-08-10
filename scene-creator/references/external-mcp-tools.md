# 外部 MCP 工具路由

外部场景包制作模式固定暴露 12 个工具。只使用线上工具 Schema 中实际存在的 action；下表只说明用途和顺序，不能替代 `tools/list`。

| 工具 | 用途 | 重要 action 或规则 |
|---|---|---|
| `workflow_task_manager` | 创建、读取、追加并完成可审计制作工单 | 第一个调用；后续所有审计操作都传 `task_id` |
| `list_assets` | 搜索可复用资产和已完成项目经验 | 只读；`asset_type=experience` 受权限约束且不要求工单 |
| `get_asset` | 读取完整资产或经验契约 | Toolset/Tool Group 返回工具 ID、input/output Schema 和版本；经验页面只读 |
| `get_diagnosis_doc` | 读取服务端共享契约、示例、方案挑战、验收、配置和诊断知识 | 外部调用必须传 `task_id`；审计只保存 topic 和返回文档名，不保存正文；MCP 知识库是共享来源 |
| `dataset_read` | 读取有权限的数据集内容 | 只读；不得导出无关用户数据 |
| `workflow_file_upload` | 把本地辅助文件或 Skill 文件上传到工单 | `prepare → upload → complete`；返回文件受用户和工单隔离 |
| `workflow_dependency_manage` | 创建或维护依赖、Auth Card、普通自定义 TPE，以及直连 MCP 取样 | `test_tool` 会真实调用供应商；审计不保存凭证明文；Workflow TPE 禁止使用 `create_custom_tpe` |
| `scene_package_manage` | 创建、读取、更新并发布场景包 | 先草稿后发布；`workflow_orchestration` 执行完整对象替换 |
| `scene_package_ui_bundle` | 下载共享 UI 模板并维护场景包定制 UI 源码包 | 所有 action 都传 `task_id`；`download_template` 是共享模板，其他上传/读取/下载操作还需 `scene_package_id` |
| `workflow_tpe_manage` | 预览、创建、更新、挂载、发布和 `bubble` Workflow TPE | 创建必须传 `scene_package_id` 和根对象 `output_schema`；`bubble` 首次返回 `run_id`，后续轮询同一运行 |
| `manage_goalfymax_project` | 运行并控制真实 Max 项目 | 传 `workflow_input` 测试 C2；省略时进入普通 SA 对话 |
| `get_project_execution_logs` | 检查日志并获取最终交付物 | `summary/detail` 用于诊断，`outputs/download/bundle` 用于交付 |

## 标准调用顺序

```text
workflow_task_manager(create)
→ get_diagnosis_doc(workflow_authoring, workflow_single)
→ get_diagnosis_doc(workflow_multi)                       # 仅多 Workflow，写任何节点前
→ get_diagnosis_doc(workflow_examples → 匹配的 topic)    # 仅在需要时
→ list_assets / get_asset
→ 读取 Skill 内方案挑战检查清单 → Agent 自检
→ 起草 apc_skill
→ workflow_file_upload(prepare → PUT → complete)          # 可选场景知识文件
→ scene_package_manage(create, offline, apc_skill, skill_file_urls)
→ workflow_dependency_manage(按需复用/创建/授权/取样)
→ workflow_file_upload(prepare → PUT → complete)          # 可选 Workflow ctx.skill_dir 文件
→ workflow_tpe_manage(preview → create)
→ scene_package_manage(update, workflow_orchestration)    # 仅多 Workflow
→ scene_package_ui_bundle(download_template → prepare_upload → complete_upload)  # 可选业务 UI
→ workflow_tpe_manage(bubble start → poll)                # 每个 Workflow 必做
→ 读取 Skill 内 Workflow 验收检查清单 → 逐条 Agent 自检
→ 读取 Skill 内场景包验收检查清单 → 整包 Agent 自检
→ workflow_tpe_manage(update) / scene_package_manage(update)  # 按需修复
→ scene_package_manage(online)
→ 分别询问每个 Workflow 是否全真验证
→ manage_goalfymax_project(run，传 workflow_input)        # 仅批准覆盖所选路径时
→ get_project_execution_logs(summary/detail/outputs/download/bundle)  # 仅真实项目已运行时
→ workflow_task_manager(complete)
```

工单创建后的每个审计调用都必须携带返回的 `task_id`；上面的紧凑路由写法不代表它可以省略。

## ID 和名称纪律

- `task_id`：审计范围，不是资产 ID。
- `scene_package_id`：创建或读取返回的目标场景包 ID。
- `tpe_id`：创建返回的 Workflow 资产 ID。
- `tool_group_id` + `tool_id`：直连 MCP 取样标识。
- `toolset_id`：挂载到 Workflow 的运行时依赖。
- 脚本工具名：使用线上 `name`/`mr_name`，禁止使用资产 ID。
- `project_id`：真实 Max 运行返回的加密 ID；后续 wait/reply/logs 必须复用。
- `run_id`：bubble 验证的不透明 ID，不是项目或沙箱 ID。

## 验证职责边界

- MCP JSON Schema：约束工具参数形状。
- 场景预览：校验脚本 AST、声明工具、input/output/文件契约和确定性字面规则。
- Hub 保存：校验场景包 orchestration 结构和映射。
- 供应商 `test_tool`：获取直连 MCP 真实返回样本，并可校验候选 Schema。
- `bubble` 运行时：FA 使用 Schema 桩值，普通/文件工具真实执行，仅 `shell` 按需创建沙箱。
- Max 运行时：执行真实 FA、默认工具、文件和完整 C2 业务行为。
- Agent：使用 Skill 内的方案挑战、Workflow 验收和场景包验收检查清单负责业务语义、Workflow/Agent 边界、副作用授权、`ctx.dry_run` 守卫位置和修复决策；不调用或虚构 External MCP 未提供的 Battle/Verify FA。`bubble` 中 FA 使用桩值，但 `shell`、`file` 和直连工具仍真实执行。
