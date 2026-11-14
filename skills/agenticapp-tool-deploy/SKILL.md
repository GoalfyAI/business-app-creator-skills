---
name: agenticapp-tool-deploy
description: 调用 business_ui_bundle、manage_goalfymax_project 运行、business_ui_manage 上线或 task_manager 结单前必须加载：放到在线预览并上线、运行哪一版、怎么核对。页面代码用 agenticapp-tool-frontend，路线用 agenticapp-tool-workflow。
---
# 部署、实际跑、上线

三个词的意思见入口 [平台对象与用词.md](../agenticapp-creator/references/平台对象与用词.md)「部署、上线、发布」，这里只管怎么调：

- **部署**：`business_ui_bundle(action="ship")`，在 ④ 做，方案确认过就直接做，不再问。
- **上线**：`business_ui_manage(action="finalize")`，部署成功后紧接着做，不问；④ 里每次再部署也一样。
- **发布**：开发者自己在发布管理页做，没有你要调的工具（见入口「红线」）。

上线成功后这一版是开发者自己的正式版，使用者只跟发布走。实际跑和 Studio 在线预览只要部署成功，上线失败或他说这版先别上线时，验收照常做。

## 部署

前提：方案已确认（修订时这次改动已确认），开发者没有说先别放；在演示版上测过的就是要部署的这份代码。

已经部署过、这次是重新部署时，提醒以工具返回为准：`ship` 返回更新提醒，就先在回复正文里原样发给开发者再上传。受影响的功能这时要已改回「在做」（`agenticapp-stage-4-acceptance`「按反馈改」）。更新中的短暂报错照实说成「正在更新」，不说成配置错了或部署不了。

1. `business_ui_bundle(action="download_template")` 核脚手架门槛，需要升级时先按 `agenticapp-tool-workspace`「脚手架升级」升级并验证。做成：返回的 `upgrade_required` 不是 `true`。
2. 应用根运行 `npm run verify:release`，全部通过后得到 `.pack/business-ui-bundle.tar.gz`；按这个包算 `source_sha256` 和 `size_bytes`。部署包只能由它产出，不手工打包。做成：命令退出码 0，应用根下有这次新打出的 `.pack/business-ui-bundle.tar.gz`。
3. `business_ui_bundle(action="ship", task_id, business_ui_id, source_sha256, file_name="business-ui-bundle.tar.gz", size_bytes)`。传上线行时同时带 `change_note`，写这次改了什么；同一张工单上线后再部署也这样传，平台派生新草稿，版本号顺延。
   - 返回 `upload_required`：按 `upload_url` 和 `headers` PUT 源码包原字节，再带上 `bundle_key` 原参数重调；
   - 返回还没到终态：带原 `deployment_id` 续调（服务端每次最多等约 45 秒），直到 `success`。带着 `deployment_id` 续调才不会重起容器。
   - 做成：返回的部署 `status` 是 `success`。工单里版本检查记的 `gate_passed=true` 只表示版本检查通过，不代表部署成功。
4. `business_ui_manage(action="get")` 核对部署已写进当前草稿。做成：当前草稿 `has_ui: true` 且 `entry_url` 不为空；`entry_url` 为空说明部署后又派生了新草稿，在当前草稿上重新部署。
5. 记 checkpoint：`deployment_id`、`source_sha256`、`deployed_scaffold_version`。
6. 接着按下面「上线」做，再按「放好后告诉开发者」发一条。

新 SDK 应用（`frontend/goalfy-app.json` 有 `"executor": "launch_agent"`）：占位草稿要先挂上编排和 `tpe_ids` 才能部署。

## 实际跑

在开发工作集里跑，测试数据不进使用者的实例。

真跑含付费工具的路线前，先调 `business_ui_manage(action="consent_status", business_ui_id)` 读开发者本人在预览范围的付费同意状态（只读）。`required=true`（没有记录，或清单新增了工具、收费条件变了、旧记录要补确认，原因见 `pending_tools[].reason`）时先不跑：请开发者在工作台「在线预览」里打开这个应用，在弹出的付费同意清单里点同意（正式入口里点的同意只管正式范围，改变不了预览范围的状态）。点同意是开发者本人的授权动作，不算入口红线里的「不代测」；你不代点，也不请他顺带测别的；他说点完后再读一次，读到 `has_record=true` 且 `required=false` 才跑。`pending_auth_card_count` 大于 0 时，授权卡仍按 `agenticapp-tool-integration` 处理，两件事分开记。开发者暂时不点的，这几条记「未测」，原因照 `agenticapp-stage-4-acceptance` 的 [证据与未测.md](../agenticapp-stage-4-acceptance/references/证据与未测.md) 表原文。

