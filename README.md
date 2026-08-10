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
version before committing:

```bash
uv run python workflow-authoring/release/build_platform_packages.py release \
  --version <MAJOR.MINOR.PATCH> \
  --reason "<tested change>"
```
