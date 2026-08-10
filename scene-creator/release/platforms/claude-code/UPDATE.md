# 更新与密钥轮换 — Claude Code

## 更新本地安装包

将新安装包解压到稳定目录，然后使用其中的插件市场根目录：

```bash
claude plugin uninstall scene-creator@scene-creator
claude plugin marketplace remove scene-creator
claude plugin marketplace add "$PACKAGE_ROOT"
claude plugin install scene-creator@scene-creator
```

执行 `/reload-plugins` 或彻底重启 Claude Code，再重新执行 `README.md` 中的五项验证。普通插件
更新期间，不要删除密钥配置。

## 轮换个人 API 密钥

1. 在 GoalfyMax QA 中创建或获取替换密钥。
2. 只替换 `~/.claude/settings.json` 中的 `env.SCENE_CREATOR_API_KEY`，保留其他所有配置。
3. 新密钥保存成功后，撤销旧密钥。
4. 彻底重启 Claude Code，再次执行只读验证。

对比或排查密钥问题时，绝不能输出新旧密钥。
