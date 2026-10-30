#!/usr/bin/env python3
"""Studio 表单与记忆卡的严格校验和定稿输出；只读输入、只写标准输出。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import json
import re
import sys

FORM_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
QUESTION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
LANG = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*")
HEX = re.compile(r"#[0-9a-f]{6}")
DATE = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
DATETIME = re.compile(DATE.pattern + "T" + TIME.pattern)

COMMON = {"id", "label", "type", "required"}
CUSTOM = {"allowCustom", "customLabel", "customPlaceholder"}
TYPES = {
    "radio": {"options", "defaultValue"} | CUSTOM,
    "checkbox": {"options", "maxSelections", "defaultValue"} | CUSTOM,
    "select": {"options", "defaultValue"} | CUSTOM,
    "text": {"placeholder", "defaultValue"},
    "textarea": {"placeholder", "defaultValue"},
    "url": {"placeholder", "defaultValue"},
    "email": {"placeholder", "defaultValue"},
    "tel": {"placeholder", "defaultValue"},
    "number": {"placeholder", "min", "max", "step", "defaultValue"},
    "range": {"min", "max", "step", "defaultValue"},
    "date": {"defaultValue"},
    "time": {"defaultValue"},
    "datetime-local": {"defaultValue"},
    "color": {"options", "defaultValue"},
    "file": {"accept", "multiple"},
    "switch": {"defaultValue"},
    "direction-cards": {"cards", "defaultValue"},
}
CHOICE = {"radio", "checkbox", "select", "direction-cards"}
MAX_OPTIONS = {"radio": 7, "checkbox": 7, "select": 20, "color": 7}
MEMORY_TYPES = {"user", "feedback", "project", "reference", "profile", "rule"}
FORM_OPEN = re.compile(r"<question-form\b([^>]*)>")
ANY_FORM_TAG = re.compile(r"<(?:question-form|ask-question)\b", re.IGNORECASE)
CARD_OPEN = re.compile(r"<od-card\b([^>]*)>")
ATTR = re.compile(r'\s+([a-z]+)="([^"<>]*)"')


def text(errors, path, value, limit):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}：必须是非空字符串")
    elif len(value) > limit:
        errors.append(f"{path}：不能超过 {limit} 个字符，现在 {len(value)} 个")


def keys(errors, path, obj, allowed, required=()):
    for k in sorted(set(obj) - allowed):
        errors.append(f"{path}.{k}：这个字段不允许出现，允许的是 {', '.join(sorted(allowed))}")
    for k in required:
        if k not in obj:
            errors.append(f"{path}.{k}：必须写")


def number(errors, path, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{path}：必须是数字（不加引号）")
        return False
    return True


def check_options(errors, path, q, qtype):
    opts = q.get("options")
    limit = MAX_OPTIONS[qtype]
    if opts is None:
        return []
    if not isinstance(opts, list) or not 2 <= len(opts) <= limit:
        errors.append(f"{path}.options：必须是 2–{limit} 项的数组")
        return []
    allowed = {"label", "value", "description"} | ({"group", "trailingLabel"} if qtype == "select" else set())
    values = []
    for i, o in enumerate(opts):
        p = f"{path}.options[{i}]"
        if not isinstance(o, dict):
            errors.append(f"{p}：必须是对象 {{\"label\", \"value\"}}，不能只写字符串")
            continue
        keys(errors, p, o, allowed, ("label", "value"))
        text(errors, f"{p}.label", o.get("label"), 40)
        v = o.get("value")
        pattern = HEX if qtype == "color" else VALUE
        hint = "#rrggbb 小写" if qtype == "color" else "英文字母、数字、.、-、_，以字母或数字开头"
        if not isinstance(v, str) or not pattern.fullmatch(v):
            errors.append(f"{p}.value：必须是 {hint}")
        elif v in values:
            errors.append(f"{p}.value：和前面的选项重复（{v}）")
        values.append(v)
        for k, limit_k in (("description", 120), ("group", 20), ("trailingLabel", 12)):
            if k in o:
                text(errors, f"{p}.{k}", o[k], limit_k)
    return values


def check_cards(errors, path, q):
    cards = q.get("cards")
    if not isinstance(cards, list) or not 2 <= len(cards) <= 4:
        errors.append(f"{path}.cards：必须是 2–4 张卡的数组")
        return []
    ids = []
    for i, c in enumerate(cards):
        p = f"{path}.cards[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{p}：必须是对象")
            continue
        fields = ("id", "label", "mood", "references", "palette", "displayFont", "bodyFont")
        keys(errors, p, c, set(fields), fields)
        cid = c.get("id")
        if not isinstance(cid, str) or not VALUE.fullmatch(cid):
            errors.append(f"{p}.id：必须是英文字母、数字、.、-、_")
        elif cid in ids:
            errors.append(f"{p}.id：和前面的卡重复（{cid}）")
        ids.append(cid)
        text(errors, f"{p}.label", c.get("label"), 40)
        text(errors, f"{p}.mood", c.get("mood"), 120)
        for k in ("displayFont", "bodyFont"):
            text(errors, f"{p}.{k}", c.get(k), 80)
        refs = c.get("references")
        if not isinstance(refs, list) or not 1 <= len(refs) <= 4:
            errors.append(f"{p}.references：必须是 1–4 项的字符串数组")
        else:
            for j, r in enumerate(refs):
                text(errors, f"{p}.references[{j}]", r, 40)
        pal = c.get("palette")
        if not isinstance(pal, list) or not 4 <= len(pal) <= 6:
            errors.append(f"{p}.palette：必须是 4–6 个颜色")
        else:
            for j, col in enumerate(pal):
                if not isinstance(col, str) or not HEX.fullmatch(col):
                    errors.append(f"{p}.palette[{j}]：必须是 #rrggbb 小写")
    return ids


def check_default(errors, path, q, qtype, values):
    if "defaultValue" not in q:
        return
    d = q["defaultValue"]
    p = f"{path}.defaultValue"
    if qtype in CHOICE:
        errors.append(f"{p}：选择题禁止预选，推荐项写在 label 末尾「（推荐）」")
        return
    if not isinstance(d, str):
        errors.append(f"{p}：必须是字符串（数字也加引号，例如 \"20\"）")
        return
    if qtype == "color":
        if not HEX.fullmatch(d):
            errors.append(f"{p}：必须是 #rrggbb 小写")
        elif values and d not in values:
            errors.append(f"{p}：必须是 options 里的一个 value")
    elif qtype in ("number", "range"):
        try:
            n = float(d)
        except ValueError:
            errors.append(f"{p}：必须是数字字符串")
            return
        lo, hi = q.get("min"), q.get("max")
        if isinstance(lo, (int, float)) and n < lo or isinstance(hi, (int, float)) and n > hi:
            errors.append(f"{p}：必须在 min 和 max 之间")
    elif qtype == "date" and not DATE.fullmatch(d):
        errors.append(f"{p}：必须是 YYYY-MM-DD")
    elif qtype == "time" and not TIME.fullmatch(d):
        errors.append(f"{p}：必须是 HH:MM（24 小时）")
    elif qtype == "datetime-local" and not DATETIME.fullmatch(d):
        errors.append(f"{p}：必须是 YYYY-MM-DDTHH:MM")
    elif qtype == "switch" and d not in ("true", "false"):
        errors.append(f"{p}：必须是 \"true\" 或 \"false\"")
    elif not d.strip():
        errors.append(f"{p}：不能是空字符串，没有已定的值就不写")


def check_question(errors, path, q):
    if not isinstance(q, dict):
        errors.append(f"{path}：必须是对象")
        return None
    qtype = q.get("type")
    if qtype not in TYPES:
        errors.append(f"{path}.type：必须是 {', '.join(TYPES)} 之一，现在是 {qtype!r}")
        return q.get("id")
    keys(errors, path, q, COMMON | TYPES[qtype], ("id", "label", "type"))
    qid = q.get("id")
    if not isinstance(qid, str) or not QUESTION_ID.fullmatch(qid):
        errors.append(f"{path}.id：必须以英文字母开头，只含字母、数字、-、_")
    text(errors, f"{path}.label", q.get("label"), 120)
    if "required" in q and not isinstance(q["required"], bool):
        errors.append(f"{path}.required：必须是 true 或 false")
    values = []
    if qtype in ("radio", "checkbox", "select"):
        if "options" not in q:
            errors.append(f"{path}.options：{qtype} 必须写选项")
        values = check_options(errors, path, q, qtype)
    elif qtype == "color":
        values = check_options(errors, path, q, qtype)
    elif qtype == "direction-cards":
        values = check_cards(errors, path, q)
    if q.get("allowCustom") is not None and not isinstance(q.get("allowCustom"), bool):
        errors.append(f"{path}.allowCustom：必须是 true 或 false")
    for k, limit in (("customLabel", 30), ("customPlaceholder", 60), ("placeholder", 60), ("accept", 120)):
        if k in q:
            text(errors, f"{path}.{k}", q[k], limit)
    if (q.get("customLabel") or q.get("customPlaceholder")) and q.get("allowCustom") is not True:
        errors.append(f"{path}.customLabel：写了自定义文案就必须同时写 allowCustom: true")
    if qtype == "checkbox" and "maxSelections" in q:
        m = q["maxSelections"]
        if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= max(len(values), 1):
            errors.append(f"{path}.maxSelections：必须是 1 到选项数之间的整数")
    if qtype == "file" and "multiple" in q and not isinstance(q["multiple"], bool):
        errors.append(f"{path}.multiple：必须是 true 或 false")
    if qtype in ("number", "range"):
        present = [k for k in ("min", "max", "step") if k in q and number(errors, f"{path}.{k}", q[k])]
        if qtype == "range":
            for k in ("min", "max"):
                if k not in q:
                    errors.append(f"{path}.{k}：range 必须写")
        if "min" in present and "max" in present and q["min"] >= q["max"]:
            errors.append(f"{path}.max：必须大于 min")
        if "step" in present and q["step"] <= 0:
            errors.append(f"{path}.step：必须大于 0")
    check_default(errors, path, q, qtype, values)
    return qid


def check_form(data):
    errors = []
    if not isinstance(data, dict):
        return ["表单体：必须是对象 {\"lang\", \"questions\"}，不能是数组"]
    keys(errors, "表单体", data, {"lang", "submitLabel", "questions"}, ("lang", "questions"))
    if not isinstance(data.get("lang"), str) or not LANG.fullmatch(data.get("lang", "")):
        errors.append("表单体.lang：必须是语言标签，例如 \"zh-CN\"")
    if "submitLabel" in data:
        text(errors, "表单体.submitLabel", data["submitLabel"], 12)
    qs = data.get("questions")
    if not isinstance(qs, list) or not 1 <= len(qs) <= 5:
        errors.append("表单体.questions：必须是 1–5 道题的数组")
        return errors
    seen = set()
    for i, q in enumerate(qs):
        qid = check_question(errors, f"questions[{i}]", q)
        if isinstance(qid, str) and qid in seen:
            errors.append(f"questions[{i}].id：和前面的题重复（{qid}）")
        seen.add(qid)
    return errors


def check_memory(data):
    errors = []
    if not isinstance(data, dict):
        return ["卡片体：必须是对象 {\"summary\", \"used\"}"]
    keys(errors, "卡片体", data, {"summary", "used"}, ("summary", "used"))
    text(errors, "卡片体.summary", data.get("summary"), 80)
    used = data.get("used")
    if not isinstance(used, list) or not 1 <= len(used) <= 10:
        errors.append("卡片体.used：必须是 1–10 项的数组")
        return errors
    for i, u in enumerate(used):
        p = f"used[{i}]"
        if not isinstance(u, dict):
            errors.append(f"{p}：必须是对象")
            continue
        keys(errors, p, u, {"type", "name", "id"}, ("type", "name"))
        if u.get("type") not in MEMORY_TYPES:
            errors.append(f"{p}.type：必须是 {', '.join(sorted(MEMORY_TYPES))} 之一")
        text(errors, f"{p}.name", u.get("name"), 40)
        if "id" in u and (not isinstance(u["id"], str) or not VALUE.fullmatch(u["id"])):
            errors.append(f"{p}.id：必须是英文字母、数字、.、-、_")
    return errors


def compact(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def load_json(raw, label):
    try:
        return json.loads(raw), []
    except json.JSONDecodeError as e:
        return None, [f"{label}：不是合法 JSON（第 {e.lineno} 行第 {e.colno} 列：{e.msg}）"]


def check_reply(reply):
    """校验整条最终回复：最多一张表单且在最后，卡片和表单都不在代码块里，体都合格。"""
    errors = []
    fences = [m.start() for m in re.finditer(r"^\s*```", reply, re.MULTILINE)]

    def in_fence(pos):
        return sum(1 for f in fences if f < pos) % 2 == 1

    tags = list(ANY_FORM_TAG.finditer(reply))
    if any(m.group(0).lower() != "<question-form" for m in tags):
        errors.append("回复：标签必须写 <question-form>，不能写 <ask-question> 或改大小写")
    forms = list(FORM_OPEN.finditer(reply))
    if len(forms) > 1:
        errors.append(f"回复：一轮只能有一张表单，现在有 {len(forms)} 张")
    for m in forms:
        if in_fence(m.start()):
            errors.append("回复：表单不能放进代码块")
        attrs = dict(ATTR.findall(m.group(1)))
        if set(attrs) != {"id", "title"} or ATTR.sub("", m.group(1)).strip():
            errors.append("回复：开标签必须正好是 <question-form id=\"…\" title=\"…\">")
        if not FORM_ID.fullmatch(attrs.get("id", "")):
            errors.append("回复：表单 id 只能用小写英文、数字、-")
        text(errors, "回复：表单 title", attrs.get("title"), 30)
        end = reply.find("</question-form>", m.end())
        if end < 0:
            errors.append("回复：表单缺闭合标签 </question-form>")
            continue
        body = reply[m.end():end].strip()
        if body.startswith("```"):
            errors.append("回复：表单体不能包代码围栏")
        data, err = load_json(body, "回复：表单体")
        errors += err or check_form(data)
        if reply[end + len("</question-form>"):].strip():
            errors.append("回复：</question-form> 后面不能再有任何文字，表单必须是这一轮的最后输出")
    for m in CARD_OPEN.finditer(reply):
        if in_fence(m.start()):
            errors.append("回复：记忆卡不能放进代码块")
        attrs = dict(ATTR.findall(m.group(1)))
        if attrs != {"type": "memory-applied"} or ATTR.sub("", m.group(1)).strip():
            errors.append("回复：记忆卡开标签必须正好是 <od-card type=\"memory-applied\">")
        end = reply.find("</od-card>", m.end())
        if end < 0:
            errors.append("回复：记忆卡缺闭合标签 </od-card>")
            continue
        data, err = load_json(reply[m.end():end].strip(), "回复：记忆卡体")
        errors += err or check_memory(data)
    if len(list(CARD_OPEN.finditer(reply))) > 1:
        errors.append("回复：一轮最多一张记忆卡")
    return errors


def read_input(path):
    return sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Studio 表单与记忆卡：严格校验并输出可直接粘贴的定稿")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("form", help="校验表单体 JSON，合格时输出整段 <question-form>")
    f.add_argument("--id", required=True)
    f.add_argument("--title", required=True)
    f.add_argument("input", help="表单体 JSON 文件，- 表示标准输入")
    m = sub.add_parser("memory", help="校验记忆卡 JSON，合格时输出整段 <od-card>")
    m.add_argument("input")
    r = sub.add_parser("reply", help="校验一整条最终回复里的表单和记忆卡")
    r.add_argument("input")
    args = ap.parse_args(argv)
    raw = read_input(args.input)
    if args.cmd == "reply":
        errors, out = check_reply(raw), "回复合格"
    else:
        data, errors = load_json(raw, "输入")
        if args.cmd == "form":
            if not FORM_ID.fullmatch(args.id):
                errors.append("--id：只能用小写英文、数字、-")
            if not args.title.strip() or len(args.title) > 30 or re.search(r'["<>]', args.title):
                errors.append("--title：必须是 1–30 个字符，不能含 \" < >")
            errors += [] if data is None else check_form(data)
            out = f'<question-form id="{args.id}" title="{args.title}">{compact(data)}</question-form>'
        else:
            errors += [] if data is None else check_memory(data)
            out = f'<od-card type="memory-applied">{compact(data)}</od-card>'
    if errors:
        print("不合格，按下面逐条改完再运行一次：", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
