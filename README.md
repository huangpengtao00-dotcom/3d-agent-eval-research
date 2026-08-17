# Evidence-grounded 3D Agent Eval

Source-neutral research pipeline for **evidence-grounded evaluation of 3D-generation agents** — the 3D-agent counterpart of "is the agent better?" turned into a reproducible measurement.

把「3D 生成 agent 变好了吗」从印象变成可复现的测量。

## What it does

Given a source workspace, the pipeline:

1. **canonical** — normalizes task specification into a versioned canonical form;
2. **bundle** — snapshots the source into an evidence bundle (with integrity checksums);
3. **audit** — runs a public-safety audit over the bundle, ensuring it contains no identifying internal references or secret-like assignments;
4. **contracts / artifacts / mapping** — typed schemas, artifact handling, and task→evidence mapping used across the pipeline.

The core thesis: **an evaluation verdict is only as good as the evidence it can point to.** Every claim a judge makes must be backed by a bundle that a third party can re-audit.

## Quick start

```bash
uv sync
uv run agent-eval --help          # bundle / audit
uv run pytest                     # 32 tests, all green
```

## Usage

```bash
# snapshot a source workspace into an evidence bundle
uv run agent-eval bundle <source-dir> <output-bundle.jsonl>

# audit a bundle for identifying/internal or secret-like content
uv run agent-eval audit <bundle-path>
```

## Design constraints

- **Source-neutral**: the pipeline contains no dependency on any internal system, data, or naming. Public-safety audit is a first-class test (`tests/test_public_safety.py`).
- **Reproducible**: single-command setup, deterministic tests, versioned bundles.
- **Minimal deps**: `pydantic` + `typer` only.

## Layout

```
src/agent_eval/
  canonical.py     — versioned task-spec canonicalization
  bundle.py        — evidence bundle snapshot + integrity
  audit.py         — public-safety / secret-pattern audit
  contracts.py     — typed schemas (pydantic)
  artifacts.py     — artifact handling
  mapping.py       — task → evidence mapping
  cli.py           — agent-eval CLI (bundle, audit)
tests/             — 32 tests across contracts / artifacts / safety
```
