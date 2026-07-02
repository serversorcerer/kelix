# Kalph roadmap

Owner intent, top-down. Milestones are releasable increments; phases are the
largest unit safely executable as one run; REQ-IDs are the coverage contract —
a phase closes only when every REQ maps to a verified-done task. Loops: read
`.kalph/STATE.md` first for where we are, this file for where we're going.

## Milestone v0.2 — Planning Core ("teach the loops to drive")

Goal: a fresh, stateless iteration orients itself in O(1) — it knows the
mission, the active phase, the decisions already made, and the one task it
should do — without re-deriving anything. Lessons adopted from GSD Core
(docs/research/gsd-lessons.md): navigation spine, milestone→phase→task
hierarchy, decisions-before-planning, requirement coverage, dependency waves.
Rejected from GSD: long-lived orchestrator sessions, runtime lifecycle hooks.

Non-goals for v0.2: no new agent types, no changes to the Ralph invariants,
no mandatory ceremony — a repo with no roadmap must work exactly as today
(flat backlog is the quick path).

### Phase P-SPINE — the state spine

Outcome: every iteration starts by reading one small runner-maintained file
that says exactly where the project is.

- REQ-S1: `.kalph/STATE.md` exists with a fixed, documented schema: active
  milestone, active phase, current/last task, last verified commit, open
  blockers, counts (tasks done/total for the active phase).
- REQ-S2: the runner (not the agent) rewrites STATE.md at run start, after
  every iteration, and at run end; it is bookkeeping-excluded from
  auto-checkpoint like other runner-owned files but IS committed with task
  commits so history shows state evolution.
- REQ-S3: the prompt's first data slot is STATE.md (budgeted); the loop
  contract instructs the agent to orient from it before reading anything else.

### Phase P-INTENT — top-down intent

Outcome: an owner writes goals once, top-down; loops decompose downward.

- REQ-I1: `.kalph/roadmap.md` (this file's format) is parsed: milestones,
  phases, REQ-IDs with descriptions.
- REQ-I2: each phase may have `.kalph/phases/<phase-id>/CONTEXT.md` holding
  owner decisions (GSD's Discuss artifact); when the active phase has one,
  it is injected as a budgeted data slot.
- REQ-I3: backlog tasks accept optional `phase: <id>` and `req: <REQ-ID>`
  fields; selection prefers tasks in the active phase; tasks without these
  fields behave exactly as today.

### Phase P-GATE — coverage-gated done

Outcome: "done" for a phase means every requirement is covered by a
verified-done task — GSD's insight that finishing without errors is not the
same as building what was decided.

- REQ-G1: a phase-gate check reports, per REQ-ID of the active phase:
  covered (verified-done task references it), in-progress, or uncovered.
- REQ-G2: the runner refuses to advance STATE.md to the next phase while any
  REQ is uncovered; uncovered REQs are surfaced in the retrospective.
- REQ-G3: `kalph status` renders the phase gate (REQ coverage table) from
  files alone.

### Phase P-WAVES — safe parallelism

Outcome: fleet agents work in dependency waves so parallel work cannot
collide on overlapping concerns.

- REQ-W1: waves are derived from backlog `deps:` (wave N = tasks whose deps
  are all in waves < N); no new syntax.
- REQ-W2: the fleet claim hook only offers tasks from the earliest
  incomplete wave; claims across waves are refused.
- REQ-W3: wave assignment is visible in `kalph status`.

### Phase P-PROOF — docs and self-referential proof

Outcome: the planning core is documented and proven by driving its own build.

- REQ-P1: `docs/planning.md` explains the hierarchy (roadmap → phase →
  task), the STATE.md spine, the gate, and waves — following
  docs/writing-for-the-loop.md style: precise, no ceremony for small work.
- REQ-P2: `kalph init` offers a roadmap template; existing repos without a
  roadmap are untouched.
- REQ-P3: at least the last phase of v0.2 is built by a Kalph run that
  orients via STATE.md and closes through the phase gate (evidence in
  transcripts + DECISIONS.md).
