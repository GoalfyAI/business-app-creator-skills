# Goalfy Workflow Authoring Install & Update Guide — Codex

Follow this runbook exactly. It installs one local marketplace plugin containing
the External MCP configuration and the `workflow-authoring` Skill.

## Safety rules

1. Accept the package directory and Personal API Key only from the user.
2. Never invent, echo, log, or copy the key into a repository, Skill, command,
   checkpoint, or chat response.
3. The user must write the key locally to `~/.codex/.env`; do not request that
   they paste the plaintext key into chat.
4. Do not create, update, publish, or run Goalfy assets while verifying install.
5. Do not claim success until the plugin, Skill, 12 MCP tools, `bubble` action,
   and a read-only asset request are all verified in a restarted session.

## Step 0 — Detect current state

Run read-only checks:

```bash
codex --version
codex plugin marketplace list
codex plugin list
codex mcp get goalfy_workflow
test -f "$HOME/.codex/.env" && grep -q '^GOALFY_WORKFLOW_API_KEY=' "$HOME/.codex/.env"
```

Do not print the matching environment line. If the plugin, MCP, and key marker
already exist, follow `UPDATE.md`; otherwise continue.

## Step 1 — Validate the package

The user must provide the extracted package directory. Confirm it contains:

```bash
export PACKAGE_ROOT="/absolute/path/to/workflow-authoring-codex"
test -f "$PACKAGE_ROOT/.agents/plugins/marketplace.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/.codex-plugin/plugin.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/.mcp.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/skills/workflow-authoring/SKILL.md"
```

If `PACKAGE_ROOT` is unknown, ask for the extracted absolute path. Do not search
the entire home directory. Replace the example path before running the checks.

## Step 2 — Install the local plugin

```bash
codex plugin marketplace add "$PACKAGE_ROOT"
codex plugin add workflow-authoring@goalfy-workflow
```

If the marketplace is already configured, do not create a second marketplace.
Follow `UPDATE.md` and reinstall the existing plugin instead.

## Step 3 — Ask the user to store the key

# ACTION REQUIRED: Configure the GoalfyMax Personal API Key

**In GoalfyMax QA, open the account menu → Developer Tools → API Key
(`/developer/api-keys`), select New API Key, enter a 1–100 character name, and
save the `sk_...` key shown once. If the menu is missing, stop and ask an
administrator to grant the developer entry. Never use another person's key.**

**Write the exact QA Personal API Key into `~/.codex/.env` as `GOALFY_WORKFLOW_API_KEY=<key>`, then run `chmod 600 ~/.codex/.env`. Do not send the key to me.**

**When the file is ready, tell me without including the key.**

After confirmation, check only presence and permissions:

```bash
grep -q '^GOALFY_WORKFLOW_API_KEY=.' "$HOME/.codex/.env"
stat -f '%Lp' "$HOME/.codex/.env" 2>/dev/null || stat -c '%a' "$HOME/.codex/.env"
```

Never display the file.

Do not ask for or configure `user_id`, `X-User-ID`, or `X-Project-ID` as auth
parameters. The plugin sends `Authorization: Bearer <key>` and the External MCP
resolves the user identity from that key.

## Step 4 — Restart

# ACTION REQUIRED: Restart Codex

**Fully quit Codex CLI, Codex App, and any IDE extension process, then open a new session. The plugin MCP cannot inherit the new key until restart.**

**After restarting, return to this task and tell me to verify the connection.**

## Step 5 — Verify in the new session

Verify all of the following yourself:

1. `workflow-authoring` is installed and the Skill can be selected.
2. `goalfy_workflow` is connected.
3. Live `tools/list` contains exactly 12 tools.
4. Live `workflow_tpe_manage` schema includes `bubble`.
5. `list_assets` succeeds with a read-only query.

Do not open a Workflow work order merely to test installation. If verification
fails, report the exact failed gate without exposing the key or full asset data.

## Completion report

Report only:

- platform and plugin version;
- MCP connected/not connected;
- Skill loaded/not loaded;
- tool count and `bubble` present/absent;
- read-only request passed/failed;
- remaining user action, if any.
