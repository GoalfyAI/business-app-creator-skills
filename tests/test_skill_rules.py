import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RULES = json.loads((ROOT / "tests" / "skill_rules.json").read_text(encoding="utf-8"))
# 源文件和两份插件副本都要带着这些规则。
SURFACES = (
    "skills",
    "claude-code/skills",
    "codex/skills",
)
_LINK = re.compile(r"\]\([^)]*\)")
# 属主部署成功后直接上线，下面这些说法描述的是另一套流程，留一句 Agent 就会多问一次或走错顺序
RETIRED_SENTENCES = (
    "可以上线",
    "同意上线",
    "确认三次",
    "，不要上线",
    "不靠上线",
    "挡上线",
    "同一草稿上改了再跑",
    "上线前自查",
    "上线前核对",
    "上线时平台在临时库彩排",
    "请开发者确认一句",
    "⑤ 上线",
    "等改好再上线」",
    "接受，先上线",
    "上线后用 `instance`",
)
# 入口「不对开发者说的词」里最常漏进模板的几个
INTERNAL_WORDS = ("部署", "工单", "真跑", "冒泡", "施工单", "阶段文档", "checkpoint")


def _normalize(text: str) -> str:
    # 链接目标随目录调整会变，只比较文字
    return _LINK.sub("]", text)


def _skill(relative: str) -> str:
    return (ROOT / "skills" / relative).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str | None = None) -> str:
    tail = text[text.index(start) + len(start) :]
    return tail if end is None else tail[: tail.index(end)]


@pytest.mark.parametrize("surface", SURFACES)
def test_every_ruled_sentence_is_still_in_the_skill(surface: str):
    """规则清单：历次评测、走查和反馈里定下的规则，重写或改动后仍要原句在 Skill 里。

    改写某条规则时，同步改 tests/skill_rules.json 里对应的句子；删掉一条规则要写明原因。
    """
    text = _normalize("\n".join(p.read_text(encoding="utf-8") for p in (ROOT / surface).rglob("*.md")))
    missing = [rule for rule in RULES if _normalize(rule["text"]) not in text]
    assert not missing, "规则句子不在 Skill 里：\n" + "\n".join(f"- [{r['source']}] {r['text']}" for r in missing)


def test_retired_sentences_are_gone():
    hits = [
        f"{path.relative_to(ROOT)}: {sentence}"
        for path in sorted((ROOT / "skills").rglob("*.md"))
        for sentence in RETIRED_SENTENCES
        if sentence in path.read_text(encoding="utf-8")
    ]
    assert not hits, "旧说法还在 Skill 里：\n" + "\n".join(hits)


def test_stage_four_goes_online_before_real_acceptance():
    steps = _between(_skill("agenticapp-stage-4-acceptance/SKILL.md"), "## 按这个顺序做", "## 交报告前的三道硬门")
    positions = [steps.index(step) for step in ("**放到在线预览并上线**", "**工作集实际跑**", "**交验收报告**", "**进 ⑤**")]
    assert positions == sorted(positions)


def test_stage_five_decides_the_branch_before_closing():
    text = _skill("agenticapp-stage-5-launch/SKILL.md")
    assert text.index("**定走哪一支**") < text.index("**结单门**") < text.index("**结单**")
    assert "## 等他选" in text
    assert "等开发者" not in _between(text, "## 开始前确认", "## 等他选")


def test_only_two_confirmations_are_marked_in_the_stage_table():
    table = _between(_skill("agenticapp-creator/SKILL.md"), "| 段 | 加载 |", "**退回**")
    rows = {line.split("|")[1].strip(): line.split("|")[-2].strip() for line in table.splitlines() if "agenticapp-stage-" in line}
    assert rows["① 需求确认"] == "回「确认这一版」"
    assert rows["② 方案"] == "确认整版方案"
    assert rows["③ 制作"] == rows["④ 试用验收"] == "不等"
    assert rows["⑤ 收尾"].startswith("全部通过或只有未测不等")


@pytest.mark.parametrize(
    ("relative", "start", "end"),
    [
        ("agenticapp-tool-deploy/SKILL.md", "## 放好后告诉开发者", "## 结单"),
        ("agenticapp-stage-4-acceptance/assets/验收报告.md", "「结论第一句」按情况照抄：", "「全部条目」怎么填："),
        ("agenticapp-stage-4-acceptance/assets/验收报告.md", "「要你做的」照抄：", None),
        ("agenticapp-stage-5-launch/assets/上线结果.md", "【⑤ 收尾 → 已完成】", "```"),
    ],
)
def test_words_for_the_developer_avoid_internal_terms(relative: str, start: str, end: str | None):
    words = _between(_skill(relative), start, end)
    assert not [word for word in INTERNAL_WORDS if word in words], words


def test_rule_ledger_entries_are_well_formed():
    assert RULES, "规则清单不能为空"
    texts = [rule["text"] for rule in RULES]
    assert len(texts) == len(set(texts)), "规则清单里有重复句子"
    for rule in RULES:
        assert set(rule) == {"source", "text"}, rule
        assert rule["text"].strip() == rule["text"] and len(rule["text"]) >= 6, rule
