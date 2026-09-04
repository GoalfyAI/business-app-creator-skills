# 场景包制作 Skill 更新指南 — 通用集成（Agent 版）

被 `SCENE_SKILL_UPGRADE_REQUIRED` 拒单，或需要把 Skill 升到最新版时按本文执行。
每一步都可重复执行。

MCP 连接指向远端服务，不需要更新配置——只有 Skill 文件需要替换。更新过程**不需要**
API 密钥，不要向用户索取。


> **1.21.3 起密钥变量改名**：`SCENE_CREATOR_API_KEY` → `BUSINESS_APP_CREATOR_API_KEY`，客户端配置里的占位符与环境变量同步改名（值不变）。

## 第 1 步：重新获取 Skill 文件

按当初的获取方式重新拉一份：

- **下载的 zip**：重新下载 `business-app-creator-generic.zip` 并解压
- **克隆的仓库**：`cd business-app-creator-skills && git pull`

## 第 2 步：读取新版本标记并重试（在本次会话内完成，先不要让用户重启）

版本闸门只校验版本串，所以本次会话内即可解除阻塞。从第 1 步刚获取的 `SKILL.md` 的
description 里读出 `[skill-version:...]`（你知道它落在哪，不需要全盘搜索），原样填入
`skill_version` 重试刚才失败的 `task_manager` create。

拒单响应和 changelog 里都不含可用于重试的版本串，唯一合法来源是上面读到的 `SKILL.md` 标记。
读不到标记说明文件没取全，重做第 1 步，**不要**编造一个版本串。

## 第 3 步：重新载入并开新会话

仅在第 2 步重试成功之后执行。重试只解除了闸门，你上下文里加载的 Skill 内容仍然是旧版本。
用用户当前对话使用的语言输出下面的模板（用户不使用中文时翻译它，保留 H1 标题和加粗，
不要放进代码块或引用块）：

# 需要操作：重新载入 Skill 并开新会话

**1. 按初次配置的方式，把更新后的 `SKILL.md` 和 `references/` 重新载入你的工具。**

**2. 开一个新会话——Skill 只在会话开始时加载，不开新会话更新内容不会生效。**

## 轮换个人 API 密钥

1. 在 GoalfyMax QA 环境创建替换密钥。
2. 更新环境变量 `BUSINESS_APP_CREATOR_API_KEY`，保留其他配置。
3. 新密钥生效后，撤销旧密钥。
4. 重启客户端，再次执行只读验证。

对比或排查密钥问题时，绝不能输出新旧密钥。
