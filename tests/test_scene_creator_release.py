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
    # 控制面收窄不能让用户可见内容只落文件：短内容照常返回，批量明细写回应用库，中间文件放 process_dir。 [任务:T-3941]
    assert "`ctx.process_dir` 文件等稳定载体" in script
    assert "给用户看的列表、正文、结论仍以业务字段出现" in script
    assert '"flagged": flagged, "summary": f"{flagged} 个计划需要关注"' in script
    assert '"draft_body": draft["draft_body"]' in script
    # 模板二的 blocked 出口会发 stage_failed，契约说明不能让它删掉这条声明；partial 要把 note 带给用户。 [任务:T-3941]
    assert 'event_key="inspection_failed"' in script
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

    making = (skill_root / "stages/3-制作.md").read_text(encoding="utf-8")
    assert "内容走稳定载体引用" in making
    assert "同类错误连续两轮就停止扩 Schema" in making


def test_single_skill_follows_the_five_stage_framework():
    """只有一个 Skill：入口路由、五段主流程、任务入口、沟通模板与按需参考。"""
    for directory in release_module.SKILL_CONTENT_MD_DIRS:
        assert (SKILL_ROOT / directory).is_dir(), directory
    for retired in release_module.RETIRED_SKILL_DIRS:
        assert not (SKILL_ROOT / retired).exists(), retired
    assert not (ROOT / "skills" / "business-app-creator-lite").exists()
    for removed in ("design/确认页.md", "design/分工表.md", "design/阶段评分.md"):
        assert not (SKILL_ROOT / removed).exists(), removed
    router = _read("SKILL.md")
    for name in release_module.STAGE_FILES:
        assert f"stages/{name}" in router, name
    for task in ("接续", "修订", "诊断", "能力试用", "仅讨论"):
        assert f"tasks/{task}.md" in router, task
    assert "business-app-creator-lite" not in router
    release_module.validate_skill_layout(SKILL_ROOT)


def test_prd_is_the_only_design_gate():
    """所有应用都在 ① 交一份 PRD；每一步谁来做写在 PRD 里，平台要求至少一条路线。"""
    requirement = _read("stages/1-需求确认.md")
    assert "design/PRD.md" in requirement and "design/谁来做.md" in requirement
    assert "平台要求每个应用至少一条路线" in requirement
    prd = _read("design/PRD.md")
    assert "费用与副作用" in prd and "可以上线" in prd


def test_identity_rules_forbid_forging_runtime_ids():
    router = _read("SKILL.md")
    assert "`workflow_runtime_id` 只由服务端生成" in router
    assert "`business_id` 由调用方在发起时生成" in router


def test_bubble_verify_and_full_run_boundaries_are_documented():
    making = _read("stages/3-制作.md")
    for fact in ('otpe_manage(action="verify"', "`needs_bubble`", 'action="assemble"', "full_run=true", "ctx.dry_run"):
        assert fact in making, fact
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
        ("stages/3-制作.md", "同类错误连续两轮就停止扩 Schema", "同类错误后继续扩 Schema"),
        ("reference/编排脚本.md", '"flagged": flagged, "summary": f"{flagged} 个计划需要关注"', '"flagged": flagged'),
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
    making = _read("stages/3-制作.md")
    assert "scaffold_bind_command" in making
    assert "先于把 `current_stage` 改成 G5" in making
    workspace = _read("reference/开发者中心与工作区.md")
    assert "进 G5 前用 `npm run scaffold:bind" in workspace


def test_online_preview_is_where_acceptance_happens():
    """④ 部署后在在线预览里验收；挂本人场景包草稿也能部署，定版应用时草稿随应用一起上线。 [任务:T-3976]"""
    acceptance = _read("stages/4-试用验收.md")
    assert "在线预览" in acceptance and "deployed_scaffold_version" in acceptance
    assert 'finalize_asset_version_online(asset_type="scenario_pack"' not in acceptance
    assert "场景包不必先上线" in acceptance
    assert "一起定版上线" in _read("stages/5-上线.md")


def test_task_closing_gate_and_waiver_are_documented():
    launch = _read("stages/5-上线.md")
    assert "route_verification_waived" in launch
    assert "WORKFLOW_TASK_ROUTE_BUBBLE_EVIDENCE_REQUIRED" in launch
    assert 'business_ui_manage(action="resolve")' in launch


