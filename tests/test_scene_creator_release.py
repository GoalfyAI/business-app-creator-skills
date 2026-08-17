import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path

import pytest
import tomllib
import yaml

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"
SCRIPT_PATH = SKILL_ROOT / "release" / "build_platform_packages.py"
PIPELINE_PATH = ROOT / ".yunxiao" / "scene-creator-skills.yml"
PROD_SCRIPT_PATH = ROOT / "scripts" / "prod-release-skill.py"

SPEC = importlib.util.spec_from_file_location("scene_creator_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
release_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_module)

PROD_SPEC = importlib.util.spec_from_file_location("prod_release_skill", PROD_SCRIPT_PATH)
assert PROD_SPEC and PROD_SPEC.loader
prod_release_module = importlib.util.module_from_spec(PROD_SPEC)
PROD_SPEC.loader.exec_module(prod_release_module)


def _copy_skill(tmp_path: Path) -> Path:
    copied = tmp_path / "scene-creator"
    shutil.copytree(SKILL_ROOT, copied)
    return copied


def _copy_repository_metadata(tmp_path: Path) -> None:
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    shutil.copy2(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    shutil.copy2(ROOT / "uv.lock", tmp_path / "uv.lock")


def _manifest(skill_root: Path = SKILL_ROOT) -> dict:
    return json.loads((skill_root / "release" / "skill-release.json").read_text(encoding="utf-8"))


def _package_version(skill_root: Path = SKILL_ROOT) -> str:
    return _manifest(skill_root)["package_version"]


def test_checked_in_scene_creator_release_is_current():
    manifest = release_module.check_release(SKILL_ROOT)

    assert manifest["skill_name"] == "scene-creator"
    assert release_module._validate_skill_version(manifest["version"]) == manifest["version"]
    assert release_module._validate_package_version(manifest["package_version"])


def test_skill_source_change_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    skill_file = copied / "SKILL.md"
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="发布校验和已过期"):
        release_module.check_release(copied)


def test_new_reference_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "references" / "unreleased.md").write_text("unreleased\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="source_files 与 Skill 唯一源文件不一致"):
        release_module.check_release(copied)


def test_platform_install_change_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    readme = copied / "release" / "platforms" / "codex" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="平台发布校验和已过期"):
        release_module.check_release(copied)


