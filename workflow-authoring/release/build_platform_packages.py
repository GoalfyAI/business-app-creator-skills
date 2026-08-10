#!/usr/bin/env python3
"""Check, release, and package the workflow-authoring Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SKILL_NAME = "workflow-authoring"
MANIFEST_RELATIVE_PATH = Path("release/skill-release.json")
OPENAI_METADATA_RELATIVE_PATH = Path("agents/openai.yaml")
PLATFORM_SOURCE_RELATIVE_PATH = Path("release/platforms")
PLATFORM_VERSION_TOKEN = "__WORKFLOW_AUTHORING_VERSION__"
PLATFORM_NAMES = ("codex", "claude-code")
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
    "released_at",
    "update_reason",
    "source_files",
    "checksums",
    "platform_source_files",
    "platform_checksums",
}
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class ReleaseError(ValueError):
    """Raised when the checked-in Skill release is invalid or stale."""


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


def discover_platform_source_files(skill_root: Path) -> list[Path]:
    """Return the reviewed platform install and plugin templates."""
    platform_root = _platform_source_root(skill_root.resolve())
    if not platform_root.is_dir():
        raise ReleaseError(f"missing platform source directory: {platform_root}")

    files = []
    for path in platform_root.rglob("*"):
        if path.is_symlink():
            raise ReleaseError(f"platform release does not allow symlinks: {path}")
        if path.is_file():
            files.append(path)
    relative_files = {path.relative_to(platform_root).as_posix() for path in files}
    if relative_files != PLATFORM_FILES:
        missing = sorted(PLATFORM_FILES - relative_files)
        extra = sorted(relative_files - PLATFORM_FILES)
        raise ReleaseError(
            f"platform source files differ: missing={missing}, extra={extra}"
        )
    return sorted(files, key=lambda path: path.relative_to(platform_root).as_posix())


def discover_source_files(skill_root: Path) -> list[Path]:
    """Return the one canonical set of files shipped as Skill content."""
    skill_root = skill_root.resolve()
    entrypoint = skill_root / "SKILL.md"
    if not entrypoint.is_file():
        raise ReleaseError(f"missing Skill entrypoint: {entrypoint}")

    openai_metadata = skill_root / OPENAI_METADATA_RELATIVE_PATH
    if not openai_metadata.is_file():
        raise ReleaseError(f"missing Codex metadata: {openai_metadata}")

    references = skill_root / "references"
    if not references.is_dir():
        raise ReleaseError(f"missing Skill directory: {references}")

    files = []
    for path in skill_root.rglob("*"):
        relative_path = path.relative_to(skill_root)
        if relative_path.parts[0] == "release":
            continue
        if path.is_symlink():
            raise ReleaseError(f"Skill release does not allow symlinks: {path}")
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in relative_path.parts):
            raise ReleaseError(f"unsupported hidden Skill file: {relative_path.as_posix()}")
        if relative_path == Path("SKILL.md") or relative_path == OPENAI_METADATA_RELATIVE_PATH:
            files.append(path)
            continue
        if relative_path.parts[0] == "references" and path.suffix.lower() == ".md":
            files.append(path)
            continue
        raise ReleaseError(f"unsupported Skill file: {relative_path.as_posix()}")

    return sorted(files, key=lambda path: _relative(path, skill_root))


def _load_yaml_mapping(content: str, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ReleaseError(f"invalid {label} YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"{label} must be a YAML object")
    return data


def validate_skill_metadata(skill_root: Path) -> None:
    """Validate the required Skill and Codex metadata before release or build."""
    skill_root = skill_root.resolve()
    skill_file = skill_root / "SKILL.md"
    try:
        content = skill_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReleaseError(f"missing Skill entrypoint: {skill_file}") from exc
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ReleaseError("SKILL.md must start with YAML frontmatter")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise ReleaseError("SKILL.md frontmatter is not closed") from exc
    frontmatter = _load_yaml_mapping("\n".join(lines[1:closing_index]), "SKILL.md frontmatter")
    if set(frontmatter) != {"name", "description"}:
        raise ReleaseError("SKILL.md frontmatter must contain only name and description")
    if frontmatter["name"] != SKILL_NAME:
        raise ReleaseError(f"SKILL.md name must be {SKILL_NAME!r}")
    description = frontmatter["description"]
    if not isinstance(description, str) or not description.strip():
        raise ReleaseError("SKILL.md description must be non-empty")
    if not "\n".join(lines[closing_index + 1 :]).strip():
        raise ReleaseError("SKILL.md body must be non-empty")

    metadata_path = skill_root / OPENAI_METADATA_RELATIVE_PATH
    try:
        metadata = _load_yaml_mapping(
            metadata_path.read_text(encoding="utf-8"), "agents/openai.yaml"
        )
    except FileNotFoundError as exc:
        raise ReleaseError(f"missing Codex metadata: {metadata_path}") from exc
    interface = metadata.get("interface")
    if not isinstance(interface, dict):
        raise ReleaseError("agents/openai.yaml interface must be a YAML object")
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ReleaseError(f"agents/openai.yaml interface.{field} must be non-empty")
    if not 25 <= len(interface["short_description"]) <= 64:
        raise ReleaseError("agents/openai.yaml short_description must contain 25 to 64 characters")
    if f"${SKILL_NAME}" not in interface["default_prompt"]:
        raise ReleaseError(f"agents/openai.yaml default_prompt must mention ${SKILL_NAME}")


def validate_platform_sources(skill_root: Path) -> None:
    """Validate plugin templates and the shared remote MCP safety contract."""
    platform_root = _platform_source_root(skill_root.resolve())
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
            raise ReleaseError(f"{platform} plugin name must be {SKILL_NAME!r}")
        if manifest.get("version") != "0.0.0":
            raise ReleaseError(f"{platform} plugin version must use the release token")
        if manifest.get("skills") != "./skills/":
            raise ReleaseError(f"{platform} plugin must load ./skills/")
        if manifest.get("mcpServers") != "./.mcp.json":
            raise ReleaseError(f"{platform} plugin must load ./.mcp.json")

        mcp = json.loads((source_root / ".mcp.json").read_text(encoding="utf-8"))
        server = (mcp.get("mcpServers") or {}).get("goalfy_workflow") or {}
        if server.get("url") != "https://workflow-mcp.qa.goalfyai.com/mcp":
            raise ReleaseError(f"{platform} MCP must use the reviewed QA endpoint")
        serialized = json.dumps(server, ensure_ascii=False)
        if "GOALFY_WORKFLOW_API_KEY" not in serialized:
            raise ReleaseError(f"{platform} MCP must reference the API Key env var")
        if re.search(r"Bearer\s+sk_[A-Za-z0-9]", serialized):
            raise ReleaseError(f"{platform} MCP must not contain a plaintext API Key")

        combined_docs = "\n".join(
            (source_root / name).read_text(encoding="utf-8")
            for name in ("README.md", "AGENTS.md", "UPDATE.md")
        )
        for required_text in (
            "12",
            "bubble",
            "list_assets",
            "/developer/api-keys",
            "sk_",
            "Authorization: Bearer",
        ):
            if required_text not in combined_docs:
                raise ReleaseError(
                    f"{platform} install docs must mention {required_text!r}"
                )


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
        raise ReleaseError(f"missing release manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"invalid release manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError("release manifest must be a JSON object")
    return data


def _validate_version(version: Any) -> tuple[int, int, int]:
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ReleaseError("version must use MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _validate_released_at(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ReleaseError("released_at must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseError("released_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseError("released_at must include a timezone")


def check_release(
    skill_root: Path, *, check_direct_install: bool = True
) -> dict[str, Any]:
    """Validate manifest metadata and every canonical source checksum."""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_sources(skill_root)
    manifest = _load_manifest(skill_root)
    if set(manifest) != MANIFEST_KEYS:
        missing = sorted(MANIFEST_KEYS - set(manifest))
        extra = sorted(set(manifest) - MANIFEST_KEYS)
        raise ReleaseError(f"release manifest keys differ: missing={missing}, extra={extra}")
    if manifest["skill_name"] != SKILL_NAME:
        raise ReleaseError(f"skill_name must be {SKILL_NAME!r}")
    _validate_version(manifest["version"])
    _validate_released_at(manifest["released_at"])

    reason = manifest["update_reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
        raise ReleaseError("update_reason must contain 1 to 1024 characters")

    files = discover_source_files(skill_root)
    expected_files = [_relative(path, skill_root) for path in files]
    if manifest["source_files"] != expected_files:
        raise ReleaseError(
            "source_files differ from canonical Skill files; run the release action"
        )
    if not isinstance(manifest["checksums"], dict):
        raise ReleaseError("checksums must be a JSON object")
    actual_checksums = _checksums(skill_root, files)
    if manifest["checksums"] != actual_checksums:
        stale = sorted(
            path
            for path in set(manifest["checksums"]) | set(actual_checksums)
            if manifest["checksums"].get(path) != actual_checksums.get(path)
        )
        raise ReleaseError(f"release checksums are stale: {stale}")

    platform_root = _platform_source_root(skill_root)
    platform_files = discover_platform_source_files(skill_root)
    expected_platform_files = [
        path.relative_to(platform_root).as_posix() for path in platform_files
    ]
    if manifest["platform_source_files"] != expected_platform_files:
        raise ReleaseError(
            "platform_source_files differ from reviewed install files; run the release action"
        )
    actual_platform_checksums = {
        path.relative_to(platform_root).as_posix(): _sha256(path)
        for path in platform_files
    }
    if manifest["platform_checksums"] != actual_platform_checksums:
        stale = sorted(
            path
            for path in set(manifest["platform_checksums"])
            | set(actual_platform_checksums)
            if manifest["platform_checksums"].get(path)
            != actual_platform_checksums.get(path)
        )
        raise ReleaseError(f"platform release checksums are stale: {stale}")
    if check_direct_install:
        check_direct_install_tree(skill_root, manifest)
    return manifest


def release(skill_root: Path, version: str, reason: str) -> dict[str, Any]:
    """Write a new explicit release manifest without performing Git operations."""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_sources(skill_root)
    new_version = _validate_version(version)
    reason = reason.strip()
    if not reason or len(reason) > 1024:
        raise ReleaseError("update_reason must contain 1 to 1024 characters")

    manifest_path = _manifest_path(skill_root)
    if manifest_path.exists():
        current = _load_manifest(skill_root)
        current_version = _validate_version(current.get("version"))
        if new_version <= current_version:
            raise ReleaseError(
                f"new version {version} must be greater than current version {current['version']}"
            )

    files = discover_source_files(skill_root)
    platform_root = _platform_source_root(skill_root)
    platform_files = discover_platform_source_files(skill_root)
    manifest = {
        "skill_name": SKILL_NAME,
        "version": version,
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
            path.relative_to(platform_root).as_posix(): _sha256(path)
            for path in platform_files
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(manifest_path)
    sync_direct_install_tree(skill_root, manifest)
    return check_release(skill_root)


def _write_member(archive: zipfile.ZipFile, archive_path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(archive_path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(
        info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
    )


def _write_zip(
    output_path: Path, skill_root: Path, source_files: Iterable[str]
) -> None:
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative_path in source_files:
            data = (skill_root / relative_path).read_bytes()
            archive_path = f"{SKILL_NAME}/{relative_path}"
            _write_member(archive, archive_path, data)


def _bundle_marketplace(platform: str, version: str) -> tuple[str, bytes]:
    if platform == "codex":
        path = ".agents/plugins/marketplace.json"
        body = {
            "name": "goalfy-workflow",
            "interface": {"displayName": "Goalfy Workflow"},
            "plugins": [
                {
                    "name": SKILL_NAME,
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
            "name": "goalfy-workflow",
            "description": "Goalfy Workflow External MCP and authoring Skill.",
            "owner": {"name": "GoalfyAI"},
            "plugins": [
                {
                    "name": SKILL_NAME,
                    "description": "Build and validate GoalfyMax Workflow scenario packages.",
                    "version": version,
                    "author": {"name": "GoalfyAI"},
                    "source": f"./plugins/{SKILL_NAME}",
                    "category": "development",
                }
            ],
        }
    return path, (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode()


def _direct_marketplace(platform: str, version: str) -> bytes:
    body: dict[str, Any] = {
        "name": "goalfy-workflow",
        "description": "Create and validate GoalfyMax Workflow scenario packages through the audited External MCP.",
        "owner": {"name": "GoalfyAI"},
        "plugins": [
            {
                "name": SKILL_NAME,
                "description": "Build and validate GoalfyMax Workflow scenario packages.",
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


def _direct_install_files(
    skill_root: Path, manifest: dict[str, Any]
) -> dict[Path, bytes]:
    """Render the checked-in marketplace trees from the one canonical Skill."""
    version = manifest["version"]
    platform_root = _platform_source_root(skill_root)
    common_files = [
        path
        for path in manifest["source_files"]
        if path == "SKILL.md" or path.startswith("references/")
    ]
    rendered: dict[Path, bytes] = {}
    for platform in PLATFORM_NAMES:
        rendered[DIRECT_MARKETPLACE_PATHS[platform]] = _direct_marketplace(
            platform, version
        )
        for source_path in sorted((platform_root / platform).rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(platform_root / platform)
            rendered[Path(platform) / relative_path] = (
                source_path.read_text(encoding="utf-8")
                .replace(PLATFORM_VERSION_TOKEN, version)
                .encode()
            )
        source_files = (
            list(manifest["source_files"]) if platform == "codex" else common_files
        )
        for relative_path in source_files:
            rendered[
                Path(platform) / "skills" / SKILL_NAME / relative_path
            ] = (skill_root / relative_path).read_bytes()
    return rendered


def sync_direct_install_tree(
    skill_root: Path, manifest: dict[str, Any] | None = None
) -> list[Path]:
    """Regenerate repository marketplace files; generated copies are never edited."""
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


def check_direct_install_tree(
    skill_root: Path, manifest: dict[str, Any] | None = None
) -> None:
    """Reject missing, edited, or extra files in generated marketplace trees."""
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
        raise ReleaseError(
            f"direct marketplace files differ: missing={missing}, extra={extra}"
        )
    stale = sorted(
        str(relative_path)
        for relative_path, data in expected.items()
        if (repository_root / relative_path).read_bytes() != data
    )
    if stale:
        raise ReleaseError(f"direct marketplace files are stale: {stale}")


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
        _write_member(
            archive, f"{bundle_root}/{marketplace_path}", marketplace_data
        )
        for source_path in sorted(platform_root.rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(platform_root).as_posix()
            data = source_path.read_text(encoding="utf-8").replace(
                PLATFORM_VERSION_TOKEN, version
            ).encode()
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
    """Build deterministic packages from the checked release only."""
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
        output_path = output_dir / f"{SKILL_NAME}-{platform}-{manifest['version']}.zip"
        source_files = (
            list(manifest["source_files"]) if platform == "codex" else common_files
        )
        _write_platform_zip(
            output_path,
            skill_root,
            platform,
            manifest["version"],
            source_files,
        )
        outputs.append(output_path)
    generic_path = output_dir / f"{SKILL_NAME}-generic-{manifest['version']}.zip"
    _write_zip(generic_path, skill_root, common_files)
    outputs.append(generic_path)
    return outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("check", help="validate the checked-in release manifest")
    subparsers.add_parser(
        "sync", help="regenerate direct-install marketplace files from the checked release"
    )

    release_parser = subparsers.add_parser("release", help="write a new release manifest")
    release_parser.add_argument("--version", required=True, help="MAJOR.MINOR.PATCH")
    release_parser.add_argument("--reason", required=True, help="release reason")

    build_parser = subparsers.add_parser("build", help="build all platform ZIPs")
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="output directory (default: repository dist/)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    skill_root = _skill_root()
    try:
        if args.action == "check":
            manifest = check_release(skill_root)
            print(f"{SKILL_NAME} release {manifest['version']} is current")
        elif args.action == "sync":
            manifest = check_release(skill_root, check_direct_install=False)
            for path in sync_direct_install_tree(skill_root, manifest):
                print(path)
            check_release(skill_root)
        elif args.action == "release":
            manifest = release(skill_root, args.version, args.reason)
            print(f"released {SKILL_NAME} {manifest['version']}")
        else:
            output_dir = args.output_dir or skill_root.parent / "dist"
            for path in build_packages(skill_root, output_dir):
                print(path)
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
