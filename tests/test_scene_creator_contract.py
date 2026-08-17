import re
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
REFERENCES = SKILL_ROOT / "references"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _skill() -> str:
    return _read(SKILL_PATH)


def _frontmatter(content: str) -> dict:
    return yaml.safe_load(content.split("---", 2)[1])


def _local_links(markdown: str) -> list[str]:
    return [
        target
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
        if "://" not in target and not target.startswith("#")
    ]


def test_skill_is_progressively_disclosed_and_has_minimal_frontmatter():
    content = _skill()
    frontmatter = _frontmatter(content)

    assert set(frontmatter) == {"name", "description"}
    assert frontmatter["name"] == "scene-creator"
    assert "[skill-version:v1.0.5]" in frontmatter["description"]
    assert len(content.splitlines()) < 600
    assert "# 场景包制作与优化" in content
    assert "## 按需参考" in content


def test_skill_local_links_resolve_and_references_declare_scope():
    content = _skill()
    for target in _local_links(content):
        assert (SKILL_ROOT / unquote(target)).resolve().is_file(), target

    expected = {
        "external-mcp-tools.md",
        "方案挑战检查清单.md",
        "Workflow验收检查清单.md",
        "业务界面制作契约.md",
        "业务界面验收检查清单.md",
        "场景包验收检查清单.md",
    }
    assert {path.name for path in REFERENCES.glob("*.md")} == expected
    for path in REFERENCES.glob("*.md"):
        reference = _read(path)
        assert "本文是 `SKILL.md` 的" in reference
        assert "\n---\n" in reference


def test_skill_uses_full_agent_asset_names_instead_of_fa_ta_abbreviations():
    published_text = _skill() + "\n" + "\n".join(
        _read(path) for path in REFERENCES.glob("*.md")
    )

    assert not re.search(r"(?<![A-Za-z])(?:FA|TA)(?![A-Za-z])", published_text)
    assert "FastAgent" in published_text
    assert "TaskAgent" in published_text


def test_authority_order_prefers_live_machine_facts():
    content = _skill()
    assert "当前 MCP `tools/list`、线上资产、服务端校验和 Max Runtime 是机器事实" in content
    assert "`get_diagnosis_doc` 返回的当前契约解释机器事实" in content
    assert "禁止虚构工具、action、ID、Schema、版本、返回字段、资产状态、业务数据或运行证据" in content
    assert "不要把仓库设计稿或集成分支当作线上契约" in content


def test_csp_prompt_business_consultant_rules_are_preserved():
    content = _skill()
    for original_rule in (
        "核心职责不是“快速完成目标”，而是“挖掘需求、确保质量”",
        "代入用户的业务视角，用管理型语言沟通",
        "主动提问和引导，用户往往不知道该提供什么，需要挖掘",
        "基于数据做判断，先用工具收集信息，再做分析和建议",
        "在关键节点与用户确认，但不要变成确认机器",
        "每轮问题聚焦最影响下一步的一至三个事项",
    ):
        assert original_rule in content
    assert "能解决什么、分几阶段、每阶段产出什么、哪里需要用户决定" in content
    assert "不要展示资产 ID、技术字段、代码或内部调用链" in content


def test_csp_prompt_intent_gaps_and_progressive_interview_are_preserved():
    content = _skill()
    for gap_rule in (
        "**意图缺失**",
        "必须向用户询问明确目标",
        "**关键参数缺失**",
        "无法启动。必须向用户索要缺失参数",
        "**知识缺失**",
        "属于规划和调查范畴",
        "**可选偏好缺失**",
        "**用户授权缺失**",
    ):
        assert gap_rule in content
    assert "必须对其进行完整阅读和理解后再继续" in content
    assert "严禁只浏览或仅阅读部分内容" in content
    assert "访谈按需组合、不要一次性全问" in content
    for context in (
        "业务场景描述",
        "参考素材",
        "业务边界",
        "成功标准",
        "创建与诊断",
    ):
        assert context in content


def test_nine_stages_have_artifacts_and_explicit_quality_gates():
    content = _skill()
    lifecycle = content.split("## 九阶段制作流程", 1)[1].split(
        "### 诊断与优化如何进入九阶段", 1
    )[0]
    headings = re.findall(r"^### ([1-9])\. (.+)$", lifecycle, re.MULTILINE)
    assert [number for number, _ in headings] == [str(number) for number in range(1, 10)]
    assert lifecycle.count("**阶段产物**") == 9
    assert lifecycle.count("**进入下一阶段的门**") == 8
    assert lifecycle.count("**完成门**") == 1


