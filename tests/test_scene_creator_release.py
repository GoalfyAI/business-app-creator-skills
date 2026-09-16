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


def test_workflow_guidance_distinguishes_output_end_states():
    # Workflow 三种结束语义的正本随 §7.3 下沉到 references/平台对象与运行模型.md（1.8.0）
    skill = (SKILL_ROOT / "references" / "平台对象与运行模型.md").read_text(encoding="utf-8")
    checklist = (SKILL_ROOT / "checklists" / "编排型TPE验收检查清单.md").read_text(
        encoding="utf-8"
    )

    for document in (skill, checklist):
        assert "技术失败" in document
        assert "合法无产物" in document
    assert "禁止用空字符串或虚构路径凑成功对象" in skill
    assert "只删除文件字段的 `required`" in checklist


def test_workflow_guidance_routes_event_workflows_through_business_runtime():
    """业务事件必须触发正式业务路线；无事件单 Workflow 仍可直接派发。"""
    # 路由器约束 5 讲"单节点业务路线"，执行形态正本（references）讲"直接派发"——合并断言
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8") + (
        SKILL_ROOT / "protocols" / "事实决定授权与变更.md"
    ).read_text(encoding="utf-8") + (
        SKILL_ROOT / "references" / "平台对象与运行模型.md"
    ).read_text(encoding="utf-8")
    asset_stage = (SKILL_ROOT / "modules" / "P3-执行形态与路线制作.md").read_text(encoding="utf-8")
    checklist = (SKILL_ROOT / "checklists" / "编排型TPE验收检查清单.md").read_text(
        encoding="utf-8"
    )
    acceptance = (SKILL_ROOT / "checklists" / "场景包验收检查清单.md").read_text(
        encoding="utf-8"
    )

    for document in (skill, checklist, acceptance):
        assert "单节点业务路线" in document
        assert "直接派发" in document
    assert "验证身份只用于本次 Bubble" in asset_stage
    assert "不得让脚本、Agent、业务应用或 MCP 调用方伪造" in checklist
    assert "只由服务端在正式路线运行中持久化生成" in acceptance


def test_workflow_guidance_separates_delivery_verification_from_business_acceptance():
    """最终交付必须先核验真实结果，再由明确责任方完成业务审阅。"""
    design = (SKILL_ROOT / "modules" / "P1-业务基线细则.md").read_text(encoding="utf-8")
    challenge = (SKILL_ROOT / "checklists" / "方案挑战检查清单.md").read_text(
        encoding="utf-8"
    )
    acceptance = (SKILL_ROOT / "checklists" / "场景包验收检查清单.md").read_text(
        encoding="utf-8"
    )
    assert "交付核验回答" in design
    assert "最终审阅回答" in design
    assert "质量检查编排型 TPE" in challenge
    assert "若声明了修订、重做或改路线" in acceptance
    assert "能力容器只声明对外稳定的资产契约" in design
    assert "属于平台实现细节" in design
    assert "没有把 Max Runtime 的 Agent 边界通知" in challenge
    assert "Runtime 直接执行所选" in design
    assert "只有已声明的 `agent_gate` 边界" in acceptance


def test_single_skill_seven_stage_layout():
    """v3：scene-creator 与 app-creator 已并入 business-app-creator——阶段层 G1–G7、模块层 P1–P8、协议层四份、两层 Checklist。"""
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    protocol = (SKILL_ROOT / "protocols" / "事实决定授权与变更.md").read_text(encoding="utf-8")

    for stage in ("G1-业务目标与范围", "G2-关键能力可行性", "G3-运行设计与验收基线", "G4-核心执行单元验证",
                  "G5-后端业务闭环验证", "G6-用户操作闭环验证", "G7-预发布与交付"):
        assert (SKILL_ROOT / "stages" / f"{stage}.md").is_file(), stage
    assert len(list((SKILL_ROOT / "modules").glob("P*.md"))) == 8
    assert len(list((SKILL_ROOT / "protocols").glob("*.md"))) == 4
    assert (SKILL_ROOT / "checklists" / "G门禁检查清单.md").is_file()
    assert (SKILL_ROOT / "checklists" / "U业务行为验收明细.md").is_file()
    assert (SKILL_ROOT / "scripts" / "feedback_report.py").is_file()
    assert not (ROOT / "skills" / "scene-creator" / "SKILL.md").exists()
    assert not (ROOT / "skills" / "app-creator" / "SKILL.md").exists()
    assert "name: business-app-creator" in router
    for g in ("G1", "G2", "G3", "G4", "G5", "G6", "G7"):
        assert f"stages/{g}-" in router
    assert "先包后应用只是工程前置" in protocol
    assert "能力容器" in router


