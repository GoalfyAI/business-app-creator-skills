import importlib.util
import json
import shutil
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "scene-creator"
SCRIPT_PATH = SKILL_ROOT / "release" / "build_platform_packages.py"

SPEC = importlib.util.spec_from_file_location("scene_creator_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
release_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_module)


def _copy_skill(tmp_path: Path) -> Path:
    copied = tmp_path / "scene-creator"
    shutil.copytree(SKILL_ROOT, copied)
    return copied


def _manifest(skill_root: Path = SKILL_ROOT) -> dict:
    return json.loads(
        (skill_root / "release" / "skill-release.json").read_text(encoding="utf-8")
    )


def _next_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def test_checked_in_scene_creator_release_is_current():
    manifest = release_module.check_release(SKILL_ROOT)

    assert manifest["skill_name"] == "scene-creator"
    assert release_module.SEMVER_RE.fullmatch(manifest["version"])


def test_skill_source_change_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    skill_file = copied / "SKILL.md"
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="checksums are stale"):
        release_module.check_release(copied)


def test_new_reference_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "references" / "unreleased.md").write_text("unreleased\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="source_files differ"):
        release_module.check_release(copied)


def test_platform_install_change_requires_a_new_release(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    readme = copied / "release" / "platforms" / "codex" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(
        release_module.ReleaseError, match="platform release checksums are stale"
    ):
        release_module.check_release(copied)


def test_release_updates_manifest_and_generates_direct_marketplaces(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    new_reference = copied / "references" / "new-rule.md"
    new_reference.write_text("# New rule\n", encoding="utf-8")
    next_version = _next_patch(_manifest(copied)["version"])

    manifest = release_module.release(copied, next_version, "Add one tested rule")

    assert manifest["version"] == next_version
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
        (repository_root / ".agents/plugins/marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    claude_marketplace = json.loads(
        (repository_root / ".claude-plugin/marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    assert codex_marketplace["plugins"][0]["source"] == "./codex"
    assert claude_marketplace["plugins"][0]["source"] == "./claude-code"
    assert codex_marketplace["plugins"][0]["version"] == manifest["version"]
    assert claude_marketplace["plugins"][0]["version"] == manifest["version"]


def test_direct_marketplace_drift_is_rejected(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    manifest = _manifest(copied)
    release_module.sync_direct_install_tree(copied, manifest)
    generated_skill = tmp_path / "codex/skills/scene-creator/SKILL.md"
    generated_skill.write_text("edited generated copy\n", encoding="utf-8")

    with pytest.raises(
        release_module.ReleaseError, match="direct marketplace files are stale"
    ):
        release_module.check_release(copied)


def test_direct_marketplaces_share_the_canonical_skill():
    repository_root = SKILL_ROOT.parent
    canonical = (SKILL_ROOT / "SKILL.md").read_bytes()

    assert (
        repository_root / "codex/skills/scene-creator/SKILL.md"
    ).read_bytes() == canonical
    assert (
        repository_root / "claude-code/skills/scene-creator/SKILL.md"
    ).read_bytes() == canonical
    assert (
        repository_root / "codex/skills/scene-creator/agents/openai.yaml"
    ).is_file()
    assert not (
        repository_root / "claude-code/skills/scene-creator/agents"
    ).exists()


def test_release_rejects_invalid_skill_frontmatter(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "SKILL.md").write_text("# Missing frontmatter\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="frontmatter"):
        release_module.release(
            copied, _next_patch(_manifest(copied)["version"]), "Invalid metadata"
        )


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
        release_module.release(
            copied, _next_patch(_manifest(copied)["version"]), "Invalid metadata"
        )


def test_release_rejects_hidden_or_unsupported_source_files(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    (copied / "references" / ".env").write_text("SECRET=value\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="unsupported hidden Skill file"):
        release_module.release(
            copied, _next_patch(_manifest(copied)["version"]), "Unsafe source"
        )


def test_release_rejects_unlisted_skill_resource_directories(tmp_path: Path):
    copied = _copy_skill(tmp_path)
    scripts = copied / "scripts"
    scripts.mkdir()
    (scripts / "unlisted.py").write_text("print('not packaged')\n", encoding="utf-8")

    with pytest.raises(release_module.ReleaseError, match="unsupported Skill file"):
        release_module.release(
            copied, _next_patch(_manifest(copied)["version"]), "Unlisted resource"
        )


def test_platform_packages_share_one_source_and_exclude_release_files(tmp_path: Path):
    output_dir = tmp_path / "dist"
    version = _manifest()["version"]
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
            codex[f"{codex_plugin}/skills/scene-creator/{relative_path}"]
            == generic[generic_member]
        )
        assert (
            claude[f"{claude_plugin}/skills/scene-creator/{relative_path}"]
            == generic[generic_member]
        )

    manifest = _manifest()
    assert set(generic) == {
        f"scene-creator/{relative_path}" for relative_path in manifest["source_files"]
        if relative_path == "SKILL.md" or relative_path.startswith("references/")
    }

    codex_manifest = json.loads(
        codex[f"{codex_plugin}/.codex-plugin/plugin.json"]
    )
    claude_manifest = json.loads(
        claude[f"{claude_plugin}/.claude-plugin/plugin.json"]
    )
    assert codex_manifest["version"] == version
    assert claude_manifest["version"] == version


def test_platform_mcp_templates_use_env_key_and_live_external_contract():
    for platform in ("codex", "claude-code"):
        platform_root = SKILL_ROOT / "release" / "platforms" / platform
        mcp_text = (platform_root / ".mcp.json").read_text(encoding="utf-8")
        docs = "\n".join(
            (platform_root / name).read_text(encoding="utf-8")
            for name in ("README.md", "AGENTS.md", "UPDATE.md")
        )

        assert "https://workflow-mcp.qa.goalfyai.com/mcp" in mcp_text
        assert "SCENE_CREATOR_API_KEY" in mcp_text
        assert set(json.loads(mcp_text)["mcpServers"]) == {"scene-creator"}
        assert "12" in docs
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

    assert {
        path.name: path.read_bytes() for path in sorted(first.iterdir())
    } == {
        path.name: path.read_bytes() for path in sorted(second.iterdir())
    }
