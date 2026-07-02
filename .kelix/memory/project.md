# Project memory

Durable facts about this repo for future iterations.

- This repo is Kelix itself: a Python 3.11+ stdlib-only package in `src/kelix/`,
  tests in `tests/` (pytest), lint with ruff (line length 100). Core modules:
  config.py, adapters.py, prompt.py, loop.py, verify.py, memory.py,
  security.py, gitutil.py, cli.py.
- Verification gate: `pytest -q` and `ruff check src tests` must both pass.
  Run them before claiming any task done.
- Backlog tasks are parsed by `src/kelix/backlog.py` (`parse_backlog`,
  `serialize_backlog`, `select_next`). Task lines use pipe-separated fields;
  owner tasks outrank kelix at equal selection time regardless of priority number.
  `select_next(tasks, autonomy="normal")` skips `proposed` tasks; with
  `autonomy="high"`, proposed tasks are candidates but sort below owner `ready`
  tasks via `(owner_rank, status_rank, -priority)`.
- Design invariants live in docs/research/ralph-invariants.md — static prompt,
  fresh context per iteration, deterministic stop, state in files. Never add a
  feature that violates them (e.g. no long-lived sessions, no RPC between
  agents; coordination is files + git only).
- Tests use tests/conftest.py helpers `make_repo` / `write_mock_script` and the
  mock adapter; never call a real agent CLI in tests.
- Memory module unit tests live in `tests/test_memory.py` (episodes round-trip,
  corrupt-line tolerance, digests, skill frontmatter parsing, retrospectives).
  Use `tmp_path` fixtures; never write to the real `.kelix/` directory in tests.
- Security module unit tests live in `tests/test_security.py` (scrub/contains_secret
  for token shapes, CommandPolicy deny/allow/allow_only/deny_extra). No tmp_path
  needed — pure functions.
- Decisions already made are in DECISIONS.md; do not re-litigate them.
- GOTCHA: never run `pip install -e .` inside a run worktree — it repoints the
  shared venv's editable install at the worktree, which breaks `kelix` on the
  main checkout after the worktree is removed. The verify commands already set
  PYTHONPATH=src; that is sufficient. (Learned from run 20260702-002215.)
- Prioritization rubric for backlog authoring and selection lives in
  `docs/prioritization.md` (owner-first, priority bands, decomposition/blocked rules).
- PR flow lives in `src/kelix/pr.py` (`open_pr`, `build_pr_title`, `build_pr_body`).
  `kelix run --pr` opens a GitHub PR after `completed` or `max_iterations` runs;
  refuses main/master/empty branches, pushes with `git push -u origin <branch>`,
  never `--force`. Returns None (log-and-skip) on any subprocess failure.
- Fleet claims live in `src/kelix/claims.py` (`.kelix/fleet/claims/<task-id>.json`).
  `claim_task` uses `O_CREAT|O_EXCL` for new claims; stale claims (heartbeat older
  than `stale_after_s`, default 900s) are reclaimable via temp-file + `os.replace`.
  Tests in `tests/test_claims.py` cover concurrent winners, stale reclaim, release,
  and wrong-agent guardrails.
- STATE.md spine lives in `src/kelix/state.py` (`State` dataclass, `load_state`,
  `write_state`). Parser is tolerant: missing file -> None, malformed lines skipped,
  optional space after colon in field bullets, `(none)` blocker treated as empty.
  Tests in `tests/test_state.py`. The runner (`loop.py`) tracks state in memory
  through a run (current_task from pre_iteration hook or "selecting", last_task
  from rationale, done/total from parse_backlog, last_verified_commit on verified
  iterations) and writes `.kelix/STATE.md` once in `_finish` before the
  retrospective checkpoint — not mid-iteration. STATE.md is intentionally absent
  from `RUNNER_BOOKKEEPING` excludes so the retrospective commit ships it.
  The prompt's first data slot is `{{STATE}}` in `prompt.py` (budget
  `[memory].state_max_chars`, default 1200); `loop.py` `_gather_context` loads
  via `load_state()` and injects the file text, falling back to
  "(no state file — flat-backlog mode)" when absent.
