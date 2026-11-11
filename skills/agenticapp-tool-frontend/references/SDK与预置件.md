# SDK 与预置件

查 SDK 有哪些能力、写新 SDK 应用的表单与版本处理时读。保留件和平台调用的硬约束在 SKILL.md「SDK 与保留件」；预置件怎么选、怎么改、能不能换 UI 框架见 [界面风格与参考网站.md](界面风格与参考网站.md)「开发者要的样子优先」。

## SDK 的两层

- **App 层**（顶层 `sdk`）：`session`（实例上下文与权限，只读时页面怎么做见 SKILL.md「SDK 与保留件」）、`projects`、`getProject` / `createProject`、`inbox`、`api`（自家后端）、`storage`（界面意图）、`ui.reservedAreas`（宿主浮层占用区，交互组件要避开）、`theme`、`file`（应用级文件）。
- **项目句柄层**：`business`（start / onCall / reply / onResult / 查询）、`upload`、`file`、`chat`、`observe`、`info`。

## 设计做不了

设计做不了（SDK 拿不到的数据、路线不发的事件）时按 `agenticapp-stage-3-build` 回去改清单或契约，不静默改设计继续做。

## 演示版 Mock 数据

清起始件时：演示版里 SDK 内置 Mock 生成的项目和待办（如消息中心的「待补充信息项目（mock）」）不是应用的数据，部署后没有：不为去掉它删消息中心、待办角标或改 Mock，开发者问起时照这个意思说明。

## 新 SDK 应用

- 写法以模板 `frontend/src/sdk/docs/README.md` 为准，SKILL.md 和 [业务页面.md](业务页面.md) 里写的项目句柄接法按它换成执行。

- 表单展示定义放 `frontend/schema/packs/<pack>/forms/` 与 `orchestrations/`，构建时收集；`goalfy-app.json` 的 `packs` 列出用到的目录。
- 页面版本落后时（`APP_VERSION_OUTDATED`）页面让使用者刷新；旧版本的执行不能再回复，要重新发起。
