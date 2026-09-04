#!/bin/zsh
# GitHub / codeup 仓库改名为 business-app-creator-skills 之后跑一次：换安装链接、pyproject 名、构建校验里的仓名，
# 然后照常 release 一版。改名前不要跑——链接会先于重定向失效。
set -e
cd "$(dirname "$0")/.."
OLD="scene-creator-skills"; NEW="business-app-creator-skills"
git ls-files | grep -E '\.(md|py|json|yaml|yml|toml)$' | grep -v '^dist/' | while read -r f; do
  if grep -q "$OLD" "$f"; then sed -i '' "s/$OLD/$NEW/g" "$f"; echo "renamed in $f"; fi
done
# 远端也换（GitHub 改名后旧地址仍可推，但显式换掉更稳）
git remote set-url github "git@github.com:GoalfyAI/$NEW.git" 2>/dev/null || true
echo "done. 接着：uv run python scripts/build_platform_packages.py check && 按常规发一版（patch）"
