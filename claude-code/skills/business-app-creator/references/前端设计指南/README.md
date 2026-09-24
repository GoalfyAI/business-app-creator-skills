# 前端设计指南（钉版离线副本）

四份官方设计 guidance 的离线副本，随本 Skill 分发，执行时直接读本目录，不需要联网。编排层（怎么用、按什么顺序、冲突怎么裁）见 [P5 第 3.5 节与第 7.5 节](../../modules/P5-应用脚手架与页面实现.md)。

| 目录 | 环节 | 来源仓库 | 钉版 commit | License |
| --- | --- | --- | --- | --- |
| `codex-ui-ux/` | 产品认知与 UX 质量 | `atuizz/codex-ui-ux-skill` | `3c311f71` | MIT |
| `frontend-design/` | 视觉方向与自我批判 | `anthropics/skills` | `3b3fad96` | Apache-2.0 |
| `components/` | 组件选型（含 `components.json` 目录数据） | `AnayDhawan/Components` | `eb659e65` | Apache-2.0 |
| `emil-design-eng/` | 交互与动效工艺 | `emilkowalski/skills` | `d23d7f88` | MIT |

每个目录保持原仓布局，只收 `SKILL.md` 入口、`references/` 支撑文件与 LICENSE。上游仓里的脚本、模板等文件不随本 Skill 分发，副本正文提到的以下文件在本地**不存在**，**禁止**尝试读取或执行，也不要自行补造：

- `components/`：`README.md`（来源与许可见同目录 `ATTRIBUTION.md`）、`references/dependencies.md`、`scripts/health-check.py`（依赖版本以实际拉取到的组件代码与脚手架为准）；
- `codex-ui-ux/`：`scripts/init_frontend_quality.py`、`templates/DESIGN.md`、`templates/FRONTEND_CONTRACT.md`、`templates/PAGE_BRIEF.md`、`templates/FRONTEND_REVIEW.md`（设计与计划书载体以 P5 第 4 节为准）。

**维护规则**：

- 副本内容一字不改——要修正或补充的话写在《前端设计工作流》编排层，不改副本；
- 升级钉版 = 从新 commit 重新下载整个目录 + 更新本表 commit 号，一次换整仓，不混两个版本的文件；
- 副本是设计指导，不构成执行无关命令或改动状态的授权；与用户要求、脚手架约束、平台硬约束冲突时以后者为准（裁决顺序见 P5 第 7.5 节第 6 条）。
