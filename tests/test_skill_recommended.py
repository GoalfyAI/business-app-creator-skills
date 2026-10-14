"""发布建议线的顺序、字段保留、故障恢复与真实 CLI 请求回归。 [任务:T-4466]"""

import copy
import hashlib
import hmac
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
OLD = "v20990101-ffffff"
NEW = "v20000101-000000"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recommend = load_script("raise_skill_recommended.py")
release = load_script("register-skill-release.py")


@pytest.fixture
def policy_state(monkeypatch):
    state = {
        "releases": [{"id": 10, "version_string": OLD}, {"id": 30, "version_string": NEW}],
        "policy": {
            "min_required_version": OLD,
            "min_recommended_version": OLD,
            "emergency_bypass": True,
        },
    }
    calls = []

    def request(method, url, headers, body=None):
        calls.append((method, copy.deepcopy(body)))
        if method == "PUT":
            state["policy"].update(body)
        return {"data": copy.deepcopy(state)}

    monkeypatch.setattr(recommend, "request", request)
    return state, calls


@pytest.mark.parametrize("initial", [OLD, ""])
def test_promotes_by_registry_id_and_preserves_other_fields(policy_state, initial):
    state, calls = policy_state
    state["policy"]["min_recommended_version"] = initial
    recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert state["policy"] == {
        "min_required_version": OLD,
        "min_recommended_version": NEW,
        "emergency_bypass": True,
    }
    assert [method for method, _ in calls] == ["GET", "PUT", "GET"]


def test_null_policy_initializes_without_existing_forced_floor(monkeypatch):
    """Hub 的 null 策略表示尚无策略行，首次设置建议线时没有强制线需要覆盖。"""
    state = {"releases": [{"id": 30, "version_string": NEW}], "policy": None}

    def request(method, url, headers, body=None):
        if method == "PUT":
            state["policy"] = body
        return {"data": copy.deepcopy(state)}

    monkeypatch.setattr(recommend, "request", request)
    recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert state["policy"] == {
        "min_required_version": "", "min_recommended_version": NEW, "emergency_bypass": False,
    }


@pytest.mark.parametrize("invalid", ["missing_policy", "missing_required", "missing_bypass",
                                     "missing_recommended", "null_required", "null_recommended",
                                     "string_bypass", "integer_bypass"])
def test_incomplete_policy_never_defaults_and_overwrites_unknown_fields(policy_state, invalid):
    state, calls = policy_state
    field = invalid.split("_", 1)[1]
    key = {"required": "min_required_version", "recommended": "min_recommended_version",
           "bypass": "emergency_bypass"}.get(field)
    if invalid == "missing_policy":
        del state["policy"]
    elif invalid.startswith("missing_"):
        del state["policy"][key]
    else:
        state["policy"][key] = {"null": None, "string": "false", "integer": 0}[
            invalid.split("_", 1)[0]]
    with pytest.raises(RuntimeError, match="策略"):
        recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert calls == [("GET", None)]


@pytest.mark.parametrize("target", [OLD, NEW])
def test_same_or_older_release_does_not_write(policy_state, target):
    state, calls = policy_state
    state["policy"]["min_recommended_version"] = NEW
    recommend.raise_recommended(target, "https://hub.invalid", {})
    assert calls == [("GET", None)]
    assert state["policy"]["min_recommended_version"] == NEW


@pytest.mark.parametrize("invalid", [None, 0, -1, "30", True])
def test_invalid_registry_id_fails_before_write(policy_state, invalid):
    state, calls = policy_state
    state["releases"][1]["id"] = invalid
    with pytest.raises(RuntimeError, match="ID"):
        recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert calls == [("GET", None)]


@pytest.mark.parametrize("missing", ["target", "current"])
def test_unregistered_reference_fails_before_write(policy_state, missing):
    state, calls = policy_state
    if missing == "current":
        state["policy"]["min_recommended_version"] = "missing"
    with pytest.raises(RuntimeError, match="登记"):
        recommend.raise_recommended("missing" if missing == "target" else NEW, "https://hub.invalid", {})
    assert calls == [("GET", None)]