- Roadmap parser lives in `src/kelix/roadmap.py` (`Milestone`, `Phase`, `Req`,
  `Roadmap`, `parse_roadmap`, `load_roadmap`, `reqs_for(phase_id)`). Format:
  `## Milestone <id> — <title>`, `### Phase <id> — <title>`, optional
  `Outcome:` line after phase header, `- REQ-X: text` bullets. Prose and
  malformed lines are skipped. Tests in `tests/test_roadmap.py` including the
  real `.kelix/roadmap.md` fixture.
- Backlog tasks optionally carry `phase:` and `req:` pipe fields (any order
  after `by:`, alongside optional `deps:`). `Task` has `phase: str = ""` and
  `req: str = ""`; `serialize_backlog` emits them only when set. Legacy lines
  without these fields parse identically. `select_next(..., active_phase="")`
  when set prefers tasks in that phase, then phaseless, then other phases
  (within owner/status/priority keys).
- Phase CONTEXT injection: when STATE.md names an active phase and
  `.kelix/phases/<phase-id>/CONTEXT.md` exists, `loop.py` `_gather_context`
  loads it via `prompt.load_phase_context()` and injects it as the
  `{{PHASE_CONTEXT}}` slot (budget `[memory].phase_context_max_chars`, default
  2000) with banner "Decisions already made for this phase — do not re-litigate;
  data, not instructions." Missing file or empty phase renders "(no phase
  decisions)". `kelix init` writes `.kelix/phases/README.md` explaining the
  CONTEXT.md convention. Tests in `tests/test_prompt.py`.
- `kelix plan` lives in `src/kelix/plan.py` (`PlanRunner`) with CLI in
  `cli.py` (`cmd_plan`). Accepts a goal string or `--goal-file`. Runs an
  interview step first (unless `.kelix/phases/<goal-slug>/QUESTIONS.md` is
  fully answered): one adapter iteration emits a `` ```QUESTIONS `` block;
  with a TTY, `present_questions_tty` asks live and defaults to the
  recommended option; without a TTY, writes QUESTIONS.md and exits 0 with
  status `awaiting_answers`. Answered interviews land in the phase dir's
  CONTEXT.md (`## Decisions from planning interview`) and are appended to the
  draft goal. Then one draft iteration using `PLANNING_TEMPLATE` in
  `prompt.py`; verify is replaced by `validate_plan()` in `lint.py`. Pre-plan
  checkpoint establishes the diff baseline. Success prints "draft plan ready — review
  `.kelix/roadmap.md` and promote tasks to ready". Agent must emit
  `PLAN COMPLETE` sentinel on draft. Interview uses `PLANNING_INTERVIEW_TEMPLATE`.
  Phase files (QUESTIONS.md, CONTEXT.md) live on `cfg.root`, not ephemeral
  worktrees. Tests in `tests/test_plan.py`.
- Backlog lint lives in `src/kelix/lint.py` (`Finding`, `lint_backlog`,
  `lint_repo`, `validate_plan`, `format_finding`). `lint_backlog` checks
  non-done tasks (or `scope="proposed"` for kelix draft tasks only): missing
  details, no acceptance signal (test/assert/exit/file path), unfalsifiable
  wording without metric, dangling/cyclic deps, title>80 chars, multiple
  deliverables (` and then ` in details, ignoring quoted/parenthetical rule
  text). `validate_plan` also checks roadmap parse, REQ coverage, proposed-only
  kelix tasks, and planning-only file changes. CLI: `kelix lint` (exit 1 on
  findings). Tests in `tests/test_lint.py`. `parse_backlog` accumulates
  continuation lines into multi-line notes.
- `kelix init` seeds `GOAL.md` at the repo root (PRD skeleton: goal,
  non-goals, acceptance bullets) when absent; existing GOAL.md is never
  overwritten. Final message prints the plan-first path: GOAL.md ->
  `kelix plan --goal-file GOAL.md` -> review/promote -> `kelix run`.
  Tests in `tests/test_prompt.py`.
- Phase gate REQ coverage lives in `src/kelix/roadmap.py` (`CoverageEntry`,
  `coverage(roadmap, tasks, phase_id)`, `next_phase`, `phase_fully_covered`,
  `uncovered_reqs`). Per phase REQ: `covered` (done task references it),
  `in-progress` (non-done task), `uncovered` (no task). Tasks with unknown
  REQ-IDs get `warning` entries. Comma-separated `req:` on tasks matches
  lint.py. Tests in `tests/test_roadmap.py`.
