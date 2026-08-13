#!/usr/bin/env python3
"""PROD pipeline entrypoint: update repository version or register Max Hub."""

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
        "--prepare-only",
        action="store_true",
        help="update the repository Skill marker without creating a package",
    )
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


def prepare_release(root: Path) -> str:
    sys.path.insert(0, str(root / "scene-creator/release"))
    from build_platform_packages import release_prod_source

    return release_prod_source(
        root / "scene-creator",
        os.environ.get("SCENE_SKILL_RELEASE_NOTES", "PROD pipeline release"),
    )


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
    timestamp = str(int(time.time()))
    secret = required_env("SCENE_SKILL_RELEASE_S2S_SECRET").encode()
    signature = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    endpoint = required_env("SCENE_SKILL_RELEASE_REGISTER_URL")
    request = urllib.request.Request(endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Goalfy-Timestamp", timestamp)
    request.add_header("X-Goalfy-Signature", signature)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"release registration failed: HTTP {response.status}")


def verify_prod_runtime(root: Path) -> None:
    sys.path.insert(0, str(root / "scene-creator/release"))
    from build_platform_packages import PROD_MCP_ENDPOINT, assert_prod_runtime

    assert_prod_runtime(root / "scene-creator")
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
    if os.environ.get("DEPLOY_ENV", "").strip().lower() != "prod":
        raise RuntimeError("refusing to update scene skill version outside PROD")
    root = Path(__file__).resolve().parents[1]
    if args.prepare_only:
        version = prepare_release(root)
        print(f"SCENE_SKILL_VERSION={version}")
    elif args.verify_runtime_only:
        verify_prod_runtime(root)
        print("CN PROD scene-creator MCP route is ready")
    else:
        version = required_env("SCENE_SKILL_VERSION")
        register_release(version)
        print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