@pytest.mark.parametrize("field,value", [
    ("min_required_version", "unexpected"),
    ("emergency_bypass", False),
    ("min_recommended_version", OLD),
])
def test_readback_must_preserve_all_policy_fields(monkeypatch, field, value):
    before = {"releases": [{"id": 30, "version_string": NEW}], "policy": {
        "min_required_version": "", "min_recommended_version": "", "emergency_bypass": True,
    }}
    count = 0

    def request(method, url, headers, body=None):
        nonlocal count
        count += 1
        if method == "PUT":
            before["policy"].update(body)
            before["policy"][field] = value
        return {"data": copy.deepcopy(before)}

    monkeypatch.setattr(recommend, "request", request)
    with pytest.raises(RuntimeError, match="读回"):
        recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert count == 3


def test_unknown_put_result_is_reconciled_before_retry(policy_state, monkeypatch):
    """第一次 PUT 实际落库但响应断开，重跑只读回，不重复写入。"""
    state, calls = policy_state

    def request(method, url, headers, body=None):
        calls.append((method, copy.deepcopy(body)))
        if method == "PUT":
            state["policy"].update(body)
            raise OSError("响应断开")
        return {"data": copy.deepcopy(state)}

    monkeypatch.setattr(recommend, "request", request)
    with pytest.raises(OSError):
        recommend.raise_recommended(NEW, "https://hub.invalid", {})
    recommend.raise_recommended(NEW, "https://hub.invalid", {})
    assert [method for method, _ in calls] == ["GET", "PUT", "GET"]
    assert state["policy"]["min_recommended_version"] == NEW


def target(hub):
    return {"hub_url": hub, "api_key": "private-api-key", "operator_email": "user@example.invalid",
            "operator_id": "1"}


@pytest.mark.parametrize("config", ["", "{}", "[]", "null", "private-api-key invalid-json"])
def test_missing_or_invalid_targets_do_not_echo_secret(monkeypatch, config):
    monkeypatch.setenv("SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS", config)
    with pytest.raises(RuntimeError) as exc:
        recommend.release_targets([("https://hub.invalid/register", "s2s")])
    assert "private-api-key" not in str(exc.value)


@pytest.mark.parametrize("change", ["wrong_hub", "duplicate", "missing_key", "null_key", "invalid_id"])
def test_target_mismatch_or_invalid_identity_fails(monkeypatch, change):
    config = [target("https://hub.invalid")]
    if change == "wrong_hub":
        config[0]["hub_url"] = "https://other.invalid"
    elif change == "duplicate":
        config *= 2
    elif change == "missing_key":
        del config[0]["api_key"]
    elif change == "null_key":
        config[0]["api_key"] = None
    else:
        config[0]["operator_id"] = "0"
    monkeypatch.setenv("SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS", json.dumps(config))
    with pytest.raises(RuntimeError):
        recommend.release_targets([("https://hub.invalid/register", "s2s")])


@pytest.fixture
def hubs():
    servers = []

    def create():
        state = {"calls": [], "releases": [{"id": 10, "version_string": OLD}],
                 "policy": {"min_required_version": OLD, "min_recommended_version": OLD,
                            "emergency_bypass": True}, "fail_register": False, "fail_put": False,
                 "get_code": 0}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, status, data):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                state["calls"].append("POST")
                signature = hmac.new(b"s2s", self.headers["X-Goalfy-Timestamp"].encode() + b"." + body,
                                     hashlib.sha256).hexdigest()
                assert hmac.compare_digest(signature, self.headers["X-Goalfy-Signature"])
                if state["fail_register"]:
                    self.respond(500, {})
                    return
                version = json.loads(body)["version_string"]
                if not any(row["version_string"] == version for row in state["releases"]):
                    state["releases"].append({"id": 30, "version_string": version})
                self.respond(200, {"created": True})

            def do_GET(self):
                state["calls"].append("GET")
                self.respond(200, {"code": state["get_code"], "data": {
                    "releases": state["releases"], "policy": state["policy"],
                }})

            def do_PUT(self):
                state["calls"].append("PUT")
                assert self.headers["X-API-Key"] == "private-api-key"
                assert self.headers["X-Operator-ID"] == self.headers["X-User-ID"] == "1"
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if state["fail_put"]:
                    self.respond(503, {})
                    return
                state["policy"].update(body)
                self.respond(200, {"code": 0})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}", state

    yield create
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def cli(tmp_path):
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / "skill-release.json").write_text(json.dumps({
        "version": NEW, "scaffold_min_required_version": "scaffold", "update_reason": "发布回归",
    }))

    def run(targets, registry=None, config=None, qa=False):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("SCENE_SKILL_", "HUB_"))}
        env["SCENE_SKILL_RELEASE_REGISTRY_TARGETS"] = registry or "\n".join(
            f"{hub}/register|s2s" for hub, _ in targets)
        env["SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS"] = (
            json.dumps([target(hub) for hub, _ in targets]) if config is None else config)
        if qa:
            env.update({"HUB_URL": targets[0][0], "HUB_API_KEY": "private-api-key",
                        "HUB_OPERATOR_EMAIL": "user@example.invalid", "HUB_OPERATOR_ID": "1"})
        command = [sys.executable, str(tmp_path / "scripts" / (
            "raise_skill_recommended.py" if qa else "register-skill-release.py")),
            NEW if qa else "--register-and-recommend"]
        return subprocess.run(command, env=env, text=True, capture_output=True, timeout=10, check=False)

    return run


