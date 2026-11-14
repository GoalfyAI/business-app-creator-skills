---
name: agenticapp-tool-automation
description: 调用 business_ui_automation、或在 business_ui_manage(update) 里写 automations 前必须加载；开发者要「每天早上自动跑」「数据一变就通知」时也加载。没按时触发要查原因用 agenticapp-task-diagnose。
---
# 自动化：到点或数据一变就自动发起路线

自动化是给应用声明「到点自动做」或「数据一变就自动做」：到了计划时刻（定时触发），或使用者实例库里声明的表有新增、修改、删除（事件触发），平台以使用者本人的正式身份自动发起一条路线，提交它的入口表单。声明写在应用版本上（`business_ui_manage(action="update", automations=[…])`），场景包不改；`business_ui_automation` 管校验、冒泡和发布后查看到点结果。

自动化只在应用发布后可用，开发者本人也一样。制作和验收时能验的是声明和处理逻辑；到点真触发要发布后在应用的「自动化」面板开规则才有。

前提：PRD 写了「到点自动做」或「数据一变就自动做」；要自动发起的路线已按 `agenticapp-tool-workflow` 建好并组装进场景包（新 SDK 应用挂在应用版本上）。

平台怎么发起、每条自动化必须全部有的条目、声明字段、事件触发的运行规则、三种收尾方式和费用，都在 [references/自动化.md](references/自动化.md)，动手前先读。

## 把路线改成能无人值守跑到交付

自动发起时没有人在旁边答题。逐条对照 [references/自动化.md](references/自动化.md)「每条自动化必须全部有」改路线，改法在它的「声明与校验」：

1. 入口：每个必填字段都要能在声明 `params` 里给出来源；给不出来的，让路线第一个节点自己取数（例如按日期查收银系统），入口只留能预先确定的字段。入口不能有文件字段，改成路线内从数据源或应用库取文件。
2. 中途：路线里不能有运行中交互（`after_success` 表单）和 `sa_handoff`。中途判断改成规则或 FA 判断；做不到的这条路线只能人工发起，照实告诉开发者，问他接不接受。
3. 自给：前置记录由路线内节点创建，产出回流也在路线内完成（`agenticapp-tool-data-template`「谁建行、谁写列」）。应用后端在无人访问时可能缩容到 0，不指望到点时它在线接回调。
4. 幂等：重复触发不重复写。同一计划时刻平台只发起一次，但立即运行与失败后再跑仍会再来一次；写库按业务键幂等，缺唯一键与累加规则的回数据模板补。
5. 收尾：结果不需要判断的用直接交付，路线 `delivery.review` 写 `type:"user_gate"`、`message_type:"result"`，只声明一个 `complete_business` 动作，`delivery.mapping.text` 指向发给使用者的那句话。只写 `user_gate` 不加 `message_type` 是等使用者确认。三种收尾的效果和费用见 [references/自动化.md](references/自动化.md)「收尾方式」。
6. 业务条件（当天已经生成、应用开关没开、配额用完）放在路线第一个节点判断；不用执行时照常输出一句说明映射到 `text` 并结束。
7. 事件触发的：单次运行要短，批量处理放进一条路线，不要每行一次；大字段不作 `event_field`，改成路线里按主键查库。

改了路线的，按 `agenticapp-tool-workflow`「组装路线」整份保存，再按它的「路线冒泡」跑一次。做成：上面七条逐条对过，路线反读里没有中途表单和 `sa_handoff`，`delivery.review.type` 是选定的收尾方式。

## 写声明

