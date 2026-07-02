# The Ralph Invariants

Source: Geoffrey Huntley, ["Ralph Wiggum as a software engineer"](https://ghuntley.com/ralph/)
and ["everything is a ralph loop"](https://ghuntley.com/loop/).

Ralph in its purest form:

```bash
while :; do cat PROMPT.md | agent ; done
```

Kelix treats the following four properties as **invariants**. Every feature must
preserve them; any feature that cannot be built without breaking one does not
ship.

## 1. Static prompt

The prompt fed to the agent is the same every iteration. It is not assembled
from conversation history and it is not mutated by the agent mid-run. Tuning
the prompt is an *operator* act between runs ("erecting signs"), not an agent
act during one.

*Kelix nuance:* Kelix injects memory digests and skills into the prompt as
**data blocks with fixed slots**. The prompt template is static; only the
file-derived data inside clearly delimited slots varies. The agent is told the
blocks are reference data, not instructions.

## 2. Fresh context per iteration

Every iteration is a brand-new agent process with an empty context window.
Nothing survives in the model's head between iterations. This is what makes the
loop deterministic-ish and cheap: no context rot, no compounding confusion, and
a wrong turn only costs one iteration.

Huntley: use as little of the context window as possible; the primary context
acts as a scheduler and expensive work goes to subagents. Kelix honors this by
budgeting every injected byte (plan slice, memory digest, skills) with hard
caps.

## 3. Deterministic stop sentinel

The loop stops for mechanical, checkable reasons only:

- a completion sentinel emitted by the agent (`KELIX COMPLETE` in Kelix),
- an iteration cap (`--max-iterations`),
- a circuit breaker (N consecutive failures / no-diff iterations),
- an explicit kill switch.

The loop never stops because the agent "feels done." Conversely, the agent
cannot keep the loop alive by refusing to exit — each iteration process exits
unconditionally; continuation is the *runner's* decision.

## 4. Externalized state

All state lives in files and git history: the plan/backlog, the memory, the
logs, the coordination data. The repo *is* the database. Anyone (human or the
next iteration) can reconstruct exactly where the run is by reading files.
Corollaries:

- every iteration ends with a working, committed state;
- anything worth remembering must be written to a file before the process
  exits, because the process's memory is discarded;
- coordination between agents (fleet mode) is expressed as "write a file,
  commit; another agent reads it" — never RPC.

## Supporting observations from the source posts (not invariants, but encoded in Kelix)

- **One task per loop.** Relaxable when things go well, the first thing to
  narrow when they don't. Kelix never relaxes it: decompose instead.
- **Backpressure is engineering.** Tests, type checkers, linters, scanners —
  anything that mechanically rejects bad generations. Kelix makes verification
  a loop responsibility (`verify` commands in config), not an agent promise.
- **Don't assume not-implemented.** Search before writing; a common Ralph
  failure is duplicate implementations. Encoded in Kelix's iteration prompt.
- **Capture the "why" in the moment.** Notes for future iterations (test
  docstrings, plan annotations) substitute for the missing memory. Kelix
  formalizes this as episodic memory and skills.
- **Let Ralph take himself to university.** The AGENT.md self-improvement rule
  becomes Kelix's skill acquisition: operational learnings are distilled to
  files that future iterations load.
- **You will wake up to a broken codebase sometimes.** Mitigations: per-run
  branch/worktree isolation, auto-checkpoint, circuit breaker with a written
  diagnosis instead of token burn.
- **Monolith over multi-agent chatter.** A single loop, one repo, one task per
  iteration. Kelix's fleet mode composes *independent* loops through files and
  git, precisely to avoid non-deterministic microservices ("a red hot mess").
