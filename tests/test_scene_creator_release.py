import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest
import tomllib
import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "skills" / "business-app-creator"
SCRIPT_PATH = ROOT / "scripts" / "build_platform_packages.py"
PROD_SCRIPT_PATH = ROOT / "scripts" / "register-skill-release.py"

SPEC = importlib.util.spec_from_file_location("scene_creator_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
release_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_module)

PROD_SPEC = importlib.util.spec_from_file_location("prod_release_skill", PROD_SCRIPT_PATH)
assert PROD_SPEC and PROD_SPEC.loader
prod_release_module = importlib.util.module_from_spec(PROD_SPEC)
PROD_SPEC.loader.exec_module(prod_release_module)

PLATFORM_FILES = ("README.md", "AGENTS.md", "UPDATE.md", ".mcp.json")


def _copy_repo(tmp_path: Path) -> Path:
    """复制一份完整仓库结构，返回其中的 Skill 内容目录。"""
    for name in ("skills", "claude-code", "codex", "manus", "generic", ".claude-plugin", ".agents"):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in ("skill-release.json", "pyproject.toml", "uv.lock", "README.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    shutil.copy2(SCRIPT_PATH, tmp_path / "scripts" / SCRIPT_PATH.name)
    return tmp_path / "skills" / "business-app-creator"


def _manifest(skill_root: Path = SKILL_ROOT) -> dict:
    return json.loads((skill_root.parents[1] / "skill-release.json").read_text(encoding="utf-8"))


def _package_version(skill_root: Path = SKILL_ROOT) -> str:
    return _manifest(skill_root)["package_version"]


# ---------------------------------------------------------------- 仓库当前状态


def test_checked_in_release_is_current():
    manifest = release_module.check_release(SKILL_ROOT)

    assert manifest["skill_name"] == "business-app-creator"
    assert release_module._validate_skill_version(manifest["version"]) == manifest["version"]
    assert release_module._validate_package_version(manifest["package_version"])
    assert manifest["scaffold_min_required_version"] == release_module.scaffold_min_required_version(SKILL_ROOT)


def test_scaffold_floor_rejects_missing_or_duplicate_marker(tmp_path):
    skill_root = _copy_repo(tmp_path)
    entry = skill_root / "SKILL.md"
    original = entry.read_text()
    marker = re.search(r"<!-- scaffold-min-required-version:[^\s]+ -->", original).group()
    entry.write_text(original.replace(marker, ""))
    with pytest.raises(release_module.ReleaseError):
        release_module.scaffold_min_required_version(skill_root)
    entry.write_text(original + "\n" + marker)
    with pytest.raises(release_module.ReleaseError):
        release_module.scaffold_min_required_version(skill_root)


def test_all_first_party_package_versions_are_synchronized():
    """四个插件 manifest 与 Python 包版本必须同版本，漏掉任何一个都会让用户收不到更新。"""
    expected = _package_version()
    assert release_module._repository_package_version(SKILL_ROOT) == expected

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == expected
    lock_match = re.search(
        r'name = "business-app-creator-skills"\nversion = "([^"]+)"',
        (ROOT / "uv.lock").read_text(encoding="utf-8"),
    )
    assert lock_match and lock_match.group(1) == expected


def test_plugin_display_metadata_follows_skill_without_changing_identity(tmp_path):
    skill_root = _copy_repo(tmp_path)
    before = {
        relative: json.loads((tmp_path / relative).read_text())
        for relative in release_module.PACKAGE_MANIFESTS
    }
    metadata_path = skill_root / "agents/openai.yaml"
    metadata = yaml.safe_load(metadata_path.read_text())
    metadata["interface"]["display_name"] = "智能应用制作"
    metadata_path.write_text(yaml.safe_dump(metadata, allow_unicode=True))

    release_module.sync_plugin_display_metadata(skill_root)

    for relative, previous in before.items():
        current = json.loads((tmp_path / relative).read_text())
        assert current["name"] == previous["name"]
        assert "业务应用" not in json.dumps(current, ensure_ascii=False)
        assert "skill-version:" not in json.dumps(current)
        plugin = current.get("plugins", [current])[0]
        old_plugin = previous.get("plugins", [previous])[0]
        for field in ("version", "source", "skills", "mcpServers", "author"):
            assert plugin.get(field) == old_plugin.get(field)
        if "interface" in plugin:
            assert plugin["interface"]["displayName"] == "智能应用制作"
        elif "displayName" in plugin:
            assert plugin["displayName"] == "智能应用制作"


def test_every_install_surface_ships_production_endpoint():
    """仓库里的安装物料必须与 PROD_MCP_ENDPOINT 一致（当前约定为 QA），别的环境地址混进来会被这里拦住。"""
    surfaces = [
        *(ROOT / "claude-code").rglob("*"),
        *(ROOT / "codex").rglob("*"),
        SKILL_ROOT / "agents" / "openai.yaml",
    ]
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in surfaces
        if path.is_file() and path.suffix in {".md", ".json", ".yaml"}
    )
    assert release_module.PROD_MCP_ENDPOINT in combined
    # 2026-09-04 起安装物料统一指向生产；不得残留 QA 域名与旧端点
    assert ".qa.goalfyai.cn" not in combined
    assert "workflow-mcp." not in combined
    assert "https://goalfymax.goalfyai.cn/developer/api-keys" in combined


