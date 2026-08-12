#!/usr/bin/env python3
"""PROD pipeline entrypoint: render artifacts and register the Max-only release."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--register-only",
        action="store_true",
        help="register SCENE_SKILL_VERSION after the pipeline artifact upload succeeds",
    )
    return parser.parse_args()


def build_prod_artifacts(root: Path, commit_sha: str, output_dir: Path) -> str:
    command = [
        sys.executable,
        str(root / "scene-creator/release/build_platform_packages.py"),
        "prod-build",
        "--commit-sha",
        commit_sha,
        "--output-dir",
        str(output_dir),
    ]
    completed = subprocess.run(command, cwd=root, check=True, text=True, capture_output=True)
    version_line = next(
        line for line in completed.stdout.splitlines() if line.startswith("SCENE_SKILL_VERSION=")
    )
    return version_line.split("=", 1)[1]


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


def main() -> int:
    args = parse_args()
    if os.environ.get("DEPLOY_ENV", "").strip().lower() != "prod":
        raise RuntimeError("refusing to update scene skill version outside PROD")
    root = Path(__file__).resolve().parents[1]
    if args.register_only:
        version = required_env("SCENE_SKILL_VERSION")
    else:
        commit_sha = required_env("CI_COMMIT_SHA")
        output_dir = Path(os.environ.get("SCENE_SKILL_OUTPUT_DIR", root / "dist"))
        version = build_prod_artifacts(root, commit_sha, output_dir)
    register_release(version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
