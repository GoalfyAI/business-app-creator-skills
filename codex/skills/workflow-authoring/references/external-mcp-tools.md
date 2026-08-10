# External MCP tool routing

The External Workflow profile exposes exactly 12 tools. Use only actions shown by the live tool schema; the summary below explains intent and ordering, not a substitute for `tools/list`.

| Tool | Purpose | Important actions or rules |
|---|---|---|
| `workflow_task_manager` | Open, inspect, append to, and complete the audited work order | Create first; pass `task_id` to every audited operation |
| `list_assets` | Search reusable assets and completed-project experiences | Read-only; `asset_type=experience` is permission scoped and does not require a work order |
| `get_asset` | Read complete asset or experience contracts | Toolset/Tool Group responses include tool ID, input/output Schema, and version; experience pages are read-only |
| `get_diagnosis_doc` | Read server-side shared contracts, examples, Battle, Verify, configuration, and diagnosis documents | External calls require `task_id`; audit stores topic and returned document names, never document bodies; MCP Knowledge is the shared source |
| `dataset_read` | Read permitted dataset content | Read-only; do not export unrelated user data |
| `workflow_file_upload` | Upload local supporting/Skill files into the work order | `prepare → upload → complete`; returned files stay scoped to user and task |
| `workflow_dependency_manage` | Create/manage dependencies, Auth Cards, ordinary custom TPEs, and direct MCP samples | `test_tool` performs a real provider call; credential plaintext is excluded from audit; Workflow TPEs never use `create_custom_tpe` |
| `scene_package_manage` | Create/get/update/publish scenario packages | Draft-first; `workflow_orchestration` is a complete object replacement |
| `scene_package_ui_bundle` | Download the shared UI template and manage a scenario package's customized UI source bundle | Every action requires `task_id`; `download_template` is shared, while prepare/complete/get/download require `scene_package_id` |
| `workflow_tpe_manage` | Preview/create/update/attach/publish and bubble Workflow TPEs | Create requires `scene_package_id` and root-object `output_schema`; bubble start returns `run_id`, later calls poll it |
| `manage_goalfymax_project` | Run and control a real Max project | Pass `workflow_input` to test C2; omit it for normal SA dialogue |
| `get_project_execution_logs` | Inspect logs and retrieve final artifacts | Use summary/detail for diagnosis and outputs/download/bundle for delivery |

## Standard call order

```text
workflow_task_manager(create)
→ get_diagnosis_doc(workflow_authoring, workflow_single)
→ get_diagnosis_doc(workflow_examples → matching topic)  # only when needed
→ list_assets / get_asset
→ get_diagnosis_doc(scene_package_battle) → Agent self-review
→ draft apc_skill
→ workflow_file_upload(prepare → PUT → complete)          # optional scenario knowledge files
→ scene_package_manage(create, offline, apc_skill, skill_file_urls)
→ workflow_dependency_manage(reuse/create/auth/test_tool as needed)
→ workflow_file_upload(prepare → PUT → complete)          # optional Workflow ctx.skill_dir files
→ workflow_tpe_manage(preview → create)
→ get_diagnosis_doc(workflow_multi)                    # multi-Workflow only
→ scene_package_manage(update, workflow_orchestration)  # multi-Workflow only
→ scene_package_ui_bundle(download_template → prepare_upload → complete_upload)  # optional business UI source
→ workflow_tpe_manage(bubble start → poll)               # every Workflow
→ get_diagnosis_doc(workflow_verify) → Agent self-review
→ get_diagnosis_doc(scene_package_verify) → Agent self-review
→ workflow_tpe_manage(update) / scene_package_manage(update) as needed
→ scene_package_manage(online)
→ ask whether to run full validation for every Workflow
→ manage_goalfymax_project(run with workflow_input)      # only when approval covers the selected path
→ get_project_execution_logs(summary/detail/outputs/download/bundle)  # only when a project ran
→ workflow_task_manager(complete)
```

Every audited call after work-order creation carries the returned `task_id`; the compact routing notation above never makes it optional.

## ID and name discipline

- `task_id`: audit scope, not an asset ID.
- `scene_package_id`: target package returned by create/get.
- `tpe_id`: Workflow asset ID returned by create.
- `tool_group_id` + `tool_id`: direct MCP sampling identifiers.
- `toolset_id`: runtime dependency attached to a Workflow.
- script tool name: live `name`/`mr_name`, never an asset ID.
- `project_id`: encrypted ID returned by a real Max run; reuse it for wait/reply/logs.
- `run_id`: opaque bubble validation ID; it is not a project or sandbox identifier.

## Validation ownership

- MCP JSON Schema: tool argument shape.
- Scene preview: script AST, declared tools, input/output/file contracts, deterministic literal checks.
- Hub save: scenario-package orchestration structure and mapping.
- Provider `test_tool`: direct MCP real return sample and optional expected Schema.
- Bubble Runtime: FA Schema stubs, real ordinary/file tools, and shell-only on-demand sandbox evidence.
- Max Runtime: real FA/default tools/files and full C2 business behavior.
- Agent: business meaning, Workflow/Agent boundary, side-effect authorization, `ctx.dry_run` guard placement, and repair decisions. Bubble mode stubs FA but really executes `shell`, `file`, and direct tools.
