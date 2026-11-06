import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RULES = json.loads((ROOT / "tests" / "skill_rules.json").read_text(encoding="utf-8"))
# 源文件和两份插件副本都要带着这些规则；通用与 Manus 包从同一份源生成，由发布校验保证一致。
SURFACES = (
    "skills",
    "claude-code/skills",
    "codex/skills",
)
_LINK = re.compile(r"\]\([^)]*\)")


def _normalize(text: str) -> str:
    # 链接目标随目录调整会变，只比较文字
    return _LINK.sub("]", text)


@pytest.mark.parametrize("surface", SURFACES)
def test_every_ruled_sentence_is_still_in_the_skill(surface: str):
    """规则清单：历次评测、走查和反馈里定下的规则，重写或改动后仍要原句在 Skill 里。

    改写某条规则时，同步改 tests/skill_rules.json 里对应的句子；删掉一条规则要写明原因。
    """
    text = _normalize("\n".join(p.read_text(encoding="utf-8") for p in (ROOT / surface).rglob("*.md")))
    missing = [rule for rule in RULES if _normalize(rule["text"]) not in text]
    assert not missing, "规则句子不在 Skill 里：\n" + "\n".join(f"- [{r['source']}] {r['text']}" for r in missing)


def test_rule_ledger_entries_are_well_formed():
    assert RULES, "规则清单不能为空"
    texts = [rule["text"] for rule in RULES]
    assert len(texts) == len(set(texts)), "规则清单里有重复句子"
    for rule in RULES:
        assert set(rule) == {"source", "text"}, rule
        assert rule["text"].strip() == rule["text"] and len(rule["text"]) >= 6, rule