def test_desktop_workbench_and_app_directory_contract():
    """桌面接管工作台；每应用独立目录，不能恢复旧网页启动前置。"""
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    display = (SKILL_ROOT / "protocols" / "阶段展示与证据等级.md").read_text(
        encoding="utf-8"
    )

    assert "Goalfy App" in router
    assert "apps/<本应用目录名>" in router
    assert "GOALFY_DEV_FRAME_ANCESTORS" in router
    assert "http://127.0.0.1:5180/" not in router
    assert 'download_app_template(template="app_workbench")' not in router
    assert "./run-dev.sh start" not in router
    assert "HTML 方案包" in display
    assert "统一入口是应用工程根下 `docs/proposal/index.html`" in display
    assert "七份 md 给 Agent 保留事实与完整证据" in router


def test_retired_workbench_template_keeps_app_scaffold_and_cloud_workspace():
    """取消工作台模板不等于取消应用脚手架、版本门禁或资料保存。"""
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    versions = (SKILL_ROOT / "references" / "脚手架版本与升级.md").read_text(
        encoding="utf-8"
    )
    preview = (SKILL_ROOT / "modules" / "P5-应用脚手架与页面实现.md").read_text(
        encoding="utf-8"
    )
    stage = (SKILL_ROOT / "stages" / "G6-用户操作闭环验证.md").read_text(
        encoding="utf-8"
    )

    assert "开发者中心不再作为脚手架下发" in router
    assert "旧的 `download_app_template` 工作台下载入口不再使用" in router
    assert 'business_ui_bundle(action="download_template"' in router
    for tool in ("workspace_remote_status", "workspace_pull", "workspace_push"):
        assert f"`{tool}`" in router
    assert "更新 App 不会替当前应用迁移脚手架" in versions
    assert "业务应用自己的预览与后端调试服务仍按模板准备" in preview
    assert "不另起开发者中心" in stage
    for path in SKILL_ROOT.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert 'download_app_template(template="app_workbench")' not in content, path
        assert "./run-dev.sh start" not in content, path


def test_desktop_resume_preserves_local_progress_before_cloud_restore():
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    recovery = (SKILL_ROOT / "protocols" / "状态恢复知识归属与平台适配.md").read_text(
        encoding="utf-8"
    )

    assert "先读当前应用本地文件" in router
    for rule in (
        "本机接续，本地工程仍在",
        "换机或本地缺失",
        "本地与云端都有内容",
        "不默认写回或删除本地文件",
        "不只凭 `updatedAt`、阶段号或版本字符串判断谁较新",
        "冲突未解决前不整份覆盖任一侧",
        "不包含之后未部署的改动",
        "服务端没有并发版本保护",
        "恢复会话不等于恢复文件，恢复文档不等于恢复源码",
    ):
        assert rule in recovery
    assert "接续顺序固定：`workspace_remote_status`" not in recovery
    assert "工单是唯一能跨轮次续作的载体" not in recovery


def test_app_progress_contract_does_not_describe_workbench_layout():
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    recovery = (SKILL_ROOT / "protocols" / "状态恢复知识归属与平台适配.md").read_text(
        encoding="utf-8"
    )

    assert "新建会话不等于新建应用" in router
    assert "保留其他会话的新改动" in router
    assert "同步到方案 HTML" in recovery
    assert "阶段状态的正本是应用工程根的 `workspace.json`" in recovery
    assert "开发者中心只认这七个键" not in recovery
    for path in SKILL_ROOT.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        for layout in ("左栏", "右栏", "开发者在右侧", "三栏各管一件事"):
            assert layout not in content, path


