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
    assert "给使用者看的列表、正文、结论仍以业务字段出现" in script
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

    # 职责边界唯一正本在编排脚本.md「FA 与脚本的职责边界」「建 FA」，速查与 ③ 只引用
    assert "一个 FA 只承担一个语义责任" in script
    assert "| 编排脚本 | 确定性准备、分发、汇合、幂等写入和固定收口 | 判断内容真假" in script
    platform = (skill_root / "reference/平台对象速查.md").read_text(encoding="utf-8")
    assert "FA 与编排脚本各管什么、怎么建 FA，见 [编排脚本.md](编排脚本.md)「FA 与脚本的职责边界」" in platform

    making = (skill_root / "stages/3-制作.md").read_text(encoding="utf-8")
    assert ("| 同类事实错误、引用错误或无产物连续两轮 | 停止加字段、不原样重跑，"
            "按 [../reference/编排脚本.md](../reference/编排脚本.md)「FA 与脚本的职责边界」重划职责") in making


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
    assert "挂的场景包至少有一条路线" in _read("SKILL.md")
    assert "平台要求应用挂的场景包至少有一条路线；只有规则步骤的应用也建一条最小的单节点路线" in _read("reference/业务路线.md")
    prd = _read("design/PRD.md")
    assert "只有脚本步骤的应用写一句「平台要求挂一条最小路线，应用界面可以不发起它」" in prd
    assert "费用与副作用" in prd and "可以上线" in prd


def test_identity_rules_forbid_forging_runtime_ids():
    router = _read("SKILL.md")
    assert "`workflow_runtime_id` 只由服务端生成" in router
    assert "`business_id` 由调用方在发起时生成" in router


def test_bubble_verify_and_full_run_boundaries_are_documented():
    # 瘦身后 stages/3 只写做什么并引用 reference，调用写法收在编排脚本.md / 业务路线.md
    making = _read("stages/3-制作.md")
    for fact in ("`needs_bubble`", "`assemble`", "`full_run`", "「建、校验和上线 TPE」", "「assemble 怎么用」",
                 "「冒泡」", "「冒泡与真跑能证明什么」"):
        assert fact in making, fact
    script = _read("reference/编排脚本.md")
    routes = _read("reference/业务路线.md")
    for fact in ('otpe_manage(action="verify"', "`needs_bubble`", "full_run=true", "if not ctx.dry_run:"):
        assert fact in script, fact
    for fact in ('scene_package_manage(action="assemble"', "full_run=true", 'otpe_manage(action="verify"'):
        assert fact in routes, fact
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
        ("reference/编排脚本.md", "一个 FA 只承担一个语义责任", "一个 FA 可承担多个语义责任"),
        ("reference/编排脚本.md", "| 编排脚本 | 确定性准备、分发、汇合、幂等写入和固定收口 |", "| 编排脚本 | 准备、分发、判断内容 |"),
        ("stages/3-制作.md", "连续两轮 | 停止加字段、不原样重跑", "连续出现 | 继续加字段"),
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
    assert "在把 `current_stage` 改成 G5 之前建好应用身份并回填工作区，见 [../reference/数据模板.md](../reference/数据模板.md)「建应用身份与挂模板」" in making
    identity = _read("reference/数据模板.md").split("### 建应用身份与挂模板", 1)[1].split("\n### ", 1)[0]
    assert "（在把 `current_stage` 改成 G5 之前）" in identity
    assert "在应用根执行返回的 `scaffold_bind_command`，回填 `app.json` 与 `WORKSPACE.md`" in identity
    workspace = _read("reference/开发者中心与工作区.md")
    assert "进 G5 前用 `npm run scaffold:bind" in workspace


def test_acceptance_deploys_draft_for_workspace_runs():
    """④ 部署草稿供 workspace 真跑，页面条目在本机版上验；挂本人场景包草稿也能部署，上线应用时草稿随应用一起上线。 [任务:T-3976]"""
    acceptance = _read("stages/4-试用验收.md")
    assert "deployed_scaffold_version" in acceptance
    assert "调用方式（`workspace`、家族 ID、`business_id`、`wait` / `reply`、`route_runs`）按 [../reference/部署与版本.md](../reference/部署与版本.md)「真跑」" in acceptance
    deploy = _read("reference/部署与版本.md")
    assert 'business_ui_id=<应用家族 ID>, business_ui_data_space="workspace"' in deploy.split("### 真跑", 1)[1].split("\n### ", 1)[0]
    assert "页面条目由你在应用的本机版上用无头浏览器照条目操作" in acceptance
    assert 'finalize_asset_version_online(asset_type="scenario_pack"' not in acceptance
    assert "挂着本人场景包草稿也能部署，场景包不用先上线" in acceptance
    assert "挂在应用上的本人场景包草稿不单独上线，随应用一起上线" in _read("stages/5-上线.md")
    assert "挂在应用上的本人场景包草稿随应用一起上线：finalize 时平台先校验、再把它一起上线" in deploy


def test_task_closing_gate_and_waiver_are_documented():
    # ⑤ 只引用：结单门与豁免在部署与版本.md「三道门」，被拒码在报错对照.md「版本与结单」，resolve 在「上线」
    launch = _read("stages/5-上线.md")
    assert "**结单门**：按 [../reference/部署与版本.md](../reference/部署与版本.md)「三道门」" in launch
    assert "最近一次失败或没法验证时，先问开发者是否接受，接受后写豁免" in launch
    assert "被拒按 [../reference/报错对照.md](../reference/报错对照.md)「版本与结单」处理" in launch
    assert "`resolve` 反读上线版本与场景包版本记进工单" in launch
    deploy = _read("reference/部署与版本.md")
    assert "route_verification_waived" in deploy.split("### 三道门", 1)[1].split("\n### ", 1)[0]
    assert 'business_ui_manage(action="resolve")' in deploy.split("### 上线", 1)[1].split("\n### ", 1)[0]
    closing = _read("reference/报错对照.md").split("### 版本与结单", 1)[1].split("\n### ", 1)[0]
    assert "| `WORKFLOW_TASK_ROUTE_BUBBLE_EVIDENCE_REQUIRED` |" in closing


def test_stage_names_follow_workspace_not_skill():
    """旧应用的阶段名可能是旧名：Skill 只按 G 键更新状态，不改名。"""
    workspace = _read("reference/开发者中心与工作区.md")
    assert "只改状态不改名" in workspace
    # 总原则 4 删「旧应用」历史说法，规则改为正面写：以工作区已有阶段名为准、按 G 键对应
    assert "| 阶段名 | 以工作区里已有的为准，按 G 键对应，只改状态不改名 |" in workspace


def test_stages_hand_over_on_explicit_conditions():
    """五段按序推进，每段交棒条件写在段文件里；确认 PRD、整版方案、「可以上线」不能跳过。"""
    skill = _read("SKILL.md")
    assert "左栏" not in skill
    for rule in (
        "每段出口写在段文件「交棒条件」，满足了才进下一段",
        "要开发者确认的（① 回「确认这一版」，② 当前整版方案已确认，④ 看过报告说「可以上线」）没确认就停在当前段等，没有跳段",
        "**修订也走五段**：每段只做和改动有关的部分，④ ⑤ 每次都做",
    ):
        assert rule in skill, rule
    # ③ 能交给 ④、④ 报告过硬门这两条出口写在段文件里
    assert "③ 交棒：应用根 `npm run verify` 全绿" in _read("stages/4-试用验收.md")
    assert "验收报告过了 2.5 的硬门并已发给开发者" in _read("stages/4-试用验收.md").split("## 5. 交棒条件", 1)[1]
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
        "5-上线.md": "用 `business_ui_stage` 写 G7，`next_stage` 填 `closeout`，在下一步 `complete` 之前写",
    }
    for name, fact in exits.items():
        text = _read(f"stages/{name}")
        assert "business_ui_stage" in text, name
        assert fact in text, name
    # SKILL.md 只指路：一句规则加链接，business_ui_stage 参数写法只在开发者中心那一处
    assert (
        "存哪、阶段标记与阶段记录（每段出口用 `business_ui_stage` 写本段的 G 项）怎么写见 "
        "[reference/开发者中心与工作区.md](reference/开发者中心与工作区.md)"
    ) in _read("SKILL.md")
    workspace = _read("reference/开发者中心与工作区.md")
    for fact in ("### 阶段记录", "`completion`", "`next_plan`", "`skipped`", "**一项调一次**", "**只写不读**",
                 "| G6 交棒条件都满足，但有「未测」条目 | `passed` | `partial`"):
        assert fact in workspace, fact
    for path in SKILL_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if path.name == "开发者中心与工作区.md":
            continue
        assert "completion=" not in text and "next_plan=" not in text, path