def test_platform_skill_copies_match_the_single_source():
    """四个平台的 Skill 副本必须与唯一源逐字节一致。"""
    release_module.check_platform_skills(SKILL_ROOT)

    canonical = (SKILL_ROOT / "SKILL.md").read_bytes()
    for platform in release_module.PLATFORM_NAMES:
        copy = release_module._platform_skill_dir(SKILL_ROOT, platform) / "SKILL.md"
        assert copy.read_bytes() == canonical, platform
    # 只有 Codex 需要 openai.yaml
    assert (ROOT / "codex/skills/business-app-creator/agents/openai.yaml").is_file()
    for platform in ("claude-code", "manus", "generic"):
        target = release_module._platform_skill_dir(SKILL_ROOT, platform) / "agents"
        assert not target.exists(), platform


def _read(relative: str) -> str:
    return (SKILL_ROOT / relative).read_text(encoding="utf-8")


def _assert_fa_orchestration_guardrails(skill_root: Path) -> None:
    script = (skill_root / "reference/编排脚本.md").read_text(encoding="utf-8")
    for fact in (
        "控制面最小合同",
        "顶层字段不超过 8 个",
        "对象嵌套不超过 2 层",
        "把内容改成稳定载体引用",
        "Schema 只校验形状，不能证明内容真实",
        "事实区与推断区",
        "连续两轮出现时，停止加字段",
    ):
        assert fact in script, fact
    # 控制面收窄不能让用户可见内容只落文件：短内容照常返回，中间文件放 process_dir。 [任务:T-3941]
    assert "`ctx.process_dir` 文件等稳定载体" in script
    assert "给用户看的列表、正文、结论仍以业务字段出现" in script
    assert '"findings": result["findings"]' in script
    assert '"draft_body": draft["draft_body"]' in script
    # 模板二的 blocked 出口会发 stage_failed，契约说明不能让它删掉这条声明；partial 要把 note 带给用户。 [任务:T-3941]
    assert 'event_key="diagnosis_failed"' in script
    assert "模板二、三用到了 `stage_failed`，用模板一时删掉第三条契约" in script
    assert '"status": result["status"], "note": result["note"]' in script
    for exit_contract in (
        "`completed`（全部做完、数据真实）",
        "`partial`（做了一部分，未做的不补不编）",
        "`blocked`（一条没做成，数据字段留空）",
    ):
        assert exit_contract in script, exit_contract

    platform = (skill_root / "reference/平台对象速查.md").read_text(encoding="utf-8")
    assert "一个 FA 只承担一个语义责任" in platform
    assert "编排脚本只做确定性准备、分发、汇合和固定收口" in platform
    assert "编排脚本.md#fa-与脚本的职责边界" in platform

    g4 = (skill_root / "flow/G4-能力制作.md").read_text(encoding="utf-8")
    assert "内容走稳定载体引用" in g4
    assert "同类错误连续两轮就停止扩 Schema" in g4


def test_single_skill_follows_the_lite_framework():
    """lite 并入后只剩一个 Skill：入口路由、七段主流程、任务入口、沟通模板与按需参考。 [任务:T-3724]"""
    for directory in release_module.SKILL_CONTENT_MD_DIRS:
        assert (SKILL_ROOT / directory).is_dir(), directory
    for retired in release_module.RETIRED_SKILL_DIRS:
        assert not (SKILL_ROOT / retired).exists(), retired
    assert not (ROOT / "skills" / "business-app-creator-lite").exists()
    router = _read("SKILL.md")
    for name in release_module.FLOW_STAGE_FILES:
        assert f"flow/{name}" in router, name
    for task in ("接续", "修订", "诊断", "能力试用", "仅讨论"):
        assert f"tasks/{task}.md" in router, task
    assert "business-app-creator-lite" not in router
    release_module.validate_skill_layout(SKILL_ROOT)


def test_confirmation_page_is_the_only_design_gate():
    """所有应用都走一页确认页；有模型或人工参与的步骤时才附分工表。"""
    g1 = _read("flow/G1-需求确认.md")
    assert "design/分工表.md" in g1 and "design/确认页.md" in g1
    assert "平台要求至少一条路线" in g1
    page = _read("design/确认页.md")
    assert "费用与副作用" in page and "可以上线" in page


def test_identity_rules_forbid_forging_runtime_ids():
    router = _read("SKILL.md")
    assert "`workflow_runtime_id` 只由服务端生成" in router
    assert "`business_id` 由调用方在发起时生成" in router


def test_bubble_verify_and_full_run_boundaries_are_documented():
    g4 = _read("flow/G4-能力制作.md")
    for fact in ('otpe_manage(action="verify"', "`needs_bubble`", 'action="assemble"', "full_run=true", "ctx.dry_run"):
        assert fact in g4, fact
    script = _read("reference/编排脚本.md")
    assert "`partial`" in script and "`blocked`" in script and "`recoverable`" in script


