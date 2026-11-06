# `pipeline()` 正反例（一）：正例与阶段接缝

多个 item 要分别经过同一条线性 stage 链时读。诊断关键词：`pipeline`、stage 接缝、错误字段路径、跨 item 汇总、全局 stage 屏障。对应契约：`WF-SINGLE-04`。

本文分 2 份：[编排示例-pipeline-正例与接缝.md](编排示例-pipeline-正例与接缝.md)、[编排示例-pipeline-汇总与清单.md](编排示例-pipeline-汇总与清单.md)。

当前 Max Runtime 的 `pipeline(items, *stages)` 语义是：

- 不同 item 并发执行；
- 同一个 item 按 stages 声明顺序逐段 `await`；
- 上一 stage 的返回值，是下一 stage 唯一的位置参数；
- 最终列表按原始 items 顺序排列；
- 不存在“所有 item 都完成 stage 1 后，再统一进入 stage 2”的全局屏障。

因此它适合“每个 item 都独立经过同一条线性加工链”，不适合跨 item 汇总、共享文件或需要全局阶段屏障的任务。跨编排型 TPE 的固定阶段和依赖仍使用 `workflow_orchestration`。

示例中的 `demo_normalize`、`demo_enrich` 和 `demo_summarize` 都是校验夹具，不是线上资产。实际开发必须从 `get_asset` 取得真实名称和 Schema。

## 1. 正例：每个 item 独立通过两个兼容阶段

正确脚本：

```python
async def run(input, ctx):
    async def normalize(item):
        return await tool(
            "demo_normalize",
            raw=item,
            _output={
                "type": "object",
                "required": ["record"],
                "properties": {
                    "record": {
                        "type": "object",
                        "required": ["title"],
                        "properties": {"title": {"type": "string"}}
                    }
                }
            },
            _rationale="将一条原始输入整理为统一记录"
        )

    async def enrich(normalized):
        return await tool(
            "demo_enrich",
            title=normalized["record"]["title"],
            _output={
                "type": "object",
                "required": ["title", "score"],
                "properties": {
                    "title": {"type": "string"},
                    "score": {"type": "number"}
                }
            },
            _rationale="为一条标准记录补充评分"
        )

    results = await pipeline(input.get("items", []), normalize, enrich)
    return {"results": results}
```

实际诊断：preview 无 `primitive` 或 `output_contract` 错误。Runtime 对每个 item 执行 `normalize(item) → enrich(normalized)`，并按输入 item 的顺序返回最终结果。

修复后证据：两个 stage 都只处理当前 item；`normalize` 声明的嵌套 `record.title` 与 `enrich` 实际读取的字段一致；没有共享容器、同路径文件或跨 item 查询。

所属契约：单 item 线性传值、stage 接缝字段一致、item 之间独立。

## 2. 反例：下一阶段读取了错误的接缝字段

错误脚本：

```python
async def run(input, ctx):
    async def normalize(item):
        return await tool(
            "demo_normalize",
            raw=item,
            _output={
                "type": "object",
                "required": ["record"],
                "properties": {
                    "record": {
                        "type": "object",
                        "required": ["title"],
                        "properties": {"title": {"type": "string"}}
                    }
                }
            },
            _rationale="将一条原始输入整理为统一记录"
        )

    async def enrich(normalized):
        return await tool(
            "demo_enrich",
            title=normalized["title"],
            _text=True,
            _rationale="为标准记录补充说明"
        )

    results = await pipeline(input.get("items", []), normalize, enrich)
    return {"results": results}
```

实际诊断：preview 当前不做跨 stage 的完整类型推导，因此可能通过；真实运行在进入第二个工具前确定性触发 `KeyError: 'title'`。第一阶段返回的是 `normalized["record"]["title"]`，不是顶层 `normalized["title"]`。

最小修复：

```diff
-            title=normalized["title"],
+            title=normalized["record"]["title"],
```

修复后证据：第二阶段读取路径与第一阶段 `_output` 的 `properties.record.properties.title` 完全一致；无需增加跨步类型推导 validator。

所属契约：相邻 stage 的 producer `_output` 与 consumer 字段路径一致。
