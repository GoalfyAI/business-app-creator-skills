# 安装 QA 版业务应用助手

QA 版装在 GitHub 的 `business-qa` 分支，连接 QA 环境的 MCP。它由 Codeup `qa/main` 自动生成：`qa/main` 有推送，
几分钟后 `business-qa` 分支就是最新的 QA 候选版，并已登记到 QA 环境，不需要手工改任何文件。

QA 版与正式版的插件同名，一台机器同一时间只能装一个。

## 1. 准备 QA 密钥

在 QA 的「API 密钥」页面生成密钥：https://goalfymax.qa.goalfyai.cn/developer/api-keys

QA 版读取的环境变量是 `BUSINESS_APP_CREATOR_QA_API_KEY`，和正式版的 `BUSINESS_APP_CREATOR_API_KEY`
分开，两个密钥可以同时保留在本机。

- Claude Code：在启动 Claude Code 的环境里 `export BUSINESS_APP_CREATOR_QA_API_KEY=<QA 密钥>`（写进 shell 配置文件）。
- Codex：在 `~/.codex/.env` 里加一行 `BUSINESS_APP_CREATOR_QA_API_KEY=<QA 密钥>`。

## 2. 安装

Claude Code（已装正式版的先卸载：`claude plugin uninstall business-app-creator@business-app-creator`，
再 `claude plugin marketplace remove business-app-creator`）：

```bash
claude plugin marketplace add "https://github.com/GoalfyAI/business-app-creator-skills.git#business-qa"
claude plugin install business-app-creator@business-app-creator
```

Codex：

```bash
codex plugin marketplace add GoalfyAI/business-app-creator-skills --ref business-qa
codex plugin add business-app-creator@business-app-creator
```

装完彻底重启客户端。

## 3. 核对版本

```bash
grep -rho '\[skill-version:[^]]*\]' ~/.claude/plugins | sort -u      # Codex 换成 ~/.codex
```

QA 版的插件版本形如 `2.0.12-qa.<构建号>`；`[skill-version:...]` 应与 QA 环境最新登记的版本一致。

## 4. 升级

```bash
claude plugin marketplace update business-app-creator && claude plugin update business-app-creator@business-app-creator
```

然后重启。Codex 用 `codex plugin marketplace upgrade business-app-creator`。

## 5. 切回正式版

卸载插件并移除市场后，按仓库根目录 README 重新安装正式版（不带 `#business-qa`），环境变量用 `BUSINESS_APP_CREATOR_API_KEY`。