def test_fa_orchestration_guardrails_are_documented():
    """内容型 FA 必须保持职责边界、最小控制面和重复错误止损。"""
    _assert_fa_orchestration_guardrails(SKILL_ROOT)


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        ("reference/编排脚本.md", "顶层字段不超过 8 个", "顶层字段按需增加"),
        ("reference/编排脚本.md", "对象嵌套不超过 2 层", "对象嵌套按需增加"),
        ("reference/编排脚本.md", "把内容改成稳定载体引用", "把内容内联进控制面"),
        ("reference/编排脚本.md", "Schema 只校验形状，不能证明内容真实", "Schema 同时保证内容真实"),
        ("reference/编排脚本.md", "事实区与推断区", "统一内容区"),
        ("reference/编排脚本.md", "连续两轮出现时，停止加字段", "连续出现时继续加字段"),
        ("reference/编排脚本.md", "`partial`（做了一部分，未做的不补不编）", "`completed`（全部做完）"),
        ("reference/编排脚本.md", "`blocked`（一条没做成，数据字段留空）", "`completed`（全部做完）"),
        ("reference/平台对象速查.md", "一个 FA 只承担一个语义责任", "一个 FA 可承担多个语义责任"),
        ("flow/G4-能力制作.md", "同类错误连续两轮就停止扩 Schema", "同类错误后继续扩 Schema"),
        ("reference/编排脚本.md", '"findings": result["findings"]', '"report_path": result["report_path"]'),
        ("reference/编排脚本.md", "模板二、三用到了 `stage_failed`，用模板一时删掉第三条契约", "模板三里用到了 `stage_failed`，用模板一、二时删掉第三条契约"),
        ("reference/编排脚本.md", '"status": result["status"], "note": result["note"]', '"status": result["status"]'),
    ],
)
def test_fa_orchestration_guardrail_regressions_are_rejected(tmp_path, relative, old, new):
    """精确撤掉任一门禁都必须让聚焦合同失败。"""
    skill_root = _copy_repo(tmp_path)
    target = skill_root / relative
    text = target.read_text(encoding="utf-8")
    assert old in text
    target.write_text(text.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(AssertionError):
        _assert_fa_orchestration_guardrails(skill_root)


def test_business_ui_identity_is_bound_before_g5_transition():
    g5 = _read("flow/G5-数据与应用.md")
    assert "npm run scaffold:bind -- --business-ui-id" in g5
    assert "先于把 `current_stage` 改成 G5" in g5
    workspace = _read("reference/开发者中心与工作区.md")
    assert "进 G5 前用 `npm run scaffold:bind" in workspace


def test_online_preview_is_the_developer_acceptance_entry():
    g6 = _read("flow/G6-预览验收.md")
    assert "「在线使用」" in g6 and "deployed_scaffold_version" in g6
    # 部署预览可挂本人场景包草稿，G6 不再单独上线场景包；定版应用时草稿随应用一起上线。 [任务:T-3976]
    assert 'finalize_asset_version_online(asset_type="scenario_pack"' not in g6
    assert "场景包不必先上线" in g6
    assert "一起定版上线" in _read("flow/G7-上线交付.md")


def test_task_closing_gate_and_waiver_are_documented():
    g7 = _read("flow/G7-上线交付.md")
    assert "route_verification_waived" in g7
    assert "WORKFLOW_TASK_ROUTE_BUBBLE_EVIDENCE_REQUIRED" in g7
    assert 'business_ui_manage(action="resolve")' in g7


def test_stage_names_follow_workspace_not_skill():
    """旧应用的阶段名可能是旧名：Skill 只按 G 键更新状态，不改名。"""
    assert "只改状态，不改名" in _read("SKILL.md")
    assert "旧应用的七项可能是旧名" in _read("reference/开发者中心与工作区.md")


def test_flows_are_chosen_by_agent_with_hard_rules_kept():
    """flow 按需选用，但开发者确认、上线前预览验收两条不能跳过。"""
    skill = _read("SKILL.md")
    assert "做哪些由你按需求选" in skill
    assert "左栏" not in skill
    for rule in ("开发者至少确认过一次要做什么", "上线前必须有开发者在「在线使用」里的确认", "跳过的保持 `not_started`"):
        assert rule in skill, rule


def test_empty_demo_preview_is_restarted_in_background():
    """T-3943：演示预览为空时由 Agent 在应用根用 run-dev 后台命令起本地服务。"""
    workspace = _read("reference/开发者中心与工作区.md")
    for fact in ("#### 演示预览为空", "npm run dev:status", "npm run dev:restart", "不要让开发者自己去启动"):
        assert fact in workspace, fact


def test_data_writes_follow_row_ownership():
    data = _read("reference/数据模板.md")
    for fact in ("数据集 FA 只更新已建行的 agent 列", "row_version=row_version+1", "`found=false`"):
        assert fact in data, fact


def test_business_app_guidance_does_not_restore_removed_form_prefill():
    pages = _read("reference/前端页面.md")
    assert "表单预填已下线" in pages
    assert "useFormPrefill" not in pages


def test_stale_zip_is_rejected(tmp_path: Path):
    """源文件改了但没重新打包时必须报错，否则只能等 CI 兜底。"""
    copied = _copy_repo(tmp_path)
    readme = tmp_path / "generic" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n补充说明\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="平台压缩包已过期"):
        release_module.check_release(copied)