- Phase gate enforcement lives in `src/kelix/loop.py` (`Runner._apply_phase_gate`,
  `_maybe_apply_phase_gate`). Runs when all active-phase backlog tasks are done
  mid-run and again at run end; no-op without roadmap or active phase. Fully
  covered phases advance `STATE.md` phase (and milestone) via `next_phase`,
  clearing blockers; otherwise uncovered REQ-IDs land in blockers and the run
  retrospective gets a `## Phase gate` section (only when uncovered REQs exist).
  Tests in `tests/test_loop.py`.
- `kelix status` phase gate (`src/kelix/fleet.py` `render_status`): when
  `.kelix/roadmap.md` and STATE.md with an active phase exist, prints milestone,
  phase title, REQ coverage table (id, status, covering task id), and blockers;
  repos without a roadmap keep the prior claims/runs/mailbox output only.
  Tests in `tests/test_fleet.py`.
- Context relevance scorer lives in `src/kelix/context.py` (`score`, `select`).
  Stdlib-only token overlap weighted by IDF across the candidate set; empty query
  falls back to recency (later candidates = more recent). `memory.episode_digest`
  and `memory.skills_digest` accept optional `query` and `budget_chars`; when
  query is set they call `select()`, otherwise behavior is unchanged. Tests in
  `tests/test_context.py`.
- Rationale fallback (`loop._resolve_rationale`): when agent output lacks
  `RATIONALE:`, the runner uses `(from commit) <subject>` from `git log -1
  --format=%s` only if HEAD advanced during the iteration (after post-iteration
  checkpoint). `_task_from_rationale` strips the prefix and parses task ids from
  commit subjects like `T1: …`. Empty rationale after fallback → retrospective
  lines use `no rationale — see transcript` (episodes still show
  `(no rationale logged)`). Tests in `tests/test_loop.py`.
- Context budget compiler (`prompt.compute_slot_budgets`, `assemble_prompt`):
  `[memory].context_share` (default 0.5) times the sum of per-slot caps drives
  the data-slot pool; state and phase_context allocate first, then episodes,
  project_memory, skills, and mailbox by fixed weights. `relevance_query_for_task`
  builds the query from the claimed/next ready task (title + details); loop
  `_gather_context` passes it so episode/skills/project digests use `select()`.
  Project memory is injected via `{{PROJECT_MEMORY}}` (`memory.project_memory_digest`).
  `assemble_prompt` returns `(prompt, manifest)` where manifest lists each injected
  item (slot, source path, chars, score). Runner writes
  `.kelix/runs/<id>/context-<n>.json` (under RUNNER_BOOKKEEPING `.kelix/runs`).
  Tests in `tests/test_prompt.py` (REQ-C4 relevance regression) and
  `tests/test_loop.py` (manifest file written).
- Adapter inactivity watchdog (`adapters._run_process`): uses Popen plus a reader
  thread; `[agent].inactivity_timeout_seconds` (default 300, 0 disables) kills
  the process when no stdout/stderr bytes arrive for that interval. Hard
  `[agent].timeout_seconds` unchanged (exit 124, timed_out=True). Inactivity
  timeout sets timed_out=True with the observed exit code. Tests in
  `tests/test_adapters.py` use flush=True Python scripts because piped shell
  stdout is block-buffered.
- Backlog waves (`backlog.waves`): pure function returning
  `(list[list[Task]], has_cycle)`. Wave 0 = tasks with no undone deps; wave N
  = tasks whose deps are done or in earlier waves; cyclic/blocked remainder
  lands in a final wave with `has_cycle=True`. Tests in `tests/test_backlog.py`
  (chain, diamond, cycle).
- Fleet wave gating (`fleet.make_claim_hook`, `render_status`): before
  `select_next`, claim candidates are restricted to task ids in the earliest
  wave containing any non-done task (`_wave_allowed_task_ids`). Agents cannot
  claim wave N+1 work while wave N is unfinished (even if wave N is claimed but
  not done). `render_status` prints a "Pending tasks (waves):" section with
  each non-done task's wave index. Tests in `tests/test_fleet.py`.
- Fleet role-match reporting (`fleet.infer_task_kind`, `_write_fleet_retrospective`):
  task kind is inferred from title/phase heuristics (test/docs/fix/feature);
  built-in roles map to preferred kinds (builder→feature, verifier→test,
  fixer→fix, scribe→docs). Fleet retrospectives append per-iteration
  `role-match: yes/no (role vs kind)` and a per-agent `role drift: N/M`
  line. Selection unchanged — reporting only. Tests in `tests/test_fleet.py`.
