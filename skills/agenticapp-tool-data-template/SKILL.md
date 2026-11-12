---
name: agenticapp-tool-data-template
description: 调用 dataset_template_workspace 写操作或 business_ui_manage(setup) 前必须加载；建表、加列、改表结构、迁移数据时也加载。页面怎么显示数据用 agenticapp-tool-frontend。
---
# 数据模板与开发工作集

**数据模板**是开发期定稿的表结构，含每一列由谁写和审计列。使用者第一次打开应用时，平台照模板给他建一份自己的库（**应用库**，也叫实例），应用后端直连它，编排脚本和 FA 经平台工具 `GOALFYAI_TOOL_query_business_app_dataset` 读写同一份。几个词：

- **开发工作集**：`dataset_template_workspace(action="open")` 给的独立 PG schema，用 `data_uid` 标识；建表、灌样例、跑查询都在这里，在线预览和带 `workspace` 的实际跑读写的也是它。
- **模板版本**：`extract` 从工作集抽出的整数版本；挂到应用时钉住，不跟随最新。

先记住这几条：

- 每个应用必须挂且只挂一份模板，模板里至少一张业务表（系统表不算）。
- 应用角色没有 DDL 权限：表结构只走模板，应用代码里不写 `CREATE / ALTER TABLE`。
- `extract` 只抽结构（表、列、类型、主键、注释、关系），不带样例数据。
- **没有应用就没有应用库**：场景包单独运行时这份库不存在，读写会报错；读的地方按「没有数据」收口，不报错、不编数。`dataset_read` 只读长期数据集，读不到应用库。

## 设计表

② 列表清单、③ 建表前，按 [references/表与列的设计.md](references/表与列的设计.md) 定：

- **数据放哪**：使用者的数据、路线读写的字段、系统字段进模板表；草稿、筛选、已读态进 `sdk.storage`；文案、开关写代码。该进库的不写成前端 mock 数组、静态 JSON 或后端常量；文件只存路径、文件名、时间。
- **入口字段放哪**：使用者这次才给的进入口表单；库里已有的入口只放业务键、脚本按键读库；所有人一样的写进代码默认值或场景包配置。同一个值只走一边。
- **每张表回答五问**：存什么（看板要的字段现在就有）；每列 `comment` 以 `[editable:user|agent|system] ` 开头、每列恰好一个写入方；有写入的表带审计列且 NOT NULL 的有默认值；同时改一行靠 `row_version` 乐观锁；路线产出直接入库还是先作草稿，写进 PRD。

## 谁建行、谁写列

按路线有没有应用后端参与选一种，细则和 SQL 形状见 [references/谁建行谁写列.md](references/谁建行谁写列.md)：

- **有后端参与**（使用者在页面上发起）：后端建行并填身份列，路线只 `UPDATE … WHERE id = :id` 更新 agent 列，改到的不是 1 行就返回 `blocked`「未入库」（只结束本节点，要停整条路线就抛错）。
- **路线自给**（到点或数据变化自动发起、没有后端参与）：路线自己建行，身份列与 `last_run_id` 一并填。
- 每次写入的一方随写入更新审计列；同一业务再做一次是更新还是新增，在 ② 施工单里定（更新原记录要给业务键建唯一约束）。

## 预览数据不进正式版

- 在线预览里产生的数据（包括 ④ 验收写入的）在开发工作集里；上线后每个使用者（包括开发者本人）第一次打开都从空库开始，平台没有迁移数据的机制。不承诺、不暗示预览里录入、收藏、反馈的数据会带到正式版。
- 上线后必须存在的设定不能只存在工作集数据里：所有人一样的写成代码默认值或场景包配置；每人不同的做首次设置入口，空库时页面引导去填（页面写法见 `agenticapp-tool-frontend`「首屏与导航」）。

## 建表与出版本

1. `dataset_template_workspace(action="open", task_id, name, description)`，记下 `data_uid`。
2. 每张表 `create_table(task_id, data_uid, table_name, target_columns=[…])`（推荐），或用连接串建表。主键、类型、注释、`default` 的写法见 [references/表与列的设计.md](references/表与列的设计.md)「建表时的列规则」。
3. 需要时 `set_relations` 声明关系（整体替换）。
4. `inspect` 反读，逐列核对类型、主键、注释、`default`。
5. 把 `inspect` 结果翻成业务语言，和 PRD 保存节点里写的会记下来的东西、施工单的表清单对一遍，对不上改到一致。
6. `extract(task_id, data_uid, template_name, template_description)`，记下模板 ID 和整数版本号。首次不传 `template_id`，新建模板；给已有模板出新版本传 `template_id` 和 `expected_base_version`（见 [references/模板版本与迁移.md](references/模板版本与迁移.md)「出新版本时的基线」）。
7. 按下一节挂到应用并绑工作集。

## 建应用身份与挂模板

