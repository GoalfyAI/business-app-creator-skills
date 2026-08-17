# 更新与密钥轮换 — Claude Code

## 升级 Skill

被 `SCENE_SKILL_UPGRADE_REQUIRED` 拒单，或需要把 Skill 升到最新版时按本文执行。每一步都可重复执行。

### 第 1 步：升级插件

```bash
claude plugin update scene-creator@scene-creator
```

插件市场会拉取内网仓库、比较 `plugin.json` 版本并完成更新。

**兜底**：如果提示插件市场不是 Git 市场，或升级后 `[skill-version:...]` 标记仍是旧值，说明市场
当初是从本地目录添加的，一直在复用陈旧缓存。重新绑回内网仓库后再执行上面的升级：

```bash
claude plugin marketplace add git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git
```

### 第 2 步：读取新版本标记并重试（在本次会话内完成，先不要让用户重启）

版本闸门只校验版本串，所以本次会话内即可解除阻塞。搜索已安装的 `skills/scene-creator/SKILL.md`，
不要凭记忆拼装安装路径——路径里有连续同名层级和中间版本目录。搜索命中多份时（旧版本目录、
市场副本），取版本目录最高或最近修改的那份。从它的 description 读出 `[skill-version:...]`，
原样填入 `skill_version` 重试刚才失败的 `task_manager` create。

拒单响应和 changelog 里都不含可用于重试的版本串，唯一合法来源是上面读到的已安装 SKILL.md 标记。

### 第 3 步：让新 Skill 完整加载

仅在第 2 步重试成功之后执行。重试只解除了闸门，你上下文里加载的 Skill 内容仍然是旧版本。
用用户当前对话使用的语言输出下面的模板（用户不使用中文时翻译它，保留 H1 标题和加粗，
不要放进代码块或引用块）：

# 需要操作：重启后生效

**在会话中执行 `/reload-plugins`，或彻底退出 Claude Code 后重新打开——更新后的 Skill 内容
只有这样才会生效。**

升级期间不要删除密钥配置。

## 轮换个人 API 密钥

1. 用户在 GoalfyMax 中创建替换密钥，并把完整新密钥提供给 Agent。
2. Agent 只替换 `~/.claude/settings.json` 中的 `env.SCENE_CREATOR_API_KEY`，保留其他所有配置；
   不得要求用户自行编辑配置文件，也不得在命令回显、差异、日志或回复中展示密钥。
3. 新密钥保存成功后，撤销旧密钥。
4. 彻底重启 Claude Code，再次执行只读验证。

对比或排查密钥问题时，绝不能输出新旧密钥。
