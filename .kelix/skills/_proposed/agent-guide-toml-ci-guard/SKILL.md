---
name: agent-guide-toml-ci-guard
description: >-
  Parametrize load_config smoke tests over every fenced [agent] TOML block in
  agent guides so documentation drift breaks CI instead of user installs. Use
  when adding or updating docs/agents/*.md, docs/kiro.md, or consolidating
  duplicate per-guide TOML tests.
---

# Agent guide TOML CI guard

User-facing guides embed copy-pasteable `kelix.toml` snippets. Without CI, a typo in a fenced block ships to docs and fails only at `kelix init` time.

## When to apply

- A guide ships or updates `[agent]` TOML examples (`docs/kiro.md`, `docs/agents/*.md`).
- Duplicate per-guide TOML tests exist elsewhere — consolidate into one parametrized module.

## Steps

1. **Centralize guide paths** in `tests/test_agent_guides.py`:
   ```python
   AGENT_GUIDES: tuple[tuple[str, Path], ...] = (
       ("kiro", ROOT / "docs" / "kiro.md"),
       ("cursor", ROOT / "docs" / "agents" / "cursor.md"),
       # ... all shipped guides
   )
   ```

2. **Extract fenced TOML containing `[agent]`:**
   ```python
   _TOML_FENCE_RE = re.compile(r"```toml\n(.*?)```", re.DOTALL)

   def _agent_toml_blocks(markdown: str) -> list[str]:
       return [b for b in _TOML_FENCE_RE.findall(markdown) if "[agent]" in b]
   ```

3. **Parametrize `load_config` over every block:**
   ```python
   @pytest.mark.parametrize(("guide_name", "toml_block"), _guide_toml_load_cases())
   def test_agent_guide_agent_toml_blocks_load(guide_name, toml_block, tmp_path):
       (tmp_path / ".kelix" / "kelix.toml").write_text(toml_block + "\n")
       load_config(tmp_path)  # must not raise
   ```

4. **Guard minimum coverage** — each guide must have at least one `[agent]` block:
   ```python
   def test_all_five_agent_guides_have_agent_toml():
       for guide_name, path in AGENT_GUIDES:
           assert _agent_toml_blocks(path.read_text()), f"{guide_name} missing [agent] TOML"
   ```

5. **Remove duplicates** — if `tests/test_reposition.py` or similar had a single-guide TOML test, delete it and keep the consolidated module.

## Verify

```bash
pytest -q tests/test_agent_guides.py
pytest -q
ruff check src tests
```

## Do not

- Test only `docs/kiro.md` — every shipped guide must be in `AGENT_GUIDES`.
- Parse TOML manually — call `load_config` so validation stays aligned with production.
