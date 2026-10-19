## 变更说明

## 变更类型

- [ ] 问题修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构
- [ ] 其他：

## 主要改动

-
-

## 验证

- [ ] `uv run ruff check scripts tests` 通过
- [ ] `uv run pytest -q` 通过
- [ ] `uv run python scripts/build_platform_packages.py check` 通过
- [ ] 仅文档变更，无需验证

## 检查项

- [ ] 只修改了 `skill/`、平台安装文档、`scripts/`、`tests/`（未手工改 `skills/` 副本）
- [ ] 改动源文件后已刷新发布清单（`release --version <当前 package_version>`）
- [ ] 未改动版本号（版本号只能由发布流水线更新）
- [ ] 提交内容中没有密钥、密码等敏感信息