def test_write_task_reads_skill_version_from_installed_skill():
    """FK-519：建 write 工单必须从已安装 SKILL.md 读 skill_version，被拒处理链到工单闸门。"""
    skill = _read("SKILL.md")
    start = skill.split("## 7. 开工", 1)[1].split("## 8.", 1)[0]
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
                 "需求全部完成后才生成完成版", "需求没做完就生成完成版，或用 `npm run dev` 起工作源码，想让演示预览提前显示",
                 "completed-preview.json",
                 "「应用尚未完成」", "「预览未启动」", "「暂时无法确认应用完成状态」", "不启动服务",
                 "「重新启动」", "「重新检查」", "内容已保存，切换到完成版"):
        assert fact in workspace, fact
    assert "工作台读应用目录 `.workbench/dev-host.json`" not in workspace
    assert "成功后工作台自动显示" not in workspace
    assert "进 ④ 前你先生成本地完成版，开发者可以在「演示预览」看，生成办法见 [../reference/开发者中心与工作区.md](../reference/开发者中心与工作区.md)「演示预览为空」" in _read("stages/4-试用验收.md")
    assert "在开发者中心的「演示预览」里看" not in _read("stages/3-制作.md")


def test_data_writes_follow_row_ownership():
    data = _read("reference/数据模板.md")
    for fact in ("只更新已建行的 agent 列：按入口带入的 id 执行 `UPDATE … WHERE id = :id`", "不写身份列",
                 "由后端的生产回流接口建行", "row_version=row_version+1"):
        assert fact in data, fact
    # 读库 FA 以 found 布尔作出口：唯一正本移到编排脚本.md「失败出口怎么写」
    assert "读应用库这类只读查询以 `found` 布尔作出口即可" in _read("reference/编排脚本.md")


def test_business_app_guidance_does_not_restore_removed_form_prefill():
    pages = _read("reference/前端页面.md")
    # 总原则 4 删「已下线」历史说法，改为正面写：入口表单没有预填，schema 只来自契约包
    assert "按 `getForms(formId)` 渲染，没有预填" in pages
    assert "表单 schema 的唯一来源是契约包 `forms/` 与 `getForms(formId)`" in pages
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
    # SKILL.md 正好 200 行（预算上限），改内容不加行，免得先撞行预算
    original = skill_file.read_text(encoding="utf-8")
    changed = original.replace("本文件只放跨段规则", "本文件只放跨段的规则", 1)
    assert changed != original
    skill_file.write_text(changed, encoding="utf-8")

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
        ("stages/2-方案.md", lambda text: text + "\n" * 60, "行预算"),
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
    # 上线不等于发布：正式入口（开发者本人也一样）要发布后才能打开；部署后、上线前用在线预览。
    # DECISIONS §7：导航路径删掉，写「从 GoalfyMax 打开这个应用」
    for fact in ("**部署状态和入口分两句写**", "生产构建直开返回 `HOST_REQUIRED`", "本地开发构建直开只进 Mock",
                 "开发者本人和使用者从 GoalfyMax 打开这个应用", "入口是工作台「在线预览」",
                 "上线后、发布前，正式入口仍打不开（开发者本人也一样）",
                 "只用于核对平台绑定与诊断，不打开、不写进任何给人看的东西、不发给任何人"):
        assert fact in deploy, fact
    assert "直接打开只会进入 mock 模式" not in deploy
    assert "GoalfyMax → 智能应用 → 预览" not in deploy
    launch = _read("stages/5-上线.md")
    assert "消费者视角的 `entry_url`" not in launch
    assert "| 应用 | 名称、上线版本、`entry_url`" not in launch
    result = _read("design/验收报告与上线结果.md")
    assert "发布前开发者想自己看，用工作台「在线预览」。不写容器地址" in result
    assert "`entry_url`" not in result
    assert "读预览入口" not in _read("stages/4-试用验收.md")


def test_draft_resolve_is_not_platform_blocked():
    """T-4130（并入 T-4062）：上线前 resolve 报只有草稿是正常结果，草稿验收走在线预览，不记平台阻塞。"""
    deploy = _read("reference/部署与版本.md")
    assert "`resolve` 只认上线版本，上线前报「还没有上线版本（只有草稿）」是正常结果" in deploy
    assert "为了真跑或打开在线预览去 finalize；它们只要部署成功" in deploy
    acceptance = _read("stages/4-试用验收.md")
    assert "`resolve` 报还没有上线版本 | 同一文件「真跑」" in acceptance
    errors = _read("reference/报错对照.md").split("### 真跑", 1)[1].split("\n### ", 1)[0]
    row = next(line for line in errors.splitlines() if line.startswith("| 上线前 `resolve` 报「还没有上线版本」"))
    assert "不是平台问题；草稿验收用 `workspace` 真跑和本机版" in row


def test_browser_red_line_points_to_one_local_acceptance_section():
    """需求责任人 10-27：SKILL.md 第 0 节一条浏览器红线，只许本机版；本机版做法只写在「④ 本机版页面验收」一处，Skill 不写站点地址、不判断环境。"""
    skill = _read("SKILL.md")
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    for fact in (
        "**禁止**用任何浏览器（含宿主内置浏览器、Playwright）打开正式入口、登录页、在线预览或容器地址，也不借用开发者的登录会话",
        "页面验收只在应用根 `npm run dev:restart` 起的本机版上用无头浏览器做",
        "「本机版页面验收」",
    ):
        assert fact in red_lines, fact
    # 裁决 D35：Skill 不记站点地址，开工时问开发者在哪个站点开发、原样填参数（站点地址由下面 goalfyai.cn 全文检查拦）
    assert "不传 `--environment`：宿主（Studio）提供了环境，脚手架自己读。只有它报「缺少环境」时，才问开发者在哪个 GoalfyMax 站点开发" in skill
    workspace = _read("reference/开发者中心与工作区.md")
    local = workspace.split("### 本机版页面验收", 1)[1].split("\n### ", 1)[0]
    for fact in (
        "GoalfyMax 正式入口、登录页、在线预览或演示预览的地址、容器地址要走平台登录和身份注入，不在你要访问的范围里；开发者已登录的会话也不借用",
        "浏览器边界的红线在 [../SKILL.md](../SKILL.md)「红线」",
        "访问被工具审批拒绝时到此为止：不重试、不绕过", "`npm run dev:restart` 后台起本机版",
        "`npm run dev:status`", "`frontend/docs/dev-host-testing.md`", "`Bridge ready`", "内容区空白的截图不作证据",
        "做到付款或授权窗口出现为止，本机版里的结果是 Mock",
        "依赖平台登录身份、真实宿主桥接的部分本机版上看到的不作证据",
        "打开过的本机路由", "`test:e2e:layout`", "`npm run dev:stop`",
    ):
        assert fact in local, fact
    # 本机版的启动与浏览器做法只写在这一节，Skill 正文不写 GoalfyMax 站点地址
    for path in SKILL_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "goalfyai.cn" not in text, path
        if path.name != "开发者中心与工作区.md":
            assert "Bridge ready" not in text and "dev:stop" not in text, path
    for retired in ("### ④ 用浏览器验收", "#### 五步", "#### 登录后无权访问或会话失效", "#### 测不了时", "#### 预览打不开时",
                    "launch(headless=False)", "--isolated", "登录好了", "preview-session", "| 环境 | GoalfyMax 地址 |"):
        assert retired not in _skill_markdown(), retired
    assert "test:e2e:layout" in workspace


