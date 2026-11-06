# 各段和任务在 Studio 下的不同

Studio 宿主下开工、做某一段、接续、修订或云端保存时读。没写到的做法和其他宿主相同。

| 段或任务 | Studio 下怎么做 |
|---|---|
| 开工 | 命令环境自带 `GOALFY_SCAFFOLD_DOCUMENT_MODE=studio`，`scaffold:init` 照常运行，不另传 `--document-mode`；脚手架把 `document_mode: studio` 写进 `WORKSPACE.md`，不生成 `docs/proposal/`，之后 `doctor`、`scaffold:repair` 和发布验证都沿用这个模式，不补回方案页。交付物的最小草案（开工时记下的业务目标、范围和待明确事项）记在阶段文档 G1，不交 PRD 草稿 |
| ① 按轮问 | 一轮的题用表单发（[表单与记忆卡.md](表单与记忆卡.md)）；PRD 写成开发文档 PRD |
| ② 方案 | 写成开发文档「方案」，另交与验收条目一致的 `acceptance.json`；工程里的 `studio.acceptance.json` 与它验收范围一致，格式按宿主和脚手架合同，不自行增减条目。验收条目另写一条「在 Studio 里打开看各页面」（按 `agenticapp-stage-2-plan`「哪些必须各写一条」），④ 把它记「未测」（按 `agenticapp-stage-4-acceptance`「「未测」只能用于这几类」） |
| ③ 制作 | 第一个动作是 `studio_write_proposal(documentType="progress")` 保存第一版制作进度，`studio_read_creation` 读回保存成功后才建资产、写代码 |
| 演示预览与演示版 | 桌面入口管理当前工程的开发服务：你只准备工程与依赖，不另起后台服务；演示版验收时桌面入口已在跑当前工程的开发服务就直接用它，不另起、不停掉 |
| ④ ⑤ | 见 SKILL.md「验收报告」 |
| 接续 | 用 `studio_read_creation` 读开发文档；只有方案记录、没有 PRD 记录的算没有 PRD，先补成 PRD 差异版按 `documentType=prd` 交，请开发者确认一次；已经上线的按 `agenticapp-task-revise`。已有的方案记录不当作 ② 已确认的方案，不凭它跳过 ① ②，也不改写它 |
| 修订 | 先用 `studio_read_creation` 分别按 `documentType="prd"`、`"proposal"` 读当前确认状态，以宿主返回为准；改动在已确认范围内的不自行增加确认步骤；要改 PRD 或方案的，按 ① 或 ② 保存新的一版，请开发者重新确认 |
| 云端保存 | `workspace_push` 的清单里没有方案页就不传；`docs/studio/` 的开发文档副本不传 |