def test_install_docs_state_the_required_facts():
    """安装文档必须交代：密钥从哪来、装完怎么验证、从哪装。"""
    for platform, layout in release_module.PLATFORM_LAYOUTS.items():
        platform_root = ROOT / platform
        docs = "\n".join(
            (platform_root / name).read_text(encoding="utf-8") for name in layout["docs"]
        )
        for required in ("/developer/api-keys", "list_assets"):
            assert required in docs, f"{platform} 缺少 {required!r}"

        mcp_name = layout["mcp_config"]
        if mcp_name:
            mcp_text = (platform_root / mcp_name).read_text(encoding="utf-8")
            assert _manifest()["mcp_endpoint"] in mcp_text
            assert set(json.loads(mcp_text)["mcpServers"]) == {release_module.MCP_SERVER_NAME}
            assert "BUSINESS_APP_CREATOR_API_KEY" in mcp_text
            assert not re.search(r"Bearer\s+sk_[A-Za-z0-9]", mcp_text)
            assert "BUSINESS_APP_CREATOR_API_KEY" in docs, f"{platform} 未说明密钥环境变量"
        if layout["skill_subdir"].startswith("skills/"):
            assert "GoalfyAI/business-app-creator-skills" in docs, f"{platform} 缺少公开市场来源"
        # 仓库已公开：任何平台文档都不得再引导用户走 Codeup 内网 / SSH 地址，
        # 否则外部用户会被带去云效配公钥（T-3741）。
        for forbidden in ("codeup.aliyun.com", "git@"):
            assert forbidden not in docs, f"{platform} 文档含内网/SSH 地址 {forbidden!r}"


def test_docs_do_not_pin_a_stale_package_version():
    """文档里不应写死插件版本号，否则发版后就会过期。"""
    version = _package_version()
    for path in (ROOT / "README.md", ROOT / "CONTRIBUTING.md"):
        assert version not in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 防手改


def test_skill_source_change_requires_a_new_release(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    skill_file = copied / "SKILL.md"
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="发布校验和已过期"):
        release_module.check_release(copied)


def test_new_reference_requires_a_new_release(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    (copied / "reference" / "unreleased.md").write_text(
        "# 未发布\n\n## 适用场景\n\n## 规则\n\n## 常见错误\n\n## 相关工具与契约主题\n", encoding="utf-8"
    )

    with pytest.raises(release_module.ReleaseError, match="source_files 与 Skill 唯一源文件不一致"):
        release_module.check_release(copied)


def test_skill_body_references_resolve_to_shipped_files():
    """正文里指向 Skill 自身文件的路径必须在发布包里（FB-38：改名后引用未同步）。"""
    assert release_module.find_broken_references(SKILL_ROOT) == []
    shipped = _manifest()["source_files"]
    assert "flow/G1-需求确认.md" in shipped
    assert "scripts/feedback_report.py" in shipped
    assert not any(item.startswith("references/") for item in shipped)


@pytest.mark.parametrize(
    ("relative", "line", "reported"),
    [
        ("SKILL.md", "见 `reference/不存在的参考.md`。", "SKILL.md:"),
        (
            "reference/平台对象速查.md",
            "详见 [G9](../flow/G9-不存在.md#出口)。",
            "reference/平台对象速查.md:",
        ),
    ],
)
def test_broken_body_reference_is_rejected(tmp_path: Path, relative: str, line: str, reported: str):
    copied = _copy_repo(tmp_path)
    target = copied / relative
    target.write_text(target.read_text(encoding="utf-8") + "\n" + line + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="Skill 正文引用了发布包里不存在的文件") as error:
        release_module.check_release(copied)
    assert reported in str(error.value)
    with pytest.raises(release_module.ReleaseError, match="Skill 正文引用了发布包里不存在的文件"):
        release_module.release(copied, _package_version(copied), "broken reference")


def test_application_workspace_paths_are_not_skill_references(tmp_path: Path):
    """`workspace.json`、`backend/README.md` 是智能应用工程里的文件，不按 Skill 引用校验。"""
    copied = _copy_repo(tmp_path)
    skill_file = copied / "SKILL.md"
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8")
        + "\n先读 `workspace.json`、`backend/README.md` 与 `docs/stages/G1-业务目标与范围.md`。\n",
        encoding="utf-8",
    )

    assert release_module.find_broken_references(copied) == []


@pytest.mark.parametrize(
    "relative",
    [
        "claude-code/skills/business-app-creator/SKILL.md",
        "codex/skills/business-app-creator/SKILL.md",
        "manus/skill/SKILL.md",
        "generic/SKILL.md",
    ],
)
def test_platform_copy_drift_is_rejected(tmp_path: Path, relative: str):
    """任一平台副本被单独改动都必须报错——这是 Skill 内容分叉的唯一入口。"""
    copied = _copy_repo(tmp_path)
    drifted = tmp_path / relative
    drifted.write_text(drifted.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="Skill 副本已过期"):
        release_module.check_release(copied)


def test_package_version_drift_between_manifests_is_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    manifest_path = tmp_path / "codex/.codex-plugin/plugin.json"
    manifest_path.write_text(
        re.sub(r'"version": "[\d.]+"', '"version": "9.9.9"', manifest_path.read_text(), count=1),
        encoding="utf-8",
    )

    with pytest.raises(release_module.ReleaseError, match="插件 manifest 版本不一致"):
        release_module.check_release(copied)


# ---------------------------------------------------------------- 源文件契约


def test_release_rejects_invalid_skill_frontmatter(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    skill_file = copied / "SKILL.md"
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    lines.insert(1, "extra: not allowed")
    skill_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="frontmatter 必须且只能包含"):
        release_module.release(copied, _package_version(copied), "invalid frontmatter")