def test_nine_stages_restore_csp_prompt_discovery_and_design_depth():
    content = _skill()
    for evidence_rule in (
        "参考项目必须三层递进分析，不能只看摘要",
        "**概览层**",
        "**深读层**",
        "**分析层**",
        "有效推进、重复沟通、失败重试和等待",
        "缺知识、缺工具、缺指引、缺前置检查或错误资产边界",
    ):
        assert evidence_rule in content
    for design_rule in (
        "现状 → 理想态 → 配置手段",
        "Focus",
        "泛化",
        "能力覆盖表",
        "工具缺口不可阻塞创建流程",
        "方案是给用户看的，用管理型语言描述",
        "质疑成立就修正",
    ):
        assert design_rule in content
    assert "诊断不是九阶段之外的简化流程" in content
    for diagnostic_layer in (
        "**场景包**",
        "**普通任务点 / Workflow**",
        "**Toolset**",
        "**FastAgent**",
        "**Tool Group / Dataset / UI**",
    ):
        assert diagnostic_layer in content


def test_creation_mode_keeps_the_original_execution_overview_visible():
    content = _skill()
    overview = content.split("### 创建模式的执行子阶段总览", 1)[1].split(
        "### 1. 识别意图、渐进访谈并建立任务", 1
    )[0]
    for collection_step in (
        "**收集子阶段**",
        "业务素材收集",
        "项目深度分析",
        "三层递进阅读",
        "里程碑提炼",
        "理想态构建与价值预测",
        "Focus / 泛化",
    ):
        assert collection_step in overview
    for orchestration_step in (
        "**编排子阶段**",
        "能力摸底",
        "架构方案设计",
        "Battle 审查",
        "用户确认",
        "执行创建",
        "创建后联动校验",
        "逐条 bubble → 逐条读取 [Workflow 验收检查清单]",
        "最终 Verify",
        "由当前 Agent 完成整包完整性和一致性验收",
    ):
        assert orchestration_step in overview
    assert "不得因九阶段已经包含这些动作而删除本总览" in overview
    assert "scene-creator 外部 MCP 不暴露、也不能调用" in overview

    diagnosis = content.split("### 诊断模式的执行子阶段总览", 1)[1].split(
        "### 1. 识别意图、渐进访谈并建立任务", 1
    )[0]
    for diagnosis_step in (
        "问题收集",
        "逐层诊断",
        "诊断报告",
        "执行修复",
        "读取 [场景包验收检查清单]",
        "再创建测试项目试运行",
    ):
        assert diagnosis_step in diagnosis


def test_skill_granularity_is_tied_to_observed_bottlenecks():
    content = _skill()
    assert "从理想态反推 Skill 颗粒度" in content
    assert "凡是希望减少的失败、绕行或沟通轮次" in content
    for bottleneck in (
        "不知道先做什么",
        "不知道工具如何搭配",
        "不知道参数或字段怎样准备",
        "找不到能力",
        "缺领域知识",
        "交付结果不稳定",
    ):
        assert bottleneck in content
    for empty_instruction in (
        "“完善流程”",
        "“调用相关工具”",
        "“输出高质量报告”",
    ):
        assert empty_instruction in content


def test_task_manager_is_the_canonical_first_business_gate():
    content = _skill()
    routing = _read(REFERENCES / "external-mcp-tools.md")

    assert 'task_manager(action="create", mode=...)' in content
    assert 'task_manager(action="get")' in content
    assert 'task_manager(action="list")' in content
    assert "完整 `skill_version`" in content
    assert "`read` 诊断转入修复时新建 `write` 工单" in content
    assert "Gate 成功后再读取服务端制作契约、搜索资产、规划或写入" in content
    assert "`list_assets/get_asset` 不接收 `task_id`" in content

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
    documented = set(re.findall(r"^\| `([^`]+)` \|", routing, re.MULTILINE))
    assert documented == expected_tools
    assert "不要虚构平行的 `list_tools`、`scene_package_task_manage` 或 `workflow_task_manager`" in routing
    assert routing.index("task_manager(create/get)") < routing.index("get_diagnosis_doc(scene_package)")
    assert routing.index("get_diagnosis_doc(scene_package)") < routing.index("list_assets / get_asset")


