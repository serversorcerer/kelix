# Lessons from GSD Core (open-gsd/gsd-core)

GSD ("Git. Ship. Done.") is a context-engineering / spec-driven framework that
drives coding agents through a Discuss → Plan → Execute → Verify → Ship phase
loop, with all heavy work in fresh-context subagents and all state in files
under `.planning/`. Studied for Kalph's planning core; sources: repo README,
`docs/explanation/context-engineering.md`, `docs/explanation/the-phase-loop.md`.

## Where GSD and Kalph already agree

- **Fresh context is the mechanism, not a nicety.** GSD: "an executor that
  runs with 180k tokens of accumulated session history is a degraded
  executor." Kalph: every iteration is a fresh process. Same insight,
  arrived at independently from Ralph.
- **State lives in files, never in a conversation.** GSD's `.planning/` is
  Kalph's `.kalph/`. Both are git-versioned, human-readable, auditable.
- **Verification is a distinct step that checks intent, not just exit
  codes.** GSD's verifier checks requirement coverage; Kalph's runner
  re-runs the verify commands. GSD goes further (see below).

## What to steal (adapted to stateless loops)

1. **A navigation spine (`STATE.md`).** GSD: "when any workflow starts, it
   reads STATE.md to orient itself." Kalph's fresh agent currently orients
   by re-reading the whole backlog + git log every iteration — O(backlog)
   tokens and no notion of "where are we in the larger plan." A compact,
   runner-maintained state file makes orientation O(1): active milestone,
   active phase, current task, blockers, last verified commit. This is the
   "how to drive the car" file.
2. **Top-down hierarchy: milestone → phase → task.** GSD scopes milestones
   at product boundaries and phases at "the largest thing that can be
   safely executed in one loop." Kalph has only tasks; goals arrive
   pre-decomposed by the owner. Adding roadmap (milestones + requirement
   IDs) and phases (goal + owner decisions) lets an owner write intent
   once, top-down, and lets the loop decompose downward legibly.
3. **Decisions captured before planning (`CONTEXT.md` / Discuss).** GSD's
   Discuss step exists because "the planner guesses plausibly but wrongly"
   without it. Kalph equivalent: a per-phase decisions file the owner can
   fill in (or the loop proposes, owner edits) before decomposition — the
   same one-line-edit steering Kalph already favors.
4. **Requirement IDs and coverage-checked done.** GSD: "a phase is not done
   because execution finished without errors. It is done because what was
   built is what was planned, and what was planned is what was decided."
   Kalph's verified-done gates each task; a phase gate should check every
   REQ-ID maps to a verified task before the phase closes.
5. **Waves for parallelism.** GSD orders plans into dependency waves so
   parallel executors touch non-overlapping concerns. Kalph's fleet claims
   prevent two agents on one task but nothing groups tasks into safe
   parallel sets. Deps already exist in the backlog; waves are derivable.
6. **A light path for light work.** GSD's `/gsd-quick` exists because "the
   phase loop is overkill for renaming a variable." Kalph's flat backlog IS
   the quick path — the hierarchy must stay optional, activated only when a
   roadmap exists.

## What to reject (and why)

- **A long-lived orchestrator session.** GSD keeps a lean main session that
  spawns subagents and monitors its own context headroom via runtime
  lifecycle hooks. That is the one piece of GSD that lives in a process
  rather than a file — and per the Ralph invariants, Kalph replaces it
  with the loop itself: the runner is the orchestrator, and it holds no
  model context at all. No headroom heuristics needed when every iteration
  starts at zero.
- **Runtime-specific lifecycle hooks.** GSD registers per-runtime hooks
  (PreCompact/Stop/BeforeModel...) and admits the maintenance surface.
  Kalph's adapter boundary is a subprocess exit code — portable by
  construction.
- **Separate researcher/planner/plan-checker agent types in-core.** Kalph's
  fleet roles are already config data, not code. Planning is one iteration
  with a planning task pinned, not a new agent species.

## Design consequence for Kalph (built as milestone v0.2)

One new layer, three files, zero new processes:

```text
.kalph/roadmap.md            owner intent: milestones, phases, REQ-IDs
.kalph/phases/<id>/CONTEXT.md  owner decisions for one phase (discuss output)
.kalph/STATE.md              runner-maintained spine: where are we now
.kalph/backlog.md            unchanged, but tasks may carry phase:/req: fields
```

The loop reads STATE.md first (cheap orientation), the active phase's
CONTEXT.md second (decisions), then selects from the backlog as today. The
phase gate closes a phase only when its REQ coverage is verified. Everything
stays plain Markdown a human can edit with one line.
