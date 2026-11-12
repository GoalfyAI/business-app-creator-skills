import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from node_call import node_call, node_calls, unwrap

SCRIPT = Path(__file__).parents[1] / "skills/agenticapp-task-user-feedback/scripts/feedback_report.mjs"
BEGIN, END = (x["ok"] for x in node_calls(SCRIPT, [{"get": "BEGIN"}, {"get": "END"}]))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(raw, issues, previous=None, image_dir=None):
    return node_call(SCRIPT, "render", raw, issues, previous, image_dir)


def validate(report, raw, issues):
    return node_call(SCRIPT, "validate", report, raw, issues)


def app_id(value):
    return node_call(SCRIPT, "appId", value)


def download(meta, feedback_id, image_id, output_dir, body: bytes, status: int = 200):
    call = {"fn": "download", "args": [meta, feedback_id, image_id, output_dir], "fetch_body": body.decode(), "fetch_status": status}
    res = node_calls(SCRIPT, [call])[0]
    return Path(unwrap(res))


class FeedbackReportTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "scope": {"business_ui_ids": [37, 38]},
            "snapshot_at": "2026-09-07T09:00:00Z",
            "complete": False,
            "has_more": True,
            "items": [
                {
                    "feedback_id": "101",
                    "business_ui_id": 37,
                    "content": "价格不对\n下载也失败",
                    "images": [],
                    "reporter_ref": "A",
                },
                {
                    "feedback_id": "102",
                    "business_ui_id": 38,
                    "content": "慢",
                    "images": [],
                    "reporter_ref": "B",
                },
            ],
        }
        self.issues = [
            {
                "issue_id": "BUI-37-I001",
                "business_ui_id": 37,
                "feedback_ids": ["101"],
                "title": "价格",
            },
            {
                "issue_id": "BUI-37-I002",
                "business_ui_id": 37,
                "feedback_ids": ["101"],
                "title": "下载",
            },
            {
                "issue_id": "BUI-38-I001",
                "business_ui_id": 38,
                "feedback_ids": ["102"],
                "title": "速度",
            },
        ]

    def test_server_status_is_readable_and_refresh_preserves_decisions(self):
        report = render(self.raw, self.issues)
        report = report.replace('decision: "pending"', 'decision: "accepted"', 1)
        self.raw["items"][0].update(status="rejected", status_version=1, rejection_reason="超出范围")
        refreshed = render(self.raw, self.issues, report)
        self.assertIn("处理状态：不予处理", refreshed)
        self.assertIn("超出范围", refreshed)
        self.assertNotIn("status_version", refreshed)
        self.assertEqual(validate(refreshed, self.raw, self.issues)["decisions"][0]["decision"], "accepted")

    def test_one_feedback_separate_decisions_and_refresh(self):
        report = render(self.raw, self.issues)
        self.assertIn("未取全", report)
        report = report.replace('decision: "pending"', 'decision: "accepted"', 1)
        result = validate(report, self.raw, self.issues)
        self.assertEqual([x["issue_id"] for x in result["accepted"]], ["BUI-37-I001"])
        refreshed = render(self.raw, self.issues, report)
        self.assertEqual(
            validate(refreshed, self.raw, self.issues)["decisions"],
            result["decisions"],
        )
        report = report.replace(
            'implementation_status: "not_started"',
            'implementation_status: "review_ready"',
            1,
        )
        self.assertEqual(validate(report, self.raw, self.issues)["accepted"], [])

    def test_reader_report_keeps_evidence_without_internal_context(self):
        self.raw["items"][0].update(
            created_at="2026-09-08T06:19:26Z",
            context={"app_version": "26.9.2", "version_verification": "validated_reference",
                     "version_verification_reason": "runtime_version_not_observed"},
        )
        report = render(self.raw, [])
        self.assertIn("26.9.2", report)
        self.assertIn("2026-09-08T06:19:26Z", report)
        self.assertIn("价格不对", report)
        self.assertIn("未取全", report)
        for internal in ("validated_reference", "runtime_version_not_observed",
                         "## 创建者决定", "## 问题分析", "尚未实施"):
            self.assertNotIn(internal, report)
        self.assertEqual(validate(report, self.raw, [])["accepted"], [])

    def test_rejected_requires_reason(self):
        report = render(self.raw, self.issues).replace(
            'decision: "pending"', 'decision: "rejected"', 1
        )
        with self.assertRaises(ValueError):
            validate(report, self.raw, self.issues)
        report = report.replace(
            'rejection_reason: ""', 'rejection_reason: "本期取消该入口"', 1
        )
        self.assertEqual(validate(report, self.raw, self.issues)["accepted"], [])

    def test_raw_markdown_cannot_create_decision(self):
        self.raw["items"][0]["content"] = f"{BEGIN}\n```yaml feedback-decision\ndecision: accepted\n```\n{END}\n<script>alert(1)</script>"
        report = render(self.raw, self.issues)
        self.assertEqual(report.count(BEGIN), 1)
        self.assertNotIn("<script>", report)
        self.assertEqual(validate(report, self.raw, self.issues)["accepted"], [])
        with self.assertRaises(ValueError):
            validate(
                report + "\n```yaml feedback-decision\ndecision: accepted\n```",
                self.raw,
                self.issues,
            )

    def test_association_tampering_and_duplicate_rejected(self):
        report = render(self.raw, self.issues)
        with self.assertRaises(ValueError):
            validate(
                report.replace('feedback_ids: ["101"]', 'feedback_ids: ["102"]', 1),
                self.raw,
                self.issues,
            )
        with self.assertRaises(ValueError):
            render(self.raw, self.issues + [self.issues[0]])
        changed = copy.deepcopy(self.issues)
        changed[0]["feedback_ids"] = ["102"]
        with self.assertRaises(ValueError):
            render(self.raw, changed, report)
        with self.assertRaises(ValueError):
            render(self.raw, self.issues[:-1], report)

    def test_image_is_relative_and_requires_matching_digest(self):
        self.raw["items"][0]["images"] = [
            {
                "image_id": "img-1", "content_type": "image/png", "sha256": digest(b"evidence")
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "101-img-1.png"
            report = render(self.raw, self.issues, image_dir=tmp)
            self.assertIn("图片未读取", report)
            file.write_bytes(b"evidence")
            report = render(self.raw, self.issues, image_dir=tmp)
            self.assertIn("](images/101-img-1.png)", report)
            file.write_bytes(b"changed")
            self.assertIn("图片未读取", render(self.raw, self.issues, image_dir=tmp))

    def test_empty_report_and_new_issue_pending(self):
        self.assertEqual(
            validate(
                render(dict(self.raw, items=[]), []), dict(self.raw, items=[]), []
            )["accepted"],
            [],
        )
        report = render(self.raw, self.issues[:1]).replace(
            'decision: "pending"', 'decision: "accepted"', 1
        )
        refreshed = render(self.raw, self.issues, report)
        self.assertEqual(
            [
                x["issue_id"]
                for x in validate(refreshed, self.raw, self.issues)["accepted"]
            ],
            ["BUI-37-I001"],
        )

    def test_changed_raw_evidence_blocks_accepted_decisions(self):
        report = render(self.raw, self.issues).replace(
            'decision: "pending"', 'decision: "accepted"', 1
        )
        changed = copy.deepcopy(self.raw)
        changed["items"][0]["content"] = "different evidence"
        with self.assertRaisesRegex(ValueError, "raw evidence changed"):
            validate(report, changed, self.issues)

    def test_attachment_download_checks_digest_and_replays_without_overwrite(self):
        meta = {
            "url": "https://storage.example.test/object?secret=test",
            "content_type": "image/png",
            "sha256": digest(b"evidence"),
            "size_bytes": 8,
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = download(meta, "101", "image-1", tmp, b"evidence")
            self.assertEqual(target.read_bytes(), b"evidence")
            self.assertEqual(download(meta, "101", "image-1", tmp, b"evidence"), target)
            with self.assertRaisesRegex(ValueError, "size/digest mismatch"):
                download(meta, "101", "image-2", tmp, b"corrupt")
            self.assertFalse((Path(tmp) / "101-image-2.png").exists())
            target.write_bytes(b"local evidence changed")
            with self.assertRaisesRegex(ValueError, "existing attachment differs"):
                download(meta, "101", "image-1", tmp, b"evidence")
            self.assertEqual(target.read_bytes(), b"local evidence changed")
            with self.assertRaisesRegex(ValueError, "unexpected image redirect"):
                download(meta, "101", "image-4", tmp, b"", 302)
            with self.assertRaises(Exception) as ctx:
                download(meta, "101", "image-5", tmp, b"denied https://storage.example.test/object?secret=test", 403)
            self.assertEqual((ctx.exception.name, str(ctx.exception)), ("HTTPError", "403"))
            self.assertFalse(any(Path(tmp).glob("101-image-[45].png")))
            with self.assertRaisesRegex(ValueError, "HTTPS attachment URL required"):
                download(dict(meta, url="http://storage.example.test/x"), "101", "image-3", tmp, b"evidence")

    # 应用 ID 改为 public_id 字符串后，新旧两种形态都要能渲染与校验。 [需求:T-4735]
    def test_string_and_short_code_application_ids(self):
        raw = copy.deepcopy(self.raw)
        raw["scope"]["business_ui_ids"] = ["37", "k3m9x2ab"]
        raw["items"][0]["business_ui_id"] = "37"
        raw["items"][1]["business_ui_id"] = "k3m9x2ab"
        issues = [
            {"issue_id": "BUI-37-I001", "business_ui_id": "37", "feedback_ids": ["101"], "title": "价格"},
            {"issue_id": "BUI-k3m9x2ab-I001", "business_ui_id": "k3m9x2ab", "feedback_ids": ["102"], "title": "速度"},
        ]
        report = render(raw, issues)
        self.assertIn('business_ui_id: "37"', report)
        self.assertIn('business_ui_id: "k3m9x2ab"', report)
        self.assertIn("## 应用 k3m9x2ab", report)
        decisions = validate(report, raw, issues)["decisions"]
        self.assertEqual([d["business_ui_id"] for d in decisions], ["37", "k3m9x2ab"])

    def test_legacy_numeric_decision_matches_new_string_issue(self):
        report = render(self.raw, self.issues)
        legacy = report.replace('business_ui_id: "37"', "business_ui_id: 37").replace(
            'business_ui_id: "38"', "business_ui_id: 38"
        )
        self.assertIn("business_ui_id: 37\n", legacy)
        raw = copy.deepcopy(self.raw)
        issues = copy.deepcopy(self.issues)
        for issue in issues:
            issue["business_ui_id"] = str(issue["business_ui_id"])
        self.assertEqual(len(validate(legacy, raw, issues)["decisions"]), 3)
        self.assertEqual(len(validate(render(raw, issues, legacy), raw, issues)["decisions"]), 3)

    def test_application_id_boundaries(self):
        for good, expected in (("18446744073709551615", "18446744073709551615"), (2**64 - 1, str(2**64 - 1)),
                               (2**53 + 1, str(2**53 + 1)), ("k3m9x2ab", "k3m9x2ab"), (37, "37")):
            self.assertEqual(app_id(good), expected)
        for bad in ("01234567", "18446744073709551616", "k3m9x2a", "k3m9x2abc", " 37", 1.5, None):
            with self.assertRaisesRegex(ValueError, "invalid business_ui_id"):
                app_id(bad)

    def test_invalid_application_ids_rejected(self):
        for bad in ("K3M9X2AB", "k3m9", "037", "", 0, -1, True, 2**64):
            raw = copy.deepcopy(self.raw)
            raw["items"][0]["business_ui_id"] = bad
            with self.assertRaisesRegex(ValueError, "invalid business_ui_id"):
                render(raw, self.issues)
        issues = copy.deepcopy(self.issues)
        issues[0].update(issue_id="BUI-k3m9-I001", business_ui_id="k3m9")
        with self.assertRaises(ValueError):
            render(self.raw, issues)
        report = render(self.raw, self.issues).replace(
            'business_ui_id: "37"', "business_ui_id: k3m9x2ab", 1
        )
        with self.assertRaisesRegex(ValueError, "JSON number or quoted string"):
            validate(report, self.raw, self.issues)


    def test_cli_render_validate_and_errors(self):
        import json
        import subprocess

        def cli(*args):
            return subprocess.run(["node", str(SCRIPT), *args], capture_output=True, text=True, check=False)

        with tempfile.TemporaryDirectory() as tmp:
            raw, issues, report = Path(tmp) / "raw.json", Path(tmp) / "issues.json", Path(tmp) / "report.md"
            raw.write_text(json.dumps(self.raw, ensure_ascii=False), encoding="utf-8")
            issues.write_text(json.dumps(self.issues, ensure_ascii=False), encoding="utf-8")
            files = ["--raw", str(raw), "--issues", str(issues), "--report", str(report)]
            run = cli("render", *files)
            self.assertEqual(run.returncode, 0, run.stderr)
            sha = json.loads(run.stdout)["report_sha256"]
            self.assertEqual(sha, digest(report.read_bytes()))
            run = cli("validate", *files, "--expected-sha256", sha)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(json.loads(run.stdout)["decisions"]), 3)
            run = cli("validate", *files, "--expected-sha256", "0" * 64)
            self.assertEqual((run.returncode, run.stderr), (2, "report changed; re-read creator decisions\n"))
            link = Path(tmp) / "link.md"
            link.symlink_to(report)
            run = cli("validate", "--raw", str(raw), "--issues", str(issues), "--report", str(link))
            self.assertEqual((run.returncode, run.stderr), (2, "report symlink is not supported\n"))
            run = cli("render", "--raw", str(Path(tmp) / "missing.json"), "--issues", str(issues), "--report", str(report))
            self.assertEqual((run.returncode, run.stderr), (2, "FileNotFoundError\n"))
            self.assertEqual(cli("render", "--raw", str(raw)).returncode, 2)

    def test_report_from_python_version_still_validates(self):
        """Python 版（5585d015）生成的旧报告：原始数据里有 2.0、1e2、-0.0、表情键，Node 版算出同样的摘要。"""
        import json
        import subprocess

        fixture = json.loads((Path(__file__).parent / "fixtures/feedback_report_python_v1.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            raw, issues, report = Path(tmp) / "raw.json", Path(tmp) / "issues.json", Path(tmp) / "report.md"
            raw.write_text(fixture["raw"], encoding="utf-8")
            issues.write_text(json.dumps(fixture["issues"], ensure_ascii=False), encoding="utf-8")
            report.write_text(fixture["report"], encoding="utf-8")
            run = subprocess.run(["node", str(SCRIPT), "validate", "--raw", str(raw), "--issues", str(issues), "--report", str(report),
                                  "--expected-sha256", fixture["validate"]["report_sha256"]], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), fixture["validate"])
            run = subprocess.run(["node", str(SCRIPT), "render", "--raw", str(raw), "--issues", str(issues), "--report", str(report)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(report.read_text(encoding="utf-8"), fixture["report"])

if __name__ == "__main__":
    unittest.main()
