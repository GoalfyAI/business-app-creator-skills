"""Codeup 环境部署入口的分支与环境路由、凭据前置校验与日志脱敏。"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("deploy_env", ROOT / "scripts" / "deploy_env.py")
deploy_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_env)

CREDS = {
    "GITHUB_PUSH_URL": "https://x-access-token:gh-secret@github.com/GoalfyAI/business-app-creator-skills.git",
    "CODEUP_PUSH_URL": "https://bot:cu-secret@codeup.aliyun.com/goalfyai/goalfyagent/scene-creator-skills.git",
    "SKILL_REGISTRY_SECRET": "s2s",
    "HUB_API_KEY": "hub-key",
    "HUB_OPERATOR_EMAIL": "qianzhipeng@goalfyai.com",
    "HUB_OPERATOR_ID": "10028",
}


@pytest.fixture
def steps(monkeypatch):
    for name, value in CREDS.items():
        monkeypatch.setenv(name, value)
    calls = []
    monkeypatch.setattr(deploy_env, "ensure_main_release",
                        lambda url: calls.append(("release",)) or ("v20261019-aaaaaa", "a" * 40, True))
    monkeypatch.setattr(deploy_env, "push_github_main",
                        lambda url, sha, version: calls.append(("github_main", sha, version)))

    def build_env(env, ref, build_number, skill_version, label, url):
        calls.append(("build_env", env, ref, skill_version, label))
        return Path("/tmp/out"), {"skill_version": skill_version or "v20261019-bbbbbb", "source_sha": "b" * 40}

    monkeypatch.setattr(deploy_env, "build_env", build_env)
    monkeypatch.setattr(deploy_env, "register",
                        lambda root, version, hub, secret: calls.append(("register", str(root), version, hub)))
    monkeypatch.setattr(deploy_env, "set_lines",
                        lambda version, hub, headers: calls.append(("lines", version, hub)))
    return calls


def test_prod_main_pushes_github_main_registers_and_raises_both_lines(steps):
    summary = deploy_env.deploy("prod", "main", 5)
    assert steps == [
        ("release",),
        ("github_main", "a" * 40, "v20261019-aaaaaa"),
        ("register", str(deploy_env.REPO_ROOT), "v20261019-aaaaaa", "https://goalfyhub.goalfyai.cn"),
        ("lines", "v20261019-aaaaaa", "https://goalfyhub.goalfyai.cn"),
    ]
    assert summary["lines"] == "raised"


@pytest.mark.parametrize("env,hub", [("qa", "https://goalfyhub.qa.goalfyai.cn"),
                                     ("pre", "https://goalfyhub.pre.goalfyai.cn")])
def test_env_main_builds_env_branch_with_main_version(steps, env, hub):
    deploy_env.deploy(env, "refs/heads/main", 5)
    assert steps == [
        ("release",),
        ("build_env", env, "a" * 40, "v20261019-aaaaaa", "main"),
        ("register", "/tmp/out", "v20261019-aaaaaa", hub),
        ("lines", "v20261019-aaaaaa", hub),
    ]


def test_feature_branch_registers_new_version_without_touching_lines(steps):
    summary = deploy_env.deploy("qa", "feat/x", 5)
    assert steps == [
        ("build_env", "qa", "HEAD", None, "feat/x"),
        ("register", "/tmp/out", "v20261019-bbbbbb", "https://goalfyhub.qa.goalfyai.cn"),
    ]
    assert summary["lines"] == "unchanged"


def test_prod_refuses_non_main_before_any_write(steps):
    with pytest.raises(deploy_env.DeployError, match="只部署 main"):
        deploy_env.deploy("prod", "feat/x", 5)
    assert steps == []


@pytest.mark.parametrize("missing", ["GITHUB_PUSH_URL", "SKILL_REGISTRY_SECRET", "CODEUP_PUSH_URL"])
def test_missing_credentials_fail_before_release(steps, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(deploy_env.DeployError, match=missing):
        deploy_env.deploy("qa", "main", 5)
    assert steps == []


def test_invalid_operator_fails_before_release(steps, monkeypatch):
    monkeypatch.setenv("HUB_OPERATOR_ID", "abc")
    with pytest.raises(deploy_env.DeployError, match="Hub 操作身份"):
        deploy_env.deploy("pre", "main", 5)
    assert steps == []


def test_unknown_env_is_rejected(steps):
    with pytest.raises(deploy_env.DeployError, match="SKILL_ENV"):
        deploy_env.deploy("staging", "main", 5)


def test_redact_removes_credentials_from_urls():
    text = "fatal: unable to access 'https://x-access-token:gh-secret@github.com/a.git'"
    assert "gh-secret" not in deploy_env.redact(text)
    assert "https://***@github.com/a.git" in deploy_env.redact(text)
