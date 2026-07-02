---
name: add-adapter-preset
description: >-
  Wire a new named agent adapter preset (e.g. cursor, claude) through config
  resolution, CmdAdapter routing, kelix init, and CLI help comments. Use when
  closing REQ-A1 preset tasks or adding headless CLI support beyond kiro/cmd/mock.
---

# Add a named adapter preset

Presets let users set `adapter = "<name>"` without hand-writing `[agent].command`. Each preset maps to a `CmdAdapter` command template with `{prompt}` substitution.

## 1. Register the command template

In `src/kelix/config.py`, add an entry to `ADAPTER_PRESET_COMMANDS`:

```python
"<preset>": "<binary-and-flags> {prompt}",
```

- Cite upstream headless-doc URL in an adjacent comment when not Kelix-verified.
- `VALID_ADAPTERS` expands automatically from the dict keys.

## 2. Resolve command at load time

In `load_config`, after parsing TOML, when `cfg.agent.adapter` is a preset key and `command` is empty, fill:

```python
preset = ADAPTER_PRESET_COMMANDS.get(cfg.agent.adapter)
if preset and not cfg.agent.command:
    cfg.agent.command = preset
```

Named presets and `cmd` share the same command field — do not add a separate adapter class.

## 3. Route in make_adapter

In `src/kelix/adapters.py`, treat preset names like `cmd`:

```python
if name in ADAPTER_PRESET_COMMANDS or name == "cmd":
    return CmdAdapter(cfg)
```

## 4. Surface in CLI and init

- Extend the `adapter = ...` comment in `render_config_template()` (`src/kelix/cli.py`).
- Add the preset to `INIT_AGENTS` so `kelix init --agent <preset>` writes it into new `.kelix/kelix.toml`.
- Named presets omit a `command =` line in the template; `cmd` keeps the placeholder `command = "your-cli {prompt}"`.

Non-interactive init **requires** `--agent`; interactive init lists all `INIT_AGENTS`.

## 5. Test coverage

In `tests/test_config.py`:

- Parametrize preset names; assert `load_config` fills `cfg.agent.command` to the template when omitted.
- Assert explicit `command` overrides are preserved.

In `tests/test_init_agent.py`:

- `render_config_template("<preset>")` contains `adapter = "<preset>"` and no `command =` line.
- `cmd_init` with `--agent <preset>` produces a loadable config whose resolved command matches the preset.

## 6. Ship the guide (if REQ-A2)

Follow the **ship-agent-guide** skill for `docs/agents/<preset>.md` and `tests/test_agent_guides.py`.

## 7. Verify

```bash
pytest -q tests/test_config.py tests/test_init_agent.py
pytest -q
ruff check src tests
```
