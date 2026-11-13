#!/usr/bin/env python3
"""智能应用升级指南：读本 Skill 自带的 upgrade-guides/，按应用 docs/upgrade/history.json 算本次候选。

只用 Python 标准库；只读文件、只写标准输出。[需求:D-3962][R-438]

  candidates --app <应用根> [--sdk-major N]   本次升级的候选指南、reconsider、retired（《升级》第 1 步）
  baseline                    当前 Skill 自带的全部有效指南，供新建应用写指南基线
  check                       只校验指南目录（格式与关系），发布检查与测试共用

只取适用本次目标模板 SDK 主版本的指南（applies_to.sdk_major，不写按 5；--sdk-major 默认 5）。

指南不合规时整次失败（退出码 2，status=invalid_guide），不当成没有指南。
sha 是指南文件内容 sha256 的前 16 位，与已有应用 history.json 里记的 sha 同一算法。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = "upgrade-guides"
SCHEMA_FILE = "schema.json"
# 目录里不是指南的固定文件。
DIRECTORY_FILES = frozenset({"README.md", SCHEMA_FILE})
GUIDE_FILE_RE = re.compile(r"^D-[0-9]+\.md$")
DID_RE = re.compile(r"^D-[0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{16}$")
MAX_GUIDE_BYTES = 16 * 1024
RELATION_FIELDS = ("replaces", "withdraws", "depends_on")
# history.json 的 how：前三种（以及缺省）算已执行；not_applicable 进 reconsider；deferred/failed 不算处理过。
EXECUTED_HOWS = frozenset({"tested", "already_done", "baseline"})
APPLIED_HOWS = EXECUTED_HOWS | {"not_applicable", "deferred", "failed"}
UNSETTLED_HOWS = frozenset({"deferred", "failed"})
# 4.1 版本线已冻结，指南只适用 SDK 5.x；指南不写 applies_to.sdk_major 时按这个值。
DEFAULT_SDK_MAJOR = 5
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


class GuideError(Exception):
    """指南目录不合规：problems 为 [{file, field, code, message}]。"""

    def __init__(self, problems: list[dict]) -> None:
        super().__init__("; ".join(f"{p['file']} {p['field']}：{p['message']}" for p in problems[:10]))
        self.problems = problems


def guide_sha(data: bytes) -> str:
    """指南文件内容 sha256 的前 16 位：applied_guides 按 did+sha 记账。"""
    return hashlib.sha256(data).hexdigest()[:16]


def _did_number(did: str) -> int:
    return int(did[2:])


# ==================== 文件头 ====================

def _reject_constant(value: str):
    raise ValueError(f"非法数值 {value}")


# 换行判定与 Studio 原 check-upgrade-guides.mjs 的 /^```[ \t]*$/m 一致：\n、\r、 、  都算行结束，接受 CRLF。
_LINE_BREAKS = "\n\r  "
_CLOSING_FENCE = re.compile(rf"(?:^|(?<=[{_LINE_BREAKS}]))```[ \t]*(?=[{_LINE_BREAKS}]|\Z)")
_OPENING_FENCE = re.compile(r"```json[ \t]*\r?\n")


def parse_guide_header(text: str) -> tuple[Any, str | None]:
    """文件开头必须是 ```json 代码块；返回 (header, 错误)。"""
    opening = _OPENING_FENCE.match(text)
    if not opening:
        return None, "文件开头必须是 ```json 代码块"
    rest = text[opening.end():]
    closing = _CLOSING_FENCE.search(rest)
    if not closing:
        return None, "文件头 json 代码块没有结束的 ``` 行"
    try:
        return json.loads(rest[:closing.start()], parse_constant=_reject_constant), None
    except ValueError as exc:
        return None, f"文件头 JSON 解析失败：{exc}"


# ==================== schema.json（JSON Schema 子集） ====================
# 只实现 schema.json 用到的关键字；schema 里出现别的关键字时整体报 SCHEMA_INVALID，不静默忽略。

