# Goalfy Workflow Authoring — Claude Code

This package installs the audited Goalfy Workflow External MCP and the
`workflow-authoring` Skill together. It targets US QA:

`https://workflow-mcp.qa.goalfyai.com/mcp`

## Prerequisites

1. Obtain a GoalfyMax Personal API Key for QA. Never paste it into a repository,
   Skill, `AGENTS.md`, command history, or chat transcript.
2. Extract this ZIP to a stable local directory.
3. Use a current Claude Code release with plugin and HTTP MCP support.

## Install

From the extracted directory that contains `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add "$PWD"
claude plugin install workflow-authoring@goalfy-workflow
```

Add the exact Personal API Key to the `env` object in
`~/.claude/settings.json`, preserving every other setting:

```json
{
  "env": {
    "GOALFY_WORKFLOW_API_KEY": "<your exact Personal API Key>"
  }
}
```

Do not replace the whole settings file when it already exists. Fully quit and
reopen Claude Code after updating it.

## Verify

In a new Claude Code session:

1. Confirm the `workflow-authoring` plugin and Skill are loaded.
2. Run `/mcp` and confirm `goalfy_workflow` is connected.
3. Confirm `tools/list` exposes exactly 12 External tools.
4. Confirm `workflow_tpe_manage` includes action `bubble`.
5. Run one read-only `list_assets` request. Do not create or modify an asset just
   to test installation.

Do not declare installation complete until all five checks pass. Knowledge
topics require an open Workflow work order and are verified during the first
real authoring task.

Do not copy only the Skill into `~/.claude/skills`: Claude Code will not load an
MCP configuration placed inside a standalone Skill directory. Install the
plugin so Skill and MCP are activated together.

For agent-assisted installation, give Claude Code the extracted package path
and the contents of `AGENTS.md`. For updates and key rotation, use `UPDATE.md`.

## Troubleshooting

- `401 Unauthorized`: the key is missing, revoked, or not inherited by the new
  Claude Code process. Check only that the setting exists; do not print it.
- `503`: the MCP authentication/registry dependency is unavailable; retry after
  the service recovers instead of changing the key.
- Tool count is not 12 or `bubble` is absent: the QA deployment is not on the
  expected External contract. Stop the test and record the live tool schema.
- Skill loads but MCP does not: reinstall the plugin and run `/reload-plugins`;
  copying only the Skill directory does not install its MCP configuration.
