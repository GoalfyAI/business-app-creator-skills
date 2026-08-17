import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"
CONTRACT_SCRIPT = ROOT / "scripts" / "check_mcp_tool_contract.py"
CONTRACT_SPEC = importlib.util.spec_from_file_location("mcp_contract", CONTRACT_SCRIPT)
assert CONTRACT_SPEC and CONTRACT_SPEC.loader
mcp_contract = importlib.util.module_from_spec(CONTRACT_SPEC)
CONTRACT_SPEC.loader.exec_module(mcp_contract)


def _skill_frontmatter(content: str) -> dict:
    return yaml.safe_load(content.split("---", 2)[1])


def _local_links(markdown: str) -> list[str]:
    return [
        target
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
        if "://" not in target and not target.startswith("#")
    ]


def test_live_contract_checker_reads_same_twelve_tool_profile():
    assert mcp_contract.documented_tool_names() == {
        "task_manager",
        "list_assets",
        "get_asset",
        "get_diagnosis_doc",
        "dataset_read",
        "workflow_file_upload",
        "workflow_dependency_manage",
        "scene_package_manage",
        "scene_package_ui_bundle",
        "workflow_tpe_manage",
        "manage_goalfymax_project",
        "get_project_execution_logs",
    }


def test_live_contract_checker_decodes_json_and_sse_tools_list():
    payload = {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
    encoded = json.dumps(payload).encode("utf-8")

    assert mcp_contract._decode_mcp_payload(encoded, "application/json") == payload
    assert mcp_contract._decode_mcp_payload(
        b"event: message\ndata: " + encoded + b"\n\n", "text/event-stream"
    ) == payload


def test_skill_local_links_resolve():
    skill = SKILL_ROOT / "SKILL.md"
    content = skill.read_text(encoding="utf-8")

    for target in _local_links(content):
        assert (skill.parent / unquote(target)).resolve().is_file(), target


def test_skill_routes_to_server_contracts_and_local_review_checklists():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "当前 MCP `tools/list` 中的工具名、action、参数和必填字段" in content
    assert "references/contracts/" not in content
    for topic in (
        "workflow_authoring",
        "workflow_single",
        "workflow_multi",
        "workflow_examples",
    ):
        assert f'topic="{topic}"' in content or f'`{topic}`' in content

    for filename, marker in (
        ("方案挑战检查清单.md", "承接 Max `csp_battle_reviewer` 的职责"),
        ("Workflow验收检查清单.md", "承接 Max `workflow_verify_fa` 的职责"),
        ("场景包验收检查清单.md", "承接 Max `csp_verify_checker` 的职责"),
    ):
        assert f"references/{filename}" in content
        reference = (SKILL_ROOT / "references" / filename).read_text(encoding="utf-8")
        assert marker in reference
        assert "不调用 FastAgent" in reference

    for obsolete_topic in ("scene_package_battle", "workflow_verify", "scene_package_verify"):
        assert f'topic="{obsolete_topic}"' not in content


def test_external_skill_embeds_scene_package_domain_model_before_tool_procedure():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert not (SKILL_ROOT / "references" / "场景包核心模型.md").exists()
    assert skill.index("## 六、场景包核心模型") < skill.index(
        "## 七、创建场景包"
    )
    assert "`scene-creator` 是场景包全生命周期 MCP" in skill

    for required_model in (
        "场景包是围绕明确业务终点组织的运行时能力包",
        "### 信息只写在正确层级",
        "### 资产角色与执行形态",
        "Workflow",
        "普通任务点 / TaskAgent",
        "FastAgent",
        "### 场景包是一张路线地图",
        "### 用业务档案支持个性化选路",
        "### `apc_skill` 的职责",
    ):
        assert required_model in skill


def test_skill_has_progressive_reference_index_prerequisites_and_hard_gates():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "## 十二、参考资料索引" in skill
    for reference in (
        "external-mcp-tools.md",
        "方案挑战检查清单.md",
        "Workflow验收检查清单.md",
        "业务界面制作契约.md",
        "业务界面验收检查清单.md",
        "场景包验收检查清单.md",
    ):
        assert f"references/{reference}" in skill
    assert "以上路径相对于本 `SKILL.md` 所在目录" in skill
    assert "## 一、使用条件与接入方式" in skill
    assert "MCP Server：`scene-creator`" in skill
    assert "外部 MCP 运行在远端，本地文件通过预签名传输流程交接" in skill
    assert "## 九、场景包资产操作规范" in skill
    assert "## 十一、异常处理与恢复" in skill


def test_each_reference_declares_its_scope_as_a_supplement():
    references = sorted((SKILL_ROOT / "references").glob("*.md"))

    assert references
    for reference in references:
        content = reference.read_text(encoding="utf-8")
        assert "本文是 `SKILL.md` 的" in content, reference.name
        assert "\n---\n" in content, reference.name


def test_embedded_scene_package_domain_model_excludes_max_runtime_protocols():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    model = skill.split("## 六、场景包核心模型", 1)[1].split(
        "## 七、创建场景包", 1
    )[0]

    for max_runtime_rule in (
        "GOALFYAI_STATE_",
        "project_plan",
        "memory_maintainer",
        "sandbox_manage",
        "agent_wait",
        "csp_battle_reviewer",
        "workflow_verify_fa",
        "project_create_taskpoint_event",
    ):
        assert max_runtime_rule not in model


def test_external_skill_preserves_scene_creator_intent_routing_without_max_state_machine():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert skill.index("## 三、工作方式与交互协议") < skill.index(
        "### 6. 创建可审计工单"
    )
    for communication_rule in (
        "业务顾问式工作方式",
        "渐进式访谈",
        "在方案、权限、副作用、发布和资金消耗等关键节点获得用户确认",
        "方案展示采用业务语言",
        "问题在发现时透明说明",
        "安全默认明确记录适用条件和影响",
        "修改前提供清晰的改前、改后和影响范围",
    ):
        assert communication_rule in skill
    for route in (
        "创建 |",
        "诊断 |",
        "优化 |",
        "续作 |",
        "Workflow",
        "分析项目执行日志",
    ):
        assert route in skill
    for gap in (
        "意图缺失",
        "关键业务参数缺失",
        "平台知识缺失",
        "可选偏好缺失",
        "用户授权缺失",
    ):
        assert gap in skill
    for context_item in (
        "业务目标",
        "业务里程碑",
        "输入与产出",
        "参考证据",
        "权限与副作用",
        "验收标准",
    ):
        assert context_item in skill

    for max_state_protocol in (
        "GOALFYAI_STATE_FOG",
        "GOALFYAI_STATE_PLAN",
        "GOALFYAI_STATE_EXEC",
        "GOALFYAI_STATE_BLOCK",
        "GOALFYAI_STATE_DELIVER",
    ):
        assert max_state_protocol not in skill


def test_external_skill_uses_only_external_procedure_names():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for external_operation in (
        'task_manager(action="get", task_id=<task_id>)',
        'workflow_dependency_manage(action="test_tool", task_id=<task_id>',
        'workflow_tpe_manage(action="bubble", task_id=',
        'manage_goalfymax_project(action="run", task_id=<task_id>',
        'scene_package_manage(action="online", task_id=<task_id>',
    ):
        assert external_operation in content

    for max_only_name in (
        "script_file",
        "workflow_verify_fa",
        "project_create_taskpoint_event",
    ):
        assert max_only_name not in content


def test_external_tool_reference_tracks_exact_profile():
    content = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )
    expected_tools = {
        "task_manager",
        "list_assets",
        "get_asset",
        "get_diagnosis_doc",
        "dataset_read",
        "workflow_file_upload",
        "workflow_dependency_manage",
        "scene_package_manage",
        "scene_package_ui_bundle",
        "workflow_tpe_manage",
        "manage_goalfymax_project",
        "get_project_execution_logs",
    }
    documented_tools = set(re.findall(r"^\| `([^`]+)` \|", content, flags=re.MULTILINE))

    assert documented_tools == expected_tools
    assert "当前线上 `tools/list` 为唯一真相" in content
    assert "不复制完整参数 Schema" in content
    assert "不要求工具数量永远不变" in content


