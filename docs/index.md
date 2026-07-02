# Kelix documentation

You can write a spec once, point any headless coding agent at it overnight,
and return to verified commits — each gated by your repo's own test and lint
commands, not agent promises.

That is not hypothetical. The dogfood proof shipped a full stdlib task-tracker
library unattended:
**[12/12 tasks verified-done in 12 iterations, zero failures](proof/final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd)**
(see the [final build report](proof/final-report.md)). Reproduce the verify gate
with `pytest tests/test_verify.py -q`.

**The loop that climbs.** Ralph runs in circles; Kelix comes back higher.

Kelix runs any headless coding agent in a loop against a static prompt: every
iteration is a fresh, stateless process; all state lives in files and git
history; the loop wins through repetition, not cleverness. Use **Claude Code**,
**Codex CLI**, **Cursor**, **Gemini CLI**, or your own CLI adapter — Kelix
keeps [Ralph's](https://ghuntley.com/ralph/) core and adds persistent memory,
self-improvement from loop outcomes, legible prioritization, and a
file-coordinated fleet mode — so you can write a spec once and wake up to
verified commits on a run branch.

```bash
pipx install kelix
cd your-repo && kelix init
kelix run --max-iterations 25
```

## Agents

Kelix is agent-agnostic: configure one adapter in `.kelix/kelix.toml` and the
loop stays the same.

- **[Kiro guide](kiro.md)** — deepest integration: headless adapter, spec→backlog
  import, the `.kiro/` steering/agent/hooks package, and MCP server registration.
- **[Cursor guide](agents/cursor.md)** — Kelix-verified headless Cursor CLI wiring.
- **[Claude Code guide](agents/claude.md)** — upstream-sourced Claude Code CLI setup.
- **[Codex CLI guide](agents/codex.md)** — upstream-sourced OpenAI Codex CLI setup.
- **[Gemini CLI guide](agents/gemini.md)** — upstream-sourced Gemini CLI setup.

## Guides

- **[Concept](concept.md)** — what Kelix is, the four Ralph invariants and how
  Kelix preserves them, verified-done, and why stateless beats clever
  orchestration.
- **[Quickstart](quickstart.md)** — install, `kelix init`, the verification
  gate, writing backlog tasks, running overnight, and reading the results.
- **[Planning](planning.md)** — plan-first flow (`GOAL.md` → `kelix plan` →
  promote → run), roadmap → phase → task hierarchy, STATE.md, lint, phase
  gate, waves, and when to stay on a flat backlog.
- **[Writing for the loop](writing-for-the-loop.md)** — the input contract:
  how to write backlog tasks and PRDs a fresh agent gets right the first
  time. Good input in, good output out.
- **[Kiro guide](kiro.md)** — deepest integration: headless adapter, spec→backlog
  import, the `.kiro/` steering/agent/hooks package, and MCP server registration.
- **[Cursor guide](agents/cursor.md)** — Kelix-verified Cursor CLI adapter,
  install, auth, and loop wiring.
- **[Claude Code guide](agents/claude.md)** — Claude Code CLI adapter and loop
  wiring (upstream-sourced; community corrections welcome).
- **[Codex CLI guide](agents/codex.md)** — OpenAI Codex CLI adapter and loop
  wiring (upstream-sourced; community corrections welcome).
- **[Gemini CLI guide](agents/gemini.md)** — Gemini CLI adapter and loop wiring
  (upstream-sourced; community corrections welcome).
- **[Memory & skills](memory-and-skills.md)** — the three memory layers,
  budgeted digest injection, retrospectives, and skill acquisition during the
  loop.
- **[Fleet mode](fleet.md)** — many role-specialized loops on one backlog,
  coordinating through claims, a mailbox, and shared skills.
- **[MCP server](mcp.md)** — driving Kelix by tool call: `kelix_run`,
  `kelix_status`, `kelix_memory`, `kelix_stop`.

## Reference

- **[Comparison](compare.md)** — honest comparison to plain Ralph, Claude Code
  and Codex alone, and GSD-style orchestrators; cites proof artifacts or reads
  "not measured — no receipt."
- **[Security model](SECURITY.md)** — the threat model (unattended agent +
  shell + prompt-injected repo content) and the mitigations that live in code.
  Read this before an unattended run.
- **[Prioritization rubric](prioritization.md)** — the backlog task format,
  selection order, priority bands, and the blocked-task protocol.

## Research notes

The design homework behind Kelix:

- **[The Ralph invariants](research/ralph-invariants.md)** — the four
  properties Kelix treats as non-negotiable, derived from the source posts.
- **[Kiro public surface](research/kiro-surface.md)** — every Kiro integration
  point Kelix uses, all public and documented.
- **[Prior art](research/prior-art.md)** — ralph-orchestrator, the official
  ralph-loop plugin, and Nous Research's Hermes Agent.
- **[GSD lessons](research/gsd-lessons.md)** — what Kelix's planning core
  (roadmap → phase → task, STATE.md spine, coverage gates, waves) adopts
  and rejects from GSD Core's phase loop.

## Project

Kelix is open source under Apache-2.0 and was built by its own loop. Source,
issues, and contributing guide live in the repository — see the
[README](https://github.com/serversorcerer/kelix) for the project overview.
