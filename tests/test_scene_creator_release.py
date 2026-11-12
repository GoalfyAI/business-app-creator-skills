import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest
import tomllib
import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "skills" / "agenticapp-creator"
SKILLS_ROOT = SKILL_ROOT.parent
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

# 随 Skill 发布的脚本：Studio 表单卡片、开发文档生成与用户反馈报告（路径相对 skills/）。
SHIPPED_SCRIPTS = (
    "agenticapp-host-studio/scripts/studio_card.mjs",
    "agenticapp-host-studio/scripts/build_studio_doc.mjs",
    "agenticapp-task-user-feedback/scripts/feedback_report.mjs",
)


def _copy_repo(tmp_path: Path) -> Path:
    """复制一份完整仓库结构，返回其中的 Skill 内容目录。"""
    for name in ("skills", "claude-code", "codex", ".claude-plugin", ".agents"):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in ("skill-release.json", "pyproject.toml", "uv.lock", "README.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    shutil.copy2(SCRIPT_PATH, tmp_path / "scripts" / SCRIPT_PATH.name)
    return tmp_path / "skills" / "agenticapp-creator"


def _manifest(skill_root: Path = SKILL_ROOT) -> dict:
    return json.loads((skill_root.parents[1] / "skill-release.json").read_text(encoding="utf-8"))


def _package_version(skill_root: Path = SKILL_ROOT) -> str:
    return _manifest(skill_root)["package_version"]


# ---------------------------------------------------------------- 仓库当前状态


def test_checked_in_release_is_current():
    manifest = release_module.check_release(SKILL_ROOT)

    assert manifest["skill_name"] == "agenticapp-creator"
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
    """两个平台的 Skill 副本必须与唯一源逐字节一致。"""
    release_module.check_platform_skills(SKILL_ROOT)

    for name in release_module.ALL_SKILLS:
        canonical = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
        for platform in release_module.PLATFORM_NAMES:
            copy = release_module._platform_skill_dir(SKILL_ROOT, platform) / name / "SKILL.md"
            assert copy.read_bytes() == canonical, (platform, name)
    # 只有 Codex 需要 openai.yaml，且只在入口
    assert (ROOT / "codex/skills/agenticapp-creator/agents/openai.yaml").is_file()
    for platform in ("claude-code",):
        target = release_module._platform_skill_dir(SKILL_ROOT, platform) / "agenticapp-creator" / "agents"
        assert not target.exists(), platform
    for platform in release_module.PLATFORM_NAMES:
        present = sorted(path.name for path in release_module._platform_skill_dir(SKILL_ROOT, platform).iterdir())
        assert present == sorted(release_module.ALL_SKILLS), platform


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
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\n补充说明\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="发布校验和已过期"):
        release_module.check_release(copied)


