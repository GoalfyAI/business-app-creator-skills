# 参与贡献

欢迎提交问题反馈、改进建议和代码。

## 提交问题

发现 Skill 指引有误、工具契约对不上、或制作流程卡住时，请开 Issue 并附上：

- 你使用的客户端（Claude Code / Codex）与版本
- `SKILL.md` description 里的 `[skill-version:...]` 值
- 完整的复现步骤和 Agent 的实际行为
- 相关的工具返回（**移除密钥、Cookie、预签名 URL 等敏感内容**）

安全漏洞请勿公开提交，见 [SECURITY.md](SECURITY.md)。

## 目录职责

| 目录 | 说明 |
|---|---|
| `skill/` | Skill 内容唯一源：`SKILL.md`、`agents/openai.yaml`、`references/` |
| `scripts/` | 构建与发布工具 |
| `tests/` | 测试 |
| `claude-code/`、`codex/` | 平台安装文档手工维护；其中 `skills/` 由发布流程从 `skill/` 复制，**不要手工编辑** |
| `.claude-plugin/`、`.agents/` | 插件市场清单，版本号由发布流程更新 |

`skills/` 副本由发布流程重建，手工改动会被覆盖并导致校验失败。

## 提交代码

只修改 `skill/`、各平台目录下的安装文档、`scripts/`、`tests/`。

改完源文件后必须刷新发布清单，否则校验不通过：

```bash
uv run python scripts/build_platform_packages.py release \
  --version "<skill-release.json 中当前 package_version>" \
  --reason "<变更说明>"
```

版本号只能由发布流水线更新，日常提交不要改动它。

## 本地验证

```bash
uv sync --group dev
uv run ruff check scripts tests
uv run pytest -q
uv run python scripts/build_platform_packages.py check
```

四项都通过再提 PR。

## 修改 Skill 内容

`skill/SKILL.md` 是给 Agent 读的执行指引，不是给人读的说明书。写作时注意：

- 用**必须** / **禁止**这类明确的强调词，不要写模棱两可的建议
- 不要出现平台内部实现细节、代码或组件名
- 参考资料放 `skill/references/`，主文件只保留流程主干
- 对外文案（description、keywords）是唯一源，会被注入到各平台安装文件

## 环境约定

仓库里的安装物料**始终是生产配置**，`.mcp.json` 指向生产 MCP。发布流程不做环境渲染。

需要连测试环境时，改**本地已安装插件**的配置，不要动仓库源文件：

```
~/.claude/plugins/marketplaces/scene-creator/claude-code/.mcp.json
```

改仓库源文件会让 `check` 因校验和不匹配而失败，也有把测试地址发进正式包的风险。

## 版本机制

两个版本号各自独立，一次发布同时更新：

| | 用途 | 格式 |
|---|---|---|
| `version` | Skill 版本，服务端据此判断是否需要升级 | `vYYYYMMDD-<6 位小写 hex>` |
| `package_version` | 插件版本，插件管理器据此判断有无新版 | `MAJOR.MINOR.PATCH` |

Skill 版本必须不可预测，插件版本必须可比大小，两个要求冲突，所以分成两个号。

**版本号只能由发布流水线更新**，日常提交、本地验证都不得修改。原因是 `main` 本身就是插件
市场：版本号一进 `main` 就分发给所有用户，若服务端未登记该版本，用户会被判定过期且升级无解。
锁住之后，改版本号与登记必然成对发生。

## 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat(skill): 新增业务界面制作流程
fix(release): 修正平台模板校验和比对
docs: 补充 Codex 安装说明
```

## 行为准则

参与本项目即表示同意遵守 [行为准则](CODE_OF_CONDUCT.md)。

## 许可

提交的贡献将按 [Apache License 2.0](LICENSE) 授权。
