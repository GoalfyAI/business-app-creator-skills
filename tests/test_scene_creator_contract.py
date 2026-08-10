import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"


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


def test_skill_routes_to_server_owned_workflow_knowledge():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "MCP 知识库是共享 Workflow 契约和示例的完整来源" in content
    assert "references/contracts/" not in content
    for topic in (
        "workflow_authoring",
        "workflow_single",
        "workflow_multi",
        "workflow_examples",
        "scene_package_battle",
        "workflow_verify",
        "scene_package_verify",
    ):
        assert f'topic="{topic}"' in content or f'`{topic}`' in content


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
    assert "外部场景包制作模式固定暴露 12 个工具" in content


def test_full_validation_is_optional_and_skips_are_audited():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    assert "预览 → `bubble` → 语义验收 → 可选全真跑" in skill
    assert "### 13. 按需运行一个真实 Max 业务项目" in skill
    assert "只有用户批准所选场景路径" in skill
    assert "full_validation_skipped" in skill
    assert "禁止虚构 `project_id`" in skill
    assert "发布完成后必须调用 `manage_goalfymax_project" not in skill
    assert "仅批准覆盖所选路径时" in routing


def test_runtime_apc_skill_and_file_handoff_rules_remain_in_procedure():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for required_rule in (
        "场景包解决什么问题、何时使用",
        "业务里程碑，以及每阶段目标",
        "禁止把制作说明、数字资产 ID",
        "每个上传的场景 Skill 文件提供明确读取时机",
        'workflow_file_upload(action="prepare", task_id=<task_id>',
        'workflow_file_upload(action="complete", task_id=<task_id>',
        'workflow_file_upload(action="from_url", task_id=<task_id>',
        'skill_files_mode="merge"',
    ):
        assert required_rule in content


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
    for stale_english in (
        "Follow the External procedure",
        "Load knowledge progressively",
        "Standard call order",
        "Validation ownership",
    ):
        assert stale_english not in skill
        assert stale_english not in reference