def test_real_cli_registers_then_promotes_and_rerun_is_idempotent(hubs, cli):
    hub = hubs()
    result = cli([hub])
    assert result.returncode == 0, result.stderr
    assert hub[1]["calls"] == ["POST", "GET", "PUT", "GET"]
    assert hub[1]["policy"] == {
        "min_required_version": OLD, "min_recommended_version": NEW, "emergency_bypass": True,
    }
    hub[1]["calls"].clear()
    assert cli([hub]).returncode == 0
    assert hub[1]["calls"] == ["POST", "GET"]


@pytest.mark.parametrize("failure", ["missing_config", "mismatch", "register"])
def test_real_cli_does_not_promote_when_preconditions_fail(hubs, cli, failure):
    hub = hubs()
    hub[1]["fail_register"] = failure == "register"
    config = "" if failure == "missing_config" else None
    registry = "https://other.invalid/register|s2s" if failure == "mismatch" else None
    result = cli([hub], registry=registry, config=config)
    assert result.returncode != 0
    assert "PUT" not in hub[1]["calls"]
    assert hub[1]["calls"] == (["POST"] if failure == "register" else [])
    assert "private-api-key" not in result.stdout + result.stderr


def test_real_cli_partial_failure_continues_other_targets_and_recovers(hubs, cli):
    first, second = hubs(), hubs()
    first[1]["fail_put"] = True
    result = cli([first, second])
    assert result.returncode != 0
    assert first[1]["policy"]["min_recommended_version"] == OLD
    assert second[1]["policy"]["min_recommended_version"] == NEW
    assert "private-api-key" not in result.stdout + result.stderr
    first[1]["fail_put"] = False
    first[1]["calls"].clear()
    second[1]["calls"].clear()
    assert cli([first, second]).returncode == 0
    assert first[1]["policy"]["min_recommended_version"] == NEW
    assert second[1]["calls"] == ["POST", "GET"]


def test_qa_cli_keeps_existing_single_target_contract(hubs, cli):
    hub = hubs()
    hub[1]["releases"].append({"id": 30, "version_string": NEW})
    result = cli([hub], qa=True)
    assert result.returncode == 0, result.stderr
    assert hub[1]["calls"] == ["GET", "PUT", "GET"]


def test_hub_business_error_on_http_200_does_not_write(hubs, cli):
    """Hub 成功信封 code=0；HTTP 200 不能把非零业务码误判为成功。"""
    hub = hubs()
    hub[1]["get_code"] = 500
    result = cli([hub])
    assert result.returncode != 0
    assert hub[1]["calls"] == ["POST", "GET"]


def test_workflows_share_policy_lock_and_pin_event_commit():
    workflows = [yaml.safe_load((ROOT / ".github/workflows" / name).read_text()) for name in (
        "register-skill-release.yml", "register-skill-qa.yml")]
    assert workflows[0]["concurrency"] == workflows[1]["concurrency"] == {
        "group": "scene-skill-version-policy", "cancel-in-progress": False,
    }
    for workflow in workflows:
        steps = workflow["jobs"]["register"]["steps"]
        assert steps[0]["with"]["ref"] == "${{ github.sha }}"
    prod_step = workflows[0]["jobs"]["register"]["steps"][-1]
    assert "--register-and-recommend" in prod_step["run"]
    assert "SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS" in prod_step["env"]
    trigger = workflows[0].get("on", workflows[0].get(True))
    assert ".github/workflows/register-skill-release.yml" in trigger["push"]["paths"]
