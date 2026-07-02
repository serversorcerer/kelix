# Value demo — cold run receipt (REQ-VP2)

**Mock adapter** — this receipt uses `[agent] adapter = "mock"` for a fast,
CI-reproducible proof. For a live-agent dogfood run with the same verify gate,
see [final-report § D1](final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd).

Reproducible evidence that Kelix completes a well-specified goal unattended and
returns verified commits. Captured from `samples/value-demo/` on 2026-07-02.

## Reproduce

From a Kelix checkout with an editable install (`pip install -e .`):

```bash
export KELIX_ROOT="$(pwd)"
export KELIX_VENV="$KELIX_ROOT/.venv/bin"

# Clean nested repo (do not run inside the monorepo root)
DEMO_TMP="$(mktemp -d /tmp/value-demo-XXXXXX)"
cp -r samples/value-demo/. "$DEMO_TMP/"
cd "$DEMO_TMP"

/usr/bin/time -p bash run-demo.sh 2>&1 | tee transcript.txt
```

Or from the bundled scaffold (initializes git on first run):

```bash
cd samples/value-demo
./run-demo.sh
```

Receipt paths after a successful run:

| Artifact | Path |
|----------|------|
| Run metadata | `.kelix/runs/<run_id>/run.json` |
| Retrospective | `.kelix/runs/<run_id>/retrospective.md` |
| Per-iteration logs | `.kelix/runs/<run_id>/iter-NNN.log` |
| Verified branch | `kelix/run-<run_id>` (git worktree under `.kelix/worktrees/`) |
| Outcome ledger | `.kelix/memory/loop-metrics.json` |

## Goal

From `samples/value-demo/GOAL.md`:

> **Gold in, diamonds out.** Build a tiny stdlib-only calculator module that
> Kelix can complete in five one-iteration tasks.
>
> Outcome: `calc.py` with `add`, `sub`, `mul`, `div` (zero-safe), and a CLI
> entrypoint. Every function has a pytest assertion in `tests/test_calc.py`.
>
> Acceptance: `python3 -m pytest -q` exits 0 after all backlog tasks are
> verified done.

## Planning interview

This scaffold ships with a pre-written roadmap and five `status: ready` backlog
tasks, so `run-demo.sh` **skips** `kelix plan` when `.kelix/roadmap.md`
contains `Milestone M1`. No `QUESTIONS.md` is produced.

For a live-agent cold run from scratch, delete `.kelix/roadmap.md` and
`.kelix/backlog.md`, then re-run; `kelix plan --goal-file GOAL.md` will
interview (or write `.kelix/phases/<slug>/QUESTIONS.md` when non-interactive).

## Promote step

Before `kelix run`, tasks must be `status: ready`. The bundled scaffold already
has five ready owner tasks (T1–T5); no manual promotion is required for the
mock demo. After a fresh `kelix plan`, change `status: proposed` →
`status: ready` for each task you want the loop to pick up.

## Captured run — 20260702-184413

| Metric | Value |
|--------|-------|
| Run id | `20260702-184413` |
| Branch | `kelix/run-20260702-184413` |
| Adapter | `mock` (`mockdir/001.sh` … `005.sh`) |
| Iterations | 5 (5 verified, 0 failures) |
| Wall clock | 3.73 s (`/usr/bin/time -p`) |
| Verify gate | `pytest -q` exit 0 (6 passed) |

### Iteration summary

| # | Task | Rationale | Duration | Verified |
|---|------|-----------|----------|----------|
| 1 | T1 add() | add() is the highest-priority ready task | 0.6 s | yes |
| 2 | T2 sub() | sub() is the highest-priority ready task | 0.6 s | yes |
| 3 | T3 mul() | mul() is the highest-priority ready task | 0.6 s | yes |
| 4 | T4 div() | div() with zero guard is the highest-priority ready task | 0.6 s | yes |
| 5 | T5 cli | cli entrypoint is the highest-priority ready task | 0.7 s | yes (sentinel) |

