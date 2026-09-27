"""从 qa/main 生成 QA 版插件，并提交到 GitHub 的 business-qa 分支。 [任务:T-3784]

测试人员装 GitHub 的 business-qa 分支就是 QA 环境：MCP 指向 QA、密钥变量名是 BUSINESS_APP_CREATOR_QA_API_KEY、
升级链接指向 business-qa 分支。源码一律保持 prod 写法，环境相关的值只在这里替换，所以 main 与 qa/main
之间合并不会因为环境配置冲突。

流程：导出源码 → 替换环境相关的值 → 生成 QA 候选版本（Skill 版本随机、package version 为
main 版本加 -qa.N）→ 按 qa 渠道重建副本、压缩包与发布清单并 check → 提交到 business-qa 分支。
登记到 QA Hub 由 GitHub 上 business-qa 分支的 workflow（register-skill-qa.yml）完成。

用法：
  python3 scripts/build_qa_branch.py --out /tmp/qa-build              # 只生成，不推送
  python3 scripts/build_qa_branch.py --push --build-number 42          # 生成并推到 GitHub business-qa 分支
推送地址默认 git@github.com:GoalfyAI/business-app-creator-skills.git，可用环境变量 QA_BRANCH_PUSH_URL 覆盖
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
QA_BRANCH = "business-qa"
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


def qa_replacements(prod: dict[str, str], qa: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """按顺序替换的规则：环境值、升级链接、安装命令。"""
    return [
        (re.compile(re.escape(prod["mcp_endpoint"])), qa["mcp_endpoint"]),
        (re.compile(re.escape(prod["api_key_env"])), qa["api_key_env"]),
        (re.compile(re.escape(prod["api_keys_page"])), qa["api_keys_page"]),
        (re.compile(rf"raw\.githubusercontent\.com/{re.escape(PUBLIC_REPO)}/main/"), f"raw.githubusercontent.com/{PUBLIC_REPO}/{QA_BRANCH}/"),
        (re.compile(rf"github\.com/{re.escape(PUBLIC_REPO)}/raw/main/"), f"github.com/{PUBLIC_REPO}/raw/{QA_BRANCH}/"),
        (re.compile(rf"claude plugin marketplace add {re.escape(PUBLIC_REPO)}(?![\w#/.-])"),
         f'claude plugin marketplace add "https://github.com/{PUBLIC_REPO}.git#{QA_BRANCH}"'),
        (re.compile(rf"codex plugin marketplace add {re.escape(PUBLIC_REPO)}(?![\w#/.-])(?! --ref)"),
         f"codex plugin marketplace add {PUBLIC_REPO} --ref {QA_BRANCH}"),
        (re.compile(rf"git clone https://github\.com/{re.escape(PUBLIC_REPO)}\.git"),
         f"git clone -b {QA_BRANCH} https://github.com/{PUBLIC_REPO}.git"),
    ]


def apply_qa_values(root: Path, rules: list[tuple[re.Pattern[str], str]]) -> int:
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


def build(out: Path, ref: str, build_number: int) -> dict[str, str]:
    source_sha = export_source(ref, out)
    # 按文件路径加载导出副本里的脚本：保证与 qa/main 源码同版本，也不会拿到 sys.modules 里
    # 指向仓库本身的同名模块（否则 release 会改写仓库而不是导出目录）
    spec = importlib.util.spec_from_file_location(f"qa_build_bpp_{id(out)}", out / "scripts" / "build_platform_packages.py")
    bpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpp)
    previous_channel = os.environ.get(bpp.CHANNEL_ENV)
    try:
        return _build_with(bpp, out, source_sha, build_number)
    finally:
        if previous_channel is None:
            os.environ.pop(bpp.CHANNEL_ENV, None)
        else:
            os.environ[bpp.CHANNEL_ENV] = previous_channel


def _build_with(bpp, out: Path, source_sha: str, build_number: int) -> dict[str, str]:
    os.environ[bpp.CHANNEL_ENV] = "prod"
    skill_root = (out / bpp.SKILL_CONTENT_DIR).resolve()
    base_package = bpp._load_manifest(skill_root)["package_version"]
    bpp._validate_package_version(base_package)
    changed = apply_qa_values(out, qa_replacements(bpp.RELEASE_CHANNELS["prod"], bpp.RELEASE_CHANNELS["qa"]))

    os.environ[bpp.CHANNEL_ENV] = "qa"
    version = bpp.generate_prod_version()
    skill_file = skill_root / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    content, count = bpp.SKILL_VERSION_RE.subn(f"[skill-version:{version}]", content, count=1)
    if count != 1:
        raise bpp.ReleaseError("SKILL.md 必须且只能有一个 skill-version 标记")
    skill_file.write_text(content, encoding="utf-8")
    package = f"{base_package}-qa.{build_number}"
    reason = f"QA 候选版，来自 qa/main {source_sha[:9]}（build {build_number}）"
    bpp.release(skill_root, package, reason, skill_version=version, allow_package_bump=True)
    bpp.check_release(skill_root)
    return {"source_sha": source_sha, "skill_version": version, "package_version": package, "files_rewritten": str(changed)}


def push(out: Path, info: dict[str, str]) -> str:
    """把 out 的内容作为 business-qa 分支的一次新提交推送（保留 business-qa 分支历史，不强推）。"""
    push_url = os.environ.get("QA_BRANCH_PUSH_URL", DEFAULT_PUSH_URL)
    with tempfile.TemporaryDirectory(prefix="qa-branch-") as tmp:
        work = Path(tmp)
        run("git", "init", "-q", cwd=work)
        run("git", "remote", "add", "origin", push_url, cwd=work)
        exists = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", QA_BRANCH], cwd=work, capture_output=True).returncode == 0
        if exists:
            run("git", "fetch", "-q", "--depth=1", "origin", QA_BRANCH, cwd=work)
            run("git", "checkout", "-q", "-b", QA_BRANCH, "FETCH_HEAD", cwd=work)
        else:
            run("git", "checkout", "-q", "--orphan", QA_BRANCH, cwd=work)
        for child in work.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        shutil.copytree(out, work, dirs_exist_ok=True)
        run("git", "add", "-A", cwd=work)
        if not subprocess.run(["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True).stdout.strip():
            return "unchanged"
        message = (
            f"chore(skill): QA {info['skill_version']} ({info['package_version']})\n\n"
            f"source: qa/main {info['source_sha']}\n"
        )
        env = {**os.environ,
               "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME", "business-app-creator-qa-sync"),
               "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL", "qa-sync@goalfyai.com"),
               "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME", "business-app-creator-qa-sync"),
               "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL", "qa-sync@goalfyai.com")}
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=work, check=True, env=env)
        run("git", "push", "-q", "origin", f"HEAD:refs/heads/{QA_BRANCH}", cwd=work)
        return run("git", "rev-parse", "HEAD", cwd=work, capture=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD", help="源码提交（默认 HEAD，Flow 里就是 qa/main）")
    parser.add_argument("--out", type=Path, help="生成目录；不给则用临时目录")
    parser.add_argument("--build-number", type=int, default=int(os.environ.get("BUILD_NUMBER") or time.strftime("%Y%m%d%H%M")))
    parser.add_argument("--push", action="store_true", help="生成后提交到 GitHub 的 business-qa 分支")
    args = parser.parse_args()
    if args.build_number <= 0:
        parser.error("--build-number 必须是正整数")

    tmp = None if args.out else tempfile.TemporaryDirectory(prefix="qa-build-")
    out = args.out or Path(tmp.name)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        parser.error(f"生成目录必须为空：{out}")
    info = build(out, args.ref, args.build_number)
    print(f"QA 包已生成：{out}")
    for key, value in info.items():
        print(f"  {key}: {value}")
    if args.push:
        print(f"  business-qa 分支提交: {push(out, info)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