1. **应用身份**，在 `current_stage` 改成 G5 之前：`business_ui_manage(action="setup", task_id, name, scenario_pack_id=<场景包家族 ID>, operation_id=<稳定键>)` 得到 `business_ui_id`；在应用根执行返回的 `scaffold_bind_command` 回填 `app.json` 与 `WORKSPACE.md`（见 `agenticapp-tool-workspace`「工作区文件」）。重复调用按 `operation_id` 复用，不会建出第二个应用。做成：`app.json` 的 `id` 与 `WORKSPACE.md` 的 `business_ui_id` 都是返回的应用 ID。
2. **挂模板并绑工作集**，模板版本抽出后：`business_ui_manage(action="setup", task_id, business_ui_id, dataset_template_id, dataset_template_version, data_uid)` 一次完成挂模板（版本钉整数）和把开发工作集绑到应用；已挂同版本的步骤会跳过。做成：返回 `success=true`，`steps` 里没有 `failed`。
3. 返回 `success=false`：看 `steps` 里哪一步 `failed`，修正后用原参数重调；仍失败再单步处理：`business_ui_manage(action="update", dataset_template_id, dataset_template_version)` 挂载、`dataset_template_workspace(action="bind")` 绑定。
4. 之后换挂模板版本、换绑工作集才单独用 `update` 与 `bind`；改已上线模板的换挂见「改已上线的模板」。

**新 SDK 应用**（`frontend/goalfy-app.json` 有 `"executor": "launch_agent"`）：① 已用 `business_ui_manage(action="create")` 建了应用占位、拿到 `business_ui_id`，不建场景包。第 1 步的 `setup` 传这个 `business_ui_id`，不传 `scenario_pack_id`。

## 开发工作集

- 它不占配额、不给使用者用，只给开发者和协作者用；在里面改数据或结构不影响使用者实例。
- `open` 给的写连接串 2 小时有效，只填进 `backend/.env`，不进工单、聊天、代码。过期用 `dataset_template_workspace(action="connect")` 重签；已知应用时传 `business_ui_id`，防止两个应用串库。
- 绑定到应用后，部署出的在线预览容器直连它（角色 `bui_w_<data_uid>`）。在线预览和带 `business_ui_data_space="workspace"` 的实际跑读写这一份；使用者运行和自动化读写各自的实例。
- **一直绑定在应用上**：制作、验收、上线之后都不解绑、不 `close`、不为它重新 deploy。`close` 会把 schema 和角色一起删掉，连着它的预览容器唤醒后健康检查一直 503、页面卡在 Waking up；还有部署跑在上面时平台会拒绝 `close`。
- 要看空库时页面怎么显示，在演示版上清空 Mock 数据看，不为此解绑或换绑。
- 有协作者时这个工作集由属主和全部协作者共用：编辑协作者改结构前先核对模板基线并和其他人协调，只读协作者只能用只读连接查询，见 `agenticapp-role-collab`。

## 改已上线的模板

上线的应用钉住的模板版本不可变：在**绑定的那个**工作集里幂等地改结构 → `extract` 新版本 → 应用出草稿改挂载 → 重新部署 → 上线。缺列就加列，不另建同义表；新增列、新增表优先；删列、改类型要带 `migration_script`；换模板家族等于换库，平台拒绝。做成：部署不报 `BUSINESS_UI_WORKSPACE_BEHIND_TEMPLATE`，上线不报 `BUSINESS_UI_TEMPLATE_*` / `BUSINESS_UI_UPGRADE_REHEARSAL_FAILED`。细则、默认值变更、基线和错误码见 [references/模板版本与迁移.md](references/模板版本与迁移.md)。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 列注释漏了 `[editable:…]` 前缀，路线写不进去 | 每列都带前缀 |
| 身份列设成 NOT NULL 又没人填，路线写不进，或 FA 自己编 INSERT | 身份列由建行的一方填，建行时不知道的不设必填 |
| `created_at`、`updated_at`、`row_version` 建成 NOT NULL 却没给 `default`，使用者第一次保存就失败，`gen:pages` 也拒绝 | 回工作集 `ALTER COLUMN … SET DEFAULT` 后重新 `extract` |
| 同一列使用者和路线都写，靠运行时仲裁 | 拆成两列 |
| 路线经平台数据集 FA（`GOALFYAI_FASTAGENT_Business_app_fastagent`）转一手读写应用库 | 新路线不用它；修订时遇到，改成脚本里的固定 SQL，要模型判断查什么的给业务 FA 挂工具（见 `agenticapp-tool-workflow`「读写应用库」） |
| 说好「脚本按唯一键写库」，实际只把结果返回让后端写；没有后端回流的路线永远进不了库 | 没有后端回流的路线由脚本自己写 |
| `close` 开发工作集、为它解绑或重新 deploy，或另开空工作集建新结构抽新版本、再想 `bind` 过来或让平台自动迁移：解绑后部署报 `PREVIEW_DATA_UNBOUND`；新工作集 `bind` 会被拒（已有绑定），旧工作集也不会被迁移，部署报 `BEHIND_TEMPLATE`（`close` 的后果见「开发工作集」） | 一直绑定；改结构回绑定的工作集用写连接补齐表列，再从它 `extract` |
| 为存使用者数据去挂目录里的「××档案场景包」 | 那是另一条产品线，数据进模板表 |
| 新 SDK 应用在 `setup` 里传 `scenario_pack_id` | 传 ① 建的 `business_ui_id` |
| `extract` / `close` 报 `TEMPLATE_*`，部署报 `BUSINESS_UI_WORKSPACE_BEHIND_TEMPLATE` / `PREVIEW_DATA_UNBOUND`，上线报 `BUSINESS_UI_TEMPLATE_*` / `BUSINESS_UI_UPGRADE_REHEARSAL_FAILED` | 见 [references/模板版本与迁移.md](references/模板版本与迁移.md)「错误码」 |
| 开发工作集连接串过期 | `connect` 重签 |
