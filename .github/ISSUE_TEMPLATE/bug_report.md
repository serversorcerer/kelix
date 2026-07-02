---
name: Bug report
about: Something in Kelix doesn't work as documented
labels: bug
---

## Describe the bug

A clear and concise description of what the bug is.

## To reproduce

Steps to reproduce the behavior:

1. `kelix init` / config in `.kelix/kelix.toml` (paste relevant sections)
2. Command run (e.g. `kelix run --max-iterations 5`)
3. What happened

If possible, reproduce with the **mock adapter** (`adapter = "mock"`) so the
report doesn't depend on Kiro or API keys.

## Expected behavior

What you expected to happen.

## Logs / artifacts

Relevant output from the run — e.g. loop output, files under `.kelix/runs/`,
or the diagnosis written by the circuit breaker. **Please check for secrets
before pasting.**

## Environment

- Kelix version: (e.g. 0.1.0)
- Python version: (`python --version`)
- OS:
- Agent adapter: (kiro / cmd / mock)

## Additional context

Anything else that helps (fleet mode? tracker sync enabled? worktree vs
branch isolation?).

> **Security issues:** do not file them here — see [SECURITY.md](../../SECURITY.md).
