"""GitHub main 发布快照：只追加、按 Codeup 来源提交的先后拒绝回退（FB-1544，!107 评审 P2）。"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """Codeup 工作区上 v1 → v2 两个发布提交，GitHub 是空的裸仓库。"""
    for key, value in IDENTITY.items():
        monkeypatch.setenv(key, value)
    codeup = tmp_path / "codeup"
    codeup.mkdir()
    git("init", "-q", "-b", "main", cwd=codeup)
    releases = {}
    for version in ("v1", "v2"):
        (codeup / "skill-release.json").write_text(f'{{"version": "{version}"}}\n', encoding="utf-8")
        git("add", "-A", cwd=codeup)
        git("commit", "-q", "-m", f"chore(skill): release {version}", cwd=codeup)
        releases[version] = git("rev-parse", "HEAD", cwd=codeup)
    github = tmp_path / "github.git"
    git("init", "-q", "--bare", str(github), cwd=tmp_path)
    spec = importlib.util.spec_from_file_location(f"deploy_env_{tmp_path.name}", ROOT / "scripts" / "deploy_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", codeup)
    return module, codeup, github, releases


def refs(github: Path) -> dict[str, str]:
    out = git("for-each-ref", "--format=%(refname) %(objectname)", cwd=github)
    return dict(line.split() for line in out.splitlines())


def test_snapshot_appends_forward(repos):
    deploy, codeup, github, rel = repos
    first = deploy.push_github_main(str(github), rel["v1"], "v1")
    second = deploy.push_github_main(str(github), rel["v2"], "v2")
    assert git("rev-parse", f"{second}^", cwd=github) == first
    assert git("rev-parse", f"{second}^{{tree}}", cwd=github) == git("rev-parse", f"{rel['v2']}^{{tree}}", cwd=codeup)
    assert refs(github)["refs/tags/skill/v2"] == second == refs(github)["refs/heads/main"]
    # GitHub 不含 Codeup 的提交
    assert subprocess.run(["git", "cat-file", "-e", rel["v1"]], cwd=github).returncode != 0


def test_old_release_without_tag_is_rejected_after_newer(repos):
    """新版已发布、旧版 tag 缺失，再发旧版必须拒绝且 main/tag 不变。"""
    deploy, _, github, rel = repos
    deploy.push_github_main(str(github), rel["v2"], "v2")
    before = refs(github)
    assert "refs/tags/skill/v1" not in before
    with pytest.raises(deploy.DeployError, match="退回旧版"):
        deploy.push_github_main(str(github), rel["v1"], "v1")
    assert refs(github) == before


def test_same_release_rerun_is_reused(repos):
    deploy, _, github, rel = repos
    snapshot = deploy.push_github_main(str(github), rel["v2"], "v2")
    assert deploy.push_github_main(str(github), rel["v2"], "v2") == snapshot
    assert refs(github)["refs/heads/main"] == snapshot


def test_legacy_main_is_codeup_commit(repos):
    """重建前 GitHub main 直接是 Codeup 提交：新版可以追加，旧版拒绝。"""
    deploy, codeup, github, rel = repos
    git("push", "-q", str(github), f"{rel['v1']}:refs/heads/main", cwd=codeup)
    snapshot = deploy.push_github_main(str(github), rel["v2"], "v2")
    assert git("rev-parse", f"{snapshot}^", cwd=github) == rel["v1"]

    git("push", "-q", "-f", str(github), f"{rel['v2']}:refs/heads/main", ":refs/tags/skill/v2", cwd=codeup)
    before = refs(github)
    with pytest.raises(deploy.DeployError, match="退回旧版"):
        deploy.push_github_main(str(github), rel["v1"], "v1")
    assert refs(github) == before


def test_unknown_source_is_rejected(repos, tmp_path):
    """GitHub main 的来源不在 Codeup 历史里时无法判断新旧，拒绝而不是盲目追加。"""
    deploy, _, github, rel = repos
    other = tmp_path / "other"
    other.mkdir()
    git("init", "-q", "-b", "main", cwd=other)
    git("commit", "-q", "--allow-empty", "-m", "unrelated", cwd=other)
    git("push", "-q", str(github), "HEAD:refs/heads/main", cwd=other)
    before = refs(github)
    with pytest.raises(deploy.DeployError, match="无法判断新旧"):
        deploy.push_github_main(str(github), rel["v2"], "v2")
    assert refs(github) == before