def test_new_reference_requires_a_new_release(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    (copied / "references" / "unreleased.md").write_text("# 未发布\n\n正文\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="source_files 与 Skill 唯一源文件不一致"):
        release_module.check_release(copied)


def test_skill_body_references_resolve_to_shipped_files():
    """正文里指向 Skill 自身文件的路径必须在发布包里（FB-38：改名后引用未同步）。"""
    assert release_module.find_broken_references(SKILL_ROOT) == []
    shipped = _manifest()["source_files"]
    for name in release_module.ALL_SKILLS:
        assert f"{name}/SKILL.md" in shipped, name
    for script in SHIPPED_SCRIPTS:
        assert script in shipped, script
    for retired in release_module.RETIRED_SKILL_DIRS:
        assert not any(item.startswith(f"agenticapp-creator/{retired}/") for item in shipped), retired


@pytest.mark.parametrize(
    ("relative", "line", "reported"),
    [
        ("agenticapp-creator/SKILL.md", "见 `references/不存在的参考.md`。", "agenticapp-creator/SKILL.md:"),
        (
            "agenticapp-creator/references/平台对象与用词.md",
            "详见 [G9](../flow/G9-不存在.md#出口)。",
            "agenticapp-creator/references/平台对象与用词.md:",
        ),
        (
            "agenticapp-tool-deploy/SKILL.md",
            "见 [不存在](references/不存在.md)。",
            "agenticapp-tool-deploy/SKILL.md:",
        ),
        (
            "agenticapp-tool-deploy/SKILL.md",
            "见 [入口参考](../agenticapp-creator/references/不存在.md)。",
            "agenticapp-tool-deploy/SKILL.md:",
        ),
        (
            "agenticapp-stage-1-requirements/references/谁来做.md",
            "见 `../../agenticapp-creator/references/不存在.md`。",
            "agenticapp-stage-1-requirements/references/谁来做.md:",
        ),
    ],
)
def test_broken_body_reference_is_rejected(tmp_path: Path, relative: str, line: str, reported: str):
    copied = _copy_repo(tmp_path)
    target = copied.parent / relative
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
        "claude-code/skills/agenticapp-creator/SKILL.md",
        "codex/skills/agenticapp-creator/SKILL.md",
        "codex/skills/agenticapp-tool-deploy/SKILL.md",
        "claude-code/skills/agenticapp-stage-1-requirements/references/谁来做.md",
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
        copy = release_module._platform_skill_dir(copied, platform) / "agenticapp-creator" / "SKILL.md"
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
    target = tmp_path / "codex/skills/agenticapp-creator/SKILL.md"
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
    assert "origin main" in script, "未提示推送 Codeup"
    # GitHub 只放流水线追加的发布快照，不能提示把带开发历史的 main 直接推过去（FB-1544）
    assert "push --follow-tags github main" not in script, "不应提示直接推 GitHub main"
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


# ---------------------------------------------------------------- 框架骨架 [任务:T-3724]


TOOL_SKILLS = tuple(name for name in release_module.ATOMIC_SKILLS if name.startswith("agenticapp-tool-"))
STAGE_HEADING_CASES = [
    (name, heading)
    for name in release_module.STAGE_SKILLS
    for heading in (
        release_module.LAST_STAGE_REQUIRED_HEADINGS
        if name == release_module.STAGE_SKILLS[-1]
        else release_module.STAGE_REQUIRED_HEADINGS
    )
]


def _atomic_skill_file(skill_root: Path, name: str) -> Path:
    return skill_root.parent / name / "SKILL.md"


def _rewrite_frontmatter(path: Path, mutate) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    closing = lines.index("---\n", 1)
    frontmatter = yaml.safe_load("".join(lines[1:closing]))
    mutate(frontmatter)
    dumped = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False, width=10**6)
    path.write_text("---\n" + dumped + "".join(lines[closing:]), encoding="utf-8")


def _rename_heading(path: Path, heading: str, new_heading: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    hits = [
        index
        for index, line in enumerate(lines)
        if (match := release_module._SECTION_HEADING_RE.match(line.rstrip("\n"))) and match.group(1) == heading
    ]
    assert len(hits) == 1, (path, heading, hits)
    lines[hits[0]] = f"## {new_heading}\n"
    path.write_text("".join(lines), encoding="utf-8")


def _layout_error(skill_root: Path, message: str) -> str:
    with pytest.raises(release_module.ReleaseError, match=message) as error:
        release_module.validate_skill_layout(skill_root)
    return str(error.value)


def test_current_skill_layout_passes():
    release_module.validate_skill_layout(SKILL_ROOT)
    present = sorted(path.name for path in SKILLS_ROOT.iterdir() if path.is_dir())
    assert present == sorted(release_module.ALL_SKILLS)
    assert len(release_module.ALL_SKILLS) == 20
    assert release_module.ATOMIC_SKILLS[:5] == release_module.STAGE_SKILLS
    assert not (SKILL_ROOT / "skills").exists()


def test_layout_constants_are_not_relaxed():
    """行数预算、description 上限和必备小节是框架约定，放宽要先改这里。"""
    assert release_module.LINE_BUDGETS == {"SKILL.md": 150, "references": 200}
    assert release_module.ATOMIC_SKILL_DESCRIPTION_MAX == 200
    assert release_module.STAGE_REQUIRED_HEADINGS == ("开始前确认", "按这个顺序做", "交棒")
    assert release_module.LAST_STAGE_REQUIRED_HEADINGS == ("开始前确认", "按这个顺序做", "结束")
    assert release_module.TOOL_REQUIRED_HEADINGS == ("常见错误",)


def test_missing_atomic_skill_is_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    shutil.rmtree(copied.parent / "agenticapp-ref-experience")

    error = _layout_error(copied, "平级 Skill 必须正好是")
    assert "缺少 ['agenticapp-ref-experience']" in error


def test_unexpected_atomic_skill_is_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    extra = _atomic_skill_file(copied, "business-extra")
    extra.parent.mkdir()
    extra.write_text("---\nname: business-extra\ndescription: 多出来的 Skill。\n---\n# 多出来\n", encoding="utf-8")

    error = _layout_error(copied, "平级 Skill 必须正好是")
    assert "多出 ['business-extra']" in error


def test_skill_nested_in_entry_is_rejected(tmp_path: Path):
    """Skill 不能再嵌套进入口目录：宿主只按插件 skills/ 下的一级目录发现 Skill。"""
    copied = _copy_repo(tmp_path)
    nested = copied / "skills" / "agenticapp-tool-deploy" / "SKILL.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("---\nname: agenticapp-tool-deploy\ndescription: 嵌套。\n---\n# 嵌套\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 文件"):
        release_module.discover_source_files(copied)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda fm: fm.update(name="agenticapp-task-diagnosis"), "name 必须与目录名"),
        (lambda fm: fm.update(keywords=["诊断"]), "frontmatter 必须且只能包含 name 和 description"),
        (lambda fm: fm.update(description=""), "description 不能为空"),
        (lambda fm: fm.update(description="诊" * 201), "201 字符，超过 200"),
        (lambda fm: fm.update(description="诊断应用时用。[skill-version:v20261103-abcdef]"), "不能带 skill-version 标记"),
    ],
    ids=["name-mismatch", "extra-field", "empty-description", "long-description", "version-marker"],
)
def test_atomic_skill_frontmatter_drift_is_rejected(tmp_path: Path, mutate, message: str):
    copied = _copy_repo(tmp_path)
    _rewrite_frontmatter(_atomic_skill_file(copied, "agenticapp-task-diagnose"), mutate)

    error = _layout_error(copied, message)
    assert "agenticapp-task-diagnose/SKILL.md" in error