def test_release_updates_manifest_and_generates_direct_marketplaces(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    new_reference = copied / "references" / "new-rule.md"
    new_reference.write_text("# New rule\n", encoding="utf-8")
    fixed_version = _manifest()["package_version"]

    manifest = release_module.release(copied, fixed_version, "Add one tested rule")

    assert manifest["package_version"] == fixed_version
    assert "references/new-rule.md" in manifest["source_files"]
    assert "codex/AGENTS.md" in manifest["platform_source_files"]
    assert "claude-code/.mcp.json" in manifest["platform_source_files"]
    repository_root = copied.parent
    assert (repository_root / ".agents/plugins/marketplace.json").is_file()
    assert (repository_root / ".claude-plugin/marketplace.json").is_file()
    assert (repository_root / "codex/skills/scene-creator/SKILL.md").is_file()
    assert (repository_root / "claude-code/skills/scene-creator/SKILL.md").is_file()
    assert not (repository_root / "generic").exists()


def test_checked_in_direct_marketplaces_are_current():
    manifest = _manifest()

    release_module.check_direct_install_tree(SKILL_ROOT, manifest)

    repository_root = SKILL_ROOT.parent
    codex_marketplace = json.loads(
        (repository_root / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
    )
    claude_marketplace = json.loads(
        (repository_root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert codex_marketplace["plugins"][0]["source"] == "./codex"
    assert claude_marketplace["plugins"][0]["source"] == "./claude-code"
    assert codex_marketplace["plugins"][0]["version"] == manifest["package_version"]
    assert claude_marketplace["plugins"][0]["version"] == manifest["package_version"]
    # 对外文案只有一个源：顶层短描述取 agents/openai.yaml 的 short_description，
    # 插件长描述取 SKILL.md 的 description。这里校验注入结果与唯一源一致，不锁措辞。
    expected = release_module._skill_copy(SKILL_ROOT)
    for marketplace in (codex_marketplace, claude_marketplace):
        assert marketplace["description"] == expected["short_description"]
        assert marketplace["plugins"][0]["description"] == expected["description"]
        assert len(marketplace["plugins"][0]["description"]) >= 80


def test_non_prod_release_rejects_package_version_bump(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    bumped = release_module._next_patch(_package_version(copied))

    with pytest.raises(release_module.ReleaseError, match="只有 PROD"):
        release_module.release(copied, bumped, "不允许提前升级")


def test_non_prod_release_rejects_skill_version_change(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    with pytest.raises(release_module.ReleaseError, match="只有 PROD"):
        release_module.release(
            copied,
            _package_version(copied),
            "不允许提前切换 Skill 版本",
            skill_version="v20260813-a1b2c3",
        )


def test_prod_version_matches_goalfydata_date_and_random_hex_format():
    fixed = release_module.datetime(2026, 8, 12, 3, 4, tzinfo=release_module.timezone.utc)
    assert release_module.generate_prod_version(fixed, random_hex="a1b2c3") == "v20260812-a1b2c3"


def test_prod_version_rejects_invalid_random_hex():
    with pytest.raises(release_module.ReleaseError, match="6 位小写 hex"):
        release_module.generate_prod_version(random_hex="NOTHEX")


def test_prod_release_updates_repository_copies_without_building_packages(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))
    expected_package_version = release_module._next_patch(_package_version(copied))
    fixed = release_module.datetime(2026, 8, 13, 3, 4, tzinfo=release_module.timezone.utc)
    version = release_module.release_prod_source(
        copied,
        "PROD release",
        now=fixed,
        random_hex="a1b2c3",
    )

    assert version == "v20260813-a1b2c3"
    assert f"[skill-version:{version}]" in (copied / "SKILL.md").read_text()
    repository_root = copied.parent
    assert f"[skill-version:{version}]" in (
        repository_root / "codex/skills/scene-creator/SKILL.md"
    ).read_text()
    assert f"[skill-version:{version}]" in (
        repository_root / "claude-code/skills/scene-creator/SKILL.md"
    ).read_text()
    manifest = _manifest(copied)
    assert manifest["version"] == version
    assert manifest["package_version"] == expected_package_version
    assert manifest["mcp_endpoint"] == release_module.PROD_MCP_ENDPOINT
    release_module.assert_prod_runtime(copied)
    for path in (
        repository_root / ".agents/plugins/marketplace.json",
        repository_root / ".claude-plugin/marketplace.json",
        repository_root / "codex/.codex-plugin/plugin.json",
        repository_root / "claude-code/.claude-plugin/plugin.json",
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual_version = (
            payload["plugins"][0]["version"]
            if path.name == "marketplace.json"
            else payload["version"]
        )
        assert actual_version == expected_package_version
    pyproject = tomllib.loads((repository_root / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == expected_package_version
    lock_match = re.search(
        r'(?ms)^\[\[package\]\]\nname = "scene-creator-skills"\nversion = "([^"]+)"',
        (repository_root / "uv.lock").read_text(),
    )
    assert lock_match and lock_match.group(1) == expected_package_version
    assert not (repository_root / "dist").exists()


def test_prod_prepare_rewrites_every_install_surface_to_cn_prod(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))

    release_module.release_prod_source(copied, "PROD release", random_hex="a1b2c3")

    checked_paths = release_module._prod_runtime_paths(copied)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_paths)
    assert release_module.PROD_MCP_ENDPOINT in combined
    assert release_module.QA_MCP_ENDPOINT not in combined
    assert "GoalfyMax QA" not in combined
    assert release_module.PROD_MCP_ENDPOINT in (
        tmp_path / "codex/.mcp.json"
    ).read_text(encoding="utf-8")
    assert release_module.PROD_MCP_ENDPOINT in (
        tmp_path / "claude-code/.mcp.json"
    ).read_text(encoding="utf-8")


def test_prod_runtime_probe_requires_auth_layer(monkeypatch, tmp_path: Path):
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))
    release_module.release_prod_source(copied, "PROD release", random_hex="a1b2c3")

    def reject_without_auth(*_args, **_kwargs):
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
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))
    release_module.release_prod_source(copied, "PROD release", random_hex="a1b2c3")

    def missing_route(*_args, **_kwargs):
        raise prod_release_module.urllib.error.HTTPError(
            release_module.PROD_MCP_ENDPOINT,
            404,
            "Not Found",
            {"X-Scene-Skill-Runtime": "unknown"},
            None,
        )

    monkeypatch.setattr(prod_release_module.urllib.request, "urlopen", missing_route)
    with pytest.raises(RuntimeError, match="not ready"):
        prod_release_module.verify_prod_runtime(tmp_path)


def test_prod_runtime_probe_rejects_qa_hub_binding(monkeypatch, tmp_path: Path):
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))
    release_module.release_prod_source(copied, "PROD release", random_hex="a1b2c3")

    def qa_binding(*_args, **_kwargs):
        raise prod_release_module.urllib.error.HTTPError(
            release_module.PROD_MCP_ENDPOINT,
            401,
            "Unauthorized",
            {"X-Scene-Skill-Runtime": "qa"},
            None,
        )

    monkeypatch.setattr(prod_release_module.urllib.request, "urlopen", qa_binding)
    with pytest.raises(RuntimeError, match="not connected"):
        prod_release_module.verify_prod_runtime(tmp_path)


