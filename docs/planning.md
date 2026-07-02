# Planning with Kelix

Kelix can run on a flat backlog — edit `.kelix/backlog.md`, set tasks to
`status: ready`, run `kelix run`. That path is still the quick path for small
repos and bugfix queues.

Use planning when the work has **structure**: milestones you will ship in
order, phases that close only when specific requirements are verified, or
parallel agents that must not collide on dependent tasks. This page is the
owner's guide to that hierarchy — how to go from a goal in your head to a
loop-ready plan a stranger can adopt tonight.

For task-level writing rules, see [writing-for-the-loop.md](writing-for-the-loop.md).

## Plan-first flow

Six steps from zero to verified commits:

```bash
kelix init                              # seeds GOAL.md, backlog, kelix.toml
$EDITOR GOAL.md                         # outcome, non-goals, acceptance bullets
kelix plan --goal-file GOAL.md          # interview + draft roadmap + proposed tasks
kelix lint                              # reject slop before you promote anything
$EDITOR .kelix/backlog.md               # status: proposed -> ready
kelix run --max-iterations 25           # one task per iteration, verified-done
```

What each step produces:

| Step | Output | Who owns it |
|---|---|---|
| `GOAL.md` | Intent: outcome, non-goals, testable acceptance | You |
| `kelix plan` | `.kelix/roadmap.md` + proposed backlog tasks | Agent drafts; you review |
| `kelix lint` | Actionable findings (missing acceptance, cyclic deps, …) | Machine |
| Promote | Tasks with `status: ready` enter the queue | You |
| `kelix run` | Verified commits, `.kelix/STATE.md` updates, retrospectives | Runner + agent |

`kelix plan` never implements code. It may ask structured questions first
(with a TTY, live; headless, it writes `.kelix/phases/<id>/QUESTIONS.md` and
exits until you answer). Answers land in the phase's `CONTEXT.md` — decisions
captured once, injected every iteration as read-only data.

Skip planning when you already know the next three tasks. Edit the backlog
directly; the loop contract is unchanged.

## Roadmap → phase → task

Three layers, top-down:

```text
Milestone (releasable increment)
  └── Phase (largest unit safely closed as one run)
        └── REQ-ID (coverage contract — must map to verified-done task(s))
              └── Backlog task (one iteration, one commit)
```

**Roadmap** (`.kelix/roadmap.md`) is owner intent. Format:

```markdown
## Milestone M1 — Title
(prose: goal, non-goals)

### Phase P-FOO — Title
Outcome: one sentence for what "done" means here.

- REQ-A1: testable requirement text
- REQ-A2: another requirement
```

Parsed by `roadmap.py`: `## Milestone <id> — <title>`, `### Phase <id> — <title>`,
optional `Outcome:` line, `- REQ-X: text` bullets.

**Backlog tasks** link upward with optional pipe fields:

```markdown
- [ ] T1: add parser | priority: 80 | status: ready | by: owner | phase: P-FOO | req: REQ-A1
  details: create src/foo.py with parse(); tests/test_foo.py round-trip.
```

Tasks without `phase:` / `req:` behave exactly like a flat backlog. Planning
adds the fields; quick-path repos never need them.

**Phase decisions** live in `.kelix/phases/<phase-id>/CONTEXT.md`. When
STATE.md names that phase and the file exists, its contents are injected into
the prompt — data, not instructions. Do not re-litigate decisions there in
every iteration.

## STATE.md — where the project is

The runner (not the agent) maintains `.kelix/STATE.md`. Every iteration reads
it first. Fixed schema:

```markdown
# Kelix state

- milestone: M1
- phase: P-FOO
- current_task: selecting
- last_task: T1
- last_verified_commit: abc1234
- done: 3
- total: 12
- blockers:
  - REQ-A2 uncovered
```

Fields:

- **milestone / phase** — active position in the roadmap (empty = flat mode)
- **current_task** — task id for this iteration, or `selecting`
- **last_task** — previous iteration's task id
- **last_verified_commit** — HEAD sha when verification last passed
- **done / total** — task counts from the backlog (for the active scope)
- **blockers** — uncovered REQs or other gates the runner surfaced

The runner writes STATE.md at run start, after verified iterations, and at run
end. It is committed with retrospectives so history shows orientation over time.

## kelix lint — reject slop before the loop runs

```bash
kelix lint          # exit 0 = clean, exit 1 = findings on stderr
```

`lint_backlog` checks non-done tasks: missing `details:`, no acceptance signal
(test path, assert, exit code, named file), unfalsifiable wording without a
metric, dangling or cyclic deps, title over 80 chars, multiple deliverables
(` and then ` in details).

With a roadmap, `validate_plan` also requires every REQ to be referenced by at
least one task. Run lint after `kelix plan` and before promoting tasks.

Good input in, good output out — see [writing-for-the-loop.md](writing-for-the-loop.md)
for the task anatomy lint enforces.

## Phase gate — when a phase closes

A phase is **done** when every REQ in that phase maps to a **verified-done**
task (`status: done` after `[verify]` commands pass). The runner computes
coverage; it does not trust the agent's sentinel.

At run end (and when all active-phase tasks finish mid-run):

- **Fully covered** — STATE.md advances to the next phase; blockers clear.
- **Uncovered REQs** — phase stays put; uncovered REQ-IDs become blockers;
  the run retrospective gets a `## Phase gate` section naming each gap.

The agent never decides the phase is closed. Inspect coverage anytime:

```bash
kelix status        # milestone, phase, REQ table, blockers
```

## Waves — safe parallelism in fleet mode

When multiple agents share one backlog, dependency order matters. Kelix derives
**waves** from task `deps:` — no new syntax:

- Wave 0 — tasks with no undone dependencies
- Wave N — tasks whose deps are done or in earlier waves
- Cycles — remaining tasks land in a final wave; the runner warns

Fleet claim hooks restrict agents to the **earliest incomplete wave**. An agent
cannot claim wave-1 work while wave 0 still has unfinished tasks. `kelix status`
lists pending tasks with wave numbers.

Solo `kelix run` ignores waves; they matter only when `.kelix/fleet.toml` runs
parallel loops.

## When NOT to use planning

Stay on the flat backlog when:

- The repo has fewer than ~5 tasks and you can write them precisely by hand.
- You are fixing one bug or polishing one module — no milestone structure.
- You do not need REQ coverage tracking or phase gates.
- You are not running a fleet and deps are obvious.

Planning adds files and ceremony. The quick path (`kelix init` → edit backlog
→ `kelix run`) is intentionally unchanged. Delete `.kelix/roadmap.md` if you
started with the init template and never promoted it.

## Quick reference

| Command | Purpose |
|---|---|
| `kelix init` | Seed GOAL.md, backlog, kelix.toml, optional roadmap skeleton |
| `kelix plan --goal-file GOAL.md` | Interview + draft roadmap and proposed tasks |
| `kelix lint` | Machine-check backlog and roadmap before promoting |
| `kelix run` | One verified task per iteration |
| `kelix status` | Milestone, phase, REQ coverage, fleet claims, waves |
| `kelix diagnose` | *(secondary)* Review failed runs; write `.kelix/memory/diagnosis-*.md` |
| `kelix propose` | *(secondary)* Tuning PR from metrics + diagnosis; owner records merge/grade |

Further reading: [quickstart.md](quickstart.md) (install and verify gate),
[prioritization.md](prioritization.md) (selection order and priority bands),
[fleet.md](fleet.md) (parallel agents and claims),
[memory-and-skills.md](memory-and-skills.md) (context compiler, distillation, manifests).
