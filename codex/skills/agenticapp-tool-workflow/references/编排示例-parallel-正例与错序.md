# `parallel()` 正反例（一）：正例与错序

要在一个确定性阶段内并发少量独立步骤时读。诊断关键词：`parallel`、共享可变状态、错序、同路径竞态、隐藏依赖。对应契约：`WF-SINGLE-04`。

本文分 2 份：[编排示例-parallel-正例与错序.md](编排示例-parallel-正例与错序.md)、[编排示例-parallel-依赖与清单.md](编排示例-parallel-依赖与清单.md)。

`parallel([...])` 在当前 Max Runtime 中等价于 `asyncio.gather(*coros)`：列表中的调用并发启动，`await` 等待这一组调用，返回值按输入位置排列。

它只适合一个确定性阶段内的少量独立调用，优先用于只读或可安全重试的步骤。跨编排型 TPE 的固定扇出、依赖和汇合仍应写进 `workflow_orchestration`，不要用本页示例替代场景包 DAG。

示例中的 `demo_search` 是校验夹具，不是线上资产。实际开发必须使用 `get_asset` 返回的真实工具名和 Schema，并为每个 `tool()` 分别声明 `_rationale` 与所需的结果契约。

## 1. 正例：两支输入已齐备且互不依赖

正确脚本：

```python
async def run(input, ctx):
    query = input.get("query", "")
    cn_result, global_result = await parallel([
        tool(
            "demo_search",
            query=query,
            region="cn",
            _output={
                "type": "object",
                "required": ["items"],
                "properties": {"items": {"type": "array"}}
            },
            _rationale="收集国内候选资料"
        ),
        tool(
            "demo_search",
            query=query,
            region="global",
            _output={
                "type": "object",
                "required": ["items"],
                "properties": {"items": {"type": "array"}}
            },
            _rationale="收集海外候选资料"
        )
    ])
    return {
        "cn_items": cn_result["items"],
        "global_items": global_result["items"]
    }
```

实际诊断：preview 无 `primitive` 或 `output_contract` 错误。Runtime 的 `gather` 返回顺序与输入列表一致，因此第一个变量稳定对应 `region="cn"`，不依赖哪一支先完成。

修复后证据：两支只读取同一个不可变输入 `query`，不读取对方结果，不写同一路径或共享容器；任一必需工具步骤抛错时，整个 `await parallel(...)` 不会产出一组伪成功结果。

注意：`gather` 抛出一支的异常，不代表其他分支从未执行或已自动回滚。邮件、发布、扣费、创建远端对象等不可幂等副作用不要放进同一 `parallel` 后依赖“整体失败”重试，否则已成功的分支可能重复执行。

所属契约：独立并发、位置对齐、每支单独履行 `tool()` 契约。

## 2. 反例：通过共享列表隐式决定结果顺序

错误脚本：

```python
async def run(input, ctx):
    collected = []

    async def collect(region):
        result = await tool(
            "demo_search",
            query=input.get("query", ""),
            region=region,
            _output={
                "type": "object",
                "required": ["items"],
                "properties": {"items": {"type": "array"}}
            },
            _rationale="按区域收集候选资料"
        )
        collected.append({"region": region, "items": result["items"]})

    await parallel([collect("cn"), collect("global")])
    return {"groups": collected}
```

实际诊断：preview 可能无错误，运行也可能 success；但 `collected` 的顺序取决于分支完成顺序，而不是 `parallel` 的输入顺序。这是无异常的静默错序，不能靠重跑证明稳定。

最小修复：让每支返回自己的值，使用 `parallel` 本身保证的位置顺序，不共享写容器。

```diff
-    collected = []
-
     async def collect(region):
         result = await tool(
             "demo_search",
             query=input.get("query", ""),
             region=region,
             _output={
                 "type": "object",
                 "required": ["items"],
                 "properties": {"items": {"type": "array"}}
             },
             _rationale="按区域收集候选资料"
         )
-        collected.append({"region": region, "items": result["items"]})
+        return {"region": region, "items": result["items"]}

-    await parallel([collect("cn"), collect("global")])
-    return {"groups": collected}
+    cn_group, global_group = await parallel([
+        collect("cn"), collect("global")
+    ])
+    return {"groups": [cn_group, global_group]}
```

修复后证据：输出顺序由 `parallel` 输入位置确定；分支不再共同修改运行时状态。

所属契约：并发分支无共享可变状态。
