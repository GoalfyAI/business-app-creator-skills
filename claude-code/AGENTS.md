# 场景包制作安装指南 — Claude Code（Agent 版）

本文供 Agent 直接执行，覆盖安装、更新与密钥轮换三种情况。
被版本闸门拒单时也可只看 [UPDATE.md](UPDATE.md)，那份是同一套更新流程的独立版本。

## 沙箱与权限处理

这段对话运行在 Claude Code 的沙箱和权限体系里，不是用户之后使用的终端。当前会话对需要
网络访问或工作区外写入的命令，有内置的权限申请通道。

1. 本文所有检查和命令**由你自己执行**。
2. 遇到网络被拦、或写入 `~/.claude/settings.json` 与插件目录被拒，**先按沙箱限制处理**，
   不要据此判断服务不可用、密钥无效或用户网络有问题。
3. 命令被沙箱拦住时，用 Bash 工具的 `dangerouslyDisableSandbox: true` 参数自己重试，
   走平台的正常权限流程。一次安装最多发起一次提权申请：申请够用的最小范围，
   然后复用它完成余下步骤。
4. 平台的授权弹窗是唯一可接受的提权交互。**禁止**把失败的命令贴进对话让用户自己跑。
5. 获批后重跑检查并自动继续。只有在平台禁用免沙箱命令、用户拒绝授权、或提权后重试仍失败时，
   才如实报告这个结果，**禁止**把命令转交给用户。

## 通用规则

1. 只运行本文列出的命令；只写入 `~/.claude/settings.json`（合并写入）和 Claude Code 插件目录。
2. 需要用户提供东西或采取行动时，**逐字输出**对应的「需要用户操作」模板：作为正文输出，
   **禁止**放进代码块或引用块，一级标题与加粗必须保留。用户不使用中文时翻译内容，
   保留结构与强调。
3. **禁止**回显密钥、在命令输出或 diff 中暴露密钥，也不得把密钥写入仓库、Skill、本文档、
   检查点或日志。
4. 每一步都以检查命令开始：已完成的跳过，任何一步重复执行都是安全的。
5. 在插件已启用、Claude Code 已重启、MCP 工具已加载、且一次只读请求成功之前，
   **禁止**宣告安装成功。

## 第 0 步：判断当前状态（安装还是升级）

以下都是检查命令，不需要用户参与。按结果分流：

```bash
claude plugin list | grep business-app-creator                      # 插件装了吗？
grep BUSINESS_APP_CREATOR_API_KEY "$HOME/.claude/settings.json"     # 密钥配了吗？
```

- 两项都通过 → 已是完整安装：直接跳到本文末尾的「更新」一节，不要问用户任何事
- 部分通过 → 只做未通过项对应的步骤
- 都没通过 → 从第 1 步开始完整安装

## 第 1 步：安装插件

检查：`claude plugin list | grep business-app-creator` —— 有输出就跳到第 2 步。

```bash
claude plugin marketplace add GoalfyAI/scene-creator-skills
claude plugin install business-app-creator@business-app-creator
```

失败处理：

- 提示市场已存在 → 不要重复添加，直接执行 install
- 提示市场不是 Git 市场，或装完后读不到 `[skill-version:...]` 标记 → 市场当初是从本地目录
  添加的，重新执行上面的 `marketplace add` 绑回公开仓库后再装

## 第 2 步：取得并配置 API 密钥

检查：`grep BUSINESS_APP_CREATOR_API_KEY "$HOME/.claude/settings.json"` —— 已存在则跳到第 3 步。

否则**逐字输出**下面的模板：

# 需要用户操作：提供 GoalfyMax 个人 API 密钥

**1. 打开 https://goalfymax.qa.goalfyai.cn/developer/api-keys ，点击「新建 API 密钥」并输入一个名称。**

**2. 完整密钥以 `sk_` 开头且只显示一次，创建后立即复制并粘贴到本对话中。**

**3. 我会替你写入本地配置，你不需要自己编辑任何文件。**

菜单里没有该入口，说明账号尚未获得开发者权限，请用户联系管理员开通——不要借用他人密钥。

拿到密钥后，把它**合并写入** `~/.claude/settings.json` 的 `env.BUSINESS_APP_CREATOR_API_KEY`：

```json
{
  "env": {
    "BUSINESS_APP_CREATOR_API_KEY": "<用户提供的密钥>"
  }
}
```

要求：

- 这个文件是用户 Claude Code 的全部配置，**必须合并写入**，保留其余所有内容，不得整体覆盖
- 文件不存在时创建所需结构
- 写入后重跑一次 grep 检查，确认找到 `BUSINESS_APP_CREATOR_API_KEY` 再继续
- 全程不回显密钥内容

## 第 3 步：重启并验证

