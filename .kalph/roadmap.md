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

### Phase P-ONRAMP — the owner's planning onramp

Outcome: a new user goes from "goal in my head" to "a loop-ready roadmap +
backlog I have reviewed" in one command. Rationale (owner directive): the
most important thing someone needs when using this application is a plan;
today `kalph init` hands them a one-line template and a doc to study —
evidence from the proof runs shows output quality tracked backlog quality
exactly (12/12 verified on precise tasks; slop would have produced slop).

- REQ-O1: `kalph plan "<goal>"` (or `--goal-file GOAL.md`) runs ONE agent
  iteration whose only deliverable is a draft plan: `.kalph/roadmap.md`
  (milestone, phases, REQ-IDs) and backlog tasks written to the
  writing-for-the-loop standard, all marked `status: proposed`. It never
  implements anything; the owner promotes tasks to `ready` by editing —
  the loop cannot start work the owner has not reviewed.
- REQ-O2: the draft is machine-validated before it is accepted: roadmap
  parses, every task line parses, every task has `details:` with a
  testable acceptance, deps are acyclic and reference real ids. A draft
  failing validation is rejected with the specific errors (agent gets one
  retry, then the errors are written for the owner).
- REQ-O3: `kalph lint` checks any backlog against the input contract and
  reports slop: tasks with no details, no acceptance signal, unfalsifiable
  words ("better", "best practices", "improve" without a metric), >1
  deliverable per task, dangling deps. Exit non-zero on findings so it can
  gate CI.
- REQ-O4: `kalph init` prints the planning path first ("no plan yet? run:
  kalph plan ...") and seeds a GOAL.md template; quickstart docs lead with
  plan-first flow.

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

### Phase P-HARDEN — lessons from the v0.1 proof runs

Outcome: the three weaknesses the dogfood/fleet runs exposed are fixed in
code (evidence: docs/proof/ logs).

- REQ-H1: rationale is never silently lost. 3 of 12 dogfood iterations and
  1 fleet iteration logged "(no rationale)" because the agent skipped the
  RATIONALE: line. Fallback: derive it from the iteration's commit subject
  (task-id prefix); only if both are absent does the episode say so, and
  that now counts as a lint-style warning in the retrospective.
- REQ-H2: hung agents end themselves. The fleet-session-2 verifier finished
  its work but its process idled ~20 min until killed by hand (D13). Add an
  output-inactivity timeout to adapters (no stdout/stderr bytes for N
  seconds -> terminate, default 300s, configurable) alongside the existing
  hard timeout; the iteration is recorded with its real exit accounting.
- REQ-H3: role fidelity is measurable. In fleet session 1 the verifier
  claimed a builder task (allowed by design — roles prefer, not restrict —
  but invisible). The fleet retrospective now reports role-match per
  iteration (task kind vs. agent role) so owners can see drift.

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
