# Prior art: what to steal, what to fix

Surveyed 2026-07. Three implementations studied before writing Kalph code.

## 1. ralph-orchestrator (github.com/mikeyobrien/ralph-orchestrator)

Rust CLI (`ralph-cli`), MIT, ~3k stars. The most complete open implementation.

**What it does:** `ralph init --backend <agent>` / `ralph plan` (interactive
spec-authoring session that writes `.ralph/specs/<feature>/requirements.md`,
`design.md`, `implementation-plan.md`) / `ralph run -p "<prompt>"` loops until
the agent outputs `LOOP_COMPLETE` or hits the iteration limit. Supports many
backends (Claude Code, **Kiro**, Gemini CLI, Codex, Amp, Copilot, OpenCode).
Adds a "hat system" (personas coordinating through events), backpressure gates
(tests/lint/typecheck reject incomplete work), persistent "memories & tasks", a
web dashboard, Telegram human-in-the-loop, and an MCP server mode scoped to one
workspace root per instance.

**Steal:**
- Pluggable backend adapters behind one interface — proves a Kiro CLI backend
  is viable and that the loop core must not know which agent it runs.
- Output-sentinel completion (`LOOP_COMPLETE`) — simple, deterministic.
- Backpressure gates as first-class config, not agent discipline.
- MCP server mode with one-workspace-per-instance scoping (deterministic).
- Plan artifacts as files under the tool's dot-directory.

**Fix / avoid:**
- The hat/event system reintroduces intra-process orchestration between
  personas — drifts from "stateless composition through files." Kalph's roles
  are *separate whole loops* with different prompts, not personas exchanging
  events inside one process.
- Big surface area (web dashboard, Telegram bot, tRPC backend) before the loop
  itself is bulletproof. Kalph ships the loop first; `kalph status` reads
  coordination files and renders text — no server.
- Memories exist but aren't budgeted or layered; nothing enforces that learning
  is injected as bounded data.

## 2. Official Anthropic `ralph-loop` plugin (anthropics/claude-plugins-official)

A Claude Code plugin (also seen as `ralph-wiggum` in anthropics/claude-code).
`/ralph-loop "<prompt>" --max-iterations N --completion-promise "DONE"` starts
a loop **inside the current session**: a Stop hook intercepts session exit,
re-feeds the same prompt (`decision: block`, `reason: <prompt>`), and counts
iterations in a project-scoped state file (`.claude/ralph-loop.local.md`) with
session-id isolation. Completion is signalled by the agent emitting
`<promise>DONE</promise>` — with an explicit warning "ONLY when statement is
TRUE - do not lie to exit!".

**Steal:**
- The completion-promise framing: make the sentinel a *statement the agent
  asserts is true*, and pair it with mechanical verification so lying is
  detectable. Kalph goes further: the sentinel alone never suffices; the runner
  re-runs verification before honoring it.
- State file with owner/session identity to prevent cross-session interference
  — Kalph's fleet claim files need exactly this.
- Tiny, auditable core (one hook script + state file).

**Fix / avoid:**
- The loop lives inside one long-lived session, so context accumulates —
  violates fresh-context-per-iteration. Huntley himself notes the plugin "isn't
  it" for this reason. Kalph uses an external runner spawning fresh processes.
- Iteration counting via frontmatter in a markdown state file is fragile
  (their own troubleshooting docs show parsing bugs); Kalph uses JSON for
  runner-owned state, markdown for human-owned state.
- No verification gate at all — completion rests entirely on the agent's
  honesty.

## 3. Hermes Agent (github.com/NousResearch/hermes-agent)

Nous Research's self-improving agent. Long-lived process with a **closed
learning loop**: autonomous skill creation after complex tasks, skills that
self-improve during use, agent-curated memory with periodic nudges, FTS5
search over past sessions, layered memory (working / episodic / long-term
semantic via Honcho user modeling), subagent delegation, and compatibility
with the agentskills.io open standard (SKILL.md + YAML frontmatter — the same
format Kiro CLI loads natively from `.kiro/skills/`).

**Steal (adapted to stateless loops):**
- **The closed learning loop**: after completing non-obvious work, distill a
  skill; when a skill is used and found wanting, improve it. Kalph puts both
  steps in the iteration contract (a completed task may emit/update a skill
  file) and the post-run retrospective.
- **Layered memory**: working memory = the iteration's own context (dies with
  the process); episodic = append-only per-iteration outcome records;
  long-term semantic = curated project memory. Hermes keeps these in a
  database inside a live process; Kalph keeps them as human-readable files
  under `.kalph/memory/`, injected as budgeted digests.
- **Memory nudges**: Hermes periodically prompts itself to persist knowledge.
  Kalph's equivalent is structural: the iteration prompt ends with "write what
  you learned to memory *before* exiting," and the runner treats memory files
  as part of the commit.
- **agentskills.io SKILL.md format** for skills — portable to Kiro, Claude
  Code, Hermes, and others. Kalph writes `.kalph/skills/<name>/SKILL.md` in
  this exact format and symlink-friendly layout.

**Fix / avoid:**
- Everything Hermes keeps in its head (session history, user model, working
  memory) must live in files for Kalph, or it doesn't exist next iteration.
- Hermes trusts its own memory store implicitly. Kalph treats even its own
  memory as *data* under prompt-injection rules (memory content cannot
  override the loop contract) because unattended repos are attack surface.
- No token budget on recalled context; Kalph caps digest size in config.

## Synthesis: Kalph's position

| Dimension | ralph-orchestrator | ralph-loop plugin | Hermes | Kalph |
|---|---|---|---|---|
| Loop process | external runner | in-session hook | long-lived | external runner, fresh process each iteration |
| Completion | output sentinel | promise string | n/a | sentinel **and** runner-verified evidence |
| Memory | flat memories | none | layered, in-process | layered, in files, budget-capped |
| Skills | n/a | n/a | agentskills.io, self-improving | agentskills.io files, loop-driven acquisition |
| Multi-agent | hats/events in-process | no | subagents in-process | independent loops + files + git only |
| Verification | backpressure gates | none | agent judgment | config-declared verify commands enforced by runner |
