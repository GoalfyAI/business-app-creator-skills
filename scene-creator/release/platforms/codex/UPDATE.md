# 更新与密钥轮换 — Codex

## 更新本地安装包

将新安装包解压到稳定目录，然后使用其中的插件市场根目录：

```bash
codex plugin remove scene-creator@scene-creator
codex plugin marketplace remove scene-creator
codex plugin marketplace add "$PACKAGE_ROOT"
codex plugin add scene-creator@scene-creator
```

彻底重启 Codex，并重新执行 `README.md` 中的五项验证。普通插件更新期间，不要删除
`~/.codex/.env`。

## 轮换个人 API 密钥

1. 用户在 GoalfyMax 中创建替换密钥，并把完整新密钥提供给 Agent。
2. Agent 只替换 `~/.codex/.env` 中的 `SCENE_CREATOR_API_KEY` 行，保留其他环境变量；不得要求
   用户自行编辑配置文件，也不得在命令回显、差异、日志或回复中展示密钥。
3. Agent 执行 `chmod 600 ~/.codex/.env`。
4. 新密钥保存成功后，撤销旧密钥。
5. 彻底重启 Codex，再次执行只读验证。

对比或排查密钥问题时，绝不能输出新旧密钥。
