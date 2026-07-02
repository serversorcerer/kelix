# Quickstart

From zero to an overnight run that leaves reviewable PRs by morning.

## 1. Install

```bash
pipx install kalph        # recommended
# or
pip install kalph
```

Kalph's core is stdlib-only Python. The default agent backend is the
[Kiro CLI](https://kiro.dev) (`kiro-cli` with `KIRO_API_KEY` set); a `cmd`
adapter can drive any other agent CLI, and a `mock` adapter powers tests.

## 2. Initialize your repo

Inside a git repository:

```bash
kalph init
```

This creates:

- `.kalph/backlog.md` — the work queue (a template with one placeholder task)
- `.kalph/memory/project.md` — durable project memory
- `.kalph/kalph.toml` — configuration (every field optional, defaults are safe)
- `.kalph/skills/` and `.kalph/prompts/` — empty, filled as the loop learns

If you already have a Kiro spec, seed the backlog from it instead of writing
tasks by hand: `kalph init --from-spec <name>` (see the
[Kiro guide](kiro.md)).

## 3. Define "done" — the verification gate

Edit `.kalph/kalph.toml` and set the commands that must all exit 0 before any
task counts as finished:

```toml
[verify]
commands = ["pytest -q", "ruff check ."]
```

This is the single most important configuration. The runner re-runs these
commands itself after every iteration; an agent claiming success does not
matter if verification is red. No commands configured means no verification
gate — fine for experimenting, not for unattended runs.

## 4. Write backlog tasks

Each task in `.kalph/backlog.md` is one line, in exactly this format:

```text
- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kalph | deps: ID,ID
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
outrank `by: kalph` proposals; only `ready` tasks with all `deps` done are
candidates. Malformed lines are skipped, never fatal. The full rubric —
priority bands, decomposition, blocked tasks — is in
[prioritization.md](prioritization.md).

## 5. Run

```bash
kalph run --max-iterations 25 --pr
```

Each iteration: a fresh agent process reads the backlog and git log, picks the
one highest-priority ready task, implements it in an isolated git worktree
(on a `kalph/run-<id>` branch), and the runner re-runs your verify commands.
Green: commit, record memory, next task. Red: the task stays on top. The run
stops on the completion sentinel, the iteration cap, the circuit breaker
(3 consecutive failures by default), or the kill switch.

With `--pr`, a completed or capped run is pushed and opened as a GitHub PR via
`gh` — never merged, never pushed to main. Humans merge.

Useful flags:

- `--max-iterations N` — override the config cap for this run
- `--role "text"` — extra role text injected into the prompt
- `--path DIR` — run against a repo other than the current directory

## 6. Read the results

Every run writes an audit trail to `.kalph/runs/<run-id>/`:

| File | Contents |
|---|---|
| `run.json` | Machine-readable record: status, branch, and per-iteration data (rationale, progress, verified, failure, duration) |
| `retrospective.md` | Human summary: iteration outcomes and a "for the owner" section listing anything that needs attention |
| `iter-001.log`, `iter-002.log`, … | Full transcript per iteration (prompt + agent output, secrets scrubbed) |
| `diagnosis.md` | Only present if the circuit breaker tripped: the failure sequence and where to look |

Start with `retrospective.md`, then the diff on the run branch, then
individual `iter-*.log` files for anything surprising. Every iteration logs a
one-line `RATIONALE:` explaining the task it chose.

## 7. Monitor and stop

```bash
kalph status
```

Shows the current state assembled purely from coordination files and git:
recent runs and their branches, any fleet task claims, mailbox notes, and
whether the kill switch is set.

```bash
kalph stop
```

Writes `.kalph/STOP`. Active runs halt before their next iteration; new runs
refuse to start. Remove the file to allow runs again.

## Where next

- [Concept](concept.md) — the invariants behind the design
- [Kiro guide](kiro.md) — specs, steering, the custom agent, MCP
- [Fleet mode](fleet.md) — several role-specialized loops on one backlog
- [Memory & skills](memory-and-skills.md) — what the loop learns between runs
- [Security model](SECURITY.md) — read this before an unattended run
