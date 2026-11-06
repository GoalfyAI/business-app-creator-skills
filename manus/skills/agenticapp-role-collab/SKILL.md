---
name: agenticapp-role-collab
description: 多人协作做应用。应用返回的角色是编辑或只读协作者，或属主说「把他拉进来」「改成只读」「移掉他」「他提了上线」时加载。属主一个人做时不用。
---
# 多人协作

一个智能应用有一位属主（创建人），可以有只读协作者和编辑协作者。属主能做全部操作；协作者能做的事更少，而且有几步做法和属主不同：只在自己的草稿上改、新建资产要落在属主名下、⑤ 改成提请属主上线。各角色在五段里的其余做法和属主相同。

最常见的错是**按属主的做法去做协作者的事**：编辑协作者调 `finalize`，或提请后对开发者说「已上线」；在别人创建的草稿上改；只读协作者为了修问题去派生草稿、申请写连接。

## 先认角色

`business_ui_manage(action="list")` 和 `business_ui_manage(action="get")` 返回的 `role` 决定能做什么：

| `role` | 是谁 | 能做 | 不能做 | 按什么做 |
|---|---|---|---|---|
| `owner` | 属主，应用的创建人 | 全部操作，包括上线、发布、下线、删除、加人改档移人 | — | 入口的任务路由；有待上线的提请先按下面「属主处理提请」 |
| `editor` | 编辑协作者 | 派生自己的草稿、改各层资产和开发库结构、部署自己的草稿、预览、提请属主上线 | 上线应用、发布、下线、删除、再分享应用；改表间关系与治理规则、绑定或关闭工作集 | 下面「编辑协作者改应用」 |
| `viewer` | 只读协作者 | [references/只读协作者能读什么.md](references/只读协作者能读什么.md) 列的读取 | 任何写入 | `agenticapp-task-diagnose` |
| `none` | 没有权限 | — | — | 告诉开发者他没有这个应用的权限，请属主把他加为协作者 |

- 角色只认平台返回，不按应用名、聊天里的说法或资产的 owner 字段推断。每次开工和接续都重新读一次：属主可能已经改档或移除了他。
- `get` 的角色在 `data.collaboration.role`；`get` 还返回全部草稿（创建人、变更说明 `change_note`、基线是否过期 `baseline_stale`）、待上线的提请和共享工作集。`list` 返回三组：我的应用（`data.items`）、协作中的应用（`data.collaborations`）、待接受的协作邀请（`data.pending_invitations`）。
- 有待接受的邀请时告诉开发者：到 GoalfyMax 的分享兑换入口输入站内信里的分享码接受邀请，接受后才能看到和操作这个应用。不替开发者兑换分享码。
- 协作者被移除或降级后立即生效：新请求按新角色判定，已签发的开发库连接最长约 10 秒后被拒并断开。原来能做的事突然被拒，先重读 `role` 再判断。
- 协作者工作区里没有应用工程：先下载源码包建工程，按 `agenticapp-tool-workspace` 的「初始化与接续细则」「接续」第 1 步。

## 编辑协作者改应用

起点仍按 `agenticapp-task-revise` 的起点表，按这个顺序做：

1. **看版本**：应用的版本和草稿看 `business_ui_manage(action="get")` 的返回；场景包、工具集、FA 等属主名下资产看 `get_asset` 和 `ensure_editable_asset_draft` 的返回，不调 `list_asset_versions`（它对智能应用以外的资产只给属主）。
2. **只改自己的草稿，各层资产自下而上**：做法见 [references/编辑协作者的草稿与资产.md](references/编辑协作者的草稿与资产.md)。
3. **新建或克隆资产**时带 `collaboration_business_ui_id=<应用家族 ID>`，新建前告诉开发者资产会落在属主名下。
4. **改开发库结构**：先告诉开发者要加改哪些表和列，请他先和属主及其他编辑协作者说一声，避免两人同时改；再按 [references/编辑协作者的草稿与资产.md](references/编辑协作者的草稿与资产.md)「共享开发工作集」带基线改结构、抽新版本，然后在自己的应用草稿上 `update` 挂新模板版本、重新部署。
5. **④ 和属主一样由你逐条测**（`agenticapp-stage-4-acceptance`）：部署按入口「红线」；`workspace` 真跑前先把自己的草稿 `ship` 到 `success`；只有协作者身份才看得到的表现、充值相关的页面条目记「未测」（平台登录身份）。
6. **⑤ 不上线应用**，改为下面的「提请属主上线」。

## 提请属主上线

编辑协作者不 `finalize` 应用。前提：草稿部署成功；④ 的验收报告已交，开发者说了「可以上线」；基线没有过期。

