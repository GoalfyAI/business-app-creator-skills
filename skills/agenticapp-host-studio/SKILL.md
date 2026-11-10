---
name: agenticapp-host-studio
description: Studio 宿主的做法。工具列表里有 studio_write_proposal 时和当前段一起加载：四份开发文档的数据、Demo、生成和保存，确认登记，表单和记忆卡。没有这个工具的宿主不用。
---
# Studio 宿主

宿主实际提供 Studio 制作工具（`studio_select_application`、`studio_write_proposal`、`studio_read_creation`、`studio_confirm_proposal`，参数以工具当前说明为准）时按这个 Skill 做；没有这些工具时不用它。Studio 只管文档怎么保存、显示和确认。五段的顺序、每段确认什么、④ 怎么验收、⑤ 做到哪一步，都按入口和各段 Skill 做，和其他宿主相同。

**核心规则：四份开发文档你只写数据，页面由脚本生成。** 写 `data.json`（方案另写每个功能的 Demo 页面），跑 `scripts/build_studio_doc.py`，它校验内容、套上统一的版式和交互，生成 `index.html`。不手写、不改生成出来的 HTML，不自己设计版式。

## 什么时候用、什么时候不用

- 用：Studio 宿主下写、更新、保存需求说明（PRD）、方案、制作进度、验收报告；登记开发者的确认；按轮问发表单。
- 不用：文档里写什么（每段的内容规则）——按当前段的 Skill；非 Studio 宿主写方案页——按 `agenticapp-tool-workspace`。

## 四份开发文档

Studio 第三栏「开发文档」有四份，代替方案页：

| 文档 | 第一次写 | 之后更新 | `documentType` | 要开发者确认 |
|---|---|---|---|---|
| 需求说明（PRD） | ① 按轮问问完之后，写第 1 版 | 开发者批注后出新一版 | `prd` | 要，确认这一版 |
| 方案 | ② 取舍、验收要求和费用变化问清之后 | 按修改意见出新一版 | `proposal` | 要，只确认一次整版 |
| 制作进度 | ③ 开始时，建任何资产、写代码之前 | 有实质进展时 | `progress` | 不要 |
| 验收报告 | ④ 报告过了硬门之后 | 按反馈重测后出新一版；⑤ 收尾时补「上线结果」，再出一版 | `acceptance` | 不要 |

- 只写当前段的文档：① 里只有 PRD，② 里才有方案，依此类推。还没到的段不写，也不写「暂无」「未开始」的占位页。
- 开工时的最小草案不交 PRD 草稿，记在哪见 [references/各段和任务在Studio下的不同.md](references/各段和任务在Studio下的不同.md)。

## 怎么写一份

开始前，把下面 6 步建成待办（Claude Code 用 TodoWrite，Codex 用 update_plan），做完一步勾一步。

1. **读这份文档的数据说明**（下表），内容写什么按那一段的 Skill，说明里每个字段都写了内容规则在哪。

   | 文档 | 数据说明和完整样例 | 另外要读 |
   |---|---|---|
   | PRD | [assets/需求说明数据.md](assets/需求说明数据.md) | — |
   | 方案 | [assets/方案数据.md](assets/方案数据.md) | [references/Demo怎么写.md](references/Demo怎么写.md) |
   | 制作进度 | [assets/制作进度数据.md](assets/制作进度数据.md) | — |
   | 验收报告 | [assets/验收报告数据.md](assets/验收报告数据.md) | — |

2. **写数据**：应用工程里 `docs/studio/<documentType>/data.json`。样例里的门店、数字、截图只用来示意，你写的都是自己查到、跑到的。方案另写 `demos/<编号>.html` 和 `acceptance.json`；验收报告的截图放 `shots/`。
3. **生成**：

   ```bash
   python3 <本 Skill 目录>/scripts/build_studio_doc.py <documentType> docs/studio/<documentType>/data.json
   ```

   退出码 1 时按它列出的每一条改 `data.json` 或 Demo 再跑，直到生成成功。它拦的是测试里真出过的错：结论条数对不上、条目外的未测没算进去、禁用词、Demo 联网或用 `<form>`、编号和说明对不上、验收条目没挂到路径上、写了原型里没有的区块。
4. **看一眼**：`build_studio_doc.py shot docs/studio/<documentType>/index.html frontend` 截 400px 和 900px 两张图，打开看，按 [references/检查清单.md](references/检查清单.md) 逐条对。第一次生成通常有排版或内容问题，改完再生成、再看，看过没问题再保存。
5. **保存**：先跑 `build_studio_doc.py verify docs/studio/<documentType>/index.html`，没过说明页面不是脚本生成的或被改过，回第 3 步。再确认已调 `studio_select_application`（初始化应用工程后、第一次保存前调；传真实应用根路径，已有 `.workbench/application.json` 时传其中的 UUID）。用 `studio_read_creation` 读这一类文档当前的 `artifactId`，调 `studio_write_proposal`：`documentType` 按上表，`version` 写 `<documentType>-<版本号>`（例如 `prd-2`），`baseArtifactId` 传刚读到的（还没有这类文档时传 `null`），`files` 放脚本最后一行列出的文件。报 `STUDIO_DOCUMENT_CONFLICT` 时重读当前一版，把对方的改动合进 `data.json` 再生成，不覆盖。保存成功只代表存好了，不代表开发者已确认。
6. **交接**：同时发交接消息（入口「交接」）：说文档在「开发文档」里、这一版改了什么，不把文档全文贴进聊天。

