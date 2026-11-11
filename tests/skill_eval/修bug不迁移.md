# 测试目标：旧路存量应用修 bug 不重新拉脚手架、不迁移；重新拉脚手架时按 Skill 自带的迁移指南迁完

用法：`skill-eval goal start --branch feat/D4133-修bug不迁移-v2/main --goal-file tests/skill_eval/修bug不迁移.md -k 2`（R-683 第 4 版第 5 项，D-4133；升级指南随 Skill 发布见 R-438 第 9 版）。

## 改了什么

- `reference/脚手架与预置件.md` 新增「修 bug 不迁移与重新拉脚手架」：所在路以返回的 `scaffold_route`、`route_source` 为准；修 bug、加功能在现有工程上改完部署，不重新下载模板、不迁移，`upgrade_recommended=true` 只记开发记录；必须升级或确需换模板时才重新拉脚手架，旧路应用拿到的就是 SDK 5 模板，按本 Skill 自带的升级指南（`scripts/upgrade_guides.py candidates`，含旧应用迁到新路的指南）迁完，不问开发者要不要迁；`base_source=current_is_latest` 是已是最新；`sdk_major_skipped` 且 `scaffold_route=legacy` 不是已是最新，其他 `sdk_major_skipped` 按已是最新结束。
- `tasks/升级.md`：识别信号写明修 bug、加功能和只有建议升级时不进升级任务；第 1 步「旧路跨主版本」：要重新拉脚手架时照样运行候选脚本，第 4 步记 `skipped`，第 7 步按迁移指南迁固定层与 SDK。
- `tasks/修订.md`：修 bug 不迁移；开发者要迁新路时走《升级》。
- `reference/新路应用.md`「旧应用迁到新路」：以本 Skill 自带的迁移指南的动作和测试为准。

## 前置条件（出题时必须满足）

- 两个任务都在 QA 上用一个旧路存量应用（`frontend/goalfy-app.json` 没有 `executor`，SDK 4.x，有业务提交，部署版本不低于 QA 旧路最低线）。QA 新建应用拿到的是最新模板（SDK 5），从零做出来是新路应用，测不到本目标，所以要用预置的旧路应用接续，不能从零建。
- 任务一：应用有一个可复现的页面问题（例如列表页状态筛选不生效）。
- 任务二：开发者明确要求重新拉脚手架（例如「把这个应用升级到新的脚手架」），或提出需要新 SDK 能力的改动；不需要应用处于必须升级状态。

## 要验证的问题

1. 修 bug 不迁移：开发者只说「列表页按状态筛选没反应，帮我修一下」时，Agent 是否在现有工程上修、`npm run verify:release` 后部署；轨迹里没有第二次 `download_template` 下载、没有 `upgrade_plan` 后的固定层替换、没有 `business_ui_manage(action="update", workflow_orchestration, tpe_ids)`、没有改 `frontend/goalfy-app.json` 的 `executor`。出现任一迁移动作即失败。
2. 不把 SDK 升级当前提：下载入口返回 `upgrade_recommended=true` 时，Agent 是否只在开发记录写「建议升级脚手架版本」，修完照常部署；交接消息里没有要求开发者先升级、换模板或迁新路。
3. 判路记录：Agent 是否把 `download_template` 返回的 `scaffold_route`、`route_source` 原样记进开发记录，没有自己按版本串另判。
4. 重新拉脚手架按指南迁完（任务二）：`upgrade_plan` 返回 `fixed_layer.base_source=sdk_major_skipped`、`scaffold_route=legacy` 时 Agent 没有按已是最新结束；运行 `scripts/upgrade_guides.py candidates`，按候选里旧应用迁到新路的指南逐条做，第 7 步迁移固定层与 SDK，没有停下问开发者要不要迁；指南要求告知的影响照常告知，发布时间留给开发者定。
5. 照做后能跑通：任务一部署成功（`gate_passed=true`）且问题修复；任务二 `verify` 通过、`goalfy-app.json` 的 `executor` 为 `launch_agent`、每条路线冒泡跑到完成。
