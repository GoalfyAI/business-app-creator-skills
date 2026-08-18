# 参与贡献

欢迎提交问题反馈、改进建议和代码。

## 提交问题

发现 Skill 指引有误、工具契约对不上、或制作流程卡住时，请开 Issue 并附上：

- 你使用的客户端（Claude Code / Codex）与版本
- `SKILL.md` description 里的 `[skill-version:...]` 值
- 完整的复现步骤和 Agent 的实际行为
- 相关的工具返回（**移除密钥、Cookie、预签名 URL 等敏感内容**）

安全漏洞请勿公开提交，见 [SECURITY.md](SECURITY.md)。

## 提交代码

只修改手工维护的源文件：

```
skill/          Skill 内容
platforms/      各平台安装文件模板
scripts/        构建与发布工具
tests/          测试
```

`claude-code/`、`codex/`、`.claude-plugin/`、`.agents/` 是发布流程生成的，**不要手工编辑**——
改了会被下次发布覆盖，而且校验和会对不上。

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
