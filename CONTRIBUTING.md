# Contributing to Kalph

Thanks for your interest in Kalph — the Ralph loop, rebuilt for Kiro. This
guide covers everything you need to get a change from idea to merged PR.

## Development setup

Kalph's core is **Python 3.11+, stdlib-only**. The only development
dependencies are `pytest` and `ruff`. No API keys are needed: tests run
against a mock agent adapter.

```bash
git clone https://github.com/kalph-dev/kalph.git
cd kalph
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests and lint

```bash
pytest -q                  # full test suite (mock agent, no network, no keys)
ruff check src tests       # lint
```

Both must be green before a PR is reviewed — they are also Kalph's own
verification gate when it builds itself.

## Project layout

```
src/kalph/
  loop.py          # the core iteration loop
  backlog.py       # backlog parsing and prioritization
  memory.py        # layered memory (project / episodic / skills)
  prompt.py        # the static iteration prompt
  adapters.py      # agent adapters (kiro | cmd | mock)
  verify.py        # verification gate (re-runs your commands)
  security.py      # command denylist, secret scrubbing
  gitutil.py       # worktree isolation, checkpoints, branch protection
  pr.py            # PR creation via gh
  fleet.py         # fleet mode orchestration
  claims.py        # atomic task claims for fleets
  kiro.py          # Kiro integration (steering, spec import)
  mcp_server.py    # MCP server so Kiro can drive Kalph by tool call
  sync/            # tracker sync (Linear), inbound sanitization
  cli.py, config.py
tests/             # one test module per source module, plus drills
docs/              # concept, security model, fleet, prioritization, ...
integrations/kiro/ # steering files, custom agent config
```

## Coding conventions

- **Stdlib-only core.** Do not add runtime dependencies to `src/kalph/`.
  If a feature seems to need a third-party library, raise it in an issue
  first — the answer is usually a smaller feature.
- **Tests use the mock adapter.** `tests/conftest.py` provides helpers:
  `make_repo(path)` creates a throwaway git repo, and
  `write_mock_script(mock_dir, name, body)` writes a shell script that
  stands in for the agent. Tests must never require network access or
  credentials.
- **Keep the four Ralph invariants intact** (see
  `docs/research/ralph-invariants.md`): static prompt, fresh stateless
  agent process per iteration, stop sentinel, all state in files and git.
  Concretely: **never add long-lived sessions, and never add RPC between
  agents** — fleet agents coordinate only through files (claims, mailbox,
  shared skills) and git.
- **Safety is code, not docs.** Changes touching `security.py`, the prompt,
  or git handling need tests (see `tests/test_denylist_regression.py` and
  `tests/test_injection_drill.py` for the pattern).
- Match the existing style; `ruff` is the arbiter of formatting disputes.

## Commits and pull requests

- Small, focused commits with imperative subject lines
  (`Add circuit-breaker diagnosis to run summary`), body explaining *why*
  when it isn't obvious.
- One logical change per PR. Fill in the PR template, including the
  verification checkboxes.
- PRs target `main`; nothing lands on `main` directly — humans review and
  merge. This mirrors how Kalph itself operates.
- Update docs in the same PR when behavior changes.

## Kalph dogfoods itself

Kalph is built by its own loop. `PLAN.md` holds the phased plan and
`DECISIONS.md` records the choices made along the way — read both before
proposing large changes, as many "why is it like this?" questions are
answered there. Backlog-worthy ideas can be filed as issues or added as
tasks in `.kalph/backlog.md` in a PR.

## Reporting issues

- Bugs and feature requests: use the issue templates.
- Security issues: **do not open a public issue** — see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