def test_atomic_skill_description_at_limit_passes(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    limit = release_module.ATOMIC_SKILL_DESCRIPTION_MAX
    _rewrite_frontmatter(
        _atomic_skill_file(copied, "agenticapp-task-diagnose"), lambda fm: fm.update(description="诊" * limit)
    )

    release_module.validate_skill_layout(copied)


@pytest.mark.parametrize(("name", "heading"), STAGE_HEADING_CASES)
def test_stage_skill_missing_required_heading_is_rejected(tmp_path: Path, name: str, heading: str):
    copied = _copy_repo(tmp_path)
    _rename_heading(_atomic_skill_file(copied, name), heading, "补充说明")

    error = _layout_error(copied, "二级标题必须按顺序包含")
    assert f"{name}/SKILL.md" in error


def test_stage_skill_headings_out_of_order_are_rejected(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = _atomic_skill_file(copied, "agenticapp-stage-2-plan")
    _rename_heading(target, "开始前确认", "临时")
    _rename_heading(target, "按这个顺序做", "开始前确认")
    _rename_heading(target, "临时", "按这个顺序做")

    _layout_error(copied, "二级标题必须按顺序包含")


def test_last_stage_must_end_instead_of_handing_over(tmp_path: Path):
    """⑤ 是最后一段，没有下一段可交：最后一节写「结束」，写成「交棒」也拒绝。"""
    copied = _copy_repo(tmp_path)
    _rename_heading(_atomic_skill_file(copied, release_module.STAGE_SKILLS[-1]), "结束", "交棒")

    error = _layout_error(copied, "二级标题必须按顺序包含")
    assert "'结束'" in error


def test_code_block_headings_do_not_count_as_sections(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = _atomic_skill_file(copied, "agenticapp-stage-1-requirements")
    _rename_heading(target, "交棒", "补充说明")
    target.write_text(target.read_text(encoding="utf-8") + "\n```text\n## 交棒\n```\n", encoding="utf-8")

    _layout_error(copied, "二级标题必须按顺序包含")


@pytest.mark.parametrize("name", TOOL_SKILLS)
def test_tool_skill_requires_common_mistakes(tmp_path: Path, name: str):
    copied = _copy_repo(tmp_path)
    _rename_heading(_atomic_skill_file(copied, name), "常见错误", "补充说明")

    error = _layout_error(copied, "二级标题必须按顺序包含")
    assert f"{name}/SKILL.md" in error


@pytest.mark.parametrize(
    "relative",
    [
        "agenticapp-tool-deploy/notes.txt",
        "agenticapp-tool-deploy/scripts/run.sh",
        "agenticapp-tool-deploy/assets/logo.png",
        "agenticapp-tool-deploy/examples/extra.md",
        "agenticapp-tool-deploy/references/deep/extra.md",
        "agenticapp-tool-deploy/agents/openai.yaml",
        "agenticapp-creator/references/extra.html",
        "agenticapp-creator/scripts/helper.py",
        "notes.md",
    ],
)
def test_unsupported_skill_files_are_rejected(tmp_path: Path, relative: str):
    copied = _copy_repo(tmp_path)
    target = copied.parent / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unsupported\n", encoding="utf-8")

    for action in (
        lambda: release_module.discover_source_files(copied),
        lambda: release_module.release(copied, _package_version(copied), "不支持的文件"),
    ):
        with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 文件") as error:
            action()
        assert relative in str(error.value)


@pytest.mark.parametrize("relative", SHIPPED_SCRIPTS)
def test_scripts_are_shipped_to_plugin_copies(tmp_path: Path, relative: str):
    skill_root = _copy_repo(tmp_path)
    for platform in ("codex", "claude-code"):
        shutil.rmtree(tmp_path / platform / "skills")
    release_module.sync_platform_skills(skill_root)
    source = skill_root.parent / relative
    for platform in ("codex", "claude-code"):
        target = tmp_path / platform / "skills" / relative
        assert target.read_bytes() == source.read_bytes(), platform


@pytest.mark.parametrize(
    ("relative", "budget"),
    [
        ("agenticapp-creator/SKILL.md", "SKILL.md"),
        ("agenticapp-tool-deploy/SKILL.md", "SKILL.md"),
        ("agenticapp-creator/references/提问与交接.md", "references"),
        ("agenticapp-tool-deploy/references/报错.md", "references"),
    ],
)
def test_line_budget_overflow_is_rejected(tmp_path: Path, relative: str, budget: str):
    copied = _copy_repo(tmp_path)
    target = copied.parent / relative
    text = target.read_text(encoding="utf-8")
    limit = release_module.LINE_BUDGETS[budget]
    padding = limit - len(text.splitlines())
    assert padding >= 0, f"{relative} 已超过预算"
    target.write_text(text + "\n" * padding, encoding="utf-8")
    release_module.validate_skill_layout(copied)

    target.write_text(text + "\n" * (padding + 1), encoding="utf-8")
    for action in (
        lambda: release_module.check_release(copied),
        lambda: release_module.release(copied, _package_version(copied), "骨架校验"),
    ):
        with pytest.raises(release_module.ReleaseError, match="行预算") as error:
            action()
        assert f"{relative} 有 {limit + 1} 行" in str(error.value)


def test_assets_are_not_line_budgeted(tmp_path: Path):
    copied = _copy_repo(tmp_path)
    target = copied.parent / "agenticapp-stage-1-requirements/assets/PRD.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n" * 300, encoding="utf-8")

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
    install_roots = ("skills", "claude-code", "codex", "docs", "README.md")
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


@pytest.mark.parametrize("retired", ["business-app-creator-lite", "business-app-creator"])
def test_retired_skill_copies_are_removed_and_rejected(tmp_path: Path, retired: str):
    """lite 已并入主 Skill [任务:T-3724]，入口已从 business-app-creator 改名为 agenticapp-creator：
    同步时删掉平台里的旧目录，残留即拒绝发布。"""
    copied = _copy_repo(tmp_path)
    for platform in release_module.EXTRA_SKILL_PLATFORMS:
        assert not (tmp_path / platform / "skills" / retired).exists(), platform
    stale = tmp_path / "codex/skills" / retired
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("stale\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="已退役的附加 Skill"):
        release_module.check_release(copied)
    release_module.sync_platform_skills(copied)
    assert not stale.exists()
    release_module.check_release(copied)


@pytest.mark.parametrize("retired", ["flow", "stages", "reference", "scripts"])
def test_retired_structure_directories_are_rejected_in_platform_copies(tmp_path: Path, retired: str):
    copied = _copy_repo(tmp_path)
    leftover = tmp_path / "claude-code/skills/agenticapp-creator" / retired
    leftover.mkdir()
    (leftover / "old.md").write_text("old\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="旧结构目录"):
        release_module.check_release(copied)
    release_module.sync_platform_skills(copied)
    assert not leftover.exists()


@pytest.mark.parametrize(
    "legacy",
    [
        "claude-code/skills/agenticapp-creator/skills/agenticapp-tool-deploy/SKILL.md",
        "codex/skills/agenticapp-creator/skills/agenticapp-tool-deploy/SKILL.md",
        "codex/skills/agenticapp-old-name/SKILL.md",
    ],
)
def test_nested_layout_copies_are_rejected_and_removed(tmp_path: Path, legacy: str):
    """改成平级之前嵌套在入口里的 Skill、改名留下的目录残留即拒绝，同步时删掉。"""
    copied = _copy_repo(tmp_path)
    leftover = tmp_path / legacy
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_text("old\n", encoding="utf-8")
    with pytest.raises(release_module.ReleaseError, match="旧结构目录"):
        release_module.check_release(copied)
    release_module.sync_platform_skills(copied)
    assert not leftover.exists()
    release_module.check_release(copied)
