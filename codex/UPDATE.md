# Update and key rotation — Codex

## Update the local package

Extract the new package to a stable directory, then use its marketplace root:

```bash
codex plugin remove workflow-authoring@goalfy-workflow
codex plugin marketplace remove goalfy-workflow
codex plugin marketplace add "$PACKAGE_ROOT"
codex plugin add workflow-authoring@goalfy-workflow
```

Fully restart Codex and repeat the five verification gates in `README.md`. Do
not delete `~/.codex/.env` during an ordinary plugin update.

## Rotate the Personal API Key

1. Create or obtain the replacement key in GoalfyMax QA.
2. Replace only the `GOALFY_WORKFLOW_API_KEY` line in `~/.codex/.env`.
3. Run `chmod 600 ~/.codex/.env`.
4. Revoke the old key after the new key is stored.
5. Fully restart Codex and run the read-only verification again.

Never print either key while comparing or troubleshooting them.