def test_direct_marketplace_drift_is_rejected(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    manifest = _manifest(copied)
    release_module.sync_direct_install_tree(copied, manifest)
    generated_skill = tmp_path / "codex/skills/scene-creator/SKILL.md"
    generated_skill.write_text("edited generated copy\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="直接安装的插件市场文件已过期"):
        release_module.check_release(copied)


def test_direct_marketplaces_share_the_canonical_skill():
    repository_root = SKILL_ROOT.parent
    canonical = (SKILL_ROOT / "SKILL.md").read_bytes()

    assert (repository_root / "codex/skills/scene-creator/SKILL.md").read_bytes() == canonical
    assert (repository_root / "claude-code/skills/scene-creator/SKILL.md").read_bytes() == canonical
    assert (repository_root / "codex/skills/scene-creator/agents/openai.yaml").is_file()
    assert not (repository_root / "claude-code/skills/scene-creator/agents").exists()


def test_checked_in_first_party_package_versions_are_synchronized():
    repository_root = SKILL_ROOT.parent
    expected = _package_version()
    for path in (
        repository_root / ".agents/plugins/marketplace.json",
        repository_root / ".claude-plugin/marketplace.json",
        repository_root / "codex/.codex-plugin/plugin.json",
        repository_root / "claude-code/.claude-plugin/plugin.json",
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual = (
            payload["plugins"][0]["version"]
            if path.name == "marketplace.json"
            else payload["version"]
        )
        assert actual == expected, path
    pyproject = tomllib.loads((repository_root / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == expected
    assert release_module._repository_package_version(SKILL_ROOT) == expected


def test_docs_do_not_pin_a_stale_first_party_package_version():
    readme = (SKILL_ROOT.parent / "README.md").read_text(encoding="utf-8")
    assert "--version 1.0.0" not in readme
    assert "Git SHA 前 6 位" not in readme
    assert "CI_COMMIT_SHA" not in readme


def test_release_rejects_invalid_skill_frontmatter(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "SKILL.md").write_text("# Missing frontmatter\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="frontmatter"):
        release_module.release(copied, _package_version(copied), "Invalid metadata")


def test_release_rejects_missing_skill_keywords(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    skill_file = copied / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    _, frontmatter_text, body = content.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    frontmatter.pop("keywords")
    skill_file.write_text(
        f"---\n{yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)}---{body}",
        encoding="utf-8",
    )

    with pytest.raises(release_module.ReleaseError, match="keywords"):
        release_module.release(copied, _package_version(copied), "Missing keywords")


def test_release_rejects_missing_skill_version_marker(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    skill_file = copied / "SKILL.md"
    content, count = release_module.SKILL_VERSION_RE.subn(
        "", skill_file.read_text(encoding="utf-8"), count=1
    )
    assert count == 1
    skill_file.write_text(content, encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="skill-version"):
        release_module.release(copied, _package_version(copied), "Missing version marker")


def test_missing_marker_contract_still_runs_after_prod_prepare(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    _copy_repository_metadata(tmp_path)
    release_module.sync_direct_install_tree(copied, _manifest(copied))
    release_module.release_prod_source(copied, "PROD release", random_hex="a1b2c3")

    skill_file = copied / "SKILL.md"
    content, count = release_module.SKILL_VERSION_RE.subn(
        "", skill_file.read_text(encoding="utf-8"), count=1
    )
    assert count == 1
    skill_file.write_text(content, encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="skill-version"):
        release_module.release(copied, _package_version(copied), "Missing marker")


def test_prod_pipeline_preserves_release_notes_for_hub_registration():
    pipeline = PIPELINE_PATH.read_text(encoding="utf-8")

    assert 'echo "SCENE_SKILL_RELEASE_NOTES=${CI_COMMIT_TITLE}" >> $FLOW_ENV' in pipeline
    assert (
        "git add README.md scene-creator codex claude-code .agents .claude-plugin pyproject.toml uv.lock"
        in pipeline
    )
    register_step = pipeline.split("step_register:", 1)[1]
    assert 'SCENE_SKILL_RELEASE_NOTES="${SCENE_SKILL_RELEASE_NOTES}"' in register_step
    assert "--verify-runtime-only" in pipeline.split("step_release:", 1)[1]


def test_release_rejects_invalid_openai_metadata(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    metadata = copied / "agents" / "openai.yaml"
    metadata.write_text(
        "interface:\n"
        '  display_name: "Workflow"\n'
        '  short_description: "This description is long enough for validation"\n'
        '  default_prompt: "Missing the required skill invocation."\n',
        encoding="utf-8",
    )

    with pytest.raises(release_module.ReleaseError, match="default_prompt"):
        release_module.release(copied, _package_version(copied), "Invalid metadata")


def test_release_rejects_missing_openai_mcp_dependency(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    metadata = copied / "agents" / "openai.yaml"
    metadata.write_text(
        "interface:\n"
        '  display_name: "场景包制作"\n'
        '  short_description: "理解资产模型，创建、诊断、优化并验证 GoalfyMax 场景包及业务界面"\n'
        '  default_prompt: "使用 $scene-creator 创建场景包。"\n'
        "policy:\n"
        "  allow_implicit_invocation: true\n",
        encoding="utf-8",
    )

    with pytest.raises(release_module.ReleaseError, match="MCP 依赖"):
        release_module.release(copied, _package_version(copied), "Invalid dependency")


def test_release_rejects_hidden_or_unsupported_source_files(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "references" / ".env").write_text("SECRET=value\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 隐藏文件"):
        release_module.release(copied, _package_version(copied), "Unsafe source")


def test_release_rejects_unlisted_skill_resource_directories(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    scripts = copied / "scripts"
    scripts.mkdir()
    (scripts / "unlisted.py").write_text("print('not packaged')\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="不支持的 Skill 文件"):
        release_module.release(copied, _package_version(copied), "Unlisted resource")


def test_platform_packages_share_one_source_and_exclude_release_files(tmp_path: Path):
    output_dir = tmp_path / "dist"
    version = _package_version()
    outputs = release_module.build_packages(SKILL_ROOT, output_dir)
    archives = {path.name: path for path in outputs}

    assert set(archives) == {
        f"scene-creator-codex-{version}.zip",
        f"scene-creator-claude-code-{version}.zip",
        f"scene-creator-generic-{version}.zip",
    }

    contents = {}
    for name, path in archives.items():
        with zipfile.ZipFile(path) as archive:
            assert all("/release/" not in member for member in archive.namelist())
            contents[name] = {member: archive.read(member) for member in archive.namelist()}

    codex = contents[f"scene-creator-codex-{version}.zip"]
    claude = contents[f"scene-creator-claude-code-{version}.zip"]
    generic = contents[f"scene-creator-generic-{version}.zip"]
    codex_plugin = "scene-creator-codex/plugins/scene-creator"
    claude_plugin = "scene-creator-claude-code/plugins/scene-creator"
    assert f"{codex_plugin}/skills/scene-creator/agents/openai.yaml" in codex
    assert f"{claude_plugin}/skills/scene-creator/agents/openai.yaml" not in claude
    assert "scene-creator/agents/openai.yaml" not in generic
    assert "scene-creator-codex/.agents/plugins/marketplace.json" in codex
    assert "scene-creator-claude-code/.claude-plugin/marketplace.json" in claude
    assert f"{codex_plugin}/.codex-plugin/plugin.json" in codex
    assert f"{claude_plugin}/.claude-plugin/plugin.json" in claude
    assert f"{codex_plugin}/.mcp.json" in codex
    assert f"{claude_plugin}/.mcp.json" in claude

    common_files = [
        path
        for path in _manifest()["source_files"]
        if path == "SKILL.md" or path.startswith("references/")
    ]
    for relative_path in common_files:
        generic_member = f"scene-creator/{relative_path}"
        assert (
            codex[f"{codex_plugin}/skills/scene-creator/{relative_path}"] == generic[generic_member]
        )
        assert (
            claude[f"{claude_plugin}/skills/scene-creator/{relative_path}"]
            == generic[generic_member]
        )

    manifest = _manifest()
    assert set(generic) == {
        f"scene-creator/{relative_path}"
        for relative_path in manifest["source_files"]
        if relative_path == "SKILL.md" or relative_path.startswith("references/")
    }

    codex_manifest = json.loads(codex[f"{codex_plugin}/.codex-plugin/plugin.json"])
    claude_manifest = json.loads(claude[f"{claude_plugin}/.claude-plugin/plugin.json"])
    assert codex_manifest["version"] == version
    assert claude_manifest["version"] == version
    # 对外文案只有一个源：SKILL.md 的 description（剥掉版本标记）。
    # 这里校验注入结果与唯一源一致，而不是锁定具体措辞。
    expected = release_module._skill_copy(SKILL_ROOT)
    for plugin_manifest in (codex_manifest, claude_manifest):
        assert len(plugin_manifest["description"]) >= 150
        assert plugin_manifest["description"] == expected["description"]


def test_platform_mcp_templates_use_env_key_and_live_external_contract():
    for platform in ("codex", "claude-code"):
        platform_root = SKILL_ROOT / "release" / "platforms" / platform
        mcp_text = (platform_root / ".mcp.json").read_text(encoding="utf-8")
        docs = "\n".join(
            (platform_root / name).read_text(encoding="utf-8")
            for name in ("README.md", "AGENTS.md", "UPDATE.md")
        )

        assert _manifest()["mcp_endpoint"] in mcp_text
        assert "SCENE_CREATOR_API_KEY" in mcp_text
        assert set(json.loads(mcp_text)["mcpServers"]) == {"scene-creator"}
        # 工具清单以实时加载的工具定义为准，不锁静态数量
        assert "不要用静态工具数量代替实时清单" in docs
        assert "bubble" in docs
        assert "list_assets" in docs
        assert "/developer/api-keys" in docs
        assert "sk_" in docs
        assert "Authorization: Bearer" in docs
        assert "X-User-ID" in docs
        assert "sk_" not in mcp_text


def test_platform_package_build_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    release_module.build_packages(SKILL_ROOT, first)
    release_module.build_packages(SKILL_ROOT, second)

    assert {path.name: path.read_bytes() for path in sorted(first.iterdir())} == {
        path.name: path.read_bytes() for path in sorted(second.iterdir())
    }
