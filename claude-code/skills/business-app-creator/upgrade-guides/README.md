# 智能应用升级指南

本目录随制作 Skill 一起发布。某张 D 的改动会让已有智能应用的代码或开发方式跟着变时，在这里写一份 `<D编号>.md`：开发者升级应用时，《升级》任务（[../tasks/升级.md](../tasks/升级.md)）用 [../scripts/upgrade_guides.py](../scripts/upgrade_guides.py) 读本目录，按应用的 `docs/upgrade/history.json` 算出还没处理过的指南，逐条判断、修改和测试。

## 什么时候要写

需求改到下面任一项时，必须同时更新制作 Skill 的说明，并在本目录写一份指南：

- 编排或 workflow 的写法；
- SDK 的用法；
- 上了开发者要用的新功能。

只改 Studio 桌面端的 D 不写指南。4.1 版本线已冻结，新指南只适用 SDK 5.x。

## 谁写、什么时候随 Skill 发

- D 的开发方写指南，和 Skill 说明改动放在同一个 Skill 仓库合并请求里；开发独立审查逐条核对，验证方用夹具应用实跑指南。
- 指南随哪一版 Skill 发出，就从那一版起生效。Skill 发版必须排在指南对应的平台需求上线之后（同一班车内顺序：平台服务 → 脚手架 → Skill）。

## 应用什么时候读

只在拉了新的 SDK 5.0 模板之后读：旧路应用重拉 5.0 模板迁到新路后读 D-4001 及之后的指南；5.0 应用升到更新的 5.0 模板后读本应用还没处理过的指南。不拉新模板时不读，旧路应用改 bug 不重拉模板、不读指南。

## 文件约定

- 每张 D 一份，文件名 `<D编号>.md`，与文件头 `did` 一致；单个文件不超过 16KB。本目录只放 `README.md`、`schema.json` 和指南文件。
- 文件开头是一个 JSON 对象，用 `json` 代码块包起来，之后是补充说明正文。
- 结构规则以本目录 `schema.json` 为准：`did`、`title`、`impact`（`none`/`recommended`/`required`）、`applies_to{layers, when}`（layers 取 `scaffold`/`sdk`/`skill`/`mcp`/`platform`）、`already_done_check`、`actions[]`、`tests[]{id, kind=command|check, run 或 how, expect}`、`replaces[]`、`withdraws[]`，可选 `depends_on[]`。
- 关系规则：`recommended`/`required` 至少 1 条测试；测试 id 不重复；只撤回旧指南的指南 `impact` 为 `none`；`replaces`、`withdraws`、`depends_on` 指向本目录已有文件、不指向自己、不成环；同一个 D 只能被一份指南 `replaces` 或 `withdraws`。
- 应用记账用文件内容 sha256 的前 16 位（`sha`）；改动文件里任何一个字节都会让已处理过的应用重新看到这份指南。

## 发布后不可修改

已随某一版 Skill 发出的指南文件冻结：不能修改、删除或改名。需要更正、撤回或补写时，另开新 D 写新指南，用 `replaces`（内容需要保留时）或 `withdraws` 指向旧指南。

用 `replaces` 替代旧指南时：

- 先读被替代指南的全文，逐条核对它的 `actions`、`tests` 与 `already_done_check`。
- 新指南要包含旧指南里仍然需要的全部动作和测试，只执行新指南就够；不写「先执行旧指南」，也不用 `depends_on` 指向被替代的指南。
- 新指南的 `already_done_check` 要让执行过旧指南的应用认出已完成的部分，这些应用只需补做差异。
- 其他指南的 `depends_on` 指向被替代的 D 时，脚本会改指向替代链上最终有效的那份（被 `withdraws` 的去掉），不用为此改那些指南。

## 检查

- `uv run pytest -q`：用本目录 `schema.json` 和 `scripts/upgrade_guides.py` 的同一份解析代码，检查本目录全部指南的格式与关系，并跑 `tests/fixtures/upgrade_guides/` 的正反样例。
- `uv run python scripts/build_platform_packages.py check`：同样校验本目录，并按仓库里 `skill/<版本>` 发布标签上的 `skill-release.json` 校验和核对已发布指南没有被修改或删除（需要先 `git fetch --tags`）。
- 单独校验：`python3 skills/business-app-creator/scripts/upgrade_guides.py check`。
