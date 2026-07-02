# Concept: what Kelix is and why

Kelix is the [Ralph loop](https://ghuntley.com/ralph/), rebuilt for
[Kiro](https://kiro.dev). Ralph in its purest form is:

```bash
while :; do cat PROMPT.md | agent ; done
```

A coding agent, run in a loop against a static prompt. Every iteration is a
fresh, stateless process; all state lives in files and git history; the loop
wins through repetition, not cleverness. Kelix keeps that core intact and adds
what plain Ralph lacks: persistent memory, self-improvement from loop outcomes,
legible prioritization, first-class Kiro integration, and a file-coordinated
fleet mode.

## The four invariants

Kelix treats four properties of the original loop as **invariants** (full
derivation in [research/ralph-invariants.md](research/ralph-invariants.md)).
Every feature must preserve them; any feature that cannot be built without
breaking one does not ship.

### 1. Static prompt

The prompt fed to the agent is the same every iteration. It is never assembled
from conversation history and never mutated by the agent mid-run. Tuning the
prompt is an operator act between runs, not an agent act during one.

*How Kelix preserves it:* the template (`.kelix/prompts/iteration.md`, or the
built-in default in `src/kelix/prompt.py`) is loaded **once per run**. Memory
digests, skills, and fleet mailbox notes are injected as file-derived data into
fixed, clearly delimited slots (`<episodes>`, `<skills>`, `<mailbox>`), each
with a hard character budget. The template tells the agent those blocks are
reference data, not instructions.

### 2. Fresh context per iteration

Every iteration is a brand-new agent process with an empty context window.
Nothing survives in the model's head between iterations. No context rot, no
compounding confusion; a wrong turn costs exactly one iteration.

*How Kelix preserves it:* the default adapter shells out to
`kiro-cli chat --no-interactive` — a one-shot process that prints its response
and exits. Every injected byte (episode digest, skills, mailbox) is capped, so
the context stays small and the primary window acts as a scheduler.

### 3. Deterministic stop sentinel

The loop stops for mechanical, checkable reasons only:

- the completion sentinel — the agent prints `KELIX COMPLETE` when every
  backlog task is `done` or `blocked` with a diagnosis;
- the iteration cap (`--max-iterations`, default 25);
- the circuit breaker — N consecutive failure iterations
  (`circuit_breaker_threshold`, default 3) stop the run and write a
  `diagnosis.md` instead of burning tokens;
- the kill switch — `kelix stop` writes `.kelix/STOP`, and runs halt before
  their next iteration.

The loop never stops because the agent "feels done" — and the agent cannot
keep the loop alive by refusing to exit, because each iteration process exits
unconditionally and continuation is the runner's decision.

### 4. Externalized state

All state lives in files and git history: the backlog
(`.kelix/backlog.md`), the memory (`.kelix/memory/`), transcripts and run
records (`.kelix/runs/<id>/`), and fleet coordination (`.kelix/fleet/`). The
repo *is* the database. Anyone — a human reviewer or the next iteration — can
reconstruct exactly where a run is by reading files. Fleet agents coordinate
by writing files, never by RPC.

## Verified-done

Plain Ralph trusts the agent to say when it is finished. Kelix does not. The
runner — not the agent — re-runs the commands you configure in
`.kelix/kelix.toml`:

```toml
[verify]
commands = ["pytest -q", "ruff check ."]
```

After every iteration, all verify commands must exit 0 for the work to count.
A failed verification marks the iteration as a failure and the task stays at
the top of the queue. Even the completion sentinel is subject to this rule: a
`KELIX COMPLETE` printed while verification is red is **ignored** and counted
as a failure iteration. The agent said "done", but done means verified-done.

This is Huntley's "backpressure is engineering" observation made structural:
tests, linters, and type checkers mechanically reject bad generations, and
Kelix makes running them a loop responsibility rather than an agent promise.

## Why stateless beats clever orchestration

The tempting alternative to a stateless loop is a long-lived orchestrator: a
planner agent with accumulated context delegating to workers over a message
bus. Kelix deliberately rejects that design.

- **Context rot is the dominant failure mode of long agent sessions.** A
  fresh process per iteration means confusion never compounds. The worst case
  of any single bad decision is one wasted iteration, fully recoverable from
  git.
- **Files are auditable; conversations are not.** Because every decision is
  externalized — a `RATIONALE:` line per iteration, an episode record, a
  committed diff — a reviewer can audit an overnight run in minutes.
- **Repetition with backpressure converges.** The loop does not need to plan
  perfectly; it needs to try, get mechanically rejected when wrong, and try
  again with the failure recorded in episodic memory so the next fresh agent
  does not repeat the dead end.
- **Multi-agent chatter is a non-deterministic mess.** Kelix's fleet mode
  composes *independent* stateless loops through atomic claim files, a
  mailbox, and git — never direct agent-to-agent communication. Each fleet
  agent is just the same simple loop with a role.

The intelligence in the system is not in orchestration machinery. It is in the
model, the verification gate, and the files the loop leaves behind for its
future selves.
