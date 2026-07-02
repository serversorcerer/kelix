# Kalph ↔ Kiro integration package

Drop-in files that make [Kiro](https://kiro.dev) and Kalph cooperate, using
**only Kiro's public, documented surfaces** (steering, custom agents, hooks,
specs, MCP). Nothing here depends on Kiro internals.

## What's here

| File | Goes to | Purpose |
|---|---|---|
| `steering/kalph.md` | `.kiro/steering/kalph.md` | Teaches Kiro's agent the Kalph loop contract (auto-included when you mention Kalph/backlog/loop). |
| `agents/kalph.json` | `.kiro/agents/kalph.json` | The custom agent `kalph run` invokes headlessly. Ships the command denylist (`toolsSettings.shell.deniedCommands`) and a shell-audit hook — a second enforcement layer on top of Kalph's own runner checks. |
| `hooks/kalph-hooks.json` | `.kiro/hooks/kalph-hooks.json` | Optional (disabled by default): offer to seed the backlog when a spec's `tasks.md` is saved; block agent pushes to main. |

## Install

```bash
# from your repo root, after `kalph init`
mkdir -p .kiro/steering .kiro/agents .kiro/hooks
cp path/to/kalph/integrations/kiro/steering/kalph.md   .kiro/steering/
cp path/to/kalph/integrations/kiro/agents/kalph.json   .kiro/agents/
cp path/to/kalph/integrations/kiro/hooks/kalph-hooks.json .kiro/hooks/   # optional

# register Kalph's MCP server so Kiro can drive runs by tool call
kiro-cli mcp add --name kalph --command "kalph mcp" --scope workspace
```

Then point Kalph's agent adapter at this agent in `.kalph/kalph.toml`:

```toml
[agent]
adapter = "kiro"
kiro_args = ["--agent", "kalph"]
```

## Spec → overnight run in one command

```bash
# 1. Write a Kiro spec the usual way -> .kiro/specs/<name>/{requirements,design,tasks}.md
# 2. Seed the Kalph backlog from the spec's task list:
kalph init --from-spec <name>
# 3. Run it overnight, leaving reviewable PRs by morning:
kalph run --max-iterations 25 --pr
```

Spec task titles import as owner-authored, top-band backlog tasks in spec
order. Kalph writes results back as files Kiro reads naturally: PR links and
retrospectives under `.kalph/runs/`, memory in `.kalph/memory/project.md`.

## Two enforcement layers

Kalph's command policy (`src/kalph/security.py`) runs regardless of backend.
When you use the Kiro adapter, `agents/kalph.json` *also* denies the same
dangerous commands via Kiro's own permission system — so a prompt-injected
instruction has to defeat both. See `docs/SECURITY.md`.
