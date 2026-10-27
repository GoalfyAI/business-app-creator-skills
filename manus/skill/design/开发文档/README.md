# 开发文档：在 Studio 里交给开发者的四份 HTML

当前宿主提供 Studio 制作工具（工具列表里有 `studio_write_proposal`）时，PRD、方案、制作进度、验收报告各写成一份 HTML，交给 Studio 第三栏「开发文档」显示。四份共用一套样式和组件，照这里的模板写，不自己设计版式。没有这些工具时（Codex 命令行、Claude Code 等），照原来的方案页写，见 [../../reference/开发者中心与工作区.md](../../reference/开发者中心与工作区.md)「方案页」。

## 哪一段写哪一份

| 文档 | 第一次写 | 之后更新 | documentType | 要开发者确认 |
|---|---|---|---|---|
| PRD | ① 按轮问问完、开发者回「对」之后，写第 1 版 | 开发者批注后出新一版 | `prd` | 要，回「确认这一版」 |
| 方案 | ② 取舍题问完之后，和判断题一起发 | 判断题答「不对」改完后出新一版 | `proposal` | 要，判断题都答「对」 |
| 制作进度 | ③ 开始时 | 每做好一个功能、每跑完一次「我先跑了一遍」、每出现或解决一个问题 | `progress` | 不要 |
| 验收报告 | ④ 报告过了硬门之后 | 按反馈重测后出新一版；⑤ 上线后在最后补「上线结果」，再出一版 | `acceptance` | 开发者看完回「可以上线」 |

- **禁止**提前写后面段的文档：① 里只有 PRD，② 里才有方案，依此类推。还没到的段没有文档，不写「暂无」「未开始」的占位页。
- 开工后第一次实质答复前写下的业务目标、范围、待明确事项，记在阶段文档 G1，不单独交一份 PRD 草稿；PRD 第 1 版等按轮问问完再写。

## 怎么写一份

1. 读 [样式.md](样式.md)、这份文档的版式文件（[PRD.md](PRD.md)、[方案.md](方案.md)、[制作进度.md](制作进度.md)、[验收报告.md](验收报告.md)）、[样例.md](样例.md) 里对应的样例，和 [检查清单.md](检查清单.md)。
2. 在应用工程里写 `docs/studio/<documentType>/index.html`：开头原样复制样式，正文原样复制骨架，再把每个【填：…】换成真实内容。方案另写 `docs/studio/proposal/acceptance.json`。
3. 按检查清单逐条自查，P0 全部满足才交；自查结果写进当段阶段文档，不发给开发者。
4. 调 `studio_write_proposal`：`documentType` 按上表，`version` 写 `<documentType>-<版本号>`（例如 `prd-2`、`progress-7`），`files` 放 `index.html`，方案加 `acceptance.json`。保存成功只代表存好了，不代表开发者已确认。
5. 同时发交接消息（[../交接消息.md](../交接消息.md)）。消息里说文档在「开发文档」里、这一版改了什么，不把文档全文贴进聊天。

更新时在上一版的 `index.html` 上改，只动变化的部分，`version` 的版本号加一。要读 Studio 里已存的版本，用 `studio_read_creation`，按 `documentType` 读。

## 确认怎么登记

PRD 和方案要开发者确认。开发者在聊天里明确同意当前这一版（「确认这一版」「可以，开始吧」）后：

1. 用 `studio_read_creation` 读这份文档当前的 `artifactId`、`version`、`digest`；
2. 调 `studio_confirm_proposal`，传 `documentType`（`prd` 或 `proposal`）、上面三项和开发者的原话 `userStatement`；
3. 读回确认状态，再往下走。

模型总结、引用、含糊的回复不算确认。新一版不继承旧版的确认，要重新确认。
