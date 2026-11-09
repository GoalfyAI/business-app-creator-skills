---
name: agenticapp-tool-frontend
description: 写或改智能应用的页面前必须加载，包括「页面改一下」「加个按钮」「看板换个样子」。表结构用 agenticapp-tool-data-template，放到在线预览用 agenticapp-tool-deploy。
---
# 前端页面

这个 Skill 管使用者看到的页面：长什么样、怎么经 SDK 接平台、哪些页面必须有、文案怎么写、做完怎么查。页面规则的正本在应用工程里（`frontend/README.md`、`frontend/docs/business-ui-guide.md`、`frontend/src/sdk/docs/`），这里只写最容易出错的约束。

样子按这个优先级定：**方案的信息架构、「功能与页面」和开发者之后反馈里说的样子** > 本 Skill 的自定规则 > 脚手架预置件和起始应用的默认样子。开发者没说过外观时按自定规则做。

## 先定样子

- 开发者说过要什么样就做成那样，可以整页自己写、大改预置件或自写外壳；只换品牌色和圆角不算满足他的风格要求。开发者给了参考网站时，读 [references/界面风格与参考网站.md](references/界面风格与参考网站.md)「参考网站」。
- 开发者没说过，就按行业与调性定品牌色、Logo、导航图标、布局、圆角、首页重点，一句话一项写进 G5。交付时不能还是缺省蓝色、名字首字方块 Logo、单字导航。做成：G5 里六项各有一句，`config.ts` 的 `APPEARANCE.accent`、`BRAND.logo`、`NAV` 各项 `icon` 已按它改过。
- 开发者确认过的页面样子记进 G5 作基线，返工和修订不改动，改完逐项核对：[references/界面风格与参考网站.md](references/界面风格与参考网站.md)「确认过的样子是基线」。
- 配色跟随宿主亮暗：开发者给的一套配色原样作亮色，暗色按同一色相自己配。
- 预置件：先按方案信息架构定导航、主工作区和信息优先级，再读 `frontend/registry.json` 选件；不改 `ui/`、`blocks/` 源码。怎么用、能不能换 UI 框架读 [references/界面风格与参考网站.md](references/界面风格与参考网站.md)「开发者要的样子优先」。

自写或大改时保住的是平台行为：照样经下面的 hook 和组件接平台，要保住的几项、完整规则、自定外观的对照表、参考网站和 Logo 的做法见 [references/界面风格与参考网站.md](references/界面风格与参考网站.md)。

## 首屏与导航

按使用者要完成的事组织，不按功能模块或平台对象组织：首页是业务工作台；导航顺序 = 使用者完成业务的顺序；空库与日常分开设计；示例数据连到业务；不露平台信息。每条的具体要求读 [references/首屏与导航.md](references/首屏与导航.md)。

## SDK 与保留件

- SDK 的 App 层和项目句柄层见 [references/SDK与预置件.md](references/SDK与预置件.md)。`permission='view'` 时置灰全部发起与写入入口。
- **保留件必经，不改不删**：`useProject`、`useProjectExecution`、`useProjectDraft`、`useInbox`、`useRuntimeUserFiles`、表单渲染、错误归一化、`FileField`、`MarkdownContent`、局部错误边界。表单 schema 的唯一来源是契约包 `forms/` 与 `getForms(formId)`。
- **一切平台调用经 SDK**：后端走 `sdk.api.request`（纯路径、GET/DELETE 无 body、载荷 ≤ 256 KiB；`code !== 0` 必须给使用者反馈，不静默失败、不自动重试）；不用 fetch / XHR / axios（ESLint 硬禁）。
- **场景包契约**写进 `frontend/schema/packs/<pack>/`（格式见 `frontend/schema/README.md`），入口表单、项目层、表单应答、交付审阅由预置件按它推导；`goalfy-app.json` 的 `packs` 与这个目录下的子目录一致，前端契约门禁会查。

## 必备页面

| 页面 | 要求 |
|---|---|
| 首页 | 根路由是欢迎页或业务展示页（可以就是看板），不是占位或空白；待办入口带 `useInbox().unreadCount` 角标 |
| 历史运行入口 | 使用者要能找回以前每次发起的进度与结果。不放通用「项目列表」页，导航与文案不出现「项目」。默认做法和刷新规则见 [references/业务页面.md](references/业务页面.md)「历史运行入口」 |
| 消息中心 | 必经 `useInbox()`；条目带归属项目、表单显示名、文案；点击导航到对应项目的应答状态 |

## 业务页面

每页先列出几种状态（没数据、资料不全、处理中、失败、完成）各显示什么；同一个判断只在后端或路线算一处。看板、入口表单、项目页与交付审阅、宿主小喇叭跳转（`goalfy-app.json` 的 `routes`）、人话展示、表单与文件的写法见 [references/业务页面.md](references/业务页面.md)。其中三条最常出错：入口表单要等文件全部上传完才可提交；交付审阅只提交 `{ action_key }`；项目句柄只建一次，各子路由共享。做成（交付审阅）：`npm --prefix frontend run check` 通过，审阅应答缺 `action_key` 或夹带字段时它直接失败。

