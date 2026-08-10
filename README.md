# Scene Creator Skills

This repository is the canonical source for coding-agent Skills used to create
GoalfyMax scenario packages. Do not keep a second editable Skill copy in an MCP
server repository.

## Skills

- [`workflow-authoring`](workflow-authoring/SKILL.md): create, validate, and
  publish Workflow scenario packages through the audited External MCP.

`workflow-authoring` owns the External Agent procedure and high-risk
guardrails. Complete shared Workflow contracts, examples, and diagnosis
documents remain server-owned MCP Knowledge and are loaded at runtime through
`get_diagnosis_doc`.

## Validate

```bash
uv run pytest -q
uv run ruff check tests workflow-authoring/release/build_platform_packages.py
uv run python workflow-authoring/release/build_platform_packages.py check
```

## Install directly from this repository

The repository root is a marketplace for both Codex and Claude Code. The
`codex/` and `claude-code/` directories are generated, checked-in install
trees; edit only the canonical files under `workflow-authoring/`.

Codex:

```bash
codex plugin marketplace add \
  git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git \
  --ref main
codex plugin add workflow-authoring@goalfy-workflow
```

Claude Code:

```bash
claude plugin marketplace add \
  git@codeup.aliyun.com:goalfyai/goalfyagent/scene-creator-skills.git
claude plugin install workflow-authoring@goalfy-workflow
```

Both plugins connect to the same External MCP. Configure the requested
`GOALFY_WORKFLOW_API_KEY` value with a GoalfyMax Personal API Key; never commit
the key to this repository. Obtain it in GoalfyMax QA from the account menu →
**Developer Tools** → **API Key** (`/developer/api-keys`). The plugin sends it
as a Bearer credential; no separate user ID authentication parameter is needed.

## Build install packages

```bash
uv run python workflow-authoring/release/build_platform_packages.py build \
  --output-dir dist/workflow-skills
```

The build produces self-contained Codex and Claude Code local-marketplace ZIPs
that install the Skill and External MCP together, plus a platform-neutral Skill
ZIP. Platform-specific installation and update instructions live under
[`workflow-authoring/release/platforms`](workflow-authoring/release/platforms/).

When Skill content, references, or platform templates change, publish a new
version before committing. The release command also regenerates the direct
marketplace trees:

```bash
uv run python workflow-authoring/release/build_platform_packages.py release \
  --version <MAJOR.MINOR.PATCH> \
  --reason "<tested change>"
```

Run `sync` only to restore deleted or locally edited generated files without
changing the released content:

```bash
uv run python workflow-authoring/release/build_platform_packages.py sync
```
