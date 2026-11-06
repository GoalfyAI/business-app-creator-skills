---
name: agenticapp-tool-workspace
description: 开工、接续，或调用 business_ui_stage、workspace_push、download_template 前必须加载：应用工程、工作区文件、阶段记录、演示版验收、脚手架版本。
---
# 应用工程与工作区

这个 Skill 管应用工程本身：放在哪、工作区文件怎么改、阶段走到哪怎么记、页面在哪看、脚手架版本够不够。几个词：

- **应用根**：`apps/<应用目录名>/` 的实际绝对路径，所有工程命令都在这里执行。
- **三件套**：应用根下的 `app.json`、`WORKSPACE.md`、`workspace.json`，记应用身份和阶段。
- **阶段标记**写在工作区里（`workspace.json` 与阶段文档）；**阶段记录**用 `business_ui_stage` 写进平台给开发观测看，两者取值不同。
- **演示版**：`npm run dev:restart` 在工作区里起的应用版本，平台能力由 SDK 内置 Mock 提供；Studio 里开发者在「演示预览」看到的就是它。
- **脚手架版本**：应用根 `scaffold-release.json` 的 `version`，属于应用工程，和 Skill 版本、插件版本、应用业务版本分开记。

## 定位应用工程

- 工作台由 Goalfy App 安装和更新，你在它分配的工作目录下工作，每个应用一个目录 `apps/<应用目录名>/`。目录名用能区分业务的稳定英文名（如 `restaurant-koc`）；同名目录已存在时先读身份，同一应用就接续，另一个应用换名，不覆盖原目录。
- 桌面会话的 cwd 可能是外层工作目录：每条命令都在应用根执行，否则会改到别的应用或模板暂存目录。
- 没有开发者中心的命令行宿主（Codex、Claude Code 命令行）有几处不同，见 [references/命令行宿主.md](references/命令行宿主.md)。

## 核脚手架版本

建工单后、初始化或继续开发前做；部署前 `agenticapp-tool-deploy` 会再核一次。

1. 在已确认的应用根读 `scaffold-release.json` 的 `version`。没有文件就是未声明，传空；不从 `package.json`、压缩包名或日期猜。
2. `business_ui_bundle(action="download_template", task_id, current_scaffold_version=<本地版本>, workspace_id=<已有应用的真实标识>)`。新建还没有工作区时省略 `workspace_id`。
3. 返回的 `version`、`sha256`、`min_required_version`、`min_recommended_version`、`upgrade_required`、`upgrade_recommended` 要齐全。
   - `upgrade_required=true`：先做「脚手架升级」再继续。
   - `upgrade_recommended=true`：可以继续，开发记录写「建议升级脚手架版本」，下一次部署前升级。
   - 达到必须线就继续，不必每次升到最新。
4. 新建时校验下载包 `sha256`，用 `tar -xzf <包> -C <应用目录>` 解到本应用的独立目录，不加 `--strip-components`。做成：`scaffold-release.json` 等在应用目录第一层，它的 `version` 与返回的 `version` 相同。

每一步的细则（返回缺字段、解压后核对什么）和各类版本号的含义读 [references/脚手架版本与升级.md](references/脚手架版本与升级.md)。

## 初始化或接续工作区

**新建**：宿主给了初始化命令就原样执行。没有时：

1. `npm run scaffold:init -- --app-name "<应用名>"`，不传 `--environment`：宿主提供了环境，脚手架自己读。报「缺少环境」或要不带示例包时，读 [references/初始化与接续细则.md](references/初始化与接续细则.md)「新建」。
2. `npm run setup`、`npm run doctor`。做成：应用根有三件套和 `docs/stages/` 七份阶段文档，`doctor` 没有 `FAIL`。
3. 第一次实质答复结束前，把已知的业务目标、范围和待明确事项写进方案页的最小草案，未知的标「未知」。

**接续**：

1. 先读工作区：三件套（`current_stage`、`business_ui_id`、阶段标记）、`docs/stages/` 当前阶段的文档、方案页 `status`。走到哪以 `workspace.json` 为准，没有工作区的从 ① 开始。工作区里缺失或换了机器才从云端取，见 [references/云端保存与换机.md](references/云端保存与换机.md)。
2. 照上一节核脚手架版本；缺的工作区文件用 `npm run scaffold:repair -- --app-name "<应用名>"` 补，保留已有事实；再 `setup`、`doctor`。做成：`doctor` 没有 `FAIL`。
3. 协作者工作区里没有工程、已有应用（先看 `role`）、没有 PRD 的应用怎么接，读 [references/初始化与接续细则.md](references/初始化与接续细则.md)「接续」。

