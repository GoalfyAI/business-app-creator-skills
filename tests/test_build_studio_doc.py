"""Studio 开发文档生成脚本：样例能生成，测试里真出过的错能拦下。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "agenticapp-host-studio"
SCRIPT = SKILL / "scripts" / "build_studio_doc.py"
SAMPLES = {"prd": "需求说明数据.md", "proposal": "方案数据.md", "progress": "制作进度数据.md", "acceptance": "验收报告数据.md"}


def _sample(doc_type: str) -> dict:
    text = (SKILL / "assets" / SAMPLES[doc_type]).read_text(encoding="utf-8")
    return json.loads(re.search(r"```json\n([\s\S]*?)\n```", text).group(1))


def _prepare(tmp_path: Path, doc_type: str, data: dict) -> Path:
    folder = tmp_path / doc_type
    folder.mkdir()
    (folder / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if doc_type == "proposal":
        demo = re.search(r"```html\n([\s\S]*?)\n```", (SKILL / "references" / "Demo怎么写.md").read_text(encoding="utf-8")).group(1)
        (folder / "demos").mkdir()
        (folder / "demos" / "01.html").write_text(demo, encoding="utf-8")
        (folder / "acceptance.json").write_text('{"version":2,"roles":[],"crud":[{"id":"1"}],"tpes":[]}', encoding="utf-8")
    if doc_type == "acceptance":
        (folder / "shots").mkdir()
        (folder / "shots" / "1-1.png").write_bytes(b"\x89PNG")
    return folder / "data.json"


def _build(doc_type: str, data_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), doc_type, str(data_path)], capture_output=True, text=True, check=False)


@pytest.mark.parametrize("doc_type", list(SAMPLES))
def test_sample_builds_and_round_trips(tmp_path: Path, doc_type: str) -> None:
    data_path = _prepare(tmp_path, doc_type, _sample(doc_type))
    run = _build(doc_type, data_path)
    assert run.returncode == 0, run.stdout + run.stderr
    page = (data_path.parent / "index.html").read_text(encoding="utf-8")
    assert "<!--BODY-->" not in page and "【填" not in page
    back = tmp_path / "back"
    run = subprocess.run([sys.executable, str(SCRIPT), "extract", str(data_path.parent / "index.html"), str(back)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert json.loads((back / "data.json").read_text(encoding="utf-8"))["app"] == _sample(doc_type)["app"]


def test_acceptance_counts_and_path_consistency(tmp_path: Path) -> None:
    data = _sample("acceptance")
    data["items"][0]["seen"] = "本机版上部署后冒泡跑通"
    data["items"][-1]["untested"] = {"kind": "没时间"}
    data["paths"][0]["nodes"][2]["state"] = "pass"
    out = _build("acceptance", _prepare(tmp_path, "acceptance", data)).stdout
    assert "不写「冒泡」" in out and "不写「部署」" in out and "不写「本机」" in out
    assert "未测只能是这几类" in out
    assert "标了通过，但条目 4 的结论是「没通过」" in out


def test_extra_untested_is_counted(tmp_path: Path) -> None:
    data_path = _prepare(tmp_path, "acceptance", _sample("acceptance"))
    assert _build("acceptance", data_path).returncode == 0
    page = (data_path.parent / "index.html").read_text(encoding="utf-8")
    assert "未测 2。" in page  # 一条条目未测 + 一条条目外的在线预览页面


def test_demo_rules(tmp_path: Path) -> None:
    data_path = _prepare(tmp_path, "proposal", _sample("proposal"))
    (data_path.parent / "demos" / "01.html").write_text('<div data-pin="1"><form><input data-pin="2"></form></div><script>fetch("https://x")</script>', encoding="utf-8")
    out = _build("proposal", data_path).stdout
    assert "不用 <form>" in out and "不联网" in out and "放在了 <input> 上" in out and "要和 notes 的条数对上" in out


def test_prd_and_proposal_only_show_prototype_blocks(tmp_path: Path) -> None:
    prd = _sample("prd")
    prd["records"] = [{"what": "批次"}]
    out = _build("prd", _prepare(tmp_path, "prd", prd)).stdout
    assert "data.records" in out and "保存那一步" in out
    prop = _sample("proposal")
    data_path = _prepare(tmp_path, "proposal", prop)
    assert _build("proposal", data_path).returncode == 0
    page = (data_path.parent / "index.html").read_text(encoding="utf-8")
    body = page.split('id="doc-data"')[0]
    assert "运行条件说明" in body and "功能与页面设计" in body
    assert "验收条目" not in body and "费用复核" not in body and "每一步用什么" not in body
    assert "新建五花肉批次" not in body  # 验收条目只校验不显示


def test_progress_blocked_event_and_marker(tmp_path: Path) -> None:
    data = _sample("progress")
    data["events"][-1].update({"status": "blocked", "time": "15:10", "detail": "放到在线预览时平台报错，已报平台"})
    data_path = _prepare(tmp_path, "progress", data)
    run = _build("progress", data_path)
    assert run.returncode == 0, run.stdout
    index = data_path.parent / "index.html"
    assert "受阻" in index.read_text(encoding="utf-8")
    verify = [sys.executable, str(SCRIPT), "verify", str(index)]
    assert subprocess.run(verify, capture_output=True, text=True, check=False).returncode == 0
    index.write_text(index.read_text(encoding="utf-8").replace("受阻", "卡住"), encoding="utf-8")
    assert subprocess.run(verify, capture_output=True, text=True, check=False).returncode == 1
    hand = data_path.parent / "hand.html"
    hand.write_text("<html><body>手写</body></html>", encoding="utf-8")
    assert subprocess.run([sys.executable, str(SCRIPT), "verify", str(hand)], capture_output=True, text=True, check=False).returncode == 1


def test_progress_and_acceptance_only_show_prototype_blocks(tmp_path: Path) -> None:
    data_path = _prepare(tmp_path, "progress", _sample("progress"))
    assert _build("progress", data_path).returncode == 0
    body = (data_path.parent / "index.html").read_text(encoding="utf-8").split('id="doc-data"')[0]
    assert "制作时间轴" in body and "交付范围与待明确条件" in body and "后厨是否共用一个账号" in body
    assert "我先跑了一遍" not in body and "每个功能做到哪" not in body and "页面说明" not in body
    data = _sample("acceptance")
    data["items"][3]["id"] = "writing_judgement"
    data["paths"][1]["nodes"][1]["items"] = ["writing_judgement"]
    data_path = _prepare(tmp_path, "acceptance", data)
    assert _build("acceptance", data_path).returncode == 0
    body = (data_path.parent / "index.html").read_text(encoding="utf-8").split('id="doc-data"')[0]
    assert "业务路径检查" in body and "你觉得后厨看得清吗" in body and "到点触发要等真实时间" in body
    assert "writing_judgement" not in body
    for old in ("<h2>好不好你说了算", "<h2>未测的", "实际跑出的结果", "自动发生的", "实际花费", "全部条目", "修改记录"):
        assert old not in body


def test_progress_and_acceptance_reject_old_blocks(tmp_path: Path) -> None:
    data = _sample("progress")
    data.update({"trials": [{"feature": "每天出清单"}], "state": "blocked"})
    out = _build("progress", _prepare(tmp_path, "progress", data)).stdout
    assert "data.trials" in out and "进度消息" in out and "blocked 事件" in out
    data = _sample("acceptance")
    data["costs"] = []
    data["paths"][1]["nodes"][1]["items"] = []
    out = _build("acceptance", _prepare(tmp_path, "acceptance", data)).stdout
    assert "data.costs" in out and "条目 5 没挂到任何一步上" in out