def test_online_preview_failure_reported_by_developer_rechecks_deployment():
    """开发者说在线预览打不开：你不打开它，先核对部署、需要时重新 ship；3024 不表示下线，不上线、不下线、不先提反馈。"""
    workspace = _read("reference/开发者中心与工作区.md")
    section = workspace.split("### 演示预览与在线预览", 1)[1].split("#### 演示预览为空", 1)[0]
    assert "真实链路；开发者自己想看时用，你不打开" in section
    assert "打不开或未就绪的处置见 [报错对照.md](报错对照.md)「部署与预览」" in section
    # 处置唯一正本移到报错对照.md「部署与预览」的 3024 一行
    errors = _read("reference/报错对照.md").split("### 部署与预览", 1)[1].split("\n### ", 1)[0]
    row = next(line for line in errors.splitlines()
               if line.startswith("| 开发者说在线预览只显示「Agentic APP 不存在或加载失败」（`code` 3024）"))
    for fact in (
        "不表示应用被下线", '先 `business_ui_manage(action="get")` 核对当前草稿有没有部署成功',
        "在当前草稿行重新 `ship` 到 `success` 再请他重开", "`ship` 已成功仍打不开，才按平台问题报",
        "应用的上线、下线状态保持不动",
    ):
        assert fact in row, fact
    assert "| 开发者说在线预览打不开或未就绪 | 同一文件「部署与预览」 |" in _read("stages/4-试用验收.md")


def test_untestable_page_items_are_fixed_or_marked_untested():
    """需求责任人 10-27：页面条目一律由 AI 在本机版上测；本机版起不来先自己修，只有线上才能验证的标「未测」写原因，不请开发者代测，开发者照样可以上线。"""
    # 「未测」唯一枚举移到 stages/4「2.4 逐条判定」；本机版起不来的修法留在开发者中心「本机版页面验收」
    local = _read("reference/开发者中心与工作区.md").split("### 本机版页面验收", 1)[1].split("\n### ", 1)[0]
    acceptance = _read("stages/4-试用验收.md")
    judging = acceptance.split("### 2.4 逐条判定", 1)[1].split("\n### ", 1)[0]
    online_only = judging.split("**「未测」只用于下面几类**", 1)[1]
    for fact in (
        "| 依赖平台登录身份", "「只有线上才能验证：平台登录身份」", "| 依赖真实宿主桥接", "「只有线上才能验证：真实宿主桥接」",
        "| 到点真触发 |", "| 使用者从目录或分享打开 |", "本机版能看的部分照常测并写证据",
        "其余部分结论「未测」、证据「无」，原因照下表原文写", "测不了的不请开发者代测",
        "| 本机版起不来，按「本机版页面验收」修过仍不行 | 「本机版起不来」，加做过哪些处理和错误原文 |",
    ):
        assert fact in online_only, fact
    assert "**禁止**请开发者在在线预览、演示预览或其他页面代测" in _read("SKILL.md")
    assert "开发者的口头回报、他在在线预览或演示预览（含 Studio 本地演示）里看到的、已发布的版本，都不作证据" in judging
    result = _read("design/验收报告与上线结果.md")
    assert "| 未测的 | ④ 有「未测」条目时单列" in result and "并写开发者自己怎么看" in result
    broken = local.split("#### 本机版起不来时", 1)[1]
    for fact in ("你自己修", "`npx playwright install chromium`", "工程本身的问题回 ③ 修", "仍起不来的按 ④「2.4 逐条判定」记「未测」"):
        assert fact in broken, fact
    assert "问是否同意由你运行" not in broken
    assert "报告里有「未测」条目时同样进 ⑤，不追问" in _read("stages/5-上线.md")
    for fact in (
        "本机版上用无头浏览器照条目操作", "「本机版页面验收」", "本机版能测的条目都要测",
        "证据写部署编号与真跑的 `project_id` 或「本机版」", "有「未测」为 `partial`", "「未测」的条目不出这道题",
        "每条「未测」都写了原因，且属于 2.4「未测」表里的一类，原因与情况对得上",
        "有「未测」条目时说「可以上线」照样算",
    ):
        assert fact in acceptance, fact
    for retired in ("我试不了", "启动浏览器", "登录好了", "身份方式不可用", "浏览器已关闭"):
        assert retired not in acceptance, retired
    # 走查 10-29：报告用业务列，页面条目写「本机版：」开头，技术字段只进 G6
    assert "页面条目写「本机版：」加操作步骤" in result
    assert "这类核对字段写进阶段文档 G6，不放进报告" in result
    report = _read("design/开发文档/验收报告.md")
    assert "【填：「本机版：」或「真跑：」开头】" in report and "启动浏览器" not in report
    assert "<th>project_id</th>" not in report and "## 截图证据" in report
    for name in ("PRD.md", "方案.md", "制作进度.md"):
        assert "启动浏览器" not in _read(f"design/开发文档/{name}"), name


def test_deploying_to_online_preview_needs_explicit_authorization():
    """陈羽杰 10-27 对 4518 的口径：部署到开发者在线预览要明确授权，PRD 同意不能推定；还没同意时依赖已部署版本的条目记「未测」；所有宿主一致。
    需求责任人 10-28：④ ⑤ 对未部署原因统一说「还没同意部署」。"""
    acceptance = _read("stages/4-试用验收.md")
    # 部署授权原句与「什么算同意」唯一正本在 SKILL.md「红线」；④ 2.1 本机先测、2.2 先问部署再部署
    local_first = acceptance.split("### 2.1 本机先测", 1)[1].split("### 2.2", 1)[0]
    assert "不用部署的先做：页面条目、`npm --prefix frontend run check`、本地布局回归" in local_first
    deploy = acceptance.split("### 2.2 先问部署，再部署", 1)[1].split("### 2.3", 1)[0]
    for fact in (
        "部署要开发者单独授权：之前没有明确同意过，就在原对话里照 [../SKILL.md](../SKILL.md)「红线」的部署授权原句问一次",
        "同意的原话记 checkpoint；之前明确同意过的直接沿用",
        "部署只到开发者的在线预览，不上线、不发布",
        "依赖已部署版本的条目（`workspace` 真跑、开发工作集里查到的行）按 2.4 的表记「未测」",
        "开发者在没部署的情况下说「可以上线」，按 [5-上线.md](5-上线.md)「2.1 只上线已部署的草稿」处理",
        # 走查 10-29：还没回答部署时不扣住报告
        "本机版的检查做完就交报告，不等部署的回答",
        "部署的问句放在交报告的同一条消息里",
    ):
        assert fact in deploy, fact
    assert "不交报告。" not in deploy
    skill = _read("SKILL.md")
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    # B18 改写：「不加必点按钮或表单」改为正面写「在原对话照抄原句问一次，文字或语音的明确同意都算」
    for fact in (
        "没有明确授权时在原对话照抄原句问一次：「是否将当前应用部署到开发者在线预览，用于试用验收？这不包含目录正式发布。」",
        "文字或语音的明确同意都算，原话记 checkpoint；已明确同意过的沿用，不重复问",
        "确认 PRD、PRD 里写的「先试用再决定」、开发者说「可以上线」都不算同意部署",
    ):
        assert fact in red_lines, fact
    assert "| 开发者还没同意部署，条目依赖已部署版本 | 「你还没同意部署到在线预览」 |" in acceptance
    assert "开发者对部署的原话" in acceptance
    assert "开发者同意部署的，最近一次部署 `status=success`；还没同意的，依赖已部署版本的条目都记了「未测」" in acceptance
    assert "④ 因为开发者还没同意部署而没有部署过的" in _read("stages/5-上线.md")
    assert "哪些情况可以记「未测」及原因怎么写，都按 [../stages/4-试用验收.md](../stages/4-试用验收.md)「2.4 逐条判定」" in _read("checklists/验收清单.md")
    for retired in ("暂不同意", "因开发者不同意而没有部署过的"):
        assert retired not in _skill_markdown(), retired
    assert "要部署而没有授权" in skill
    # 所有宿主一致：Studio 宿主部署和上线分开授权，④ 照 stages 做
    assert "宿主指令里的部署、上线、发布与本文同义，部署和上线分开授权" in skill
    assert "问是否部署到开发者在线预览" in _read("design/交接消息.md")
    assert "还没部署到在线预览的应用上不了线，你回『可以上线』时我会再问一次是否部署" in _read("design/验收报告与上线结果.md")


