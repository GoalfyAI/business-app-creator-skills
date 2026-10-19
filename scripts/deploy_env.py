"""Codeup 环境部署入口：qa / pre / prod 三条流水线各自调用，GitHub 完全跟随 Codeup 的部署。

部署 main：
  1. main 最新提交上已有 skill/<版本> tag 就沿用该版本；否则自动发版（scripts/release-skill.sh），
     把发布提交与 tag 推回 Codeup main。同一份 main 先后部署到三个环境用的是同一个版本。
  2. prod：把这次提交与 tag 推到 GitHub main；qa / pre：按环境渠道生成安装物料，推到 GitHub business-qa / business-pre。
  3. 登记到该环境 Hub，并把该环境的强制线与建议线设为这个版本（按登记 ID 只升不降）。
部署其他分支（只允许 qa / pre）：
  按环境渠道生成带新版本的安装物料，推到该环境 GitHub 分支并登记，不动版本线。

环境变量（Flow 加密变量）：
  SKILL_ENV               qa / pre / prod（每条流水线固定）
  CODEUP_PUSH_URL         带凭据的 Codeup 仓库 https 地址，部署 main 时推发布提交与 tag
  GITHUB_PUSH_URL         带凭据的 GitHub 仓库 https 地址，推 main 或环境分支
  SKILL_REGISTRY_SECRET   该环境 Hub 的 Skill 登记签名密钥（scene_skill_release.s2s_secret）
  HUB_API_KEY / HUB_OPERATOR_EMAIL / HUB_OPERATOR_ID / HUB_APP_ID（可省，默认 goalfymax）  部署 main 时设版本线
用法：python3 scripts/deploy_env.py --env qa --branch "${CI_COMMIT_REF_NAME}" --build-number "${BUILD_NUMBER}"
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import runpy
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVS = {
    "qa": {"hub": "https://goalfyhub.qa.goalfyai.cn", "github_branch": "business-qa"},
    "pre": {"hub": "https://goalfyhub.pre.goalfyai.cn", "github_branch": "business-pre"},
    "prod": {"hub": "https://goalfyhub.goalfyai.cn", "github_branch": "main"},
}
REGISTER_PATH = "/api/internal/workflow/scene-skill-versions/releases/register"
RELEASE_COMMIT_PREFIX = "chore(skill): release "
BOT_IDENTITY = {
    "GIT_AUTHOR_NAME": "business-app-creator-release",
    "GIT_AUTHOR_EMAIL": "skill-release@goalfyai.com",
    "GIT_COMMITTER_NAME": "business-app-creator-release",
    "GIT_COMMITTER_EMAIL": "skill-release@goalfyai.com",
}
CREDENTIAL_RE = re.compile(r"://[^/@\s]+@")


class DeployError(RuntimeError):
    """部署前置条件不满足或某一步失败；信息里不含凭据。"""


def redact(text: str) -> str:
    return CREDENTIAL_RE.sub("://***@", text)


def git(*args: str, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, env=env, check=False)
    if result.returncode != 0:
        command = redact(" ".join(args))
        raise DeployError(f"git {command} 失败：{redact((result.stderr or result.stdout).strip())}")
    return result.stdout.strip()


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise DeployError(f"缺少环境变量 {name}")
    return value


def manifest_version(root: Path) -> str:
    return json.loads((root / "skill-release.json").read_text(encoding="utf-8"))["version"]


def release_notes(head: str) -> str:
    """上一个 skill/ tag 之后的提交标题，作为本次发版说明。"""
    try:
        last = git("describe", "--tags", "--abbrev=0", "--match", "skill/*", head)
        span = f"{last}..{head}"
    except DeployError:
        span = head
    subjects = [line for line in git("log", "--no-merges", "--format=%s", span).splitlines()
                if line.strip() and not line.startswith(RELEASE_COMMIT_PREFIX)]
    notes = "；".join(subjects) or f"Codeup 部署 main {head[:9]}"
    return notes if len(notes) <= 1000 else notes[:999] + "…"


def ensure_main_release(codeup_url: str) -> tuple[str, str, bool]:
    """返回（版本, 提交, 是否本次新发版）。只在 main 最新提交上发版，避免推回时覆盖他人提交。"""
    if git("rev-parse", "--is-shallow-repository") == "true":
        git("fetch", "-q", "--unshallow", codeup_url)
    git("fetch", "-q", "--tags", codeup_url, "+refs/heads/main:refs/remotes/codeup/main")
    head = git("rev-parse", "HEAD")
    if head != git("rev-parse", "refs/remotes/codeup/main"):
        raise DeployError("本次检出的不是 Codeup main 最新提交，请重新运行流水线")
    version = manifest_version(REPO_ROOT)
    if f"skill/{version}" in git("tag", "--points-at", head).splitlines():
        print(f"main {head[:9]} 已是发布版本 {version}，沿用")
        return version, head, False
    notes = release_notes(head)
    git("checkout", "-q", "-B", "main", head)
    env = {**os.environ, **BOT_IDENTITY}
    result = subprocess.run(["bash", "scripts/release-skill.sh", notes], cwd=REPO_ROOT, text=True, capture_output=True, env=env, check=False)
    print(redact(result.stdout))
    if result.returncode != 0:
        raise DeployError(f"自动发版失败：{redact(result.stderr.strip())}")
    version = manifest_version(REPO_ROOT)
    sha = git("rev-parse", "HEAD")
    git("push", "--atomic", codeup_url, "HEAD:refs/heads/main", f"refs/tags/skill/{version}")
    print(f"已发版 {version}（{sha[:9]}），发布提交与 tag 已推回 Codeup main")
    return version, sha, True


def push_github_main(github_url: str, sha: str, version: str) -> None:
    git("push", "--atomic", github_url, f"{sha}:refs/heads/main", f"refs/tags/skill/{version}")
    print(f"GitHub main 与 tag skill/{version} 已同步到 {sha[:9]}")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_env(env: str, ref: str, build_number: int, skill_version: str | None, label: str,
              github_url: str) -> tuple[Path, dict[str, str]]:
    builder = _load("deploy_build_env_branch", REPO_ROOT / "scripts" / "build_env_branch.py")
    out = Path(tempfile.mkdtemp(prefix=f"{env}-deploy-"))
    info = builder.build(out, ref, build_number, env=env, skill_version=skill_version, source_label=label)
    os.environ["ENV_BRANCH_PUSH_URL"] = github_url
    commit = builder.push(out, info)
    print(f"GitHub {info['branch']} 已同步：{commit}（{info['skill_version']} / {info['package_version']}）")
    return out, info


def register(root: Path, version: str, hub: str, secret: str) -> None:
    os.environ["SCENE_SKILL_RELEASE_REGISTRY_TARGETS"] = f"{hub}{REGISTER_PATH}|{secret}"
    manifest = json.loads((root / "skill-release.json").read_text(encoding="utf-8"))
    os.environ["SCENE_SKILL_RELEASE_NOTES"] = manifest.get("update_reason", "")
    module = runpy.run_path(str(root / "scripts" / "register-skill-release.py"))
    module["register_release"](version)


def hub_headers() -> dict[str, str]:
    module = runpy.run_path(str(REPO_ROOT / "scripts" / "raise_skill_recommended.py"))
    return module["operator_headers"]({
        "api_key": os.environ.get("HUB_API_KEY", ""),
        "app_id": os.environ.get("HUB_APP_ID") or "goalfymax",
        "operator_email": os.environ.get("HUB_OPERATOR_EMAIL", ""),
        "operator_id": os.environ.get("HUB_OPERATOR_ID", ""),
    })


def set_lines(version: str, hub: str, headers: dict[str, str]) -> None:
    module = runpy.run_path(str(REPO_ROOT / "scripts" / "raise_skill_recommended.py"))
    module["raise_lines"](version, module["hub_url"](hub), headers, required=True)


def deploy(env: str, branch: str, build_number: int) -> dict[str, str]:
    if env not in ENVS:
        raise DeployError(f"SKILL_ENV 只能是 {sorted(ENVS)}")
    branch = branch.removeprefix("refs/heads/").strip()
    if not branch:
        raise DeployError("缺少部署分支")
    if env == "prod" and branch != "main":
        raise DeployError("生产环境只部署 main：GitHub main 是已安装用户的升级源")
    hub = ENVS[env]["hub"]
    # 先校验全部凭据，任何一项缺失都在写入前失败
    github_url = required_env("GITHUB_PUSH_URL")
    secret = required_env("SKILL_REGISTRY_SECRET")
    if branch == "main":
        codeup_url = required_env("CODEUP_PUSH_URL")
        try:
            headers = hub_headers()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise DeployError(f"Hub 操作身份配置无效：{exc}") from None
        version, sha, released = ensure_main_release(codeup_url)
        if env == "prod":
            push_github_main(github_url, sha, version)
            root = REPO_ROOT
        else:
            root, _ = build_env(env, sha, build_number, version, "main", github_url)
        register(root, version, hub, secret)
        set_lines(version, hub, headers)
        return {"env": env, "branch": branch, "version": version, "source_sha": sha,
                "released": str(released), "lines": "raised"}
    root, info = build_env(env, "HEAD", build_number, None, branch, github_url)
    register(root, info["skill_version"], hub, secret)
    return {"env": env, "branch": branch, "version": info["skill_version"], "source_sha": info["source_sha"],
            "released": "False", "lines": "unchanged"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default=os.environ.get("SKILL_ENV", ""), help="qa / pre / prod，默认读 SKILL_ENV")
    parser.add_argument("--branch", default=os.environ.get("CI_COMMIT_REF_NAME", ""), help="部署的 Codeup 分支")
    parser.add_argument("--build-number", type=int, default=int(os.environ.get("BUILD_NUMBER") or 0))
    args = parser.parse_args()
    if args.build_number <= 0:
        parser.error("--build-number 必须是正整数（Flow 里用 BUILD_NUMBER）")
    try:
        summary = deploy(args.env.strip(), args.branch, args.build_number)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        # 登记与抬线的异常只带目标地址与状态，不含密钥；仍统一去掉地址里的凭据再输出
        print(f"部署失败：{type(exc).__name__}: {redact(str(exc))}")
        return 1
    print("部署完成：" + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