def test_stage_names_follow_workspace_not_skill():
    """旧应用的阶段名可能是旧名：Skill 只按 G 键更新状态，不改名。"""
    workspace = _read("reference/开发者中心与工作区.md")
    assert "只改状态不改名" in workspace
    assert "旧应用的七项可能是旧名" in workspace


def test_stages_hand_over_on_explicit_conditions():
    """五段按序推进，每段交棒条件写在段文件里；确认 PRD、判断题、「可以上线」不能跳过。"""
    skill = _read("SKILL.md")
    assert "左栏" not in skill
    for rule in (
        "每段的交棒条件写在段文件末尾，满足了才进下一段",
        "① 开发者回「确认这一版」，② 判断题都答「对」，③ 能部署，④ 报告过了硬门、开发者看后说「可以上线」",
        "④ 和 ⑤ 每次都做",
    ):
        assert rule in skill, rule
    for name in release_module.STAGE_FILES[:4]:
        assert "## 6. 交棒条件" in _read(f"stages/{name}") or "## 5. 交棒条件" in _read(f"stages/{name}"), name
    assert "跳过的项写进 `skipped`" in _read("reference/开发者中心与工作区.md")


def test_stage_exits_write_stage_records_in_one_place():
    """R-367：每段出口按段内做过的项写 business_ui_stage；参数写法只在《开发者中心与工作区》一处。"""
    exits = {
        "1-需求确认.md": "写 G1、G2 各一条",
        "2-方案.md": "写 G3 一条",
        "3-制作.md": "写 G4、G5 各一条",
        "4-试用验收.md": "在「可以上线」checkpoint 之后用 `business_ui_stage` 写 G6",
        "5-上线.md": "用 `business_ui_stage` 写 G7，`next_stage` 填 `closeout`，必须在下一步 `complete` 之前",
    }
    for name, fact in exits.items():
        text = _read(f"stages/{name}")
        assert "business_ui_stage" in text, name
        assert fact in text, name
    assert "business_ui_stage" in _read("SKILL.md")
    workspace = _read("reference/开发者中心与工作区.md")
    for fact in ("**阶段记录**", "`completion`", "`next_plan`", "`skipped`", "**只调一次**", "**只写不读**",
                 "有「未测」条目时 `result` 填 `partial`"):
        assert fact in workspace, fact
    for path in SKILL_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if path.name == "开发者中心与工作区.md":
            continue
        assert "completion=" not in text and "next_plan=" not in text, path


def test_write_task_reads_skill_version_from_installed_skill():
    """FK-519：建 write 工单必须从已安装 SKILL.md 读 skill_version，被拒处理链到工单闸门。"""
    skill = _read("SKILL.md")
    start = skill.split("## 5. 开工", 1)[1].split("## 6.", 1)[0]
    assert 'task_manager(action="create", mode="write", skill_version=…)' in start
    assert "`skill_version` **必须**填已安装 SKILL.md description 里 `[skill-version:...]` 的原值" in start
    assert "「工单闸门」" in start


def test_skill_body_has_no_retired_structure_or_proxy_testing_wording():
    """R-367：正文不链 flow/G、不提阶段评分，不写请开发者代测页面条目的话。"""
    for path in SKILL_ROOT.rglob("*"):
        if path.suffix not in (".md", ".yaml") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for retired in ("flow/G", "阶段评分", "business_ui_stage_rating", "需要你在在线预览里试", "开发者未试"):
            assert retired not in text, (path, retired)


def test_empty_demo_preview_follows_completed_copy_gate():
    """FK-264：演示预览只展示完成版固定副本，不需要部署；为空按原因处理，不用 npm run dev 冒充。"""
    workspace = _read("reference/开发者中心与工作区.md")
    for fact in ("#### 演示预览为空", "完成版固定副本", "不需要部署", "completedPreview.argv",
                 "不要**为了提前打开演示预览去生成完成版", "completed-preview.json",
                 "「应用尚未完成」", "「预览未启动」", "「暂时无法确认应用完成状态」", "不启动服务",
                 "「重新启动」", "「重新检查」", "内容已保存，切换到完成版"):
        assert fact in workspace, fact
    assert "工作台读应用目录 `.workbench/dev-host.json`" not in workspace
    assert "成功后工作台自动显示" not in workspace
    assert "完成版命令" in _read("stages/4-试用验收.md")
    assert "在开发者中心的「演示预览」里看" not in _read("stages/3-制作.md")


