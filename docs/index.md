# Kelix documentation

**I want to ship something unattended.** Write a well-specified goal, point any
headless coding agent at it, walk away, and come back to verified commits —
each gated by your repo's own test and lint commands, not agent promises.

## Start here

Pick the link that matches what you need right now (five links, no side quests):

1. **[Quickstart](quickstart.md)** — install, `kelix init`, plan, run, read verified
   commits on the run branch.
2. **[Writing for the loop](writing-for-the-loop.md)** — the input contract: backlog
   tasks and goals a fresh agent gets right the first time.
3. **[Concept](concept.md)** — what Kelix is, the four Ralph invariants, verified-done,
   and why stateless beats clever orchestration.
4. **[Security model](SECURITY.md)** — threat model for unattended runs; read this
   before you leave the loop alone overnight.
5. **[Dogfood proof](proof/final-report.md)** — receipt for the value sentence:
   [12/12 tasks verified-done in 12 iterations](proof/final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd)
   with reproduction commands.

**The loop that climbs.** Ralph runs in circles; Kelix comes back higher. Kelix
runs any headless coding agent in a loop against a static prompt — **Claude Code**,
**Codex CLI**, **Cursor**, **Gemini CLI**, or your own CLI adapter — with persistent
memory, legible prioritization, and optional fleet mode when one agent is not enough.

```bash
pipx install kelix
cd your-repo && kelix init
kelix plan --goal-file GOAL.md   # optional: structured plan-first path
kelix run --max-iterations 25
```

## Agents

Kelix is agent-agnostic: configure one adapter in `.kelix/kelix.toml` and the
loop stays the same.

- **[Kiro guide](kiro.md)** — deepest integration: headless adapter, spec→backlog
  import, and the `.kiro/` steering/agent/hooks package.
- **[Cursor guide](agents/cursor.md)** — Kelix-verified headless Cursor CLI wiring.
- **[Claude Code guide](agents/claude.md)** — upstream-sourced Claude Code CLI setup.
- **[Codex CLI guide](agents/codex.md)** — upstream-sourced OpenAI Codex CLI setup.
- **[Gemini CLI guide](agents/gemini.md)** — upstream-sourced Gemini CLI setup.

## More guides

- **[Planning](planning.md)** — plan-first flow (`GOAL.md` → `kelix plan` → promote →
  run), roadmap → phase → task hierarchy, STATE.md, lint, phase gate, and waves.
- **[Memory & skills](memory-and-skills.md)** — episode digest, retrospectives, context
  compiler, loop-metrics rollup, and skill distillation.
- **[Fleet mode](fleet.md)** — many role-specialized loops on one backlog, coordinating
  through claims and a mailbox.
- **[MCP server](mcp.md)** — drive Kelix by tool call (`kelix_run`, `kelix_status`,
  `kelix_memory`, `kelix_stop`) from MCP-capable agents.
- **[Prioritization rubric](prioritization.md)** — backlog task format, selection
  order, priority bands, and the blocked-task protocol.

## Reference

- **[Comparison](compare.md)** — honest comparison to plain Ralph, Claude Code and
  Codex alone, and GSD-style orchestrators; cites proof artifacts or reads
  "not measured — no receipt."
- **[Value ledger](value-ledger.md)** — module-by-module SHARPEN / KEEP / SCRAP verdicts
  with receipts; owner veto before execution phases.

## Research notes

The design homework behind Kelix:

- **[The Ralph invariants](research/ralph-invariants.md)** — the four properties Kelix
  treats as non-negotiable, derived from the source posts.
- **[Kiro public surface](research/kiro-surface.md)** — every Kiro integration point
  Kelix uses, all public and documented.
- **[Prior art](research/prior-art.md)** — ralph-orchestrator, the official ralph-loop
  plugin, and Nous Research's Hermes Agent.
- **[GSD lessons](research/gsd-lessons.md)** — what Kelix's planning core adopts and
  rejects from GSD Core's phase loop.

## Project

Kelix is open source under Apache-2.0 and was built by its own loop. Source,
issues, and contributing guide live in the repository — see the
[README](https://github.com/serversorcerer/kelix) for the project overview.

---

Every page linked from this index maps to a **SHARPEN** or **KEEP** row in
[docs/value-ledger.md](value-ledger.md). Doc pages for scrapped modules (`sync/`,
`pr`) were removed with backlog tasks KV2–KV3; nothing here points at a SCRAP-only
surface.
