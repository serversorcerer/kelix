# Kiro integration guide

Kalph's primary agent backend is the [Kiro CLI](https://kiro.dev), and the
integration works in both directions: Kalph drives Kiro headlessly to execute
iterations, and Kiro can drive Kalph through steering, specs, hooks, and an
MCP server.

**Everything here uses only Kiro's public, documented surfaces** — headless
chat, steering files, custom agents, hooks, specs, skills, and MCP. Nothing
depends on Kiro internals; the full survey is in
[research/kiro-surface.md](research/kiro-surface.md).

## The headless adapter

The `kiro` adapter (the default) invokes Kiro's one-shot headless mode for
each iteration, which gives exactly the fresh-process semantics the loop
needs:

```bash
kiro-cli chat --no-interactive --trust-all-tools "<prompt>"
```

Configure it in `.kalph/kalph.toml`:

```toml
[agent]
adapter = "kiro"                    # kiro | cmd | mock
kiro_args = ["--agent", "kalph"]    # extra args; use the shipped custom agent
timeout_seconds = 1800              # per-iteration wall clock
```

Requirements: `kiro-cli` on PATH and `KIRO_API_KEY` in the environment (or a
browser session). Kalph never reads or stores the key; it only inherits the
environment variable.

`--trust-all-tools` is required because headless mode cannot prompt for
approval. Kalph runs it *inside* its own safety rails — worktree isolation,
the runner's command denylist, secret scrubbing — and the shipped custom agent
adds Kiro-side enforcement on top (below).

If you use a different agent CLI entirely, set `adapter = "cmd"` and
`command = "your-agent {prompt_file}"` (tokens `{prompt_file}` and `{prompt}`
are substituted).

## Spec → backlog: `kalph init --from-spec`

Write a Kiro spec the usual way, producing
`.kiro/specs/<name>/{requirements,design,tasks}.md`. Then:

```bash
kalph init --from-spec <name>       # import .kiro/specs/<name>/tasks.md
kalph run --max-iterations 25 --pr  # execute it overnight
```

Import behavior (from `src/kalph/kiro.py`):

- Unchecked checklist items in `tasks.md` become backlog tasks; already
  checked items are skipped.
- Tasks land as **owner-authored** (`by: owner`) in the owner priority band:
  the first task gets priority 89, each subsequent one counts down (never
  below 70), so spec order is preserved.
- Each imported task depends on the previous one (`deps:` chain), so the loop
  works the spec in order.
- Titles are sanitized (pipes and extra whitespace stripped) so spec text
  cannot forge backlog fields — spec content is data, never instructions.
- The import is idempotent per title: re-running it will not duplicate tasks.

Results flow back as files Kiro reads naturally: PR links and retrospectives
under `.kalph/runs/`, durable notes in `.kalph/memory/project.md`.

## The `.kiro/` integration package

`integrations/kiro/` in the Kalph repository ships drop-in files:

| File | Install to | Purpose |
|---|---|---|
| `steering/kalph.md` | `.kiro/steering/kalph.md` | Teaches Kiro's agent the loop contract (task format, verified-done, one task per change, PRs-only). `inclusion: auto`, keyed to mentions of Kalph, the backlog, or the loop — so interactive Kiro sessions cooperate with the loop instead of fighting it. |
| `agents/kalph.json` | `.kiro/agents/kalph.json` | The custom agent that `kalph run` invokes headlessly (`kiro_args = ["--agent", "kalph"]`). Ships Kalph's command denylist as `toolsSettings.shell.deniedCommands` and a `preToolUse` shell-audit hook. |
| `hooks/kalph-hooks.json` | `.kiro/hooks/kalph-hooks.json` | Optional, **disabled by default**: offer to seed the backlog when a spec's `tasks.md` is saved; block agent pushes to main from interactive Kiro sessions. |

Install:

```bash
# from your repo root, after `kalph init`
mkdir -p .kiro/steering .kiro/agents .kiro/hooks
cp path/to/kalph/integrations/kiro/steering/kalph.md      .kiro/steering/
cp path/to/kalph/integrations/kiro/agents/kalph.json      .kiro/agents/
cp path/to/kalph/integrations/kiro/hooks/kalph-hooks.json .kiro/hooks/   # optional
```

### Two enforcement layers

Kalph's command policy (`src/kalph/security.py`) runs regardless of backend.
With the Kiro adapter and the shipped agent config, the same dangerous
commands (`curl | sh`, force-push, pushes to main, package publish, credential
reads, `sudo`, …) are *also* denied by Kiro's own permission system. A
prompt-injected instruction has to defeat both, independently. See the
[security model](SECURITY.md).

## Registering the MCP server

Let Kiro drive Kalph by tool call — start runs, check status, inspect memory,
hit the kill switch — by registering Kalph's stdio MCP server:

```bash
kiro-cli mcp add --name kalph --command "kalph mcp" --scope workspace
```

The four tools (`kalph_run`, `kalph_status`, `kalph_memory`, `kalph_stop`) and
their exact schemas are documented in [mcp.md](mcp.md).

## Kalph vs Kiro's `/goal`

Kiro's `/goal` is an in-session autonomous loop: great for a single task while
you watch, but it accumulates context within one session. Kalph is the
external, stateless loop: a backlog of tasks, fresh context per iteration,
overnight and unattended. They compose — use `/goal` interactively, hand the
backlog to Kalph when you step away.
