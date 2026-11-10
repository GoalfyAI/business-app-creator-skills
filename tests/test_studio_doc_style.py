"""Studio 开发文档外壳的样式和《四份开发文档样式规范清单》v2（B 版「文档」风格，陈羽杰 2026-11-06）比对。

清单第 3 节的 22 个固定色是外壳唯一能用的颜色；字体、字号层级、间距、圆角、阴影按清单第 1、2、4、5、6 节。
外壳里 v1 的规则还在前面，v2 的组件层接在后面覆盖，所以同一个选择器取最后一条比对。
外壳样式要改，先和陈羽杰确认并更新清单，再改这里的期望值。 [任务:T-5077]
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "skills" / "agenticapp-host-studio" / "assets" / "开发文档外壳.html"
BUILDER = ROOT / "skills" / "agenticapp-host-studio" / "scripts" / "build_studio_doc.py"

# 清单第 3 节：名称 → 值
SPEC_COLORS = {
    "ink": "#1f1d1a", "ink-2": "#3a3631", "muted": "#7a7268", "faint": "#a89f93",
    "page": "#fdfcfa", "surface": "#ffffff", "surface-2": "#f7f4ef", "surface-3": "#efeae2",
    "seg-bg": "#f2eee8", "border": "#e9e3da", "phase-border": "#e2dacd", "edge": "#d8d0c4",
    "accent": "#3b4ba8", "accent-soft": "#eef0fa",
    "ok": "#3f7a4f", "ok-soft": "#eef5ef", "ok-line": "#c6dccb",
    "warn": "#a3651b", "warn-soft": "#fbf3e6",
    "bad": "#b0413e", "bad-soft": "#faeceb", "fail": "#e3aaa8",
}
# 清单第 3、5 节：选中外圈和两种暖灰阴影
SPEC_RGBA = {"rgba(59,75,168,.14)", "rgba(60,45,20,.06)", "rgba(60,45,20,.25)"}
SERIF = '"Songti SC","STSong","Noto Serif CJK SC","Source Han Serif SC",serif'


def _css() -> str:
    text = SHELL.read_text(encoding="utf-8")
    return text[text.index("<style>") + 7 : text.index("</style>")]


def _norm(hex_color: str) -> str:
    h = hex_color.lower()
    return "#" + "".join(c * 2 for c in h[1:]) if len(h) == 4 else h


def _rule(css: str, selector: str) -> str:
    """同一选择器取最后一条（v2 组件层在后面）；@media 里的窄屏规则不算。"""
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    found = re.findall(r"(?:^|\})\s*" + re.escape(selector) + r"\{([^}]*)\}", css, re.MULTILINE)
    assert found, f"外壳里找不到样式规则 {selector}"
    return found[-1]


def test_shell_uses_only_spec_colors():
    text = SHELL.read_text(encoding="utf-8")
    used = {_norm(c) for c in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", text)}
    extra = used - set(SPEC_COLORS.values())
    assert not extra, f"外壳用了清单 22 色以外的颜色：{sorted(extra)}"
    rgba = set(re.findall(r"rgba\([^)]*\)", text))
    assert rgba <= SPEC_RGBA, f"外壳用了清单以外的透明色：{sorted(rgba - SPEC_RGBA)}"


def test_spec_has_22_colors():
    assert len(set(SPEC_COLORS.values())) == 22


def test_builder_writes_no_colors():
    text = BUILDER.read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9a-fA-F]{6}\b", text), "生成脚本里不写死颜色，用外壳的类名"


def test_root_variables_match_spec():
    root = _rule(_css(), ":root")
    for name, value in SPEC_COLORS.items():
        assert re.search(rf"--{re.escape(name)}:{value}(;|$)", root), f"--{name} 应为 {value}"


def test_shadows():
    root = _rule(_css(), ":root")
    assert "--card-shadow:none" in root, "内容卡片不加阴影"
    assert "--raise:0 1px 2px rgba(60,45,20,.06)" in root
    assert "--demo-shadow:0 12px 32px -18px rgba(60,45,20,.25)" in root


def test_fonts_and_type_scale():
    css = _css()
    root = _rule(css, ":root")
    assert '--font:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif' in root
    assert '--mono:ui-monospace,"SF Mono",Menlo,monospace' in root
    assert f"--h1-font:{SERIF}" in root and f"--h2-font:{SERIF}" in root
    assert "--h1:34px" in root and "--h1-weight:700" in root and "--h2:20px" in root
    body = _rule(css, "body")
    assert "14px/1.7" in body and '"tnum" 1' in body
    assert "var(--h1-font)" in _rule(css, ".doc-head h1")
    h2 = _rule(css, ".section-head h2")
    assert "var(--h2-font)" in h2 and "font-weight:700" in h2
    eyebrow = _rule(css, ".eyebrow")
    assert "font-size:11px" in eyebrow and "font-weight:500" in eyebrow and "var(--faint)" in eyebrow
    assert "font-size:15px" in _rule(css, ".doc-head .lead")
    assert "font-size:28px" in _rule(css, ".stat-card strong")
    num = _rule(css, ".num")
    assert "font-size:13px" in num and "var(--mono)" in num


def test_spacing_radius_and_components():
    css = _css()
    root = _rule(css, ":root")
    assert "--doc-w:860px" in root and "--gap:56px" in root
    assert "--radius:6px" in root and "--radius-sm:5px" in root and "--radius-lg:8px" in root
    assert "padding:36px 28px 80px" in _rule(css, ".doc")
    section = _rule(css, ".section")
    assert "border-top:1px solid var(--border)" in section and "padding-top:36px" in section
    pin = _rule(css, ".pin")
    for part in ("width:20px", "height:20px", "border-radius:999px", "var(--pin-bg)"):
        assert part in pin, f"编号标注缺 {part}"
    assert "border-top:1px solid var(--ink)" in _rule(css, ".overview")
    assert "var(--seg-bg)" in _rule(css, ".phase-tabs")
    assert "1px dashed var(--phase-border)" in _rule(css, ".phase")
    assert "border-bottom:1px solid var(--border)" in _rule(css, "details.fold")
    assert "grid-template-columns:76px" in _rule(css, ".event")


def test_narrow_rules():
    text = SHELL.read_text(encoding="utf-8")
    assert "narrow=w<700,base=narrow?640:1100" in text, "Demo 栏宽 <700px 按 640px 排版，≥700px 按 1100px"
    narrow = re.findall(r"@media\(max-width:520px\)\{(.*)\}", _css())[-1]
    assert "padding:22px 16px 60px" in narrow and "grid-template-columns:52px" in narrow
    assert ".overview .row{grid-template-columns:1fr" in narrow, "520px 以下概览字段名改到内容上方"
