#!/usr/bin/env bash
# 本地发版：切一个新的 Skill 版本，提交并打 tag。
#
# 推送后由 GitHub Actions 接手：register-skill-release 校验产物并登记到各环境 Hub，
# publish-skill-release 从 tag 创建 GitHub Release。
#
# 用法：./scripts/release-skill.sh "变更说明"
set -euo pipefail

NOTES="${*:-}"
if [ -z "${NOTES}" ]; then
  echo "用法: $0 \"变更说明\"" >&2
  exit 2
fi
if [ "${#NOTES}" -gt 1024 ]; then
  echo "变更说明不能超过 1024 个字符" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

# 发版会改动大量生成文件，工作区必须干净，否则无法分辨哪些改动属于本次发布。
if [ -n "$(git status --porcelain)" ]; then
  echo "工作区有未提交的改动，请先提交或暂存后再发版：" >&2
  git status --short >&2
  exit 1
fi

if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
  echo "只能在 main 分支发版，当前分支：$(git rev-parse --abbrev-ref HEAD)" >&2
  exit 1
fi

# 切版本：生成随机 Skill 版本、提升所有插件 package version、
# 重建四个平台的 Skill 副本与压缩包、刷新发布清单。
VERSION="$(SCENE_SKILL_RELEASE_NOTES="${NOTES}" python3 - "${NOTES}" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from build_platform_packages import _skill_root, release_prod_source

print(release_prod_source(_skill_root(), sys.argv[1]))
PY
)"

python3 scripts/build_platform_packages.py check

git add -A
git commit -m "chore(skill): release ${VERSION}" -m "${NOTES}"
# 每个版本对应一次提交，GitHub Actions 据此发布 Release。
git tag -a "skill/${VERSION}" -m "${NOTES}"

echo
echo "已发布 ${VERSION}"
echo "推送两个远程："
echo "  git push --follow-tags origin main"
echo "  git push --follow-tags github main"