def test_g3_proposal_allows_reading_interaction_without_business_or_screenshot_gate():
    pages = (SKILL_ROOT / "modules" / "P5-应用脚手架与页面实现.md").read_text(
        encoding="utf-8"
    )
    stage = (SKILL_ROOT / "stages" / "G3-运行设计与验收基线.md").read_text(
        encoding="utf-8"
    )

    display = (SKILL_ROOT / "protocols" / "阶段展示与证据等级.md").read_text(
        encoding="utf-8"
    )

    assert "HTML 展示给开发者看的方案，阶段 MD 保存完整事实与证据" in pages
    assert "不要求完整可操作原型，也不要求截图" in pages
    assert "操作前后可并列展示或轻量切换" in stage
    assert "允许阅读辅助交互，不把它当成业务能力" in display
    assert "Tab 切换、展开收起、页内定位、示例状态切换" in display
    assert "禁止**接真实接口或把示例切换当成已验证的业务交互" in display
    for path in SKILL_ROOT.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        for retired in ("没有截图的页面视为未设计", "MD + 原型本地地址一起交开发者",
                        "每页截图展示", "正文与截图目录指针", "可点原型", "可点的页面原型",
                        "做不成才用截图", "截图作为展示替代", "开发者点得动"):
            assert retired not in content, path


def test_proposal_package_supports_local_assets_and_readable_fallback():
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    display = (SKILL_ROOT / "protocols" / "阶段展示与证据等级.md").read_text(
        encoding="utf-8"
    )

    assert "HTML 组包，不限定为单页长文" in router
    for rule in (
        "统一入口不等于所有内容必须塞进一个文件",
        "配套样式、脚本、图示与必要的子页面",
        "所有内容从入口可达",
        "脚本失败时仍能读到概览、承诺和待决定项",
        "键盘可用、焦点与选中态可辨",
        "禁止**加载包外或外网资源",
    ):
        assert rule in display
    for path in SKILL_ROOT.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert "不依赖点击、切换或脚本执行才能看到" not in content, path
        assert "不依赖点击或脚本执行，也不要求截图" not in content, path


def test_proposal_visual_guidance_prioritizes_readability_over_decoration():
    display = (SKILL_ROOT / "protocols" / "阶段展示与证据等级.md").read_text(
        encoding="utf-8"
    )

    for rule in (
        "结构为查阅服务，不强制一页长文",
        "避免多层 Tab 套折叠",
        "关键风险不能藏进默认收起的详情",
        "审美为阅读服务，直观、克制，有业务感",
        "不把每句话都塞进一张卡片",
        "窄宽度下不挤字、不裁切关键信息",
        "避免模板化的“AI 感”",
        "不把方案做成营销落地页或复杂仪表盘",
        "交付前按阅读路径检查",
    ):
        assert rule in display


def test_proposal_feedback_uses_conversation_without_annotation_promises():
    display = (SKILL_ROOT / "protocols" / "阶段展示与证据等级.md").read_text(
        encoding="utf-8"
    )

    assert "开发者在开发对话中说明哪里不对" in display
    assert "由你核对当前应用、对应页面、业务步骤和版本" in display
    assert "不代表工作台提供自动截图、批注或反馈回传" in display
    assert "每条自动带页面、步骤、版本上下文" not in display


def test_business_app_guidance_does_not_restore_removed_form_prefill():
    """所有 app-creator 指引都必须沿用静态 Schema，不能从旁支重新引入已下线预填。"""
    documents = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SKILL_ROOT.rglob("*.md")
    )

    assert "已知信息的预填由业务应用实现" not in documents
    assert "稳定业务事实由应用后端在发起时拼进 `submit_data`" in documents


def test_business_ui_identity_is_bound_before_g5_transition():
    """G4 出口先创建身份草稿并 bind；G5 只完善同一草稿。"""
    router = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    g4 = (SKILL_ROOT / "stages" / "G4-核心执行单元验证.md").read_text(
        encoding="utf-8"
    )
    g5 = (SKILL_ROOT / "stages" / "G5-后端业务闭环验证.md").read_text(
        encoding="utf-8"
    )

    assert "G1 到 G4 的新应用两处写真实的 `null`" in router
    assert "绑定成功才允许进入 G5" in router
    assert 'business_ui_manage(action="create"' in g4
    assert "npm run scaffold:bind -- --business-ui-id <真实 ID>" in g4
    assert "本阶段不打包部署" in g4
    assert "完善并部署 G4 已创建的验证实例" in g5
    assert "禁止**在这里再 create" in g5


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
    (copied / "references" / "unreleased.md").write_text("unreleased\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="source_files 与 Skill 唯一源文件不一致"):
        release_module.check_release(copied)


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