def test_scene_package_route_map_precedes_asset_procedure():
    content = _skill()
    assert content.index("## 场景包模型") < content.index("## 九阶段制作流程")
    for marker in (
        "候选路线",
        "稳定路段",
        "选路节点",
        "到达标准",
        "当前用户表达优先于历史记录",
        "Agent 推断保持为假设",
        "最小充分信息",
    ):
        assert marker in content


def test_asset_form_is_selected_by_responsibility_not_workflow_first():
    content = _skill()
    assert "把场景包作为整体交付，不把某一种资产当成默认答案" in content
    for form in (
        "SA 直接执行",
        "普通任务点 / TaskAgent",
        "FastAgent",
        "单 Workflow",
        "一条无环路线",
        "多路线图编排",
    ):
        assert form in content
    assert "确认需要 Workflow 后读取 `workflow_authoring`" in content
    assert content.index("形成场景包蓝图") < content.index("按需制作普通任务点、Workflow 和编排")


def test_information_ownership_keeps_apc_skill_balanced():
    content = _skill()
    for owner in (
        "Tool Group / 实时工具契约",
        "Toolset 使用指南",
        "FastAgent Prompt",
        "任务点 Prompt",
        "Workflow 脚本与 IO Schema",
        "`workflow_orchestration`",
        "`apc_skill`",
        "场景 Skill 文件",
        "Dataset Skill",
        "业务界面源码和宿主 SDK",
    ):
        assert owner in content
    assert "不要在 `apc_skill` 复制 DAG、工具完整 Schema 或制作说明" in content
    assert "不要因为避免重复而删掉 SA 必须始终知道的业务路由" in content


def test_workflow_and_orchestration_are_version_gated():
    content = _skill()
    routing = _read(REFERENCES / "external-mcp-tools.md")
    checklist = _read(REFERENCES / "场景包验收检查清单.md")

    assert '`schema_version: "2.0"` 的多路线图编排' in content
    assert "每个 Runtime 只执行一个已发布 `orchestration_id`" in content
    assert "服务端 `workflow_single` 和 `workflow_multi` 两份 Workflow 指南" in content
    assert "不能把旧 `schema_version: \"1.0\"`" in content
    assert "中途 `business_interaction`" in checklist
    assert "`delivery.review`" in checklist
    assert "最终交付不再要求 Delivery 节点额外声明 `sa_handoff`" in checklist
    assert "workflow_orchestration` 是完整对象整体替换" in routing
    assert '只接受 `schema_version:"2.0"`' in routing
    assert "orchestration_static_validated" in checklist
    assert "orchestration_runtime_verified" in checklist
    for draft_only_field in ("capability_key", "user_gate", "gate_policy", "reentry_policy"):
        assert draft_only_field not in content
        assert draft_only_field not in routing


def test_every_workflow_scene_package_requires_business_ui():
    content = _skill()
    contract = _read(REFERENCES / "业务界面制作契约.md")
    checklist = _read(REFERENCES / "业务界面验收检查清单.md")

    assert "只要包含至少一个 Workflow" in content
    assert "`business_ui` 记录为 `required`" in content
    assert "完全没有 Workflow 时才能记录 `business_ui=not_required`" in contract
    assert "当前场景包至少挂载一个真实 Workflow" in checklist
    assert "不能服务纯 SA 或只有普通任务点的场景包" in contract
    assert "业务界面只负责公开交互与结果展示，不执行或解释内部 DAG" in content
    assert "不得把包含 Workflow 的场景包改记为 `not_required`" in contract
    assert "包含 Workflow 但业务界面缺失" in _read(REFERENCES / "场景包验收检查清单.md")
    assert "普通 SA、单 Workflow、多 Workflow或展示与管理" not in content
    assert "伪造 Workflow" in contract


def test_business_ui_uses_live_runtime_mode_and_official_template():
    content = _skill()
    contract = _read(REFERENCES / "业务界面制作契约.md")

    assert "单 Workflow" in contract
    assert "2.0 多路线图编排" in contract
    assert "Business/Runtime 启动、状态、交互和 Delivery Review 契约" in contract
    assert "Hub 能保存 2.0 但宿主或模板 SDK 尚未支持" in contract
    assert "download_template" in content
    for field in ("file_name", "size_bytes", "download_url", "expires_in"):
        assert field in contract
    for required_file in (
        "AGENTS.md",
        "README.md",
        "schema/README.md",
        "src/sdk/docs/README.md",
    ):
        assert required_file in contract
    assert "路径穿越" in contract
    assert "唯一包含 `goalfy-app.json`" in contract
    assert "通用 `init_project`" in contract


