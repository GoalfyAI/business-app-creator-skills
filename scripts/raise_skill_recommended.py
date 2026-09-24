"""把某个环境 Hub 的 Skill 建议线抬到指定版本，强制线保持不变。 [任务:T-3784]

QA 分支每出一个候选版就调用一次：旧版本仍能建工单，只会收到升级提示。
策略接口是整体覆盖（PUT /api/internal/workflow/scene-skill-versions/policy），所以先读当前
强制线再写回。建议线只升不降：当前建议线已经是这个版本就跳过。

环境变量：HUB_URL（如 https://goalfyhub.qa.goalfyai.cn）、HUB_API_KEY、HUB_APP_ID、
HUB_OPERATOR_EMAIL、HUB_OPERATOR_ID。
用法：python3 scripts/raise_skill_recommended.py v20260924-39692d
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

POLICY_PATH = "/api/internal/workflow/scene-skill-versions/policy"
RELEASES_PATH = "/api/internal/workflow/scene-skill-versions/releases"


def request(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read() or b"{}")


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("用法：raise_skill_recommended.py <skill 版本>", file=sys.stderr)
        return 2
    version = sys.argv[1].strip()
    hub = os.environ["HUB_URL"].rstrip("/")
    headers = {
        "X-API-Key": os.environ["HUB_API_KEY"],
        "X-App-ID": os.environ.get("HUB_APP_ID", "goalfymax"),
        "X-Operator-Email": os.environ["HUB_OPERATOR_EMAIL"],
        "X-Operator-ID": os.environ["HUB_OPERATOR_ID"],
        "X-User-ID": os.environ["HUB_OPERATOR_ID"],
        "Content-Type": "application/json",
    }
    payload = request("GET", hub + RELEASES_PATH, headers)
    data = payload.get("data", payload)
    policy = data.get("policy") or {}
    registered = {row.get("version_string") for row in data.get("releases") or [] if isinstance(row, dict)}
    if version not in registered:
        print(f"{version} 尚未在 {hub} 登记，不能设为建议线", file=sys.stderr)
        return 1
    if policy.get("min_recommended_version") == version:
        print(f"建议线已是 {version}，跳过")
        return 0
    body = {
        "min_required_version": policy.get("min_required_version") or "",
        "min_recommended_version": version,
        "emergency_bypass": bool(policy.get("emergency_bypass")),
    }
    request("PUT", hub + POLICY_PATH, headers, body)
    after = request("GET", hub + RELEASES_PATH, headers)
    after_policy = (after.get("data", after).get("policy") or {})
    if after_policy.get("min_recommended_version") != version:
        print(f"写入后读回不一致：{after_policy}", file=sys.stderr)
        return 1
    print(f"建议线已抬到 {version}，强制线保持 {after_policy.get('min_required_version')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
