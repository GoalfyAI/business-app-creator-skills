# 更新与密钥轮换 — Claude Code

## 从受控 Codeup Tag 更新

版本门禁返回的 `upgrade_source` 是唯一批准来源。取其 `latest_version`/`ref`，从内部 Codeup
克隆精确 tag；本流程直接使用仓库中的 `claude-code/`，不下载或生成 ZIP：

```bash
export SCENE_CREATOR_VERSION="<请替换为返回的 latest_version>"
git clone --depth 1 --branch "skill/${SCENE_CREATOR_VERSION}" \
  git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git \
  scene-creator-skills-${SCENE_CREATOR_VERSION}
export PACKAGE_ROOT="$PWD/scene-creator-skills-${SCENE_CREATOR_VERSION}/claude-code"
```

只有 `upgrade_source.git_url`、`upgrade_source.ref` 与上面一致时才继续。Tag 不存在或当前账号没有
Codeup 权限时停止更新并联系内部运维，不猜测镜像、压缩包或其他下载地址。

然后使用该仓库目录中的插件市场根目录：

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