def test_launch_only_finalizes_a_deployed_draft():
    """O11（需求责任人 10-27）：⑤ 只上线 ④ 已部署成功的草稿；没部署过的如实说上不了线，按 ④ 2.1 原句再问一次，同意后部署、补测再上线，不同意就停。
    需求责任人 10-28：补测有「好不好你说了算」的给开发者看结果、请他再说一次「可以上线」。
    需求责任人 10-29：补测没通过、AI 能改的自己改好重测，设上限 3 轮；改不了或到上限才问开发者接不接受先上线。"""
    launch = _read("stages/5-上线.md")
    step = launch.split("### 2.1 只上线已部署的草稿", 1)[1].split("\n### ", 1)[0]
    for fact in (
        "上线的是 ④ 已部署成功的最新草稿",
        "如实说「还没部署到在线预览，上不了线」，再照 [../SKILL.md](../SKILL.md)「红线」的部署授权原句问一次",
        "同意：部署到 `success`，按 ④「2.3 工作集真跑」「2.4 逐条判定」补测依赖已部署版本的条目",
        "原因在你能改的东西里（应用代码、场景包配置、数据）：不问开发者，按 ④「2.6 按反馈改」改好、重新部署、重测，补测最多 3 轮",
        "原因你改不了（平台故障、外部数据源、要开发者授权或付费），或 3 轮后仍没通过",
        "「接受，先上线 / 等改好再上线」选择题",
        "选「接受」的记「没通过，开发者选了接受」，照常上线",
        "有「好不好你说了算」的，把实际结果给开发者看，请他看过后再说一次「可以上线」",
        "补测的条目都是通过、开发者选了接受，或判断类他再说过「可以上线」，才上线",
        "不同意：停在这里，告诉开发者这一版还没部署、所以没有上线，不上线",
    ):
        assert fact in step, fact
    assert "都有结论后再上线" not in step
    assert "补测的条目全部通过" not in step
    assert "补测后请他再说过一次的，晚于再说的那一次" in launch
    assert "| ④ 没部署过，开发者说「可以上线」 |" in launch
    assert "| 部署后补测有「没通过」或「好不好你说了算」 |" in launch
    assert "我能改的自己改好再测（最多 3 轮），改不了或 3 轮还没过的逐条问你接不接受先上线" in _read("design/验收报告与上线结果.md")
    for retired in ("即同意上线所需的部署", "同意上线所需的部署"):
        assert retired not in _skill_markdown(), retired
    assert "你上线报告里验过、④ 已部署成功的那一版" in launch
    assert "没部署成功过的草稿上不了线" in _read("reference/部署与版本.md")