_SCHEMA_KEYWORDS = frozenset({
    "$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "type", "required", "properties",
    "additionalProperties", "enum", "const", "minLength", "pattern", "minItems", "uniqueItems", "items",
    "allOf", "if", "then",
})
_TYPES: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _schema_unsupported(node: Any, where: str = "#") -> list[str]:
    if isinstance(node, bool):
        return []
    if not isinstance(node, dict):
        return [f"{where} 不是对象或布尔值"]
    out = [f"{where}/{key}" for key in node if key not in _SCHEMA_KEYWORDS]
    for key in ("properties", "$defs"):
        for name, sub in (node.get(key) or {}).items():
            out += _schema_unsupported(sub, f"{where}/{key}/{name}")
    for key in ("items", "if", "then", "additionalProperties"):
        if key in node:
            out += _schema_unsupported(node[key], f"{where}/{key}")
    for index, sub in enumerate(node.get("allOf") or []):
        out += _schema_unsupported(sub, f"{where}/allOf/{index}")
    if "type" in node and node["type"] not in _TYPES:
        out.append(f"{where}/type={node['type']}")
    return out


def load_schema(guides_dir: Path) -> dict:
    """读 schema.json；缺失、不是 JSON 或用了本脚本不支持的关键字 → GuideError。"""
    file = f"{GUIDE_DIR}/{SCHEMA_FILE}"
    path = guides_dir / SCHEMA_FILE
    if not path.is_file():
        raise GuideError([{"file": file, "field": "(文件)", "code": "SCHEMA_MISSING", "message": "规则文件不存在"}])
    try:
        schema = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GuideError([{"file": file, "field": "(文件)", "code": "SCHEMA_INVALID", "message": f"不是合法 JSON：{exc}"}]) from None
    unsupported = _schema_unsupported(schema)
    if not isinstance(schema, dict) or unsupported:
        raise GuideError([{"file": file, "field": "(文件)", "code": "SCHEMA_INVALID",
                           "message": f"用了本脚本不支持的写法：{unsupported or ['顶层不是对象']}"}])
    return schema


def _resolve(root: dict, ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"只支持本文件内的 $ref：{ref}")
    node: Any = root
    for piece in ref[2:].split("/"):
        node = node[piece.replace("~1", "/").replace("~0", "~")]
    return node


def _json_equal(a: Any, b: Any) -> bool:
    # JSON 里 true 与 1 不相等，Python 里相等。
    return type(a) is type(b) and a == b if isinstance(a, bool) or isinstance(b, bool) else a == b


def schema_problems(instance: Any, schema: Any, root: dict | None = None, path: tuple = ()) -> list[tuple[list, str, str]]:
    """返回 [(字段路径, 关键字, 说明)]；required、additionalProperties、false 落到具体属性上。"""
    root = root if root is not None else schema
    if schema is True:
        return []
    if schema is False:
        return [(list(path), "false", "不允许出现")]
    out: list[tuple[list, str, str]] = []
    if "$ref" in schema:
        out += schema_problems(instance, _resolve(root, schema["$ref"]), root, path)
    expected = schema.get("type")
    if expected and not _TYPES[expected](instance):
        return out + [(list(path), "type", f"应为 {expected}")]
    if "enum" in schema and not any(_json_equal(instance, option) for option in schema["enum"]):
        out.append((list(path), "enum", f"取值 {json.dumps(instance, ensure_ascii=False)} 不在 {schema['enum']} 中"))
    if "const" in schema and not _json_equal(instance, schema["const"]):
        out.append((list(path), "const", f"必须是 {json.dumps(schema['const'], ensure_ascii=False)}"))
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            out.append((list(path), "minLength", f"至少 {schema['minLength']} 个字符"))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            out.append((list(path), "pattern", f"不符合 {schema['pattern']}"))
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            out.append((list(path), "minItems", f"至少 {schema['minItems']} 项"))
        if schema.get("uniqueItems"):
            seen: list[str] = []
            for item in instance:
                key = json.dumps(item, sort_keys=True)
                if key in seen:
                    out.append((list(path), "uniqueItems", "有重复项"))
                    break
                seen.append(key)
        if "items" in schema:
            for index, item in enumerate(instance):
                out += schema_problems(item, schema["items"], root, path + (index,))
    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                out.append((list(path) + [name], "required", "缺少必填字段"))
        properties = schema.get("properties", {})
        for name, value in instance.items():
            if name in properties:
                out += schema_problems(value, properties[name], root, path + (name,))
            elif schema.get("additionalProperties") is False:
                out.append((list(path) + [name], "additionalProperties", "不是约定字段"))
    for sub in schema.get("allOf", []):
        out += schema_problems(instance, sub, root, path)
    if "if" in schema and not schema_problems(instance, schema["if"], root, path) and "then" in schema:
        out += schema_problems(instance, schema["then"], root, path)
    return out


