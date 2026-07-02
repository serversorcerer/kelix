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
- Prioritization rubric for backlog authoring and selection lives in
  `docs/prioritization.md` (owner-first, priority bands, decomposition/blocked rules).

## Run 20260702-002215 (completed)
4 iterations, 4 verified. Clean run.