def test_skill_uses_deploy_finalize_release_terms_only():
    """需求责任人 10-27：部署 = ship 到开发者在线预览；上线 = finalize，成为开发者自己的正式版；发布 = 开发者在发布管理页发给使用者。正本不出现「定版」等混用说法。
    需求责任人 10-28：MCP 文字里的「定版」转述时说成「上线」；只允许 SKILL.md 三词说明里唯一一句点名这个旧称。"""
    # 旧称对照的唯一位置移到平台对象速查.md「术语表」（DECISIONS 总原则 6），另允许同文件「常见错误」点名一次
    old_name_row = "| 定版、提请属主定版、等属主定版 | 上线、提请属主上线、等属主上线 |"
    old_name_error = "- 给开发者转述时照搬 MCP 里的「定版」等旧词；按本文「术语表」改说。"
    glossary = SKILL_ROOT / "reference/平台对象速查.md"
    for path in sorted(SKILL_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if path == glossary:
            assert text.count(old_name_row) == 1 and text.count(old_name_error) == 1
            assert old_name_row in text.split("### 术语表", 1)[1].split("\n### ", 1)[0]
            text = text.replace(old_name_row, "").replace(old_name_error, "")
        for retired in ("定版", "上线部署", "部署上线"):
            assert retired not in text, (path.relative_to(SKILL_ROOT).as_posix(), retired)
    skill = _read("SKILL.md")
    terms = skill.split("- **部署、上线、发布各指一件事**", 1)[1].split("\n- **", 1)[0]
    assert "MCP 文字里的旧称按 [reference/平台对象速查.md](reference/平台对象速查.md)「术语表」转述" in terms
    assert "交接消息一律改说「上线」「提请属主上线」「等属主上线」，不出现旧称" in _read("design/交接消息.md")
    for fact in (
        '部署：`business_ui_bundle(action="ship")` 把草稿放到开发者自己的在线预览，在 ④ 做，要开发者单独授权（见「红线」）',
        '上线：开发者说「可以上线」后你 `business_ui_manage(action="finalize")`，在 ⑤ 做；这一版成为开发者自己的正式版，使用者还看不到',
        "发布：开发者在发布管理页把应用发给使用者。正式使用（包括开发者本人正式使用、到点自动运行）只认发布；你不做、不请求、不等待",
        # 裁决 F1（FB-711）：上线结果原句改为带「要自己正式使用或给别人用，需要你在发布管理页发布」
        "「这一版成为你自己的正式版；要自己正式使用或给别人用，需要你在发布管理页发布，发不发布由你决定」",
    ):
        assert fact in terms, fact
    sentence = "这一版成为你自己的正式版；要自己正式使用或给别人用，需要你在发布管理页发布，发不发布由你决定"
    assert _read("design/验收报告与上线结果.md").count(sentence) >= 2
    assert "这一版成为开发者自己的正式版；要自己正式使用或给别人用，需要开发者在发布管理页发布，发不发布由他决定" in _read("stages/5-上线.md")
    assert "部署、上线、发布三个词的含义见 [../SKILL.md](../SKILL.md)「角色与用词」" in _read("reference/部署与版本.md")


def test_studio_host_launch_wording_means_deploy():
    """需求责任人 10-28：Studio 宿主下部署照 ④ 2.1 原句单独问，「可以上线」不当作同意部署。
    工作台 530dc4ff 起宿主指令的部署、上线、发布与 Skill 同义；较早版本把部署叫上线，按部署处理。
    脚手架 986238a：Studio 会话环境自动带文档模式，Skill 不另传 --document-mode。"""
    skill = _read("SKILL.md")
    studio = next(line for line in skill.splitlines() if line.startswith("- **Studio 宿主**"))
    assert "宿主指令里的部署、上线、发布与本文同义，部署和上线分开授权" in studio
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    assert "已明确同意过的沿用，不重复问" in red_lines
    assert "开发者说「可以上线」都不算同意部署" in red_lines
    assert "Studio 宿主指令里说的「上线」指这里的部署" not in skill
    # 总原则 4 删「较早版本的宿主指令把部署叫上线」这类历史分支
    assert "较早版本" not in _skill_markdown()
    section = _studio_section()
    for fact in (
        "五段的顺序、每段确认什么、④ 怎么验收、⑤ 做到哪一步，都按 `SKILL.md` 和 `stages/` 执行，和其他宿主相同",
        "`GOALFY_SCAFFOLD_DOCUMENT_MODE=studio`",
        "不另传 `--document-mode`",
        "`document_mode: studio` 写进 `WORKSPACE.md`，不生成 `docs/proposal/`",
    ):
        assert fact in section, fact
    start = skill.split("## 7. 开工", 1)[1].split("## 8.", 1)[0]
    assert "Studio 宿主不另传文档模式参数（同文件「Studio 宿主」）" in start


def test_page_items_pass_only_with_local_steps_and_screenshot_or_assertion():
    """需求责任人 10-28：页面条目「通过」必须附本机版操作步骤和截图文件路径（或断言原文），报告硬门写明；判定表写清冒泡、真跑、未测、没通过。"""
    # 判定标准唯一正本移到 stages/4「2.4 逐条判定」（DECISIONS §4），开发者中心与验收清单只引用
    acceptance = _read("stages/4-试用验收.md")
    judging = acceptance.split("### 2.4 逐条判定", 1)[1].split("\n### ", 1)[0]
    for fact in (
        "**页面条目**：「通过」要有本机版操作步骤，以及截图文件路径或断言原文；只请求过页面地址（`curl`、HEAD 返回 200）不算操作过",
        "| 操作步骤、截图文件路径或断言原文、打开过的本机路由；",
        "读写应用库的条目只有冒泡证据（读库返回 `not_a_business_app_project`、写库被 `ctx.dry_run` 跳过）时，自查记录写「冒泡无法验证真实读写」，不算通过",
        "回 2.3 用 `workspace` 真跑、在开发工作集查到写入的行才算通过",
        "**没通过**：结果不对、报错、该写的行没写，记「没通过」，按 2.6 改；挡上线，开发者选了接受的除外",
        "| 依赖平台登录身份", "| 依赖真实宿主桥接", "| 到点真触发 |",
    ):
        assert fact in judging, fact
    assert "有「未测」条目时说「可以上线」照样算" in acceptance  # 「未测」不挡
    gate = acceptance.split("报告的硬门，三条都满足才交：", 1)[1].split("\n### ", 1)[0]
    for fact in (
        "每条「通过」都有 2.4 要的证据，「全部条目」里后三列都填了",
        "有「冒泡无法验证真实读写」的行就不满足",
        "有一条不满足：G6 记 `failed`，不交报告",
    ):
        assert fact in gate, fact
    assert "未验证：只冒泡过" not in acceptance
    workspace = _read("reference/开发者中心与工作区.md")
    local = workspace.split("### 本机版页面验收", 1)[1].split("\n### ", 1)[0]
    assert "怎么判结论、哪些记「未测」，见 [../stages/4-试用验收.md](../stages/4-试用验收.md)「2.4 逐条判定」" in local
    assert "每条记操作步骤、截图文件路径（写进阶段文档 G6；不截图的写断言原文）和打开过的本机路由" in local
    checklist = _read("checklists/验收清单.md")
    for fact in (
        "结论和证据达到 ④「2.4 逐条判定」的标准",
        "怎么测、证据要到什么程度、哪些情况可以记「未测」及原因怎么写，都按 [../stages/4-试用验收.md](../stages/4-试用验收.md)「2.4 逐条判定」",
    ):
        assert fact in checklist, fact


def test_every_write_task_entry_carries_skill_version():
    """需求责任人 10-28：main 上各处建 write 工单带 `skill_version` 的要求在五段版里补回。"""
    same = "`skill_version` 按 [../SKILL.md](../SKILL.md)「开工」建工单"
    assert f"1. 建 write 工单，{same}（从 ① 进来的沿用原工单）。" in _read("tasks/能力试用.md")
    assert f"1. 建 read 工单（只读协作者也是 read 工单）；转修复时新建 write 工单并传 `continued_from_task_id`，{same}。" in _read("tasks/诊断.md")
    assert f"1. 建 write 工单，{same}；" in _read("tasks/修订.md")
    assert f"新建 write 工单并传 `continued_from_task_id`，{same}。" in _read("tasks/接续.md")
    assert f"要改应用或同步状态时用 write 工单（{same}）" in _read("tasks/用户反馈.md")
    errors = _read("reference/报错对照.md")
    assert "新建 `mode=\"write\"` 工单并传 `continued_from_task_id`，按 [../SKILL.md](../SKILL.md)「开工」带 `skill_version`。" in errors
    assert "**`SCENE_SKILL_VERSION_MISSING`** — 本次 create 没有填 `skill_version`（或填了 `dev`），工单**未创建**。" in errors
    # 编辑协作者改应用走 tasks/修订.md（上面已核 skill_version）
    assert "[../tasks/修订.md](../tasks/修订.md) 的协作者做法" in _read("reference/多人协作.md")


def test_stages_advance_one_by_one_without_local_only_exit():
    """需求责任人 10-27：五段一段一段推进，交棒靠开发者确认；没有 Studio 专有的「只做本地演示、不进 ④ ⑤」路径。"""
    skill = _read("SKILL.md")
    assert "没确认就停在当前段等，没有跳段" in skill
    body = _skill_markdown()
    for retired in ("只做本地演示", "只要本地演示", "只要本地修改", "不进 ④ ⑤", "做到 ③ 本地检查和桌面演示为止",
                    "未部署、未验收、未上线"):
        assert retired not in body, retired


def test_launch_finalizes_without_requesting_release():
    """R-367 options E：⑤ AI 上线，报告结果与实际花费，说明发布影响；不请开发者发布、不在发布的版本上验证。"""
    launch = _read("stages/5-上线.md")
    for fact in (
        "上线的时间晚于这句话的 checkpoint",
        "上线后即结单，发布不在结单条件里",
        "这一段不再请开发者确认什么，也不请他发布、不等发布",
    ):
        assert fact in launch, fact
    # 上线结果的写法与照抄原句唯一正本在 design/验收报告与上线结果.md（裁决 F1 改了「发布会怎样」原句）
    result = _read("design/验收报告与上线结果.md")
    for fact in (
        "「发布后你自己和已安装的使用者会用上这一版；正式入口和到点自动运行在发布后才能用，你自己也一样；发不发、发给谁由你定」",
        "本段 N；累计 N；上限 N", "| 未测的 |", "| ④ 验过什么 |",
        "「要你做的」不写「请你发布」，也不等开发者回「发布了」再结单",
    ):
        assert fact in result, fact
    for retired in ("在正式版里真跑一次", "**不传** `business_ui_data_space`", "run_once", "我试不了"):
        assert retired not in launch, retired
    skill = _read("SKILL.md")
    assert "你不调用发布、不请开发者发布、不等发布，也不在发布的版本或正式实例上验证；工单照常结单" in skill


def test_stage_name_describes_concrete_business_step():
    """执行状态条显示 stage_name：写具体动作，多个业务步骤各发一次 stage_started。"""
    script = _read("reference/编排脚本.md")
    for fact in (
        "`stage_name` 就是使用者在应用顶部执行状态条上看到的那句话",
        "写成「正在<动作><对象>」",
        "`stage_name` 写成「正在处理本次任务」「正在执行」这类泛词，或几个业务步骤共用一次 `stage_started`，使用者在状态条上看不出在做什么",
        "每个步骤开始前各发一次 `stage_started`，各用自己的 `event_key`、`stage_key` 并各自声明契约",
        "同一步骤内部的工具调用不再发",
        "- 每个 `tool()` 后机械发一次事件。",
    ):
        assert fact in script, fact


def test_online_preview_needs_deployed_draft_not_finalize():
    """在线预览只要草稿部署成功；需要上线、发布的操作列在同一张表里，上线不是发布。"""
    deploy = _read("reference/部署与版本.md")
    table = deploy.split("### 草稿、上线、发布各能做什么", 1)[1].split("\n### ", 1)[0]
    assert "| 开发者在工作台「在线预览」里看（真实身份、开发工作集、路线） | ✓ | | |" in table
    assert "为了真跑或打开在线预览去 finalize；它们只要部署成功" in deploy
    assert "| 开发者本人从正式入口打开、在「自动化」面板开真实到点规则 | | ✓ | ✓ |" in table
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
    """整版方案确认后一路做到 ④ 交报告；制作中的测试费用已在 PRD 同意，不再逐次等开发者。"""
    skill = _read("SKILL.md")
    assert "② 整版方案确认后一路做到 ④ 交出验收报告" in skill
    assert "**确认 PRD 即同意 PRD 列出的费用与副作用**" in skill
    assert "之后照做，跑完在交付物「费用与副作用」补实际花费、在交接消息里报，不逐次问" in skill
    assert "先向开发者说明费用并取得同意" not in _read("stages/3-制作.md")
    assert "部署预览前要先把场景包上线" not in _read("design/PRD.md")


def test_confirmed_interface_beats_preset_look():
    """开发者要的界面是最高依据：G1 主动问、确认页必填、预置件可用可不用、参考网站只借样式、验收要对照。"""
    pages = _read("reference/前端页面.md")
    for fact in (
        "### 界面以开发者为准，预置件可用可不用",
        "**PRD「界面」一节和开发者之后反馈里说的样子**",
        "用不用预置件、用多少、改到什么程度由你按开发者要求判断",
        "只换品牌色、圆角不算满足开发者的风格要求",
        "外壳（导航、布局、配色体系）也可以自己写",
        "自写或大改时保住平台行为，不是外观",
        "### 参考网站",
        "**只借样式，不搬内容**",
        "不保留对参考站接口、脚本或 CDN 的引用",
    ):
        assert fact in pages, fact
    requirement = _read("stages/1-需求确认.md")
    assert "界面三问（参考、第一眼看到什么、整体感觉）" in requirement
    rounds = _read("design/按轮问.md")
    assert "发「我理解的是这些」之前核对这几题都有答案" in rounds and "| 界面三问：" in rounds
    prd = _read("design/PRD.md")
    assert "开发者不指定，按《前端页面》界面风格自定" in prd
    assert "页面的**最高依据**，高于脚手架" in prd
    assert "**业务页**：PRD「界面」一节是页面的最高依据" in _read("stages/3-制作.md")
    assert "16. 页面样子与 PRD「界面」一致" in _read("checklists/验收清单.md")

def test_route_reads_and_writes_app_db_through_the_dataset_tool():
    """应用库读写走数据集工具：db() 唯一定义在《编排脚本》，读失败按空、写失败 blocked；业务 FA 建时挂工具只读；数据集 FA 只留存量。"""
    script = _read("reference/编排脚本.md")
    for fact in (
        "### 读写应用库",
        "async def db(sql, mode=\"reader\", params=None, why=\"读写应用库\"):",
        "不改成 `**kwargs` 展开",
        "读库不用包",
        "`preload_toolset_ids` 里要有一个装了工具组「query_business_app_dataset」的工具集",
        "jsonb_to_recordset(:rows::jsonb)",
        'list_assets(asset_type="tool_group", keyword="query_business_app_dataset")',
        "挂不上时按 [报错对照.md](报错对照.md) 排查，取数方式保持由 FA 自己查",
        "提示词写明只用 `mode=\"reader\"`",
    ):
        assert fact in script, fact
    assert "<写库 FA 的 mr_name>" not in script and "<读库 FA 的 mr_name>" not in script
    db_block = script[script.index("async def db("):script.index("```", script.index("async def db("))]
    assert "**kwargs" not in db_block and "raise" not in db_block
    assert "except Exception as exc" in db_block and 'body.get("results") or []' in db_block
    assert "not_a_business_app_project" in script and "冒泡无法验证真实读写" not in script
    assert "写库包在 `if not ctx.dry_run:` 里" in script and "这是跳过不是删除" in script
    # 三种模板（拉数落库、查库判读写回、生成写库）都写应用库，各有一处写库包在 dry_run 判断里
    assert script.count("if not ctx.dry_run:  # 冒泡跳过写库，真跑照常写") == 3
    template = _read("reference/数据模板.md")
    for fact in (
        "GOALFYAI_TOOL_query_business_app_dataset",
        "要模型决定查什么的取数，没给 FA 挂工具，改成把素材全从入口传进来",
        "FA 只用 `mode=\"reader\"` 查；写库一律由脚本按 FA 的输出执行固定 SQL",
        "- 让 FA 用 `mode=\"writer\"` 直接写库。",
        "路线经平台数据集 FA（`GOALFYAI_FASTAGENT_Business_app_fastagent`）转一手去读写应用库；新路线不用它，修订时遇到改成脚本固定 SQL",
        "业务键在模板里有唯一约束",
        "`INSERT … ON CONFLICT` 的冲突目标必须是模板里已有的唯一约束",
    ):
        assert fact in template, fact
    assert "async def db(" not in template
    making = _read("stages/3-制作.md")
    assert "写开发者本人的正式实例" in _read("reference/部署与版本.md")
    assert "**反读自查**：每条读写应用库的路线 online 后反读，四项各记「有 / 没有」" in making
    assert "2. **写库包在 `if not ctx.dry_run:` 里**" in script.split("### 反读自查四项", 1)[1]
    plan = _read("stages/2-方案.md")
    assert "现在就读 [../reference/数据模板.md]" in plan
    assert "要按情况查应用库的，建时就挂应用库只读工具并反读确认" in making
    assert "（脚本要读写应用库时再加「query_business_app_dataset」）" in making
    # 建 FA 挂工具「不管施工单怎么写」与反读自查四项的定义收进编排脚本.md；③ 写「preview 前逐项自查」与「任一项没有回第 5 步改」
    assert "以这一步实际要不要按情况查库为准——施工单漏写的也挂，并回 ② 把施工单补上" in script
    assert "preview 前逐项自查，再 preview → create → online" in making
    assert "任一项「没有」回第 5 步改；四项都有，这条路线才能标「做好了」" in making
    assert "每条读写应用库的路线 preview 前逐项自查一遍" in script
    checks = script.split("### 反读自查四项", 1)[1].split("\n### ", 1)[0]
    for field in ("`materials_text`", "`records`", "`customer_profile`", "`fallback_*`"):
        assert field in checks, field
    assert "不自写 `sql_literal()`、`query_db()` 之类的转义或查询函数" in script
    assert "不自写 `sql_literal()`、`query_db()` 之类的转义或查询函数" in template and "读出来交给 FA 总结、判断是允许的" in template
    assert "[../reference/数据模板.md](../reference/数据模板.md)「编排脚本怎么读写应用库」逐行写清" in plan
    assert "| 执行中取数，要看上一步结果再决定查什么 | 业务 FA 挂上这个工具自己查" in template
    # R-367 options H：② 的「入口字段放哪」细表移到《数据模板》，段文件只链接
    assert "### 入口字段放哪" in template and "同一个值不既放入口又读库" in template
    assert "「入口字段放哪」" in plan and "| 这个值 | 放哪 |" not in plan
    assert "json 是脚本环境内置的" in script and "不补 `import json`" in script
    assert "冒泡时跳过、不报「未入库」" in script
    assert "写库语句包在 `if not ctx.dry_run:` 里（[编排脚本.md](编排脚本.md)「读写应用库」）" in template
    assert "### 读长期数据集（不是智能应用的应用库）" in script
    # 裁决 R1：取消「发起时铺底」，入口只放业务键和这次才给的值，库里已有的由脚本按业务键 db() 读
    assert "入口只放业务键和使用者这次才给的值；库里已有的由脚本按业务键用 `db()` 读，不由应用后端拼进发起报文" in template
    assert "铺底" not in template
    scaffold = _read("reference/脚手架与预置件.md")
    assert "不加 `--strip-components`" in scaffold and "tar -xzf <包> -C <应用目录>" in scaffold


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
    assert "冒泡里读空、写被跳过是预期" in making
    script = _read("reference/编排脚本.md")
    assert "为了让冒泡通过，把读库包进 `dry_run`、从入口塞数据、加 `fallback_*` 兜底或删掉读写" in script
    acceptance = _read("stages/4-试用验收.md")
    deploy = _read("reference/部署与版本.md")
    real_run = deploy.split("### 真跑", 1)[1].split("\n### ", 1)[0]
    assert 'business_ui_data_space="workspace"' in real_run
    assert "只要求应用已部署成功，不要求上线" in real_run
    assert 'otpe_manage(action="verify", task_id, tpe_id, project_id)' in acceptance
    assert "先 `business_ui_manage(action=\"finalize\")` 上线再跑" not in acceptance
    assert "为了真跑或打开在线预览去 finalize；它们只要部署成功" in deploy
    assert "冒泡和结单门豁免代替不了它" in acceptance
    assert "| 真跑报错、卡 `waiting-input`、`resolve` 报还没有上线版本 | 同一文件「真跑」 |" in acceptance
    errors_run = _read("reference/报错对照.md").split("### 真跑", 1)[1].split("\n### ", 1)[0]
    assert "| `BUSINESS_UI_NOT_DEPLOYED`（`run` 带 `workspace` 时） |" in errors_run
    # 出口要接上 ③「passed 由 ④ 真跑补上」；残留的「核对上线版本 / 先上线自测」会把 Agent 引去 finalize
    assert "每条 TPE 最近一次 `verify(tpe_id, project_id)` 为 `passed`" in acceptance
    assert "按第 3 步核对上线版本" not in acceptance
    assert "按 G6 第 3 步先定版自测" not in deploy and "首版先 finalize" not in deploy
    table = deploy.split("### 草稿、上线、发布各能做什么", 1)[1].split("\n### ", 1)[0]
    assert "| `business_ui_automation(run_once)`、`resolve` 反读、发布管理页预览 | | ✓ | |" in table
    assert "| 带 `business_ui_id` 不传 `workspace` 的真跑（读写正式实例） | | ✓ | ✓ |" in table
    assert "要应用已上线并发布，制作和验收不用它" in deploy
    assert "所以不用于 ④ ⑤ 的验证" in _read("reference/自动化.md")


def test_dev_feedback_reports_by_blocking():
    """平台问题按阻塞程度报：走不下去立即提并带两项标注，已绕过与诉求交付时汇总，应用自身问题不提。"""
    skill = _read("SKILL.md")
    platform = skill.split("## 10. 平台问题", 1)[1].split("## 11.", 1)[0]
    assert "已经绕过去的也照提" not in skill
    assert '阻塞的（按指引处理后仍走不下去、没有绕法）立即 `submit_dev_feedback(blocking="blocked")`' in platform
    assert "不阻塞的（已绕过、功能诉求）记进开发记录，⑤ 上线或会话结束时汇总成一条" in platform
    assert "应用自己的脚本、页面、数据格式、提示词问题自己改，不提交" in platform
    assert "[reference/报错对照.md](reference/报错对照.md)「平台问题怎么报」" in platform
    errors = _read("reference/报错对照.md")
    report = errors.split("### 平台问题怎么报", 1)[1].split("\n### ", 1)[0]
    assert "确实是平台问题时按阻塞程度报" in report
    assert "**`attribution`**（新建时必填）" in report
    assert "`platform_defect`" in report and "`skill_mismatch`" in report and "`environment`" in report
    assert "⑤ 上线或本次会话结束时和功能诉求汇总成一条" in report
    assert "新建前先 `query_dev_feedback` 查本人未关闭的反馈" in report
    assert "此时汇总成一条提交，没有就不提" in _read("stages/5-上线.md")
    assert "绕过后继续" not in _read("stages/4-试用验收.md")


def test_shell_success_is_judged_by_exit_code_of_whole_pipeline():
    """T-4417：shell 成败只看退出码，管道前段失败要用 && 或子 shell 内 pipefail 显式表达。"""
    script = _read("reference/编排脚本.md")
    for fact in ("### shell 步骤的成败", "退出码只看**最后一条命令**", "( set -o pipefail;", "|| true"):
        assert fact in script, fact
    assert "共用一个会话" in script and "只写在子 shell 的括号里" in script


# Studio 只管文档的保存、显示与确认，五段规则不变（需求责任人 10-27 定）；这些是文档回归检查，不是 Agent 行为评测。
def _studio_section() -> str:
    workspace = _read("reference/开发者中心与工作区.md")
    return workspace.split("### Studio 宿主", 1)[1].split("\n## ", 1)[0]


def _studio_row(stage: str) -> str:
    return next(line for line in _studio_section().splitlines() if line.startswith(f"| {stage} |"))


def _skill_markdown() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(SKILL_ROOT.rglob("*.md")))