MCP 连接只有重启后才生效，重启前无法验证。**逐字输出**下面的模板：

# 需要用户操作：重启 Claude Code

**1. 在会话中执行 `/reload-plugins`，或彻底退出 Claude Code 后重新打开。**

**2. 回到这个对话告诉我你已经重启（任意消息即可）——我会自己验证连接。**

用户确认重启后，**由你自己验证**，不要让用户去检查任何东西：

1. 确认 `business-app-creator` 插件与 Skill 已加载
2. 确认你的工具列表里有 `business-app-creator` 的 MCP 工具（如 `task_manager`、`list_assets`）
3. 用 `list_assets` 做一次只读请求作为自检——**禁止**为了测试连通性去创建、修改或删除任何资产

自检失败时按下表处理：

| 现象 | 处理 |
|---|---|
| `401 Unauthorized` | 确认 `~/.claude/settings.json` 里有 `BUSINESS_APP_CREATOR_API_KEY`，且该密钥在 GoalfyMax 未被撤销，然后请用户再彻底重启一次。只检查变量是否存在，不要输出其值 |
| `403 Forbidden` | 该账号没有目标场景包的访问权限，告知用户在 GoalfyMax 侧确认授权 |
| `503` | 依赖暂时不可用，等待恢复后重试，**不要**更换密钥 |
| 缺少 `task_manager` 等核心工具 | 部署未提供预期的外部契约。记录线上工具 Schema 并停止，**不要**用静态工具数量代替实时清单 |
| 插件已加载但 MCP 未连接 | 重新安装插件；只复制 Skill 目录不会安装 MCP 配置 |

## 完成报告

全部步骤结束后，按此模板报告：

```
场景包制作 Skill 安装结果：

[已完成]
- 插件 business-app-creator 已安装（版本 = plugin list 的实际输出）
- Skill 版本 = SKILL.md description 里 [skill-version:...] 的实际值
- API 密钥已写入 ~/.claude/settings.json
- business-app-creator MCP 工具已加载，只读请求成功

[需要你操作]
-（无 / 重启 Claude Code 后告诉我，我来验证连接）

[未完成]
-（无 / 列出原因）
```

**禁止**在报告中出现密钥内容或其片段。

---

## 更新

用户要求更新、或第 0 步判定为已安装时走这里。

### 第 1 步：升级插件

```bash
claude plugin update business-app-creator@business-app-creator
```

失败处理：提示市场不是 Git 市场，或升级后 `[skill-version:...]` 标记仍是旧值，说明市场
当初是从本地目录添加的、一直在复用陈旧缓存。重新绑定后再升级：

```bash
claude plugin marketplace add GoalfyAI/scene-creator-skills
```

### 第 2 步：确认新版本已生效

搜索已安装的 `skills/business-app-creator/SKILL.md`，从 description 读出 `[skill-version:...]`。
**不要凭记忆拼装安装路径**——路径里有连续同名层级和中间版本目录。命中多份时取版本目录
最高或最近修改的那份。

读不到该文件或没有版本标记，说明安装已损坏，回到第 1 步重装（先 `plugin uninstall`
再 `marketplace add` + `plugin install`）。

### 第 3 步：重启生效

**逐字输出**下面的模板：

# 需要用户操作：重启后生效

**在会话中执行 `/reload-plugins`，或彻底退出 Claude Code 后重新打开——更新后的 Skill
内容只有这样才会生效。**

> 若本次更新是因为创建工单被 `SCENE_SKILL_UPGRADE_REQUIRED` 拒绝：版本闸门只校验版本串，
> 所以读到新标记后**先在当前会话内用它重试**被拒的 `task_manager` create，重试成功再提示
> 用户重启。顺序反了会让用户白等一次重启。

---

## 轮换 API 密钥

用户要更换密钥、或旧密钥已被撤销时走这里。

1. 引导用户获取新密钥：执行上面「第 2 步：取得并配置 API 密钥」的模板
2. 把新密钥**合并写入** `~/.claude/settings.json` 的 `env.BUSINESS_APP_CREATOR_API_KEY`，
   覆盖旧值，保留其余全部配置
3. **逐字输出**重启模板——环境变量只在新会话生效，不重启的话 MCP 仍用旧密钥
4. 重启后由你自己跑一次 `list_assets` 只读自检，确认新密钥可用
5. 确认可用后，提示用户去 GoalfyMax 撤销旧密钥

对比或排查密钥问题时，**禁止**输出新旧密钥的任何片段。

---

## 装好之后

告诉用户可以直接用自然语言描述业务目标，例如：

- 「我们每周要给 20 家门店做朋友圈广告投放复盘，把这个流程做成场景包」
- 「这个场景包执行时总绕弯，你看下哪里配置有问题」

Skill 会先带着做业务访谈、给出方案，用户确认后才动手制作。