def format_field(path) -> str:
    text = ""
    for part in path:
        text = f"{text}[{part}]" if isinstance(part, int) else (f"{text}.{part}" if text else str(part))
    return text or "(文件头)"


def _describe_schema_problem(path: list, keyword: str, message: str, header: Any) -> tuple[str, str, str]:
    field = format_field(path)
    layers = header.get("applies_to", {}).get("layers") if isinstance(header, dict) and isinstance(header.get("applies_to"), dict) else None
    if (len(path) == 3 and path[:2] == ["applies_to", "layers"] and keyword == "enum" and isinstance(layers, list)
            and isinstance(path[2], int) and path[2] < len(layers) and layers[path[2]] == "studio"):
        return "LAYER_STUDIO", field, "layers 不能含 studio：只改 Studio 桌面端的 D 不写升级指南"
    if field == "tests" and keyword == "minItems":
        return "TESTS_REQUIRED", field, "impact 为 recommended 或 required 时至少要有 1 条测试"
    if keyword == "false" and path and path[0] == "tests":
        return "schema:false", field, "kind=command 只写 run，kind=check 只写 how"
    return f"schema:{keyword}", field, message


# ==================== 单份指南与关系 ====================

def check_guide_file(name: str, data: bytes, schema: dict) -> tuple[list[dict], Any]:
    """单份指南：大小、文件头、schema、文件名与 did、测试 id、只撤回与 impact=none 规则。返回 (问题, header)。"""
    file = f"{GUIDE_DIR}/{name}"
    problems: list[dict] = []

    def report(code: str, field: str, message: str) -> None:
        problems.append({"file": file, "field": field, "code": code, "message": message})

    if len(data) > MAX_GUIDE_BYTES:
        report("TOO_LARGE", "(文件)", f"文件 {len(data)} 字节，超过 {MAX_GUIDE_BYTES} 字节（16KB）上限")
    header, error = parse_guide_header(data.decode("utf-8", errors="replace"))
    if error:
        report("HEADER", "(文件头)", error)
        return problems, None
    for path, keyword, message in schema_problems(header, schema):
        report(*_describe_schema_problem(path, keyword, message, header))
    if not isinstance(header, dict):
        return problems, None
    if isinstance(header.get("did"), str) and header["did"] != name[:-3]:
        report("FILE_NAME", "did", f"文件名 {name} 与 did {header['did']} 不一致，应为 {header['did']}.md")
    if isinstance(header.get("tests"), list):
        seen: set[str] = set()
        for index, test in enumerate(header["tests"]):
            test_id = test.get("id") if isinstance(test, dict) else None
            if isinstance(test_id, str):
                if test_id in seen:
                    report("DUPLICATE_TEST_ID", f"tests[{index}].id", f"测试 id {test_id} 重复")
                seen.add(test_id)

    def items(key: str) -> list:
        value = header.get(key)
        return value if isinstance(value, list) else []

    withdraw_only = bool(items("withdraws")) and not items("replaces") and not items("actions")
    if withdraw_only and "impact" in header and header["impact"] != "none":
        report("WITHDRAW_ONLY_IMPACT", "impact", "只撤回旧指南、不要求应用修改的指南 impact 应为 none")
    if header.get("impact") == "none" and (items("actions") or not items("withdraws")):
        report("IMPACT_NONE_SCOPE", "impact", "impact=none 只用于撤回旧指南且应用无需修改：withdraws 不能为空，actions 应为空")
    return problems, header


