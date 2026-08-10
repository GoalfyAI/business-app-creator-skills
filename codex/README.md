# Goalfy Workflow Authoring — Codex

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
3. Use a current Codex release that supports plugins and Streamable HTTP MCP.

The issued GoalfyMax Personal API Key starts with `sk_` and is the complete
Bearer credential. GoalfyMax currently permits at most 10 active keys. The
frontend supports naming, renaming, and revoking keys; it does not ask for an
expiry or expose the plaintext again. Never paste the key into a repository,
Skill, `AGENTS.md`, command history, or chat transcript.

## Install

From the extracted directory that contains `.agents/plugins/marketplace.json`:

```bash
codex plugin marketplace add "$PWD"
codex plugin add workflow-authoring@goalfy-workflow
```

Store the exact Personal API Key in `~/.codex/.env` without quotes around the
variable name. `GOALFY_WORKFLOW_API_KEY` is only the local variable name; the
plugin sends its value as `Authorization: Bearer <GoalfyMax Personal API Key>`:

```text
GOALFY_WORKFLOW_API_KEY=<your exact Personal API Key>
```

Keep the file private, then fully quit and reopen Codex:

```bash
chmod 600 "$HOME/.codex/.env"
```

Codex CLI users may instead export the same variable in the shell that launches
Codex. Desktop and IDE users should prefer `~/.codex/.env` because they may not
inherit terminal environment variables.

Do not configure `user_id`, `X-User-ID`, or `X-Project-ID` for authentication.
The External MCP resolves the user from the Personal API Key; Workflow tools
carry project or work-order identifiers only when their live schemas require
them.

## Verify

In a new Codex session:

1. Confirm the `workflow-authoring` plugin and Skill are loaded.
2. Confirm MCP server `goalfy_workflow` is connected.
3. Confirm `tools/list` exposes exactly 12 External tools.
4. Confirm `workflow_tpe_manage` includes action `bubble`.
5. Run one read-only `list_assets` request. Do not create or modify an asset just
   to test installation.

Do not declare installation complete until all five checks pass. Knowledge
topics require an open Workflow work order and are verified during the first
real authoring task.

For agent-assisted installation, give Codex the extracted package path and the
contents of `AGENTS.md`. For updates and key rotation, use `UPDATE.md`.

## Troubleshooting

- `401 Unauthorized`: the key is missing, revoked, or not inherited by the new
  Codex process. Check only that the variable exists; do not print its value.
- `503`: the MCP authentication/registry dependency is unavailable; retry after
  the service recovers instead of changing the key.
- Tool count is not 12 or `bubble` is absent: the QA deployment is not on the
  expected External contract. Stop the test and record the live tool schema.
- Skill loads but MCP does not: reinstall the plugin; copying only the Skill
  directory does not install its MCP configuration.