1. 调 `business_ui_manage(action="request_finalize", task_id, business_ui_id)`。`draft_asset_id` 可以省略，省略时取你本人在该应用的草稿；`note` 是给属主的补充说明，可选；草稿的 `change_note` 会一并带给属主。
2. 成功后对开发者说：「已提请，等属主上线。属主上线后这一版成为属主的正式版，发不发布由属主决定；如果属主先上线了别人改的版本，你会收到通知，我会先把那次的改动并进你这一版，再重新提请。」附草稿版本和变更说明；属主会收到站内信。只说已提请，不说已上线，也不为此去 `finalize`、`resolve` 或请属主以外的人上线。
3. 提请被拒（如 `BUSINESS_UI_FINALIZE_REQUEST_NOT_READY`、`PERSONAL_VERSION_STALE_SOURCE`）：按 [references/协作报错.md](references/协作报错.md) 处理后再提请。
4. 之后 ⑤ 的结单门、花费、阶段记录、结单照 `agenticapp-stage-5-launch` 做；上线结果的「上线的版本」写「已提请，等属主上线」和草稿版本、变更说明。

### 属主处理提请

1. 告诉开发者谁提请了哪份草稿、改了什么：用 `compare_asset_versions` 对比当前上线版，连同提请说明一起说。
2. 依据是协作者为这份草稿做的 ④ 验收报告（提请说明里附）；没有就请提请人先补 ④。
3. 问开发者要不要上线。他看过报告、明确说「可以上线」后，按 `agenticapp-stage-5-launch` 上线，`finalize` 的 `draft_asset_id` 用那份协作者草稿。这一版成为属主自己的正式版，发不发布由属主决定。
4. 提请的草稿基线已过期，上线会返回 `PERSONAL_VERSION_STALE_SOURCE`：告诉开发者要提请人先合并新版本。

## 基线过期的合并

协作者的草稿基线过期（`baseline_stale=true`、提请或上线返回 `PERSONAL_VERSION_STALE_SOURCE`、站内信通知基线过期），说明属主已经上线了更新的版本，而这份草稿是从旧版派生的。按顺序做：

1. 用业务话告诉开发者原因和下面要做的事，他确认后开始。
2. 先把工作区里当前的改动提交到 git；应用目录还没有 git 仓库就先初始化再提交。
3. `business_ui_bundle(action="download")` 下载最新上线版的源码包，放到另一个分支，用 git 合并到自己的改动上。不直接用新版覆盖工作区里的工程，也不用工作区里的工程覆盖新版。冲突在技术上怎么合由你定；合并结果会影响使用者已有数据或页面行为的，用业务话出选择题给开发者。
4. 从最新上线版重新派生自己的应用草稿（`ensure_draft` 带 `change_note`）。返回的仍是那份过期草稿时，告诉开发者后先用 `abandon_asset_version_draft` 作废它，再重新派生。
5. 合并后的代码跑 `npm run verify:release`，`ship` 到新草稿，按 `agenticapp-stage-4-acceptance` 重新验收受影响的条目。
6. 再次提请属主上线。

场景包、工具集等资产层的草稿过期时同理：从新上线版重新派生，把改动重做到新草稿上。

## 属主：加人、改档、移除

用 `business_ui_manage(action="collaborators", collaborator_action=list / add / update / remove)`。add、update、remove 执行前先向开发者复述对象账号、档位和影响，他明确同意后才带 `confirm_collaborator_change=true` 执行。参数、影响怎么讲、邀请和分享码的限制见 [references/加人改档移人.md](references/加人改档移人.md)。

## 预期限制，不是故障

协作者预览提示要用新版脚手架重建、充值被拒、只读写入被拒、外部登录回调对不上，都是预期结果，不提 `submit_dev_feedback`。原因、怎么处理、费用怎么说见 [references/预览费用与限制.md](references/预览费用与限制.md)。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 编辑协作者调 `finalize`，或提请后说「已上线」 | 用 `request_finalize`，只说已提请 |
| 在别人创建的草稿上改，或复用别人的草稿部署 | 只用自己的草稿 |
| 改共享工作集结构前不打招呼；抽模板被拒后按旧基线硬抽，或删掉别人加的表列 | 先打招呼；按 [references/编辑协作者的草稿与资产.md](references/编辑协作者的草稿与资产.md) 重读基线，保留别人的结构 |
| 用 `dataset_read` 查应用开发库 | 只读查询用 `dataset_template_workspace(action="connect", mode="reader")` |
| 替开发者兑换分享码，或没经他确认就 add、update、remove | 告诉他去哪兑换；改动前复述并等他同意 |
| `change_note` 填「更新」这类空话 | 写清这次改了什么 |
| 把费用写成「协作者自付」之类的承诺 | 只说按平台当前规则从发起运行的账号扣 |

各错误码的含义和处置见 [references/协作报错.md](references/协作报错.md)。
