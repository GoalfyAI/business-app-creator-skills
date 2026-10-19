"""按环境生成 QA / PRE 版插件，并提交到 GitHub 的 business-qa / business-pre 分支。 [任务:T-3784]

测试人员装 GitHub 的 business-<环境> 分支就是对应环境：MCP 指向该环境、密钥变量名是
BUSINESS_APP_CREATOR_<环境>_API_KEY、升级链接指向该分支。源码一律保持 prod 写法，环境相关的值只在这里替换，
所以 main 与其他分支之间合并不会因为环境配置冲突。

流程：导出源码 → 替换环境相关的值 → 写入 Skill 版本（部署 main 时沿用 main 的发布版本，其他分支随机生成）
→ package version 为源码版本加 -<环境>.N → 按该环境渠道重建副本、压缩包与发布清单并 check → 提交到环境分支。
登记与抬线由 scripts/deploy_env.py 在 Codeup 流水线里完成。

用法：
  python3 scripts/build_env_branch.py --env qa --out /tmp/qa-build             # 只生成，不推送
  python3 scripts/build_env_branch.py --env pre --push --build-number 42       # 生成并推到 GitHub business-pre 分支
推送地址默认 git@github.com:GoalfyAI/business-app-creator-skills.git，可用环境变量 ENV_BRANCH_PUSH_URL 覆盖
（例如 Flow 里用带令牌的 https 地址）。
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_BRANCHES = {"qa": "business-qa", "pre": "business-pre"}
DEFAULT_PUSH_URL = "git@github.com:GoalfyAI/business-app-creator-skills.git"
PUBLIC_REPO = "GoalfyAI/business-app-creator-skills"
# 只改安装物料与文档；脚本、测试、CI 配置保持原样
TEXT_ROOTS = ("skills", "claude-code", "codex", "manus", "generic", "docs", ".claude-plugin", ".agents", "README.md")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt"}


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ""


def export_source(ref: str, out: Path) -> str:
    """把 ref 的源码导出到 out，返回完整提交号。"""
    sha = run("git", "rev-parse", f"{ref}^{{commit}}", cwd=REPO_ROOT, capture=True)
    archive = subprocess.run(["git", "archive", "--format=tar", sha], cwd=REPO_ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out, filter="data")
    return sha


def env_replacements(prod: dict[str, str], target: dict[str, str], branch: str) -> list[tuple[re.Pattern[str], str]]:
    """按顺序替换的规则：环境值、升级链接、安装命令。"""
    return [
        (re.compile(re.escape(prod["mcp_endpoint"])), target["mcp_endpoint"]),
        (re.compile(re.escape(prod["api_key_env"])), target["api_key_env"]),
        (re.compile(re.escape(prod["api_keys_page"])), target["api_keys_page"]),
        (re.compile(rf"raw\.githubusercontent\.com/{re.escape(PUBLIC_REPO)}/main/"), f"raw.githubusercontent.com/{PUBLIC_REPO}/{branch}/"),
        (re.compile(rf"github\.com/{re.escape(PUBLIC_REPO)}/raw/main/"), f"github.com/{PUBLIC_REPO}/raw/{branch}/"),
        (re.compile(rf"claude plugin marketplace add {re.escape(PUBLIC_REPO)}(?![\w#/.-])"),
         f'claude plugin marketplace add "https://github.com/{PUBLIC_REPO}.git#{branch}"'),
        (re.compile(rf"codex plugin marketplace add {re.escape(PUBLIC_REPO)}(?![\w#/.-])(?! --ref)"),
         f"codex plugin marketplace add {PUBLIC_REPO} --ref {branch}"),
        (re.compile(rf"git clone https://github\.com/{re.escape(PUBLIC_REPO)}\.git"),
         f"git clone -b {branch} https://github.com/{PUBLIC_REPO}.git"),
    ]


def apply_env_values(root: Path, rules: list[tuple[re.Pattern[str], str]]) -> int:
    changed = 0
    for name in TEXT_ROOTS:
        base = root / name
        paths = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
        for path in paths:
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            updated = text
            for pattern, replacement in rules:
                updated = pattern.sub(replacement, updated)
            if updated != text:
                path.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def build(out: Path, ref: str, build_number: int, *, env: str = "qa", skill_version: str | None = None,
          source_label: str | None = None) -> dict[str, str]:
    if env not in ENV_BRANCHES:
        raise ValueError(f"环境只能是 {sorted(ENV_BRANCHES)}")
    source_sha = export_source(ref, out)
    # 按文件路径加载导出副本里的脚本：保证与源码同版本，也不会拿到 sys.modules 里
    # 指向仓库本身的同名模块（否则 release 会改写仓库而不是导出目录）
    spec = importlib.util.spec_from_file_location(f"env_build_bpp_{id(out)}", out / "scripts" / "build_platform_packages.py")
    bpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpp)
    previous_channel = os.environ.get(bpp.CHANNEL_ENV)
    try:
        return _build_with(bpp, out, env, source_sha, build_number, skill_version, source_label or ref)
    finally:
        if previous_channel is None:
            os.environ.pop(bpp.CHANNEL_ENV, None)
        else:
            os.environ[bpp.CHANNEL_ENV] = previous_channel


def _build_with(bpp, out: Path, env: str, source_sha: str, build_number: int, skill_version: str | None,
                source_label: str) -> dict[str, str]:
    os.environ[bpp.CHANNEL_ENV] = "prod"
    skill_root = (out / bpp.SKILL_CONTENT_DIR).resolve()
    base_package = bpp._load_manifest(skill_root)["package_version"]
    bpp._validate_package_version(base_package)
    branch = ENV_BRANCHES[env]
    changed = apply_env_values(out, env_replacements(bpp.RELEASE_CHANNELS["prod"], bpp.RELEASE_CHANNELS[env], branch))

    os.environ[bpp.CHANNEL_ENV] = env
    version = bpp._validate_skill_version(skill_version) if skill_version else bpp.generate_prod_version()
    skill_file = skill_root / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    content, count = bpp.SKILL_VERSION_RE.subn(f"[skill-version:{version}]", content, count=1)
    if count != 1:
        raise bpp.ReleaseError("SKILL.md 必须且只能有一个 skill-version 标记")
    skill_file.write_text(content, encoding="utf-8")
    package = f"{base_package}-{env}.{build_number}"
    reason = f"{env.upper()} 版，来自 {source_label} {source_sha[:9]}（build {build_number}）"
    bpp.release(skill_root, package, reason, skill_version=version, allow_package_bump=True)
    bpp.check_release(skill_root)
    return {"env": env, "branch": branch, "source_sha": source_sha, "skill_version": version,
            "package_version": package, "files_rewritten": str(changed)}


def push(out: Path, info: dict[str, str]) -> str:
    """把 out 的内容作为环境分支的一次新提交推送（保留分支历史，不强推）。"""
    push_url = os.environ.get("ENV_BRANCH_PUSH_URL", DEFAULT_PUSH_URL)
    branch = info["branch"]
    with tempfile.TemporaryDirectory(prefix="env-branch-") as tmp:
        work = Path(tmp)
        run("git", "init", "-q", cwd=work)
        run("git", "remote", "add", "origin", push_url, cwd=work)
        exists = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch], cwd=work, capture_output=True, check=False).returncode == 0
        if exists:
            run("git", "fetch", "-q", "--depth=1", "origin", branch, cwd=work)
            run("git", "checkout", "-q", "-b", branch, "FETCH_HEAD", cwd=work)
        else:
            run("git", "checkout", "-q", "--orphan", branch, cwd=work)
        for child in work.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        shutil.copytree(out, work, dirs_exist_ok=True)
        run("git", "add", "-A", cwd=work)
        if not subprocess.run(["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True, check=True).stdout.strip():
            return "unchanged"
        message = (
            f"chore(skill): {info['env'].upper()} {info['skill_version']} ({info['package_version']})\n\n"
            f"source: {info['source_sha']}\n"
        )
        bot = f"business-app-creator-{info['env']}-sync"
        env = {**os.environ,
               "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME", bot),
               "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL", f"{info['env']}-sync@goalfyai.com"),
               "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME", bot),
               "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL", f"{info['env']}-sync@goalfyai.com")}
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=work, check=True, env=env)
        run("git", "push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=work)
        return run("git", "rev-parse", "HEAD", cwd=work, capture=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", choices=sorted(ENV_BRANCHES), required=True, help="目标环境")
    parser.add_argument("--ref", default="HEAD", help="源码提交（默认 HEAD）")
    parser.add_argument("--out", type=Path, help="生成目录；不给则用临时目录")
    parser.add_argument("--build-number", type=int, default=int(os.environ.get("BUILD_NUMBER") or time.strftime("%Y%m%d%H%M")))
    parser.add_argument("--skill-version", help="沿用的 Skill 版本（部署 main 时传 main 的发布版本）；不给则随机生成")
    parser.add_argument("--push", action="store_true", help="生成后提交到 GitHub 的环境分支")
    args = parser.parse_args()
    if args.build_number <= 0:
        parser.error("--build-number 必须是正整数")

    tmp = None if args.out else tempfile.TemporaryDirectory(prefix=f"{args.env}-build-")
    out = args.out or Path(tmp.name)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        parser.error(f"生成目录必须为空：{out}")
    info = build(out, args.ref, args.build_number, env=args.env, skill_version=args.skill_version)
    print(f"{args.env.upper()} 包已生成：{out}")
    for key, value in info.items():
        print(f"  {key}: {value}")
    if args.push:
        print(f"  {info['branch']} 分支提交: {push(out, info)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
