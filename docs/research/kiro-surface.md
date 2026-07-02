# Kiro public surface: integration points for Kelix

Surveyed 2026-07 from the public docs at kiro.dev/docs (index: kiro.dev/llms.txt).
Kelix uses **only** the interfaces documented here. If a page moves, everything
below is discoverable from the docs index.

Kiro ships three surfaces: the **IDE**, the **CLI** (`kiro-cli`), and **Web**.
Kelix's primary integration target is the **Kiro CLI**, because it is the only
surface that supports unattended, scriptable agent invocation — which is what a
Ralph loop needs. The IDE integration package (steering/specs/hooks) rides on
shared `.kiro/` file conventions that both IDE and CLI read.

## 1. Headless invocation (the loop's engine) — docs/cli/headless

```bash
export KIRO_API_KEY=ksk_...        # from app.kiro.dev, Pro/Pro+/Power plans
kiro-cli chat --no-interactive --trust-all-tools "prompt"
```

- `--no-interactive`: print response to stdout and exit. Requires the prompt as
  an argument. No mid-session input. **This is exactly the fresh-process,
  one-shot semantics Ralph needs.**
- `--trust-all-tools` or `--trust-tools=<categories>` (e.g. `read,grep,write`):
  headless can't prompt for approval. Kelix defaults to `--trust-all-tools`
  *inside* its own safety rails (worktree isolation + hooks-based command
  denylist) and documents the tighter `--trust-tools` alternative.
- `--agent <name>`: use a custom agent config — Kelix ships one (see §3).
- Exit codes (docs/cli/reference/exit-codes): 0 success, 1 general failure,
  3 MCP startup failure (with `--require-mcp-startup`).
- Auth precedence: browser session, then `KIRO_API_KEY`. `kiro-cli whoami`
  to check. Kelix never reads/stores the key; it only inherits the env var.
- `KIRO_LOG_NO_COLOR=1` for clean transcript capture.

**Kelix adapter command (default):**
`kiro-cli chat --no-interactive --trust-all-tools --agent kelix <prompt-from-file>`

## 2. Steering files — docs/steering, docs/cli/steering

- Workspace: `.kiro/steering/*.md`; global: `~/.kiro/steering/`. Markdown with
  optional YAML frontmatter `inclusion: always | fileMatch | manual | auto`.
- `AGENTS.md` (repo root or `~/.kiro/steering/`) is also honored, always
  included, no inclusion modes.
- File references inside steering: `#[[file:relative/path]]`.

**Kelix ships** `.kiro/steering/kelix.md` (inclusion: auto, description keyed
to Kelix/loop/backlog requests) teaching Kiro's agent the loop contract: how to
read `.kelix/backlog.md`, the one-task rule, verified-done, and how to start
runs. This makes interactive Kiro sessions cooperate with the loop instead of
fighting it.

## 3. Custom agents — docs/cli/custom-agents/*

JSON at `.kiro/agents/<name>.json` (workspace) or `~/.kiro/agents/`:
`prompt` (inline or `file://`), `tools`, `allowedTools` (glob patterns),
`toolsSettings` (e.g. `shell.allowedCommands` / `deniedCommands`,
`write.allowedPaths`), `resources` (`file://`, `skill://` globs), `hooks`
(`agentSpawn`, `preToolUse` with matcher — **can block**, `postToolUse`,
`stop`), `mcpServers`, `model`.

**Kelix ships** `.kiro/agents/kelix.json`:
- `prompt: file://../../.kelix/prompts/iteration.md` (the static prompt),
- `resources`: backlog, memory digests, `skill://.kelix/skills/**/SKILL.md`,
- `toolsSettings.shell.deniedCommands`: Kelix's denylist enforced *inside*
  Kiro's own permission layer (defense in depth with Kelix's runner),
- `hooks.preToolUse`: audit-log shell commands to the iteration transcript.

## 4. Hooks — docs/hooks (IDE), docs/cli/hooks (CLI)