- 真跑被付费同意拦截后，再读一次状态：`required=true` 按上面处理；`required=false` 说明已同意仍被拦，这条记「没通过」，附完整报错，按入口 [平台问题怎么报.md](../agenticapp-creator/references/平台问题怎么报.md) 提交，不记工具故障。
- 读状态失败：返回 3028（还没有已部署的预览草稿）时先按上面「部署」部署预览草稿再读；返回 3024（最新版本借用的部署已不在运行）时按「部署」在当前草稿行重新 ship 到 success 再读；其他失败（含平台还没有这个接口）不凭开发者口头说「点过了」判断，照常真跑一次，以真跑结果判定；真跑被付费同意拦截时按「预览还没有付费同意」处理，工具名取报错里的工具名，同时按「平台问题怎么报」提交读状态失败。
- 新路应用的路线冒泡（传 `business_ui_id`，含 `full_run`）是对你最新草稿的一次预览执行，付费工具同样要预览范围的付费同意：路线含付费工具时，冒泡前也按上面先读，被拦也按上面处理。旧路场景包的冒泡（传 `scene_package_id`）跑在隐藏的验证项目里，不经过付费同意门禁，冒泡前不读。

```text
manage_goalfymax_project(action="run", task_id, idempotency_key,
  scenario_package_ids=[<场景包当前草稿或上线版本的物理行 ID>],
  submit_data={"business_id": …, "orchestration_id": …, "form_id": …, "formdata": {<入口表单字段>}},
  business_ui_id=<WORKSPACE.md 里的 business_ui_id 原值>, business_ui_data_space="workspace")
```

- 旧应用：`business_id` 由你生成（如 `biz-<简称>-<日期>-<序号>`），同一业务实例里不变；`orchestration_id` 取场景包里那条路线的 id。
- 旧应用：路线读写应用库时才带 `business_ui_id` 和 `workspace`；不碰应用库就不传。
- `wait` 等到终态；中途表单或审阅用 `reply`，业务表单的 `content` 传空字符串、答案放表单数据里。卡在 `waiting-input` 而没人答是正常挂起。
- 实际花费：新 SDK 应用用带 `business_id` 的 `wait` / `status` 读本次执行的 `cost_credits`，**禁止**拿按 `project_id` 查到的隐藏项目累计当本次；旧应用读项目的。口径见入口 [平台对象与用词.md](../agenticapp-creator/references/平台对象与用词.md)「积分」。
- 结果以 `route_runs` 里各路线的状态为准（路线完成后项目可能仍显示 running）；`get_project_execution_logs(action="workflow_trace")` 看每一步。
- **跑的是哪一版**：用这个应用版本号最高、且有可用容器的版本（草稿一创建就会被选中）。只换了挂载（场景包或模板版本）、没重新部署的版本也会被选中：挂载按它解析，直接生效；容器沿用它继承的源版本，所以源版本必须部署过。改了页面或后端代码，要重新部署才生效。跑完先核对返回的 `business_ui.version` 是不是你要验的那一版（`host_version` 是实际承载的容器版本）。
- 做成：`business_ui.version` 是要验的那一版，`route_runs` 里每条要验的路线都是 `succeeded`；项目还显示 running 不影响这个判断。
- 读写应用库的路线，跑完对每条 TPE 调 `otpe_manage(action="verify", task_id, tpe_id, project_id)` 补运行证据（新 SDK 应用传这次实际跑的 `business_id`：`verify(tpe_id, run_id=<BIZ- 号>)`），见 `agenticapp-tool-workflow` 的 [冒泡与实际跑能证明什么.md](../agenticapp-tool-workflow/references/冒泡与实际跑能证明什么.md)「verify 收哪种证据」。

新 SDK 应用：不论碰不碰应用库都传 `business_ui_id` 和 `business_ui_data_space`（制作和验收用 `workspace`，上线后也一样，读写开发工作集；`instance` 读写开发者本人的正式实例，要应用已发布，制作和验收不用它），不传 `scenario_package_ids`；`submit_data` 写 `{orchestration_id, form_id, formdata}`，不放 `business_id`。`business_id` 由服务端生成、在回执里给出，用于后面的 `wait / status / reply / stop`。执行里没有对话，没有 `send`；`reply` 时 `orchestration_id` 由工具补上，按回执的 `next_action.template` 填。

## 上线

前提：角色是 `owner`；最新代码部署成功，部署后没再改过代码、编排或挂载，改过的先重新部署；开发者没说这版先别上线。

1. `business_ui_manage(action="get")` 看家族里的草稿、创建人和变更说明，选这次部署 `success` 的那一份。家族里有协作者的提请时，告诉他谁提请了什么，不等回答，接着上线自己这一版（`agenticapp-role-collab`「属主处理提请」）。
2. `business_ui_manage(action="finalize", draft_asset_id=<那一份>, task_id)`。必须显式传 `draft_asset_id`，平台不替你挑。挂在应用上的本人场景包草稿会一起上线，不要单独上线它。
3. `business_ui_manage(action="resolve")` 反读上线版本和挂载的场景包版本，两个版本号记进工单。`resolve` 报没有上线版本，就是没上线成功，照实说。新 SDK 应用没有场景包，改为核对应用版本上挂的编排与 `tpe_ids`。
4. 反读上线版本绑定的部署，确认是这次部署的那一份。做成：它的 `deployment_id`、`source_sha256` 和部署第 5 步记进 checkpoint 的相同，`entry_url` 非空。

