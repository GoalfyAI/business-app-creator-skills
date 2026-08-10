# Goalfy Workflow Authoring — Claude Code

This package installs the audited Goalfy Workflow External MCP and the
`workflow-authoring` Skill together. It targets US QA:

`https://workflow-mcp.qa.goalfyai.com/mcp`

## Prerequisites

1. Sign in to GoalfyMax QA, then open the account menu → **Developer Tools** →
   **API Key** (`/developer/api-keys`). Select **New API Key** and enter a name
   containing 1–100 characters. The full key is shown and automatically copied
   only once. Save it before closing the dialog. If this menu is absent, the
   account does not have the currently gated developer entry; ask an
   administrator for access instead of using another person's key.
2. Extract this ZIP to a stable local directory.
3. Use a current Claude Code release with plugin and HTTP MCP support.

The issued GoalfyMax Personal API Key starts with `sk_` and is the complete
Bearer credential. GoalfyMax currently permits at most 10 active keys. The
frontend supports naming, renaming, and revoking keys; it does not ask for an
expiry or expose the plaintext again. Never paste the key into a repository,
Skill, `AGENTS.md`, command history, or chat transcript.

## Install

From the extracted directory that contains `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add "$PWD"
claude plugin install workflow-authoring@goalfy-workflow
```

Add the exact Personal API Key to the `env` object in
`~/.claude/settings.json`, preserving every other setting.
`GOALFY_WORKFLOW_API_KEY` is only the local variable name; the plugin sends its
value as `Authorization: Bearer <GoalfyMax Personal API Key>`:

```json
{
  "env": {
    "GOALFY_WORKFLOW_API_KEY": "<your exact Personal API Key>"
  }
}
```

Do not replace the whole settings file when it already exists. Fully quit and
reopen Claude Code after updating it.

Do not configure `user_id`, `X-User-ID`, or `X-Project-ID` for authentication.
The External MCP resolves the user from the Personal API Key; Workflow tools
carry project or work-order identifiers only when their live schemas require
them.

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
