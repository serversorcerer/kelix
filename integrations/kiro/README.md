# Kelix ↔ Kiro integration package

Drop-in files that make [Kiro](https://kiro.dev) and Kelix cooperate, using
**only Kiro's public, documented surfaces** (steering, custom agents, hooks,
specs, MCP). Nothing here depends on Kiro internals.

## What's here

| File | Goes to | Purpose |
|---|---|---|
| `steering/kelix.md` | `.kiro/steering/kelix.md` | Teaches Kiro's agent the Kelix loop contract (auto-included when you mention Kelix/backlog/loop). |
| `agents/kelix.json` | `.kiro/agents/kelix.json` | The custom agent `kelix run` invokes headlessly. Ships the command denylist (`toolsSettings.shell.deniedCommands`) and a shell-audit hook — a second enforcement layer on top of Kelix's own runner checks. |
| `hooks/kelix-hooks.json` | `.kiro/hooks/kelix-hooks.json` | Optional (disabled by default): offer to seed the backlog when a spec's `tasks.md` is saved; block agent pushes to main. |

## Install

```bash
# from your repo root, after `kelix init`
mkdir -p .kiro/steering .kiro/agents .kiro/hooks
cp path/to/kelix/integrations/kiro/steering/kelix.md   .kiro/steering/
cp path/to/kelix/integrations/kiro/agents/kelix.json   .kiro/agents/
cp path/to/kelix/integrations/kiro/hooks/kelix-hooks.json .kiro/hooks/   # optional

# register Kelix's MCP server so Kiro can drive runs by tool call
kiro-cli mcp add --name kelix --command "kelix mcp" --scope workspace
```

Then point Kelix's agent adapter at this agent in `.kelix/kelix.toml`:

```toml
[agent]
adapter = "kiro"
kiro_args = ["--agent", "kelix"]
```

## Spec → overnight run in one command

```bash
# 1. Write a Kiro spec the usual way -> .kiro/specs/<name>/{requirements,design,tasks}.md
# 2. Seed the Kelix backlog from the spec's task list:
kelix init --from-spec <name>
# 3. Run it overnight — verified commits on a run branch:
kelix run --max-iterations 25
```

Spec task titles import as owner-authored, top-band backlog tasks in spec
order. Kelix writes results back as files Kiro reads naturally: retrospectives
under `.kelix/runs/`, memory in `.kelix/memory/project.md`.

## Two enforcement layers

Kelix's command policy (`src/kelix/security.py`) runs regardless of backend.
When you use the Kiro adapter, `agents/kelix.json` *also* denies the same
dangerous commands via Kiro's own permission system — so a prompt-injected
instruction has to defeat both. See `docs/SECURITY.md`.
