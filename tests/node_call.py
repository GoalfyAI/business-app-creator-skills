"""测试里调用 Skill 的 Node 脚本（.mjs）导出的函数：参数和结果都走 JSON，一次进程跑一批调用。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HELPER = r"""
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const m = await import(pathToFileURL(process.argv[1]).href);
const parse = m.parseJson || JSON.parse;
const dump = m.pyDumps ? v => m.pyDumps(v, { compact: true }) : v => JSON.stringify(v, (_k, x) => (typeof x === 'bigint' ? x.toString() : x));
const out = [];
for (const c of parse(readFileSync(0, 'utf8'))) {
  if (c.fetch_body !== undefined) globalThis.fetch = async () => new Response(Buffer.from(c.fetch_body), { status: c.fetch_status || 200 });
  try {
    out.push({ ok: c.get ? m[c.get] : await m[c.fn](...(c.args || [])) });
  } catch (e) {
    out.push({ err: e.name, msg: e.message });
  }
}
process.stdout.write(dump(out));
"""


def node_calls(module: Path, calls: list[dict]) -> list[dict]:
    """calls 每项 {"fn": 函数名, "args": [...]} 或 {"get": 导出名}；可带 fetch_body（和 fetch_status）替换 fetch 的返回。"""
    run = subprocess.run(["node", "--input-type=module", "-e", HELPER, str(module.resolve())],
                         input=json.dumps(calls, ensure_ascii=False), capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


class NodeError(Exception):
    """Node 函数抛的错：name 是 JS 的错误名（如 ValueError），str() 是原因。"""

    def __init__(self, name: str, msg: str) -> None:
        super().__init__(msg)
        self.name = name


class NodeValueError(NodeError, ValueError):
    """JS 里抛的 ValueError：测试照旧用 assertRaises(ValueError) 接。"""


def unwrap(res: dict):
    if "ok" in res:
        return res["ok"]
    raise (NodeValueError if res["err"] == "ValueError" else NodeError)(res["err"], res["msg"])


def node_call(module: Path, fn: str, *args):
    """调一个函数，返回结果；抛错时在这里抛 NodeError。"""
    return unwrap(node_calls(module, [{"fn": fn, "args": list(args)}])[0])
