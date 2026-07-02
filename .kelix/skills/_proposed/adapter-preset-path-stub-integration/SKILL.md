---
name: adapter-preset-path-stub-integration
description: >-
  Prove a named adapter preset resolves and completes one verified kelix loop
  iteration using a PATH stub instead of the real CLI. Use when closing preset
  integration tasks (e.g. KE13) or adding CI coverage for headless agents that
  are not installed in the test environment.
---

# Adapter preset PATH-stub integration test

Unit tests for `load_config` and `make_adapter` are not enough — prove the preset survives a full `Runner` iteration without the real binary on PATH.

## When to apply

- A named preset (e.g. `claude`, `cursor`) is wired in `ADAPTER_PRESET_COMMANDS` but CI cannot install the upstream CLI.
- Acceptance requires "one verified loop iteration" through the preset, not just config resolution.

## Steps

1. **Create a minimal fixture repo** with `.kelix/backlog.md` (one `ready` task), `kelix.toml` using `adapter = "<preset>"`, trivial `[verify]` (`echo verified`), and `[git] isolation = "none"`.

2. **Write a PATH stub** named after the preset binary (e.g. `bin/claude`):
   - Emit `RATIONALE: <task-id> — <reason>` to stdout.
   - Make agent-visible progress (create a file, commit it).
   - Prepend the stub directory to `PATH` via `monkeypatch.setenv`.

3. **Assert resolution before running:**
   - `load_config` fills `cfg.agent.command` from `ADAPTER_PRESET_COMMANDS["<preset>"]`.
   - `make_adapter(cfg)` returns `CmdAdapter`.

4. **Run one iteration:**
   ```python
   result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
   ```
   Assert: exactly one iteration, `verified` and `made_progress` true, artifact on disk.

5. **Place the test** in `tests/test_adapters.py` alongside other adapter integration tests.

## Verify

```bash
pytest -q tests/test_adapters.py -k preset_run_integration
pytest -q
ruff check src tests
```

## Do not

- Require the real CLI in CI — the stub must stand in completely.
- Skip the `Runner` call; config-only smoke tests belong in `tests/test_config.py`.
