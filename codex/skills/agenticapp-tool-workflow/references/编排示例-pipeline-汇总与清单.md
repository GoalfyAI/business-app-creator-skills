# `pipeline()` 正反例（二）：跨 item 汇总与重复调用

想把需要全批次输入的汇总放进 `pipeline`、或把 `pipeline` 的返回值又调用了一次时读；最后有判断清单。

本文分 2 份：[编排示例-pipeline-正例与接缝.md](编排示例-pipeline-正例与接缝.md)、[编排示例-pipeline-汇总与清单.md](编排示例-pipeline-汇总与清单.md)。

## 3. 反例：把需要全批次输入的汇总器放进 pipeline

错误脚本：

```python
async def run(input, ctx):
    async def collect(item):
        return await tool(
            "demo_normalize",
            raw=item,
            _output={
                "type": "object",
                "required": ["record"],
                "properties": {"record": {"type": "object"}}
            },
            _rationale="整理一条待汇总记录"
        )

    async def summarize(records):
        return await tool(
            "demo_summarize",
            records=records,
            _output={
                "type": "object",
                "required": ["summary"],
                "properties": {"summary": {"type": "string"}}
            },
            _rationale="汇总全部标准记录"
        )

    summaries = await pipeline(input.get("items", []), collect, summarize)
    return {"summaries": summaries}
```

实际诊断：`summarize` 的参数名看起来像全批次，实际每次只收到当前 item 的 `collect` 返回值。脚本可能成功，但会生成 N 个单条摘要，而不是 1 个全局摘要；`pipeline` 不会自动做 fan-in。

最小修复：先完成逐 item 加工，再在 `pipeline` 外显式汇总一次。

```diff
-    summaries = await pipeline(input.get("items", []), collect, summarize)
-    return {"summaries": summaries}
+    collected = await pipeline(input.get("items", []), collect)
+    summary = await tool(
+        "demo_summarize",
+        records=[result["record"] for result in collected],
+        _output={
+            "type": "object",
+            "required": ["summary"],
+            "properties": {"summary": {"type": "string"}}
+        },
+        _rationale="汇总全部标准记录"
+    )
+    return {"summary": summary["summary"]}
```

修复后证据：`collected` 是全部 items 的有序结果列表；全局汇总工具只调用一次，并明确收到完整 `records` 数组。

所属契约：pipeline 是 per-item 流水线，不提供跨 item fan-in 或全局 stage 屏障。

## 4. 反例：把 `pipeline` 返回值再次调用

错误脚本：

```python
async def run(input, ctx):
    async def normalize(item):
        return item

    results = await pipeline(input.get("items", []), normalize)()
    return {"results": results}
```

实际 preview 诊断：

```text
pipeline(...) 返回值不可再调用：pipeline 直接 await，不要 pipeline(...)(...)
```

最小修复：

```diff
-    results = await pipeline(input.get("items", []), normalize)()
+    results = await pipeline(input.get("items", []), normalize)
```

修复后证据：`primitive` 检查无错误；Runtime 直接等待每个 item 的 stage 链并返回结果列表。

所属契约：`pipeline(items, *stages)` 是一次可等待调用，不是可继续传参的函数。

## 判断清单

只有下面五项都为“是”时才使用 `pipeline`：

1. 每个 stage 都是接受一个值、返回一个值的异步函数；
2. 下一 stage 消费的字段路径由上一 stage 的 `_output` 明确保证；
3. 每个 item 不依赖其他 item 的中间结果、完成顺序或副作用；
4. 业务不要求“所有 item 完成 stage N 后，才能开始 stage N+1”；
5. 单个 item 失败后，即使其他 item 已执行，重试也不会制造重复副作用。

否则使用显式串行步骤、先收集再汇总，或把跨编排型 TPE 固定阶段写入 `workflow_orchestration`。
