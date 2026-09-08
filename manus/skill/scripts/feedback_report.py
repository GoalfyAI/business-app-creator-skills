#!/usr/bin/env python3
"""T-3269: 本地反馈报告与决定校验；只写报告文件，不调用应用写接口。仅使用 Python 标准库。"""

from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

BEGIN = "<!-- feedback-decisions:v1 -->"
END = "<!-- /feedback-decisions:v1 -->"
FIELDS = {
    "issue_id",
    "business_ui_id",
    "feedback_ids",
    "decision",
    "rejection_reason",
    "developer_notes",
    "implementation_status",
}
STATES = {"not_started", "in_progress", "review_ready", "blocked"}
ID = re.compile(r"[1-9][0-9]{0,19}")
ISSUE = re.compile(r"BUI-([1-9][0-9]*)-I[0-9]{3,}")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literal(value):
    # 原文永远不是 Markdown 结构或 HTML。保留逐行原文；原字节另存 JSON。
    return "\n".join(
        "> "
        + html.escape(line, quote=True)
        .replace("`", "&#96;")
        .replace("*", "&#42;")
        .replace("_", "&#95;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("\\", "&#92;")
        for line in str(value).split("\n")
    )


def records(raw):
    result = {}
    for row in raw["items"]:
        key = row.get("feedback_id")
        if (
            not isinstance(key, str)
            or not ID.fullmatch(key)
            or int(key) > 2**64 - 1
            or key in result
        ):
            raise ValueError("invalid/duplicate feedback_id")
        app = row.get("business_ui_id")
        if type(app) is not int or not 0 < app <= 2**53 - 1:
            raise ValueError("invalid business_ui_id")
        if not isinstance(row.get("content"), str) or not isinstance(
            row.get("images"), list
        ):
            raise ValueError("missing original feedback")
        result[key] = row
    return result


def check_decision(d, source):
    if set(d) != FIELDS or not isinstance(d["issue_id"], str):
        raise ValueError("unknown decision format")
    m = ISSUE.fullmatch(d["issue_id"])
    app = d["business_ui_id"]
    if not m or type(app) is not int or int(m[1]) != app:
        raise ValueError("issue/application mismatch")
    ids = d["feedback_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(x, str) for x in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("invalid feedback_ids")
    if any(x not in source or source[x]["business_ui_id"] != app for x in ids):
        raise ValueError("feedback/application mismatch")
    if (
        d["decision"] not in ("pending", "accepted", "rejected")
        or d["implementation_status"] not in STATES
    ):
        raise ValueError("invalid decision/status")
    if any(not isinstance(d[x], str) for x in ("rejection_reason", "developer_notes")):
        raise ValueError("decision notes must be strings")
    if d["decision"] == "rejected" and not d["rejection_reason"].strip():
        raise ValueError("rejected requires a reason")
    if d["decision"] != "accepted" and d["implementation_status"] in (
        "in_progress",
        "review_ready",
    ):
        raise ValueError("unaccepted issue cannot be implemented")


def parse_decisions(text, source):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("missing/duplicate decision section")
    before, tail = text.split(BEGIN)
    area, after = tail.split(END)
    if "```yaml feedback-decision" in before + after:
        raise ValueError("decision block outside decision section")
    blocks = re.findall(r"^```yaml feedback-decision\n(.*?)\n```$", area, re.M | re.S)
    remainder = re.sub(
        r"^```yaml feedback-decision\n.*?\n```$", "", area, flags=re.M | re.S
    )
    if remainder.strip():
        raise ValueError("unknown content in decision section")
    result = {}
    for block in blocks:
        # 有意只支持模板的单层 YAML 子集：JSON 数组/引号字符串、整数与未加引号枚举。
        d = {}
        for line in block.splitlines():
            key, sep, value = line.partition(":")
            if not sep or key not in FIELDS or key in d:
                raise ValueError("invalid/duplicate decision field")
            value = value.strip()
            if not value:
                raise ValueError("use quoted empty string")
            if value[0] in '["' or key == "business_ui_id":
                d[key] = json.loads(value)
            elif re.fullmatch(r"[A-Za-z0-9_-]+", value):
                d[key] = value
            else:
                raise ValueError("use JSON quoted string for notes")
        check_decision(d, source)
        if d["issue_id"] in result:
            raise ValueError("duplicate issue_id")
        result[d["issue_id"]] = d
    return result


def validate(report, raw, issues):
    source = records(raw)
    source_hash = digest(
        json.dumps(
            raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    )
    if (
        report.count("<!-- feedback-source-sha256:") != 1
        or "<!-- feedback-source-sha256:" + source_hash + " -->" not in report
    ):
        raise ValueError("raw evidence changed; rebuild and re-read the report")
    decisions = parse_decisions(report, source)
    expected = {i["issue_id"]: i for i in issues}
    if len(expected) != len(issues) or decisions.keys() != expected.keys():
        raise ValueError("decision/issue inventory mismatch")
    for key, d in decisions.items():
        issue = expected[key]
        if (
            d["business_ui_id"] != issue["business_ui_id"]
            or d["feedback_ids"] != issue["feedback_ids"]
        ):
            raise ValueError("decision associations changed")
    return {
        "report_sha256": digest(report.encode()),
        "accepted": [
            d
            for d in decisions.values()
            if d["decision"] == "accepted"
            and d["implementation_status"] != "review_ready"
        ],
        "decisions": list(decisions.values()),
    }


def render(raw, issues, previous=None, image_dir=None):
    source = records(raw)
    old = parse_decisions(previous, source) if previous is not None else {}
    decisions = []
    seen = set()
    source_hash = digest(
        json.dumps(
            raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    )
    scope = raw.get("scope", {})
    lines = [
        "# 业务应用用户反馈报告",
        "<!-- feedback-source-sha256:" + source_hash + " -->",
        "",
        literal("business_ui_id：" + ", ".join(map(str, scope.get("business_ui_ids", [])))),
        "",
        literal("使用范围：" + {"formal": "正式使用", "preview": "预览"}.get(
            scope.get("usage_mode", "formal"), "未提供"
        )),
        "",
        literal("截至：" + str(raw.get("snapshot_at", "未提供"))),
        "",
        "反馈数量：" + str(len(source)),
    ]
    for field, label in (("from", "开始时间"), ("to", "结束时间（不含）")):
        if scope.get(field):
            lines += ["", literal(label + "：" + str(scope[field]))]
    if raw.get("complete") is not True or raw.get("has_more") is not False:
        lines += ["", "反馈未取全，以下仅为已读取的内容。"]
    if not source:
        lines += ["", "本次查询未读取到反馈。"]
    group = None
    for issue in sorted(
        issues,
        key=lambda i: (i["business_ui_id"], i.get("category", "待分类"), i["issue_id"]),
    ):
        current = (issue["business_ui_id"], issue.get("category", "待分类"))
        if current != group:
            lines += [
                "",
                "## 应用 " + str(current[0]),
                literal("问题类型：" + current[1]),
            ]
            group = current
        key = issue["issue_id"]
        if key in seen:
            raise ValueError("duplicate issue_id")
        seen.add(key)
        decision = old.get(
            key,
            dict(
                issue_id=key,
                business_ui_id=issue["business_ui_id"],
                feedback_ids=issue["feedback_ids"],
                decision="pending",
                rejection_reason="",
                developer_notes="",
                implementation_status="not_started",
            ),
        )
        if (
            decision["business_ui_id"] != issue["business_ui_id"]
            or decision["feedback_ids"] != issue["feedback_ids"]
        ):
            raise ValueError(
                "existing issue associations changed; create a new pending issue"
            )
        check_decision(decision, source)
        decisions.append(decision)
        reporters = {source[x].get("reporter_ref") for x in issue["feedback_ids"]}
        reporters.discard(None)
        lines += [
            "",
            "### " + key,
            literal(issue.get("title", "待分类问题")),
            literal(
                "应用：%s；分类：%s；反馈：%s 条；已知独立用户：%s"
                % (
                    issue["business_ui_id"],
                    issue.get("category", "待分类"),
                    len(issue["feedback_ids"]),
                    len(reporters),
                )
            ),
            literal("来源：" + ", ".join(issue["feedback_ids"])),
        ]
        for field, label in (("analysis", "分析"), ("suggestion", "建议"),
                             ("implementation_result", "处理结果")):
            if issue.get(field):
                lines += ["", literal(label + "：" + issue[field])]
    if set(old) - seen:
        raise ValueError("refresh cannot discard existing decisions")
    if decisions:
        lines += ["", "## 创建者决定", "", "只编辑下方决定块；备注用 JSON 双引号字符串。"]
    lines += ["", BEGIN]
    for d in decisions:
        lines += (
            ["```yaml feedback-decision"]
            + [k + ": " + json.dumps(v, ensure_ascii=False) for k, v in d.items()]
            + ["```"]
        )
    lines += [END, "", "## 反馈原文"]
    for key, row in source.items():
        lines += [
            "",
            "### 反馈 " + key,
            "",
            literal("business_ui_id：" + str(row["business_ui_id"])),
            "",
            literal("提交时间：" + str(row.get("created_at", "未提供"))),
            "",
            literal("上报版本：" + str(row.get("context", {}).get("app_version", "未提供"))),
            "",
            literal(row["content"]),
            "",
        ]
        for im in row["images"]:
            ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(
                im.get("content_type")
            )
            iid = im.get("image_id", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", iid) or not ext:
                raise ValueError("invalid image metadata")
            name = key + "-" + iid + "." + ext
            file = Path(image_dir) / name if image_dir else None
            if (
                file
                and file.is_file()
                and not file.is_symlink()
                and digest(file.read_bytes()) == im.get("sha256")
            ):
                lines += ["![反馈图片](images/" + name + ")"]
            else:
                lines += ["图片未读取：" + iid]
    output = "\n".join(lines) + "\n"
    validate(output, raw, issues)
    return output


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unexpected image redirect; request a fresh attachment URL")


def download(metadata, feedback_id, image_id, output_dir):
    if not ID.fullmatch(feedback_id) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", image_id
    ):
        raise ValueError("invalid attachment identity")
    url = urllib.parse.urlsplit(metadata["url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("HTTPS attachment URL required")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(
        metadata.get("content_type")
    )
    if not ext or not re.fullmatch(r"[a-f0-9]{64}", metadata.get("sha256", "")):
        raise ValueError("invalid attachment metadata")
    with urllib.request.build_opener(NoRedirect).open(
        metadata["url"], timeout=30
    ) as response:
        body = response.read(10 * 1024 * 1024 + 1)
    if (
        len(body) > 10 * 1024 * 1024
        or digest(body) != metadata["sha256"]
        or len(body) != metadata["size_bytes"]
    ):
        raise ValueError("attachment size/digest mismatch")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (feedback_id + "-" + image_id + "." + ext)
    # 不覆盖已存在的本地证据；相同摘要重放可直接复用。
    if target.exists() or target.is_symlink():
        if target.is_symlink() or digest(target.read_bytes()) != metadata["sha256"]:
            raise ValueError("existing attachment differs")
    else:
        with target.open("xb") as f:
            f.write(body)
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for cmd in ("render", "validate"):
        s = sub.add_parser(cmd)
        s.add_argument("--raw", required=True)
        s.add_argument("--issues", required=True)
        s.add_argument("--report", required=True)
        if cmd == "validate":
            s.add_argument("--expected-sha256")
    s = sub.add_parser("download")
    for name in ("metadata", "feedback-id", "image-id", "output-dir"):
        s.add_argument("--" + name, required=True)
    a = p.parse_args()
    try:
        if a.command == "download":
            sys.stdout.write(
                str(download(load(a.metadata), a.feedback_id, a.image_id, a.output_dir))
                + "\n"
            )
            return
        report = Path(a.report)
        if report.is_symlink():
            raise ValueError("report symlink is not supported")
        previous = report.read_text(encoding="utf-8") if report.exists() else None
        raw, issues = load(a.raw), load(a.issues)
        if a.command == "render":
            content = render(raw, issues, previous, report.parent / "images")
            report.write_text(content, encoding="utf-8")
            sys.stdout.write(
                json.dumps({"report_sha256": digest(content.encode())}) + "\n"
            )
        else:
            result = validate(previous, raw, issues)
            if a.expected_sha256 and a.expected_sha256 != result["report_sha256"]:
                raise ValueError("report changed; re-read creator decisions")
            sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except Exception as exc:
        # HTTP 异常正文可能包含签名 URL；只输出异常类型，业务校验错误没有凭证。
        sys.stderr.write(
            (str(exc) if isinstance(exc, ValueError) else type(exc).__name__) + "\n"
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