上线只查有源码包、部署成功、容器在线和基线没过期，所以它不挡未验过的版本，也不彩排迁移；路线契约、数据模板、模板升级链和迁移彩排在开发者发布时才查，发布时也不看验收结果。

上线只有属主能做；编辑协作者用 `request_finalize` 提请，见 `agenticapp-role-collab`。上线被拒或结果不明，见 [references/报错.md](references/报错.md)「上线与下线」。

## 放好后告诉开发者

上线成功时先照抄一句：「这一版已成为你自己的正式版，在 Studio「在线预览」里能看到；我还在验收，验收完成前在发布管理页发布的话，使用者会拿到没验过的版本。」然后接着验收。验收结论由验收报告的第一句告诉他，见 `agenticapp-stage-4-acceptance` 的验收报告模板。

没有上线成功时按下表照抄。不给任何地址：`entry_url`（形如 `https://app-…goalfymax.cn`）是容器地址，应用要嵌在 GoalfyMax 里和宿主握手才能运行，单独打开只会显示「应用连接失败」（FK-1600）。

| 情况 | 说什么 |
|---|---|
| 上线没成功 | 「已放到在线预览，在 Studio「在线预览」里能看到。上线没成功：<原因的业务话>。我接着处理，验收不受影响。」 |
| 他说过这版先别上线 | 「已放到在线预览，在 Studio「在线预览」里能看到。按你说的，这一版没有上线。」不在 Studio 的，他要上线后才能在发布管理页看到 |
| 编辑协作者 | 「已放到你的在线预览，在 Studio「在线预览」里能看到。上线要由属主来做。」 |

这时不请他去试，验收由你做。

## 结单

`task_manager(action="complete")` 时平台检查每条路线：当前合同下最近一次到终态的运行通过（路线冒泡，或 `workspace` 实际跑里该路线 `succeeded`）。读写应用库的路线只认 `workspace` 实际跑，冒泡碰不到应用库，不算。没通过又补不了的，先按 `agenticapp-stage-5-launch`「等他选」问开发者继续改还是接受。读写应用库的路线不能豁免，他接受了也不写，工单开着等实际跑通；其余路线在他选接受后每条写一条豁免：

```text
task_manager(action="insert", entry_type="checkpoint", metadata={"evidence_type": "route_verification_waived",
  "scene_package_id": …, "orchestration_id": …, "reason": "<至少 5 个字>", "run_id": <失败那次；没跑过不带>})
```

新 SDK 应用把 `scene_package_id` 换成 `business_ui_id` 和 `business_ui_version_id`，两个值原样取自 `complete` 被拒时返回里给出的那一对，不换成上线返回的别的编号。豁免只记下没验证及原因，不算通过。`complete` 被拒时按返回逐条给的出口在同一张工单上补；有路线被豁免或未验证时，成功回执带 `delivery_note`，原样补进发给开发者的上线结果和交付物（结单后工单不能再写）。做成：`complete` 返回成功并带 `delivery_note`。写豁免的 `insert` 返回带 `format_warning` 时还没做完：多条路线合在了一条里，要补成每条路线一条。

## 别的版本操作

修订已上线版本、回滚、作废草稿、场景包单独上线、下线、删除，以及草稿、上线、发布各能做什么：见 [references/版本与下线.md](references/版本与下线.md)。删除、下线、回滚每一步都要开发者确认。

## 常见错误

工具返回了错误码，先查 [references/报错.md](references/报错.md)。下面是不报错、但做错了的情况：

| 错误 | 正确做法 |
|---|---|
| 部署后又改了代码，把旧部署上线 | 只上线最新代码部署成功的那一份，重新部署后再上线 |
| 按传进去的上线行 ID 反读，以为修改没生效 | 按返回的 `draft_asset_id` 反读 |
| 上线后不 `resolve`，没发现上线没生效 | 每次上线都反读 |
| 把 `entry_url` 当应用地址交给开发者 | 它是容器地址，只用于核对平台绑定和诊断，不打开、不写进任何给人看的东西。生产构建直开返回 `HOST_REQUIRED`，开发构建直开只进 Mock，都证明不了真实身份、数据或路线 |
| 被版本闸门拒绝后绕过去改状态字段、手改版本清单 | 按 `agenticapp-tool-workspace` 升级脚手架后重新打包 |
| 版本工具传 `asset_type="scenario_package"` | 这里要 `scenario_pack` |
| 用 `delete` 轮询删除进度 | 用 `deletion_status` |
| 新 SDK 应用自己编 `business_id`，或用 `send` 跟执行对话 | `business_id` 只取回执；回答中途表单和审阅只用 `reply` |
