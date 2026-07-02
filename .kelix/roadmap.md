# Kelix roadmap

Owner intent, top-down. Milestones are releasable increments; phases are the
largest unit safely executable as one run; REQ-IDs are the coverage contract —
a phase closes only when every REQ maps to a verified-done task. Loops: read
`.kelix/STATE.md` first for where we are, this file for where we're going.

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

Owner directives in force (D16): MCP and skills are FROZEN — keep working,
keep tested, zero new investment. Context quality carries 50% of the value:
the prompt's context half is curated by relevance, not recency, and is
auditable per iteration. Planning interviews the owner instead of guessing.
Audacity is the point — v0.3 below is the boundary push, not more plumbing.

### Phase P-SPINE — the state spine

Outcome: every iteration starts by reading one small runner-maintained file
that says exactly where the project is.

- REQ-S1: `.kelix/STATE.md` exists with a fixed, documented schema: active
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

- REQ-I1: `.kelix/roadmap.md` (this file's format) is parsed: milestones,
  phases, REQ-IDs with descriptions.
- REQ-I2: each phase may have `.kelix/phases/<phase-id>/CONTEXT.md` holding
  owner decisions (GSD's Discuss artifact); when the active phase has one,
  it is injected as a budgeted data slot.
- REQ-I3: backlog tasks accept optional `phase: <id>` and `req: <REQ-ID>`
  fields; selection prefers tasks in the active phase; tasks without these
  fields behave exactly as today.

### Phase P-ONRAMP — the owner's planning onramp

Outcome: a new user goes from "goal in my head" to "a loop-ready roadmap +
backlog I have reviewed" in one command. Rationale (owner directive): the
most important thing someone needs when using this application is a plan;
today `kelix init` hands them a one-line template and a doc to study —
evidence from the proof runs shows output quality tracked backlog quality
exactly (12/12 verified on precise tasks; slop would have produced slop).

- REQ-O1: `kelix plan "<goal>"` (or `--goal-file GOAL.md`) runs ONE agent
  iteration whose only deliverable is a draft plan: `.kelix/roadmap.md`
  (milestone, phases, REQ-IDs) and backlog tasks written to the
  writing-for-the-loop standard, all marked `status: proposed`. It never
  implements anything; the owner promotes tasks to `ready` by editing —
  the loop cannot start work the owner has not reviewed.
- REQ-O1b: planning interviews the owner before drafting (D16 directive 1).
  The planning iteration first emits structured questions (decision point,
  2-4 options, its recommendation). With a TTY, `kelix plan` asks them live
  and feeds answers back; without one, it writes
  `.kelix/phases/<id>/QUESTIONS.md` and exits; the owner answers by editing
  and re-runs `kelix plan` to resume. Answers land in the phase CONTEXT.md
  — decisions captured once, then injected every iteration.
- REQ-O2: the draft is machine-validated before it is accepted: roadmap
  parses, every task line parses, every task has `details:` with a
  testable acceptance, deps are acyclic and reference real ids. A draft
  failing validation is rejected with the specific errors (agent gets one
  retry, then the errors are written for the owner).
- REQ-O3: `kelix lint` checks any backlog against the input contract and
  reports slop: tasks with no details, no acceptance signal, unfalsifiable
  words ("better", "best practices", "improve" without a metric), >1
  deliverable per task, dangling deps. Exit non-zero on findings so it can
  gate CI.
- REQ-O4: `kelix init` prints the planning path first ("no plan yet? run:
  kelix plan ...") and seeds a GOAL.md template; quickstart docs lead with
  plan-first flow.

### Phase P-GATE — coverage-gated done

Outcome: "done" for a phase means every requirement is covered by a
verified-done task — GSD's insight that finishing without errors is not the
same as building what was decided.

- REQ-G1: a phase-gate check reports, per REQ-ID of the active phase:
  covered (verified-done task references it), in-progress, or uncovered.
- REQ-G2: the runner refuses to advance STATE.md to the next phase while any
  REQ is uncovered; uncovered REQs are surfaced in the retrospective.
- REQ-G3: `kelix status` renders the phase gate (REQ coverage table) from
  files alone.

### Phase P-WAVES — safe parallelism

Outcome: fleet agents work in dependency waves so parallel work cannot
collide on overlapping concerns.

- REQ-W1: waves are derived from backlog `deps:` (wave N = tasks whose deps
  are all in waves < N); no new syntax.
- REQ-W2: the fleet claim hook only offers tasks from the earliest
  incomplete wave; claims across waves are refused.
- REQ-W3: wave assignment is visible in `kelix status`.

### Phase P-CONTEXT — the context compiler (50% of the value)

Outcome: the prompt's context half is engineered, not accumulated. Today the
loop injects recency-ordered digests (last N episodes, first N chars of
memory) — cheap but dumb. The compiler chooses what a fresh agent needs for
THIS task and proves it chose well. MCP/skills stay frozen (D16); the effort
goes here instead.

- REQ-C1: a context budget split is configurable and defaults to 50% of
  prompt chars for curated context (state, phase decisions, task-relevant
  memory, task-relevant code excerpts), 50% for the static contract.
- REQ-C2: relevance beats recency: memory entries and episode records are
  selected by lexical overlap with the active task's title/details (stdlib
  scoring, no embeddings, no network), not by timestamp; ties break to
  recency. Skills selection uses the same scorer (no new skill features —
  selection only).
- REQ-C3: every iteration writes a context manifest
  (`.kelix/runs/<id>/context-<n>.json`): what was injected, from where, how
  many chars, and why (score). Context quality becomes auditable the same
  way decisions already are.
- REQ-C4: a context regression test proves the compiler beats recency: a
  fixture repo where the relevant gotcha is old and the recent episodes are
  noise; the compiled prompt must contain the gotcha.

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
- REQ-P2: `kelix init` offers a roadmap template; existing repos without a
  roadmap are untouched.
- REQ-P3: at least the last phase of v0.2 is built by a Kelix run that
  orients via STATE.md and closes through the phase gate (evidence in
  transcripts + DECISIONS.md).

## Milestone v0.3 — The Self-Tuning Loop (the audacity milestone)

Goal: Kelix doesn't just execute the loop — it improves the loop. Anyone can
build an app; the boundary worth pushing is a system that measurably gets
better at building because it studies its own iterations. Everything stays
inside the safety model: Kelix proposes changes to itself as reviewable
diffs; it NEVER self-applies them.

Sketch (decomposed via `kelix plan` interviewing the owner once P-ONRAMP
ships — the onramp's first real use is planning the milestone after it):

- Phase T-METRICS: an outcome ledger per iteration — verified rate, retry
  count, tokens/duration, circuit-breaker causes, lint findings on
  agent-written backlog edits — aggregated across runs into
  `.kelix/memory/loop-metrics.json` (runner-owned, human-readable).
- Phase T-DIAGNOSE: a periodic self-review iteration reads the ledger and
  transcripts of failed iterations and writes a diagnosis: which prompt
  sections, policies, or budgets correlate with failure.
- Phase T-PROPOSE: Kelix opens a PR against its own prompt template,
  denylist, budgets, or selection weights, with the metric evidence in the
  PR body and a predicted improvement. Owner merges or closes — the same
  gate as any code change. A merged proposal's prediction is checked
  against the next runs' ledger and the result is recorded (the loop grades
  its own homework).
- Phase T-SKILLS: skill learning that actually fires (D17). Evidence: in
  ~20 live v0.1 iterations the prompt's acquisition rule produced zero
  skills. Fix the mechanism, not the wording: at retrospective time the
  runner runs a distillation pass over the run's verified episodes (which
  tasks took retries, what unblocked them) and writes candidate skills as
  `proposed` artifacts the owner can keep or delete; the ledger tracks
  skill injections (via the context manifest) vs. task outcomes so a
  skill's efficacy is a number, not a feeling. Plumbing stays frozen —
  same format, same directories.
- Staged next: autonomous roadmapping (v0.5 — Kelix drafts the next
  milestone from repo observation; owner edits instead of authors), then
  self-reviewing fleet chains (v0.6 — review/fix/re-verify cycles between
  agents until merge-ready, owner merges).

## Milestone v0.4 — Kelix for everyone (agent-agnostic, audacious, honest)

Goal: reposition Kelix as **the loop that climbs, for any coding agent** —
Kiro remains the deepest first-class integration, not the product identity.
Voice everywhere: audacity backed by evidence, never hype without receipts.
The `cmd` adapter contract stays: spawn CLI, pass prompt, read exit code +
transcript — no per-agent SDKs or streaming parsers.

Non-goals: no new runtime dependencies (stdlib-only core); no weakening of
Kiro integration, security rails, or the verification gate; no benchmark
numbers we did not run or cannot cite.

Owner decisions captured in `.kelix/phases/*/CONTEXT.md` for this milestone.

### Phase P-REPOS — Reposition (de-Kiro the identity, keep the integration)

Outcome: README, docs/index.md, pyproject description, CLI help, and MCP
server description lead with agent-agnostic framing; Kiro is "deepest
integration," prominently linked; docs/kiro.md is untouched in depth.

- REQ-R1: README.md first 20 lines do not lead with Kiro; new framing names
  Claude Code, Codex CLI, Cursor, Gemini CLI, and Kiro (deepest integration).
- REQ-R2: docs/index.md, pyproject.toml description/keywords, CLI help text
  (including CONFIG_TEMPLATE comment), and mcp_server module description match
  the agent-agnostic voice; Kiro linked as flagship integration.
- REQ-R3: docs/kiro.md content and examples unchanged in capability; all
  existing tests pass with no test edits required for this phase.

### Phase P-AGENT — Named adapters + a guide per agent

Outcome: named adapter presets resolve to the existing `cmd` adapter with
verified or documented invocation templates; each preset has a comparable
guide; `kelix init` wires first-run config with zero guesswork.

- REQ-A1: presets `claude`, `codex`, `cursor`, `gemini` resolve to `cmd` with
  the correct command template; `kiro`, `cmd`, `mock` behavior unchanged.
- REQ-A2: docs/agents/{claude,codex,cursor,gemini}.md follow docs/kiro.md
  heading parity for loop wiring (install, auth, kelix.toml, worked example,
  quirks, troubleshooting); cursor guide labels Kelix-verified invocations;
  others label upstream-sourced, community-feedback welcome.
- REQ-A3: `kelix init` on TTY prompts with a numbered agent list; on non-TTY
  requires `--agent <name>`; writes the matching `[agent]` block to kelix.toml.
- REQ-A4: `kelix run` with adapter `claude` and a stub binary on PATH completes
  one mock-style iteration in tests; each guide's TOML snippet parses via
  `load_config`; CI exercises every guide TOML snippet (doctest-style).

### Phase P-AUDIT — Audacity audit (every feature owns the claim)

Outcome: feature docs and CLI surfaces answer "what does this let one person
do that they couldn't before?" — one audacious sentence, then evidence.
Sequencing: feature docs first, CLI strings second, README/index audacity
pass last (after P-REPOS structural reposition).

- REQ-U1: docs/proof/* renames Kalph residue to Kelix; docs/proof/final-report.md
  gains a one-line provenance note at the top.
- REQ-U2: each feature page (concept, memory-and-skills, prioritization,
  planning, fleet, SECURITY, mcp, writing-for-the-loop) opens with a capability
  claim followed by a link to proof (test, docs/proof artifact, or reproducible
  command).
- REQ-U3: CLI surfaces in cli.py use art.say() theming; run-complete message
  states what was verified, not just "done."
- REQ-U4: README.md and docs/index.md receive a final audacity pass (voice,
  not structural reposition — that is REQ-R1/R2).

### Phase P-COMPARE — Honest comparison page

Outcome: docs/compare.md compares Kelix vs plain Ralph, vs single-agent CLIs,
vs long-lived orchestrators on measurable axes only; weakness rows are explicit;
every number cites a receipt or reads "not measured — no receipt."

- REQ-CM1: docs/compare.md exists with cited rows for axes where proof exists;
  missing axes marked "not measured — no receipt"; at least two rows where
  Kelix loses (single-iteration latency, IDE pairing affordances, adapter
  hang/timeout wart per D13).
- REQ-CM2: compare.md linked from README and docs/index.md; zero uncited numbers.

### Phase P-GOLD — First-contact spec gate (gold in, diamonds out)

Outcome: the loop refuses to burn tokens on slop at first contact; owner can
always bypass with `--force` (spec gate only, never git safety).

- REQ-GD1: `kelix run` on a backlog whose `status: ready` tasks fail lint stops
  before iteration 1 with actionable output (good/bad example inline); well-
  specified backlog proceeds; `--force` skips the spec gate only.
- REQ-GD2: `kelix plan` interview asks at least one acceptance-criteria question
  per phase; rubric reuses docs/writing-for-the-loop rules.
- REQ-GD3: GOAL.md template and lint gate messages carry the canon tagline once:
  "Gold in, diamonds out." (good/slop demoted to body examples in writing-for-the-loop).

## Milestone V — The value cut (ship Kelix)

Goal: one honest pass before release — keep what demonstrably creates value,
sharpen it, scrap what doesn't. The measure of every decision is the same
question the user will ask: "what did the agent give me that I couldn't get
without it?" The value sentence to protect: **you write a well-specified goal,
walk away, and come back to verified commits.** Sequencing: complete v0.2
(PC7–PC23), then v0.3, then v0.4, then this milestone. Owner decisions for
this milestone live in `.kelix/phases/V-CUT/CONTEXT.md`.

Non-goals: no new features; do not weaken the verification gate, security
rails, or worktree isolation; no rewrites for elegance; no compat shims,
deprecation warnings, or feature flags for scrapped code — git history is the
attic.

### Phase V-LEDGER — The value ledger (evidence before opinions)

Outcome: every feature/module is judged from receipts, not sentiment; the owner
can veto any row by editing the ledger before execution phases run.

- REQ-VL1: `docs/value-ledger.md` exists with one row per feature/module
  (loop, verify, plan+interview, lint, state/roadmap/backlog, memory, skills,
  fleet, claims, mcp_server, sync/, pr, kiro, security, adapters, art).
  Columns: lines of code, receipt (proof artifact / test / real run path, or
  "none"), verdict (SHARPEN | KEEP | SCRAP).
- REQ-VL2: the decision rule is applied without sentiment: SHARPEN = receipt
  AND on the critical path of the value sentence; KEEP = receipt but off the
  critical path (freeze — no new code/docs); SCRAP = no receipt.
- REQ-VL3: every SCRAP verdict names the backlog task id that will delete it;
  known owner SCRAPs (sync/, pr.py) are documented as SCRAP pending KV2/KV3.

### Phase V-SHARPEN — Double down on what's working

Outcome: the verification gate, plan interview, circuit breaker, lint gate,
and fleet mode produce receipt-grade user-facing output — the user sees what
was verified, decided, or blocked and knows the next move in one read.

- REQ-VS1: run-complete message names each verify command, its exit status,
  and the commits it blessed — not bare "done."
- REQ-VS2: plan interview emits at most 7 questions; each is a decision
  (2–4 options + recommendation), never open-ended; every answer lands in
  the phase CONTEXT.md.
- REQ-VS3: when the circuit breaker fires, the message names the failing
  condition, the task id, and the concrete fix (what to change in backlog or
  repo).
- REQ-VS4: when lint or the run spec-gate fires, each finding names task id,
  rule, file/line where applicable, and a one-line fix.
- REQ-VS5: fleet run-complete and retrospective messaging match REQ-VS1
  receipt style (per-agent verified commits, claim outcomes).

### Phase V-SIMPLE — Cut the surface, not the power

Outcome: a new user reaches their first verified commit via init → plan → run
only; secondary ops (lint, status, stop) stay documented but out of quickstart;
config and docs fit on one screen; scrapped features leave no dangling CLI,
config, or doc pages.

- REQ-VM1: CLI subcommands are audited against the ledger; scrapped features
  (`kelix sync`, `--pr`, mcp if SCRAP) are removed; happy path is init, plan,
  run; lint, status, stop remain as documented secondary ops.
- REQ-VM2: `kelix.toml` shipped template is ≤ 25 lines with comments; keys
  nobody sets in proof runs, docs, or test fixtures are removed or defaulted
  silently.
- REQ-VM3: `docs/index.md` routes by user intent ("I want to ship X
  unattended") in five links or fewer; every remaining doc page maps to a
  SHARPEN or KEEP ledger row.
- REQ-VM4: `docs/quickstart.md` documents init → plan → run → verified commits
  with a measured step count and no side quests (no fleet/pr/sync in the
  happy path).

### Phase V-PROOF — The value demo is the release gate

Outcome: one cold scripted run on a minimal fresh sample repo proves the value
sentence end-to-end; README leads with the real transcript, not a synthetic
example.

- REQ-VP1: a new minimal sample repo (stdlib toy project, 3–5 tasks, no
  fleet/pr/sync) lives under `samples/value-demo/` with its own GOAL and
  reproducible run script.
- REQ-VP2: `docs/proof/value-demo.md` captures the full transcript (goal in,
  interview, promote, run, verified commits out) with wall-clock time and
  iteration count; commands in the doc reproduce the run.
- REQ-VP3: README first screen contains the value sentence and a link to
  `docs/proof/value-demo.md`; `pytest -q`, `ruff check src tests`, and
  `kelix lint` pass on this repo after the cut.