**更新**：出新一版时读 [references/更新一份.md](references/更新一份.md)。

## 文档里的交互

生成的页面里有流程图连线、节点详情、可以操作的 Demo、进度和验收回放。这些只在 Studio 放开文档脚本后可用；没有脚本时页面照样能完整阅读（连线、回放没有，内容都在）。页面能做什么、不能做什么见 [references/交互约定.md](references/交互约定.md)。不论哪种情况：

- 确认、提问都在聊天里做，页面上不放「确认这一版」，也不写请开发者去在线预览、演示预览或正式入口里点、试、查的话（入口「红线」不代测）。
- Demo 是设计示例，用写好的示例数据，不连真实服务；制作进度、验收报告的回放只按已有记录走一遍，不能当成完成或通过的证据。

## 确认怎么登记

PRD 和方案要开发者确认；什么算「确认这一版」、新一版要不要重新确认，按 `agenticapp-stage-1-requirements`，整版确认按 `agenticapp-stage-2-plan`。确认卡上点确认和在聊天里明确同意任选其一，完成后不再要求另一种确认。Studio 里这样登记：

- **在聊天里同意的**（文字或语音转写都算）：用 `studio_read_creation` 读这份文档当前的 `artifactId`、`version`、`digest`；调 `studio_confirm_proposal`，传 `documentType`（`prd` 或 `proposal`）、这三项和开发者原话 `userStatement`；再用 `studio_read_creation` 读回已确认。原话要是针对这一份的：对方案的同意（包括方案确认卡）不登记成需求文档的确认，反过来也一样。
- **在确认卡上点了确认的**：宿主已登记，用 `studio_read_creation` 读回已确认。
- 读回已确认才往下走：PRD 读到确认之前只查不建，方案读到确认之后才进 ③。已确认范围内的修订以宿主返回的当前确认状态为准，不自行增加确认步骤。
- 给开发者只说文档内容、实际确认状态和下一步；`artifactId`、`version`、`digest` 这类核对字段只记进阶段文档。

## 验收报告

④ 的验收报告：内容照 `agenticapp-stage-4-acceptance`，数据照 [assets/验收报告数据.md](assets/验收报告数据.md)。

1. 过了 `agenticapp-stage-4-acceptance`「交报告前的三道硬门」才保存；生成脚本会拦下一部分（未测类别、条目外的未测计数、路径结论和条目对不上），其余按硬门自查。
2. 页面条目的截图存成 `shots/<条目编号>-<序号>.png`，写进那条的 `shots`，随 `files` 一起保存。
3. 按反馈重测后出新一版，只改变了的条目，改了什么、重测了哪几条写进 `changes`。每出一版有没通过的条目，制作进度在同一条回复里跟着更新。
4. ⑤ 收尾时，上线结果写进 `launch`（每项写什么按 `agenticapp-stage-5-launch`），再保存新的一版。

## 表单与记忆卡

按轮问的一轮、收集参数或文件用表单；这一轮用到了开发者偏好时可以发记忆卡。两者都由脚本校验并生成，把输出的一整行原样贴进最终回复：

```bash
python3 <本 Skill 目录>/scripts/studio_card.py form --id round-2 --title "需求确认 · 第 2 轮" -   # 标准输入给表单体 JSON
python3 <本 Skill 目录>/scripts/studio_card.py memory -                                         # 记忆卡体 JSON
python3 <本 Skill 目录>/scripts/studio_card.py reply <整条回复的文件>                              # 排查为什么没显示
```

退出码非 0 时按它列出的每一条改 JSON 再跑。表单是最终回复的最后一段，一条回复最多一张表单、一张记忆卡。表单体怎么写、按轮问怎么映射、答案怎么回来见 [references/表单与记忆卡.md](references/表单与记忆卡.md) 和 [references/表单控件.md](references/表单控件.md)。

## 各段和任务在 Studio 下的不同

开工、各段、接续、修订、云端保存在 Studio 下各怎么做，读 [references/各段和任务在Studio下的不同.md](references/各段和任务在Studio下的不同.md)。

**写入结果未知**：Studio 工具或平台写入（保存、登记确认）返回结果未知时，只查询原操作的结果，不重新发起写入。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 开工就把四份开发文档一起写出来 | 只写当前段的那一份 |
| 手写或手改 `index.html`、自己加样式 | 改 `data.json` 和 Demo，重新生成 |
| 生成脚本报错，删掉报错的字段绕过去 | 按报错补齐内容；写不出来的就是还没查到、没跑到，先去查、去跑 |
| 生成成功就保存，没看过页面 | 截图看两种宽度，对过检查清单再保存 |
| 没调 `studio_select_application`、没传 `baseArtifactId` 就保存 | 先登记应用，保存前读当前一版并传它的 `artifactId` |
| 保存成功就当作开发者已确认 | 读回已确认才往下走 |
| Demo 里连真实服务、真存数据，或把 Demo 的结果写成做好了 | Demo 只用示例数据；做没做好看制作进度和验收报告 |
| 手写表单标签 | 用 `scripts/studio_card.py` 生成 |
