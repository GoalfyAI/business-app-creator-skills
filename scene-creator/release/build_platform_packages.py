#!/usr/bin/env python3
"""校验、发布并打包 scene-creator Skill。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import sys
import zipfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SKILL_NAME = "scene-creator"
MANIFEST_RELATIVE_PATH = Path("release/skill-release.json")
OPENAI_METADATA_RELATIVE_PATH = Path("agents/openai.yaml")
PLATFORM_SOURCE_RELATIVE_PATH = Path("release/platforms")
PLATFORM_VERSION_TOKEN = "__SCENE_CREATOR_VERSION__"
PLATFORM_NAMES = ("codex", "claude-code")
QA_MCP_ENDPOINT = "https://workflow-mcp.qa.goalfyai.com/mcp"
PROD_MCP_ENDPOINT = "https://workflow-mcp.goalfyai.cn/mcp"
ALLOWED_MCP_ENDPOINTS = {QA_MCP_ENDPOINT, PROD_MCP_ENDPOINT}
DATA_SKILL_VERSION_RE = re.compile(r"^v\d{8}-[0-9a-f]{6}$")
LEGACY_SKILL_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
SKILL_VERSION_RE = re.compile(
    r"\[skill-version:(v(?:\d+\.\d+\.\d+|\d{8}-[0-9a-f]{6}))\]"
)
REQUIRED_SKILL_KEYWORDS = {
    "scene package",
    "scenario package",
    "场景包",
    "workflow",
    "business UI",
    "业务界面",
    "GoalfyMax",
    "MCP",
    "business archive",
    "业务档案",
    "personalized routes",
    "个性化选路",
}
DIRECT_MARKETPLACE_PATHS = {
    "codex": Path(".agents/plugins/marketplace.json"),
    "claude-code": Path(".claude-plugin/marketplace.json"),
}
PLATFORM_FILES = {
    "codex/.codex-plugin/plugin.json",
    "codex/.mcp.json",
    "codex/AGENTS.md",
    "codex/README.md",
    "codex/UPDATE.md",
    "claude-code/.claude-plugin/plugin.json",
    "claude-code/.mcp.json",
    "claude-code/AGENTS.md",
    "claude-code/README.md",
    "claude-code/UPDATE.md",
}
MANIFEST_KEYS = {
    "skill_name",
    "version",
    "package_version",
    "mcp_endpoint",
    "released_at",
    "update_reason",
    "source_files",
    "checksums",
    "platform_source_files",
    "platform_checksums",
}
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MARKETPLACE_DESCRIPTION = (
    "面向编码 Agent 的 GoalfyMax 场景包制作与验证能力。通过经过审计的 scene-creator 外部 MCP，"
    "把业务流程转成可直接运行的单 Workflow 或多 Workflow 场景包，并维护从线上资产复用、工具契约"
    "取样、依赖与辅助文件准备、输入输出 Schema、场景编排、预览、bubble 验证、业务界面制作与部署、"
    "可选全真项目验证、日志与交付物检查到最终发布的完整制作链路。"
)


class ReleaseError(ValueError):
    """仓库中的 Skill 发布信息无效或已过期。"""


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_path(skill_root: Path) -> Path:
    return skill_root / MANIFEST_RELATIVE_PATH


def _relative(path: Path, skill_root: Path) -> str:
    return path.relative_to(skill_root).as_posix()


def _platform_source_root(skill_root: Path) -> Path:
    return skill_root / PLATFORM_SOURCE_RELATIVE_PATH


def _repository_root(skill_root: Path) -> Path:
    return skill_root.resolve().parent


def _prod_runtime_paths(skill_root: Path) -> list[Path]:
    repository_readme = _repository_root(skill_root) / "README.md"
    if not repository_readme.is_file():
        raise ReleaseError(f"缺少仓库安装说明：{repository_readme}")
    return [
        *discover_source_files(skill_root),
        *discover_platform_source_files(skill_root),
        repository_readme,
    ]


def discover_platform_source_files(skill_root: Path) -> list[Path]:
    """返回经过审查的平台安装文件和插件模板。"""
    platform_root = _platform_source_root(skill_root.resolve())
    if not platform_root.is_dir():
        raise ReleaseError(f"缺少平台源文件目录：{platform_root}")

    files = []
    for path in platform_root.rglob("*"):
        if path.is_symlink():
            raise ReleaseError(f"平台发布文件不允许使用符号链接：{path}")
        if path.is_file():
            files.append(path)
    relative_files = {path.relative_to(platform_root).as_posix() for path in files}
    if relative_files != PLATFORM_FILES:
        missing = sorted(PLATFORM_FILES - relative_files)
        extra = sorted(relative_files - PLATFORM_FILES)
        raise ReleaseError(f"平台源文件不一致：缺少={missing}，多出={extra}")
    return sorted(files, key=lambda path: path.relative_to(platform_root).as_posix())


def discover_source_files(skill_root: Path) -> list[Path]:
    """返回作为 Skill 内容发布的唯一源文件集合。"""
    skill_root = skill_root.resolve()
    entrypoint = skill_root / "SKILL.md"
    if not entrypoint.is_file():
        raise ReleaseError(f"缺少 Skill 入口文件：{entrypoint}")

    openai_metadata = skill_root / OPENAI_METADATA_RELATIVE_PATH
    if not openai_metadata.is_file():
        raise ReleaseError(f"缺少 Codex 元数据：{openai_metadata}")

    references = skill_root / "references"
    if not references.is_dir():
        raise ReleaseError(f"缺少 Skill 目录：{references}")

    files = []
    for path in skill_root.rglob("*"):
        relative_path = path.relative_to(skill_root)
        if relative_path.parts[0] == "release":
            continue
        if path.is_symlink():
            raise ReleaseError(f"Skill 发布文件不允许使用符号链接：{path}")
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in relative_path.parts):
            raise ReleaseError(f"不支持的 Skill 隐藏文件：{relative_path.as_posix()}")
        if relative_path == Path("SKILL.md") or relative_path == OPENAI_METADATA_RELATIVE_PATH:
            files.append(path)
            continue
        if relative_path.parts[0] == "references" and path.suffix.lower() == ".md":
            files.append(path)
            continue
        raise ReleaseError(f"不支持的 Skill 文件：{relative_path.as_posix()}")

    return sorted(files, key=lambda path: _relative(path, skill_root))


def _load_yaml_mapping(content: str, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ReleaseError(f"{label} 不是有效的 YAML：{exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"{label} 必须是 YAML 对象")
    return data


def _configured_mcp_endpoint(skill_root: Path) -> str:
    metadata = _load_yaml_mapping(
        (skill_root / OPENAI_METADATA_RELATIVE_PATH).read_text(encoding="utf-8"),
        "agents/openai.yaml",
    )
    dependencies = metadata.get("dependencies")
    tools = dependencies.get("tools") if isinstance(dependencies, dict) else None
    if not isinstance(tools, list) or len(tools) != 1 or not isinstance(tools[0], dict):
        raise ReleaseError("agents/openai.yaml 必须声明唯一的 scene-creator MCP 依赖")
    endpoint = tools[0].get("url")
    if endpoint not in ALLOWED_MCP_ENDPOINTS:
        raise ReleaseError("agents/openai.yaml 必须使用经过审查的 QA 或国内生产 MCP 地址")
    return endpoint


def validate_skill_metadata(skill_root: Path) -> None:
    """在发布或构建前校验必需的 Skill 与 Codex 元数据。"""
    skill_root = skill_root.resolve()
    skill_file = skill_root / "SKILL.md"
    try:
        content = skill_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReleaseError(f"缺少 Skill 入口文件：{skill_file}") from exc
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ReleaseError("SKILL.md 必须以 YAML frontmatter 开头")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise ReleaseError("SKILL.md frontmatter 未闭合") from exc
    frontmatter = _load_yaml_mapping("\n".join(lines[1:closing_index]), "SKILL.md frontmatter")
    if set(frontmatter) != {"name", "description", "keywords"}:
        raise ReleaseError("SKILL.md frontmatter 必须且只能包含 name、description 和 keywords")
    if frontmatter["name"] != SKILL_NAME:
        raise ReleaseError(f"SKILL.md 的 name 必须是 {SKILL_NAME!r}")
    description = frontmatter["description"]
    if not isinstance(description, str) or not description.strip():
        raise ReleaseError("SKILL.md 的 description 不能为空")
    markers = SKILL_VERSION_RE.findall(description)
    if len(markers) != 1:
        raise ReleaseError("SKILL.md 的 description 必须且只能包含一个有效 skill-version 标记")
    keywords = frontmatter["keywords"]
    if not isinstance(keywords, list) or not keywords:
        raise ReleaseError("SKILL.md 的 keywords 必须是非空列表")
    if any(not isinstance(keyword, str) or not keyword.strip() for keyword in keywords):
        raise ReleaseError("SKILL.md 的 keywords 只能包含非空字符串")
    if len(keywords) != len(set(keywords)):
        raise ReleaseError("SKILL.md 的 keywords 不允许重复")
    missing_keywords = sorted(REQUIRED_SKILL_KEYWORDS - set(keywords))
    if missing_keywords:
        raise ReleaseError(f"SKILL.md 缺少核心 keywords：{missing_keywords}")
    if not "\n".join(lines[closing_index + 1 :]).strip():
        raise ReleaseError("SKILL.md 正文不能为空")

    metadata_path = skill_root / OPENAI_METADATA_RELATIVE_PATH
    try:
        metadata = _load_yaml_mapping(
            metadata_path.read_text(encoding="utf-8"), "agents/openai.yaml"
        )
    except FileNotFoundError as exc:
        raise ReleaseError(f"缺少 Codex 元数据：{metadata_path}") from exc
    interface = metadata.get("interface")
    if not isinstance(interface, dict):
        raise ReleaseError("agents/openai.yaml 的 interface 必须是 YAML 对象")
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ReleaseError(f"agents/openai.yaml 的 interface.{field} 不能为空")
    if not 25 <= len(interface["short_description"]) <= 64:
        raise ReleaseError("agents/openai.yaml 的 short_description 必须包含 25～64 个字符")
    if f"${SKILL_NAME}" not in interface["default_prompt"]:
        raise ReleaseError(f"agents/openai.yaml 的 default_prompt 必须包含 ${SKILL_NAME}")

    policy = metadata.get("policy")
    if not isinstance(policy, dict) or policy.get("allow_implicit_invocation") is not True:
        raise ReleaseError("agents/openai.yaml 必须启用 policy.allow_implicit_invocation")

    dependencies = metadata.get("dependencies")
    tools = dependencies.get("tools") if isinstance(dependencies, dict) else None
    if not isinstance(tools, list) or len(tools) != 1:
        raise ReleaseError("agents/openai.yaml 必须声明唯一的 scene-creator MCP 依赖")
    dependency = tools[0]
    expected_dependency = {
        "type": "mcp",
        "value": "scene-creator",
        "transport": "streamable_http",
        "url": _configured_mcp_endpoint(skill_root),
        "bearer_token_env_var": "SCENE_CREATOR_API_KEY",
    }
    if dependency != expected_dependency:
        raise ReleaseError("agents/openai.yaml 的 scene-creator MCP 依赖配置不正确")


def validate_platform_sources(skill_root: Path) -> None:
    """校验插件模板和共用的远程 MCP 安全契约。"""
    platform_root = _platform_source_root(skill_root.resolve())
    expected_endpoint = _configured_mcp_endpoint(skill_root)
    discover_platform_source_files(skill_root)
    for platform in PLATFORM_NAMES:
        source_root = platform_root / platform
        manifest_relative = (
            Path(".codex-plugin/plugin.json")
            if platform == "codex"
            else Path(".claude-plugin/plugin.json")
        )
        manifest = json.loads(
            (source_root / manifest_relative)
            .read_text(encoding="utf-8")
            .replace(PLATFORM_VERSION_TOKEN, "0.0.0")
        )
        if manifest.get("name") != SKILL_NAME:
            raise ReleaseError(f"{platform} 插件名称必须是 {SKILL_NAME!r}")
        if manifest.get("version") != "0.0.0":
            raise ReleaseError(f"{platform} 插件版本必须使用发布占位符")
        if manifest.get("skills") != "./skills/":
            raise ReleaseError(f"{platform} 插件必须加载 ./skills/")
        if manifest.get("mcpServers") != "./.mcp.json":
            raise ReleaseError(f"{platform} 插件必须加载 ./.mcp.json")

        mcp = json.loads((source_root / ".mcp.json").read_text(encoding="utf-8"))
        server = (mcp.get("mcpServers") or {}).get("scene-creator") or {}
        if server.get("url") != expected_endpoint:
            raise ReleaseError(f"{platform} MCP 必须使用经过审查的环境地址")
        serialized = json.dumps(server, ensure_ascii=False)
        if "SCENE_CREATOR_API_KEY" not in serialized:
            raise ReleaseError(f"{platform} MCP 必须引用 API Key 环境变量")
        if re.search(r"Bearer\s+sk_[A-Za-z0-9]", serialized):
            raise ReleaseError(f"{platform} MCP 不得包含明文 API Key")

        combined_docs = "\n".join(
            (source_root / name).read_text(encoding="utf-8")
            for name in ("README.md", "AGENTS.md", "UPDATE.md")
        )
        for required_text in (
            "tools/list",
            "bubble",
            "list_assets",
            "/developer/api-keys",
            "sk_",
            "Authorization: Bearer",
        ):
            if required_text not in combined_docs:
                raise ReleaseError(f"{platform} 安装文档必须提到 {required_text!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksums(skill_root: Path, files: Iterable[Path]) -> dict[str, str]:
    return {_relative(path, skill_root): _sha256(path) for path in files}


def _load_manifest(skill_root: Path) -> dict[str, Any]:
    path = _manifest_path(skill_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"缺少发布清单：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"发布清单不是有效的 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError("发布清单必须是 JSON 对象")
    return data


def _validate_package_version(version: Any) -> tuple[int, int, int]:
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ReleaseError("版本号必须使用 MAJOR.MINOR.PATCH 格式")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _validate_skill_version(version: Any) -> str:
    if not isinstance(version, str) or not (
        DATA_SKILL_VERSION_RE.fullmatch(version) or LEGACY_SKILL_VERSION_RE.fullmatch(version)
    ):
        raise ReleaseError("Skill 版本必须使用 vYYYYMMDD-6位小写hex；仅兼容初始 vMAJOR.MINOR.PATCH")
    return version


def _next_patch(version: str) -> str:
    major, minor, patch = _validate_package_version(version)
    return f"{major}.{minor}.{patch + 1}"


def _current_skill_version(skill_root: Path) -> str:
    content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    markers = SKILL_VERSION_RE.findall(content)
    if len(markers) != 1:
        raise ReleaseError("SKILL.md 必须且只能包含一个有效 skill-version 标记")
    return _validate_skill_version(markers[0])


def _repository_package_version(skill_root: Path) -> str | None:
    repository_root = _repository_root(skill_root)
    pyproject = repository_root / "pyproject.toml"
    lockfile = repository_root / "uv.lock"
    if not pyproject.exists() and not lockfile.exists():
        return None
    if not pyproject.is_file() or not lockfile.is_file():
        raise ReleaseError("仓库 package version 要求 pyproject.toml 与 uv.lock 同时存在")

    project_match = re.search(
        r"(?ms)^\[project\]\n.*?^version = \"([^\"]+)\"",
        pyproject.read_text(encoding="utf-8"),
    )
    lock_match = re.search(
        rf'(?ms)^\[\[package\]\]\nname = "{re.escape("scene-creator-skills")}"\nversion = "([^"]+)"',
        lockfile.read_text(encoding="utf-8"),
    )
    if not project_match or not lock_match:
        raise ReleaseError("无法读取仓库自身的 package version")
    project_version = project_match.group(1)
    lock_version = lock_match.group(1)
    _validate_package_version(project_version)
    _validate_package_version(lock_version)
    if project_version != lock_version:
        raise ReleaseError("pyproject.toml 与 uv.lock 的仓库 package version 不一致")
    return project_version


def _sync_repository_package_version(skill_root: Path, version: str) -> None:
    repository_root = _repository_root(skill_root)
    pyproject = repository_root / "pyproject.toml"
    lockfile = repository_root / "uv.lock"
    if not pyproject.exists() and not lockfile.exists():
        return
    if not pyproject.is_file() or not lockfile.is_file():
        raise ReleaseError("仓库 package version 要求 pyproject.toml 与 uv.lock 同时存在")
    _validate_package_version(version)

    pyproject_text, project_count = re.subn(
        r'(?ms)^(\[project\]\n.*?^version = ")[^"]+("$)',
        rf"\g<1>{version}\g<2>",
        pyproject.read_text(encoding="utf-8"),
        count=1,
    )
    lock_text, lock_count = re.subn(
        rf'(?ms)^(\[\[package\]\]\nname = "{re.escape("scene-creator-skills")}"\nversion = ")[^"]+("$)',
        rf"\g<1>{version}\g<2>",
        lockfile.read_text(encoding="utf-8"),
        count=1,
    )
    if project_count != 1 or lock_count != 1:
        raise ReleaseError("仓库 package version 必须且只能各更新一次")
    pyproject.write_text(pyproject_text, encoding="utf-8")
    lockfile.write_text(lock_text, encoding="utf-8")


def _validate_released_at(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ReleaseError("released_at 必须是非空的 ISO-8601 时间戳")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseError("released_at 必须是有效的 ISO-8601 时间戳") from exc
    if parsed.tzinfo is None:
        raise ReleaseError("released_at 必须包含时区")


def check_release(skill_root: Path, *, check_direct_install: bool = True) -> dict[str, Any]:
    """校验发布清单元数据和所有唯一源文件的校验和。"""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_sources(skill_root)
    manifest = _load_manifest(skill_root)
    if set(manifest) != MANIFEST_KEYS:
        missing = sorted(MANIFEST_KEYS - set(manifest))
        extra = sorted(set(manifest) - MANIFEST_KEYS)
        raise ReleaseError(f"发布清单字段不一致：缺少={missing}，多出={extra}")
    if manifest["skill_name"] != SKILL_NAME:
        raise ReleaseError(f"skill_name 必须是 {SKILL_NAME!r}")
    skill_version = _validate_skill_version(manifest["version"])
    package_version = manifest["package_version"]
    _validate_package_version(package_version)
    if manifest["mcp_endpoint"] != _configured_mcp_endpoint(skill_root):
        raise ReleaseError("skill-release.json.mcp_endpoint 与当前 Skill MCP 环境不一致")
    if _current_skill_version(skill_root) != skill_version:
        raise ReleaseError("SKILL.md 标记必须等于 skill-release.json.version")
    repository_package_version = _repository_package_version(skill_root)
    if repository_package_version is not None and repository_package_version != package_version:
        raise ReleaseError("仓库 package version 必须等于 skill-release.json.package_version")
    _validate_released_at(manifest["released_at"])

    reason = manifest["update_reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
        raise ReleaseError("update_reason 必须包含 1～1024 个字符")

    files = discover_source_files(skill_root)
    expected_files = [_relative(path, skill_root) for path in files]
    if manifest["source_files"] != expected_files:
        raise ReleaseError("source_files 与 Skill 唯一源文件不一致，请执行 release 操作")
    if not isinstance(manifest["checksums"], dict):
        raise ReleaseError("checksums 必须是 JSON 对象")
    actual_checksums = _checksums(skill_root, files)
    if manifest["checksums"] != actual_checksums:
        stale = sorted(
            path
            for path in set(manifest["checksums"]) | set(actual_checksums)
            if manifest["checksums"].get(path) != actual_checksums.get(path)
        )
        raise ReleaseError(f"发布校验和已过期：{stale}")

    platform_root = _platform_source_root(skill_root)
    platform_files = discover_platform_source_files(skill_root)
    expected_platform_files = [
        path.relative_to(platform_root).as_posix() for path in platform_files
    ]
    if manifest["platform_source_files"] != expected_platform_files:
        raise ReleaseError("platform_source_files 与经过审查的安装文件不一致，请执行 release 操作")
    actual_platform_checksums = {
        path.relative_to(platform_root).as_posix(): _sha256(path) for path in platform_files
    }
    if manifest["platform_checksums"] != actual_platform_checksums:
        stale = sorted(
            path
            for path in set(manifest["platform_checksums"]) | set(actual_platform_checksums)
            if manifest["platform_checksums"].get(path) != actual_platform_checksums.get(path)
        )
        raise ReleaseError(f"平台发布校验和已过期：{stale}")
    if check_direct_install:
        check_direct_install_tree(skill_root, manifest)
    return manifest


def release(
    skill_root: Path,
    package_version: str,
    reason: str,
    *,
    skill_version: str | None = None,
    allow_package_bump: bool = False,
) -> dict[str, Any]:
    """写入新的明确版本发布清单，不执行 Git 操作。"""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_sources(skill_root)
    _validate_package_version(package_version)
    skill_version = _validate_skill_version(skill_version or _current_skill_version(skill_root))
    reason = reason.strip()
    if not reason or len(reason) > 1024:
        raise ReleaseError("update_reason 必须包含 1～1024 个字符")

    manifest_path = _manifest_path(skill_root)
    if manifest_path.exists():
        current = _load_manifest(skill_root)
        current_package_version = current.get("package_version", current.get("version"))
        _validate_package_version(current_package_version)
        if skill_version != current.get("version") and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以更新 Skill version")
        if package_version != current_package_version and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以提升 package version")
        if allow_package_bump and package_version != _next_patch(current_package_version):
            raise ReleaseError("PROD 发布必须把所有插件 package version 统一提升一个 patch")
        if allow_package_bump and not DATA_SKILL_VERSION_RE.fullmatch(skill_version):
            raise ReleaseError("PROD Skill version 必须使用 vYYYYMMDD-6位小写hex")

    files = discover_source_files(skill_root)
    platform_root = _platform_source_root(skill_root)
    platform_files = discover_platform_source_files(skill_root)
    manifest = {
        "skill_name": SKILL_NAME,
        "version": skill_version,
        "package_version": package_version,
        "mcp_endpoint": _configured_mcp_endpoint(skill_root),
        "released_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "update_reason": reason,
        "source_files": [_relative(path, skill_root) for path in files],
        "checksums": _checksums(skill_root, files),
        "platform_source_files": [
            path.relative_to(platform_root).as_posix() for path in platform_files
        ],
        "platform_checksums": {
            path.relative_to(platform_root).as_posix(): _sha256(path) for path in platform_files
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(manifest_path)
    _sync_repository_package_version(skill_root, package_version)
    sync_direct_install_tree(skill_root, manifest)
    return check_release(skill_root)


def _write_member(archive: zipfile.ZipFile, archive_path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(archive_path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _write_zip(output_path: Path, skill_root: Path, source_files: Iterable[str]) -> None:
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative_path in source_files:
            data = (skill_root / relative_path).read_bytes()
            archive_path = f"{SKILL_NAME}/{relative_path}"
            _write_member(archive, archive_path, data)


def _bundle_marketplace(platform: str, version: str) -> tuple[str, bytes]:
    client_name = "Codex" if platform == "codex" else "Claude Code"
    plugin_description = (
        f"在 {client_name} 中创建、更新、验证并发布 GoalfyMax 场景包。支持线上资产复用、工具契约"
        "取样、依赖与辅助文件准备、单 Workflow 或多 Workflow 编排、输入输出 Schema 校验、预览、"
        "bubble、业务界面制作与部署、可选全真项目验证、日志诊断和交付物检查。"
    )
    if platform == "codex":
        path = ".agents/plugins/marketplace.json"
        body = {
            "name": "scene-creator",
            "description": MARKETPLACE_DESCRIPTION,
            "interface": {"displayName": "场景包制作"},
            "plugins": [
                {
                    "name": SKILL_NAME,
                    "description": plugin_description,
                    "version": version,
                    "author": {"name": "GoalfyAI"},
                    "source": {
                        "source": "local",
                        "path": f"./plugins/{SKILL_NAME}",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Developer Tools",
                }
            ],
        }
    else:
        path = ".claude-plugin/marketplace.json"
        body = {
            "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
            "name": "scene-creator",
            "description": MARKETPLACE_DESCRIPTION,
            "owner": {"name": "GoalfyAI"},
            "plugins": [
                {
                    "name": SKILL_NAME,
                    "description": plugin_description,
                    "version": version,
                    "author": {"name": "GoalfyAI"},
                    "source": f"./plugins/{SKILL_NAME}",
                    "category": "development",
                }
            ],
        }
    return path, (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode()


def _direct_marketplace(platform: str, version: str) -> bytes:
    client_name = "Codex" if platform == "codex" else "Claude Code"
    body: dict[str, Any] = {
        "name": "scene-creator",
        "description": MARKETPLACE_DESCRIPTION,
        "owner": {"name": "GoalfyAI"},
        "plugins": [
            {
                "name": SKILL_NAME,
                "description": (
                    f"在 {client_name} 中创建、更新、验证并发布 GoalfyMax 场景包。支持线上资产复用、"
                    "工具契约取样、依赖与辅助文件准备、单 Workflow 或多 Workflow 编排、输入输出 "
                    "Schema 校验、预览、bubble、业务界面制作与部署、可选全真项目验证、日志诊断和交付物检查。"
                ),
                "version": version,
                "author": {"name": "GoalfyAI"},
                "source": f"./{platform}",
            }
        ],
    }
    if platform == "claude-code":
        body["$schema"] = "https://anthropic.com/claude-code/marketplace.schema.json"
        body["plugins"][0]["category"] = "development"
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode()


def _direct_install_files(skill_root: Path, manifest: dict[str, Any]) -> dict[Path, bytes]:
    """根据唯一 Skill 源文件渲染需要提交到仓库的插件市场目录。"""
    version = manifest["package_version"]
    platform_root = _platform_source_root(skill_root)
    common_files = [
        path
        for path in manifest["source_files"]
        if path == "SKILL.md" or path.startswith("references/")
    ]
    rendered: dict[Path, bytes] = {}
    for platform in PLATFORM_NAMES:
        rendered[DIRECT_MARKETPLACE_PATHS[platform]] = _direct_marketplace(platform, version)
        for source_path in sorted((platform_root / platform).rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(platform_root / platform)
            rendered[Path(platform) / relative_path] = (
                source_path.read_text(encoding="utf-8")
                .replace(PLATFORM_VERSION_TOKEN, version)
                .encode()
            )
        source_files = list(manifest["source_files"]) if platform == "codex" else common_files
        for relative_path in source_files:
            rendered[Path(platform) / "skills" / SKILL_NAME / relative_path] = (
                skill_root / relative_path
            ).read_bytes()
    return rendered


def sync_direct_install_tree(
    skill_root: Path, manifest: dict[str, Any] | None = None
) -> list[Path]:
    """重新生成仓库中的插件市场文件；生成副本不得直接编辑。"""
    skill_root = skill_root.resolve()
    manifest = manifest or _load_manifest(skill_root)
    repository_root = _repository_root(skill_root)
    rendered = _direct_install_files(skill_root, manifest)

    for generated_directory in (
        repository_root / "codex",
        repository_root / "claude-code",
        repository_root / ".agents",
        repository_root / ".claude-plugin",
    ):
        if generated_directory.exists():
            shutil.rmtree(generated_directory)

    written = []
    for relative_path, data in sorted(rendered.items(), key=lambda item: str(item[0])):
        target = repository_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written


def check_direct_install_tree(skill_root: Path, manifest: dict[str, Any] | None = None) -> None:
    """拒绝生成目录中缺失、被修改或多出的文件。"""
    skill_root = skill_root.resolve()
    manifest = manifest or _load_manifest(skill_root)
    repository_root = _repository_root(skill_root)
    expected = _direct_install_files(skill_root, manifest)
    actual_paths: set[Path] = set()
    for generated_directory in (
        repository_root / "codex",
        repository_root / "claude-code",
        repository_root / ".agents",
        repository_root / ".claude-plugin",
    ):
        if not generated_directory.exists():
            continue
        actual_paths.update(
            path.relative_to(repository_root)
            for path in generated_directory.rglob("*")
            if path.is_file()
        )
    expected_paths = set(expected)
    if actual_paths != expected_paths:
        missing = sorted(str(path) for path in expected_paths - actual_paths)
        extra = sorted(str(path) for path in actual_paths - expected_paths)
        raise ReleaseError(f"直接安装的插件市场文件不一致：缺少={missing}，多出={extra}")
    stale = sorted(
        str(relative_path)
        for relative_path, data in expected.items()
        if (repository_root / relative_path).read_bytes() != data
    )
    if stale:
        raise ReleaseError(f"直接安装的插件市场文件已过期：{stale}")


def _write_platform_zip(
    output_path: Path,
    skill_root: Path,
    platform: str,
    version: str,
    skill_files: Iterable[str],
) -> None:
    bundle_root = f"{SKILL_NAME}-{platform}"
    plugin_root = f"{bundle_root}/plugins/{SKILL_NAME}"
    platform_root = _platform_source_root(skill_root) / platform
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        marketplace_path, marketplace_data = _bundle_marketplace(platform, version)
        _write_member(archive, f"{bundle_root}/{marketplace_path}", marketplace_data)
        for source_path in sorted(platform_root.rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(platform_root).as_posix()
            data = (
                source_path.read_text(encoding="utf-8")
                .replace(PLATFORM_VERSION_TOKEN, version)
                .encode()
            )
            _write_member(archive, f"{plugin_root}/{relative_path}", data)
            if relative_path in {"README.md", "AGENTS.md", "UPDATE.md"}:
                _write_member(archive, f"{bundle_root}/{relative_path}", data)
        for relative_path in skill_files:
            data = (skill_root / relative_path).read_bytes()
            _write_member(
                archive,
                f"{plugin_root}/skills/{SKILL_NAME}/{relative_path}",
                data,
            )


def build_packages(skill_root: Path, output_dir: Path) -> list[Path]:
    """只根据已校验的发布版本构建可复现安装包。"""
    skill_root = skill_root.resolve()
    manifest = check_release(skill_root)
    common_files = [
        path
        for path in manifest["source_files"]
        if path == "SKILL.md" or path.startswith("references/")
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for platform in PLATFORM_NAMES:
        output_path = output_dir / f"{SKILL_NAME}-{platform}-{manifest['package_version']}.zip"
        source_files = list(manifest["source_files"]) if platform == "codex" else common_files
        _write_platform_zip(
            output_path,
            skill_root,
            platform,
            manifest["package_version"],
            source_files,
        )
        outputs.append(output_path)
    generic_path = output_dir / f"{SKILL_NAME}-generic-{manifest['package_version']}.zip"
    _write_zip(generic_path, skill_root, common_files)
    outputs.append(generic_path)
    return outputs


def generate_prod_version(
    now: datetime | None = None, *, random_hex: str | None = None
) -> str:
    """按 GoalfyData 规则生成 UTC 日期加 3 随机字节的生产版本。"""
    instant = now or datetime.now(timezone.utc)
    suffix = random_hex or secrets.token_hex(3)
    if not re.fullmatch(r"[0-9a-f]{6}", suffix):
        raise ReleaseError("生产发布随机后缀必须是 6 位小写 hex")
    return f"v{instant.astimezone(timezone.utc):%Y%m%d}-{suffix}"


def render_prod_runtime(skill_root: Path) -> None:
    """把唯一源和平台模板切到国内生产；生成目录随后统一重建。"""
    skill_root = skill_root.resolve()
    replacements = {
        QA_MCP_ENDPOINT: PROD_MCP_ENDPOINT,
        "GoalfyMax QA 后端": "GoalfyMax 国内生产后端",
        "GoalfyMax QA 个人 API 密钥": "GoalfyMax 国内生产个人 API 密钥",
        "GoalfyMax QA 的": "GoalfyMax 国内生产环境（https://goalfymax.goalfyai.cn）的",
        "登录 GoalfyMax QA": "登录 GoalfyMax 国内生产环境（https://goalfymax.goalfyai.cn）",
        "当前连接美国 QA 环境": "当前连接国内生产环境",
        "在 GoalfyMax QA 中": "在 GoalfyMax 国内生产环境（https://goalfymax.goalfyai.cn）中",
        "完整的 QA 个人 API 密钥": "完整的国内生产个人 API 密钥",
        "QA 部署尚未提供": "国内生产部署尚未提供",
        "GoalfyMax QA": "GoalfyMax 国内生产环境（https://goalfymax.goalfyai.cn）",
    }
    paths = _prod_runtime_paths(skill_root)
    for path in paths:
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def assert_prod_runtime(skill_root: Path) -> None:
    """PROD 切版必须只包含国内生产 MCP 和生产密钥说明。"""
    skill_root = skill_root.resolve()
    if _configured_mcp_endpoint(skill_root) != PROD_MCP_ENDPOINT:
        raise ReleaseError("PROD Skill 未连接国内生产 MCP")
    paths = _prod_runtime_paths(skill_root)
    forbidden = (QA_MCP_ENDPOINT, "GoalfyMax QA", "QA 个人 API 密钥")
    stale: list[str] = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        if any(value in content for value in forbidden):
            stale.append(str(path.relative_to(skill_root)))
    if stale:
        raise ReleaseError(f"PROD Skill 仍包含 QA 安装配置：{sorted(stale)}")


def release_prod_source(
    skill_root: Path,
    reason: str,
    *,
    now: datetime | None = None,
    random_hex: str | None = None,
) -> str:
    """按 Data 规则更新 Skill 版本并统一提升所有一方 package version。"""
    skill_root = skill_root.resolve()
    manifest = check_release(skill_root)
    version = generate_prod_version(now, random_hex=random_hex)
    package_version = _next_patch(manifest["package_version"])
    skill_file = skill_root / "SKILL.md"
    rollback = {
        path: path.read_bytes()
        for path in _prod_runtime_paths(skill_root)
    }
    render_prod_runtime(skill_root)
    original = skill_file.read_text(encoding="utf-8")
    updated, count = SKILL_VERSION_RE.subn(f"[skill-version:{version}]", original, count=1)
    if count != 1:
        raise ReleaseError("SKILL.md 必须且只能更新一个 skill-version 标记")
    skill_file.write_text(updated, encoding="utf-8")
    try:
        release(
            skill_root,
            package_version,
            reason,
            skill_version=version,
            allow_package_bump=True,
        )
        assert_prod_runtime(skill_root)
    except Exception:
        for path, content in rollback.items():
            path.write_bytes(content)
        raise
    return version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("check", help="校验仓库中的发布清单")
    subparsers.add_parser("sync", help="根据已校验的发布版本重新生成直接安装的插件市场文件")

    release_parser = subparsers.add_parser("release", help="写入新的发布清单")
    release_parser.add_argument(
        "--version",
        required=True,
        help="仓库当前 package version；只有 PROD 发布可以提升 patch",
    )
    release_parser.add_argument("--reason", required=True, help="发布原因")

    build_parser = subparsers.add_parser("build", help="构建所有平台的 ZIP 安装包")
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录（默认：仓库 dist/）",
    )

    prod_parser = subparsers.add_parser(
        "prod-release", help="仅供 PROD 流水线更新仓库内版本标记；不生成安装包"
    )
    prod_parser.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    skill_root = _skill_root()
    try:
        if args.action == "check":
            manifest = check_release(skill_root)
            print(f"{SKILL_NAME} 发布版本 {manifest['version']} 已是最新状态")
        elif args.action == "sync":
            manifest = check_release(skill_root, check_direct_install=False)
            for path in sync_direct_install_tree(skill_root, manifest):
                print(path)
            check_release(skill_root)
        elif args.action == "release":
            manifest = release(skill_root, args.version, args.reason)
            print(f"已发布 {SKILL_NAME} {manifest['version']}")
        elif args.action == "build":
            output_dir = args.output_dir or skill_root.parent / "dist"
            for path in build_packages(skill_root, output_dir):
                print(path)
        elif args.action == "prod-release":
            version = release_prod_source(skill_root, args.reason)
            print(f"SCENE_SKILL_VERSION={version}")
        else:
            raise ReleaseError(f"不支持的动作：{args.action}")
    except ReleaseError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
