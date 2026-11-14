"""回调故障只影响登记，原运行和物理部署结果保持。"""

import importlib.util
import json
from pathlib import Path

import yaml

MODULE = Path(__file__).parents[1] / "scripts" / "notify_oa.py"
spec = importlib.util.spec_from_file_location("notify_oa", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_callback_timeout_keeps_receipt_and_exact_replay(tmp_path):
    def timeout(request, timeout):
        raise TimeoutError("不能进入回执的网络正文")

    receipt = module.notify("prod", "5333330", "47", tmp_path, timeout)
    assert receipt == {"pipeline_id": "5333330", "run_id": 47, "stage": "prod",
                       "status": "pending", "reason_code": "CALLBACK_UNAVAILABLE"}
    path = tmp_path / "5333330-47-prod.json"
    assert json.loads(path.read_text()) == receipt

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"code":200,"data":{"skipped":"duplicate"}}'

    def success(request, timeout):
        assert json.loads(request.data) == {"pipeline_id": "5333330", "run_id": 47, "stage": "prod"}
        assert timeout == 10
        return Response()

    assert module.notify("prod", "5333330", "47", tmp_path, success)["status"] == "registered"
    assert json.loads(path.read_text())["status"] == "registered"


def test_invalid_identity_does_not_send_or_create_receipt(tmp_path):
    def forbidden(*args, **kwargs): raise AssertionError("无效身份不得发请求")
    assert module.notify("prod", "bad", "47", tmp_path, forbidden)["reason_code"] == "CALLBACK_IDENTITY_INVALID"
    assert module.notify("prod", "0", "47", tmp_path, forbidden)["reason_code"] == "CALLBACK_IDENTITY_INVALID"
    assert not list(tmp_path.iterdir())


def test_skipped_callback_is_pending_and_main_keeps_deployment_result(tmp_path, monkeypatch, capsys):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"code":200,"data":{"skipped":"unknown_pipeline"}}'

    assert module.notify("pre", "5333330", "47", tmp_path, lambda *a, **kw: Response())["reason_code"] == "CALLBACK_NOT_REGISTERED"
    monkeypatch.setattr(module, "notify", lambda *a, **kw: {"status": "pending", "reason_code": "CALLBACK_UNAVAILABLE"})
    monkeypatch.setattr("sys.argv", ["notify_oa.py", "--stage", "pre"])
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path))
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out) == {"oa_registration": {"status": "pending", "reason_code": "CALLBACK_UNAVAILABLE"}, "deployment_unchanged": True}


def test_flow_notifies_exact_stage_after_deploy():
    pipeline = yaml.safe_load((MODULE.parent / "flow" / "skill-release.yaml").read_text())
    for stage, job in (("pre", "job_deploy_cn_pre"), ("prod", "job_deploy_cn")):
        steps = pipeline["stages"][f"stage_deploy_{stage}"]["jobs"][job]["steps"]
        command = steps["notify_oa"]["with"]["run"]
        assert f"python3 scripts/notify_oa.py --stage {stage}" in command
        assert "deploy_env.py" in steps["deploy"]["with"]["run"]
