---
name: workflow-authoring
description: Create, update, validate, and publish GoalfyMax Workflow assets and multi-Workflow scenario packages through the audited External MCP profile. Use when Codex, Claude Code, or another coding agent must turn a business process into Workflow scripts, discover live tool contracts, sample safe MCP returns, define workflow_orchestration or sa_handoff, validate in a real Max project when required, diagnose failures, or maintain an existing Workflow package.
---

# Goalfy Workflow Authoring

Use the External MCP profile to create the same Workflow assets that Max executes. Treat live MCP tool schemas, server validation, and returned asset data as authoritative. Never invent asset IDs, tool names, parameters, schemas, versions, or return fields.

## Load knowledge progressively

1. Read [references/external-mcp-tools.md](references/external-mcp-tools.md) for the External 12-tool routing surface and confirm it against live `tools/list`.
2. Open the Workflow work order before reading server-side contracts.
3. After deciding that the task needs Workflow authoring, call `get_diagnosis_doc(task_id=..., topic="workflow_authoring")` once.
4. Before writing any Workflow script, call `get_diagnosis_doc(task_id=..., topic="workflow_single")` once. Only after deciding that the package needs multiple Workflows, call `get_diagnosis_doc(task_id=..., topic="workflow_multi")` once.
5. When the task uses a specialized primitive or contract, or a Preview, Hub, or Runtime error needs a known repair pattern, read `workflow_examples` once and then fetch only the matching `workflow_example_*` topic.

Do not reread the same topic in one work order. MCP Knowledge is the complete source for shared Workflow contracts and examples. Because external agents load this Skill first, it deliberately repeats a compact set of high-risk guardrails for `apc_skill`, `_output`, files, failures, final contracts, and validation; use MCP Knowledge for the full rule and treat live schemas and server validation as authoritative on conflict.

## Follow the External procedure

### 1. Open one audited work order

Call `workflow_task_manager(action="create", task_name=..., task_description=...)` before the first preview, write, real sample, project run, download, or audit action. Save the returned `task_id` and pass it to every audited operation.

Use `workflow_task_manager(action="get", task_id=<task_id>)` to restore context after interruption. Record concise checkpoints with `workflow_task_manager(action="insert", task_id=<task_id>, entry_type="checkpoint", content=...)` after asset creation and validation; do not copy complete tool inputs, provider outputs, credentials, or logs into the work order.

### 2. Inspect and reuse live assets

Use `list_assets` to find candidate scenario packages, Workflows, Toolsets, Tool Groups, FAs, and datasets. Use `get_asset` for complete current configuration.

For every scripted dependency, collect its live invocation name, owning asset IDs, input schema, visible formal output schema, current version, and Toolset dependency. Do not infer them from manuals, another project, or a previous conversation.

When a completed project contains reusable business knowledge, use `list_assets(asset_type="experience", ...)` and `get_asset(asset_type="experience"|"experience_page", ...)`. Experience data is read-only and remains subject to the current user's Hub permissions.

### 3. Read Battle and challenge the package design

Call `get_diagnosis_doc(task_id=<task_id>, topic="scene_package_battle")`. CC/Codex performs the review itself using the returned contract and current asset evidence. Do not start the historical Beta Battle FastAgent.

Resolve unclear business inputs, unnecessary Workflows, misplaced Agent judgment, unsafe side effects, and missing deliverables before creating the package. Record only the concise conclusion with `workflow_task_manager(action="insert", ...)`.

### 4. Choose the execution form and draft the runtime Skill

Apply the authoring contract to separate fixed stages from Agent judgment. Apply the single-Workflow contract to every script and the multi-Workflow contract only when a fixed DAG is required.

Draft `apc_skill` from the confirmed business milestones before creating assets. Keep only what the runtime Agent must always know:

- what the package solves and when to use it;
- business milestones, each stage's objective and user-visible output, without restating scripted steps;
- required business inputs and the output users should expect;
- which judgments or permissions stay with the Agent or user;
- business rules, system boundaries, and necessary tool guidance only for Agent-controlled work not already scripted;
- which optional scenario knowledge file to read at a named stage.

Do not put authoring instructions, numeric asset IDs, implementation details, or the deterministic `workflow_orchestration` DAG into `apc_skill`. Put long domain rules, templates, examples, or detailed SOPs in scenario Skill files and index each file from `apc_skill` only when it has a concrete read trigger.

Call `scene_package_manage(action="create", task_id=<task_id>, name=..., description=..., apc_skill=...)` once to create the offline draft before creating Workflows. Retain its `scene_package_id`. If later configuration fails, repair the same package with `action="update", task_id=<task_id>`; do not repeat create.