def test_skill_opens_or_recovers_scene_task_before_other_business_calls():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    for content in (skill, routing):
        assert "task_manager" in content
        assert "workflow_task_manager" not in content
        assert 'action="list"' in content or "task_manager(create|get|list)" in content
        assert "必须等待" in content or "必须先等待" in content
        assert "list_assets" in content
        assert "task_id/op_summary" in content
        assert "项目执行日志" in content
        assert "skill_version" in content
        assert "continued_from_task_id" in content
        assert "WORKFLOW_TASK_MODE_MISMATCH" in content


def test_skill_has_platform_discovery_metadata_and_data_style_sections():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = _skill_frontmatter(skill)
    required_keywords = {
        "scene package",
        "scenario package",
        "场景包",
        "workflow",
        "business UI",
        "业务界面",
        "GoalfyMax",
        "MCP",
        "business archive",
        "业务档案",
        "personalized routes",
        "个性化选路",
    }

    assert frontmatter["name"] == "scene-creator"
    assert "[skill-version:v" in frontmatter["description"]
    assert required_keywords <= set(frontmatter["keywords"])
    assert len(frontmatter["keywords"]) == len(set(frontmatter["keywords"]))
    for heading in (
        "## 一、使用条件与接入方式",
        "## 二、MCP 定位与职责",
        "## 三、工作方式与交互协议",
        "## 四、意图识别与任务启动",
        "## 五、运行前能力准备与规划",
        "## 六、场景包核心模型",
        "## 七、创建场景包",
        "## 八、诊断和优化场景包",
        "## 九、场景包资产操作规范",
        "## 十、验证、发布与交付",
        "## 十一、异常处理与恢复",
        "## 十二、参考资料索引",
    ):
        assert heading in skill

    expected_tools = {
        "task_manager",
        "list_assets",
        "get_asset",
        "get_diagnosis_doc",
        "dataset_read",
        "workflow_file_upload",
        "workflow_dependency_manage",
        "scene_package_manage",
        "scene_package_ui_bundle",
        "workflow_tpe_manage",
        "manage_goalfymax_project",
        "get_project_execution_logs",
    }
    overview = skill.split("## 九、场景包资产操作规范", 1)[1].split(
        "## 十、验证、发布与交付", 1
    )[0]
    assert set(re.findall(r"^\| `([^`]+)` \|", overview, flags=re.MULTILINE)) == expected_tools