## 工作区文件

应用 ID 在 G1–G4 可以是 `null`；进 G5 前执行 `business_ui_manage(action="setup")` 返回的 `scaffold_bind_command`（即 `npm run scaffold:bind -- --business-ui-id <ID>`）回填，ID 原样用返回值。做成：`app.json` 的 `id` 与 `WORKSPACE.md` 的 `business_ui_id` 都是 `setup` 返回的那个 ID。

改三件套、方案页、阶段文档前读 [references/三件套与阶段标记.md](references/三件套与阶段标记.md)：这些文件只由脚手架生成、写入前重读（「每个文件的规矩」），进入一段、完成一项、退回时三处状态在同一个动作里改（「状态怎么改」），还有文件清单和五段与 G1–G7 的对应。

## 阶段记录

每段出口，对段内实际做过的每一项各调一次只写的 `business_ui_stage`；没通过、退回前面的段也写。哪一段写哪几项、写在什么之前，见各段 Skill 的「交棒」。③ 建好应用后带上 `business_ui_id`。参数怎么填、样例读 [references/阶段记录怎么写.md](references/阶段记录怎么写.md)。

- 一项调一次。写失败不挡交付：错误原文记进本段阶段文档，接着做，不重试。
- 只写不读：接续、修订照旧按工作区里的阶段文档和工单 checkpoint 定位。
- 工具列表里没有 `business_ui_stage`：把这三件事写进阶段文档和工单 checkpoint，交接消息说「这一步的完成记录没能存到平台，已经记在工作区里，不影响继续」，按入口「报错和平台问题」报一次，照常往下做。写失败和没有这个工具，交棒时这一条都算满足。

## 方案页

非 Studio 宿主才有。工作台里开发者在右栏「方案」看到 `docs/proposal/index.html`，改动后自动刷新，命令行宿主没有右栏；资源留在 `docs/proposal/` 内，样式只用脚手架的 `proposal.css`（缺了先 `scaffold:repair`），`doctor` 按固定版式校验。内容和版式怎么写见 `agenticapp-stage-1-requirements`「方案页」。每发一条交接消息时、改动要标出时、出新版时，读 [references/方案页怎么改.md](references/方案页怎么改.md)。

## 演示预览与在线预览

Studio 右栏有两个预览：「演示预览」是工作区里的当前工程，改了就能看，③ 页面做好时告诉开发者一句；「在线预览」是部署成功的草稿，走真实链路。两个都是开发者自己想看时看的，你不打开在线预览，他看过也不算验收。各自证明什么、打不开怎么办读 [references/演示预览与在线预览.md](references/演示预览与在线预览.md)。

## 演示版页面验收

④ 的页面条目由你在演示版上用 Playwright 无头 Chromium 逐条操作，只打开 `127.0.0.1` / `localhost`。访问被拒怎么办、操作顺序、完整做法和起不来怎么修读 [references/演示版页面验收.md](references/演示版页面验收.md)。做成：每条在 G6 都有操作步骤、截图路径（截图里应用内容已出现）和打开过的演示版路由。

## 脚手架升级

`download_template` 返回 `upgrade_required=true`，或部署报 `SCAFFOLD_UPGRADE_REQUIRED` 时做，做完才继续制作或部署。按 [references/脚手架版本与升级.md](references/脚手架版本与升级.md)「升级步骤」四步做：独立目录下载新模板并备份当前应用，三方差异迁移平台固定层、保留业务代码和数据，验证通过后用同一个 `workspace_id` 上报。做成：`task_manager(action="get")` 的 `scaffold_versions` 里，这个工作区的 `local_report` 是升级后的版本。

迁移边界、部署时的版本证据、`SCAFFOLD_*` 错误码也在这份 references。所有工程命令见 [references/脚手架命令与预置件.md](references/脚手架命令与预置件.md)。

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 在外层工作目录跑 `npm` 命令，改到别的应用或模板暂存目录 | 在应用根的绝对路径下跑 |
| `current_stage` 改成 G5 时 `business_ui_id` 仍是 `null`，被拒 | 先 `scaffold:bind` |
| `npm run doctor` / `verify` 失败 | 先修第一条 `FAIL`；`GIT_ROOT_MISMATCH` 见 [references/命令行宿主.md](references/命令行宿主.md) |

阶段改名、版本与升级、演示预览、演示版浏览器与 Mock、云端保存的其他常见错误，在上面各节指向的 references 的「常见错误」里。
