# Kiro integration guide

Kelix's primary agent backend is the [Kiro CLI](https://kiro.dev), and the
integration works in both directions: Kelix drives Kiro headlessly to execute
iterations, and Kiro can drive Kelix through steering, specs, hooks, and an
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

Configure it in `.kelix/kelix.toml`:

```toml
[agent]
adapter = "kiro"                    # kiro | cmd | mock
kiro_args = ["--agent", "kelix"]    # extra args; use the shipped custom agent
timeout_seconds = 1800              # per-iteration wall clock
```

Requirements: `kiro-cli` on PATH and `KIRO_API_KEY` in the environment (or a
browser session). Kelix never reads or stores the key; it only inherits the
environment variable.

`--trust-all-tools` is required because headless mode cannot prompt for
approval. Kelix runs it *inside* its own safety rails — worktree isolation,
the runner's command denylist, secret scrubbing — and the shipped custom agent
adds Kiro-side enforcement on top (below).

If you use a different agent CLI entirely, set `adapter = "cmd"` and
`command = "your-agent {prompt_file}"` (tokens `{prompt_file}` and `{prompt}`
are substituted).

## Spec → backlog: `kelix init --from-spec`

Write a Kiro spec the usual way, producing
`.kiro/specs/<name>/{requirements,design,tasks}.md`. Then:

```bash
kelix init --from-spec <name>       # import .kiro/specs/<name>/tasks.md
kelix run --max-iterations 25 --pr  # execute it overnight
```

Import behavior (from `src/kelix/kiro.py`):

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
under `.kelix/runs/`, durable notes in `.kelix/memory/project.md`.

## The `.kiro/` integration package

`integrations/kiro/` in the Kelix repository ships drop-in files:

| File | Install to | Purpose |
|---|---|---|
| `steering/kelix.md` | `.kiro/steering/kelix.md` | Teaches Kiro's agent the loop contract (task format, verified-done, one task per change, PRs-only). `inclusion: auto`, keyed to mentions of Kelix, the backlog, or the loop — so interactive Kiro sessions cooperate with the loop instead of fighting it. |
| `agents/kelix.json` | `.kiro/agents/kelix.json` | The custom agent that `kelix run` invokes headlessly (`kiro_args = ["--agent", "kelix"]`). Ships Kelix's command denylist as `toolsSettings.shell.deniedCommands` and a `preToolUse` shell-audit hook. |
| `hooks/kelix-hooks.json` | `.kiro/hooks/kelix-hooks.json` | Optional, **disabled by default**: offer to seed the backlog when a spec's `tasks.md` is saved; block agent pushes to main from interactive Kiro sessions. |

Install:

```bash
# from your repo root, after `kelix init`
mkdir -p .kiro/steering .kiro/agents .kiro/hooks
cp path/to/kelix/integrations/kiro/steering/kelix.md      .kiro/steering/
cp path/to/kelix/integrations/kiro/agents/kelix.json      .kiro/agents/
cp path/to/kelix/integrations/kiro/hooks/kelix-hooks.json .kiro/hooks/   # optional
```

### Two enforcement layers

Kelix's command policy (`src/kelix/security.py`) runs regardless of backend.
With the Kiro adapter and the shipped agent config, the same dangerous
commands (`curl | sh`, force-push, pushes to main, package publish, credential
reads, `sudo`, …) are *also* denied by Kiro's own permission system. A
prompt-injected instruction has to defeat both, independently. See the
[security model](SECURITY.md).

## Registering the MCP server

Let Kiro drive Kelix by tool call — start runs, check status, inspect memory,
hit the kill switch — by registering Kelix's stdio MCP server:

```bash
kiro-cli mcp add --name kelix --command "kelix mcp" --scope workspace
```

The four tools (`kelix_run`, `kelix_status`, `kelix_memory`, `kelix_stop`) and
their exact schemas are documented in [mcp.md](mcp.md).

## Kelix vs Kiro's `/goal`

Kiro's `/goal` is an in-session autonomous loop: great for a single task while
you watch, but it accumulates context within one session. Kelix is the
external, stateless loop: a backlog of tasks, fresh context per iteration,
overnight and unattended. They compose — use `/goal` interactively, hand the
backlog to Kelix when you step away.