IDE hooks: JSON in `.kiro/hooks/`, triggers `SessionStart`, `Stop`,
`PreToolUse` (blocking), `PostToolUse`, `PreTaskExec`/`PostTaskExec` (spec
tasks), `UserPromptSubmit`, `PostFileCreate/Save/Delete`; actions are agent
prompts or shell commands; exit code 2 blocks for blockable triggers, stdout of
`SessionStart`/`UserPromptSubmit` command hooks joins context.

**Kelix ships** example hooks (opt-in): "on spec task file save, offer to seed
the Kelix backlog" and "on tests failing, propose a fixer run". Agent-config
hooks (§3) are used for in-loop auditing.

## 5. Specs — docs/specs

`.kiro/specs/<feature>/requirements.md` + `design.md` + `tasks.md`; tasks.md is
a checklist Kiro tracks and can execute in dependency waves.

**Kelix maps** `tasks.md` checklist items → backlog tasks (owner-authored
priority class), preserving the spec path as the task's rationale link.
`kelix init --from-spec <name>` performs the import; Kelix writes results back
as files (PR links in retrospectives) that Kiro naturally reads.

## 6. Skills — docs/skills, docs/cli/skills

Open Agent Skills standard (agentskills.io): folder with `SKILL.md`, YAML
frontmatter `name` (≤64 chars, kebab) + `description` (≤1024 chars), optional
`references/`. Workspace `.kiro/skills/`, global `~/.kiro/skills/`. Loaded
progressively: metadata at start, body on demand.

**Kelix's skills live at `.kelix/skills/<name>/SKILL.md` in the same format.**
Because the format is identical, a shareable skill can be copied into
`.kiro/skills/` so Kiro sessions benefit from what the loop learned. (Kept
separate so `.kelix/` stays gitignored-by-default while curated skills can be
committed.) NOTE (as-built): `kelix init` creates `.kelix/skills/` but does not
auto-copy into `.kiro/skills/`; that copy is a documented manual step.

## 7. MCP — docs/mcp, docs/cli/mcp/*

Config at `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json`
(global); stdio servers via `command`/`args`/`env`. `kiro-cli mcp add|list|...`.

**Kelix ships** `kelix mcp` (stdio MCP server exposing start/status/memory/
stop tools) plus a documented one-liner to register it with Kiro. This is how
"Kiro drives Kelix" works without any non-public interface.

## 8. Other relevant surfaces (noted, not depended on)

- `/goal` (docs/cli/chat/goal): Kiro's own in-session autonomous loop with
  verification. In-session (accumulating context), max ~iterations per goal.
  Good for single tasks; not a substitute for the external stateless loop.
  Kelix docs position them honestly: `/goal` for one task while you watch,
  Kelix for a backlog overnight.
- ACP (docs/cli/acp): Kiro CLI as an Agent Client Protocol server — a possible
  future adapter transport; not used in v1 (headless chat is simpler and
  sufficient).
- Kiro Web automations/autonomous mode: cloud-side, not scriptable locally;
  out of scope.
- CLI 3.0 early access (`kiro-cli --v3`): agent config moves to Markdown,
  hooks become standalone files. Kelix targets stable 2.x surfaces; the
  adapter isolates version differences.

## Consequences for Kelix's design

1. The agent adapter interface is one function: *run(prompt-file, cwd, env) →
   (exit code, transcript)*. Default adapter shells out to `kiro-cli chat
   --no-interactive`. A `mock` adapter (scripted responses) powers CI.
2. Everything Kelix teaches Kiro is files under `.kiro/` — steering, agent
   config, hooks, skills, MCP registration. No plugin API, no internals.
3. Kiro's permission system (`allowedTools`, `toolsSettings`, `preToolUse`
   hooks) gives Kelix a second, independent enforcement layer for its command
   policy — the runner's own checks remain primary because they're
   agent-agnostic.