def test_studio_only_governs_saving_display_and_confirmation():
    section = _studio_section()
    assert "Studio 只管文档怎么保存、显示和确认" in section
    assert "都按 `SKILL.md` 和 `stages/` 执行，和其他宿主相同" in section
    assert "`studio_write_proposal`" in section and "`studio_read_creation`" in section
    skill = _read("SKILL.md")
    assert "**Studio 宿主**：五段和以上规则照旧，只是交付物写成四份开发文档、没有方案页" in skill and "「Studio 宿主」" in skill
    assert "## Studio 适用方式" not in skill
    # 正文没有 flow/ 的 Studio 旁注，规则只写成五段的最终写法
    assert not any(line.startswith("> **Studio**") for line in _skill_markdown().splitlines())


def test_studio_confirms_prd_in_stage_one_and_plan_in_stage_two():
    """决定 1：① 的确认对象是 PRD、② 的确认对象是方案；Studio 四份文档按 documentType 保存，聊天里的明确同意经登记后算确认。"""
    # Studio 四份文档与确认登记唯一正本在 design/开发文档/README.md（DECISIONS 总原则 7），确认口径在 design/PRD.md
    docs = _read("design/开发文档/README.md")
    prd_row = next(line for line in docs.splitlines() if line.startswith("| PRD |"))
    plan_row = next(line for line in docs.splitlines() if line.startswith("| 方案 |"))
    assert "| `prd` | 要，确认这一版 |" in prd_row
    assert "| `proposal` | 要，只确认一次整版 |" in plan_row
    assert "方案" not in prd_row
    confirm = docs.split("## 确认怎么登记", 1)[1]
    assert "调 `studio_confirm_proposal`，传 `documentType`（`prd` 或 `proposal`）" in confirm
    assert "读回已确认才往下走：PRD 读到确认之前只查不建，方案读到确认之后才进 ③" in confirm
    assert "已确认范围内的修订以宿主返回的当前确认状态为准，不自行增加确认步骤" in confirm
    assert "`artifactId`、`version`、`digest` 这类核对字段只记进阶段文档" in confirm
    assert "方案另写 `docs/studio/proposal/acceptance.json`" in docs
    assert "只写当前段的文档：① 里只有 PRD，② 里才有方案，依此类推。还没到的段不写" in docs
    prd = _read("design/PRD.md")
    assert "开发者对**当前这一版**的明确同意" in prd and "新一版不继承旧版的确认" in prd
    assert "PRD 和方案的确认都不是部署或上线授权" in prd
    stage_one = _read("stages/1-需求确认.md")
    assert "这一段只交 PRD 这一份文档（Studio 下是开发文档 PRD）" in stage_one
    assert "开发者回「确认这一版」之前，工作区最多标到 G2，不建业务资产、不写编排脚本、不建表、不部署；开工建的工单和工作区" in stage_one
    assert "Studio 下读到这一版的确认" in stage_one.split("## 5. 交棒条件", 1)[1]
    stage_two = _read("stages/2-方案.md")
    assert "Studio 下写成开发文档「方案」，另交与验收条目一致的 `acceptance.json`" in stage_two
    assert "Studio 下读到当前这一版方案的确认" in stage_two.split("## 5. 交棒条件", 1)[1]
    assert "确认前不初始化业务工程" not in _skill_markdown()


