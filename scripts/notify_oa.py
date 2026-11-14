#!/usr/bin/env python3
"""部署完成后的OA登记：失败留下原运行补登记凭据，不改变物理部署结果。"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

CALLBACK_URL = "https://oa.goalfyai.cn/internal/v1/deploy-reviews/flow-webhook"


def notify(stage: str, pipeline: str, run: str, directory: Path, opener=urllib.request.urlopen) -> dict:
    if (not pipeline.isascii() or not pipeline.isdigit() or int(pipeline) <= 0
            or not run.isascii() or not run.isdigit() or int(run) <= 0 or stage not in {"pre", "prod"}):
        return {"status": "pending", "reason_code": "CALLBACK_IDENTITY_INVALID", "stage": stage}
    event = {"pipeline_id": pipeline, "run_id": int(run), "stage": stage}
    receipt = {**event, "status": "pending", "reason_code": "CALLBACK_PENDING"}
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{pipeline}-{run}-{stage}.json"

    def save() -> None:
        # 先保留原运行身份；补登记只重放该事件，不执行部署脚本。
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False, encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False)
            temporary = Path(f.name)
        temporary.replace(path)

    save()
    request = urllib.request.Request(CALLBACK_URL, data=json.dumps(event).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener(request, timeout=10) as response:
            body = response.read(65537)
            payload = json.loads(body) if len(body) <= 65536 else None
            if response.status == 200 and isinstance(payload, dict) and payload.get("code") == 200:
                data = payload.get("data")
                if isinstance(data, dict) and data.get("skipped") is not None and data.get("skipped") != "duplicate":
                    receipt["reason_code"] = "CALLBACK_NOT_REGISTERED"
                else:
                    receipt.update(status="registered", reason_code="CALLBACK_REGISTERED")
            else:
                receipt["reason_code"] = "CALLBACK_RESPONSE_INVALID"
    except (OSError, TimeoutError, ValueError, urllib.error.HTTPError):
        # 不保存异常原文、请求头或响应正文，避免把网络凭据带进流水线和补偿文件。
        receipt["reason_code"] = "CALLBACK_UNAVAILABLE"
    save()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("pre", "prod"))
    args = parser.parse_args()
    directory = Path(os.environ.get("PROJECT_DIR", ".")) / ".oa-release-callbacks"
    try:
        receipt = notify(args.stage, os.environ.get("PIPELINE_ID", ""), os.environ.get("BUILD_NUMBER", ""), directory)
    except OSError:
        receipt = {"status": "pending", "reason_code": "CALLBACK_RECEIPT_UNAVAILABLE", "stage": args.stage}
    print(json.dumps({"oa_registration": receipt, "deployment_unchanged": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
