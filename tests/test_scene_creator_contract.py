import re
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"


def _skill_frontmatter(content: str) -> dict:
    return yaml.safe_load(content.split("---", 2)[1])


def _local_links(markdown: str) -> list[str]:
    return [
        target
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
        if "://" not in target and not target.startswith("#")
    ]


def test_skill_local_links_resolve():
    skill = SKILL_ROOT / "SKILL.md"
    content = skill.read_text(encoding="utf-8")

    for target in _local_links(content):
        assert (skill.parent / unquote(target)).resolve().is_file(), target


def test_skill_routes_to_server_contracts_and_local_review_checklists():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "MCP 知识库是共享 Workflow 契约和正反例的完整来源" in content
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
    assert skill.index("## 3. Scene Package Model") < skill.index(
        "## 4. Authoring Contracts"
    )
    assert "不要把 Max 内部“场景包助手”的整份系统提示词复制进本 Skill" in skill

    for required_model in (
        "场景包不是一段长提示词、一个工具列表、一张配置表",
        "### 3.3 Information Ownership and Single Source of Truth",
        "### 3.4 Choosing Workflow, TaskAgent, FastAgent, or Direct Execution",
        "Workflow",
        "普通任务点 / TaskAgent",
        "FastAgent",
        "### 3.5 Route Diversity and Archive-Guided Execution",
        "### 3.7 Runtime Scene Skill Quality",
        "### 3.8 Evidence Chains for Creation, Diagnosis, and Optimization",
        "### 3.9 Knowledge Boundaries",
    ):
        assert required_model in skill


def test_skill_has_progressive_reference_index_prerequisites_and_hard_gates():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "本文件是完整制作主流程" in skill
    for reference in (
        "external-mcp-tools.md",
        "方案挑战检查清单.md",
        "Workflow验收检查清单.md",
        "业务界面制作契约.md",
        "业务界面验收检查清单.md",
        "场景包验收检查清单.md",
    ):
        assert f"references/{reference}" in skill
    assert "上述路径相对于本 `SKILL.md` 所在目录" in skill
    assert "## Prerequisites" in skill
    assert "**Required MCP Server**：`scene-creator`" in skill
    assert "远端，不能直接读取或写入当前 Agent 的本地文件系统" in skill
    assert "## 2. Core Constraints (violation = task failure)" in skill
    assert "## 8. Common Issues and Recovery" in skill


def test_each_reference_declares_its_scope_as_a_supplement():
    references = sorted((SKILL_ROOT / "references").glob("*.md"))

    assert references
    for reference in references:
        content = reference.read_text(encoding="utf-8")
        assert "本文是 `SKILL.md` 的" in content, reference.name
        assert "\n---\n" in content, reference.name


def test_embedded_scene_package_domain_model_excludes_max_runtime_protocols():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    model = skill.split("## 3. Scene Package Model", 1)[1].split(
        "## 4. Authoring Contracts", 1
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

    assert skill.index("## 5. User Collaboration and Intent Routing") < skill.index(
        "### 7.1 创建一个可审计工单"
    )
    for communication_rule in (
        "场景包业务顾问",
        "渐进式访谈",
        "关键节点确认",
        "用业务语言展示方案",
        "问题及时透明",
        "不做确认机器",
        "变更可审阅",
    ):
        assert communication_rule in skill
    for route in (
        "创建模式",
        "诊断模式",
        "优化模式",
        "续作模式",
        "Workflow 资产任务",
        "分析这个项目的执行日志",
    ):
        assert route in skill
    for gap in (
        "意图缺失",
        "关键业务参数缺失",
        "知识缺失",
        "可选偏好缺失",
        "授权缺失",
    ):
        assert gap in skill
    for context_item in (
        "业务目标",
        "业务里程碑",
        "输入与产出",
        "参考证据",
        "权限和副作用",
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
        'workflow_task_manager(action="get", task_id=<task_id>)',
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
        "workflow_task_manager",
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
        "## Prerequisites",
        "### 1.1 When to Use Scene Creator",
        "### 1.2 Capabilities",
        "### 1.3 Intent Routing",
        "## 6. Tool Overview",
        "### 6.2 Validation Responsibilities",
        "### 6.3 Core Call Chain",
        "## 7. Execution Flows",
        "## 8. Common Issues and Recovery",
    ):
        assert heading in skill

    expected_tools = {
        "workflow_task_manager",
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
    overview = skill.split("### 6.1 MCP Tools", 1)[1].split(
        "### 6.2 Validation Responsibilities", 1
    )[0]
    assert set(re.findall(r"^\| `([^`]+)` \|", overview, flags=re.MULTILINE)) == expected_tools


def test_business_ui_is_co_built_after_workflow_acceptance_and_before_pack_release():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )
    contract = (SKILL_ROOT / "references" / "业务界面制作契约.md").read_text(
        encoding="utf-8"
    )
    checklist = (SKILL_ROOT / "references" / "业务界面验收检查清单.md").read_text(
        encoding="utf-8"
    )

    for reference in ("业务界面制作契约.md", "业务界面验收检查清单.md"):
        assert f"references/{reference}" in skill

    assert skill.index("### 7.9 根据契约和轨迹验收每个 Workflow") < skill.index(
        "### 7.10 按最终 Workflow 契约制作并发布业务界面"
    )
    assert skill.index("### 7.10 按最终 Workflow 契约制作并发布业务界面") < skill.index(
        "### 7.11 验收完整场景包"
    )
    assert routing.index("workflow_tpe_manage(bubble start → poll)") < routing.index(
        "冻结最终 Workflow/编排契约"
    )
    assert routing.index("业务界面验收检查清单") < routing.index(
        "场景包验收检查清单"
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
    assert "只提交顶层 `workflow_input`" in contract
    assert "不得用单 Workflow `workflow.run` 假装执行整包编排" in checklist
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
    assert "强制初始化入口" in skill
    assert "不能用通用 `init_project`、Git 克隆" in skill
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
    assert "### 7.14 按需运行一个真实 Max 业务项目" in skill
    assert "只有用户批准所选场景路径" in skill
    assert "full_validation_skipped" in skill
    assert "禁止虚构 `project_id`" in skill
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
    assert "运行时只有 `continue_as_planned`" in skill
    assert "不存在名为 `resume` 或 `stop` 的 action" in skill


def test_workflow_dependencies_are_online_before_create_and_empty_arrays_do_not_pass():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )
    checklist = (SKILL_ROOT / "references" / "Workflow验收检查清单.md").read_text(
        encoding="utf-8"
    )

    assert skill.index("依赖 Toolset 上线硬门") < skill.index(
        'workflow_tpe_manage(action="create"'
    )
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
        "禁止把制作说明、数字资产 ID",
        "每个上传的场景 Skill 文件提供明确读取时机",
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
        "也不是所有用户只能照走的一条固定 SOP",
        "通往业务终点的路线地图",
        "实体档案",
        "情境档案",
        "只读取足以影响本次选路的内容",
        "实质改变本次执行的路线、参数、优先级或解释",
        "用户明确表达和当前有效约束优先",
        "Agent 推断必须标为假设",
        "场景包不能直接修改用户档案",
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

    assert skill.index("### 3.5 Route Diversity and Archive-Guided Execution") < skill.index(
        "### 3.7 Runtime Scene Skill Quality"
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
        "线上资产复用",
        "工具契约发现与真实取样",
        "输入输出 Schema",
        "辅助文件交付",
        "场景编排",
        "bubble 验证",
        "业务界面制作与发布",
        "可选全真项目验证",
        "日志与交付物检查",
        "最终发布",
    ):
        assert capability in skill_description
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
