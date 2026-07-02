# Quickstart

From zero to an overnight run that leaves verified commits on a run branch.

## 1. Install

```bash
pipx install kelix        # recommended
# or
pip install kelix
```

Kelix's core is stdlib-only Python. The default agent backend is the
[Kiro CLI](https://kiro.dev) (`kiro-cli` with `KIRO_API_KEY` set); a `cmd`
adapter can drive any other agent CLI, and a `mock` adapter powers tests.

## 2. Initialize your repo

Inside a git repository:

```bash
kelix init
```

This creates:

- `GOAL.md` — describe your outcome, non-goals, and acceptance criteria
- `.kelix/backlog.md` — the work queue (a template with one placeholder task)
- `.kelix/memory/project.md` — durable project memory
- `.kelix/kelix.toml` — configuration (every field optional, defaults are safe)
- `.kelix/skills/` and `.kelix/prompts/` — empty, filled as the loop learns

If you already have a Kiro spec, seed the backlog from it instead of writing
tasks by hand: `kelix init --from-spec <name>` (see the
[Kiro guide](kiro.md)).

## 3. Plan first — goal to backlog

Edit `GOAL.md` with your outcome, non-goals, and testable acceptance bullets
(the PRD skeleton from [writing-for-the-loop.md](writing-for-the-loop.md)).
Then let one planning iteration draft a roadmap and proposed backlog tasks:

```bash
$EDITOR GOAL.md
kelix plan --goal-file GOAL.md
```

Review `.kelix/roadmap.md` and the new tasks in `.kelix/backlog.md`. Run
`kelix lint` to catch slop before you promote anything. Change task
`status: proposed` to `status: ready` for work you want the loop to pick up.

Already have a hand-written backlog? Skip planning and edit
`.kelix/backlog.md` directly — the flat-backlog path still works.

## 4. Define "done" — the verification gate

Edit `.kelix/kelix.toml` and set the commands that must all exit 0 before any
task counts as finished:

```toml
[verify]
commands = ["pytest -q", "ruff check ."]
```

This is the single most important configuration. The runner re-runs these
commands itself after every iteration; an agent claiming success does not
matter if verification is red. No commands configured means no verification
gate — fine for experimenting, not for unattended runs.

## 5. Write backlog tasks (optional)

Each task in `.kelix/backlog.md` is one line, in exactly this format:

```text
- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kelix | deps: ID,ID
```

Optional note lines, indented two spaces below the task:

```text
  rationale: why this task exists
  details: scope and acceptance criteria
  diagnosis: why a blocked task is stuck (required when status is blocked)
```

For example:

```text
- [ ] T1: add rate limiting to the API client | priority: 80 | status: ready | by: owner
  rationale: we are getting 429s from the upstream service in CI
  details: exponential backoff with jitter, max 5 retries, covered by a unit test

- [ ] T2: document the retry behavior | priority: 60 | status: ready | by: owner | deps: T1
```

Higher `priority` number means more important; `by: owner` tasks always
outrank `by: kelix` proposals; only `ready` tasks with all `deps` done are
candidates. Malformed lines are skipped, never fatal. The full rubric —
priority bands, decomposition, blocked tasks — is in
[prioritization.md](prioritization.md).

If you used `kelix plan`, most tasks are already written — promote the ones
you want and skip this section.

## 6. Run

```bash
kelix run --max-iterations 25
```

Each iteration: a fresh agent process reads the backlog and git log, picks the
one highest-priority ready task, implements it in an isolated git worktree
(on a `kelix/run-<id>` branch), and the runner re-runs your verify commands.
Green: commit, record memory, next task. Red: the task stays on top. The run
stops on the completion sentinel, the iteration cap, the circuit breaker
(3 consecutive failures by default), or the kill switch.

Each run works on an isolated `kelix/run-<id>` branch. Review the diff and
merge when ready — Kelix never pushes to `main`/`master`.

Useful flags:

- `--max-iterations N` — override the config cap for this run
- `--role "text"` — extra role text injected into the prompt
- `--path DIR` — run against a repo other than the current directory
- `--force` — skip the run-time spec gate only (ready-task backlog lint);
  git safety rails (worktree isolation, command denylist) are unchanged

## 7. Read the results

Every run writes an audit trail to `.kelix/runs/<run-id>/`:

| File | Contents |
|---|---|
| `run.json` | Machine-readable record: status, branch, and per-iteration data (rationale, progress, verified, failure, duration) |
| `retrospective.md` | Human summary: iteration outcomes and a "for the owner" section listing anything that needs attention |
| `iter-001.log`, `iter-002.log`, … | Full transcript per iteration (prompt + agent output, secrets scrubbed) |
| `diagnosis.md` | Only present if the circuit breaker tripped: the failure sequence and where to look |

Start with `retrospective.md`, then the diff on the run branch, then
individual `iter-*.log` files for anything surprising. Every iteration logs a
one-line `RATIONALE:` explaining the task it chose.

## Secondary operations

These commands stay available but are not on the init → plan → run happy path.
Use them when you need to inspect or steer an active run.

| Command | Purpose |
|---------|---------|
| `kelix lint` | Check backlog tasks against the input contract before promoting |
| `kelix status` | Show active runs, claims, and kill-switch state from coordination files |
| `kelix stop` | Write `.kelix/STOP` — active runs halt before the next iteration |
| `kelix watch` | Stream a running agent's output live (`ctrl-c` detaches without stopping the run) |

## Where next

- [Concept](concept.md) — the invariants behind the design
- [Kiro guide](kiro.md) — specs, steering, the custom agent, MCP
- [Fleet mode](fleet.md) — several role-specialized loops on one backlog
- [Memory & skills](memory-and-skills.md) — what the loop learns between runs
- [Security model](SECURITY.md) — read this before an unattended run