## 数据管理页

- 用生成器出，不手写：把 `dataset_template_workspace(action="inspect")` 返回的 `columns` 原样存成 `<表名>.json`（形如 `{"table","label","columns":[…]}`），执行 `npm run gen:pages -- --table <表名> --label <中文名> --spec <表名>.json`。生成什么、被拒怎么办读 [references/数据管理页生成器.md](references/数据管理页生成器.md)。做成：生成器没有拒绝，这张表的列表、详情、新建、编辑页和后端 CRUD 已生成，并接进路由和导航。
- 只对 `editable:user` 列开放编辑，`agent` 列只读并标来源；批量与删除有确认；错误按后端信封 `code/msg` 呈现。

## 后端接口

生成的 CRUD 够用就不写。要统计或生产回流时在 `backend/src/common` 上包一层（`createCrudService` 的 `applyGeneratedResult` 写 agent 列），先写 `frontend/schema/api/<operationId>.yaml` 再实现。哪些行由后端建见 `agenticapp-tool-data-template`「谁建行、谁写列」。

## 业务文案

名字从 PRD、真实路线、表单、记录和产物里取，写成完整短语，整体业务对象和每个入口的动作分别命名；不用「任务 / 提交 / 查看」这类空词。配置字段和接线只按当前模板 `frontend/README.md`「业务文案」。做完沿 G5 的「已确认业务含义—界面文案—实际页面/动作」逐个场景核。细则见 [references/业务文案.md](references/业务文案.md)。做成：G5 的每个场景都对上了实际页面的文案和动作，没有配置了却没接线、仍是默认词的入口；构建和静态词检查通过不算这一条做成。

## 清起始件

页面做完、在演示版上跑之前一次做完：

1. 去掉示例包 `demo-pack`：初始化时用了 `--without-demo-pack` 的已经没有；否则删掉 `frontend/schema/packs/demo-pack/`，并把它从 `goalfy-app.json` 的 `packs` 移出，只留本应用的包。
2. 删掉起始页占位、demo 路由和对应导航项；`npm run verify:release` 会拦留下的占位。
3. `goalfy-app.json` 的 `routes` 逐条对上 `App.tsx` 实际注册的项目页、表单应答页、交付审阅页路径，没有对应页面的那条删掉。
4. 应用自己放的示例数据在界面上标明是示例。演示版里 Mock 生成的项目和待办不删，见 [references/SDK与预置件.md](references/SDK与预置件.md)「演示版 Mock 数据」。
5. 跑 `npm --prefix frontend run check`，路由模板、packs、内部 ID 警告都清零。

## 做完怎么查

- `npm --prefix frontend run check` 通过；用布局回归查桌面与移动宽度下的溢出与裁切，并对照代码查键盘、焦点、对比度和长文本，至少修一轮（布局回归的命令见 `agenticapp-tool-workspace`「演示版页面验收」）。
- 能点、能填、能切换的地方都要有人操作过：由前端测试覆盖，或 ④ 由你在演示版上照验收条目操作（`agenticapp-tool-workspace`「演示版页面验收」），测不了的按 `agenticapp-stage-4-acceptance` 记。开发者想看时在「演示预览」看当前工程；他看了不算验收。
- 设计做不了时不静默改设计继续做，读 [references/SDK与预置件.md](references/SDK与预置件.md)「设计做不了」。
- 页面文案用需求文档的语言，注释用中文；组件单一职责，超过约 200 行考虑拆分。

## 新 SDK 应用

`frontend/goalfy-app.json` 有 `"executor": "launch_agent"` 时：

- SDK 以执行为单位：`sdk.business.start` 发起（拿到回执前禁用提交按钮），`useExecution(businessId)` 取执行句柄，消息中心聚合待答；没有项目句柄和聊天。
- 写法、表单展示定义放哪、页面版本落后（`APP_VERSION_OUTDATED`）怎么办，读 [references/SDK与预置件.md](references/SDK与预置件.md)「新 SDK 应用」。
- 旧应用的页面改成以执行为单位，属于迁到新 SDK，按 `agenticapp-task-revise`。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 开发者给了参考样式，只改了品牌色和圆角，交付的样子不算满足他的风格要求 | 按参考拆设计说明再实现 |
| 用 fetch 直连后端，ESLint 拦下或上线后跨域失败 | 走 `sdk.api.request` |
| 每个子路由各建一个项目句柄，重放把使用者拉回旧表单 | 项目层句柄只建一次 |
| 数据管理页让使用者改 `agent` 列 | 只开放 `editable:user` 列 |
| 写占位页、手写本该由生成器出的数据页，或在应用代码里建表改表；占位会被 `verify:release` 拦下，应用角色没有 DDL 权限，建表改表执行不了 | 用 `gen:pages`；表结构只走数据模板 |
| 留着起始页占位或示例包，`verify:release` 失败；前端契约门禁报 packs 不一致 | 按「清起始件」做，`packs` 与 `frontend/schema/packs/` 目录一致 |

其他常见错误在上面各节指向的 references 的「常见错误」里。
