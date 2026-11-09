#!/usr/bin/env python3
"""把 Studio 开发文档的数据生成 index.html，生成前逐条校验。

用法：
  python3 build_studio_doc.py <prd|proposal|progress|acceptance> <data.json> [-o 输出文件]
  python3 build_studio_doc.py shot <index.html> <应用的 frontend 目录>   # 400px、900px 各截一张图到同目录 .shots/，报页面脚本错误
  python3 build_studio_doc.py extract <index.html> <目录>   # 从保存过的一版取回 data.json（方案连同 Demo 文件）写进目录
  python3 build_studio_doc.py verify <index.html>   # 保存前核对：是脚本生成的、生成后没被改过

data.json 放在应用工程 docs/studio/<documentType>/ 下；方案的 Demo、验收报告的截图按 data.json 里写的相对路径找。
退出码：0 已生成，最后几行列出调 studio_write_proposal 时 files 要放的文件；1 有问题，逐条列出位置和改法；2 用法错误。
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

SHELL = Path(__file__).resolve().parent.parent / "assets" / "开发文档外壳.html"
DOC_TYPES = ("prd", "proposal", "progress", "acceptance")
DOC_NAMES = {"prd": "需求说明", "proposal": "方案", "progress": "制作进度", "acceptance": "验收报告"}
BY = {"user": "使用者", "app": "应用自动处理", "ai": "AI"}
CONDITION_KEYS = [
    ("data", "数据从哪里来、多久更新一次？"),
    ("account", "要准备什么账号，谁来授权？"),
    ("cost", "哪些地方要花钱？"),
    ("access", "谁能看到、谁能改这些数据？"),
    ("effects", "会不会自动对外做事，资料会交给谁？"),
]
BACKEND_STATES = ("做好了，实际跑过", "做好了，只用模拟数据试过", "做好了，等在线预览时实际跑", "在做", "没开始", "不需要")
CELL_STATES = ("做好了", "在做", "没开始", "不需要")
EVENT_STATES = ("done", "doing", "todo", "blocked")
# 原型里没有、已并到别处的旧字段：字段 → 写到哪
MOVED_KEYS = {
    "prd": {
        "users": "谁来用写进 overview.audience",
        "records": "会记下来的东西写进保存那一步节点的 rule",
        "cost": "花多少写进方案 conditions.cost；花费上限在聊天里问，记工单",
        "side_effects": "费用与副作用写进方案 conditions.cost 和 conditions.effects",
        "external": "外部数据写进方案 conditions.data",
        "needs": "要他提供的写进方案 conditions.account",
        "cannot": "替代做法写进被替代那一步节点的 rule，环节 verified 写「做不到，见替代」",
        "automations": "自动发生的事画成「到点开始」的 app 节点",
        "others": "非刚需写进方案 scope.summary",
        "out_of_scope": "这次不做的写进方案 scope.summary",
        "defaults": "按默认定下的在节点 rule 原处标「按默认」",
        "screens": "界面写进方案 features（每个功能的页面）",
        "launch_scope": "上线范围不写进文档",
        "decisions": "还要他定的事在聊天里用表单问",
    },
    "proposal": {
        "steps": "每一步用什么、花多少写在需求说明 AI 节点的 tier 和 cost",
        "cost_review": "费用复核写进 conditions.cost 和 conditions.effects",
        "summary": "一共要做什么写进 scope.summary",
    },
    "progress": {
        "trials": "「我先跑了一遍」只在聊天的进度消息里发；跑过的那一次在 events 里记一条",
        "pages": "页面说明只在聊天的进度消息里写，页面长什么样看方案「功能与页面设计」",
        "problems": "卡在哪写成 events 里一条 status 为 blocked 的事件，detail 写原因、影响哪个功能、谁在处理、什么时候能继续",
    },
    "acceptance": {
        "results": "实际跑出的结果写进那一条条目的 seen；要他判断的写进 actual",
        "automation": "自动发生的那件事按它的验收条目写，挂到路径里到点开始的那一步",
        "costs": "每次花了多少、和估算比、要等多久写进跑它的那一条条目的 seen；总花费在聊天交接里说",
        "fix_log": "这一版改了什么、重测了哪几条写进 changes",
    },
}
RESULTS = ("通过", "没通过", "好不好你说了算", "未测")
NODE_STATES = {"pass": "通过", "fail": "没通过", "blocked": "受阻", "unknown": "未验证"}
UNTESTED = {
    # 类别：(原因原文, 这意味着, 要不要补 detail)。第二项只说没确认过什么，不请开发者去看、去试。
    "login": ("要用真实账号登录才看得到：平台登录身份", "按真实账号显示的内容没确认过", False),
    "bridge": ("要在 GoalfyMax 里打开才看得到：提醒、授权和付款窗口", "从提醒跳进应用、授权和付款这几处没确认过", False),
    "studio": ("要在 Studio 窗口里打开才看得到", "页面在 Studio 窗口里的样子没确认过，内容和演示一致", False),
    "cannot_run": ("演示版跑不起来", "页面上的操作没确认过", True),
    "not_placed": ("你说先不放到在线预览", "放到在线预览后的表现没确认过", False),
    "sample": ("缺你手上的样本", "用你的真实样本时的结果没确认过", True),
    "online_page": ("在线预览里的页面我打不开", "在线预览里页面能不能打开、保存和读取走不走得通没确认过", False),
    "schedule": ("到点触发要等真实时间", "到点会不会自动开始没确认过；发布并在「自动化」面板打开规则后才会自动跑", False),
    "catalog": ("从目录或分享打开要先发布", "使用者从目录或分享打开的样子没确认过", False),
    "cannot_fail": ("测试中造不出这种失败", "真遇到这种失败时页面怎么提示没确认过", True),
}
LAUNCH_TITLES = ("上线的版本", "④ 验过什么", "未测的", "实际花了多少", "发布会怎样", "发布要准备的", "你可以做的事")
# 给开发者看的文字里不该出现的词：词 → 改说什么
BANNED = {
    "冒泡": "「用测试数据跑一遍」",
    "真跑": "「用真实数据跑一遍」",
    "部署": "「放到在线预览」",
    "本机": "不提本地的事",
    "本地": "不提本地的事",
    "工单": "不提",
    "施工": "不提",
    "演练": "写清跑了什么、用的什么数据",
    "空跑": "写清跑了什么、用的什么数据",
    "替身": "写清是测试数据",
    "schema": "说成业务话",
    "project_id": "不写核对字段",
    "【填": "换成真实内容",
}
BANNED_WORDS = {"FA": "「模型步骤」", "TPE": "「这一步」或路线的业务名"}
EXEMPT_KEYS = {"evidence", "shots", "demo", "time", "id", "kind", "by", "status", "state", "tone", "result"}
DEMO_FORBIDDEN = [
    (r"<\s*form\b", "不用 <form>：Studio 会把整个表单删掉；用 div 包住，按钮绑 click"),
    (r"<\s*(iframe|object|embed|link|base|meta|style)\b", "Demo 里不放 iframe、link、style 这类标签，样式只用外壳里的类名和行内 style"),
    (r"<\s*script\b[^>]*\bsrc\s*=", "不引外部脚本"),
    (r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b", "不联网：Demo 只用页面里写好的示例数据"),
    (r"\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b", "不存东西：刷新或点「重置示例」就回到初始状态"),
    (r"\b(window\.parent|parent\.|window\.top|top\.location|opener|window\.open)\b", "不碰宿主窗口"),
    (r"\blocation\s*\.\s*(href|assign|replace)|\blocation\s*=", "不跳转页面"),
    (r"\bimport\s*\(", "不动态加载代码"),
    (r"https?://", "不引外部网址：图片用 data: 或纯 CSS 画"),
]
VOID_TAGS = {"input", "img", "br", "hr", "select", "textarea", "option"}


class Problems:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, where: str, msg: str) -> None:
        self.items.append(f"{where}：{msg}")


def e(value) -> str:
    """转义并把换行变成 <br>。"""
    return html.escape(str(value if value is not None else "")).replace("\n", "<br>")


def text(p: Problems, data: dict, key: str, where: str, required: bool = True, max_len: int | None = None) -> str:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            p.add(f"{where}.{key}", "必填，不能为空")
        return ""
    if not isinstance(value, (str, int, float)):
        p.add(f"{where}.{key}", "要写成一段文字")
        return ""
    value = str(value).strip()
    if max_len and len(value) > max_len:
        p.add(f"{where}.{key}", f"一行一项，最多 {max_len} 字（现在 {len(value)} 字）")
    return value


def items(p: Problems, data: dict, key: str, where: str, required: bool = True, min_len: int = 1) -> list:
    value = data.get(key)
    if value is None:
        if required:
            p.add(f"{where}.{key}", "必填")
        return []
    if not isinstance(value, list):
        p.add(f"{where}.{key}", "要写成列表 [...]")
        return []
    if required and len(value) < min_len:
        p.add(f"{where}.{key}", f"至少 {min_len} 项")
    return value


def scan_words(p: Problems, value, where: str) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in EXEMPT_KEYS:
                scan_words(p, v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            scan_words(p, v, f"{where}[{i}]")
    elif isinstance(value, str):
        for word, fix in BANNED.items():
            if word in value:
                p.add(where, f"开发者看得到这里，不写「{word}」，改成{fix}")
        for word, fix in BANNED_WORDS.items():
            if re.search(rf"(?<![A-Za-z]){word}(?![A-Za-z])", value):
                p.add(where, f"开发者看得到这里，不写「{word}」，改成{fix}")


def common(p: Problems, data: dict, doc_type: str) -> dict:
    app = text(p, data, "app", "data")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        p.add("data.version", "写整数版本号，第一版是 1，每保存一版加一")
        version = 0
    updated = text(p, data, "updated", "data")
    if updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", updated):
        p.add("data.updated", "写成 2026-11-05 14:20 这样的实际时间")
    changes = items(p, data, "changes", "data", required=isinstance(version, int) and version > 1)
    if isinstance(version, int) and version > 1 and not changes:
        p.add("data.changes", "第 2 版起写清这一版改了什么，一条一句")
    return {"app": app, "version": version, "updated": updated, "changes": changes, "name": DOC_NAMES[doc_type]}


def head(c: dict, eyebrow: str, h1: str, lead: str, tag: str = "") -> str:
    out = [f'<main class="doc"><div class="eyebrow">{e(eyebrow)}</div>',
           f'<div class="doc-head"><div><h1>{e(h1)}</h1><p class="lead">{e(lead)}</p></div>{tag}</div>',
           f'<div class="meta">{e(c["app"])} · 第 {c["version"]} 版 · 更新于 {e(c["updated"])}</div>']
    if c["changes"]:
        lis = "".join(f"<li>{e(x)}</li>" for x in c["changes"])
        out.append(f'<details class="changes" open><summary>这一版改了什么</summary><ul>{lis}</ul></details>')
    return "".join(out)


def foot(c: dict) -> str:
    return f'<div class="footer">{e(c["name"])} · 第 {c["version"]} 版 · 更新于 {e(c["updated"])}</div></main>'


def fold(title: str, body: str, open_: bool = False) -> str:
    return f'<details class="fold"{" open" if open_ else ""}><summary>{e(title)}</summary><div class="fold-body">{body}</div></details>'


def table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{e(h)}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def ul(values: list) -> str:
    return '<ul class="plain">' + "".join(f"<li>{e(v)}</li>" for v in values) + "</ul>"


def kv(pairs: list[tuple[str, str]]) -> str:
    return '<dl class="kv">' + "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in pairs if v) + "</dl>"


# ---------------- 需求说明 ----------------

def build_prd(p: Problems, d: dict) -> str:
    c = common(p, d, "prd")
    ov = d.get("overview") or {}
    rows = []
    for key, label in (("audience", "服务对象"), ("problem", "业务问题"), ("goal", "建设目标"), ("approach", "设计思路")):
        rows.append(f'<div class="row"><small>{label}</small><p>{e(text(p, ov, key, "overview", max_len=60))}</p></div>')
    out = [head(c, "01 / 需求说明", c["app"], "给谁用、要解决什么，每一步谁来做。点流程图里的一步看详情。"),
           f'<div class="overview">{"".join(rows)}</div>']

    phases = items(p, d, "phases", "data")
    node_ids: dict[str, int] = {}
    graph_cols, tabs, edges, details, phase_heads = [], [], [], [], []
    n = 0
    for k, ph in enumerate(phases):
        where = f"phases[{k}]"
        title = text(p, ph, "title", where)
        tabs.append(f'<button type="button" data-phase="{k}" aria-pressed="false">{k + 1:02d} {e(title)}</button>')
        verified = text(p, ph, "verified", where)
        if verified and verified not in ("已试过，能做", "能做", "要新做，没试过", "做不到，见替代"):
            p.add(f"{where}.verified", "只写四种之一：已试过，能做 / 能做 / 要新做，没试过 / 做不到，见替代")
        evidence = text(p, ph, "evidence", where)
        vtag = f'<span class="tag {"warn" if "没试过" in verified or "做不到" in verified else ""} verified" title="{e(evidence)}">{e(verified)}</span>'
        phase_heads.append(f'<p class="muted" style="font-size:12px">{vtag} {e(evidence)}</p>')
        col_nodes = []
        ph_nodes = items(p, ph, "nodes", where)
        first = n
        for j, node in enumerate(ph_nodes):
            w = f"{where}.nodes[{j}]"
            nt = text(p, node, "title", w)
            by = node.get("by")
            if by not in BY:
                p.add(f"{w}.by", "只写 user（使用者）、app（应用自动处理）、ai（AI）")
                by = "app"
            if nt in node_ids:
                p.add(f"{w}.title", f"节点名「{nt}」重复了，回环要按名字找节点")
            node_ids[nt] = n
            pairs = [("输入", text(p, node, "input", w)), ("输出", text(p, node, "output", w)),
                     ("重要信息", text(p, node, "rule", w)), ("做不成时", text(p, node, "fail", w, required=False))]
            if by == "ai":
                pairs.append(("用哪一档、每次约", f'{text(p, node, "tier", w)} · {text(p, node, "cost", w)}'))
            sub = f"{title} · {BY[by]}"
            grid = "".join(f"<section><h4>{e(a)}</h4><p>{e(b)}</p></section>" for a, b in pairs if b)
            details.append((k, (f'<details data-detail="{n}"><summary>{n + 1:02d} {e(nt)} <small>{e(BY[by])}</small></summary>'
                                f'<div class="detail-src" data-sub="{e(sub)}"><div class="detail-grid">{grid}</div></div></details>')))
            col_nodes.append(f'<button type="button" class="node by-{by}" data-node="{n}" data-phase="{k}" aria-pressed="false">'
                             f'<small><span><i class="dot {by}"></i>{e(BY[by])}</span><span>{n + 1:02d}</span></small><b>{e(nt)}</b></button>')
            if j > 0:
                edges.append({"from": n - 1, "to": n})
            n += 1
        if k > 0 and ph_nodes and first > 0:
            edges.append({"from": first - 1, "to": first})
        graph_cols.append(f'<div class="phase"><div class="phase-title"><span class="num">{k + 1:02d}</span>{e(title)} {vtag}</div><div class="nodes">{"".join(col_nodes)}</div></div>')
    for i, loop in enumerate(items(p, d, "loops", "data", required=False)):
        a, b = loop.get("from"), loop.get("to")
        if a not in node_ids or b not in node_ids:
            p.add(f"loops[{i}]", "from、to 要写成上面节点的名字（一字不差）")
            continue
        edges.append({"from": node_ids[a], "to": node_ids[b], "loop": True, "label": str(loop.get("label", ""))[:16]})
    cols = min(max(len(phases), 1), 4)
    legend = '<div class="legend"><span><i class="dot user"></i>使用者</span><span><i class="dot"></i>应用自动处理</span><span><i class="dot ai"></i>AI</span><span>虚线：返回或复用</span></div>'
    node_list = "".join(
        f'<section><h3 style="margin-top:14px">{k + 1:02d} {e(phases[k].get("title", ""))}</h3>{phase_heads[k]}'
        + "".join(h for kk, h in details if kk == k) + "</section>" for k in range(len(phases)))
    out.append(f'<section class="section"><div class="section-head"><h2>完整业务流程</h2></div>{legend}'
               f'<div class="phase-tabs">{"".join(tabs)}</div>'
               f'<div class="graph" style="--cols:{cols}"><svg class="edges" aria-hidden="true"></svg>{"".join(graph_cols)}</div>'
               f'<script type="application/json" id="graph-edges">{json.dumps(edges, ensure_ascii=False)}</script>'
               f'<div class="card node-panel" id="node-panel" hidden><div class="detail-head"><div><h3 class="panel-title"></h3><small class="panel-sub"></small></div>'
               f'<div class="detail-nav"><button type="button" id="node-prev" aria-label="上一个节点">←</button><button type="button" id="node-next" aria-label="下一个节点">→</button></div></div><div class="panel-body"></div></div>'
               f'<div class="node-list">{node_list}</div></section>')
    out.append(foot(c))
    return "".join(out)


# ---------------- 方案 ----------------

def inject_pins(src: str, where: str, p: Problems) -> tuple[str, list[int]]:
    found: list[int] = []

    def repl(m: re.Match) -> str:
        tag, num = m.group(1).lower(), int(m.group(3))
        if tag in VOID_TAGS:
            p.add(where, f"data-pin=\"{num}\" 放在了 <{tag}> 上，改放到包住它的元素上")
            return m.group(0)
        found.append(num)
        return m.group(0) + f'<span class="pin">{num}</span>'

    out = re.sub(r'<([a-zA-Z][a-zA-Z0-9]*)(\s[^<>]*?\bdata-pin="(\d+)"[^<>]*)>', repl, src)
    return out, found


def build_proposal(p: Problems, d: dict, base: Path) -> tuple[str, str]:
    c = common(p, d, "proposal")
    prd_v = d.get("prd_version")
    if not isinstance(prd_v, int):
        p.add("data.prd_version", "写依据的需求说明版本号（整数）")
    out = [head(c, "02 / 方案", "应用设计方案", "按业务过程看页面怎么用、每个编号是什么意思、最后得到什么。",
                f'<span class="tag accent">依据需求说明第 {e(prd_v)} 版</span>')]
    scope = d.get("scope") or {}
    route = items(p, scope, "route", "scope", min_len=2)
    out.append(fold("制作范围与预期产出", '<div class="route">' + "<i>→</i>".join(f"<span>{e(x)}</span>" for x in route) + "</div>"
                    + f'<p class="muted" style="margin-top:10px">{e(text(p, scope, "summary", "scope"))}</p>'))
    conds = d.get("conditions") or {}
    blocks = []
    for i, (key, q) in enumerate(CONDITION_KEYS):
        cd = conds.get(key)
        where = f"conditions.{key}"
        if not isinstance(cd, dict):
            p.add(where, "五件事都要写：data、account、cost、access、effects")
            continue
        now = text(p, cd, "now", where)
        impact = text(p, cd, "impact", where)
        decide, settled = cd.get("decide"), cd.get("settled")
        if bool(decide) == bool(settled):
            p.add(where, "decide（还要他定的问题）和 settled（已经定了的结论）只写一个")
        box = (f'<div class="decide settled"><b>已定</b><p>{e(settled)}</p></div>' if settled
               else f'<div class="decide"><b>需要你决定</b><p>{e(decide)}</p></div>')
        blocks.append(f'<article class="condition"><h3>{i + 1}. {e(cd.get("question") or q)}</h3><p class="now">{e(now)}</p><p class="impact">{e(impact)}</p>{box}</article>')
    out.append('<section class="section"><div class="section-head"><h2><span class="num">01</span>运行条件说明</h2></div>'
               '<p class="intro">真正用起来之前，要说清楚下面五件事。</p>' + "".join(blocks) + "</section>")

    feats = items(p, d, "features", "data")
    brand = d.get("brand") or {}
    brand_name = text(p, brand, "name", "brand")
    workspace = text(p, brand, "workspace", "brand", required=False) or "我的工作台"
    nav_pages = [str(f.get("page") or f.get("title") or "") for f in feats]
    jump = '<nav class="jump">' + "".join(f'<a href="#feature-{i}">{i + 1}. {e(x)}</a>' for i, x in enumerate(nav_pages)) + "</nav>"
    feat_html, scripts = [], []
    for i, f in enumerate(feats):
        where = f"features[{i}]"
        title = text(p, f, "title", where)
        how = text(p, f, "how", where)
        page = text(p, f, "page", where)
        demo_rel = text(p, f, "demo", where)
        demo_src, script = "", ""
        if demo_rel:
            path = (base / demo_rel).resolve()
            if not path.is_file():
                p.add(f"{where}.demo", f"找不到文件 {demo_rel}（相对 data.json 所在目录）")
            else:
                raw = path.read_text(encoding="utf-8")
                m = re.search(r"<script>([\s\S]*?)</script>\s*$", raw)
                if m:
                    script, raw = m.group(1), raw[: m.start()]
                if "<script" in raw:
                    p.add(f"{where}.demo", "Demo 里只能在文件最后放一个 <script>…</script>")
                for pat, why in DEMO_FORBIDDEN:
                    if re.search(pat, raw + script, re.IGNORECASE):
                        p.add(f"{where}.demo", why)
                demo_src, pins = inject_pins(raw, f"{where}.demo", p)
                notes_n = len(f.get("notes") or [])
                if sorted(set(pins)) != list(range(1, notes_n + 1)) or len(pins) != len(set(pins)):
                    p.add(f"{where}.demo", f"页面上的 data-pin 编号是 {sorted(pins)}，要和 notes 的条数对上：1 到 {notes_n} 各出现一次")
        notes = items(p, f, "notes", where, min_len=1)
        note_html = []
        for j, nt in enumerate(notes):
            w = f"{where}.notes[{j}]"
            extra = ""
            ins = nt.get("input") or []
            if j == 0:
                if not ins:
                    p.add(f"{w}.input", "第一条说明写输入：这一步要用到什么、从哪来、要什么授权（一条一句）")
                extra += "".join(f"<p>{'<b>输入：</b>' if k == 0 else ''}{e(x)}</p>" for k, x in enumerate(ins))
            elif ins:
                p.add(f"{w}.input", "只有第一条写输入，中间的只写操作说明")
            outp = nt.get("output")
            if j == len(notes) - 1:
                if not outp:
                    p.add(f"{w}.output", "最后一条说明写输出：做完得到什么、存在哪")
                extra += f"<p><b>输出：</b>{e(outp)}</p>" if outp else ""
            elif outp:
                p.add(f"{w}.output", "只有最后一条写输出")
            note_html.append(f'<div class="note" data-note="{j + 1}"><strong>{j + 1} · {e(text(p, nt, "title", w))}</strong><p>{e(text(p, nt, "text", w))}</p>{extra}</div>')
        ctx = f.get("context")
        ctx_html = ""
        if ctx:
            tone = "warn" if ctx.get("tone") == "warn" else "info"
            ctx_html = (f'<details class="context {tone}"><summary><span><b>{e(ctx.get("title"))}</b> · {e(ctx.get("impact"))}</span><span>{e(ctx.get("action", "查看"))} ⌄</span></summary>'
                        f'<div class="context-body">{ul(ctx.get("items") or [])}</div></details>')
        side = "".join(f'<a href="#feature-{k}" data-goto="{k}" class="{"current" if k == i else ""}">{e(x)}</a>' for k, x in enumerate(nav_pages))
        shell = (f'<div class="app-shell"><aside class="app-side"><div class="app-logo"><b>{e(brand_name[:1])}</b>{e(brand_name)}</div>{side}</aside>'
                 f'<div class="app-work"><div class="app-top"><span>{e(workspace)} / <strong>{e(page)}</strong></span><span>示例数据</span></div>'
                 f'<div class="app-body">{ctx_html}{demo_src}</div></div></div>')
        biz = kv([("做不成时", text(p, f, "fail", where)), ("完成后", text(p, f, "after", where)), ("例子", text(p, f, "example", where))])
        feat_html.append(
            f'<article class="feature" id="feature-{i}"><div class="feature-head"><div><h3><span class="num">2.{i + 1}</span>{e(title)}</h3><p>{e(how)}</p></div>'
            f'<button type="button" data-reset="{i}">↺ 重置示例</button></div>'
            f'<div class="demo-label"><span>完整页面示例</span><span>按栏宽缩放 · 可以直接点</span></div>'
            f'<div class="demo" data-demo="{i}"><div class="demo-stage">{shell}</div></div>'
            f'<div class="notes">{"".join(note_html)}</div>{fold("业务说明", biz)}</article>')
        if script.strip():
            scripts.append(f'<script>window.__studioDemos=window.__studioDemos||{{}};window.__studioDemos["{i}"]=function(root){{\n{script}\n}};</script>')
    out.append(f'<section class="section"><div class="section-head"><h2><span class="num">02</span>功能与页面设计</h2><small>{len(feats)} 个功能</small></div>'
               '<p class="intro">页面按使用顺序排。示例可以直接操作，用的是写好的示例数据，不连真实服务；每个编号对应下面一条说明。</p>'
               f'{jump}{"".join(feat_html)}</section>')

    # 验收条目只校验、不显示：页面上不出现，随 acceptance.json 一起保存
    acc = items(p, d, "acceptance", "data")
    ids = set()
    for i, a in enumerate(acc):
        w = f"acceptance[{i}]"
        aid = text(p, a, "id", w)
        if aid in ids:
            p.add(f"{w}.id", f"编号 {aid} 重复")
        ids.add(aid)
        judge = text(p, a, "judge", w)
        if judge and judge not in ("AI 能判断", "要人判断"):
            p.add(f"{w}.judge", "只写「AI 能判断」或「要人判断」")
        for key in ("who", "entry", "do", "get", "pass"):
            text(p, a, key, w)
    plan_file = base / "acceptance.json"
    if plan_file.is_file():
        try:
            plan = json.loads(plan_file.read_text(encoding="utf-8"))
            for cr in plan.get("crud") or []:
                if str(cr.get("id")) not in ids:
                    p.add("acceptance.json", f"crud 里的 {cr.get('id')} 在验收条目里找不到同编号的一条")
        except (json.JSONDecodeError, AttributeError) as exc:
            p.add("acceptance.json", f"不是合法 JSON：{exc}")
    else:
        p.add("acceptance.json", "方案要和 data.json 放在同一目录下的 acceptance.json 一起保存（格式见 studio_write_proposal 的说明）")
    out.append(foot(c))
    return "".join(out), "".join(scripts)


# ---------------- 制作进度 ----------------

def feature_done(f: dict) -> str:
    b, pg, da = f.get("backend"), f.get("page"), f.get("data")
    ok_b = str(b).startswith("做好了") or b == "不需要"
    ok_c = lambda x: x in ("做好了", "不需要")
    if ok_b and ok_c(pg) and ok_c(da):
        return "done"
    if all(x in ("没开始", "不需要") for x in (b, pg, da)):
        return "todo"
    return "doing"


def journal_side(p: Problems, d: dict, feats: list) -> str:
    """时间轴下面折叠的「交付范围与待明确条件」：原型里制作进度只有摘要、时间轴和这一块。"""
    word = {"done": "做好了", "doing": "在做", "todo": "没开始"}
    rows = "".join(f'<div class="dependency">{e(f.get("name"))}<small>{word[feature_done(f)]} · 后台 {e(f.get("backend"))} · 页面 {e(f.get("page"))} · 存数据 {e(f.get("data"))}</small></div>'
                   for f in feats if isinstance(f, dict))
    diffs = items(p, d, "diffs", "data", required=False)
    if diffs:
        rows += "".join(f'<div class="dependency">和方案不一样<small>{e(x)}</small></div>' for x in diffs)
    out = f'<section><h3>本轮交付范围</h3>{rows}</section>'
    pend = items(p, d, "pending", "data", required=False)
    for i, x in enumerate(pend):
        text(p, x, "what", f"pending[{i}]")
        text(p, x, "affects", f"pending[{i}]")
    if pend:
        out += '<section><h3>仍需明确的条件</h3>' + "".join(f'<div class="dependency">{e(x.get("what"))}<small>影响：{e(x.get("affects"))}</small></div>' for x in pend) + "</section>"
    return f'<details class="journal-side"><summary>交付范围与待明确条件</summary>{out}</details>'


def build_progress(p: Problems, d: dict) -> str:
    c = common(p, d, "progress")
    feats = items(p, d, "features", "data")
    for i, f in enumerate(feats):
        w = f"features[{i}]"
        text(p, f, "name", w)
        if f.get("backend") not in BACKEND_STATES:
            p.add(f"{w}.backend", "只写：" + " / ".join(BACKEND_STATES))
        for key in ("page", "data"):
            if f.get(key) not in CELL_STATES:
                p.add(f"{w}.{key}", "只写：" + " / ".join(CELL_STATES))
    states = [feature_done(f) for f in feats]
    done, doing, todo = states.count("done"), states.count("doing"), states.count("todo")
    total = len(feats)
    state = d.get("state")
    if state not in ("working", "done", "blocked"):
        p.add("data.state", "只写 working（在做）、done（都做完了）、blocked（卡住了）")
    if state == "done" and done != total:
        p.add("data.state", f"还有 {total - done} 个功能没做好，不能写 done")
    if state == "blocked" and not any(isinstance(ev, dict) and ev.get("status") == "blocked" for ev in d.get("events") or []):
        p.add("data.events", "写了卡住了，就要在时间轴上有一条 blocked 事件，detail 写卡在哪、影响哪个功能、谁在处理、什么时候能继续")
    label = {"working": "制作中", "done": "都做完了", "blocked": "卡住了"}.get(state, "")
    not_real = sum(1 for f in feats if f.get("backend") in ("做好了，只用模拟数据试过", "做好了，等在线预览时实际跑"))
    caveat = f"其中 {not_real} 个的后台还没用真实数据跑过。" if not_real else ""
    caveat += "做好了不等于验收通过，验收结果看验收报告。"
    now = d.get("now") or {}
    nxt = d.get("next") or {}
    out = [head(c, "03 / 制作进度", "制作进度", "按功能看做到哪，沿时间看做了什么。"),
           f'<section class="summary-card state-{e(state)}"><div class="summary-top"><span><i class="state-dot"></i>{label}</span><span>更新于 {e(c["updated"])}</span></div>'
           f'<h2>{e(text(p, now, "title", "now"))}</h2><p class="muted">{e(text(p, now, "detail", "now", required=False))}</p>'
           f'<div class="bigline"><b>{done}</b>/ {total} 个功能做好了 · {doing} 个在做 · {todo} 个没开始</div>'
           f'<div class="bar" style="--w:{round(done * 100 / total) if total else 0}%"><i></i></div>'
           f'<p class="muted" style="font-size:12px;margin-top:8px">{caveat}</p>'
           + (f'<div class="next"><small>下一步</small><div><b>{e(nxt.get("title"))}</b><p class="muted">{e(nxt.get("detail", ""))}</p></div></div>' if nxt.get("title") else "")
           + "</section>"]
    events = items(p, d, "events", "data")
    ev_html = []
    for i, ev in enumerate(events):
        w = f"events[{i}]"
        st = ev.get("status")
        if st not in EVENT_STATES:
            p.add(f"{w}.status", "只写 done（做完了）、doing（在做）、todo（没开始）、blocked（受阻，detail 写卡在哪）；"
                                 "整份卡住时另把 data.state 写成 blocked 并补 problems。不要因为这里报错就手写 index.html")
        tm = str(ev.get("time") or "")
        if st in ("done", "doing", "blocked") and not re.fullmatch(r"(\d{2}-\d{2} )?\d{2}:\d{2}", tm):
            p.add(f"{w}.time", "做过的事写实际时间（14:20 或 11-05 14:20），从工作记录里取，不估")
        subs = []
        for j, s in enumerate(ev.get("steps") or []):
            sst = s.get("status")
            if sst not in EVENT_STATES:
                p.add(f"{w}.steps[{j}].status", "只写 done、doing、todo、blocked")
            sym = {"done": "✓ 做完了", "doing": "◉ 在做", "todo": "○ 没开始", "blocked": "! 受阻"}.get(sst, "")
            subs.append(f'<div class="substep"><span><small>{e(s.get("time", ""))}</small> {e(s.get("title"))}</span><span>{sym}</span></div>')
        mark = {"done": "✓", "doing": "◉", "todo": "○", "blocked": "!"}.get(st, "")
        tag = {"done": '<span class="tag">做完了</span>', "doing": '<span class="tag warn">在做</span>', "todo": '<span class="tag unknown">没开始</span>',
               "blocked": '<span class="tag fail">受阻</span>'}.get(st, "")
        sub_html = f'<details{" open" if st in ("doing", "blocked") else ""}><summary>{len(subs)} 个小步骤</summary>{"".join(subs)}</details>' if subs else ""
        ev_html.append(f'<article class="event {e(st)}"><time>{e(tm or "—")}</time><div class="track"><span class="mark">{mark}</span></div>'
                       f'<div class="body"><h3>{e(text(p, ev, "title", w))} {tag}</h3><p>{e(text(p, ev, "detail", w))}</p>{sub_html}</div></article>')
    out.append('<section class="section"><div class="section-head"><h2>制作时间轴</h2><span><button type="button" data-play="progress">▶ 回放</button> '
               '<button type="button" data-stop="progress">停止</button></span></div>'
               f'<div class="timeline">{"".join(ev_html)}</div><p class="muted" style="font-size:12px">回放只按上面已有的记录走一遍。</p>'
               + journal_side(p, d, feats) + "</section>")
    out.append(foot(c))
    return "".join(out)


# ---------------- 验收报告 ----------------

def build_acceptance(p: Problems, d: dict, base: Path) -> tuple[str, list[str]]:
    c = common(p, d, "acceptance")
    its = items(p, d, "items", "data")
    by_id, shots_all = {}, []
    counts = {r: 0 for r in RESULTS}
    accepted = 0
    untested_list = []
    records = {}
    for i, it in enumerate(its):
        w = f"items[{i}]"
        iid = text(p, it, "id", w)
        if iid in by_id:
            p.add(f"{w}.id", f"编号 {iid} 重复")
        by_id[iid] = it
        title = text(p, it, "title", w)
        res = it.get("result")
        if res not in RESULTS:
            p.add(f"{w}.result", "只写：通过 / 没通过 / 好不好你说了算 / 未测")
            continue
        counts[res] += 1
        if res == "没通过" and it.get("accepted"):
            accepted += 1
        if res in ("通过", "没通过", "好不好你说了算"):
            for key in ("how", "seen", "evidence"):
                text(p, it, key, w)
        if res == "好不好你说了算" and not it.get("actual"):
            p.add(f"{w}.actual", "要你判断的条目附上实际结果原文（报告全文、内容原文、前后对比）")
        why_untested = ""
        if res == "未测":
            un = it.get("untested") or {}
            kind = un.get("kind")
            if kind not in UNTESTED:
                p.add(f"{w}.untested.kind", "未测只能是这几类：" + "、".join(UNTESTED))
            else:
                reason, later, need = UNTESTED[kind]
                if need and not un.get("detail"):
                    p.add(f"{w}.untested.detail", f"「{reason}」要补上具体情况（做过的处理和错误原文 / 哪一份样本 / 试过哪些做法）")
                why_untested = reason + ("：" + un["detail"] if un.get("detail") else "") + "。" + later
                untested_list.append(title)
        shot_html = ""
        for s in it.get("shots") or []:
            if not (base / s).is_file():
                p.add(f"{w}.shots", f"找不到截图 {s}（相对 data.json 所在目录）")
            elif not re.fullmatch(r"shots/[\w.-]+\.(png|jpg|jpeg|webp)", s):
                p.add(f"{w}.shots", "截图放在 shots/ 下，文件名只用字母数字和 - _ .，格式 png/jpg/webp")
            else:
                shots_all.append(s)
                shot_html += f'<img src="{e(s)}" alt="{e(title)} 的截图">'
        res_cls = {"通过": "pass", "没通过": "fail", "好不好你说了算": "judge", "未测": "untested"}[res]
        label = res + ("，你选了接受" if res == "没通过" and it.get("accepted") else "")
        pairs = [("怎么测的", it.get("how", "")), ("看到的结果", it.get("seen", "")), ("实际结果", it.get("actual", "")),
                 ("证据", it.get("evidence", "")), ("为什么没测", why_untested)]
        records[iid] = (f'<span class="item-record"><b>{e(title)}</b> <span class="result-{res_cls}">{e(label)}</span>{kv(pairs)}'
                        + (f'<span class="shots">{shot_html}</span>' if shot_html else "") + "</span>")
    for i, x in enumerate(items(p, d, "extra_untested", "data", required=False)):
        w = f"extra_untested[{i}]"
        kind = x.get("kind")
        if kind not in UNTESTED:
            p.add(f"{w}.kind", "未测只能是这几类：" + "、".join(UNTESTED))
            continue
        reason, later, need = UNTESTED[kind]
        if need and not x.get("detail"):
            p.add(f"{w}.detail", f"「{reason}」要补上具体情况")
        untested_list.append(f'{text(p, x, "title", w)}（{reason}{"：" + x["detail"] if x.get("detail") else ""}）')
        counts["未测"] += 1
    total = sum(counts.values())
    out = [head(c, "04 / 验收报告", "验收报告", "按业务路径看每一步走没走通，结论都有依据。")]
    stat = lambda cls, n_, label, sub: f'<div class="stat-card {cls}"><p>{label}</p><strong>{n_}</strong><p>{sub}</p></div>'
    untested_sub = "；".join(e(x) for x in untested_list) or "没有"
    out.append('<div class="stats">' + stat("fail", counts["没通过"], "没通过", f"其中你接受的 {accepted} 条") + stat("pass", counts["通过"], "通过", "")
               + stat("judge", counts["好不好你说了算"], "要你判断", "点路径里的那一步看实际结果") + stat("untested", counts["未测"], "未测", untested_sub)
               + f'</div><p style="margin-top:10px">共 {total} 条：没通过 {counts["没通过"]} · 通过 {counts["通过"]} · 要你判断 {counts["好不好你说了算"]} · 未测 {counts["未测"]}。{e(text(p, d, "impact", "data"))}</p>')
    paths = items(p, d, "paths", "data")
    plist, pflows = [], []
    shown = set()
    for i, pa in enumerate(paths):
        w = f"paths[{i}]"
        nodes = items(p, pa, "nodes", w, min_len=2)
        links = pa.get("links") or []
        if len(links) != max(len(nodes) - 1, 0):
            p.add(f"{w}.links", f"{len(nodes)} 个节点之间要写 {len(nodes) - 1} 句衔接")
        states = []
        n_html = []
        for j, nd in enumerate(nodes):
            nw = f"{w}.nodes[{j}]"
            st = nd.get("state")
            if st not in NODE_STATES:
                p.add(f"{nw}.state", "只写 pass、fail、blocked、unknown")
                st = "unknown"
            states.append(st)
            refs = nd.get("items") or []
            shown.update(refs)
            if st in ("pass", "fail") and not refs:
                p.add(f"{nw}.items", "通过、没通过的节点要写依据哪几条验收条目（编号）")
            for r in refs:
                if r not in by_id:
                    p.add(f"{nw}.items", f"条目 {r} 不在 items 里")
                elif st == "pass" and by_id[r].get("result") != "通过":
                    p.add(f"{nw}.state", f"标了通过，但条目 {r} 的结论是「{by_id[r].get('result')}」")
            if st == "fail" and refs and not any(by_id.get(r, {}).get("result") == "没通过" for r in refs):
                p.add(f"{nw}.state", "标了没通过，依据的条目里要有一条结论是「没通过」")
            if st in ("blocked", "unknown") and not nd.get("note"):
                p.add(f"{nw}.note", "受阻、未验证的节点写清为什么")
            ev = "".join(records.get(r, "") for r in refs)
            n_html.append(f'<button type="button" class="pnode {st}"><span>{j + 1:02d} {e(text(p, nd, "title", nw))}</span><span class="st">{NODE_STATES[st]}</span>'
                          f'<span class="node-ev"><span class="label">第 {j + 1} 步 · {NODE_STATES[st]}</span><b>{e(nd.get("title"))}</b><p>{e(nd.get("note", ""))}</p>{ev}</span></button>')
            if j < len(nodes) - 1 and j < len(links):
                nxt = nodes[j + 1].get("state", "unknown")
                n_html.append(f'<div class="plink {e(nxt)}">↓ {e(links[j])}</div>')
        overall = "fail" if "fail" in states else "blocked" if "blocked" in states else "unknown" if "unknown" in states else "pass"
        tag_cls = {"pass": "", "fail": "fail", "blocked": "warn", "unknown": "unknown"}[overall]
        name = text(p, pa, "name", w)
        plist.append(f'<button type="button" data-path="{i}" aria-pressed="false"><span class="sdot {overall}"></span>{e(name)}<small>{NODE_STATES[overall]}</small></button>')
        detail = e(text(p, pa, "detail", w))
        pflows.append(f'<div class="path-flow" data-path="{i}"><div class="path-title"><b>{e(name)}</b><span class="tag {tag_cls}">{NODE_STATES[overall]}</span></div>'
                      f'{"".join(n_html)}<div class="evidence-box"><p>{detail}</p></div><div class="path-detail-src" hidden><p>{detail}</p><small class="muted">点任意一步看依据。</small></div></div>')
    for iid in by_id:
        if iid not in shown:
            p.add("data.paths", f"条目 {iid} 没挂到任何一步上，页面上看不到它；写进它验证的那一步的 items")
    out.append('<section class="section"><div class="section-head"><h2>业务路径检查</h2><span><button type="button" data-play="paths">▶ 回放这条路径</button> '
               '<button type="button" data-stop="paths">停止</button></span></div>'
               f'<div class="checks"><div class="path-list">{"".join(plist)}</div><div>{"".join(pflows)}</div></div>'
               '<p class="muted" style="font-size:12px;margin-top:8px">回放只按已有的验收记录走一遍，不是重新测试。</p></section>')
    launch = d.get("launch")
    if launch:
        li = launch.get("items") or []
        titles = tuple(x.get("title") for x in li)
        if titles != LAUNCH_TITLES:
            p.add("launch.items", "上线结果按顺序写这七项：" + "、".join(LAUNCH_TITLES))
        out.append('<section class="section"><div class="section-head"><h2>上线结果</h2></div>'
                   + table(["项", "内容"], [[e(x.get("title")), e(x.get("text"))] for x in li]) + "</section>")
    out.append(foot(c))
    return "".join(out), shots_all


# ---------------- 入口 ----------------

def extract(path: Path, out_dir: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="doc-data">([\s\S]*?)</script>', raw)
    if not m:
        print("这份 index.html 里没有数据块，不是用 build_studio_doc.py 生成的", file=sys.stderr)
        return 1
    data = json.loads(m.group(1).replace("<\\/", "</"))
    sources = data.pop("_demo_sources", {})
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, src in sources.items():
        target = (out_dir / rel).resolve()
        if out_dir.resolve() not in target.parents:
            print(f"跳过不在目录内的 Demo 路径 {rel}", file=sys.stderr)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(src, encoding="utf-8")
    (out_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已取回 {out_dir / 'data.json'}" + (f" 和 {len(sources)} 个 Demo 文件" if sources else ""))
    return 0


SHOT_JS = r"""
const { chromium } = require('@playwright/test');
(async () => {
  const [file, outDir] = process.argv.slice(1);
  const browser = await chromium.launch();
  let bad = 0;
  for (const w of [400, 900]) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    const errs = [];
    page.on('pageerror', e => errs.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await page.goto('file://' + file);
    await page.waitForTimeout(800);
    for (const b of await page.$$('[data-reset]')) { await b.click(); }
    await page.waitForTimeout(300);
    const out = `${outDir}/shot-${w}.png`;
    await page.screenshot({ path: out, fullPage: true });
    console.log(`${w}px：${out}` + (errs.length ? `；页面脚本报错：${errs.join(' | ')}` : ''));
    if (errs.length) bad = 1;
    await page.close();
  }
  await browser.close();
  process.exit(bad);
})().catch(e => { console.error('截图失败：' + e.message); process.exit(2); });
"""


def shot(index: Path, frontend: Path) -> int:
    import subprocess

    out_dir = index.parent / ".shots"
    out_dir.mkdir(exist_ok=True)
    try:
        run = subprocess.run(["node", "-e", SHOT_JS, str(index.resolve()), str(out_dir.resolve())],
                             cwd=frontend, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"截图没跑成：{exc}", file=sys.stderr)
        return 2
    print((run.stdout + run.stderr).strip())
    if run.returncode == 2:
        print("前端目录里要有 @playwright/test 和浏览器（npx playwright install chromium）；截不了图时按检查清单逐条读生成的页面", file=sys.stderr)
    return run.returncode


MARK_RE = re.compile(r'<meta name="studio-doc" content="(prd|proposal|progress|acceptance);sha256=([0-9a-f]{64})">')


def marker(doc_type: str, page: str) -> str:
    """生成标记：页面其余部分的 sha256。手写或手改过的页面对不上。"""
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
    return f'<meta name="studio-doc" content="{doc_type};sha256={digest}">'


def verify(index: Path) -> int:
    page = index.read_text(encoding="utf-8")
    m = MARK_RE.search(page)
    if not m:
        print(f"{index} 不是 build_studio_doc.py 生成的（没有标记），不能保存：改 data.json 后重新生成", file=sys.stderr)
        return 1
    if hashlib.sha256(page.replace(m.group(0), "", 1).encode("utf-8")).hexdigest() != m.group(2):
        print(f"{index} 生成后被改过，不能保存：改 data.json 后重新生成", file=sys.stderr)
        return 1
    print(f"{index} 是生成的{DOC_NAMES[m.group(1)]}，没被改过")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "verify":
        return verify(Path(argv[1]))
    if len(argv) >= 3 and argv[0] == "extract":
        return extract(Path(argv[1]), Path(argv[2]))
    if len(argv) >= 3 and argv[0] == "shot":
        return shot(Path(argv[1]), Path(argv[2]))
    if len(argv) < 2 or argv[0] not in DOC_TYPES:
        print(__doc__, file=sys.stderr)
        return 2
    doc_type, data_path = argv[0], Path(argv[1]).resolve()
    out_path = Path(argv[argv.index("-o") + 1]).resolve() if "-o" in argv else data_path.parent / "index.html"
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读不了 {data_path}：{exc}", file=sys.stderr)
        return 1
    p = Problems()
    base = data_path.parent
    demos, shots = "", []
    if doc_type == "prd":
        body = build_prd(p, data)
    elif doc_type == "proposal":
        body, demos = build_proposal(p, data, base)
    elif doc_type == "progress":
        body = build_progress(p, data)
    else:
        body, shots = build_acceptance(p, data, base)
    scan_words(p, data, "data")
    for key, where_to in MOVED_KEYS.get(doc_type, {}).items():
        if key in data:
            p.add(f"data.{key}", f"这一项不在{DOC_NAMES[doc_type]}里显示，删掉：{where_to}")
    if out_path.is_file():
        m = re.search(r'<script type="application/json" id="doc-data">([\s\S]*?)</script>', out_path.read_text(encoding="utf-8"))
        if m:
            try:
                old_v = json.loads(m.group(1).replace("<\\/", "</")).get("version")
                if isinstance(old_v, int) and isinstance(data.get("version"), int) and data["version"] < old_v:
                    p.add("data.version", f"上一次生成的是第 {old_v} 版，版本号不能变小")
            except json.JSONDecodeError:
                pass
    if p.items:
        print(f"{DOC_NAMES[doc_type]}有 {len(p.items)} 处要改，改完再跑：")
        for x in p.items:
            print("  ✗ " + x)
        return 1
    shell = SHELL.read_text(encoding="utf-8")
    stored = dict(data)
    if doc_type == "proposal":
        stored["_demo_sources"] = {f["demo"]: (base / f["demo"]).read_text(encoding="utf-8") for f in data.get("features", []) if f.get("demo")}
    payload = json.dumps(stored, ensure_ascii=False).replace("</", "<\\/")
    page = (shell.replace("<!--TITLE-->", html.escape(f'{DOC_NAMES[doc_type]} · {data["app"]}'))
            .replace("<!--BODY-->", body).replace("<!--DEMOS-->", demos).replace("<!--DATA-->", payload))
    page = page.replace("<head>", "<head>" + marker(doc_type, page), 1)
    out_path.write_text(page, encoding="utf-8")
    files = ["index.html"] + (["acceptance.json"] if doc_type == "proposal" else []) + shots
    size = sum((out_path.parent / f).stat().st_size for f in files if (out_path.parent / f).is_file())
    print(f"已生成 {out_path}（{len(page.encode('utf-8')) // 1024} KB）")
    print("studio_write_proposal 的 files 放：" + "、".join(files) + f"（合计 {size // 1024} KB，上限 8 MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