def test_studio_launch_finalizes_without_catalog_publication():
    """决定 2：Studio 下 ⑤ 也只上线并报告，发布由开发者在发布管理页决定。"""
    # Studio 不另写 ⑤ 规则：SKILL「红线」的发布一行对所有宿主适用，Studio 节写明 ⑤ 与其他宿主相同
    launch = _read("stages/5-上线.md")
    assert "保存或登记结果未知时只查原操作结果，不重新写入" in launch
    assert "Studio 下上线结果写进开发文档「验收报告」最后一节" in launch
    assert "⑤ 做到哪一步，都按 `SKILL.md` 和 `stages/` 执行，和其他宿主相同" in _studio_section()
    skill = _read("SKILL.md")
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    assert "| 发布 | 你不调用发布、不请开发者发布、不等发布，也不在发布的版本或正式实例上验证；工单照常结单 |" in red_lines
    assert "**Studio 宿主**：五段和以上规则照旧" in skill
    assert "发布：开发者在发布管理页把应用发给使用者" in skill
    body = _skill_markdown()
    for retired in ("目录发布使用", "当前实际提供的 MCP 能力", "分别报告定版、目录发布和正式运行"):
        assert retired not in body, retired


def test_studio_acceptance_uses_local_version_and_workspace():
    """需求责任人 10-27：Studio 下 ④ 和其他宿主一样，页面条目在本机版上用无头浏览器验，业务结果在开发工作集里验；开发者看过的本地演示和已发布版本都不作证据。"""
    # Studio 节不再单列各段，④ 与其他宿主相同；Studio 特有的一句（桌面入口已在跑就直接用）在「本机版页面验收」
    section = _studio_section()
    assert "④ 怎么验收" in section and "和其他宿主相同" in section
    assert "/preview" not in section
    local = _read("reference/开发者中心与工作区.md").split("### 本机版页面验收", 1)[1].split("\n### ", 1)[0]
    assert "Studio 下桌面入口已在跑当前工程的开发服务时直接用它，不另起、不停掉" in local
    acceptance = _read("stages/4-试用验收.md")
    assert "业务结果在开发者同意部署后，用开发工作集真跑并查库" in acceptance
    assert "部署成功本身、开发者的口头回报、他在在线预览或演示预览（含 Studio 本地演示）里看到的、已发布的版本，都不作证据" in acceptance
    assert "五段和以上规则照旧" in _read("SKILL.md") and "Studio 本地演示和已发布版本都不作验收证据" in _read("SKILL.md")
    body = _skill_markdown()
    for retired in ("在线预览展示已发布正式版本", "只展示已发布版本", "本地验收"):
        assert retired not in body, retired