### 5. Prepare only missing dependencies

Reuse existing dependencies whenever possible. Use `workflow_dependency_manage` only when a required Toolset, Tool Group, FA, Auth Card, custom TPE, or Skill file is absent or must be managed for this work order. Auth Card actions are `create_auth_card`, `update_auth_card`, and `link_auth_card`; never copy returned or supplied credential plaintext into checkpoints or logs. Use `create_custom_tpe` only for ordinary custom/predefined TPEs. Workflow TPEs always use `workflow_tpe_manage`.

For an independently callable MCP tool with no trustworthy formal output schema:

1. Confirm the call is read-only or otherwise authorized.
2. Call `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=...)` once with representative input.
3. Draft the smallest step `_output` required by downstream code.
4. Call `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=<fresh input>, expected_output_schema=<candidate>)` again.
5. Record only the contract conclusion and asset version in a checkpoint.

Do not sample destructive, external-publishing, credential-changing, financial, or other irreversible operations without explicit authorization. Do not use `test_tool` for FA, `file`, `shell`, or `send_email`; those require Max runtime context.

### 6. Deliver supporting files and create every Workflow

External MCP accepts the complete script inline. It cannot read a client-local Codex/CC file path or any path from a separate Max project.

If a Workflow references `ctx.skill_dir`, deliver every helper, template, or static sample through the same work order:

1. Call `workflow_file_upload(action="prepare", task_id=<task_id>, file_name=..., relative_path=..., size_bytes=...)`.
2. Upload the exact local bytes with the returned HTTP `PUT` request.
3. Call `workflow_file_upload(action="complete", task_id=<task_id>, file_name=..., relative_path=..., file_key=...)` and collect `data.skill_file`.
4. Pass the collected objects as `skill_file_urls=[...]` to the Workflow create or update call.

For an existing trusted HTTPS file, use `workflow_file_upload(action="from_url", task_id=<task_id>, file_name=..., relative_path=..., source_url=...)`. On Workflow update, reread the existing file list and send the full intended set because `skill_file_urls` replaces that Workflow's Skill directory. Scenario knowledge files use the same handoff but are passed to `scene_package_manage(..., skill_file_urls=[...], skill_files_mode="merge")`; only Workflow helper files are mounted under that Workflow's `ctx.skill_dir`.

For each Workflow:

1. Draft the inline script and root-object input/output schemas under the single-Workflow contract.
2. Call `workflow_tpe_manage(action="preview", task_id=..., script=..., input_schema=..., output_schema=..., preload_toolset_ids=...)`.
3. Fix every returned error at its reported tool, field, line, node, or path. Do not suppress validation.
4. Call `workflow_tpe_manage(action="create", task_id=..., scene_package_id=..., ...)` only after preview passes.
5. Save the returned `tpe_id`; use `action="update"` for all later repairs.

Do not split or duplicate a Workflow merely to bypass a recoverable preview error.

Every create call must include a root-object `output_schema`; a missing, non-object, or invalid JSON Schema is a creation error even when the script can return a value.

### 7. Save one complete multi-Workflow object

After all Workflow IDs exist and are attached to the package, build one complete object under the multi-Workflow contract and call:

```text
scene_package_manage(
  action="update",
  task_id=<task_id>,
  scene_package_id=<scene_package_id>,
  workflow_orchestration=<complete object>
)
```

Use whole-object replacement. The node named by `delivery.node_id` must declare node-level `sa_handoff`: instruct the runtime Agent to read the committed result, deliver a user-facing natural-language response with `message_user(type="result")`, then choose `stop` to prevent compatibility automatic delivery. Apply Hub's exact node, mapping, delivery, or `sa_handoff` error to the same object and resubmit it. Do not copy the DAG into `apc_skill` and do not invent unsupported fields.

### 8. Bubble every Workflow

For each Workflow, call `workflow_tpe_manage(action="bubble", task_id=..., tpe_id=..., workflow_input=<valid object>)` and save the returned `run_id`. Poll the same action with `task_id + run_id` until a terminal state, then inspect `steps`, `run_trace`, `coverage`, `unreached_tools`, `final_output`, and `error`.
Before bubble-running, confirm that direct calls use authorized representative input and that email, notification, publishing, charging, remote-object creation, or formal business-state writes use `ctx.dry_run` only to suppress that external side effect. Do not use `ctx.dry_run` to skip ordinary tools, Schema checks, Workspace pipeline steps, or failures caused by FA stub values.

