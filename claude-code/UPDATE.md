# Update and key rotation — Claude Code

## Update the local package

Extract the new package to a stable directory, then use its marketplace root:

```bash
claude plugin uninstall workflow-authoring@goalfy-workflow
claude plugin marketplace remove goalfy-workflow
claude plugin marketplace add "$PACKAGE_ROOT"
claude plugin install workflow-authoring@goalfy-workflow
```

Run `/reload-plugins` or fully restart Claude Code, then repeat the five
verification gates in `README.md`. Do not remove the key setting during an
ordinary plugin update.

## Rotate the Personal API Key

1. Create or obtain the replacement key in GoalfyMax QA.
2. Replace only `env.GOALFY_WORKFLOW_API_KEY` in
   `~/.claude/settings.json`, preserving all other settings.
3. Revoke the old key after the replacement is stored.
4. Fully restart Claude Code and run the read-only verification again.

Never print either key while comparing or troubleshooting them.