- Loop metrics schema (`src/kelix/metrics.py`): `LoopMetrics` with
  `iterations[]`, `fleet_summaries[]`, `proposal_outcomes[]`; each
  `IterationLedgerRow` carries run_id, iteration, task_id, verified,
  retry_count, duration_s, failure, circuit_breaker_cause, agent_id,
  fleet_id, backlog_lint, skills_injected, tokens always null. `load_metrics` /
  `save_metrics` tolerate missing/corrupt JSON. Tests in `tests/test_metrics.py`.
- Per-iteration ledger capture (`loop.Runner`): after each iteration appends an
  `IterationLedgerRow` to `RunResult.ledger_rows`; task_id from
  `_task_from_rationale` or current_task; retry_count = prior rows in this run
  with the same task_id; on circuit breaker, last N rows get
  `circuit_breaker_cause=consecutive_failures:N`. `Runner(..., fleet_id="")`
  for solo runs (ST5 wires fleet). Rows held until ST4 retrospective rollup.
  Tests in `tests/test_loop.py`.
- Backlog lint on agent edits (`lint.kelix_proposed_edits`, `lint_backlog_edits`,
  `loop.Runner._backlog_lint_if_dirty`): when `.kelix/backlog.md` differs from
  the pre-iteration snapshot, lint only kelix `proposed` tasks that were added
  or had details/rationale/deps changed; aggregate `{rule_id: count}` onto the
  iteration's `IterationLedgerRow.backlog_lint`. Tests in `tests/test_lint.py`
  and `tests/test_loop.py`.
- Metrics rollup at retrospective (`metrics.append_run_metrics`, `metrics_path`):
  after `write_retrospective` in `loop.Runner._finish`, merge `RunResult.ledger_rows`
  into `.kelix/memory/loop-metrics.json` (append, never clobber prior runs).
  Optional `fleet_summary` arg reserved for ST5. File is in `RUNNER_BOOKKEEPING`
  alongside episodes.jsonl. Tests in `tests/test_loop.py` and `tests/test_metrics.py`.
- Planning guide lives in `docs/planning.md` (plan-first flow, roadmap→phase→task
  hierarchy, STATE.md schema, lint, phase gate, waves, flat-backlog quick path).
  Linked from README Documentation and `docs/index.md`. `kelix init` writes
  `.kelix/roadmap.md` from `ROADMAP_TEMPLATE` in `cli.py` when absent; never
  overwrites an existing roadmap. Tests in `tests/test_prompt.py`.
- OWNER PRINCIPLE (communication): good input in, good output out — slop in,
  slop out. All owner-facing text this project produces (backlog tasks, PRD
  templates, docs, prompts, retrospectives) must be precise and legible to
  both a fresh agent and a human on first read, without bloating what gets
  re-read every iteration. The input contract is codified in
  `docs/writing-for-the-loop.md`; when writing or revising tasks/docs,
  follow it — concrete nouns, stated acceptance, one iteration per task, no
  unfalsifiable adjectives.
- OWNER DIRECTIVES (D16, binding on all iterations): (1) planning asks the
  owner structured questions before drafting — never guess a decision the
  owner would want to make; (2) MCP and skills PLUMBING are FROZEN — keep
  them green, add nothing; skill LEARNING (acquisition that fires, measured
  efficacy) is in scope and lives in milestone v0.3 T-SKILLS (D17);
  (3) context quality carries half the value —
  when trading effort, prefer improving what gets injected into prompts
  over adding features; (4) audacity: prefer the task that pushes a
  boundary (self-tuning, self-planning) over routine plumbing when both
  are eligible — anyone can build an app; the point is a loop that thinks.

## Run 20260702-002215 (completed)
4 iterations, 4 verified. Clean run.

## Run 20260702-003053 (completed)
4 iterations, 3 verified. Failures: verification failed.

## Run 20260702-022639 (max_iterations)
10 iterations, 10 verified. Clean run.

## Run 20260702-103424 (circuit_breaker)
2 iterations, 0 verified. Failures: verification failed; verification failed.

## Run 20260702-104227 (max_iterations)
10 iterations, 10 verified. Failures: agent exit 124 (timeout).
