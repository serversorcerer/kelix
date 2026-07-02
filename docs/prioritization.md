# Prioritization rubric

How Kelix chooses work from `.kelix/backlog.md`. The runner and
`select_next()` in `src/kelix/backlog.py` implement a subset of this rubric
mechanically; the rest guides humans and agents when writing or proposing tasks.

## Backlog task format

Each task is one line (optional indented notes below):

```text
- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kelix | deps: ID,ID
```

Optional note lines (indented two spaces):

```text
  rationale: why this task exists
  details: scope and acceptance criteria
  diagnosis: why a blocked task is stuck (required when status is blocked)
```

Higher `priority` number means more important. Checkbox `[x]` implies `status: done`.
Malformed lines are skipped on parse, never fatal.

## Selection order

When an iteration picks work, apply these rules in order:

1. **Owner intent first** — Tasks with `by: owner` always outrank `by: kelix`
   tasks, regardless of priority number. Owner tasks express mission direction;
   kelix-proposed tasks are suggestions only.

2. **Ready and unblocked** — Only tasks with `status: ready` whose every
   dependency ID is `done` are candidates. Tasks in `proposed`, `blocked`, or
   waiting on deps are skipped.

3. **Highest priority wins** — Among remaining candidates, pick the highest
   numeric `priority`. Ties at the same `by` value are arbitrary (first in file
   order is fine).

This matches `select_next()`: sort key is `(owner_rank, -priority)` where
`owner_rank` is 0 for owner and 1 for kelix.

## What the numbers mean

Priority bands are guidance when authoring tasks, not hard-coded in the parser.

| Band | Typical use |
|------|-------------|
| **90–100** | Broken build, owner urgent, or blocking correctness — fix before anything else |
| **70–89** | Owner features and mission-critical docs or infrastructure |
| **50–69** | Correctness debt: tests, regressions, edge cases not yet blocking the loop |
| **30–49** | Kelix-proposed improvements (refactors, observability, nice-to-have fixes) |
| **1–29** | Polish: wording, style, minor cleanup with no behavioral impact |

Within a band, rank by **category** when choosing relative scores:

1. Correctness / broken builds (tests red, verification gate failing)
2. Security (scrubber, command policy, secret handling)
3. Feature progress (backlog items that advance the plan)
4. Polish (docs clarity, naming, formatting)

Example from the self-hosting backlog: parser and safety tests (KB1–KB3) at
75–90 before prioritization docs (KB4) at 70.

## One task per iteration

Each iteration implements **exactly one** ready task. If a task is too large for
one iteration:

- Do **not** start partial implementation.
- Decompose it into smaller tasks in the backlog (each sized for one iteration).
- Add `deps:` so subtasks run in a sensible order.
- Commit the backlog update, print `RATIONALE:` explaining the decomposition,
  and stop.

Subtasks inherit the parent's intent; give each a clear `details:` line so the
next iteration knows when it is done.

## Blocked tasks

If the **same failure** appears twice on the same task (check `git log` and the
episode digest in the iteration prompt):

- Mark the task `status: blocked`.
- Add a `diagnosis:` note with the error, what was tried, and what is needed to
  unblock (human decision, missing dependency, environment issue).
- Do **not** attempt a third grind on the identical failure.

The loop completes only when every task is `done` or `blocked` with a
`diagnosis`. Blocked tasks stay visible until the owner resolves them.

## Proposed tasks

Tasks with `status: proposed` are ideas, not work queue items. An iteration may
add proposed tasks when it notices out-of-scope problems; it must not implement
them unless promoted to `ready` by the owner.

When promoting: set `status: ready`, assign a priority band, and set `by: owner`
if the owner endorses the work.

## Verification before done

Mark a task `done` only after the verification gate passes for the code you
touched:

```bash
pytest -q
ruff check src tests
```

A task left at `ready` with failing verification is not finished; the next
iteration will pick it again if it remains highest priority.
