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

## Run 20260702-002215 (completed)
4 iterations, 4 verified. Clean run.

## Run 20260702-003053 (completed)
4 iterations, 3 verified. Failures: verification failed.
