import contextlib
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).parents[1] / "skills/business-app-creator"
spec = importlib.util.spec_from_file_location("studio_card", SKILL / "scripts/studio_card.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def reference_questions():
    text = (SKILL / "reference/Studio表单与卡片.md").read_text(encoding="utf-8")
    block = re.search(r"```json\n(.*?)```", text, re.DOTALL).group(1)
    return [json.loads(line) for line in block.strip().splitlines()]


def run(argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        old, m.sys.stdin = m.sys.stdin, io.StringIO(stdin)
        try:
            code = m.main(argv)
        finally:
            m.sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class StudioCardTests(unittest.TestCase):
    def test_reference_covers_every_type_and_passes(self):
        questions = reference_questions()
        self.assertEqual({q["type"] for q in questions}, set(m.TYPES))
        for q in questions:
            with self.subTest(type=q["type"]):
                self.assertEqual(m.check_form({"lang": "zh-CN", "questions": [q]}), [])

    def test_form_command_prints_single_line_block(self):
        body = {"lang": "zh-CN", "submitLabel": "提交回答", "questions": reference_questions()[:5]}
        code, out, err = run(["form", "--id", "round-2", "--title", "需求确认 · 第 2 轮", "-"], json.dumps(body))
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count("\n"), 1)
        self.assertTrue(out.startswith('<question-form id="round-2" title="需求确认 · 第 2 轮">{'))
        self.assertEqual(m.check_reply("说明一句。\n\n" + out), [])

    def test_rejects_common_drift(self):
        cases = {
            "同义词 type": {"id": "a", "label": "x", "type": "dropdown", "options": []},
            "字符串选项": {"id": "a", "label": "x", "type": "radio", "options": ["甲", "乙"]},
            "中文 value": {"id": "a", "label": "x", "type": "radio",
                         "options": [{"label": "甲", "value": "甲"}, {"label": "乙", "value": "b"}]},
            "选择题预选": {"id": "a", "label": "x", "type": "radio", "defaultValue": "b",
                      "options": [{"label": "甲", "value": "a"}, {"label": "乙", "value": "b"}]},
            "多余字段": {"id": "a", "label": "x", "type": "text", "help": "说明"},
            "数字没加引号": {"id": "a", "label": "x", "type": "number", "defaultValue": 3},
            "大写颜色": {"id": "a", "label": "x", "type": "color", "defaultValue": "#3B82F6"},
            "range 缺 max": {"id": "a", "label": "x", "type": "range", "min": 1},
            "自定义文案缺开关": {"id": "a", "label": "x", "type": "radio", "customLabel": "其他",
                          "options": [{"label": "甲", "value": "a"}, {"label": "乙", "value": "b"}]},
        }
        for name, q in cases.items():
            with self.subTest(name):
                self.assertNotEqual(m.check_form({"lang": "zh-CN", "questions": [q]}), [])

    def test_form_limits(self):
        q = {"id": "a", "label": "x", "type": "text"}
        self.assertNotEqual(m.check_form({"lang": "zh-CN", "questions": []}), [])
        many = [dict(q, id=f"q{i}") for i in range(6)]
        self.assertNotEqual(m.check_form({"lang": "zh-CN", "questions": many}), [])
        self.assertNotEqual(m.check_form([q]), [])
        self.assertNotEqual(m.check_form({"lang": "zh-CN", "questions": [q, dict(q)]}), [])

    def test_memory_card(self):
        card = {"summary": "本轮按你的开发偏好写", "used": [{"type": "project", "name": "界面用简体中文", "id": "pref-1"}]}
        code, out, err = run(["memory", "-"], json.dumps(card, ensure_ascii=False))
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith('<od-card type="memory-applied">{'))
        self.assertNotEqual(m.check_memory({"summary": "x", "used": [{"type": "skill", "name": "y"}]}), [])

    def test_reply_rules(self):
        _, form, _ = run(["form", "--id", "round-1", "--title", "第 1 轮", "-"],
                         json.dumps({"lang": "zh-CN", "questions": reference_questions()[:1]}))
        form = form.strip()
        self.assertEqual(m.check_reply("正文\n\n" + form), [])
        self.assertNotEqual(m.check_reply(form + "\n请填写上面的表单"), [])
        self.assertNotEqual(m.check_reply("```\n" + form + "\n```"), [])
        self.assertNotEqual(m.check_reply(form.replace("question-form", "ask-question")), [])
        self.assertNotEqual(m.check_reply(form + "\n" + form), [])
        broken = form.replace('"lang":"zh-CN",', '"lang":"zh-CN"')
        self.assertNotEqual(m.check_reply(broken), [])

    def test_errors_exit_nonzero(self):
        code, out, err = run(["form", "--id", "Round 1", "--title", "x", "-"], "{")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("不是合法 JSON", err)
        self.assertIn("--id", err)


if __name__ == "__main__":
    unittest.main()