def test_business_ui_is_optional_and_independent_from_workflow():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    contract = (SKILL_ROOT / "references" / "业务界面制作契约.md").read_text(
        encoding="utf-8"
    )
    checklist = (SKILL_ROOT / "references" / "业务界面验收检查清单.md").read_text(
        encoding="utf-8"
    )

    for reference in ("业务界面制作契约.md", "业务界面验收检查清单.md"):
        assert f"references/{reference}" in skill

    assert "业务界面由开发者根据场景交互需求开发并发布" in skill
    assert "通过 `entry_url` 与场景包关联" in skill
    assert "它可以服务普通 SA、单 Workflow、多 Workflow或展示与管理交互" in skill
    assert skill.index("### 12. 按需制作业务界面") < skill.index(
        "## 十、验证、发布与交付"
    )

    for action in (
        "download_template",
        "prepare_upload",
        "complete_upload",
        "deploy",
        "status",
        "get",
    ):
        assert action in contract
    assert "业务界面是场景包面向用户的专属操作层" in contract
    assert "业务界面没有暴露 MCP 工具" in checklist
    assert "MCP 工具清单只服务制作 Agent" in contract


def test_business_ui_template_download_is_a_mandatory_initialization_gate():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    contract = (SKILL_ROOT / "references" / "业务界面制作契约.md").read_text(
        encoding="utf-8"
    )
    checklist = (SKILL_ROOT / "references" / "业务界面验收检查清单.md").read_text(
        encoding="utf-8"
    )
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    assert 'scene_package_ui_bundle(action="download_template"' in skill
    assert "返回的当前官方模板初始化项目" in skill
    for response_field in (
        "file_name",
        "size_bytes",
        "download_url",
        "expires_in",
    ):
        assert response_field in contract
    for required_file in (
        "AGENTS.md",
        "README.md",
        "schema/README.md",
        "src/sdk/docs/README.md",
    ):
        assert required_file in contract
    assert "路径穿越" in contract
    assert "唯一包含 `goalfy-app.json`" in contract
    assert "不得用通用 `init_project` 或 Git 克隆替代" in routing
    assert "模板实际字节数与响应一致" in checklist


def test_full_validation_is_optional_and_skips_are_audited():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    assert "预览 → `bubble` → 语义验收 → 可选全真跑" in skill
    assert "### 可选的真实 Max 项目验证" in skill
    assert "必须在用户批准后执行" in skill
    assert "full_validation_skipped" in skill
    assert "复用返回的 `project_id`" in skill
    assert "用户跳过真实项目时，记录 `full_validation_skipped`" in skill
    assert "发布完成后必须调用 `manage_goalfymax_project" not in skill
    assert "仅批准覆盖所选路径时" in routing