1. `business_ui_manage(action="update", automations=[…])`，每条声明写：
   - `automation_key`：跨版本保持不变。改了等于删掉旧自动化，使用者已开的规则会被暂停并要求重新确认。
   - 触发方式：定时 `trigger{type:"schedule", default_cron（5 段）, timezone, min_interval_minutes, user_editable}`；事件 `trigger{type:"event", table, operations, watch_columns, max_runs_per_hour, timezone}`，`max_runs_per_hour` 必填。定时与事件之间改触发方式，使用者要删掉旧规则重新开启。
   - `params`：入口每个必填字段一个来源，`fixed`、`user`、`trigger_var`、`event_field`（仅事件触发）四种，各自能填什么见 [references/自动化.md](references/自动化.md)「声明与校验」。每个 `event_field` 参数写 `label`，需要说明格式时写 `help`。
   - `timeout_minutes`，以及 `review`（`user_gate` 或 `agent_gate`，缺省 `user_gate`），`review` 必须等于路线的 `delivery.review.type`。
2. 排队上限、逐条触发的行数上限、连续失败几次自动暂停这类数值归平台管理，不写死进设计，以 `validate` 返回和平台当前配置为准。

做成：保存成功。平台在保存和发布时逐项校验，不满足直接拒绝，按返回逐条改。

## 校验和冒泡

1. `business_ui_automation(action="validate")` 校验声明。挂着本人场景包草稿时直接对草稿校验，不用先把场景包上线。做成：`validate` 通过，返回的 `validated_against` 是你挂载的那一行。
2. `business_ui_automation(action="bubble")` 按自动化的入口在开发工作集里跑一次，验处理逻辑。做成：跑到终态、结果符合 PRD，`run_id` 与结果留作 ④ 的证据。
3. 这两个是 ④ 的证据。到点真触发要发布后开规则才有，④ 记「未测」（`agenticapp-stage-4-acceptance`），上线结果里告诉开发者发布并在「自动化」面板打开规则后才会自动跑。
4. `run_once` 以开发者身份用当前已部署的那一版在开发工作集里跑一次，结果不作验收证据（见 [references/自动化.md](references/自动化.md)）；`run_status` / `run_stop` 看和停。

各动作的花费按入口「花费」；冒泡和自动化运行都花开发者的积分。

## 发布后查看到点结果

开发者发布并给自己开启规则后回来问到点结果时：

1. `business_ui_automation(action="rules")` 核对规则是否已保存、状态和下次运行时间；返回的 `version` 是每次运行用的当前上线版本。被拒时请开发者先从 GoalfyMax 打开一次这个应用。
2. `business_ui_automation(action="runs", rule_id=…)` 看到点后是否已发起、结果如何。返回空列表只说明本人没有运行记录。

这两个动作只读，不能开启或修改规则；规则的开启与暂停只在应用的「自动化」面板。

**新 SDK 应用**（`frontend/goalfy-app.json` 有 `"executor": "launch_agent"`）：到点在使用者实例的隐藏项目里发起一次执行，不另建项目；满额时延后，不算失败。收尾只能直接交付或等使用者确认，没有 Agent 收尾，路线和声明都不用 `agent_gate`。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 把 `run_once` 的结果当 ④ 验收证据 | ④ 只用 `validate` 和 `bubble`；到点真触发记「未测」 |
| 想验到点真触发，先去上线或催开发者发布 | 上线在 ④ 部署成功后做，发布由开发者定；到点真触发照记「未测」 |
| 在开发工作集里写库，等事件规则触发 | 事件触发只看使用者实例库，开发工作集里的写入不会触发；处理逻辑用 `bubble` 验 |
| 以为写了 `user_gate` 就是直接交付 | 直接交付要显式写 `message_type:"result"`，缺省是等使用者确认 |
| 声明的 `review` 和路线 `delivery.review.type` 不一致，保存被拒 | 改路线的审阅形态或改声明，两者一致 |
| 改版本时换了 `automation_key` | 保持不变；改了使用者已开的规则会被暂停 |
| 指望事件逐行处理批量导入 | 一条语句批量改很多行时只有前面一部分逐条触发；需要全量处理的改成定时触发 |
| 用 MCP 给开发者开启或暂停规则 | MCP 不提供；请开发者在应用的「自动化」面板操作 |

其他常见错误见 [references/自动化.md](references/自动化.md)「常见错误」。
