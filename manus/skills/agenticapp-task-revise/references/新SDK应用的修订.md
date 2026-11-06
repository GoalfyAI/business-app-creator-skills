# 新 SDK 应用的修订

修订前认路、把旧应用迁到新 SDK、让使用者在上一趟交付的基础上修正时读。新旧两条路在保存路线、冒泡、真跑、前端 SDK 上的其他差别，见 `agenticapp-tool-workflow`、`agenticapp-tool-deploy`、`agenticapp-tool-frontend` 各自的新 SDK 一段。

## 先认是哪条路

- 新旧怎么判定见入口 [平台对象与用词.md](../../agenticapp-creator/references/平台对象与用词.md)；新 SDK 的「执行」是什么见 `agenticapp-tool-workflow`「新 SDK 应用的路线」；新建应用走哪条路由脚手架模板决定，见 `agenticapp-tool-workspace`「初始化与接续细则」。
- 同一应用的旧版本仍走旧路；发布新 SDK 版本后，新发起的执行走新路。

## 旧应用迁到新 SDK

迁移是一次修订，按 SKILL.md 的起点表属于「只改做法」，从 ③ 进（`agenticapp-stage-3-build`），试用验收后再上线。

1. **编排格式不变**：从场景包取出 `workflow_orchestration` 与 TPE 清单，去掉需要运行 Agent 的写法（哪些写法不能用见 `agenticapp-tool-workflow` 的新 SDK 一段）。
2. **核对节点工具**：节点在旧路就只用它的 TPE 自己挂的工具集，迁移不改变节点能用的工具；场景包工具箱里的工具是给主控 Agent 用的，不用搬。只需确认每个节点脚本调用的工具都挂在该节点 TPE 上；旧应用里偶有脚本调了 TPE 没挂的工具，借迁移补上（`update_asset_relations(asset_type="tpe", asset_id, add_toolset_ids)`）。
3. **挂到应用草稿**：`business_ui_manage(action="update", business_ui_id, workflow_orchestration, tpe_ids)`。保存是整体替换，规则见 `agenticapp-tool-workflow`。场景包挂载与编排挂载互斥，同一份草稿只留一种。
4. **换新 SDK 脚手架**：页面改成以执行为单位（写法以模板 `frontend/src/sdk/docs/README.md` 为准，见 `agenticapp-tool-frontend`），重新部署、试用验收后再上线；发布由开发者决定。
5. **上线前告诉开发者**：发布后，旧路上停在等待使用者的执行会被平台取消并通知使用者。

发布新 SDK 版本受灰度名单控制，被拒时把原文告诉开发者，不为了能发布改回旧路。

## 修正上次交付

使用者审阅不满意、要在上一趟的基础上改时，加一条修正路线，写法见 `agenticapp-tool-workflow`「新 SDK 应用的路线」「修正上次交付」。

## 和修订有关的报错

| 错误码 | 意思 | 怎么做 |
|---|---|---|
| `BUSINESS_UI_NO_SCENARIO_PACK` | 应用版本既没挂场景包也没挂编排，上传或部署被拒 | 先用 `business_ui_manage(action="update")` 挂编排与 `tpe_ids` 再部署 |

其余新 SDK 错误码（`APP_VERSION_NOT_LAUNCH_AGENT`、`APP_VERSION_OUTDATED`、`EXECUTION_STATE_LIMIT` 等）见 `agenticapp-tool-workflow`「冒泡和执行里可能遇到的错误码」。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 修正路线不读 `ctx.previous_delivery`，从头重做 | 读上一趟的文件，在它基础上改 |
| 迁移时把场景包工具箱整个搬到节点上 | 只补节点脚本实际调用、TPE 还没挂的工具 |
| 同一份草稿同时留着场景包挂载和编排挂载 | 两者互斥，只留编排 |
| 灰度名单拒绝发布后改回旧路 | 把原文告诉开发者，由他决定 |
