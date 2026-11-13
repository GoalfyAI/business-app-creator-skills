"""升级指南随 Skill 发布：目录校验、候选计算、发布检查。 [需求:D-3962][R-438 第 9 版]

tests/fixtures/upgrade_guides/cases/ 取自 Studio 仓库 goalfy-app-workbench 的 scripts/upgrade-guides-fixtures/
（原 check-upgrade-guides.mjs 与制作 MCP 共用的正反样例）；候选计算的用例从制作 MCP 的 tests/test_upgrade_guides.py
移植，去掉了 OA 发布状态、环境、分页与游标（指南随 Skill 发出即生效）。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "skills" / "business-app-creator"
GUIDES = SKILL_ROOT / "upgrade-guides"
SCRIPT = SKILL_ROOT / "scripts" / "upgrade_guides.py"
CASES = Path(__file__).parent / "fixtures" / "upgrade_guides" / "cases"

_spec = importlib.util.spec_from_file_location("skill_upgrade_guides_under_test", SCRIPT)
ug = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ug)

_release_spec = importlib.util.spec_from_file_location("release_for_guides", ROOT / "scripts" / "build_platform_packages.py")
release = importlib.util.module_from_spec(_release_spec)
_release_spec.loader.exec_module(release)


def guide(did: str, *, impact: str = "recommended", replaces=(), withdraws=(), depends_on=None,
          body: str = "补充说明。\n", sdk_major: int | None = None) -> bytes:
    header = {
        "did": did, "title": f"{did} 的指南", "impact": impact,
        "applies_to": {"layers": ["sdk"], "when": f"用到 {did} 改动的应用"},
        "already_done_check": f"{did} 的改动已在业务代码里",
        "actions": [] if impact == "none" else [f"按 {did} 修改"],
        "tests": [] if impact == "none" else [{"id": "t1", "kind": "command", "run": "npm run verify", "expect": "退出码 0"}],
        "replaces": list(replaces), "withdraws": list(withdraws),
    }
    if depends_on is not None:
        header["depends_on"] = list(depends_on)
    if sdk_major is not None:
        header["applies_to"]["sdk_major"] = sdk_major
    return ("```json\n" + json.dumps(header, ensure_ascii=False, indent=2) + "\n```\n\n" + body).encode("utf-8")


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def guides_dir(tmp_path: Path, files: dict[str, bytes]) -> Path:
    directory = tmp_path / "upgrade-guides"
    directory.mkdir()
    shutil.copy2(GUIDES / "schema.json", directory / "schema.json")
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return directory


def applied(*triples) -> list[dict]:
    return [{"did": did, "sha": sha, "how": how} for did, sha, how in triples]


def dids(result: dict) -> list[str]:
    return [g["did"] for g in result["guides"]]


def deps(result: dict, did: str) -> tuple[list[str], list[str]]:
    item = next(g for g in result["guides"] if g["did"] == did)
    return item["depends_on"], item["depends_on_declared"]


# ==================== 仓库里的指南 ====================

def test_shipped_guides_are_valid_and_cover_studio_migration():
    _, headers = ug.load_guides(GUIDES)
    assert {"D-3962", "D-4001", "D-4009", "D-4013", "D-4036", "D-4052", "D-4114", "D-4122"} <= set(headers)
    assert (GUIDES / "README.md").is_file()


def test_storage_diagnostics_guide_supersedes_interaction_evidence():
    result = ug.candidates(GUIDES, [])
    by_did = {item["did"]: item for item in result["guides"]}
    assert by_did["D-4267"]["replaces"] == ["D-4009", "D-4139"]
    assert {"D-4009", "D-4139"}.isdisjoint(by_did)


def test_d3962_manual_edit_ban_only_applies_after_upgrade_script():
    """陈汶君 !120 评审：「不要手工改」只管跑了升级脚本的；旧路手工迁移要拷贝固定层清单、按第 11 步补版本记录。"""
    _, headers = ug.load_guides(GUIDES)
    header = headers["D-3962"]
    actions = header["actions"]
    assert actions[1].startswith("跑了升级脚本的：不要再按旧的三方对照手工迁移固定层")
    assert actions[2].startswith("旧路应用按迁到新路的指南手工迁移固定层、没跑升级脚本的：scaffold-fixed-layer.json 从目标模板根目录原样拷贝到应用根")
    assert "tasks/升级.md" not in (GUIDES / "D-3962.md").read_text(encoding="utf-8")


def test_shipped_guides_are_in_release_manifest_and_both_platforms():
    manifest = json.loads((ROOT / "skill-release.json").read_text(encoding="utf-8"))
    for path in sorted(GUIDES.iterdir()):
        relative = f"upgrade-guides/{path.name}"
        assert relative in manifest["source_files"] and relative in manifest["checksums"], relative
        for platform in ("claude-code", "codex"):
            copy = ROOT / platform / "skills" / "business-app-creator" / relative
            assert copy.read_bytes() == path.read_bytes(), (platform, relative)
    for platform in ("claude-code", "codex"):
        copy = ROOT / platform / "skills" / "business-app-creator" / "scripts" / "upgrade_guides.py"
        assert copy.read_bytes() == SCRIPT.read_bytes()


# ==================== 与原 check 同一组样例 ====================

def _cases() -> list[dict]:
    return json.loads((CASES / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_fixture_cases_match_studio_check(case):
    files = {path.name: path.read_bytes() for path in (CASES / case["dir"]).iterdir()}
    problems, _ = ug.check_guide_set(files, ug.load_schema(GUIDES))
    got = sorted({(p["file"], p["field"], p["code"]) for p in problems})
    expected = sorted({(e["file"], e["field"], e["code"]) for e in case["expect"]})
    assert got == expected, problems


def test_fixture_cases_cover_every_directory():
    assert {path.name for path in CASES.iterdir() if path.is_dir()} == {case["dir"] for case in _cases()}


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_fixture_cases_reach_same_conclusion_through_candidates(case, tmp_path):
    directory = guides_dir(tmp_path, {p.name: p.read_bytes() for p in (CASES / case["dir"]).iterdir()})
    if not case["expect"]:
        assert ug.candidates(directory, [])["status"] == "ok"
        return
    with pytest.raises(ug.GuideError) as info:
        ug.candidates(directory, [])
    assert {p["file"] for p in info.value.problems} == {e["file"] for e in case["expect"]}


def test_directory_rules_and_schema_problems(tmp_path):
    directory = guides_dir(tmp_path, {"D-1.md": guide("D-1"), "notes.txt": b"x"})
    with pytest.raises(ug.GuideError) as info:
        ug.load_guides(directory)
    assert [p["code"] for p in info.value.problems] == ["UNEXPECTED_FILE"]
    (directory / "notes.txt").unlink()
    (directory / "schema.json").unlink()
    with pytest.raises(ug.GuideError) as info:
        ug.load_guides(directory)
    assert info.value.problems[0]["code"] == "SCHEMA_MISSING"
    (directory / "schema.json").write_text('{"type": "object", "oneOf": []}', encoding="utf-8")
    with pytest.raises(ug.GuideError) as info:
        ug.load_guides(directory)
    assert info.value.problems[0]["code"] == "SCHEMA_INVALID", "不支持的关键字不能被静默忽略"


# ==================== 文件头换行 ====================

HEADER_VARIANTS = {
    "lf": "```json\n{\"a\": 1}\n```\n正文\n",
    "crlf": "```json\r\n{\"a\": 1}\r\n```\r\n正文\r\n",
    "crlf_no_trailing_newline": "```json\r\n{\"a\": 1}\r\n```",
    "cr_only_closing": "```json\n{\"a\": 1}\r```\r正文",
    "closing_with_spaces": "```json\r\n{\"a\": 1}\r\n```  \t\r\n",
    "line_separator": "```json\n{\"a\": 1} ``` ",
    "opening_cr_only": "```json\r{\"a\": 1}\n```\n",
    "fence_not_at_line_start": "```json\n{\"a\": 1} ```\n",
    "closing_with_trailing_text": "```json\n{\"a\": 1}\n```x\n",
    "no_closing": "```json\r\n{\"a\": 1}\r\n",
}


def test_header_line_break_variants_match_original_check():
    ok = {name for name, text in HEADER_VARIANTS.items() if ug.parse_guide_header(text)[1] is None}
    assert ok == {"lf", "crlf", "crlf_no_trailing_newline", "cr_only_closing", "closing_with_spaces"}


def test_real_guide_converted_to_crlf_parses_like_lf():
    real = (GUIDES / "D-4013.md").read_bytes()
    crlf = real.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert ug.parse_guide_header(crlf.decode())[0] == ug.parse_guide_header(real.decode())[0]
    problems, _ = ug.check_guide_set({"D-4013.md": crlf}, ug.load_schema(GUIDES))
    assert problems == []


# ==================== 有效集合：替代、撤回 ====================

def test_replaces_and_withdraws_including_chains(tmp_path):
    directory = guides_dir(tmp_path, {
        "D-1.md": guide("D-1"), "D-2.md": guide("D-2", replaces=["D-1"]), "D-3.md": guide("D-3", replaces=["D-2"]),
        "D-4.md": guide("D-4"), "D-5.md": guide("D-5", impact="none", withdraws=["D-4"]),
    })
    result = ug.candidates(directory, [])
    assert dids(result) == ["D-3", "D-5"]
    assert result["counts"] == {"required": 0, "recommended": 1, "none": 1, "changed_since_applied": 0}


def test_app_that_executed_old_guide_receives_replacement_and_retired_lists_it(tmp_path):
    old, d7 = guide("D-1"), guide("D-7")
    directory = guides_dir(tmp_path, {"D-1.md": old, "D-2.md": guide("D-2", replaces=["D-1"]), "D-7.md": d7})
    result = ug.candidates(directory, applied(("D-1", sha16(old), "tested"), ("D-7", sha16(d7), "tested")))
    assert dids(result) == ["D-2"]
    assert result["retired"] == ["D-1"]


def test_withdrawn_replacer_does_not_revive_replaced_guide(tmp_path):
    directory = guides_dir(tmp_path, {"D-1.md": guide("D-1"), "D-2.md": guide("D-2", replaces=["D-1"]),
                                      "D-3.md": guide("D-3", impact="none", withdraws=["D-2"])})
    result = ug.candidates(directory, applied(("D-1", "0" * 16, "tested")))
    assert dids(result) == ["D-3"] and result["retired"] == ["D-1"]


def test_retired_reasons_cover_replaced_withdrawn_and_deleted_files(tmp_path):
    directory = guides_dir(tmp_path, {
        "D-1.md": guide("D-1"), "D-2.md": guide("D-2", replaces=["D-1"]),
        "D-3.md": guide("D-3"), "D-4.md": guide("D-4", impact="none", withdraws=["D-3"]), "D-9.md": guide("D-9"),
    })
    result = ug.candidates(directory, applied(*((f"D-{n}", "0" * 16, "tested") for n in (1, 3, 5, 9))))
    assert result["retired_reasons"] == [
        {"did": "D-1", "reason": "replaced"}, {"did": "D-3", "reason": "withdrawn"}, {"did": "D-5", "reason": "file_deleted"}]
    assert result["retired"] == ["D-1", "D-3", "D-5"]


# ==================== 按条过滤 ====================

def test_sha_change_returns_guide_as_changed_since_applied(tmp_path):
    v1 = guide("D-1", body="v1\n")
    directory = guides_dir(tmp_path, {"D-1.md": v1})
    assert dids(ug.candidates(directory, applied(("D-1", sha16(v1), "tested")))) == []
    v2 = guide("D-1", body="v2\n")
    (directory / "D-1.md").write_bytes(v2)
    changed = ug.candidates(directory, applied(("D-1", sha16(v1), "tested")))
    view = changed["guides"][0]
    assert view["changed_since_applied"] is True and view["sha"] == sha16(v2) and view["sha256"].startswith(sha16(v2))
    assert changed["counts"]["changed_since_applied"] == 1


def test_baseline_without_sha_is_exempt_by_did_and_matching_sha_filters(tmp_path):
    directory = guides_dir(tmp_path, {"D-1.md": guide("D-1"), "D-2.md": guide("D-2"), "D-3.md": guide("D-3")})
    result = ug.candidates(directory, applied(("D-1", None, "baseline"), ("D-2", sha16(guide("D-2")), "already_done")))
    assert dids(result) == ["D-3"]


def test_not_applicable_goes_to_reconsider_and_back_to_candidates_when_sha_changes(tmp_path):
    text = guide("D-1")
    directory = guides_dir(tmp_path, {"D-1.md": text, "D-2.md": guide("D-2")})
    result = ug.candidates(directory, applied(("D-1", sha16(text), "not_applicable")))
    assert dids(result) == ["D-2"] and result["counts"]["recommended"] == 1
    [item] = result["reconsider"]
    assert item["did"] == "D-1" and item["sha"] == sha16(text) and item["changed_since_applied"] is False
    assert item["actions"] == ["按 D-1 修改"] and item["tests"][0]["id"] == "t1", "复核后转候选要用的完整内容"
    stale = ug.candidates(directory, applied(("D-1", "f" * 16, "not_applicable")))
    assert dids(stale) == ["D-1", "D-2"] and stale["reconsider"] == []
    assert stale["guides"][0]["changed_since_applied"] is True


# ==================== depends_on 解析 ====================

def test_depends_on_follows_replacement_chain_and_drops_withdrawn(tmp_path):
    directory = guides_dir(tmp_path, {
        "D-1.md": guide("D-1"), "D-2.md": guide("D-2", replaces=["D-1"]), "D-3.md": guide("D-3", replaces=["D-2"]),
        "D-5.md": guide("D-5"), "D-9.md": guide("D-9", depends_on=["D-1", "D-5", "D-2"]),
        "D-11.md": guide("D-11"), "D-12.md": guide("D-12", impact="none", withdraws=["D-11"]),
        "D-13.md": guide("D-13"), "D-14.md": guide("D-14", replaces=["D-13"]),
        "D-15.md": guide("D-15", impact="none", withdraws=["D-14"]),
        "D-18.md": guide("D-18", depends_on=["D-11"]), "D-19.md": guide("D-19", depends_on=["D-13", "D-11"]),
    })
    result = ug.candidates(directory, [])
    assert deps(result, "D-9") == (["D-3", "D-5"], ["D-1", "D-5", "D-2"]), "两条依赖都追到 D-3，只保留一次"
    assert deps(result, "D-18") == ([], ["D-11"])
    assert deps(result, "D-19") == ([], ["D-13", "D-11"]), "D-13 → D-14 被撤回，D-13 不复活，这条依赖去掉"


def test_depends_on_keeps_original_target_already_applied(tmp_path):
    old = guide("D-1")
    directory = guides_dir(tmp_path, {"D-1.md": old, "D-2.md": guide("D-2", replaces=["D-1"]),
                                      "D-3.md": guide("D-3", depends_on=["D-1"])})
    assert deps(ug.candidates(directory, applied(("D-1", sha16(old), "tested"))), "D-3") == (["D-1"], ["D-1"])
    assert deps(ug.candidates(directory, []), "D-3") == (["D-2"], ["D-1"])


# ==================== history.json ====================

def _app(tmp_path: Path, history) -> Path:
    app = tmp_path / "app"
    (app / "docs" / "upgrade").mkdir(parents=True)
    if history is not None:
        text = history if isinstance(history, str) else json.dumps(history)
        (app / "docs" / "upgrade" / "history.json").write_text(text, encoding="utf-8")
    return app


@pytest.mark.parametrize("history,state", [
    (None, "missing"),
    ("{not json", "broken"),
    ('{"applied_guides": [\n<<<<<<< HEAD\n]}', "broken"),
    ([{"from": "a", "to": "b"}], "no_applied_guides"),
    ({"upgrades": []}, "no_applied_guides"),
])
def test_history_states(tmp_path, history, state):
    entries, got, warnings = ug.read_history(_app(tmp_path, history))
    assert (entries, got, warnings) == ([], state, [])


def test_history_skips_unsettled_and_invalid_entries(tmp_path):
    app = _app(tmp_path, {"applied_guides": [
        {"did": "D-1", "sha": "ABCDEF0123456789", "how": "tested", "fail_count": 0, "updated_at": "x"},
        {"did": "D-2", "how": "baseline"},
        {"did": "D-3", "sha": "0" * 16, "how": "deferred", "reason": "待确认"},
        {"did": "D-4", "sha": "0" * 16, "how": "failed", "reason": "t1"},
        {"did": "X-5", "sha": "0" * 16, "how": "tested"},
        {"did": "D-6", "how": "tested"},
        "D-7",
    ]})
    entries, state, warnings = ug.read_history(app)
    assert state == "ok"
    assert entries == [{"did": "D-1", "sha": "abcdef0123456789", "how": "tested"}, {"did": "D-2", "sha": None, "how": "baseline"}]
    assert [w["index"] for w in warnings] == [4, 5, 6] and {w["code"] for w in warnings} == {"history_entry_invalid"}


def test_deferred_and_failed_do_not_count_as_processed(tmp_path):
    text = guide("D-1")
    directory = guides_dir(tmp_path, {"D-1.md": text})
    app = _app(tmp_path, {"applied_guides": [{"did": "D-1", "sha": sha16(text), "how": "deferred", "reason": "x"}]})
    entries, _, _ = ug.read_history(app)
    result = ug.candidates(directory, entries)
    assert dids(result) == ["D-1"] and result["guides"][0]["changed_since_applied"] is False


# ==================== 命令行 ====================

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, check=False)


def test_cli_candidates_baseline_and_check(tmp_path):
    first = ug.effective_dids(ug.load_guides(GUIDES)[1])[0]
    data = (GUIDES / f"{first}.md").read_bytes()
    app = _app(tmp_path, {"applied_guides": [{"did": first, "sha": sha16(data), "how": "tested"}]})
    done = _run("candidates", "--app", str(app))
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["status"] == "ok" and out["history"] == "ok" and first not in dids(out)
    assert out["skill_version"] and set(out) >= {"counts", "guides", "reconsider", "retired", "retired_reasons", "warnings"}
    base = json.loads(_run("baseline").stdout)
    assert {"did": first, "sha": sha16(data), "how": "baseline"} in base["applied_guides"]
    assert json.loads(_run("check").stdout) == {"status": "ok"}


def test_cli_invalid_guides_fail_whole_run(tmp_path):
    directory = guides_dir(tmp_path, {"D-7.md": guide("D-8")})
    done = _run("--guides-dir", str(directory), "candidates", "--app", str(_app(tmp_path, None)))
    assert done.returncode == 2
    out = json.loads(done.stdout)
    assert out["status"] == "invalid_guide" and out["problems"][0]["code"] == "FILE_NAME"


# ==================== 发布检查 ====================

def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def test_released_guides_are_frozen_by_release_tags(tmp_path):
    skill_root = tmp_path / "skills" / "business-app-creator"
    (skill_root / "upgrade-guides").mkdir(parents=True)
    released = skill_root / "upgrade-guides" / "D-1.md"
    released.write_bytes(guide("D-1"))
    manifest = {"checksums": {"upgrade-guides/D-1.md": hashlib.sha256(guide("D-1")).hexdigest()}}
    (tmp_path / "skill-release.json").write_text(json.dumps(manifest), encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "release")
    _git(tmp_path, "tag", "skill/v20261110-aaaaaa")

    release.check_released_guides_frozen(skill_root)
    (skill_root / "upgrade-guides" / "D-2.md").write_bytes(guide("D-2", replaces=["D-1"]))
    release.check_released_guides_frozen(skill_root)  # 新增指南不受限
    released.write_bytes(guide("D-1", body="改了\n"))
    with pytest.raises(release.ReleaseError, match="D-1.md 已随 v20261110-aaaaaa 发布，内容已改"):
        release.check_released_guides_frozen(skill_root)
    released.unlink()
    with pytest.raises(release.ReleaseError, match="已删除或改名"):
        release.check_released_guides_frozen(skill_root)


def test_invalid_guide_blocks_release_check(tmp_path):
    for name in ("skills", "claude-code", "codex", ".claude-plugin", ".agents"):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in ("skill-release.json", "pyproject.toml", "uv.lock", "README.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    skill_root = tmp_path / "skills" / "business-app-creator"
    (skill_root / "upgrade-guides" / "D-9999.md").write_bytes(guide("D-9998"))
    with pytest.raises(release.ReleaseError, match="升级指南不合规"):
        release.check_release(skill_root)


# ==================== 只取适用 SDK 5.x 的指南（A3） ====================

def _allow_sdk_majors(directory: Path, majors: list[int]) -> None:
    """测试里放开 schema 的 sdk_major 取值，模拟以后有新主版本的指南。"""
    path = directory / "schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["applies_to"]["properties"]["sdk_major"]["enum"] = majors
    path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")


def test_sdk_major_other_than_5_is_rejected_by_shipped_schema(tmp_path):
    directory = guides_dir(tmp_path, {"D-1.md": guide("D-1", sdk_major=4)})
    with pytest.raises(ug.GuideError) as exc:
        ug.candidates(directory, [])
    assert [(p["file"], p["field"]) for p in exc.value.problems] == [("upgrade-guides/D-1.md", "applies_to.sdk_major")]
    (tmp_path / "ok").mkdir()
    assert ug.candidates(guides_dir(tmp_path / "ok", {"D-1.md": guide("D-1", sdk_major=5)}), [])["sdk_major"] == 5


def test_candidates_and_baseline_only_take_guides_for_target_sdk_major(tmp_path):
    d1, d2, d3 = guide("D-1"), guide("D-2", sdk_major=6), guide("D-3", sdk_major=5)
    directory = guides_dir(tmp_path, {"D-1.md": d1, "D-2.md": d2, "D-3.md": d3})
    _allow_sdk_majors(directory, [5, 6])
    assert dids(ug.candidates(directory, [])) == ["D-1", "D-3"]
    assert dids(ug.candidates(directory, [], sdk_major=6)) == ["D-2"]
    # 不适用本主版本的 not_applicable 记录也不进 reconsider；已执行记录照常不算 retired。
    result = ug.candidates(directory, applied(("D-2", sha16(d2), "not_applicable"), ("D-1", sha16(d1), "tested")))
    assert dids(result) == ["D-3"] and result["reconsider"] == [] and result["retired"] == []
    assert [e["did"] for e in ug.baseline(directory)["applied_guides"]] == ["D-1", "D-3"]


def test_cli_sdk_major_option(tmp_path):
    directory = guides_dir(tmp_path, {"D-1.md": guide("D-1"), "D-2.md": guide("D-2", sdk_major=6)})
    _allow_sdk_majors(directory, [5, 6])
    app = _app(tmp_path, None)
    default = json.loads(_run("--guides-dir", str(directory), "candidates", "--app", str(app)).stdout)
    six = json.loads(_run("--guides-dir", str(directory), "candidates", "--app", str(app), "--sdk-major", "6").stdout)
    assert (default["sdk_major"], dids(default)) == (5, ["D-1"])
    assert (six["sdk_major"], dids(six)) == (6, ["D-2"])
