# Goalfy Workflow Authoring Install & Update Guide — Claude Code

Follow this runbook exactly. It installs one local marketplace plugin containing
the External MCP configuration and the `workflow-authoring` Skill.

## Safety rules

1. Accept the package directory and Personal API Key only from the user.
2. Never invent, echo, log, or copy the key into a repository, Skill, command,
   checkpoint, or chat response.
3. The user must write the key locally to `~/.claude/settings.json`; do not ask
   them to paste the plaintext key into chat.
4. Preserve every existing Claude Code setting when adding the environment key.
5. Do not create, update, publish, or run Goalfy assets while verifying install.
6. Do not claim success until the plugin, Skill, 12 MCP tools, `bubble` action,
   and a read-only asset request are all verified in a restarted session.

## Step 0 — Detect current state

Run read-only checks:

```bash
claude --version
claude plugin list
claude mcp get goalfy_workflow
test -f "$HOME/.claude/settings.json" && grep -q 'GOALFY_WORKFLOW_API_KEY' "$HOME/.claude/settings.json"
```

Do not print the matching JSON line. If the plugin, MCP, and key marker already
exist, follow `UPDATE.md`; otherwise continue.

## Step 1 — Validate the package

The user must provide the extracted package directory. Confirm it contains:

```bash
export PACKAGE_ROOT="/absolute/path/to/workflow-authoring-claude-code"
test -f "$PACKAGE_ROOT/.claude-plugin/marketplace.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/.claude-plugin/plugin.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/.mcp.json"
test -f "$PACKAGE_ROOT/plugins/workflow-authoring/skills/workflow-authoring/SKILL.md"
```

If `PACKAGE_ROOT` is unknown, ask for the extracted absolute path. Do not search
the entire home directory. Replace the example path before running the checks.

## Step 2 — Install the local plugin

```bash
claude plugin marketplace add "$PACKAGE_ROOT"
claude plugin install workflow-authoring@goalfy-workflow
```

If the marketplace is already configured, do not create a second marketplace.
Follow `UPDATE.md` and update the existing plugin instead.

## Step 3 — Ask the user to store the key

# ACTION REQUIRED: Configure the GoalfyMax Personal API Key

**Merge `"GOALFY_WORKFLOW_API_KEY": "<exact key>"` into the existing `env` object in `~/.claude/settings.json`. Preserve all other settings and do not send the key to me.**

**When the file is ready, tell me without including the key.**

After confirmation, validate only structure and key presence without printing
the value:

```bash
python3 -c 'import json, pathlib; p=pathlib.Path.home()/".claude/settings.json"; d=json.loads(p.read_text()); assert isinstance(d.get("env"), dict) and d["env"].get("GOALFY_WORKFLOW_API_KEY")'
```

Never display the settings file.

## Step 4 — Restart

# ACTION REQUIRED: Restart Claude Code

**Fully quit Claude Code, its Desktop/IDE host, and every existing session, then open a new session. The plugin MCP cannot inherit the new key until restart.**

**After restarting, return to this task and tell me to verify the connection.**

## Step 5 — Verify in the new session

Verify all of the following yourself:

1. `workflow-authoring` is installed and the Skill can be selected.
2. `/mcp` shows `goalfy_workflow` connected.
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
