# 外部 MCP 工具路由

> 本文是 `SKILL.md` 的补充工具指南。开始任何场景包制作、诊断或优化任务时读取；它提供完整能力清单和稳定调用关系，但不替代实时 `tools/list`。

---

下表是外部场景包制作工具的语义路由。工具名、action 和参数以当前线上 `tools/list` 为唯一真相；本文只说明用途和顺序，不复制完整参数 Schema，也不要求工具数量永远不变。

| 工具 | 用途 | 重要 action 或规则 |
|---|---|---|
| `task_manager` | 创建、查找、读取、追加并完成统一的场景包制作工单 | 新任务先 `create`；已知任务先 `get`；续作未知 ID 先 `list`；拿到结果前不并行调用其他业务工具 |
| `list_assets` | 搜索可复用资产和已完成项目经验 | 只读；`asset_type=experience` 受权限约束且不要求工单 |
| `get_asset` | 读取完整资产或经验契约 | Toolset/Tool Group 返回工具 ID、input/output Schema 和版本；经验页面只读 |
| `get_diagnosis_doc` | 读取服务端共享契约、示例、方案挑战、验收、配置和诊断知识 | 外部调用必须传 `task_id`；审计只保存 topic 和返回文档名，不保存正文；MCP 知识库是共享来源 |
| `dataset_read` | 读取有权限的数据集内容 | 只读；不得导出无关用户数据 |
| `workflow_file_upload` | 把本地辅助文件或 Skill 文件上传到工单 | `prepare → upload → complete`；返回文件受用户和工单隔离 |
| `workflow_dependency_manage` | 创建或维护依赖、Auth Card、普通自定义 TPE，以及直连 MCP 取样 | `test_tool` 会真实调用供应商；审计不保存凭证明文；Workflow TPE 禁止使用 `create_custom_tpe` |
| `scene_package_manage` | 创建、读取、更新并发布场景包 | 先草稿后发布；`workflow_orchestration` 执行完整对象替换 |
| `scene_package_ui_bundle` | 下载共享 UI 模板，维护、部署并反读场景包定制 UI 源码包 | 所有 action 都传 `task_id`；业务界面开发必须以 `download_template` 为初始化入口并消费返回的 `data.file_name/size_bytes/download_url/expires_in`，不得用通用 `init_project` 或 Git 克隆替代；其余 action 按实时 Schema 使用 `prepare_upload/complete_upload/get/download/deploy/status` 并绑定 `scene_package_id` |
| `workflow_tpe_manage` | 预览、创建、更新、挂载、发布和 `bubble` Workflow TPE | 创建必须传 `scene_package_id` 和根对象 `output_schema`；`bubble` 首次返回 `run_id`，后续轮询同一运行 |
| `manage_goalfymax_project` | 运行并控制真实 Max 项目 | 传 `workflow_input` 测试 C2；省略时进入普通 SA 对话 |
| `get_project_execution_logs` | 检查日志并获取最终交付物 | `summary/detail` 用于诊断，`outputs/download/bundle` 用于交付 |

## 标准调用顺序

```text
task_manager(create|get|list)                              # 工单 Gate，必须先等待结果
→ get_diagnosis_doc(workflow_authoring, workflow_single)
→ get_diagnosis_doc(workflow_multi)                       # 仅多 Workflow，写任何节点前
→ get_diagnosis_doc(workflow_examples → 匹配的 topic)    # 仅在需要时
→ list_assets / get_asset
→ 读取 Skill 内方案挑战检查清单 → Agent 自检
→ 起草 apc_skill
→ workflow_file_upload(prepare → PUT → complete)          # 可选场景知识文件
→ scene_package_manage(create, offline, apc_skill, skill_file_urls)
→ workflow_dependency_manage(按需复用/创建/授权/取样)
→ get_asset(toolset) → workflow_dependency_manage(online_toolsets) → get_asset(is_online=true)  # Workflow 依赖必须在 create 前上线反读
→ workflow_file_upload(prepare → PUT → complete)          # 可选 Workflow ctx.skill_dir 文件
→ workflow_tpe_manage(preview → create)
→ scene_package_manage(update, workflow_orchestration)    # 仅多 Workflow
→ workflow_tpe_manage(bubble start → poll)                # 每个 Workflow 必做
→ 读取 Skill 内 Workflow 验收检查清单 → 逐条 Agent 自检
→ 冻结最终 Workflow/编排契约
→ 读取业务界面制作契约 → scene_package_ui_bundle(download_template → prepare_upload → complete_upload → deploy/status → get)  # business_ui=required 时
→ 读取 Skill 内业务界面验收检查清单 → Agent 自检       # business_ui=required 时
→ 读取 Skill 内场景包验收检查清单 → 整包 Agent 自检
→ workflow_tpe_manage(update) / scene_package_manage(update)  # 按需修复
→ scene_package_manage(online)
→ 分别询问每个 Workflow 是否全真验证
→ manage_goalfymax_project(run，传 workflow_input)        # 仅批准覆盖所选路径时
→ get_project_execution_logs(summary/detail/outputs/download/bundle)  # 仅真实项目已运行时
→ task_manager(complete)
```

新任务第一项业务调用必须是 `task_manager(create)`，并按任务模式传 `mode`；write 工单还必须传当前 Skill description 中的完整 `skill_version`。已知 `task_id` 的续作先 `get`；明确续作但未知 ID 时先 `list`，唯一匹配后再 `get`、无匹配才 `create`、多个候选则请用户选择。上述 Gate 的结果返回前不得并行调用制作契约、资产搜索或修改工具，服务端拒绝只作为兜底。

read 工单转入任何写操作时，必须新建 write 工单，并传 `continued_from_task_id` 与当前 `skill_version`；遇到 `WORKFLOW_TASK_MODE_MISMATCH` 按服务端返回的实际/必需模式纠正。`SCENE_SKILL_UPGRADE_REQUIRED` 必须保持写阻断并严格使用返回的 Codeup 精确 ref 与平台安装根目录升级，不猜测下载来源。

工单建立后的每个**需要审计**的调用都必须携带返回的 `task_id`；`list_assets/get_asset` 是例外，它们不接收 `task_id/op_summary`，也不形成逐次工具审计。影响后续制作的资产选择结论通过 `task_manager(insert)` 写入检查点。Max 项目内的 shell、file、FA、消息和规划执行保留在项目执行日志中，工单只记录阶段结论，不复制其内部日志。

MCP 协议已经通过 `tools/list` 暴露实时工具清单，不再增加平行的 `list_tools` 业务工具。Skill 只维护稳定的能力路由；浏览器中的业务界面不接收这份 MCP 清单，只使用宿主 SDK 和公开运行契约。

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
