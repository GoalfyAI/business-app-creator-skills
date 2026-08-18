# 场景包制作 Skill 更新指南 — Manus（Agent 版）

被 `SCENE_SKILL_UPGRADE_REQUIRED` 拒单，或需要把 Skill 升到最新版时按本文执行。

MCP 连接器指向远端服务，不需要更新——只有 Skill 文件需要替换。Skill 由用户在
Skills 管理页维护，**Manus 上没有任何在当前对话内解除阻塞的办法**（更新后的
Skill 文件在这里读不到），唯一路径是带着新 Skill 开一个新对话。所以引导用户完成替换：

## 第 1 步：替换 Skill

用用户当前对话使用的语言输出下面的模板（用户不使用中文时翻译它，保留 H1 标题和加粗，
不要放进代码块或引用块）：

# 需要操作：更新场景包制作 Skill

**1. 下载最新的 Skill 包：https://github.com/GoalfyAI/scene-creator-skills/raw/main/manus/scene-creator-skill.zip**

**2. 在 Manus 的 Skills 管理页删除旧的 `scene-creator` Skill，然后上传新的 zip。**

**3. 关闭当前对话并开一个新对话——Skill 只在会话开始时加载。**

## 第 2 步：在新对话中继续

新对话里，更新后的 Skill 的 description 会带上新的 `[skill-version:...]`，按 Skill 的
指引创建工单即可自动通过版本闸门——请用户在那边重述原本的需求即可。

**禁止**在当前对话里编造版本串。Manus 上唯一有效的来源是新装的 Skill，而它只有在开新
对话后才能读到。

## 轮换个人 API 密钥

1. 在 GoalfyMax 线上环境创建替换密钥。
2. 在 Manus 的 Plugins 页编辑 `scene-creator` 连接器，把 `Authorization` 头改成
   `Bearer sk_新密钥`。
3. 保存并确认新密钥可用后，在 GoalfyMax 撤销旧密钥。
4. 开新对话，再次执行只读验证。

对比或排查密钥问题时，绝不能输出新旧密钥。
