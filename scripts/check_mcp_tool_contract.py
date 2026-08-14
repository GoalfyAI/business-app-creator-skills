#!/usr/bin/env python3
"""Compare the scene-creator Skill tool profile with a live MCP tools/list response."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "scene-creator" / "SKILL.md"
TOOL_REFERENCE_PATH = (
    ROOT / "scene-creator" / "references" / "external-mcp-tools.md"
)
DEFAULT_MCP_URL = "https://workflow-mcp.qa.goalfyai.com/mcp"
TOOL_ROW_RE = re.compile(r"^\| `([^`]+)` \|", flags=re.MULTILINE)


class ContractError(RuntimeError):
    """The checked-in Skill and the live MCP tool contract do not match."""


def _table_tools(content: str) -> set[str]:
    return set(TOOL_ROW_RE.findall(content))


def documented_tool_names() -> set[str]:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    overview = skill.split("## 九、工具能力与调用纪律", 1)[1].split(
        "## 十、验证、发布与交付", 1
    )[0]
    skill_tools = _table_tools(overview)
    reference_tools = _table_tools(TOOL_REFERENCE_PATH.read_text(encoding="utf-8"))
    if not skill_tools or skill_tools != reference_tools:
        raise ContractError(
            "SKILL.md 与 external-mcp-tools.md 的工具清单不一致："
            f"skill={sorted(skill_tools)}, reference={sorted(reference_tools)}"
        )
    return skill_tools


def _decode_mcp_payload(body: bytes, content_type: str) -> dict[str, Any]:
    text = body.decode("utf-8")
    if "text/event-stream" in content_type:
        events = [
            line.removeprefix("data:").strip()
            for line in text.splitlines()
            if line.startswith("data:") and line.removeprefix("data:").strip()
        ]
        if not events:
            raise ContractError("MCP SSE 响应没有 data 事件")
        text = events[-1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("MCP 返回的不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError("MCP 返回必须是 JSON 对象")
    if payload.get("error"):
        raise ContractError(f"MCP 返回错误：{payload['error']}")
    return payload


class McpClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token = token
        self.session_id: str | None = None

    def _post(self, payload: dict[str, Any], *, expect_body: bool = True) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        http_request = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=30) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                body = response.read()
                if not body and not expect_body:
                    return {}
                return _decode_mcp_payload(
                    body,
                    response.headers.get("Content-Type", "application/json"),
                )
        except error.HTTPError as exc:
            raise ContractError(f"MCP HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise ContractError(f"MCP 连接失败：{exc.reason}") from exc

    def initialize(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "scene-creator-skill-contract-check",
                        "version": "1.0.0",
                    },
                },
            }
        )
        if not isinstance(response.get("result"), dict):
            raise ContractError("MCP initialize 缺少 result")
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_body=False,
        )

    def list_tools(self) -> set[str]:
        response = self._post(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tools = response.get("result", {}).get("tools")
        if not isinstance(tools, list):
            raise ContractError("MCP tools/list 缺少 result.tools")
        names = {
            tool.get("name")
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }
        if len(names) != len(tools):
            raise ContractError("MCP tools/list 含无效或重复工具名")
        return names


def check_live_contract(url: str, token: str) -> tuple[set[str], set[str]]:
    expected = documented_tool_names()
    client = McpClient(url, token)
    client.initialize()
    actual = client.list_tools()
    if actual != expected:
        raise ContractError(
            "Skill 与 MCP tools/list 不一致："
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    return expected, actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("SCENE_CREATOR_MCP_URL", DEFAULT_MCP_URL))
    parser.add_argument("--token-env", default="SCENE_CREATOR_API_KEY")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        parser.error(f"缺少环境变量 {args.token_env}")
    try:
        expected, _ = check_live_contract(args.url, token)
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"scene-creator MCP contract OK: {len(expected)} tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