def test_release_rejects_missing_skill_keywords(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    skill_file = copied / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    content = content.replace("  - 场景包\n", "", 1)
    skill_file.write_text(content, encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="缺少核心 keywords"):
        release_module.release(copied, _package_version(copied), "missing keyword")


def test_release_rejects_missing_skill_version_marker(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    skill_file = copied / "SKILL.md"
    content = release_module.SKILL_VERSION_RE.sub("", skill_file.read_text(encoding="utf-8"))
    skill_file.write_text(content, encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="skill-version 标记"):
        release_module.release(copied, _package_version(copied), "missing marker")


def test_release_rejects_hidden_or_unsupported_source_files(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    (copied / "notes.txt").write_text("unsupported\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 文件"):
        release_module.release(copied, _package_version(copied), "unsupported file")


def test_release_rejects_unlisted_skill_resource_directories(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    extra = copied / "extras"
    extra.mkdir()
    (extra / "note.md").write_text("# note\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 文件"):
        release_module.release(copied, _package_version(copied), "unsupported directory")


def test_release_rejects_invalid_openai_metadata(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    metadata_path = copied / "agents" / "openai.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["interface"]["short_description"] = "太短"
    metadata_path.write_text(yaml.safe_dump(metadata, allow_unicode=True), encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="short_description"):
        release_module.release(copied, _package_version(copied), "invalid metadata")


def test_release_rejects_missing_openai_mcp_dependency(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    metadata_path = copied / "agents" / "openai.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["dependencies"]["tools"] = []
    metadata_path.write_text(yaml.safe_dump(metadata, allow_unicode=True), encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="唯一的 business-app-creator MCP 依赖"):
        release_module.release(copied, _package_version(copied), "missing dependency")


# ---------------------------------------------------------------- 版本机制


def test_non_prod_release_rejects_package_version_bump(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    bumped = release_module._next_patch(_package_version(copied))

    with pytest.raises(release_module.ReleaseError, match="只有 PROD"):
        release_module.release(copied, bumped, "不允许提前升级")


def test_non_prod_release_rejects_skill_version_change(tmp_path: Path):
    copied = _copy_repo(tmp_path)

    with pytest.raises(release_module.ReleaseError, match="只有 PROD"):
        release_module.release(
            copied,
            _package_version(copied),
            "不允许提前切换 Skill 版本",
            skill_version="v20260813-a1b2c3",
        )


def test_prod_version_uses_date_and_random_hex():
    fixed = release_module.datetime(2026, 8, 12, 3, 4, tzinfo=release_module.timezone.utc)
    assert release_module.generate_prod_version(fixed, random_hex="a1b2c3") == "v20260812-a1b2c3"


def test_prod_version_rejects_invalid_random_hex():
    with pytest.raises(release_module.ReleaseError, match="6 位小写 hex"):
        release_module.generate_prod_version(random_hex="NOTHEX")


def test_prod_release_updates_every_version_surface(tmp_path: Path):
    """一次 PROD 发布必须同时切 Skill 版本、提升所有插件版本、同步平台副本。"""
    copied = _copy_repo(tmp_path)
    expected_package_version = release_module._next_patch(_package_version(copied))
    fixed = release_module.datetime(2026, 8, 13, 3, 4, tzinfo=release_module.timezone.utc)

    version = release_module.release_prod_source(
        copied, "PROD release", now=fixed, random_hex="a1b2c3"
    )

    assert version == "v20260813-a1b2c3"
    marker = f"[skill-version:{version}]"
    assert marker in (copied / "SKILL.md").read_text(encoding="utf-8")
    for platform in release_module.PLATFORM_NAMES:
        copy = release_module._platform_skill_dir(copied, platform) / "SKILL.md"
        assert marker in copy.read_text(encoding="utf-8")

    manifest = _manifest(copied)
    assert manifest["version"] == version
    assert manifest["package_version"] == expected_package_version
    assert release_module._repository_package_version(copied) == expected_package_version
    release_module.check_release(copied)


def test_prod_release_rolls_back_marker_on_failure(tmp_path: Path):
    """发布中途失败时不得留下已改标记但未发布的半成品。"""
    copied = _copy_repo(tmp_path)
    original = (copied / "SKILL.md").read_text(encoding="utf-8")
    (copied / "notes.txt").write_text("unsupported\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError):
        release_module.release_prod_source(copied, "will fail", random_hex="a1b2c3")

    assert (copied / "SKILL.md").read_text(encoding="utf-8") == original


def test_sync_restores_platform_copies(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = tmp_path / "codex/skills/business-app-creator/SKILL.md"
    target.unlink()

    release_module.sync_platform_skills(copied)

    release_module.check_release(copied)
    assert target.is_file()


# ---------------------------------------------------------------- 流水线契约


def test_release_script_covers_the_whole_publish_flow():
    """本地发版脚本必须完成：切版本、校验、提交、打 tag，并提示推送两个远程。"""
    script = (ROOT / "scripts" / "release-skill.sh").read_text(encoding="utf-8")

    assert "release_prod_source" in script, "未切版本"
    assert "build_platform_packages.py check" in script, "未在提交前校验"
    assert "git commit" in script and "git tag" in script, "未提交或未打 tag"
    assert "origin main" in script and "github main" in script, "未提示推送两个远程"
    # 工作区不干净时无法分辨哪些改动属于本次发布
    assert "git status --porcelain" in script



def test_registration_workflow_injects_the_expected_env_name():
    """workflow 注入的环境变量名必须与脚本读取的一致。

    名字对不上时脚本会退回单目标兜底分支，报缺少 SCENE_SKILL_RELEASE_REGISTER_URL，
    错误信息完全指向另一个方向。
    """
    workflow = (ROOT / ".github/workflows/register-skill-release.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "register-skill-release.py").read_text(encoding="utf-8")

    assert 'SCENE_SKILL_RELEASE_REGISTRY_TARGETS: ${{ secrets.SCENE_SKILL_RELEASE_REGISTRY_TARGETS }}' in workflow
    assert 'os.environ.get("SCENE_SKILL_RELEASE_REGISTRY_TARGETS"' in script


def test_registration_workflow_reuses_the_release_script():
    """登记逻辑只保留一份实现，避免签名方式出现第二份。"""
    workflow = (ROOT / ".github/workflows/register-skill-release.yml").read_text(encoding="utf-8")

    assert "build_platform_packages.py check" in workflow, "登记前必须校验产物"
    assert "scripts/register-skill-release.py" in workflow
    assert "register_release" in workflow



def test_prod_runtime_probe_requires_auth_layer(monkeypatch, tmp_path: Path):
    _copy_repo(tmp_path)

    def reject_without_auth(request, timeout=None):
        raise prod_release_module.urllib.error.HTTPError(
            release_module.PROD_MCP_ENDPOINT,
            401,
            "Unauthorized",
            {"X-Scene-Skill-Runtime": "cn-prod"},
            None,
        )

    monkeypatch.setattr(prod_release_module.urllib.request, "urlopen", reject_without_auth)
    prod_release_module.verify_prod_runtime(tmp_path)


def test_prod_runtime_probe_rejects_missing_route(monkeypatch, tmp_path: Path):
    _copy_repo(tmp_path)

    def not_found(request, timeout=None):
        raise prod_release_module.urllib.error.HTTPError(
            release_module.PROD_MCP_ENDPOINT, 404, "Not Found", {}, None
        )

    monkeypatch.setattr(prod_release_module.urllib.request, "urlopen", not_found)
    with pytest.raises(RuntimeError, match="not ready"):
        prod_release_module.verify_prod_runtime(tmp_path)


def test_prod_runtime_probe_rejects_wrong_hub_binding(monkeypatch, tmp_path: Path):
    _copy_repo(tmp_path)

    def wrong_runtime(request, timeout=None):
        raise prod_release_module.urllib.error.HTTPError(
            release_module.PROD_MCP_ENDPOINT,
            401,
            "Unauthorized",
            {"X-Scene-Skill-Runtime": "qa"},
            None,
        )

    monkeypatch.setattr(prod_release_module.urllib.request, "urlopen", wrong_runtime)
    with pytest.raises(RuntimeError, match="not connected"):
        prod_release_module.verify_prod_runtime(tmp_path)


def test_registry_targets_parsing():
    """多目标登记：格式错误必须拦住，未配置时回退单目标。"""
    import os

    os.environ["SCENE_SKILL_RELEASE_REGISTRY_TARGETS"] = "https://a/reg|s1\n\nhttps://b/reg|s2\n"
    assert prod_release_module._registry_targets() == [
        ("https://a/reg", "s1"),
        ("https://b/reg", "s2"),
    ]

    os.environ["SCENE_SKILL_RELEASE_REGISTRY_TARGETS"] = "https://a/reg-without-secret"
    with pytest.raises(RuntimeError, match="<url>\\|<secret>"):
        prod_release_module._registry_targets()

    del os.environ["SCENE_SKILL_RELEASE_REGISTRY_TARGETS"]
    os.environ["SCENE_SKILL_RELEASE_REGISTER_URL"] = "https://only/reg"
    os.environ["SCENE_SKILL_RELEASE_S2S_SECRET"] = "s0"
    assert prod_release_module._registry_targets() == [("https://only/reg", "s0")]


def test_feedback_report_script_is_shipped_with_skill(tmp_path):
    skill_root = _copy_repo(tmp_path)
    release_module.sync_platform_skills(skill_root)
    source = skill_root / "scripts" / "feedback_report.py"
    for platform in ("codex", "claude-code"):
        target = tmp_path / platform / "skills/business-app-creator/scripts/feedback_report.py"
        assert target.read_bytes() == source.read_bytes()


# ---------------------------------------------------------------- 框架骨架 [任务:T-3724]


def test_current_skill_layout_passes():
    release_module.validate_skill_layout(SKILL_ROOT)


@pytest.mark.parametrize(
    ("relative", "mutate", "message"),
    [
        ("flow/G4-能力制作.md", lambda text: text.replace("## 5. 出口", "## 5. 完成标准"), "二级标题必须依次为"),
        ("reference/数据模板.md", lambda text: text.replace("## 常见错误\n", ""), "二级标题必须依次为"),
        ("tasks/诊断.md", lambda text: text + "\n## 补充\n", "二级标题必须依次为"),
        ("SKILL.md", lambda text: text + "\n" * 60, "行预算"),
    ],
)
def test_skeleton_drift_is_rejected(tmp_path: Path, relative: str, mutate, message: str):
    copied = _copy_repo(tmp_path)
    target = copied / relative
    target.write_text(mutate(target.read_text(encoding="utf-8")), encoding="utf-8")

    for action in (
        lambda: release_module.check_release(copied),
        lambda: release_module.release(copied, _package_version(copied), "骨架校验"),
    ):
        with pytest.raises(release_module.ReleaseError, match=message) as error:
            action()
        assert relative in str(error.value)


def test_missing_flow_stage_is_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    (copied / "flow" / "G7-上线交付.md").unlink()
    with pytest.raises(release_module.ReleaseError, match="flow/ 必须正好是七段文件"):
        release_module.validate_skill_layout(copied)


def test_code_block_headings_do_not_count_as_sections(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = copied / "reference" / "编排脚本.md"
    text = target.read_text(encoding="utf-8").replace(
        "## 常见错误", "```text\n## 示例里的标题\n```\n\n## 常见错误", 1
    )
    target.write_text(text, encoding="utf-8")
    release_module.validate_skill_layout(copied)


# ---------------------------------------------------------------- QA 渠道 [任务:T-3784]


QA_BUILD_SPEC = importlib.util.spec_from_file_location("build_qa_branch", ROOT / "scripts" / "build_qa_branch.py")
assert QA_BUILD_SPEC and QA_BUILD_SPEC.loader
qa_build_module = importlib.util.module_from_spec(QA_BUILD_SPEC)
QA_BUILD_SPEC.loader.exec_module(qa_build_module)


def test_prod_install_files_reject_qa_values(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    readme = tmp_path / "claude-code" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nBUSINESS_APP_CREATOR_QA_API_KEY\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="混入了其他渠道的配置"):
        release_module.validate_platform_install_files(copied)


def test_prod_channel_rejects_qa_package_version(monkeypatch):
    monkeypatch.setenv(release_module.CHANNEL_ENV, "prod")
    with pytest.raises(release_module.ReleaseError, match="MAJOR.MINOR.PATCH"):
        release_module._validate_package_version("2.0.12-qa.3")
    monkeypatch.setenv(release_module.CHANNEL_ENV, "qa")
    assert release_module._validate_package_version("2.0.12-qa.3") == (2, 0, 12)
    with pytest.raises(release_module.ReleaseError, match="-qa.N"):
        release_module._validate_package_version("2.0.12")


def test_unknown_channel_is_rejected(monkeypatch):
    monkeypatch.setenv(release_module.CHANNEL_ENV, "staging")
    with pytest.raises(release_module.ReleaseError, match="SKILL_RELEASE_CHANNEL"):
        release_module.release_channel()


def test_qa_build_switches_every_environment_value(tmp_path: Path, monkeypatch):
    out = tmp_path / "qa"
    out.mkdir()
    info = qa_build_module.build(out, "HEAD", 7)
    monkeypatch.setenv(release_module.CHANNEL_ENV, "qa")

    assert info["package_version"].endswith("-qa.7")
    manifest = json.loads((out / "skill-release.json").read_text(encoding="utf-8"))
    assert manifest["mcp_endpoint"] == release_module.RELEASE_CHANNELS["qa"]["mcp_endpoint"]
    prod = release_module.RELEASE_CHANNELS["prod"]
    install_roots = ("skills", "claude-code", "codex", "manus", "generic", "docs", "README.md")
    for root_name in install_roots:
        base = out / root_name
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.suffix in {".md", ".json", ".yaml"}]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for value in prod.values():
                assert value not in text, f"{path.relative_to(out)} 仍含 prod 值 {value}"
    claude_readme = (out / "claude-code" / "README.md").read_text(encoding="utf-8")
    assert '.git#business-qa"' in claude_readme
    assert "--ref business-qa" in (out / "codex" / "README.md").read_text(encoding="utf-8")


def test_retired_lite_copies_are_removed_and_rejected(tmp_path: Path):
    """lite 已并入主 Skill：同步时删掉平台里的旧副本，残留即拒绝发布。 [任务:T-3724]"""
    copied = _copy_repo(tmp_path)
    for platform in release_module.EXTRA_SKILL_PLATFORMS:
        assert not (tmp_path / platform / "skills/business-app-creator-lite").exists(), platform
    stale = tmp_path / "codex/skills/business-app-creator-lite"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("stale\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="已退役的附加 Skill"):
        release_module.check_release(copied)
    release_module.sync_platform_skills(copied)
    assert not stale.exists()
    release_module.check_release(copied)


def test_retired_structure_directories_are_rejected_in_platform_copies(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    leftover = tmp_path / "claude-code/skills/business-app-creator/stages"
    leftover.mkdir()
    (leftover / "G1-业务目标与范围.md").write_text("old\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="旧结构目录"):
        release_module.check_release(copied)


def test_delivery_separates_deploy_status_from_real_entry():
    """T-4130：entry_url 是开发者容器地址，交付只写部署状态与真实入口，不把它当用户入口。"""
    deploy = _read("reference/部署与版本.md")
    for fact in ("### 部署状态与入口", "直接打开只会进入 mock 模式", "GoalfyMax → 智能应用 → 预览", "开发者中心右侧「在线使用」"):
        assert fact in deploy, fact
    delivery = _read("flow/G7-上线交付.md")
    assert "消费者视角的 `entry_url`" not in delivery
    assert "| 应用 | 名称、上线版本、`entry_url`" not in delivery
    assert "不写容器地址" in delivery
    assert "读预览入口" not in _read("flow/G6-预览验收.md")


def test_draft_resolve_is_not_platform_blocked():
    """T-4130（并入 T-4062）：定版前 resolve 报只有草稿是正常结果，草稿验收走在线使用，不记平台阻塞。"""
    assert "`resolve` 只认上线版本" in _read("reference/部署与版本.md")
    g6 = _read("flow/G6-预览验收.md")
    assert "定版前 `resolve` 报「还没有上线版本（只有草稿）」" in g6
    assert "不记 platform_blocked，也不为拿入口去 finalize" in g6


def test_page_checks_go_through_developer_center_not_agent_browser():
    """Agent 不用内置浏览器访问正式入口或登录页；看页面走开发者中心，审批拒绝不绕过。"""
    assert "**禁止**用 Codex 内置浏览器" in _read("SKILL.md")
    workspace = _read("reference/开发者中心与工作区.md")
    for fact in ("#### 看页面只用开发者中心", "`passport` 登录页", "不借用开发者已登录的会话", "访问被工具审批拒绝时不重试", "test:e2e:layout"):
        assert fact in workspace, fact
    assert "在开发者中心「演示预览」里看真实渲染，桌面与移动各过一遍" not in _read("reference/前端页面.md")


def test_stage_name_describes_concrete_business_step():
    """执行状态条显示 stage_name：写具体动作，多个业务步骤各发一次 stage_started。"""
    script = _read("reference/编排脚本.md")
    for fact in (
        "`stage_name` 就是使用者在应用顶部执行状态条上看到的那句话",
        "**禁止**「正在处理本次任务」「正在执行」这类看不出在做什么的泛词",
        "每个步骤开始前各发一次 `stage_started`，各用自己的 `event_key`、`stage_key` 并各自声明契约",
        "**禁止**在每个 `tool()` 后机械发事件",
    ):
        assert fact in script, fact


def test_online_preview_needs_deployed_draft_not_finalize():
    """在线使用只要草稿部署成功；需要上线的操作列在同一张表里，上线不是发布。"""
    deploy = _read("reference/部署与版本.md")
    assert "### 哪些用草稿就行，哪些要先上线" in deploy
    assert "不为打开它去 finalize" in deploy
    for path in ("reference/开发者中心与工作区.md", "flow/G6-预览验收.md"):
        text = _read(path)
        assert "`PREVIEW_NOT_READY` 记为阻塞" not in text, path
        assert "记为阻塞处理" not in text, path
    assert "定稿并对最终用户可运行" not in _read("reference/平台对象速查.md")


def test_long_text_tool_output_declares_single_string_field():
    """FB-147：返回整段文本的工具 `_output` 只声明一个 string 字段，平台直接包装原文，不经模型抽取。"""
    script = _read("reference/编排脚本.md")
    for fact in ("`_output` 只声明一个必填 string 字段", "平台直接把原文包进去，不经模型", "`_output extraction` 45 秒"):
        assert fact in script, fact


def test_no_waiting_on_developer_after_confirmation():
    """确认页确认后一路做到在线使用可用；制作中的测试费用已在确认页同意，不再逐次等开发者。"""
    skill = _read("SKILL.md")
    assert "中间不设等开发者的环节" in skill
    assert "先向开发者说明费用并取得同意" not in _read("flow/G4-能力制作.md")
    confirm = _read("design/确认页.md")
    assert "制作中的测试：冒泡与真跑约" in confirm
    assert "部署预览前要先把场景包上线" not in confirm


def test_confirmed_interface_beats_preset_look():
    """开发者确认过的界面优先；预置件只是工具，保住的是行为不是外观。"""
    pages = _read("reference/前端页面.md")
    assert "### 预置件怎么用" in pages
    assert "**不为了用预置件把确认过的界面改掉**" in pages
    assert "**界面**（开发者给过截图、参考或说过样子时才写）" in _read("design/确认页.md")
    assert "按确认过的界面写业务页" in _read("flow/G5-数据与应用.md")


def test_self_supply_route_matches_dataset_fa_contract():
    """自给路线建行要按数据集 FA 的约定写 context_hint（FA 只在「自给建行」时允许 INSERT）。"""
    template = _read("reference/数据模板.md")
    for fact in (
        "`context_hint` 写明「自给建行」",
        "业务键列与值、要填的身份列与值、本次 `run_id`",
        "没写「自给建行」，数据集 FA 只按行 id 更新、不建行",
        "业务键在模板里必须有唯一约束",
    ):
        assert fact in template, fact


def test_delivery_review_reply_only_action_key():
    """线上 50829：审阅应答夹带商家数据被拒后应用没展示；Skill 写明只提交 action_key、展示被拒原因。"""
    pages = _read("reference/前端页面.md")
    assert "**交付审阅只提交所选动作**" in pages
    assert "`data.field_errors`" in pages
    assert "DELIVERY_REVIEW_REPLY_INVALID" in _read("reference/报错对照.md")


def test_online_tab_named_zaixian_shiyong():
    """开发者中心右栏分页已改名为「在线使用」，Skill 不再出现旧叫法。"""
    root = Path(__file__).resolve().parents[1] / "skills" / "business-app-creator"
    for path in root.rglob("*"):
        if path.suffix in (".md", ".yaml") and path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "在线预览" not in text and "在线试用" not in text, path