def _strongly_connected(nodes: list[str], edges_of: Callable[[str], list[str]]) -> list[list[str]]:
    """长度大于 1 的强连通分量（迭代版 Tarjan）。"""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = 0
    for start in nodes:
        if start in index_of:
            continue
        work = [(start, iter(edges_of(start)))]
        index_of[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index_of:
                    index_of[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(edges_of(child))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index_of[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
    return components


def check_relations(headers: dict[str, dict], existing: set[str]) -> list[dict]:
    """replaces/withdraws/depends_on：不指向自己、目标文件存在、同一 D 只被一份指南替代或撤回、不成环。"""
    problems: list[dict] = []

    def file_of(stem: str) -> str:
        return f"{GUIDE_DIR}/{stem}.md"

    def targets(header: dict, key: str) -> list[str]:
        value = header.get(key)
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

    claimants: dict[str, list[tuple[str, str]]] = {}
    for stem, header in headers.items():
        for key in RELATION_FIELDS:
            for index, target in enumerate(targets(header, key)):
                field = f"{key}[{index}]"
                if target == stem:
                    problems.append({"file": file_of(stem), "field": field, "code": "REF_SELF", "message": f"{key} 不能指向自己 {target}"})
                elif target not in existing:
                    problems.append({"file": file_of(stem), "field": field, "code": "REF_MISSING",
                                     "message": f"{key} 指向的 {GUIDE_DIR}/{target}.md 不存在"})
                if key != "depends_on" and target != stem:
                    claimants.setdefault(target, []).append((stem, field))
    for target, claims in claimants.items():
        if len(claims) < 2:
            continue
        for stem, field in claims:
            others = "、".join(f"{s}.md 的 {f}" for s, f in claims if (s, f) != (stem, field))
            problems.append({"file": file_of(stem), "field": field, "code": "DOUBLE_SUCCESSION",
                             "message": f"{target} 同时被 {others} 替代或撤回；同一个 D 只能被一份指南 replaces 或 withdraws"})
    for name, keys in (("替代/撤回", ("replaces", "withdraws")), ("前置依赖", ("depends_on",))):
        def edges_of(stem: str, keys=keys) -> list[str]:
            return [t for key in keys for t in targets(headers[stem], key) if t != stem and t in headers]

        for component in _strongly_connected(list(headers), edges_of):
            members = set(component)
            for stem in component:
                for key in keys:
                    for index, target in enumerate(targets(headers[stem], key)):
                        if target != stem and target in members:
                            problems.append({"file": file_of(stem), "field": f"{key}[{index}]", "code": "REF_CYCLE",
                                             "message": f"{name}关系成环：{'、'.join(component)}"})
    return problems


def check_guide_set(files: dict[str, bytes], schema: dict) -> tuple[list[dict], dict[str, dict]]:
    """离线检查一组指南文件（文件名→内容）。返回 (问题, stem→header)。"""
    problems: list[dict] = []
    headers: dict[str, dict] = {}
    for name in sorted(files):
        file_problems, header = check_guide_file(name, files[name], schema)
        problems.extend(file_problems)
        if isinstance(header, dict):
            headers[name[:-3]] = header
    problems.extend(check_relations(headers, {name[:-3] for name in files}))
    return problems, headers


def load_guides(guides_dir: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    """读整个指南目录并校验；任何问题都抛 GuideError（整体不可用）。返回 (文件名→内容, did→header)。"""
    if not guides_dir.is_dir():
        raise GuideError([{"file": GUIDE_DIR, "field": "(目录)", "code": "DIR_MISSING", "message": "指南目录不存在"}])
    bad = [{"file": f"{GUIDE_DIR}/{path.name}", "field": "(文件)", "code": "UNEXPECTED_FILE",
            "message": f"{GUIDE_DIR}/ 只放 README.md、schema.json 和 <D编号>.md 指南文件"}
           for path in sorted(guides_dir.iterdir())
           if path.name not in DIRECTORY_FILES and not path.name.startswith(".") and path.name != "__pycache__"
           and (not path.is_file() or not GUIDE_FILE_RE.match(path.name))]
    if bad:
        raise GuideError(bad)
    schema = load_schema(guides_dir)
    files = {path.name: path.read_bytes() for path in guides_dir.iterdir() if GUIDE_FILE_RE.match(path.name)}
    problems, headers = check_guide_set(files, schema)
    if problems:
        raise GuideError(problems)
    return files, headers


# ==================== 应用记录 ====================

def read_history(app_root: Path) -> tuple[list[dict], str, list[dict]]:
    """读 docs/upgrade/history.json 的 applied_guides。返回 (条目, 文件状态, 警告)。

    文件状态：ok、missing（不存在）、broken（JSON 损坏或含合并冲突标记）、no_applied_guides。
    不合规的条目跳过并告警（对应指南会再作为候选返回）；deferred、failed 的条目不算处理过。
    """
    path = app_root / "docs" / "upgrade" / "history.json"
    if not path.is_file():
        return [], "missing", []
    text = path.read_text(encoding="utf-8", errors="replace")
    if any(line.startswith(CONFLICT_MARKERS) for line in text.splitlines()):
        return [], "broken", []
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return [], "broken", []
    raw = data.get("applied_guides") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return [], "no_applied_guides", []
    entries: list[dict] = []
    warnings: list[dict] = []
    for index, item in enumerate(raw):
        did, sha, how = (item.get(k) for k in ("did", "sha", "how")) if isinstance(item, dict) else (None, None, None)
        problem = None
        if not isinstance(item, dict):
            problem = "不是对象"
        elif not isinstance(did, str) or not DID_RE.match(did):
            problem = "did 不是 D-数字"
        elif how is not None and how not in APPLIED_HOWS:
            problem = f"how 只能是 {'|'.join(sorted(APPLIED_HOWS))}"
        elif sha is not None and (not isinstance(sha, str) or not SHA_RE.match(sha.lower())):
            problem = "sha 不是 16 位十六进制"
        elif sha is None and how not in (None, "baseline"):
            problem = "缺 sha（只有 how=baseline 的旧条目可以不带）"
        if problem:
            warnings.append({"code": "history_entry_invalid", "index": index,
                             "message": f"history.json applied_guides[{index}] {problem}，本次不算处理过"})
            continue
        if how in UNSETTLED_HOWS:
            continue
        entries.append({"did": did, "sha": sha.lower() if sha else None, "how": how})
    return entries, "ok", warnings


# ==================== 计算 ====================

def resolve_depends_on(did: str, declared: list[str], *, replaced_by: dict[str, str], withdrawn: set[str],
                       satisfied: set[str]) -> list[str]:
    """按替代/撤回解析 depends_on：应用已处理过原目标保留原目标；被替代追到替代链最终有效的那份；
    链上被撤回去掉；其余原样。解析到自己或重复的只保留一次、不保留自己。"""
    result: list[str] = []
    for target in declared:
        current: str | None = target
        if target not in satisfied:
            seen: set[str] = set()
            while current is not None and current not in seen:
                seen.add(current)
                if current in withdrawn:
                    current = None
                elif current in replaced_by:
                    current = replaced_by[current]
                else:
                    break
        if current is not None and current != did and current not in result:
            result.append(current)
    return result


def effective_dids(headers: dict[str, dict]) -> list[str]:
    """有效集合：没有被任何指南 replaces / withdraws 的指南（替代方后来自己被替代/撤回也不让原指南复活）。"""
    retired = {t for header in headers.values() for key in ("replaces", "withdraws") for t in header.get(key) or []}
    return sorted((did for did in headers if did not in retired), key=_did_number)


def _skill_version() -> str | None:
    skill = SKILL_ROOT / "SKILL.md"
    match = re.search(r"\[skill-version:([^\]\s]+)\]", skill.read_text(encoding="utf-8")) if skill.is_file() else None
    return match.group(1) if match else None


def _view(did: str, header: dict, data: bytes, deps: list[str], changed: bool) -> dict:
    return {
        "did": did, "title": header["title"], "impact": header["impact"], "applies_to": header["applies_to"],
        "already_done_check": header["already_done_check"], "actions": header.get("actions") or [],
        "tests": header.get("tests") or [], "replaces": header.get("replaces") or [],
        "withdraws": header.get("withdraws") or [], "depends_on": deps,
        "depends_on_declared": header.get("depends_on") or [],
        "sha": guide_sha(data), "sha256": hashlib.sha256(data).hexdigest(), "changed_since_applied": changed,
    }


def sdk_major_of(header: dict) -> int:
    return header["applies_to"].get("sdk_major", DEFAULT_SDK_MAJOR)


def candidates(guides_dir: Path, applied: list[dict], sdk_major: int = DEFAULT_SDK_MAJOR) -> dict:
    """本次候选：有效集合里适用 sdk_major、did+sha 没处理过的指南（按 did 数字排序），以及 reconsider、retired。"""
    files, headers = load_guides(guides_dir)
    retired_targets = {t for header in headers.values() for key in ("replaces", "withdraws") for t in header.get(key) or []}
    replaced_targets = {t for header in headers.values() for t in header.get("replaces") or []}
    replaced_by = {t: did for did, header in headers.items() for t in header.get("replaces") or []}
    withdrawn = {t for header in headers.values() for t in header.get("withdraws") or []}
    satisfied = {entry["did"] for entry in applied}
    by_did: dict[str, list[dict]] = {}
    for entry in applied:
        by_did.setdefault(entry["did"], []).append(entry)

    # retired：history 里可移除的 did（被替代、被撤回，或目录里已没有这份指南）。
    retired_reasons = []
    for did in sorted(by_did, key=_did_number):
        reason = ("replaced" if did in replaced_targets else "withdrawn" if did in retired_targets
                  else "file_deleted" if did not in headers else None)
        if reason:
            retired_reasons.append({"did": did, "reason": reason})

    guides: list[dict] = []
    reconsider: list[dict] = []
    for did in effective_dids(headers):
        header, data = headers[did], files[f"{did}.md"]
        if sdk_major_of(header) != sdk_major:
            continue
        sha = guide_sha(data)
        entries = by_did.get(did, [])
        if any(e["sha"] == sha and (e["how"] is None or e["how"] in EXECUTED_HOWS) for e in entries) \
                or any(e["sha"] is None and e["how"] in (None, "baseline") for e in entries):
            continue
        deps = resolve_depends_on(did, list(header.get("depends_on") or []), replaced_by=replaced_by,
                                  withdrawn=withdrawn, satisfied=satisfied)
        if any(e["sha"] == sha and e["how"] == "not_applicable" for e in entries):
            # 给完整内容：复核后转为候选时直接用，不再另读文件。
            reconsider.append(_view(did, header, data, deps, False))
            continue
        changed = any(e["sha"] is not None and e["sha"] != sha for e in entries)
        guides.append(_view(did, header, data, deps, changed))

    counts = {"required": 0, "recommended": 0, "none": 0, "changed_since_applied": 0}
    for view in guides:
        counts[view["impact"]] = counts.get(view["impact"], 0) + 1
        counts["changed_since_applied"] += view["changed_since_applied"]
    return {"status": "ok", "skill_version": _skill_version(), "sdk_major": sdk_major, "counts": counts, "guides": guides,
            "reconsider": reconsider, "retired": [r["did"] for r in retired_reasons],
            "retired_reasons": retired_reasons}


def baseline(guides_dir: Path, sdk_major: int = DEFAULT_SDK_MAJOR) -> dict:
    """当前 Skill 自带的、适用 sdk_major 的全部有效指南，写成 applied_guides 的 baseline 条目。"""
    files, headers = load_guides(guides_dir)
    return {"status": "ok", "skill_version": _skill_version(),
            "applied_guides": [{"did": did, "sha": guide_sha(files[f"{did}.md"]), "how": "baseline"}
                               for did in effective_dids(headers) if sdk_major_of(headers[did]) == sdk_major]}


# ==================== 命令行 ====================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--guides-dir", type=Path, default=SKILL_ROOT / GUIDE_DIR, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("candidates", help="本次升级的候选指南")
    plan.add_argument("--app", type=Path, required=True, help="应用根（含 docs/upgrade/history.json）")
    plan.add_argument("--sdk-major", type=int, default=DEFAULT_SDK_MAJOR,
                      help="本次目标模板的 SDK 主版本，只返回适用这个主版本的指南（默认 5）")
    sub.add_parser("baseline", help="全部有效指南的 baseline 条目")
    sub.add_parser("check", help="只校验指南目录")
    args = parser.parse_args(argv)
    try:
        if args.command == "candidates":
            applied, history, warnings = read_history(args.app)
            result = {**candidates(args.guides_dir, applied, args.sdk_major), "history": history, "warnings": warnings}
        elif args.command == "baseline":
            result = baseline(args.guides_dir)
        else:
            load_guides(args.guides_dir)
            result = {"status": "ok"}
    except GuideError as exc:
        print(json.dumps({"status": "invalid_guide", "problems": exc.problems}, ensure_ascii=False, indent=1))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
