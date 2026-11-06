# `tool()` 正反例（二）：`_output` 合法性、模式互斥与证据边界

`_output` 不是合法 JSON Schema、`_output` 与 `_text=True` 同时出现，或要弄清取样和冒泡各证明什么时读。案例共用的 `input_schema` 在 [编排示例-tool-参数与返回.md](编排示例-tool-参数与返回.md) 开头。

本文分 2 份：[编排示例-tool-参数与返回.md](编排示例-tool-参数与返回.md)、[编排示例-tool-Schema与证据边界.md](编排示例-tool-Schema与证据边界.md)。

## 4. `_output` 本身不是合法 JSON Schema

错误脚本：

```python
async def run(input, ctx):
    result = await tool(
        "demo_search",
        query=input.get("query", ""),
        mode="safe",
        _output={"type": "not-a-json-schema-type"},
        _rationale="查询候选资料"
    )
    return {"result": result}
```

实际 preview 诊断首行：

```text
第 1 步 tool("demo_search")（第 2 行） 的 `_output` 不是合法 Draft 2020-12 JSON Schema: 'not-a-json-schema-type' is not valid under any of the given schemas
```

最小修复：

```diff
-        _output={"type": "not-a-json-schema-type"},
+        _output={"type": "object"},
```

修复后证据：字面 `_output` 通过 Draft 2020-12 `check_schema`。这只证明 Schema 写法合法；真实返回是否匹配仍由取样或 Max Runtime 证明。

所属契约：步骤 `_output` 的 Draft 2020-12 Schema 合法性。

## 5. 同时声明结构化和纯文本模式

错误脚本：

```python
async def run(input, ctx):
    result = await tool(
        "demo_search",
        query=input.get("query", ""),
        mode="safe",
        _output={"type": "object"},
        _text=True,
        _rationale="查询候选资料"
    )
    return {"result": result}
```

实际 preview 诊断：

```text
第 1 步 tool("demo_search")（第 2 行） 同时声明了 `_output` 和 `_text=True`：按字段消费请保留 `_output`；只需纯文本请移除 `_output`
```

结构化消费的最小修复：

```diff
         _output={"type": "object"},
-        _text=True,
```

如果业务只需要全文，则反过来移除 `_output`，保留 `_text=True`，并且只使用字符串方法。

修复后证据：`output_contract` 检查无冲突；返回值只有一种明确消费方式。

所属契约：`_output` 与字面 `_text=True` 互斥。

## 证据边界

- Preview 通过只证明脚本满足静态契约，不证明 Provider 可用或真实输出匹配。
- MCP 连接资产优先用 `otpe_tool_test` 直接取得真实证据；整条编排型 TPE 仍必须冒泡。冒泡中 FA 为 Schema 桩，`file`、`shell` 和直连工具按 Runtime 语义真实执行；FA 真实内容或完整业务交付用全真运行验证，要不要先问开发者见 [编排型TPE总契约.md](编排型TPE总契约.md) 的全真运行规则。
- 目标工具依赖 `/workspace` 文件时，先对每个本地文件调用 `file_to_url(purpose="tool_test_fixture")` 完成上传，再把返回的 `data.file_ref` 放入 `workspace_files`；另用 `workspace_bindings` 把某个已上传文件的路径或父目录绑定到目标工具顶层参数。服务端会从临时 HTTPS URL 下载文件、写入自动创建的隐藏验证项目，并在调用后清理；不要借用用户项目，也不要同时传 `project_id`。
- 工具失败不是业务数据。必需步骤让错误冒泡；可选步骤只有在最终 `output_schema` 明确声明降级字段并返回真实降级状态时才捕获。
