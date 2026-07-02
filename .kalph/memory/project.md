# Project memory

Durable facts about this repo for future iterations.

- This repo is Kalph itself: a Python 3.11+ stdlib-only package in `src/kalph/`,
  tests in `tests/` (pytest), lint with ruff (line length 100). Core modules:
  config.py, adapters.py, prompt.py, loop.py, verify.py, memory.py,
  security.py, gitutil.py, cli.py.
- Verification gate: `pytest -q` and `ruff check src tests` must both pass.
  Run them before claiming any task done.
- Backlog tasks are parsed by `src/kalph/backlog.py` (`parse_backlog`,
  `serialize_backlog`, `select_next`). Task lines use pipe-separated fields;
  owner tasks outrank kalph at equal selection time regardless of priority number.
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
  Use `tmp_path` fixtures; never write to the real `.kalph/` directory in tests.
- Security module unit tests live in `tests/test_security.py` (scrub/contains_secret
  for token shapes, CommandPolicy deny/allow/allow_only/deny_extra). No tmp_path
  needed — pure functions.
- Decisions already made are in DECISIONS.md; do not re-litigate them.
- GOTCHA: never run `pip install -e .` inside a run worktree — it repoints the
  shared venv's editable install at the worktree, which breaks `kalph` on the
  main checkout after the worktree is removed. The verify commands already set
  PYTHONPATH=src; that is sufficient. (Learned from run 20260702-002215.)
- Prioritization rubric for backlog authoring and selection lives in
  `docs/prioritization.md` (owner-first, priority bands, decomposition/blocked rules).
- PR flow lives in `src/kalph/pr.py` (`open_pr`, `build_pr_title`, `build_pr_body`).
  `kalph run --pr` opens a GitHub PR after `completed` or `max_iterations` runs;
  refuses main/master/empty branches, pushes with `git push -u origin <branch>`,
  never `--force`. Returns None (log-and-skip) on any subprocess failure.
- Fleet claims live in `src/kalph/claims.py` (`.kalph/fleet/claims/<task-id>.json`).
  `claim_task` uses `O_CREAT|O_EXCL` for new claims; stale claims (heartbeat older
  than `stale_after_s`, default 900s) are reclaimable via temp-file + `os.replace`.
  Tests in `tests/test_claims.py` cover concurrent winners, stale reclaim, release,
  and wrong-agent guardrails.
- STATE.md spine lives in `src/kalph/state.py` (`State` dataclass, `load_state`,
  `write_state`). Parser is tolerant: missing file -> None, malformed lines skipped,
  optional space after colon in field bullets, `(none)` blocker treated as empty.
  Tests in `tests/test_state.py`. The runner (`loop.py`) tracks state in memory
  through a run (current_task from pre_iteration hook or "selecting", last_task
  from rationale, done/total from parse_backlog, last_verified_commit on verified
  iterations) and writes `.kalph/STATE.md` once in `_finish` before the
  retrospective checkpoint — not mid-iteration. STATE.md is intentionally absent
  from `RUNNER_BOOKKEEPING` excludes so the retrospective commit ships it.
  The prompt's first data slot is `{{STATE}}` in `prompt.py` (budget
  `[memory].state_max_chars`, default 1200); `loop.py` `_gather_context` loads
  via `load_state()` and injects the file text, falling back to
  "(no state file — flat-backlog mode)" when absent.
- Roadmap parser lives in `src/kalph/roadmap.py` (`Milestone`, `Phase`, `Req`,
  `Roadmap`, `parse_roadmap`, `load_roadmap`, `reqs_for(phase_id)`). Format:
  `## Milestone <id> — <title>`, `### Phase <id> — <title>`, optional
  `Outcome:` line after phase header, `- REQ-X: text` bullets. Prose and
  malformed lines are skipped. Tests in `tests/test_roadmap.py` including the
  real `.kalph/roadmap.md` fixture.
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