### Verified commits (run branch)

```
b3f296a14f3aa065c050da5bfec0d7e7681a83da  T1: add function
b8d7c4d348d83ba121c8c41c3410285a5d2fa480  T2: sub function
25d10209dededdeaac68d420cf742090190607bf  T3: mul function
a1142bc56e8fb776c7ca85da1ceed7c66ef505c0  T4: div with zero guard
c06766bd9e631f392a596970cc4ea912ce78a284  T5: cli entrypoint
```

Inspect on the run branch:

```bash
git log kelix/run-20260702-184413 --oneline
```

### Verify receipt

From `run.json` → `last_verify_report`:

```
pytest -q  exit 0
......                                                                   [100%]
6 passed in 0.00s
```

Run-complete output:

```
◉ run 20260702-184413 finished: completed (5 iterations, 5 verified-done)
◉ verify: pytest -q exit 0
◉ verified commits: b3f296a..., b8d7c4d..., 25d1020..., a1142bc..., c06766b...
```

### Full stdout transcript

```
◉ initialized: .kelix/phases/README.md
↻ next moves:
    1. describe your goal in GOAL.md
    2. kelix plan --goal-file GOAL.md   (it will interview you)
    3. review the draft, promote tasks to ready
    4. kelix run                        (wake up to verified commits)
Roadmap present — skipping kelix plan.

=== PROMOTE STEP ===
This scaffold ships with status: ready tasks (mock demo needs no edits).
For a live agent run after kelix plan, promote proposed tasks in
.kelix/backlog.md from status: proposed to status: ready before run.
kelix run 20260702-184413: branch=kelix/run-20260702-184413 cap=10
  iter 1: rationale=T1 — add() is the highest-priority ready task progress=True verified=True ok
  iter 2: rationale=T2 — sub() is the highest-priority ready task progress=True verified=True ok
  iter 3: rationale=T3 — mul() is the highest-priority ready task progress=True verified=True ok
  iter 4: rationale=T4 — div() with zero guard is the highest-priority ready task progress=True verified=True ok
  iter 5: rationale=T5 — cli entrypoint is the highest-priority ready task progress=True verified=True ok
  distill: calc.py: not under .kelix/skills/_proposed/
  distill: tests/test_calc.py: not under .kelix/skills/_proposed/
◉ run 20260702-184413 finished: completed (5 iterations, 5 verified-done)
◉ verify: pytest -q exit 0
◉ verified commits: b3f296a14f3aa065c050da5bfec0d7e7681a83da, b8d7c4d348d83ba121c8c41c3410285a5d2fa480, 25d10209dededdeaac68d420cf742090190607bf, a1142bc56e8fb776c7ca85da1ceed7c66ef505c0, c06766bd9e631f392a596970cc4ea912ce78a284
real 3.73
user 1.71
sys 0.65
```

### Retrospective excerpt

From `.kelix/runs/20260702-184413/retrospective.md`:

```
- status: **completed**
- iterations: 5 (5 verified, 0 failures)
- branch: `kelix/run-20260702-184413`

## Iterations
- 1: T1 — add() is the highest-priority ready task -> verified
- 2: T2 — sub() is the highest-priority ready task -> verified
- 3: T3 — mul() is the highest-priority ready task -> verified
- 4: T4 — div() with zero guard is the highest-priority ready task -> verified
- 5: T5 — cli entrypoint is the highest-priority ready task -> verified
```

## What this proves

- **Init → run path works** without fleet, PR, sync, or MCP tooling.
- **Spec gate + verify gate** pass on every iteration (`pytest -q` after each task).
- **Receipt output** names verify command, exit status, and commit SHAs (REQ-VS1).
- **Mock adapter** makes the demo CI-reproducible; swap `[agent] adapter = "mock"`
  for a named preset (`cursor`, `claude`, etc.) to run the same backlog with a
  live agent.
