# `tool()` 正反例（一）：参数与返回

工具参数校验、结构化返回消费或 `_output` / `_text` 模式选择时读。诊断关键词：`tool_args`、`output_contract`、`ToolText`、`_output`、`_text`。对应契约：`WF-SINGLE-02`、`WF-SINGLE-03`。

本文分 2 份：[编排示例-tool-参数与返回.md](编排示例-tool-参数与返回.md)、[编排示例-tool-Schema与证据边界.md](编排示例-tool-Schema与证据边界.md)。

本页只覆盖单个 `tool()` 的确定性契约错误。示例中的 `demo_search` 是校验夹具，不是线上资产；实际开发必须先用 `get_asset` 取得真实工具名和当前 Schema。

以下案例共用这个 `input_schema`：

```json
{
  "type": "object",
  "required": ["query", "mode"],
  "properties": {
    "query": {"type": "string"},
    "mode": {"type": "string", "enum": ["fast", "safe"]},
    "limit": {"type": "integer"}
  }
}
```

诊断文案来自当前 Scene preview 和 Max Runtime。案例只保留可复现的契约模式，不复制运行日志中的用户输入、业务结果或项目标识。

## 1. 缺少必填参数

错误脚本：

```python
async def run(input, ctx):
    text = await tool(
        "demo_search",
        query=input.get("query", ""),
        _text=True,
        _rationale="查询候选资料"
    )
    return {"text": text}
```

实际 preview 诊断：

```text
tool("demo_search") 缺必填参数: mode（该工具 required=['query', 'mode']；用 get_asset 确认参数后补齐）
```

最小修复：

```diff
         query=input.get("query", ""),
+        mode="safe",
```

修复后证据：`tool_args` 检查无错误；真实资产仍须以 `get_asset` 返回的 `required` 为准。

所属契约：工具 `input_schema.required`。

## 2. 字面参数类型或枚举错误

错误脚本：

```python
async def run(input, ctx):
    text = await tool(
        "demo_search",
        query=input.get("query", ""),
        mode="other",
        limit="3",
        _text=True,
        _rationale="查询候选资料"
    )
    return {"text": text}
```

实际 preview 诊断（两条，顺序不保证）：

```text
tool("demo_search") 第 2 行参数 `mode` 的字面值 'other' 不在 input_schema.enum=['fast', 'safe'] 中
tool("demo_search") 第 2 行参数 `limit` 的字面值 '3' 不符合 input_schema.type='integer'
```

最小修复：

```diff
-        mode="other",
-        limit="3",
+        mode="safe",
+        limit=3,
```

修复后证据：`tool_args` 检查无错误。变量或表达式不会被 preview 猜类型，运行时仍以工具自身校验为准。

所属契约：工具 `input_schema.properties.*.type/enum`。

## 3. 把未声明结构的返回值当作对象

错误脚本：

```python
async def run(input, ctx):
    result = await tool(
        "demo_search",
        query=input.get("query", ""),
        mode="safe",
        _rationale="查询候选资料"
    )
    return {"items": result["items"]}
```

实际 preview 诊断：

```text
对未声明 _output 的 tool() 结果按字段下标 ["items"]（它是不透明文本，不是 dict）
```

如果静态分析没有覆盖到复杂传播，Max Runtime 仍会用 `ToolText` 拒绝字段访问，并提示在本次调用声明 `_output`。不要用 `json.loads`、`hasattr`、`isinstance` 或手工清洗绕过。

最小修复：

```diff
         mode="safe",
+        _output={
+            "type": "object",
+            "required": ["items"],
+            "properties": {"items": {"type": "array"}}
+        },
         _rationale="查询候选资料"
```

修复后证据：preview 不再报告 ToolText 结构化消费；运行时只有在真实返回通过该 `_output` 校验后，`result["items"]` 才能执行。

所属契约：步骤 `_output`。优先从工具正式 `output_schema` 裁出最小子集；没有正式 Schema 时，按 `otpe_tool_test` 的安全真实取样流程验证，不凭一次样本扩张 `required`。