Bubble is a trusted Max validation run, not local execution. FA steps return Schema stub values and do not start real FAs; ordinary MCP and file tools execute for real. A temporary server sandbox is created only when the script references `shell`, and internal project/sandbox IDs and mount paths are never returned. Treat provider side effects as real and obtain authorization before bubbling destructive or publishing tools. After bubble and semantic verification pass, ask the user separately for every Workflow whether to run FA-real full validation and record each decision. Continue when the user skips it; never substitute the optional full run for mandatory bubble evidence.

### 9. Verify each Workflow from contract and trace

External and Max authoring use the same Preview → bubble → semantic verification → optional full-run lifecycle. Their tool surfaces may differ, but both execute through Max Runtime and apply the same evidence standard. Reuse the checkpointed `project_id` when full project validation is necessary instead of creating a project for every repair.

Call `get_diagnosis_doc(task_id=<task_id>, topic="workflow_verify")`. CC/Codex performs the semantic check itself against the current Workflow asset, preview result, and bubble trace; do not start the historical Workflow Verify FastAgent. Repair the original Workflow and rerun bubble until the evidence meets the contract.

### 10. Verify the complete scenario package

Call `get_diagnosis_doc(task_id=<task_id>, topic="scene_package_verify")`. Check the package Skill, dependency closure, every Workflow contract, `workflow_orchestration`, delivery mapping, and Agent handoff as one unit. Do not start the historical Scene Package Verify FastAgent. Insert the concise Battle/Workflow/Scene verification conclusions into the work order.

### 11. Repair the owning layer

- Live tool argument or return mismatch: reread the asset and repair the call or step contract.
- Workflow preview/runtime failure: update the original Workflow.
- Hub orchestration failure: update the same complete `workflow_orchestration` object.
- Missing runtime tool: verify invocation name, Toolset membership, online state, and preload dependency.
- Missing or untrusted output file: inspect TaskAgent evidence and repair the file source or generation step.
- Uncertain business decision: stop forcing deterministic Workflow and return that stage to the Agent.
- Infrastructure error: retry only when the returned error is explicitly retryable and the action is idempotent.

### 12. Publish the verified package

Before publishing, reread the package and confirm that referenced assets exist, every Workflow has current input/output contracts, any multi-Workflow package has one valid saved orchestration object whose delivery node has the required final `sa_handoff`, deliverable files use workspace paths, and the work order contains concise validation evidence. Confirm that `apc_skill` still matches the final milestones, names every required business input and Agent/user decision, contains no numeric asset IDs or copied DAG, and indexes every uploaded scenario Skill file with a concrete read trigger.

If asset changes made the draft stale, call `scene_package_manage(action="update", task_id=<task_id>, scene_package_id=<scene_package_id>, apc_skill=...)` before publishing. Then call `scene_package_manage(action="online", task_id=<task_id>, scene_package_id=<scene_package_id>)` and reread the online package.

### 13. Optionally run one real Max business project

Run this step only when the user approved full validation for every Workflow that the selected scenario path can execute, or explicitly requested complete business-project evidence. If approval does not cover the whole path, do not start the project. Record `full_validation_skipped` and the remaining FA/content/side-effect blind spots, then continue to close the work order.

When approved, call `manage_goalfymax_project(action="run", task_id=<task_id>, scenario_package_ids=[...], workflow_input=<object>, ...)` after publication. Explicit `workflow_input={}` triggers the deterministic C2 package; omitting the field intentionally runs normal SA dialogue. This run starts the real Max project and real FA/runtime behavior, unlike bubble.

Continue the returned `project_id` with `wait` or `status`. Use `reply` or `confirm` only when Max reports `needs_input=true`; use `send` for a new attempt after an asset update. Do not create a new project for every poll or minor repair.

### 14. Inspect real logs and deliverables when full validation ran

If step 13 ran, call `get_project_execution_logs` with the same `task_id` and `project_id`: use `summary/detail` for execution evidence and `outputs/download/bundle` for true delivery artifacts. Temporary FA files and internal mount paths must not appear. Overall project completion alone is not proof that the intended Workflow and deliverables passed. If full validation was skipped, do not invent a `project_id`, project result, log result, or deliverable result.

### 15. Close the work order

Insert a final checkpoint containing asset IDs and bubble conclusions. Include either the approved real-project result and deliverable summary, or `full_validation_skipped` with the user's decision and remaining blind spots; never include credentials or raw logs. Call `workflow_task_manager(action="complete", task_id=<task_id>)`. Do not claim full-validation evidence when it was skipped, and do not claim auditable completion when mandatory bubble evidence or audit persistence is missing.
