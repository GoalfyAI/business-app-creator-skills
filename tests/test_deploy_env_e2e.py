"""用本地裸仓库代替 Codeup / GitHub、本机 HTTP 服务代替 Hub，完整跑三种部署。"""

import hashlib
import hmac
import importlib.util
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def hub():
    state = {"releases": [], "policy": {"min_required_version": "", "min_recommended_version": "",
                                         "emergency_bypass": False}, "puts": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            signature = hmac.new(b"s2s", self.headers["X-Goalfy-Timestamp"].encode() + b"." + body,
                                 hashlib.sha256).hexdigest()
            assert hmac.compare_digest(signature, self.headers["X-Goalfy-Signature"])
            version = json.loads(body)["version_string"]
            if not any(row["version_string"] == version for row in state["releases"]):
                state["releases"].append({"id": len(state["releases"]) + 1, "version_string": version})
            self.respond({"created": True})

        def do_GET(self):
            self.respond({"code": 0, "data": {"releases": state["releases"], "policy": state["policy"]}})

        def do_PUT(self):
            assert self.headers["X-API-Key"] == "hub-key"
            state["policy"].update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            state["puts"] += 1
            self.respond({"code": 0})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    server.server_close()


def checkout(tmp_path: Path, codeup: Path, name: str, branch: str) -> Path:
    """模拟 Flow：每次运行全新检出所选分支。"""
    work = tmp_path / name
    git("clone", "-q", "-b", branch, str(codeup), str(work), cwd=tmp_path)
    return work


def load_deploy(work: Path, hub_url: str):
    spec = importlib.util.spec_from_file_location(f"deploy_env_{work.name}", work / "scripts" / "deploy_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for cfg in module.ENVS.values():
        cfg["hub"] = hub_url
    return module


def test_main_then_prod_then_feature(tmp_path, hub, monkeypatch):
    hub_url, state = hub
    codeup = tmp_path / "codeup.git"
    github = tmp_path / "github.git"
    git("clone", "-q", "--bare", str(ROOT), str(codeup), cwd=tmp_path)
    head = git("rev-parse", "HEAD", cwd=ROOT)
    git("update-ref", "refs/heads/main", head, cwd=codeup)
    git("clone", "-q", "--bare", str(codeup), str(github), cwd=tmp_path)
    monkeypatch.chdir(tmp_path)
    for key, value in {**IDENTITY, "GITHUB_PUSH_URL": str(github), "CODEUP_PUSH_URL": str(codeup),
                       "SKILL_REGISTRY_SECRET": "s2s", "HUB_API_KEY": "hub-key",
                       "HUB_OPERATOR_EMAIL": "ops@goalfyai.com", "HUB_OPERATOR_ID": "1"}.items():
        monkeypatch.setenv(key, value)

    # 1. QA 部署 main：HEAD 没有发布 tag → 自动发版并推回 Codeup，business-qa 用同一版本
    qa = checkout(tmp_path, codeup, "qa-main", "main")
    summary = load_deploy(qa, hub_url).deploy("qa", "main", 3)
    version = summary["version"]
    assert summary["released"] == "True"
    codeup_main = git("rev-parse", "refs/heads/main", cwd=codeup)
    assert codeup_main != head and git("rev-parse", f"refs/tags/skill/{version}^{{commit}}", cwd=codeup) == codeup_main
    assert git("log", "-1", "--format=%s", "main", cwd=codeup) == f"chore(skill): release {version}"
    qa_manifest = json.loads(git("show", "business-qa:skill-release.json", cwd=github))
    assert qa_manifest["version"] == version and qa_manifest["package_version"].endswith("-qa.3")
    assert state["policy"]["min_required_version"] == state["policy"]["min_recommended_version"] == version

    # 2. prod 部署同一份 main：沿用版本，不再发版；GitHub main 与 tag 跟上 Codeup
    prod = checkout(tmp_path, codeup, "prod-main", "main")
    summary = load_deploy(prod, hub_url).deploy("prod", "main", 4)
    assert summary == {**summary, "version": version, "released": "False", "source_sha": codeup_main}
    assert git("rev-parse", "refs/heads/main", cwd=github) == codeup_main
    assert git("rev-parse", f"refs/tags/skill/{version}^{{commit}}", cwd=github) == codeup_main
    puts = state["puts"]

    # 3. QA 部署功能分支：新版本登记、business-qa 前进，版本线不动
    git("push", "-q", str(codeup), f"{codeup_main}:refs/heads/feat/x", cwd=prod)
    feature = checkout(tmp_path, codeup, "qa-feat", "feat/x")
    summary = load_deploy(feature, hub_url).deploy("qa", "feat/x", 5)
    assert summary["lines"] == "unchanged" and summary["version"] != version
    assert any(row["version_string"] == summary["version"] for row in state["releases"])
    assert state["puts"] == puts
    assert state["policy"]["min_required_version"] == version
    assert json.loads(git("show", "business-qa:skill-release.json", cwd=github))["version"] == summary["version"]
    assert git("rev-parse", "refs/heads/main", cwd=codeup) == codeup_main