def test_external_review_order_and_runtime_actions_match_current_contract():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    assert routing.index("get_diagnosis_doc(workflow_multi)") < routing.index(
        "workflow_tpe_manage(preview → create)"
    )
    assert routing.index("Workflow 验收检查清单") < routing.index("场景包验收检查清单")
    assert routing.index("场景包验收检查清单") < routing.index("分别询问每个 Workflow")
    assert "运行时控制动作来自当前服务端契约" in skill


def test_workflow_dependencies_are_online_before_create_and_empty_arrays_do_not_pass():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )
    checklist = (SKILL_ROOT / "references" / "Workflow验收检查清单.md").read_text(
        encoding="utf-8"
    )

    assert "依赖 Toolset 上线硬门" in skill
    assert 'get_asset` 反读确认每个 Toolset 的 `is_online=true`' in skill
    assert routing.index("workflow_dependency_manage(online_toolsets)") < routing.index(
        "workflow_tpe_manage(preview → create)"
    )
    assert "空数组未执行循环而放行" in checklist
    assert "items.properties" in checklist


def test_runtime_apc_skill_and_file_handoff_rules_remain_in_procedure():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for required_rule in (
        "场景包解决什么问题、共同业务终点是什么、何时使用",
        "业务里程碑，以及每阶段目标",
        "制作说明、调试记录和发布步骤",
        "必须在 `apc_skill` 中给出明确读取时机",
        'workflow_file_upload(action="prepare", task_id=<task_id>',
        'workflow_file_upload(action="complete", task_id=<task_id>',
        'workflow_file_upload(action="from_url", task_id=<task_id>',
        'skill_files_mode="merge"',
    ):
        assert required_rule in content


def test_scene_package_routes_are_personalized_by_business_archives():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    checklist = (SKILL_ROOT / "references" / "场景包验收检查清单.md").read_text(
        encoding="utf-8"
    )

    for principle in (
        "场景包根据用户状态选择路线",
        "场景包是一张路线地图",
        "实体档案",
        "情境档案",
        "只读取足以影响本次选路的内容",
        "实质改变本次执行的路线、参数、优先级或解释",
        "用户当前明确表达和有效约束优先",
        "Agent 推断以假设标注",
        "通过现有投稿与审稿机制形成候选事实",
    ):
        assert principle in skill

    for apc_gate in (
        "共同业务终点",
        "候选路线",
        "业务档案选路规则",
        "具体私有档案事实",
        "唯一 SOP",
        "最小充分信息",
        "现有投稿与审稿机制",
    ):
        assert apc_gate in skill or apc_gate in checklist

    assert skill.index("### 场景包是一张路线地图") < skill.index(
        "### `apc_skill` 的职责"
    )


def test_skill_and_agent_metadata_use_chinese():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )
    metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert "name: scene-creator" in skill
    assert "# 场景包制作" in skill
    assert "# 外部 MCP 工具路由" in reference
    assert 'display_name: "场景包制作"' in metadata
    assert "$scene-creator" in metadata
    skill_description = _skill_frontmatter(skill)["description"]
    for capability in (
        "业务顾问式访谈",
        "线上资产",
        "场景 Skill",
        "普通任务点",
        "Toolset",
        "FastAgent",
        "Dataset",
        "Workflow",
        "业务界面",
        "真实项目复盘",
    ):
        assert capability in skill_description
    for forbidden_positioning in (
        "Workflow 只是",
        "核心职责不是",
        "默认目标",
        "不是本 Skill",
        "你是",
    ):
        assert forbidden_positioning not in skill
    for stale_english in (
        "Follow the External procedure",
        "Load knowledge progressively",
        "Standard call order",
        "Validation ownership",
    ):
        assert stale_english not in skill
        assert stale_english not in reference


def test_openai_metadata_declares_implicit_invocation_and_mcp_dependency():
    metadata = yaml.safe_load(
        (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )

    assert metadata["policy"]["allow_implicit_invocation"] is True
    assert metadata["interface"]["brand_color"] == "#6366F1"
    assert metadata["dependencies"]["tools"] == [
        {
            "type": "mcp",
            "value": "scene-creator",
            "transport": "streamable_http",
            "url": "https://workflow-mcp.qa.goalfyai.com/mcp",
            "bearer_token_env_var": "SCENE_CREATOR_API_KEY",
        }
    ]
