# Writing for the loop

Kalph is a fresh, stateless agent every iteration. It cannot ask you a
follow-up question, and it cannot remember the conversation where you
explained what you really meant. **Everything it knows about your intent is
what you wrote down.** Good input in, good output out; slop in, slop out.

This page is the input contract: how to write backlogs, PRDs, and plans that
a fresh agent executes correctly on the first read — without padding them
into essays that slow every iteration down.

## The three rules

1. **Write the acceptance, not the vibe.** "Improve the CLI" is slop.
   "`done <id>` on a missing id exits non-zero with an error on stderr" is a
   task. If you can't state how the agent proves it's done, the task isn't
   ready for the loop — it's still a thought.
2. **One iteration, one task.** If a task needs an "and then", split it. The
   loop's unit of progress is one verified commit; tasks sized bigger than
   that get decomposed by the agent anyway, burning an iteration you could
   have spent building.
3. **Say the constraint once, in the file the agent reads.** Conventions go
   in `.kalph/memory/project.md`, work goes in `.kalph/backlog.md`, done
   goes in `[verify] commands`. Repeating yourself across files creates
   contradictions; the agent will trip on them.

## Anatomy of a good task

```markdown
- [ ] T6: JSON persistence | priority: 80 | status: ready | by: owner | deps: T4
  details: tasklite/persistence.py save(store, path) and load(path)->Store
  using json (human-readable, indent=2). Round-trip test: save then load
  yields equal tasks.
```

Every field earns its place:

- **Title** — what, in five words. This becomes the branch name and commit
  prefix, so make it greppable.
- **priority** — a number, because "important" is not sortable. The rubric
  is in [prioritization.md](prioritization.md).
- **deps** — the loop won't start work whose foundation doesn't exist yet.
- **details** — file paths, function signatures, and the test that proves
  it. Concrete nouns beat adjectives: name the file, name the function,
  name the error message.

The dogfood run that built a whole library in 12/12 verified iterations ran
on tasks written exactly like this. Nothing about the run was lucky — the
input made wrong turns hard to take.

## Anatomy of a bad task, and the fix

| Slop | Why it fails | Steak |
|---|---|---|
| "Make persistence better" | No acceptance; agent guesses | "save/load preserve `next_id` so ids don't reset after reload; regression test included" |
| "Add auth, tests, and docs" | Three tasks wearing one id | Three tasks with `deps` between them |
| "Fix the bug" | Which bug? Reproduce how? | "`kalph status` crashes when run.json is truncated; repro: `echo '{' > run.json`; should print `?` instead" |
| "Use best practices" | Unfalsifiable | Put the practice in `[verify]` (a linter) or delete the sentence |

## From PRD to backlog

A PRD for the loop is not a pitch deck — it's the decomposition source. Keep
it to four sections, in the repo where the agent can read it:

```markdown
# <feature> PRD
## Outcome        — one paragraph: what exists when this ships, for whom
## Non-goals      — what the loop must NOT build, even if tempting
## Acceptance     — bullet list; each bullet is testable, each becomes verify evidence
## Task seeds     — the first backlog entries, written to the anatomy above
```

Non-goals matter as much as goals: the loop's failure mode isn't laziness,
it's enthusiasm. A stated non-goal is a fence; an unstated one is an
invitation. (Kiro users: a spec's `tasks.md` imports directly via
`kalph init --from-spec <name>` — same rules apply to how you write the
spec tasks.)

## Don't over-think it either

Precision is not length. Every character you write gets re-read by a fresh
agent every single iteration — a bloated backlog is a tax on the whole run.

- If the codebase already answers a question (style, structure, naming),
  don't answer it again in the task. The agent reads the code.
- Don't pre-decompose what you can't see yet. Seed the first few tasks
  precisely and let the loop propose the rest (`status: proposed`); you
  review them by editing a file, not by having a meeting.
- Trust the rails. You don't need "make sure tests pass" in every task —
  the runner re-runs `[verify]` regardless of what the agent claims.
- A good check before committing a backlog: read each task and ask
  *"could a competent stranger with no context do this tomorrow morning?"*
  That stranger is exactly who shows up.

## Steering the running loop

You steer with one-line edits, not conversations:

- Reprioritize: change a `priority:` number.
- Redirect: edit a task's `details:` — the next iteration reads the new text.
- Veto: set `status: blocked` with a `diagnosis:` note.
- Stop: `kalph stop` (writes the kill switch file).

The loop reads state from disk at every iteration start, so every edit
lands at the next natural boundary — no need to interrupt anything.
