# Kelix documentation

**The [Ralph loop](https://ghuntley.com/ralph/), rebuilt for
[Kiro](https://kiro.dev).**

Kelix runs a coding agent in a loop against a static prompt: every iteration
is a fresh, stateless agent process; all state lives in files and git history;
the loop wins through repetition, not cleverness. Kelix adds persistent
memory, self-improvement, legible prioritization, first-class Kiro
integration, and a file-coordinated fleet mode — so you can write a spec once
and wake up to reviewable PRs.

```bash
pipx install kelix
cd your-repo && kelix init
kelix run --max-iterations 25 --pr
```

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
- **[Kiro guide](kiro.md)** — the headless adapter, spec→backlog import, the
  `.kiro/` steering/agent/hooks package, and registering the MCP server.
- **[Memory & skills](memory-and-skills.md)** — the three memory layers,
  budgeted digest injection, retrospectives, and skill acquisition during the
  loop.
- **[Fleet mode](fleet.md)** — many role-specialized loops on one backlog,
  coordinating through claims, a mailbox, and shared skills.
- **[MCP server](mcp.md)** — driving Kelix by tool call: `kelix_run`,
  `kelix_status`, `kelix_memory`, `kelix_stop`.

## Reference

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
