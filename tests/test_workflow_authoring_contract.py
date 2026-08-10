import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "workflow-authoring"


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

    assert "MCP Knowledge is the complete source" in content
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
    assert "External Workflow profile exposes exactly 12 tools" in content


def test_full_validation_is_optional_and_skips_are_audited():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    routing = (SKILL_ROOT / "references" / "external-mcp-tools.md").read_text(
        encoding="utf-8"
    )

    assert "Preview → bubble → semantic verification → optional full-run" in skill
    assert "### 13. Optionally run one real Max business project" in skill
    assert "Run this step only when the user approved full validation" in skill
    assert "full_validation_skipped" in skill
    assert "do not invent a `project_id`" in skill
    assert "After publication, call `manage_goalfymax_project" not in skill
    assert "only when approval covers the selected path" in routing


def test_runtime_apc_skill_and_file_handoff_rules_remain_in_procedure():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for required_rule in (
        "what the package solves and when to use it",
        "business milestones, each stage's objective",
        "Do not put authoring instructions, numeric asset IDs",
        "indexes every uploaded scenario Skill file with a concrete read trigger",
        'workflow_file_upload(action="prepare", task_id=<task_id>',
        'workflow_file_upload(action="complete", task_id=<task_id>',
        'workflow_file_upload(action="from_url", task_id=<task_id>',
        'skill_files_mode="merge"',
    ):
        assert required_rule in content
