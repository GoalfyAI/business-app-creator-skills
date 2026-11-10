# `parallel()` 正反例（二）：隐藏依赖与重复调用

并行步骤之间有文件依赖、或把 `parallel` 的返回值又调用了一次时读；最后有判断清单。

本文分 2 份：[编排示例-parallel-正例与错序.md](编排示例-parallel-正例与错序.md)、[编排示例-parallel-依赖与清单.md](编排示例-parallel-依赖与清单.md)。

## 3. 反例：把有文件依赖的两步并行

错误脚本：

```python
async def run(input, ctx):
    source_path = f"{ctx.process_dir}source.json"
    _, source_text = await parallel([
        tool(
            "file",
            action="file_write_text",
            abs_path=source_path,
            text=json.dumps(input.get("source", {}), ensure_ascii=False),
            _rationale="写入后续步骤要读取的过程文件"
        ),
        tool(
            "file",
            action="file_process",
            abs_path=source_path,
            _text=True,
            _rationale="读取刚写入的过程文件"
        )
    ])
    return {"source_text": source_text}
```

实际诊断：preview 无法从两个普通 `tool()` 调用推断文件读写依赖，因此可能通过。Runtime 会并发启动读和写；读取可能先执行并报文件不存在，也可能读到先前残留内容，属于竞态而不是可重试的随机 Provider 故障。

最小修复：先等待生产者成功，再启动消费者。

```diff
-    _, source_text = await parallel([
-        tool(
+    await tool(
             "file",
             action="file_write_text",
             abs_path=source_path,
             text=json.dumps(input.get("source", {}), ensure_ascii=False),
             _rationale="写入后续步骤要读取的过程文件"
-        ),
-        tool(
+    )
+    source_text = await tool(
             "file",
             action="file_process",
             abs_path=source_path,
             _text=True,
             _rationale="读取已写入的过程文件"
-        )
-    ])
+    )
```

修复后证据：写步骤成功返回后才会发起读步骤；`WorkflowStepError` 会把写失败停在生产者边界，不会继续读取不存在的产物。

所属契约：数据依赖必须串行；同一路径的读写不是独立并发。

## 4. 反例：把 `parallel` 返回值再次调用

错误脚本：

```python
async def run(input, ctx):
    left, right = await parallel([
        tool("demo_search", query="a", _text=True, _rationale="读取左侧资料"),
        tool("demo_search", query="b", _text=True, _rationale="读取右侧资料")
    ])()
    return {"left": left, "right": right}
```

实际 preview 诊断：

```text
parallel(...) 返回值不可再调用：parallel 直接 await，不要 parallel(...)(...)
```

最小修复：

```diff
-    ])()
+    ])
```

修复后证据：`primitive` 检查无错误，运行时直接等待并接收结果列表。

所属契约：`parallel([...])` 是一次可等待调用，不是可继续传参的函数。

## 判断清单

只有下面五项都为“是”时才使用 `parallel`：

1. 每支所需输入在进入 `parallel` 前已经完整存在；
2. 每支不读取另一支的文件、返回值或副作用；
3. 每支不修改同一个 list/dict/文件或远端对象；
4. 分支结果通过 `parallel` 返回值显式汇合，而不是靠完成顺序或外部状态汇合。
5. 任一分支失败后，即使其他分支已经执行，重试也不会制造重复副作用。

否则使用串行 `await`；如果是跨编排型 TPE 的固定扇出和汇合，使用 `workflow_orchestration`。
