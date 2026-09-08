import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import io

spec = importlib.util.spec_from_file_location(
    "feedback_report",
    Path(__file__).parents[1] / "skills/app-creator/scripts/feedback_report.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


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
            dict(
                issue_id="BUI-37-I001",
                business_ui_id=37,
                feedback_ids=["101"],
                title="价格",
            ),
            dict(
                issue_id="BUI-37-I002",
                business_ui_id=37,
                feedback_ids=["101"],
                title="下载",
            ),
            dict(
                issue_id="BUI-38-I001",
                business_ui_id=38,
                feedback_ids=["102"],
                title="速度",
            ),
        ]

    def test_server_status_is_readable_and_refresh_preserves_decisions(self):
        report = m.render(self.raw, self.issues)
        report = report.replace('decision: "pending"', 'decision: "accepted"', 1)
        self.raw["items"][0].update(status="rejected", status_version=1, rejection_reason="超出范围")
        refreshed = m.render(self.raw, self.issues, report)
        self.assertIn("处理状态：不予处理", refreshed)
        self.assertIn("超出范围", refreshed)
        self.assertNotIn("status_version", refreshed)
        self.assertEqual(m.validate(refreshed, self.raw, self.issues)["decisions"][0]["decision"], "accepted")

    def test_one_feedback_separate_decisions_and_refresh(self):
        report = m.render(self.raw, self.issues)
        self.assertIn("未取全", report)
        report = report.replace('decision: "pending"', 'decision: "accepted"', 1)
        result = m.validate(report, self.raw, self.issues)
        self.assertEqual([x["issue_id"] for x in result["accepted"]], ["BUI-37-I001"])
        refreshed = m.render(self.raw, self.issues, report)
        self.assertEqual(
            m.validate(refreshed, self.raw, self.issues)["decisions"],
            result["decisions"],
        )
        report = report.replace(
            'implementation_status: "not_started"',
            'implementation_status: "review_ready"',
            1,
        )
        self.assertEqual(m.validate(report, self.raw, self.issues)["accepted"], [])

    def test_reader_report_keeps_evidence_without_internal_context(self):
        self.raw["items"][0].update(
            created_at="2026-09-08T06:19:26Z",
            context={"app_version": "26.9.2", "version_verification": "validated_reference",
                     "version_verification_reason": "runtime_version_not_observed"},
        )
        report = m.render(self.raw, [])
        self.assertIn("26.9.2", report)
        self.assertIn("2026-09-08T06:19:26Z", report)
        self.assertIn("价格不对", report)
        self.assertIn("未取全", report)
        for internal in ("validated_reference", "runtime_version_not_observed",
                         "## 创建者决定", "## 问题分析", "尚未实施"):
            self.assertNotIn(internal, report)
        self.assertEqual(m.validate(report, self.raw, [])["accepted"], [])

    def test_rejected_requires_reason(self):
        report = m.render(self.raw, self.issues).replace(
            'decision: "pending"', 'decision: "rejected"', 1
        )
        with self.assertRaises(ValueError):
            m.validate(report, self.raw, self.issues)
        report = report.replace(
            'rejection_reason: ""', 'rejection_reason: "本期取消该入口"', 1
        )
        self.assertEqual(m.validate(report, self.raw, self.issues)["accepted"], [])

    def test_raw_markdown_cannot_create_decision(self):
        self.raw["items"][0]["content"] = "\n".join(
            [
                m.BEGIN,
                "```yaml feedback-decision",
                "decision: accepted",
                "```",
                m.END,
                "<script>alert(1)</script>",
            ]
        )
        report = m.render(self.raw, self.issues)
        self.assertEqual(report.count(m.BEGIN), 1)
        self.assertNotIn("<script>", report)
        self.assertEqual(m.validate(report, self.raw, self.issues)["accepted"], [])
        with self.assertRaises(ValueError):
            m.validate(
                report + "\n```yaml feedback-decision\ndecision: accepted\n```",
                self.raw,
                self.issues,
            )

    def test_association_tampering_and_duplicate_rejected(self):
        report = m.render(self.raw, self.issues)
        with self.assertRaises(ValueError):
            m.validate(
                report.replace('feedback_ids: ["101"]', 'feedback_ids: ["102"]', 1),
                self.raw,
                self.issues,
            )
        with self.assertRaises(ValueError):
            m.render(self.raw, self.issues + [self.issues[0]])
        changed = copy.deepcopy(self.issues)
        changed[0]["feedback_ids"] = ["102"]
        with self.assertRaises(ValueError):
            m.render(self.raw, changed, report)
        with self.assertRaises(ValueError):
            m.render(self.raw, self.issues[:-1], report)

    def test_image_is_relative_and_requires_matching_digest(self):
        self.raw["items"][0]["images"] = [
            dict(
                image_id="img-1", content_type="image/png", sha256=m.digest(b"evidence")
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "101-img-1.png"
            report = m.render(self.raw, self.issues, image_dir=tmp)
            self.assertIn("图片未读取", report)
            file.write_bytes(b"evidence")
            report = m.render(self.raw, self.issues, image_dir=tmp)
            self.assertIn("](images/101-img-1.png)", report)
            file.write_bytes(b"changed")
            self.assertIn("图片未读取", m.render(self.raw, self.issues, image_dir=tmp))

    def test_empty_report_and_new_issue_pending(self):
        self.assertEqual(
            m.validate(
                m.render(dict(self.raw, items=[]), []), dict(self.raw, items=[]), []
            )["accepted"],
            [],
        )
        report = m.render(self.raw, self.issues[:1]).replace(
            'decision: "pending"', 'decision: "accepted"', 1
        )
        refreshed = m.render(self.raw, self.issues, report)
        self.assertEqual(
            [
                x["issue_id"]
                for x in m.validate(refreshed, self.raw, self.issues)["accepted"]
            ],
            ["BUI-37-I001"],
        )

    def test_changed_raw_evidence_blocks_accepted_decisions(self):
        report = m.render(self.raw, self.issues).replace(
            'decision: "pending"', 'decision: "accepted"', 1
        )
        changed = copy.deepcopy(self.raw)
        changed["items"][0]["content"] = "different evidence"
        with self.assertRaisesRegex(ValueError, "raw evidence changed"):
            m.validate(report, changed, self.issues)

    def test_attachment_download_checks_digest_and_replays_without_overwrite(self):
        meta = dict(
            url="https://storage.example.test/object?secret=test",
            content_type="image/png",
            sha256=m.digest(b"evidence"),
            size_bytes=8,
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(m.urllib.request, "build_opener") as factory,
        ):
            factory.return_value.open.side_effect = lambda *a, **kw: io.BytesIO(
                b"evidence"
            )
            target = m.download(meta, "101", "image-1", tmp)
            self.assertEqual(target.read_bytes(), b"evidence")
            self.assertEqual(m.download(meta, "101", "image-1", tmp), target)
            factory.return_value.open.side_effect = lambda *a, **kw: io.BytesIO(
                b"corrupt"
            )
            with self.assertRaisesRegex(ValueError, "size/digest mismatch"):
                m.download(meta, "101", "image-2", tmp)
            self.assertFalse((Path(tmp) / "101-image-2.png").exists())
            factory.return_value.open.side_effect = lambda *a, **kw: io.BytesIO(
                b"evidence"
            )
            target.write_bytes(b"local evidence changed")
            with self.assertRaisesRegex(ValueError, "existing attachment differs"):
                m.download(meta, "101", "image-1", tmp)
            self.assertEqual(target.read_bytes(), b"local evidence changed")


if __name__ == "__main__":
    unittest.main()
