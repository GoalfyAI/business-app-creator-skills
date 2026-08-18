#!/usr/bin/env python3
"""把已发布的 Skill 版本登记到各环境 Max Hub，并探测生产 MCP 是否就绪。

版本切换由 scripts/release-skill.sh 在本地完成，本脚本只负责发布之后的事：
--register-only 由 GitHub Actions 在推送后调用；--verify-runtime-only 供发版前手工检查。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--register-only",
        action="store_true",
        help="register SCENE_SKILL_VERSION after the release commit is pushed",
    )
    actions.add_argument(
        "--verify-runtime-only",
        action="store_true",
        help="verify that the CN PROD MCP route reaches its authentication layer",
    )
    return parser.parse_args()



def _registry_targets() -> list[tuple[str, str]]:
    """解析登记目标列表。

    Skill 只有一份、版本号只有一条线，但 Hub 分多个环境各自持有 registry。
    只登记生产会让其他环境的 registry 恒空，闸门在那些环境既不生效也无法验证，
    所以按环境逐个登记。

    SCENE_SKILL_RELEASE_REGISTRY_TARGETS 每行一个 `<url>|<secret>`；
    未配置时回退到单目标的 SCENE_SKILL_RELEASE_REGISTER_URL +
    SCENE_SKILL_RELEASE_S2S_SECRET，保持既有流水线变量可用。
    """
    raw = os.environ.get("SCENE_SKILL_RELEASE_REGISTRY_TARGETS", "").strip()
    if not raw:
        return [
            (
                required_env("SCENE_SKILL_RELEASE_REGISTER_URL"),
                required_env("SCENE_SKILL_RELEASE_S2S_SECRET"),
            )
        ]
    targets = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        url, separator, secret = line.partition("|")
        if not separator or not url.strip() or not secret.strip():
            raise RuntimeError("registry target format must be <url>|<secret>")
        targets.append((url.strip(), secret.strip()))
    if not targets:
        raise RuntimeError("SCENE_SKILL_RELEASE_REGISTRY_TARGETS is empty")
    return targets


def register_release(version: str) -> None:
    if not version.strip():
        raise RuntimeError("missing scene skill version")
    version = version.strip()
    body = json.dumps(
        {
            "version_string": version,
            "notes": os.environ.get("SCENE_SKILL_RELEASE_NOTES", "PROD pipeline release"),
            "source": "codeup-prod-pipeline",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    # 逐个环境登记，先跑完全部目标再汇总失败，避免前面的环境成功、后面的静默漏登记。
    failures = []
    for endpoint, secret in _registry_targets():
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        request = urllib.request.Request(endpoint, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Goalfy-Timestamp", timestamp)
        request.add_header("X-Goalfy-Signature", signature)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
            print(f"registered {version} at {endpoint}")
        except Exception as exc:
            print(f"FAILED {endpoint}: {exc}")
            failures.append(endpoint)
    if failures:
        raise RuntimeError(
            f"release registration failed for {len(failures)} target(s): {failures}"
        )


def verify_prod_runtime(root: Path) -> None:
    sys.path.insert(0, str(root / "scripts"))
    from build_platform_packages import PROD_MCP_ENDPOINT

    request = urllib.request.Request(
        PROD_MCP_ENDPOINT,
        method="GET",
        headers={"Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            runtime = response.headers.get("X-Scene-Skill-Runtime", "")
    except urllib.error.HTTPError as exc:
        status = exc.code
        runtime = exc.headers.get("X-Scene-Skill-Runtime", "")
    except urllib.error.URLError as exc:
        raise RuntimeError("CN PROD scene-creator MCP route is unreachable") from exc
    if status not in (401, 403):
        raise RuntimeError(
            f"CN PROD scene-creator MCP route is not ready: expected auth rejection, got HTTP {status}"
        )
    if runtime != "cn-prod":
        raise RuntimeError(
            "CN PROD scene-creator MCP is not connected to the CN PROD Max Hub"
        )


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.verify_runtime_only:
        verify_prod_runtime(root)
        print("CN PROD scene-creator MCP route is ready")
    else:
        version = required_env("SCENE_SKILL_VERSION")
        register_release(version)
        print(version)
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
