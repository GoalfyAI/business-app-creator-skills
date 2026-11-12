#!/usr/bin/env python3
"""校验并发布 business-app-creator 插件（入口 Skill agenticapp-creator 与五段、任务、平台对象等 19 个平级 Skill）。

模型很简单：`skills/` 下 20 个平级 Skill 目录是唯一源，发布时逐个复制到各平台的 `skills/<名字>/`，
版本标记只写在入口 SKILL.md。平台安装文档（README/AGENTS/UPDATE/.mcp.json）
和插件 manifest 都是手工维护的最终文件，不做模板渲染。

发布清单 `skill-release.json` 记录版本与校验和，用来发现"改了内容但没发布"。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SKILL_NAME = "agenticapp-creator"
MCP_SERVER_NAME = "business-app-creator-mcp"  # 客户端 mcpServers 键 / 服务端 EXTERNAL_MCP_NAME
PLUGIN_NAME = "business-app-creator"  # 插件 / 市场名（产品名）；已安装的插件按这个名字升级，所以不随 Skill 改名
# Skill 唯一源：仓库 skills/ 下 20 个平级目录，每个一个 SKILL.md（name 等于目录名）。
# 宿主（Claude Code、Codex）按插件 skills/ 下的一级目录发现 Skill，嵌套在入口里的 Skill 不会出现在宿主列表。
SKILLS_DIR = "skills"
# 入口 Skill 的目录：版本标记、keywords、Codex 元数据与发布清单都以它为准。
SKILL_CONTENT_DIR = f"{SKILLS_DIR}/{SKILL_NAME}"
MANIFEST_RELATIVE_PATH = Path("skill-release.json")
OPENAI_METADATA_RELATIVE_PATH = Path("agents/openai.yaml")
# 入口目录里允许的内容：SKILL.md、agents/openai.yaml 与 references/*.md。
ENTRY_REFERENCES_DIR = "references"
# 其他 Skill 目录里允许的内容：参考与模板只放文本，脚本只放 Python。
# 它们不带 agents/openai.yaml：MCP 由插件的 .mcp.json 统一声明，Codex 的 Skill 级依赖只在入口声明一次。
ATOMIC_SKILL_SUBDIRS = {"references": (".md",), "assets": (".md", ".html", ".css"), "scripts": (".mjs",)}
# 五段 Skill，按段的顺序。
STAGE_SKILLS = (
    "agenticapp-stage-1-requirements",
    "agenticapp-stage-2-plan",
    "agenticapp-stage-3-build",
    "agenticapp-stage-4-acceptance",
    "agenticapp-stage-5-launch",
)
# 入口之外的全部 Skill；少一个或多出一个都拒绝发布，防止改名或漏建。
ATOMIC_SKILLS = (
    *STAGE_SKILLS,
    "agenticapp-task-revise",
    "agenticapp-task-diagnose",
    "agenticapp-task-user-feedback",
    "agenticapp-tool-workspace",
    "agenticapp-tool-workflow",
    "agenticapp-tool-data-template",
    "agenticapp-tool-frontend",
    "agenticapp-tool-deploy",
    "agenticapp-tool-integration",
    "agenticapp-tool-automation",
    "agenticapp-role-collab",
    "agenticapp-host-studio",
    "agenticapp-ref-platform-limits",
    "agenticapp-ref-experience",
)
ALL_SKILLS = (SKILL_NAME, *ATOMIC_SKILLS)
# 旧结构的目录（七节点版的 flow、modules、protocols，以及拆成子 Skill 之前的五段、任务、沟通模板、
# 参考、清单和根目录脚本）。平台副本按 Skill 整目录重建，残留在 Skill 目录里的旧文件由副本校验拦下。
RETIRED_SKILL_DIRS = ("flow", "modules", "protocols", "stages", "tasks", "design", "reference", "checklists", "scripts")
# 只发 Claude Code 与 Codex 两个插件市场平台，20 个 Skill 平级放在平台目录的 skills/ 下，内容与唯一源完全一致。
# Manus 与通用集成已停止维护：不再生成目录和 zip，zip 每次发版重新提交曾把仓库撑到 69MB，
# 让插件市场克隆超时（FB-1544）。
# 升级指南：<D编号>.md、README.md 与 schema.json 随插件发布，格式与关系由同目录上一级的
# scripts/upgrade_guides.py 校验。 [需求:D-3962]
# 指南与脚本留在 D-3962 发布时的位置 skills/business-app-creator/（已发布指南按路径冻结，入口改名后不搬）；
# 这个目录不是 Skill，没有 SKILL.md，只放指南目录和读取脚本。
UPGRADE_GUIDES_HOME = "business-app-creator"
UPGRADE_GUIDES_DIR = "upgrade-guides"
UPGRADE_GUIDES_SCRIPT = Path("scripts/upgrade_guides.py")
PLATFORM_LAYOUTS = {
    "claude-code": {
        "with_openai_metadata": False,
        "mcp_config": ".mcp.json",
        "docs": ("README.md", "AGENTS.md", "UPDATE.md"),
    },
    "codex": {
        # Codex 读入口的 agents/openai.yaml 取展示名、默认提示词与 MCP 依赖声明
        "with_openai_metadata": True,
        "mcp_config": ".mcp.json",
        "docs": ("README.md", "AGENTS.md", "UPDATE.md"),
    },
}
PLATFORM_NAMES = tuple(PLATFORM_LAYOUTS)
# 附加 Skill：仓库根目录下自研的额外 Skill，随插件同步到 claude-code / codex 的 skills/ 下。
# 不进入口 Skill 的发布清单与版本闸门，随插件版本自然更新。
# 2026-09-27 起 lite 版并入主 Skill，不再有附加 Skill；机制保留给以后需要时使用。 [任务:T-3724]
EXTRA_SKILL_SOURCES: dict[str, Path] = {}
# 已退役的 Skill 目录：同步时从各平台 skills/ 下删除，校验时发现残留即拒绝发布。
# business-app-creator 是入口改名为 agenticapp-creator 之前的目录。
RETIRED_EXTRA_SKILLS = ("business-app-creator-lite",)
EXTRA_SKILL_PLATFORMS = ("claude-code", "codex")
# 仓库里的安装物料统一指向同一个 MCP 地址，由本常量唯一决定。
# 2026-09-02 拍板：生产 MCP 尚未部署（404），安装物料先指向 QA；切回生产时改这一处 +
# 文档里的 API 密钥页域名（goalfymax.goalfyai.cn ↔ goalfymax.goalfyai.cn），再发版。
PROD_MCP_ENDPOINT = "https://business-app-creator-mcp.goalfyai.cn/mcp"
# 渠道：同一份 Skill 源码按环境生成不同的安装物料。main 分支就是 prod 渠道（已安装用户都在这里），
# qa / pre 渠道由 scripts/build_env_branch.py 生成、推到 GitHub 的 business-qa / business-pre 分支。
# 环境相关的只有 MCP 地址、密钥环境变量名与 API 密钥页；源码一律保持 prod 写法。 [任务:T-3784]
RELEASE_CHANNELS = {
    "prod": {
        "mcp_endpoint": PROD_MCP_ENDPOINT,
        "api_key_env": "BUSINESS_APP_CREATOR_API_KEY",
        "api_keys_page": "https://goalfymax.goalfyai.cn/developer/api-keys",
    },
    "qa": {
        "mcp_endpoint": "https://business-app-creator-mcp.qa.goalfyai.cn/mcp",
        "api_key_env": "BUSINESS_APP_CREATOR_QA_API_KEY",
        "api_keys_page": "https://goalfymax.qa.goalfyai.cn/developer/api-keys",
    },
    "pre": {
        "mcp_endpoint": "https://business-app-creator-mcp.pre.goalfyai.cn/mcp",
        "api_key_env": "BUSINESS_APP_CREATOR_PRE_API_KEY",
        "api_keys_page": "https://goalfymax.pre.goalfyai.cn/developer/api-keys",
    },
}
CHANNEL_ENV = "SKILL_RELEASE_CHANNEL"
ENV_PACKAGE_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-(qa|pre)\.(0|[1-9]\d*)$")
DATA_SKILL_VERSION_RE = re.compile(r"^v\d{8}-[0-9a-f]{6}$")
LEGACY_SKILL_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
SKILL_VERSION_RE = re.compile(r"\[skill-version:(v(?:\d+\.\d+\.\d+|\d{8}-[0-9a-f]{6}))\]")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PACKAGE_VERSION_RE = re.compile(r'("version":\s*")(\d+\.\d+\.\d+(?:-(?:qa|pre)\.\d+)?)(")')
REQUIRED_SKILL_KEYWORDS = {
    "scene package",
    "scenario package",
    "场景包",
    "workflow",
    "business UI",
    "智能应用",
    "GoalfyMax",
    "MCP",
}
# 每次发布都要同步提升的插件 manifest：Claude 与 Codex 靠 plugin.json 的版本
# 判断有无新版，漏掉任何一个都会让已安装用户收不到更新。
PACKAGE_MANIFESTS = (
    Path("claude-code/.claude-plugin/plugin.json"),
    Path("codex/.codex-plugin/plugin.json"),
    Path(".claude-plugin/marketplace.json"),
    Path(".agents/plugins/marketplace.json"),
)
MANIFEST_KEYS = {
    "scaffold_min_required_version",
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


def release_channel() -> str:
    """当前构建渠道，默认 prod；只接受 RELEASE_CHANNELS 里的值。"""
    channel = os.environ.get(CHANNEL_ENV, "prod").strip() or "prod"
    if channel not in RELEASE_CHANNELS:
        raise ReleaseError(f"{CHANNEL_ENV} 只能是 {sorted(RELEASE_CHANNELS)}，当前为 {channel!r}")
    return channel


def channel_config(channel: str | None = None) -> dict[str, str]:
    return RELEASE_CHANNELS[channel or release_channel()]


def _other_channel_markers(channel: str) -> list[str]:
    """其他渠道独有的环境值：出现在本渠道产物里就说明配置串了。"""
    own = set(channel_config(channel).values())
    return sorted({value for name, config in RELEASE_CHANNELS.items() if name != channel for value in config.values()} - own)


def _skill_root() -> Path:
    """入口 Skill 目录（skills/agenticapp-creator）；其他 Skill 是它的同级目录。"""
    return Path(__file__).resolve().parents[1] / SKILL_CONTENT_DIR


def _skills_root(skill_root: Path) -> Path:
    """全部 Skill 的上级目录：仓库的 skills/。"""
    return skill_root.resolve().parent


def _repository_root(skill_root: Path) -> Path:
    return skill_root.resolve().parents[1]


def _manifest_path(skill_root: Path) -> Path:
    return _repository_root(skill_root) / MANIFEST_RELATIVE_PATH


def _relative(path: Path, skill_root: Path) -> str:
    """发布清单里的路径：相对 skills/，以 Skill 名开头，例如 agenticapp-creator/SKILL.md。"""
    return path.resolve().relative_to(_skills_root(skill_root)).as_posix()


def _is_shipped(relative_path: PurePosixPath, suffix: str) -> bool:
    parts = relative_path.parts
    if len(parts) < 2:
        return False
    rest = parts[1:]
    if parts[0] == UPGRADE_GUIDES_HOME:
        return rest == UPGRADE_GUIDES_SCRIPT.parts or (
            len(rest) == 2 and rest[0] == UPGRADE_GUIDES_DIR and (suffix == ".md" or rest[1] == "schema.json")
        )
    if rest == ("SKILL.md",):
        return True
    if parts[0] == SKILL_NAME:
        return rest == OPENAI_METADATA_RELATIVE_PATH.parts or (
            len(rest) == 2 and rest[0] == ENTRY_REFERENCES_DIR and suffix == ".md"
        )
    return len(rest) == 2 and rest[0] in ATOMIC_SKILL_SUBDIRS and suffix in ATOMIC_SKILL_SUBDIRS[rest[0]]


def discover_source_files(skill_root: Path) -> list[Path]:
    """返回作为 Skill 内容发布的唯一源文件集合（skills/ 下全部平级 Skill）。"""
    skill_root = skill_root.resolve()
    skills_root = _skills_root(skill_root)
    entrypoint = skill_root / "SKILL.md"
    if not entrypoint.is_file():
        raise ReleaseError(f"缺少 Skill 入口文件：{entrypoint}")

    openai_metadata = skill_root / OPENAI_METADATA_RELATIVE_PATH
    if not openai_metadata.is_file():
        raise ReleaseError(f"缺少 Codex 元数据：{openai_metadata}")

    if not (skill_root / ENTRY_REFERENCES_DIR).is_dir():
        raise ReleaseError(f"缺少 Skill 目录：{skill_root / ENTRY_REFERENCES_DIR}")

    files = []
    for path in skills_root.rglob("*"):
        relative_path = PurePosixPath(path.relative_to(skills_root).as_posix())
        if path.is_symlink():
            raise ReleaseError(f"Skill 发布文件不允许使用符号链接：{path}")
        if not path.is_file():
            continue
        if "__pycache__" in relative_path.parts:
            continue
        if any(part.startswith(".") for part in relative_path.parts):
            raise ReleaseError(f"不支持的 Skill 隐藏文件：{relative_path.as_posix()}")
        if _is_shipped(relative_path, path.suffix.lower()):
            files.append(path)
            continue
        raise ReleaseError(f"不支持的 Skill 文件：{relative_path.as_posix()}")

    return sorted(files, key=lambda path: _relative(path, skill_root))


# 正文里指向 Skill 自身文件的路径，Agent 会照着去读或执行；指向发布包里不存在的文件时，
# 用户侧直接表现为 No such file。Markdown 链接一律检查；`代码` 里的路径只检查以 Skill 内容目录
# 开头的写法——`workspace.json`、`backend/README.md` 这类是智能应用工程里的文件，不在发布包内。
_REFERENCE_SPAN_RE = re.compile(r"`([^`\n]+)`|\]\(([^)\s]+)\)")
_REFERENCE_PATH_RE = re.compile(r"^(?:\.{1,2}/)*[\w\-.]+(?:/[\w\-.]+)*\.(?:md|py|json|ya?ml|sh|ts|js|txt)$")
_SKILL_CONTENT_DIRS = {ENTRY_REFERENCES_DIR, *ATOMIC_SKILL_SUBDIRS, "agents", *ALL_SKILLS, UPGRADE_GUIDES_HOME, UPGRADE_GUIDES_DIR}
# 允许不在发布包里的引用：(引用所在文件的前缀, 引用原文, 原因)。前缀为空表示任意文件。
REFERENCE_ALLOWLIST: tuple[tuple[str, str, str], ...] = (
    ("", "./scripts/pack.sh", "智能应用工程里的打包脚本"),
    ("", "scripts/gen-types.ts", "智能应用工程里的类型生成脚本"),
)


def _reference_allowed(source: str, reference: str) -> bool:
    return any(
        reference == allowed and source.startswith(prefix)
        for prefix, allowed, _reason in REFERENCE_ALLOWLIST
    )


def _normalize_reference(base: PurePosixPath, reference: str) -> str | None:
    parts: list[str] = []
    for part in (base / reference).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def find_broken_references(skill_root: Path) -> list[str]:
    """列出发布包内 md 正文中指向不存在文件的引用（文件:行号: 引用）。

    解析顺序：引用所在目录、引用所在 Skill 的根目录。跨 Skill 引用写成 `../<名字>/...` 的相对路径。
    """
    skill_root = skill_root.resolve()
    skills_root = _skills_root(skill_root)
    shipped ={_relative(path, skill_root) for path in discover_source_files(skill_root)}
    shipped_dirs = {str(parent) for item in shipped for parent in PurePosixPath(item).parents}
    broken = []
    for source in sorted(item for item in shipped if item.endswith(".md")):
        # 指南正文写的是智能应用工程里的路径，不是 Skill 自身文件。
        if re.fullmatch(rf"{UPGRADE_GUIDES_HOME}/{UPGRADE_GUIDES_DIR}/D-[0-9]+\.md", source):
            continue
        source_path = PurePosixPath(source)
        bases = [source_path.parent, PurePosixPath(source_path.parts[0])]
        text = (skills_root / source).read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in _REFERENCE_SPAN_RE.finditer(line):
                code_span, link_target = match.groups()
                reference = (code_span or link_target).split("#", 1)[0].strip()
                if not _REFERENCE_PATH_RE.fullmatch(reference) or _reference_allowed(source, reference):
                    continue
                if code_span is not None:
                    leading = [part for part in PurePosixPath(reference).parts if part not in (".", "..")]
                    if not reference.startswith("../") and (len(leading) < 2 or leading[0] not in _SKILL_CONTENT_DIRS):
                        continue
                candidates = (_normalize_reference(base, reference) for base in bases)
                if any(item in shipped or item in shipped_dirs for item in candidates if item):
                    continue
                broken.append(f"{source}:{line_number}: {reference}")
    return broken


def validate_internal_references(skill_root: Path) -> None:
    broken = find_broken_references(skill_root)
    if broken:
        raise ReleaseError("Skill 正文引用了发布包里不存在的文件：\n" + "\n".join(broken))


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
        raise ReleaseError("agents/openai.yaml 必须声明唯一的 business-app-creator MCP 依赖")
    endpoint = tools[0].get("url")
    expected = channel_config()["mcp_endpoint"]
    if endpoint != expected:
        raise ReleaseError(f"agents/openai.yaml 必须使用 {release_channel()} 渠道的 MCP 地址 {expected}")
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
    channel = release_channel()
    config = channel_config(channel)
    foreign = _other_channel_markers(channel)
    for platform, layout in PLATFORM_LAYOUTS.items():
        platform_root = repository_root / platform
        mcp_name = layout["mcp_config"]
        if mcp_name:
            mcp_path = platform_root / mcp_name
            if not mcp_path.is_file():
                raise ReleaseError(f"缺少 {platform} 的 MCP 配置：{mcp_path}")
            mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
            server = (mcp.get("mcpServers") or {}).get(MCP_SERVER_NAME) or {}
            if server.get("url") != config["mcp_endpoint"]:
                raise ReleaseError(f"{platform} MCP 必须使用 {channel} 渠道的 MCP 地址 {config['mcp_endpoint']}")
            serialized = json.dumps(server, ensure_ascii=False)
            if config["api_key_env"] not in serialized:
                raise ReleaseError(f"{platform} MCP 必须引用 API Key 环境变量")
            if re.search(r"Bearer\s+sk_[A-Za-z0-9]", serialized):
                raise ReleaseError(f"{platform} MCP 不得包含明文 API Key")

        docs = "\n".join(
            (platform_root / name).read_text(encoding="utf-8") for name in layout["docs"]
        )
        # 只校验安装文档必须交代清楚的事实，不锁具体措辞：
        # 密钥从哪来、装完怎么验证。
        for required_text in ("/developer/api-keys", "list_assets"):
            if required_text not in docs:
                raise ReleaseError(f"{platform} 安装文档必须提到 {required_text!r}")
        # 有 .mcp.json 的平台靠环境变量注入密钥，文档必须写明变量名
        if mcp_name and config["api_key_env"] not in docs:
            raise ReleaseError(f"{platform} 安装文档必须说明 API Key 环境变量 {config['api_key_env']}")
        # 渠道之间不能串：prod 物料里出现 QA 地址或 QA 变量名（反之亦然）都拒绝发布 [任务:T-3784]
        mcp_text = (platform_root / mcp_name).read_text(encoding="utf-8") if mcp_name else ""
        leaked = [marker for marker in foreign if marker in docs or marker in mcp_text]
        if leaked:
            raise ReleaseError(f"{platform} 的安装物料混入了其他渠道的配置：{leaked}")
        # 两个平台都走插件市场，必须给出公开来源
        if "GoalfyAI/business-app-creator-skills" not in docs:
            raise ReleaseError(f"{platform} 安装文档必须给出公开插件市场来源")


# 体积预算（行数）：每个 SKILL.md 只写这个时机要做的事，细节进 references/、模板进 assets/。
LINE_BUDGETS: dict[str, int] = {"SKILL.md": 150, "references": 200}
# 段 Skill 这几节必须有且按顺序：开工前核对、可逐条核对的步骤、交棒条件与下一个 Skill；
# ⑤ 是最后一段，没有下一段可交，最后一节写「结束」。
STAGE_REQUIRED_HEADINGS = ("开始前确认", "按这个顺序做", "交棒")
LAST_STAGE_REQUIRED_HEADINGS = ("开始前确认", "按这个顺序做", "结束")
# 平台对象 Skill 必须有「常见错误」：工具用错的地方集中在这里。
TOOL_REQUIRED_HEADINGS = ("常见错误",)
# 入口之外的 Skill 的 description 全部常驻宿主的 Skill 目录，控制长度（Codex 单条超过 1024 字符会被截断）。
ATOMIC_SKILL_DESCRIPTION_MAX = 200
_SECTION_HEADING_RE = re.compile(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$")


def _frontmatter(path: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ReleaseError(f"{label} 必须以闭合的 YAML frontmatter 开头")
    closing = lines.index("---", 1)
    return _load_yaml_mapping("\n".join(lines[1:closing]), f"{label} frontmatter"), lines[closing + 1 :]


def _headings(lines: list[str]) -> list[str]:
    in_code = False
    headings = []
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
            continue
        match = None if in_code else _SECTION_HEADING_RE.match(line)
        if match:
            headings.append(match.group(1))
    return headings


def _atomic_skill_errors(skill_root: Path, name: str) -> list[str]:
    """入口之外的 Skill 的 frontmatter 与必备小节：name 与目录同名、description 非空不超长、不带版本标记。"""
    label = f"{name}/SKILL.md"
    path = _skills_root(skill_root) / name / "SKILL.md"
    if not path.is_file():
        return [f"{label} 缺失"]
    frontmatter, body = _frontmatter(path, label)
    errors = []
    if set(frontmatter) != {"name", "description"}:
        errors.append(f"{label} 的 frontmatter 必须且只能包含 name 和 description")
    if frontmatter.get("name") != name:
        errors.append(f"{label} 的 name 必须与目录名 {name!r} 一致")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{label} 的 description 不能为空")
    elif len(description) > ATOMIC_SKILL_DESCRIPTION_MAX:
        errors.append(f"{label} 的 description 有 {len(description)} 字符，超过 {ATOMIC_SKILL_DESCRIPTION_MAX}")
    elif SKILL_VERSION_RE.search(description):
        errors.append(f"{label} 不能带 skill-version 标记，版本只写在入口 SKILL.md")
    headings = _headings(body)
    if name == STAGE_SKILLS[-1]:
        required = LAST_STAGE_REQUIRED_HEADINGS
    elif name in STAGE_SKILLS:
        required = STAGE_REQUIRED_HEADINGS
    elif name.startswith("agenticapp-tool-"):
        required = TOOL_REQUIRED_HEADINGS
    else:
        required = ()
    if required and tuple(h for h in headings if h in required) != required:
        errors.append(f"{label} 的二级标题必须按顺序包含 {list(required)}，当前 {headings}")
    return errors


def validate_skill_layout(skill_root: Path) -> None:
    """校验框架骨架：skills/ 下正好是约定的平级 Skill、各自元数据与必备小节齐全、行数不超预算。"""
    skill_root = skill_root.resolve()
    errors = []
    present = sorted(
        path.name for path in _skills_root(skill_root).iterdir() if path.is_dir() and path.name != UPGRADE_GUIDES_HOME
    )
    missing = sorted(set(ALL_SKILLS) - set(present))
    unexpected = sorted(set(present) - set(ALL_SKILLS))
    if missing or unexpected:
        errors.append(f"平级 Skill 必须正好是 {list(ALL_SKILLS)}；缺少 {missing}，多出 {unexpected}")
    for name in ATOMIC_SKILLS:
        if name in present:
            errors.extend(_atomic_skill_errors(skill_root, name))
    for path in discover_source_files(skill_root):
        relative = PurePosixPath(_relative(path, skill_root))
        if relative.suffix != ".md" or "assets" in relative.parts:
            continue
        budget = LINE_BUDGETS["SKILL.md" if relative.name == "SKILL.md" else "references"]
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > budget:
            errors.append(f"{relative} 有 {len(lines)} 行，超过 {budget} 行预算")
    if errors:
        raise ReleaseError("Skill 框架骨架不符：\n" + "\n".join(errors))


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
    """prod 渠道只接受 MAJOR.MINOR.PATCH；qa / pre 渠道只接受 MAJOR.MINOR.PATCH-<渠道>.N。"""
    if not isinstance(version, str):
        raise ReleaseError("package version 必须是字符串")
    channel = release_channel()
    if channel != "prod":
        matched = ENV_PACKAGE_VERSION_RE.fullmatch(version)
        if not matched or matched.group(4) != channel:
            raise ReleaseError(f"{channel} 渠道的 package version 必须是 MAJOR.MINOR.PATCH-{channel}.N")
        return tuple(int(part) for part in matched.groups()[:3])  # type: ignore[return-value]
    if not SEMVER_RE.fullmatch(version):
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


def _valid_bumps(version: str) -> set[str]:
    """合法的下一个 package version：patch+1、minor+1（patch 归零）或 major+1（minor/patch 归零）。"""
    major, minor, patch = _validate_package_version(version)
    return {
        f"{major}.{minor}.{patch + 1}",
        f"{major}.{minor + 1}.0",
        f"{major + 1}.0.0",
    }


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
        versions[relative.as_posix()] = found.group(2)
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
            lambda match, new=version: f"{match.group(1)}{new}{match.group(3)}", content, count=1
        )
        if count != 1:
            raise ReleaseError(f"{relative} 的 version 字段替换失败")
        path.write_text(updated, encoding="utf-8")

    # pyproject / uv.lock 只跟 prod 版本走：qa / pre 的预发布后缀不是合法的 PEP 440 版本，且不影响插件分发
    if release_channel() != "prod":
        return
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
            r'(?ms)(name = "business-app-creator-skills"\nversion = ")\d+\.\d+\.\d+(")',
            lambda match, new=version: f"{match.group(1)}{new}{match.group(2)}",
            content,
            count=1,
        )
        if count == 1:
            lockfile.write_text(updated, encoding="utf-8")


def sync_plugin_display_metadata(skill_root: Path) -> None:
    """安装入口的展示文案随 Skill 正本生成，保留插件身份与安装配置。"""
    frontmatter = _load_yaml_mapping(
        (skill_root / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1],
        "SKILL.md frontmatter",
    )
    interface = _load_yaml_mapping(
        (skill_root / OPENAI_METADATA_RELATIVE_PATH).read_text(encoding="utf-8"),
        "agents/openai.yaml",
    )["interface"]
    description = SKILL_VERSION_RE.sub("", frontmatter["description"]).strip()
    for relative in PACKAGE_MANIFESTS:
        path = _repository_root(skill_root) / relative
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if "plugins" in manifest:
            manifest["description"] = interface["short_description"]
            plugin = next(item for item in manifest["plugins"] if item["name"] == PLUGIN_NAME)
        else:
            plugin = manifest
        plugin["description"] = description
        if "displayName" in plugin:
            plugin["displayName"] = interface["display_name"]
        if "keywords" in plugin:
            plugin["keywords"] = frontmatter["keywords"]
        if "interface" in plugin:
            plugin["interface"].update({
                "displayName": interface["display_name"],
                "shortDescription": interface["short_description"],
                "longDescription": description,
                "defaultPrompt": interface["default_prompt"],
            })
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_released_at(value: Any) -> None:
    if not isinstance(value, str):
        raise ReleaseError("released_at 必须是 ISO-8601 字符串")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReleaseError("released_at 必须形如 2026-01-01T00:00:00Z") from exc


def _platform_skill_dir(skill_root: Path, platform: str) -> Path:
    """平台副本里放 20 个平级 Skill 的目录：<平台>/skills/。"""
    return _repository_root(skill_root) / platform / SKILLS_DIR


def _platform_skill_files(skill_root: Path, platform: str) -> dict[str, Path]:
    """返回该平台应当持有的 Skill 内容文件（相对 <平台>/skills/ 的路径 -> 唯一源路径）。"""
    layout = PLATFORM_LAYOUTS[platform]
    openai_metadata = f"{SKILL_NAME}/{OPENAI_METADATA_RELATIVE_PATH.as_posix()}"
    selected = {}
    for path in discover_source_files(skill_root):
        relative = _relative(path, skill_root)
        if relative == openai_metadata and not layout["with_openai_metadata"]:
            continue
        selected[relative] = path
    return selected


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def sync_platform_skills(skill_root: Path) -> None:
    """把 Skill 内容复制到各平台安装目录。

    复制而非渲染：各平台拿到的 Skill 内容必须逐字节相同。每个 Skill 整目录删掉重建
    （改成平级前嵌套在入口里的副本随之清掉），平台自己的安装文档和配置不受影响。
    """
    for platform in PLATFORM_NAMES:
        target_root = _platform_skill_dir(skill_root, platform)
        # skills/ 由发布流程独占：本插件的 Skill 整目录重建，改名或嵌套留下的目录一并删掉（附加 Skill 另行同步）
        if target_root.is_dir():
            for path in target_root.iterdir():
                if path.name not in EXTRA_SKILL_SOURCES:
                    _remove(path)
        for relative, source in _platform_skill_files(skill_root, platform).items():
            destination = target_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    sync_extra_skills(skill_root)


def _extra_skill_files(repository_root: Path, source: Path) -> dict[str, Path]:
    root = repository_root / source
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or not (
            path.suffix == ".md"
            or (relative.parts[0] == "scripts" and path.suffix == ".py")
            or (relative.parts[0] == "agents" and path.suffix in {".yaml", ".yml"})
        ):
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        files[path.relative_to(root).as_posix()] = path
    return files


def sync_extra_skills(skill_root: Path) -> None:
    repository_root = _repository_root(skill_root)
    for name in RETIRED_EXTRA_SKILLS:
        for platform in EXTRA_SKILL_PLATFORMS:
            shutil.rmtree(repository_root / platform / "skills" / name, ignore_errors=True)
    for name, source in EXTRA_SKILL_SOURCES.items():
        if not (repository_root / source).is_dir():
            # 附加 Skill 是可选资产：源目录不存在（如测试夹具）时跳过，不视为发布错误。
            continue
        for platform in EXTRA_SKILL_PLATFORMS:
            target = repository_root / platform / "skills" / name
            shutil.rmtree(target, ignore_errors=True)
            for relative, src in _extra_skill_files(repository_root, source).items():
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, destination)


def _extra_skill_markers(skill_root: Path) -> dict[str, Path]:
    repository_root = _repository_root(skill_root)
    return {
        name: repository_root / source / "SKILL.md"
        for name, source in EXTRA_SKILL_SOURCES.items()
        if (repository_root / source / "SKILL.md").is_file()
    }


def stamp_extra_skill_versions(skill_root: Path, version: str) -> dict[Path, str]:
    """把附加 Skill 的 skill-version 标记改成与主 Skill 相同的版本，返回改前内容供失败时还原。

    Hub 的版本闸门只按上报的版本号判定；附加 Skill 若保留独立标记，主 Skill 每次抬强制线后
    都会被拒（426）。统一版本后只需登记一次。 [任务:T-3724]
    """
    originals: dict[Path, str] = {}
    for name, skill_file in _extra_skill_markers(skill_root).items():
        original = skill_file.read_text(encoding="utf-8")
        updated, count = SKILL_VERSION_RE.subn(f"[skill-version:{version}]", original, count=1)
        if count != 1 or len(SKILL_VERSION_RE.findall(original)) != 1:
            raise ReleaseError(f"附加 Skill {name} 的 SKILL.md 必须且只能包含一个 skill-version 标记")
        originals[skill_file] = original
        if updated != original:
            skill_file.write_text(updated, encoding="utf-8")
    return originals


def check_extra_skill_versions(skill_root: Path, version: str) -> None:
    for name, skill_file in _extra_skill_markers(skill_root).items():
        markers = SKILL_VERSION_RE.findall(skill_file.read_text(encoding="utf-8"))
        if markers != [version]:
            raise ReleaseError(f"附加 Skill {name} 的 skill-version 必须等于主 Skill 的 {version}，当前 {markers}")


def check_extra_skills(skill_root: Path) -> None:
    repository_root = _repository_root(skill_root)
    for name in RETIRED_EXTRA_SKILLS:
        for platform in EXTRA_SKILL_PLATFORMS:
            if (repository_root / platform / "skills" / name).exists():
                raise ReleaseError(f"{platform} 仍带着已退役的附加 Skill {name}，请重新 release/sync")
    for name, source in EXTRA_SKILL_SOURCES.items():
        if not (repository_root / source).is_dir():
            continue
        expected = {
            relative: _sha256(src)
            for relative, src in _extra_skill_files(repository_root, source).items()
        }
        for platform in EXTRA_SKILL_PLATFORMS:
            target = repository_root / platform / "skills" / name
            for relative, digest in expected.items():
                copy = target / relative
                if not copy.is_file() or _sha256(copy) != digest:
                    raise ReleaseError(f"{platform} 的附加 Skill 副本已过期：{name}/{relative}，请重新 release/sync")


def check_platform_skills(skill_root: Path) -> None:
    """校验各平台的 Skill 副本与唯一源逐字节一致。"""
    for platform in PLATFORM_NAMES:
        target_root = _platform_skill_dir(skill_root, platform)
        known = {*ALL_SKILLS, UPGRADE_GUIDES_HOME, *EXTRA_SKILL_SOURCES, *RETIRED_EXTRA_SKILLS}
        leftovers = []
        if target_root.is_dir():
            leftovers = sorted(f"{SKILLS_DIR}/{path.name}" for path in target_root.iterdir() if path.name not in known)
        if leftovers:
            raise ReleaseError(f"{platform} 仍带着旧结构目录 {leftovers}，请执行 release")
        expected = {
            relative: _sha256(source)
            for relative, source in _platform_skill_files(skill_root, platform).items()
        }
        extra = sorted(
            path.relative_to(target_root).as_posix()
            for name in (*ALL_SKILLS, UPGRADE_GUIDES_HOME)
            if (target_root / name).is_dir()
            for path in (target_root / name).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.relative_to(target_root).as_posix() not in expected
        )
        if extra:
            raise ReleaseError(f"{platform} 仍带着旧结构目录或多余文件 {extra}，请执行 release")
        actual = {}
        for relative in expected:
            path = target_root / relative
            if not path.is_file():
                raise ReleaseError(f"{platform} 缺少 Skill 副本：{relative}")
            actual[relative] = _sha256(path)
        if expected != actual:
            stale = sorted(name for name, digest in expected.items() if actual.get(name) != digest)
            raise ReleaseError(f"{platform} 的 Skill 副本已过期，请执行 release：{stale}")
    check_extra_skills(skill_root)


def _upgrade_guides_module(skill_root: Path):
    """加载 Skill 自带的 upgrade_guides.py：发布检查与 Agent 用同一份解析与校验代码。"""
    script = _skills_root(skill_root) / UPGRADE_GUIDES_HOME / UPGRADE_GUIDES_SCRIPT
    spec = importlib.util.spec_from_file_location("skill_upgrade_guides", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_upgrade_guides(skill_root: Path) -> None:
    """升级指南的格式与关系；不合规不能发布。"""
    module = _upgrade_guides_module(skill_root)
    try:
        module.load_guides(_skills_root(skill_root) / UPGRADE_GUIDES_HOME / UPGRADE_GUIDES_DIR)
    except module.GuideError as error:
        lines = [f"{p['file']} {p['field']}（{p['code']}）：{p['message']}" for p in error.problems]
        raise ReleaseError("升级指南不合规：\n" + "\n".join(lines)) from None


def _git(repository_root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repository_root), *args], check=True, capture_output=True, text=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def released_guide_checksums(skill_root: Path) -> dict[str, dict[str, str]]:
    """各发布标签 skill/<版本> 上 skill-release.json 里的指南校验和：{路径: {版本: sha256}}。

    shortcut: 依赖本地已有发布标签；没有 git 或没 fetch 标签时查不到历史，按无已发布指南处理，
    流水线要拦就先 git fetch --tags。
    """
    repository_root = _repository_root(skill_root)
    tags = _git(repository_root, "tag", "--list", "skill/*") or ""
    released: dict[str, dict[str, str]] = {}
    for tag in tags.split():
        raw = _git(repository_root, "show", f"{tag}:{MANIFEST_RELATIVE_PATH.as_posix()}")
        try:
            checksums = json.loads(raw).get("checksums", {}) if raw else {}
        except (ValueError, AttributeError):
            continue
        for path, digest in checksums.items():
            # 拆成平级 Skill 之前的清单路径相对入口目录（upgrade-guides/D-x.md），之后相对 skills/
            if re.fullmatch(rf"{UPGRADE_GUIDES_DIR}/D-[0-9]+\.md", path):
                path = f"{UPGRADE_GUIDES_HOME}/{path}"
            if re.fullmatch(rf"{UPGRADE_GUIDES_HOME}/{UPGRADE_GUIDES_DIR}/D-[0-9]+\.md", path):
                released.setdefault(path, {})[tag.removeprefix("skill/")] = digest
    return released


def check_released_guides_frozen(skill_root: Path) -> None:
    """已随某版 Skill 发出的指南文件不能再改、删或改名；更正用新 D 的 replaces / withdraws。"""
    errors = []
    for path, versions in sorted(released_guide_checksums(skill_root).items()):
        current = _skills_root(skill_root) / path
        actual = _sha256(current) if current.is_file() else None
        for version, digest in sorted(versions.items()):
            if actual != digest:
                state = "已删除或改名" if actual is None else "内容已改"
                errors.append(f"{path} 已随 {version} 发布，{state}")
                break
    if errors:
        raise ReleaseError(
            "已发布的升级指南不能修改，要更正请新写一份指南用 replaces / withdraws：\n" + "\n".join(errors)
        )


def scaffold_min_required_version(skill_root: Path) -> str:
    markers = re.findall(r"<!-- scaffold-min-required-version:([^\s]+) -->", (skill_root / "SKILL.md").read_text(encoding="utf-8"))
    if len(markers) != 1 or not DATA_SKILL_VERSION_RE.fullmatch(markers[0]):
        raise ReleaseError("SKILL.md 必须包含唯一有效的 scaffold-min-required-version 标记")
    return markers[0]


def check_release(skill_root: Path) -> dict[str, Any]:
    """校验发布清单、Skill 内容校验和与各平台副本。"""
    skill_root = skill_root.resolve()
    validate_skill_metadata(skill_root)
    validate_platform_install_files(skill_root)
    validate_internal_references(skill_root)
    validate_skill_layout(skill_root)
    validate_upgrade_guides(skill_root)
    check_released_guides_frozen(skill_root)
    manifest = _load_manifest(skill_root)
    if set(manifest) != MANIFEST_KEYS:
        missing = sorted(MANIFEST_KEYS - set(manifest))
        extra = sorted(set(manifest) - MANIFEST_KEYS)
        raise ReleaseError(f"发布清单字段不一致：缺少={missing}，多出={extra}")
    if manifest["skill_name"] != SKILL_NAME:
        raise ReleaseError(f"skill_name 必须是 {SKILL_NAME!r}")
    skill_version = _validate_skill_version(manifest["version"])
    if manifest["scaffold_min_required_version"] != scaffold_min_required_version(skill_root):
        raise ReleaseError("发布清单的脚手架最低版本与 SKILL.md 不一致")
    package_version = manifest["package_version"]
    _validate_package_version(package_version)
    if manifest["mcp_endpoint"] != _configured_mcp_endpoint(skill_root):
        raise ReleaseError("skill-release.json.mcp_endpoint 与当前 Skill MCP 环境不一致")
    if _current_skill_version(skill_root) != skill_version:
        raise ReleaseError("SKILL.md 标记必须等于 skill-release.json.version")
    check_extra_skill_versions(skill_root, skill_version)
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
    validate_internal_references(skill_root)
    validate_skill_layout(skill_root)
    validate_upgrade_guides(skill_root)
    check_released_guides_frozen(skill_root)
    _validate_package_version(package_version)
    skill_version = _validate_skill_version(skill_version or _current_skill_version(skill_root))
    reason = reason.strip()
    if not reason or len(reason) > 1024:
        raise ReleaseError("update_reason 必须包含 1～1024 个字符")

    manifest_path = _manifest_path(skill_root)
    # qa / pre 渠道的版本号是「main 的 package version + -<渠道>.N」，由 build_env_branch.py 生成，不走 prod 的递增规则
    if manifest_path.exists() and release_channel() == "prod":
        current = _load_manifest(skill_root)
        current_package_version = current.get("package_version")
        _validate_package_version(current_package_version)
        if skill_version != current.get("version") and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以更新 Skill version")
        if package_version != current_package_version and not allow_package_bump:
            raise ReleaseError("只有 PROD 发布可以提升 package version")
        if allow_package_bump and package_version not in _valid_bumps(current_package_version):
            raise ReleaseError("PROD 发布必须把所有插件 package version 统一递增（patch+1、minor+1 或 major+1）")
        if allow_package_bump and not DATA_SKILL_VERSION_RE.fullmatch(skill_version):
            raise ReleaseError("PROD Skill version 必须使用 vYYYYMMDD-6位小写hex")

    stamp_extra_skill_versions(skill_root, skill_version)
    _bump_package_version(skill_root, package_version)
    sync_plugin_display_metadata(skill_root)
    sync_platform_skills(skill_root)

    files = discover_source_files(skill_root)
    manifest = {
        "scaffold_min_required_version": scaffold_min_required_version(skill_root),
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
    extra_originals = {path: path.read_text(encoding="utf-8") for path in _extra_skill_markers(skill_root).values()}
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
        for path, content in extra_originals.items():
            path.write_text(content, encoding="utf-8")
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
