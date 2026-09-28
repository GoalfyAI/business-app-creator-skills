from pathlib import Path

SKILL_ROOT = Path(__file__).parents[1] / "skills" / "business-app-creator"


def test_workspace_output_guidance_distinguishes_provenance_from_delivery():
    text = (SKILL_ROOT / "reference" / "编排脚本.md").read_text(encoding="utf-8")
    section = text.split("### 文件产物", 1)[1].split("### ", 1)[0]
    assert "`ctx.process_dir` 用于过程文件" in section
    assert "本次新生成且要返回的文件（包括诊断附件）写进 `ctx.output_dir`" in section
    assert "输入文件字段带入的路径" in section
    assert "裸路径或完整 JSON" in section
    assert "File written successfully: <path>" in section
    assert "不会被解析为可信来源" in section
    assert "WORKSPACE_PATH_UNTRUSTED" in section
    assert "不能只改路径字符串" in section
    assert "最终交付仍须满足" in section


def test_untrusted_path_diagnosis_requires_real_file_remediation():
    text = (SKILL_ROOT / "reference" / "报错对照.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| `WORKSPACE_PATH_UNTRUSTED` |")]
    assert len(rows) == 1
    row = rows[0]
    assert "文字成功回执不算来源证明" in row
    assert "实际写入或复制到 `ctx.output_dir`" in row
    assert "虚构文件或删文件声明" in row
