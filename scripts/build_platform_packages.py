#!/usr/bin/env python3
"""校验并发布 scene-creator Skill。

模型很简单：`skill/` 是唯一源，发布时把它复制到各平台的 `skills/scene-creator/`，
再给所有 SKILL.md 副本打上同一个版本标记。平台安装文档（README/AGENTS/UPDATE/.mcp.json）
和插件 manifest 都是手工维护的最终文件，不做模板渲染。

发布清单 `skill-release.json` 记录版本与校验和，用来发现"改了内容但没发布"。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SKILL_NAME = "scene-creator"
SKILL_CONTENT_DIR = "skill"
MANIFEST_RELATIVE_PATH = Path("skill-release.json")
OPENAI_METADATA_RELATIVE_PATH = Path("agents/openai.yaml")
PLATFORM_NAMES = ("codex", "claude-code")
# 仓库里的安装物料始终是生产配置。开发者要连测试环境时，改本地已安装插件的
# .mcp.json，不动仓库源文件——那会让发布校验和失配。
PROD_MCP_ENDPOINT = "https://workflow-mcp.goalfyai.cn/mcp"
DATA_SKILL_VERSION_RE = re.compile(r"^v\d{8}-[0-9a-f]{6}$")
LEGACY_SKILL_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
SKILL_VERSION_RE = re.compile(r"\[skill-version:(v(?:\d+\.\d+\.\d+|\d{8}-[0-9a-f]{6}))\]")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PACKAGE_VERSION_RE = re.compile(r'("version":\s*")(\d+)\.(\d+)\.(\d+)(")')
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
# 每次发布都要同步提升的插件 manifest：Claude 与 Codex 靠 plugin.json 的版本
# 判断有无新版，漏掉任何一个都会让已安装用户收不到更新。
PACKAGE_MANIFESTS = (
    Path("claude-code/.claude-plugin/plugin.json"),
    Path("codex/.codex-plugin/plugin.json"),
    Path(".claude-plugin/marketplace.json"),
    Path(".agents/plugins/marketplace.json"),
)
# 平台安装目录：Skill 内容复制到 skills/ 下，其余文件手工维护
PLATFORM_DOC_FILES = ("README.md", "AGENTS.md", "UPDATE.md")
MANIFEST_KEYS = {
    "skill_name",
    "version",
    "package_version",
    "mcp_endpoint",
    "released_at",
    "update_reason",
    "source_files",
    "checksums",
}


class ReleaseError(ValueError):
    """仓库中的 Skill 发布信息无效或已过期。"""


def _skill_root() -> Path:
    """Skill 内容目录：只放要发给用户的 SKILL.md / agents / references。"""
    return Path(__file__).resolve().parents[1] / SKILL_CONTENT_DIR


def _repository_root(skill_root: Path) -> Path:
    return skill_root.resolve().parent


def _manifest_path(skill_root: Path) -> Path:
    return _repository_root(skill_root) / MANIFEST_RELATIVE_PATH


def _relative(path: Path, skill_root: Path) -> str:
    return path.relative_to(skill_root).as_posix()


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
    if endpoint != PROD_MCP_ENDPOINT:
        raise ReleaseError("agents/openai.yaml 必须使用生产 MCP 地址")
    return endpoint


def validate_skill_metadata(skill_root: Path) -> None:
    """校验 SKILL.md frontmatter 与 Codex 元数据。"""
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

    metadata = _load_yaml_mapping(
        (skill_root / OPENAI_METADATA_RELATIVE_PATH).read_text(encoding="utf-8"),
        "agents/openai.yaml",
    )
    interface = metadata.get("interface")
    if not isinstance(interface, dict):
        raise ReleaseError("agents/openai.yaml 必须包含 interface 配置")
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ReleaseError(f"agents/openai.yaml 的 interface.{field} 不能为空")
    if not 25 <= len(interface["short_description"]) <= 64:
        raise ReleaseError("agents/openai.yaml 的 short_description 必须包含 25～64 个字符")
    _configured_mcp_endpoint(skill_root)


def validate_platform_install_files(skill_root: Path) -> None:
    """校验各平台安装文件的安全契约与必备事实。"""
    repository_root = _repository_root(skill_root)
    for platform in PLATFORM_NAMES:
        platform_root = repository_root / platform
        mcp_path = platform_root / ".mcp.json"
        if not mcp_path.is_file():
            raise ReleaseError(f"缺少 {platform} 的 MCP 配置：{mcp_path}")
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        server = (mcp.get("mcpServers") or {}).get(SKILL_NAME) or {}
        if server.get("url") != PROD_MCP_ENDPOINT:
            raise ReleaseError(f"{platform} MCP 必须使用生产地址")
        serialized = json.dumps(server, ensure_ascii=False)
        if "SCENE_CREATOR_API_KEY" not in serialized:
            raise ReleaseError(f"{platform} MCP 必须引用 API Key 环境变量")
        if re.search(r"Bearer\s+sk_[A-Za-z0-9]", serialized):
            raise ReleaseError(f"{platform} MCP 不得包含明文 API Key")

        docs = "\n".join(
            (platform_root / name).read_text(encoding="utf-8") for name in PLATFORM_DOC_FILES
        )
        # 只校验安装文档必须交代清楚的事实，不锁具体措辞：
        # 密钥从哪来、怎么发送、装完怎么验证、从哪装。
        for required_text in (
            "/developer/api-keys",
            "Authorization: Bearer",
            "SCENE_CREATOR_API_KEY",
            "list_assets",
            "GoalfyAI/scene-creator-skills",
        ):
            if required_text not in docs:
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
    manifest_path = _manifest_path(skill_root)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"缺少发布清单：{manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"发布清单不是有效的 JSON：{exc}") from exc
    if not isinstance(manifest, dict):
        raise ReleaseError("发布清单必须是 JSON 对象")
    return manifest


def _validate_package_version(version: Any) -> tuple[int, int, int]:
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ReleaseError("package version 必须是 MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _validate_skill_version(version: Any) -> str:
    if not isinstance(version, str) or not (
        DATA_SKILL_VERSION_RE.fullmatch(version) or LEGACY_SKILL_VERSION_RE.fullmatch(version)
    ):
        raise ReleaseError("Skill version 必须是 vYYYYMMDD-6位小写hex 或 vMAJOR.MINOR.PATCH")
    return version


def _next_patch(version: str) -> str:
    major, minor, patch = _validate_package_version(version)
    return f"{major}.{minor}.{patch + 1}"


def _current_skill_version(skill_root: Path) -> str:
    content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    markers = SKILL_VERSION_RE.findall(content)
    if len(markers) != 1:
        raise ReleaseError("SKILL.md 必须且只能包含一个 skill-version 标记")
    return markers[0]


def _repository_package_version(skill_root: Path) -> str:
    """读取仓库中各插件 manifest 的 package version，要求完全一致。"""
    repository_root = _repository_root(skill_root)
    versions = {}
    for relative in PACKAGE_MANIFESTS:
        path = repository_root / relative
        if not path.is_file():
            raise ReleaseError(f"缺少插件 manifest：{path}")
        found = PACKAGE_VERSION_RE.search(path.read_text(encoding="utf-8"))
        if not found:
            raise ReleaseError(f"{relative} 缺少 version 字段")
        versions[relative.as_posix()] = f"{found.group(2)}.{found.group(3)}.{found.group(4)}"
    unique = set(versions.values())
    if len(unique) != 1:
        raise ReleaseError(f"插件 manifest 版本不一致：{versions}")
    return unique.pop()


def _bump_package_version(skill_root: Path, version: str) -> None:
    """把所有插件 manifest 与 Python 包版本统一写成同一个值。"""
    _validate_package_version(version)
    repository_root = _repository_root(skill_root)
    for relative in PACKAGE_MANIFESTS:
        path = repository_root / relative
        content = path.read_text(encoding="utf-8")
        updated, count = PACKAGE_VERSION_RE.subn(
            lambda match, new=version: f"{match.group(1)}{new}{match.group(5)}", content, count=1
        )
        if count != 1:
            raise ReleaseError(f"{relative} 的 version 字段替换失败")
        path.write_text(updated, encoding="utf-8")

    pyproject = repository_root / "pyproject.toml"
    if pyproject.is_file():
        content = pyproject.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(?m)^version = "\d+\.\d+\.\d+"$', f'version = "{version}"', content, count=1
        )
        if count == 1:
            pyproject.write_text(updated, encoding="utf-8")
    lockfile = repository_root / "uv.lock"
    if lockfile.is_file():
        content = lockfile.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(?ms)(name = "scene-creator-skills"\nversion = ")\d+\.\d+\.\d+(")',
            lambda match, new=version: f"{match.group(1)}{new}{match.group(2)}",
            content,
            count=1,
        )
        if count == 1:
            lockfile.write_text(updated, encoding="utf-8")


def _validate_released_at(value: Any) -> None:
    if not isinstance(value, str):
        raise ReleaseError("released_at 必须是 ISO-8601 字符串")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ReleaseError("released_at 必须形如 2026-01-01T00:00:00Z") from exc


def _platform_skill_dir(skill_root: Path, platform: str) -> Path:
    return _repository_root(skill_root) / platform / "skills" / SKILL_NAME


def sync_platform_skills(skill_root: Path) -> None:
    """把 Skill 内容复制到各平台安装目录。

    Codex 需要 agents/openai.yaml，Claude Code 不需要，其余文件两边一致。
    复制而非渲染：各平台拿到的 Skill 内容必须逐字节相同。
    """
    files = discover_source_files(skill_root)
    for platform in PLATFORM_NAMES:
        target_root = _platform_skill_dir(skill_root, platform)
        if target_root.exists():
            shutil.rmtree(target_root)
        for path in files:
            relative = Path(_relative(path, skill_root))
            if platform == "claude-code" and relative == OPENAI_METADATA_RELATIVE_PATH:
                continue
            destination = target_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def check_platform_skills(skill_root: Path) -> None:
    """校验各平台的 Skill 副本与唯一源逐字节一致。"""
    files = discover_source_files(skill_root)
    for platform in PLATFORM_NAMES:
        target_root = _platform_skill_dir(skill_root, platform)
        expected = {}
        for path in files:
            relative = Path(_relative(path, skill_root))
            if platform == "claude-code" and relative == OPENAI_METADATA_RELATIVE_PATH:
                continue
            expected[relative.as_posix()] = _sha256(path)
        actual = {
            path.relative_to(target_root).as_posix(): _sha256(path)
            for path in sorted(target_root.rglob("*"))
            if path.is_file()
        }
        if expected != actual:
            stale = sorted(set(expected) ^ set(actual)) or sorted(
                name for name, digest in expected.items() if actual.get(name) != digest
            )
            raise ReleaseError(f"{platform} 的 Skill 副本已过期，请执行 release：{stale}")


def check_release(skill_root: Path) -> dict[str, Any]:
    """校验发布清单、Skill 内容校验和与各平台副本。"""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_install_files(skill_root)
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
    if _repository_package_version(skill_root) != package_version:
        raise ReleaseError("插件 manifest 版本必须等于 skill-release.json.package_version")
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

    check_platform_skills(skill_root)
    return manifest


def release(
    skill_root: Path,
    package_version: str,
    reason: str,
    *,
    skill_version: str | None = None,
    allow_package_bump: bool = False,
) -> dict[str, Any]:
    """写入新的发布清单并同步各平台副本，不执行 Git 操作。"""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_install_files(skill_root)
    _validate_package_version(package_version)
    skill_version = _validate_skill_version(skill_version or _current_skill_version(skill_root))
    reason = reason.strip()
    if not reason or len(reason) > 1024:
        raise ReleaseError("update_reason 必须包含 1～1024 个字符")

    manifest_path = _manifest_path(skill_root)
    if manifest_path.exists():
        current = _load_manifest(skill_root)
        current_package_version = current.get("package_version")
        _validate_package_version(current_package_version)
        if skill_version != current.get("version") and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以更新 Skill version")
        if package_version != current_package_version and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以提升 package version")
        if allow_package_bump and package_version != _next_patch(current_package_version):
            raise ReleaseError("PROD 发布必须把所有插件 package version 统一提升一个 patch")
        if allow_package_bump and not DATA_SKILL_VERSION_RE.fullmatch(skill_version):
            raise ReleaseError("PROD Skill version 必须使用 vYYYYMMDD-6位小写hex")

    _bump_package_version(skill_root, package_version)
    sync_platform_skills(skill_root)

    files = discover_source_files(skill_root)
    manifest = {
        "skill_name": SKILL_NAME,
        "version": skill_version,
        "package_version": package_version,
        "mcp_endpoint": _configured_mcp_endpoint(skill_root),
        "released_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "update_reason": reason,
        "source_files": [_relative(path, skill_root) for path in files],
        "checksums": _checksums(skill_root, files),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def generate_prod_version(
    now: datetime | None = None, *, random_hex: str | None = None
) -> str:
    """生成 UTC 日期加 3 随机字节的生产版本。"""
    instant = now or datetime.now(timezone.utc)
    suffix = random_hex or secrets.token_hex(3)
    if not re.fullmatch(r"[0-9a-f]{6}", suffix):
        raise ReleaseError("生产发布随机后缀必须是 6 位小写 hex")
    return f"v{instant.astimezone(timezone.utc):%Y%m%d}-{suffix}"


def release_prod_source(
    skill_root: Path,
    reason: str,
    *,
    now: datetime | None = None,
    random_hex: str | None = None,
) -> str:
    """切一个新的随机 Skill 版本，并统一提升所有插件 package version。"""
    skill_root = skill_root.resolve()
    manifest = check_release(skill_root)
    version = generate_prod_version(now, random_hex=random_hex)
    package_version = _next_patch(manifest["package_version"])
    skill_file = skill_root / "SKILL.md"
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
    except Exception:
        skill_file.write_text(original, encoding="utf-8")
        raise
    return version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("check", help="校验仓库中的发布清单与各平台副本")
    subparsers.add_parser("sync", help="按当前发布版本重新同步各平台 Skill 副本")

    release_parser = subparsers.add_parser("release", help="写入新的发布清单")
    release_parser.add_argument("--version", required=True, help="package version")
    release_parser.add_argument("--reason", required=True, help="变更说明")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    skill_root = _skill_root()
    try:
        if args.action == "check":
            manifest = check_release(skill_root)
            print(f"{SKILL_NAME} 发布版本 {manifest['version']} 已是最新状态")
        elif args.action == "sync":
            manifest = _load_manifest(skill_root)
            sync_platform_skills(skill_root)
            check_release(skill_root)
            print(f"{SKILL_NAME} 平台副本已按 {manifest['version']} 同步")
        else:
            manifest = release(skill_root, args.version, args.reason)
            print(f"已发布 {SKILL_NAME} {manifest['version']}")
    except ReleaseError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