def test_validation_evidence_is_layered_without_overclaiming():
    content = _skill()
    routing = _read(REFERENCES / "external-mcp-tools.md")
    required = {
        "asset_contract_validated",
        "workflow_bubble_passed",
        "orchestration_static_validated",
        "orchestration_runtime_verified",
        "ui_deployment_verified",
        "full_validation_skipped",
    }
    for evidence in required:
        assert evidence in content
        assert evidence in routing
    assert "缺少整图运行工具或真实日志时只能记录静态通过和运行盲区" in content
    assert "没有整图运行入口或实际日志时，不能声称 `orchestration_runtime_verified`" in routing


def test_full_validation_and_external_side_effects_require_authorization():
    content = _skill()
    assert "只有用户批准覆盖所选路线可能执行的全部 Workflow 后才运行" in content
    assert "跳过时继续交付并记录 `full_validation_skipped`" in content
    assert "发布是外部状态变更" in content
    for action in ("删除资产", "扩大权限", "收费", "真实 Max 全真运行"):
        assert action in content
    assert "复用同一 `project_id`" in content


def test_workflow_semantic_checklist_preserves_runtime_edges():
    checklist = _read(REFERENCES / "Workflow验收检查清单.md")
    assert "不调用 FastAgent" in checklist
    assert "没有终态轨迹只能裁决 `needs_bubble`" in checklist
    assert "FastAgent 使用 Schema 桩" in checklist
    assert "空数组未执行循环而放行" in checklist
    assert "items.properties" in checklist
    assert "重新 Preview、bubble 和验收" in checklist


def test_local_checklists_cover_review_fastagents_when_the_external_mcp_does_not_expose_them():
    content = _skill()
    for filename, marker in (
        ("方案挑战检查清单.md", "承接 Max `csp_battle_reviewer` 的职责"),
        ("Workflow验收检查清单.md", "承接 Max `workflow_verify_fa` 的职责"),
        ("场景包验收检查清单.md", "承接 Max `csp_verify_checker` 的职责"),
    ):
        assert f"references/{filename}" in content
        reference = _read(REFERENCES / filename)
        assert marker in reference
        assert "不调用 FastAgent" in reference
    for obsolete_topic in (
        'topic="scene_package_battle"',
        'topic="workflow_verify"',
        'topic="scene_package_verify"',
    ):
        assert obsolete_topic not in content
    assert "scene-creator 外部 MCP 不暴露、也不能调用" in content
    assert "这些名称只说明三份参考清单承接的审查职责，不是外部工具调用路径" in content


def test_external_skill_does_not_copy_max_internal_state_machine():
    content = _skill()
    for internal_protocol in (
        "GOALFYAI_STATE_FOG",
        "GOALFYAI_STATE_PLAN",
        "GOALFYAI_STATE_EXEC",
        "GOALFYAI_STATE_BLOCK",
        "GOALFYAI_STATE_DELIVER",
        "project_create_taskpoint_event",
        "memory_maintainer",
        "agent_wait",
    ):
        assert internal_protocol not in content


def test_skill_and_agent_metadata_are_chinese_and_invocable():
    content = _skill()
    description = _frontmatter(content)["description"]
    metadata = yaml.safe_load(_read(SKILL_ROOT / "agents" / "openai.yaml"))

    for capability in (
        "场景 Skill",
        "普通任务点",
        "Toolset",
        "FastAgent",
        "Dataset",
        "Workflow",
        "业务界面",
        "真实项目复盘",
    ):
        assert capability in description
    assert metadata["policy"]["allow_implicit_invocation"] is True
    assert "$scene-creator" in metadata["interface"]["default_prompt"]
    assert "为所有 Workflow 配套业务界面" in metadata["interface"]["short_description"]
    assert metadata["dependencies"]["tools"] == [
        {
            "type": "mcp",
            "value": "scene-creator",
            "transport": "streamable_http",
            "url": "https://workflow-mcp.goalfyai.com/mcp",
            "bearer_token_env_var": "SCENE_CREATOR_API_KEY",
        }
    ]