def test_studio_restricted_checks_only_supplement_local_acceptance():
    """决定 4：浏览器规则只在「④ 本机版页面验收」；宿主受限检查是补充，机器结果与 AI 在本机版上的操作分开记录。"""
    # 唯一正本在 stages/4「2.4 逐条判定」，对所有宿主适用
    judging = _read("stages/4-试用验收.md").split("### 2.4 逐条判定", 1)[1].split("\n### ", 1)[0]
    assert "宿主提供的受限检查能力的机器结果可以作补充，和你在本机版上的操作分开记，不代替页面条目的本机版操作" in judging
    body = _skill_markdown()
    for retired in ("不放开通用浏览器禁令", "开发者亲自操作"):
        assert retired not in body, retired


def test_studio_desktop_demo_scope_without_local_only_exit():
    """与五段不冲突的 Studio 规则：桌面演示、验收范围一致、不虚构流程；不再有「只做本地演示、不进 ④ ⑤」的出口，④ ⑤ 每次都做。"""
    section = _studio_section()
    assert "**演示**：桌面入口管理当前工程的开发服务，你只准备工程与依赖，不另起后台服务、不生成完成版" in section
    assert "`studio.acceptance.json` 与方案的 `acceptance.json` 验收范围一致" in section and "不自行增减条目" in section
    assert "不为纯数据管理应用虚构额外业务流程" in _read("stages/2-方案.md")
    assert "Studio 宿主的演示见同一文件「Studio 宿主」" in _read("stages/3-制作.md")
    assert "不部署、不进 ④ ⑤" not in section and "只做本地演示" not in section
    assert "不回写已确认的 PRD 和方案" in _read("design/开发文档/README.md")
    assert "写入结果未知" in section and "只查询原操作的结果，不重新发起写入" in section
    revision = _read("tasks/修订.md")
    assert "不进 ④ ⑤" not in revision and "只要本地修改" not in revision
    assert "要上线的修订 ④ 和 ⑤ 每次都做" in revision
    studio_revision = next(line for line in revision.splitlines() if line.startswith("- Studio 宿主："))
    assert "改动在已确认范围内的不自行增加确认步骤" in studio_revision
    assert "开发者这次只要本地演示" not in _read("stages/4-试用验收.md")


def test_publish_dependent_items_are_untested_with_reason():
    """需求责任人 10-27：取消「发布后才能看到」，到点真触发、从目录或分享打开记「未测」并写原因，⑤ 单列。"""
    assert "发布后才能看到" not in _skill_markdown()
    acceptance = _read("stages/4-试用验收.md")
    assert "`business_ui_automation(bubble)` 按自动化的入口跑一次" in acceptance
    assert "`bubble` 用冒泡按自动化的入口在开发工作集里跑一次，验处理逻辑" in _read("reference/自动化.md")
    assert "「到点真触发」另列一条，按下面的表记「未测」" in acceptance
    assert "| 到点真触发 | 「到点触发要等真实时间，且要发布后在正式入口开规则」 | 发布后在应用的「自动化」面板开规则，等到点看 |" in acceptance
    assert "| 使用者从目录或分享打开 | 「从目录或分享打开要先发布」 | 发布后从目录或分享打开看 |" in acceptance
    # 裁决 D14：报告结论改为四格（没通过 / 通过 / 要你判断 / 未测）加单列「开发者已接受的没通过」
    result = _read("design/验收报告与上线结果.md")
    assert "四格依次：没通过、通过、要你判断（好不好你说了算）、未测，四格相加等于总条数；再单列「开发者已接受的没通过」" in result
    assert "结论只有四种：通过 / 没通过 / 好不好你说了算 / 未测" in acceptance
    # 硬门：「未测」只能用表里的一类且原因对得上（代替旧的「以『要先发布』为由标了『未测』」反例）
    assert "每条「未测」都写了原因，且属于 2.4「未测」表里的一类，原因与情况对得上" in acceptance
    assert "**「未测」只用于下面几类**（唯一枚举）" in acceptance
    assert "| 未测的 | ④ 有「未测」条目时单列" in result and "到点真触发、从目录或分享打开，发布后看（写清怎么看）" in result
    assert "到点真触发按 ④「2.4 逐条判定」记「未测」，上线结果单列" in _read("checklists/验收清单.md")
    assert "到点真触发怎么记见 [../stages/4-试用验收.md](../stages/4-试用验收.md)「2.4 逐条判定」" in _read("reference/自动化.md")