def test_data_writes_follow_row_ownership():
    data = _read("reference/数据模板.md")
    for fact in ("路线只更新已建行的 agent 列", "row_version=row_version+1", "`found`"):
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
    assert "stages/1-需求确认.md" in shipped
    assert not any(item.startswith("flow/") for item in shipped)
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
    assert "--register-and-recommend" in workflow
    script = PROD_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "register_release(version)" in script



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
        ("stages/3-制作.md", lambda text: text.replace("## 4. 产出与落盘", "## 4. 产出"), "二级标题必须按顺序包含"),
        ("stages/2-方案.md", lambda text: text + "\n" * 20, "行预算"),
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


def test_missing_stage_file_is_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    (copied / "stages" / "5-上线.md").unlink()
    with pytest.raises(release_module.ReleaseError, match="stages/ 必须正好是五段文件"):
        release_module.validate_skill_layout(copied)


def test_line_budgets_are_not_raised():
    """R-367：行数预算保持 SKILL.md 200、stages 160、reference 400。"""
    assert release_module.LINE_BUDGETS == {"SKILL.md": 200, "stages": 160, "reference": 400}


def test_code_block_headings_do_not_count_as_sections(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = copied / "reference" / "编排脚本.md"
    text = target.read_text(encoding="utf-8").replace(
        "## 常见错误", "```text\n## 示例里的标题\n```\n\n## 常见错误", 1
    )
    target.write_text(text, encoding="utf-8")
    release_module.validate_skill_layout(copied)


# ---------------------------------------------------------------- QA 渠道 [任务:T-3784]


QA_BUILD_SPEC = importlib.util.spec_from_file_location("build_env_branch", ROOT / "scripts" / "build_env_branch.py")
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


def test_pre_build_uses_pre_channel_and_reuses_given_version(tmp_path: Path, monkeypatch):
    """部署 main 到 PRE：沿用 main 的发布版本，安装物料全部指向 PRE，升级链接指向 business-pre。"""
    out = tmp_path / "pre"
    out.mkdir()
    info = qa_build_module.build(out, "HEAD", 9, env="pre", skill_version="v20261019-abcdef", source_label="main")
    monkeypatch.setenv(release_module.CHANNEL_ENV, "pre")

    assert info["branch"] == "business-pre"
    assert info["skill_version"] == "v20261019-abcdef"
    assert info["package_version"].endswith("-pre.9")
    manifest = json.loads((out / "skill-release.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "v20261019-abcdef"
    assert manifest["mcp_endpoint"] == release_module.RELEASE_CHANNELS["pre"]["mcp_endpoint"]
    for other in ("prod", "qa"):
        for value in release_module.RELEASE_CHANNELS[other].values():
            assert value not in (out / "claude-code" / "README.md").read_text(encoding="utf-8")
    assert '.git#business-pre"' in (out / "claude-code" / "README.md").read_text(encoding="utf-8")


def test_env_channel_package_suffix_must_match_channel(monkeypatch):
    monkeypatch.setenv(release_module.CHANNEL_ENV, "pre")
    assert release_module._validate_package_version("2.0.12-pre.3") == (2, 0, 12)
    with pytest.raises(release_module.ReleaseError, match="-pre.N"):
        release_module._validate_package_version("2.0.12-qa.3")


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
    leftover = tmp_path / "claude-code/skills/business-app-creator/flow"
    leftover.mkdir()
    (leftover / "G1-需求确认.md").write_text("old\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="旧结构目录"):
        release_module.check_release(copied)


def test_delivery_separates_deploy_status_from_real_entry():
    """T-4130：entry_url 是开发者容器地址，交付只写部署状态与真实入口，不把它当用户入口。"""
    deploy = _read("reference/部署与版本.md")
    # 上线不等于发布：正式入口（开发者本人也一样）要发布后才能打开；部署后、定版前用在线预览。
    for fact in ("### 部署状态与入口", "生产构建直开返回 `HOST_REQUIRED`", "只有本地开发构建直开才进入 Mock",
                 "GoalfyMax → 我的资产 → 智能应用 → 打开", "开发者中心右侧「在线预览」", "正式入口还打不开，开发者本人也一样"):
        assert fact in deploy, fact
    assert "直接打开只会进入 mock 模式" not in deploy
    assert "GoalfyMax → 智能应用 → 预览" not in deploy
    launch = _read("stages/5-上线.md")
    assert "消费者视角的 `entry_url`" not in launch
    assert "| 应用 | 名称、上线版本、`entry_url`" not in launch
    assert "不写容器地址" in launch
    assert "读预览入口" not in _read("stages/4-试用验收.md")


def test_draft_resolve_is_not_platform_blocked():
    """T-4130（并入 T-4062）：定版前 resolve 报只有草稿是正常结果，草稿验收走在线预览，不记平台阻塞。"""
    assert "`resolve` 只认上线版本" in _read("reference/部署与版本.md")
    acceptance = _read("stages/4-试用验收.md")
    assert "定版前 `resolve` 报「还没有上线版本」" in acceptance
    assert "不记 platform_blocked，也不为拿入口去 finalize" in acceptance


def test_browser_red_lines_are_four_rules_with_one_detailed_source():
    """R-367 options F：SKILL.md 第 0 节写四条浏览器红线，启动参数、地址与五步只在「④ 用浏览器验收」一处。"""
    skill = _read("SKILL.md")
    red_lines = skill.split("## 0. 红线", 1)[1].split("## 1.", 1)[0]
    for fact in (
        "开发者在本次 ④ 同意后你才启动浏览器打开 GoalfyMax",
        "只用你自己启动的有界面 Chromium，浏览器资料只在内存",
        "**禁止**用开发者日常浏览器、它已有的资料或登录会话",
        "**禁止**连接开发者已打开的浏览器",
        "**禁止**用 Codex 内置浏览器或无界面窗口",
        "登录由开发者本人在这个窗口里完成",
        "**禁止**在登录页输入",
        "**禁止**读取或复制口令、Cookie、token、页面存储",
        "**禁止**保存登录状态",
        "登录后只打开本应用的在线预览 `/business-ui/<应用 ID>/preview`",
        "**禁止**打开发布管理页、正式入口、我的资产、其他应用、容器地址",
        "**禁止**真实付款和授权，**禁止**发布",
        "页面条目做完、开发者收回同意或出错停止时关闭浏览器",
        "「④ 用浏览器验收」",
    ):
        assert fact in red_lines, fact
    workspace = _read("reference/开发者中心与工作区.md")
    browser = workspace.split("### ④ 用浏览器验收", 1)[1].split("\n### ", 1)[0]
    for fact in (
        "`launch(headless=False)` 加 `new_context`", "`--isolated`、不带 `--headless`",
        "**禁止**用 `launch_persistent_context`、`--user-data-dir`、`--storage-state`、`--save-session`",
        "`https://goalfymax.goalfyai.cn`", "`https://goalfymax.pre.goalfyai.cn`",
        "应用 ID 原样取工作区 `app.json` 的 `id`", "`resource_group_id`", "地址上不加 `asset_version_id`",
        "**必须**先在当前草稿 `ship` 到 `success` 再打开", "去掉 `?` 与 `#` 之后的部分",
        "开发者的原话用 `task_manager(action=\"insert\", entry_type=\"checkpoint\")` 记下",
    ):
        assert fact in browser, fact
    # 启动参数只写在这一处
    for path in SKILL_ROOT.rglob("*.md"):
        if path.name == "开发者中心与工作区.md":
            continue
        text = path.read_text(encoding="utf-8")
        assert "launch_persistent_context" not in text and "--isolated" not in text, path
    assert "#### 看页面只用开发者中心" not in workspace
    assert "test:e2e:layout" in workspace


def test_preview_failures_are_read_from_preview_session_code():
    """R-367 options D：预览打不开按 preview-session 的 code 判读，3024 先重新 ship，不定版、不下线、不先提反馈。"""
    browser = _read("reference/开发者中心与工作区.md").split("### ④ 用浏览器验收", 1)[1].split("\n### ", 1)[0]
    failure = browser.split("#### 预览打不开时", 1)[1].split("\n#### ", 1)[0]
    for fact in (
        "「Agentic APP 不存在或加载失败」", "HTTP 状态仍是 200", "`POST /business-uis/<应用 ID>/preview-session`",
        "`browser_network_requests`", "`browser_network_request` 只取 response-body",
        "**禁止**读取或保存成功的 `preview-session` 响应",
        "3027「预览部署尚未就绪」", "3024「智能应用已下线，预览容器不在线」", "3028「暂无可预览的提交版本」",
        "3024 不表示应用被下线", "**禁止**定版、下线或先提反馈", "在当前草稿行重新 `ship` 到 `success`",
        "`ship` 成功后重开仍是这几种结果，才 `submit_dev_feedback`", "3023「预览会话不存在或已过期」", "3040", "3041",
    ):
        assert fact in failure, fact


def test_untestable_page_items_are_recovered_then_marked_untested():
    """R-367 O2：页面条目一律由 AI 测；测不了先按恢复办法处理，仍不行标「未测」写原因，开发者照样可以上线。"""
    browser = _read("reference/开发者中心与工作区.md").split("### ④ 用浏览器验收", 1)[1].split("\n### ", 1)[0]
    untestable = browser.split("#### 测不了时", 1)[1]
    for fact in (
        "页面条目一律由你在浏览器里测", "**禁止**请开发者在在线预览或其他地方代测", "开发者的口头回报不作「通过」的证据",
        "开发者不同意启动浏览器", "不启动、不追问", "浏览器起不来", "`npx playwright install chromium`",
        "问是否同意由你运行", "**禁止**改用其他浏览器或已登录的会话", "身份方式不可用或预览打不开",
        "结论写「未测」、证据写「无」", "开发者照常可以说「可以上线」进入 ⑤，你不追问、不因此拒绝定版",
    ):
        assert fact in untestable, fact
    acceptance = _read("stages/4-试用验收.md")
    for fact in (
        "先问开发者是否同意你启动浏览器", "测不了的先恢复再标「未测」",
        "**禁止**请开发者在在线预览、演示预览或其他页面代测", "开发者的口头回报不算证据",
        "| 未测的 |", "有「未测」条目为 `partial`", "「未测」的条目不用出这道题",
    ):
        assert fact in acceptance, fact
    assert "我试不了" not in acceptance and "本机版" not in acceptance


def test_launch_finalizes_without_requesting_release():
    """R-367 options E：⑤ AI 定版，报告结果与实际花费，说明发布影响；不请开发者发布、不在发布的版本上验证。"""
    launch = _read("stages/5-上线.md")
    for fact in (
        "`finalize` 的时间必须晚于「可以上线」的 checkpoint",
        "你不调用发布、不等发布，也不在发布的版本或正式实例上做验证",
        "「发布后已安装的使用者会更新到这一版；正式入口和到点自动化在发布后才能用；发不发、发给谁由你定」",
        "本段 N；累计 N；上限 N", "| 未测的 |", "| ④ 验过什么 |",
        "**禁止**写「请你发布」或等开发者回「发布了」", "工单正常结单，不因为还没发布而停住",
    ):
        assert fact in launch, fact
    for retired in ("在正式版里真跑一次", "**不传** `business_ui_data_space`", "run_once", "我试不了"):
        assert retired not in launch, retired
    skill = _read("SKILL.md")
    assert "**禁止**请开发者发布、等发布或在发布的版本上做验证" in skill


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
    """在线预览只要草稿部署成功；需要上线、发布的操作列在同一张表里，上线不是发布。"""
    deploy = _read("reference/部署与版本.md")
    assert "### 哪些用草稿就行，哪些要先上线" in deploy
    assert "不为打开它去 finalize" in deploy
    assert "| 开发者本人从「我的资产」进正式入口、在自动化面板开真实到点规则 | | ✓ | ✓ |" in deploy
    for path in ("reference/开发者中心与工作区.md", "stages/4-试用验收.md"):
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
    """判断题答完后一路做到 ④ 交报告；制作中的测试费用已在 PRD 同意，不再逐次等开发者。"""
    skill = _read("SKILL.md")
    assert "② 的判断题答完后，一路做到 ④ 交出验收报告" in skill
    assert "开发者确认 PRD 即视为同意" in skill
    assert "先向开发者说明费用并取得同意" not in _read("stages/3-制作.md")
    assert "部署预览前要先把场景包上线" not in _read("design/PRD.md")


def test_confirmed_interface_beats_preset_look():
    """开发者要的界面是最高依据：G1 主动问、确认页必填、预置件可用可不用、参考网站只借样式、验收要对照。"""
    pages = _read("reference/前端页面.md")
    for fact in (
        "### 界面以开发者为准，预置件可用可不用",
        "**开发者在确认页「界面」一节和之后反馈里说的样子**",
        "用不用预置件、用多少、改到什么程度由你按开发者要求判断",
        "**禁止**只换品牌色、圆角就当作满足了开发者的风格要求",
        "外壳（导航、布局、配色体系）也可以自己写",
        "自写或大改时**必须**保住平台行为，不是外观",
        "### 参考网站",
        "**只借样式，不搬内容**",
        "**禁止**保留对参考站接口、脚本或 CDN 的引用",
    ):
        assert fact in pages, fact
    requirement = _read("stages/1-需求确认.md")
    assert "界面三问（参考、第一眼看到什么、整体感觉）" in requirement
    assert "发之前核对界面三问都有答案" in requirement
    prd = _read("design/PRD.md")
    assert "开发者不指定，按《前端页面》界面风格自定" in prd
    assert "页面的**最高依据**，高于脚手架" in prd
    assert "**按 PRD「界面」写业务页**" in _read("stages/3-制作.md")
    assert "16. 页面样子与 PRD「界面」一致" in _read("checklists/验收清单.md")

def test_route_reads_and_writes_app_db_through_the_dataset_tool():
    """应用库读写走数据集工具：db() 唯一定义在《编排脚本》，读失败按空、写失败 blocked；业务 FA 建时挂工具只读；数据集 FA 只留存量。"""
    script = _read("reference/编排脚本.md")
    for fact in (
        "### 读写应用库",
        "async def db(sql, mode=\"reader\", params=None, why=\"读写应用库\"):",
        "**禁止**改成 `**kwargs` 展开",
        "读库不用包",
        "`preload_toolset_ids` 里要有一个装了工具组「query_business_app_dataset」的工具集",
        "jsonb_to_recordset(:rows::jsonb)",
    ):
        assert fact in script, fact
    assert "<写库 FA 的 mr_name>" not in script and "<读库 FA 的 mr_name>" not in script
    db_block = script[script.index("async def db("):script.index("```", script.index("async def db("))]
    assert "**kwargs" not in db_block and "raise" not in db_block
    assert "except Exception as exc" in db_block and 'body.get("results") or []' in db_block
    assert "not_a_business_app_project" in script and "冒泡无法验证真实读写" not in script
    assert "写库包在 `if not ctx.dry_run:` 里" in script and "**跳过不是删除**" in script
    # 三种模板（拉数落库、查库判读写回、生成写库）都写应用库，各有一处写库包在 dry_run 判断里
    assert script.count("if not ctx.dry_run:  # 冒泡跳过写库，真跑照常写") == 3
    template = _read("reference/数据模板.md")
    for fact in (
        "GOALFYAI_TOOL_query_business_app_dataset",
        'list_assets(asset_type="tool_group", keyword="query_business_app_dataset")',
        "**禁止**退回「把素材都从入口传进来」",
        "**禁止**让 FA 用 `mode=\"writer\"`",
        "只为存量路线保留，新路线不用",
        "业务键在模板里必须有唯一约束",
    ):
        assert fact in template, fact
    assert "async def db(" not in template
    making = _read("stages/3-制作.md")
    assert "开发者本人的正式实例" in template and "写库包在 `if not ctx.dry_run:` 里" in making
    plan = _read("stages/2-方案.md")
    assert "现在就读 [../reference/数据模板.md]" in plan
    assert "建 FA 时就按" in making and "把工具组「query_business_app_dataset」也装进来" in making
    assert "不管施工单怎么写" in making and "任一项不满足先改，禁止 preview / create" in making
    for field in ("`materials_text`", "`records`", "`customer_profile`", "`query_db`", "`sql_literal`"):
        assert field in making, field
    assert "**禁止**自写 `sql_literal()`" in template and "读出来交给 FA 总结、判断是允许的" in template
    assert "禁止**改成入口传全部素材或规则预填" in plan
    # R-367 options H：② 的「入口字段放哪」细表移到《数据模板》，段文件只链接
    assert "### 入口字段放哪" in template and "**禁止**同一个值既放入口又读库" in template
    assert "「入口字段放哪」" in plan and "| 这个值 | 放哪 |" not in plan
    assert "json 是脚本环境内置的" in script and "**禁止**补 `import json`" in script
    assert "冒泡时跳过、不报「未入库」" in script and "冒泡时跳过（见" in template
    assert "### 读长期数据集（不是智能应用的应用库）" in script
    assert "不能铺底，交给 FA 挂工具查" in template
    scaffold = _read("reference/脚手架与预置件.md")
    assert "**禁止**加 `--strip-components`" in scaffold and "tar -xzf <包> -C <应用目录>" in scaffold


def test_delivery_review_reply_only_action_key():
    """线上 50829：审阅应答夹带商家数据被拒后应用没展示；Skill 写明只提交 action_key、展示被拒原因。"""
    pages = _read("reference/前端页面.md")
    assert "**交付审阅只提交所选动作**" in pages
    assert "`data.field_errors`" in pages
    assert "DELIVERY_REVIEW_REPLY_INVALID" in _read("reference/报错对照.md")


def test_online_tab_named_zaixian_yulan():
    """工作台右栏分页名是「在线预览」，Skill 不再出现「在线试用」「在线使用」等叫法。"""
    root = Path(__file__).resolve().parents[1] / "skills" / "business-app-creator"
    for path in root.rglob("*"):
        if path.suffix in (".md", ".yaml") and path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "在线试用" not in text and "在线使用" not in text, path


def test_app_db_routes_prove_with_workspace_real_run():
    """读写应用库的路线：③ 不为冒泡改脚本，④ 带 workspace 真跑并用 verify(project_id) 作证据，不为真跑 finalize。"""
    making = _read("stages/3-制作.md")
    assert "`passed` 由 ④ 真跑补上" in making
    assert "**不要**为了让冒泡通过把读库包进 `dry_run`" in making and "`fallback_*`" in making
    acceptance = _read("stages/4-试用验收.md")
    assert 'business_ui_data_space="workspace"' in acceptance
    assert 'otpe_manage(action="verify", task_id, tpe_id, project_id)' in acceptance
    assert "先 `business_ui_manage(action=\"finalize\")` 上线再跑" not in acceptance
    assert "不要为真跑去 finalize" in acceptance and "读写应用库的路线不能用冒泡或结单门豁免代替这一步" in acceptance
    assert "BUSINESS_UI_NOT_DEPLOYED" in acceptance and "BUSINESS_UI_NOT_DEPLOYED" in _read("reference/报错对照.md")
    # 出口要接上 ③「passed 由 ④ 真跑补上」；残留的「核对上线版本 / 先定版自测」会把 Agent 引去定版
    assert "每条 TPE 最近一次 `verify(tpe_id, project_id)` 为 `passed`" in acceptance
    assert "按第 3 步核对上线版本" not in acceptance
    deploy = _read("reference/部署与版本.md")
    assert "按 G6 第 3 步先定版自测" not in deploy and "首版先 finalize" not in deploy
    assert "`run_once` 要先定版，读写正式实例的真跑要先定版并发布，制作和验收都不用它们" in deploy


def test_dev_feedback_reports_by_blocking():
    """平台问题按阻塞程度报：走不下去立即提并带两项标注，已绕过与诉求交付时汇总，应用自身问题不提。"""
    skill = _read("SKILL.md")
    assert "平台问题按阻塞程度报" in skill and "已经绕过去的也照提" not in skill
    assert 'blocking="blocked"' in skill and "`attribution`" in skill
    assert "⑤ 上线或本次会话结束时汇总成一条提交" in skill and "先 `query_dev_feedback` 查本人未关闭的反馈" in skill
    assert "应用自己的脚本、页面、数据格式、提示词问题自己改，不提交" in skill
    errors = _read("reference/报错对照.md")
    assert "`platform_defect`" in errors and "`skill_mismatch`" in errors and "`environment`" in errors
    assert "汇总成一条 `submit_dev_feedback`" in _read("stages/5-上线.md")
    assert "绕过后继续" not in _read("stages/4-试用验收.md")


def test_shell_success_is_judged_by_exit_code_of_whole_pipeline():
    """T-4417：shell 成败只看退出码，管道前段失败要用 && 或子 shell 内 pipefail 显式表达。"""
    script = _read("reference/编排脚本.md")
    for fact in ("### shell 步骤的成败", "退出码只看**最后一条命令**", "( set -o pipefail;", "|| true"):
        assert fact in script, fact
    assert "共用一个会话" in script and "只写在子 shell 的括号里" in script
