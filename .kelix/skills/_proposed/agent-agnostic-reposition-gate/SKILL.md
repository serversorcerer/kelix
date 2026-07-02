---
name: agent-agnostic-reposition-gate
description: >-
  Reposition Kelix from single-agent (Kiro-first) to multi-agent voice while
  keeping Kiro as reference integration, plus REQ-R3 acceptance tests that lock
  the reposition. Use for P-REPOS metadata, CLI help, MCP docs, or README tasks.
---

# Agent-agnostic reposition with acceptance gate

Goal: lead with multi-agent support (Claude Code, Codex CLI, Cursor, Gemini CLI) and cite Kiro as deepest/reference integration — not sole identity.

## 1. Touch surfaces consistently

Update voice across every user-facing entry point in one phase:

| Surface | Pattern |
|---------|---------|
| `pyproject.toml` | Description names all agents; keywords include `claude`, `codex`, `cursor`, `gemini`; Kiro as flagship/deepest integration |
| `src/kelix/cli.py` | `CLI_DESCRIPTION` first paragraph lists agents; `CONFIG_TEMPLATE` adapter comment lists all valid values |
| Module docstrings | MCP server, adapters — any MCP-capable agent, Kiro registration example unchanged |
| `README.md` | Agent-agnostic identity in opening sections; first `Kiro` mention pushed below the fold |

Use `rg -i 'rebuilt for kiro'` (or project-specific stale phrases) to confirm old framing is gone.

## 2. Do not break legacy Kiro paths

- Keep `docs/kiro.md` examples and `kiro-cli mcp add` registration snippets intact.
- Do not rename the `kiro` adapter or change default behavior for existing configs.

## 3. Add REQ-R3 acceptance tests

Create or extend `tests/test_reposition.py`:

**README de-Kiro check** — first case-insensitive `kiro` mention must be after a line threshold (e.g. line 20):

```python
def _first_kiro_line(text: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if "kiro" in line.lower():
            return index
    return None
```

Assert the line exists (Kiro still documented) and `first > 20`.

**Kiro guide TOML still loads** — extract every ` ```toml ` block from `docs/kiro.md`, write to `tmp_path/.kelix/kelix.toml`, call `load_config(tmp_path)`, and assert expected kiro-specific fields (adapter, kiro_args, timeout) when the block is a full example.

## 4. Verify

```bash
pytest -q tests/test_reposition.py
pytest -q
ruff check src tests
pip install -e .   # optional: confirm package Summary metadata
kelix --help       # confirm multi-agent first paragraph
```

## 5. Phase gate

Only advance from P-REPOS after reposition tests pass and stale single-agent phrasing is cleared from metadata, CLI, and MCP docs.
