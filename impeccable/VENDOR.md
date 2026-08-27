# Vendored: impeccable（插件形态）

- 上游：https://github.com/pbakaus/impeccable （Apache-2.0，LICENSE 已随包保留）
- 本副本取自上游 commit `63b04e2530f5c7b41ea83c133daab24f34912456`（v4.1.2），内容为上游 `plugin/` 目录原样拷贝，未修改功能代码。
- 升级方式：同步上游 → diff review → 更新本目录与本文件的 commit 记录 → 随 scene-creator-skills 发版分发。
- 使用边界：在 GoalfyMax 脚手架项目内使用时，服从该仓库 AGENTS.md 的「设计与优化边界」；其修改完成后必须重跑 `npm run check` 与穷尽交互自查（见 scene-creator Skill S3）。
- 注意：59 条确定性检测的 CLI（`npx impeccable`）不随本插件分发，需要时另行安装。
