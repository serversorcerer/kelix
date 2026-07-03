# Claude Code integration guide

Kelix drives the [Claude Code CLI](https://code.claude.com/docs/en/headless)
headlessly for each loop iteration — a fresh process, static prompt, all state
on disk.

**Not Kelix CI-tested — community corrections welcome.** The command below
matches Kelix's `claude` named preset (`src/kelix/config.py`) and upstream
headless docs as of 2026-07; Kelix has not run a dogfood proof on this backend.
If your install uses different flags or permission modes, please open a PR.

## The headless adapter

Each iteration Kelix starts one non-interactive Claude Code process with the
assembled prompt on the command line:

```bash
claude --bare --permission-mode dontAsk -p "<prompt>"
```

- `--bare` skips auto-discovery of hooks, skills, plugins, MCP servers, and
  project `CLAUDE.md` — recommended for reproducible CI and unattended runs
  ([headless docs](https://code.claude.com/docs/en/headless)).
- `--permission-mode dontAsk` auto-denies tool calls that would prompt — required
  when nobody is at the keyboard. Kelix still enforces its own rails (worktree
  isolation, command denylist, secret scrubbing, verify gate).
- `-p` (or `--print`) passes the prompt inline (Kelix substitutes `{prompt}` from
  the assembled iteration prompt).

If file edits are denied under `dontAsk`, try `--permission-mode acceptEdits`
instead (upstream allows writes without prompts for common filesystem commands).
Document any change in a PR so the preset can be updated.

Use the `claude` named preset so Kelix fills in the template automatically, or
set `adapter = "cmd"` with the same command string if you prefer explicit
control.

## Configure kelix.toml

```toml
[agent]
adapter = "claude"                  # resolves to the upstream-sourced template
timeout_seconds = 1800              # per-iteration wall clock (seconds)

[verify]
commands = ["pytest -q", "ruff check ."]

[loop]
max_iterations = 25
```

The preset expands internally to:

```toml
[agent]
adapter = "cmd"
command = "claude --bare --permission-mode dontAsk -p {prompt}"
```

You can override `command` while keeping `adapter = "claude"` if you need
`acceptEdits`, extra `--allowedTools`, or a wrapper script.

Optional: raise `inactivity_timeout_seconds` (default 300) if Claude finishes
work but the process hangs before exit — Kelix's adapter timeout reaps stuck
processes while keeping verified commits.

## Install

Install the native Claude Code CLI (recommended; no Node.js required):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

On Windows PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Confirm the binary is on `PATH`:

```bash
claude --version
```

If you previously installed via npm (`npm install -g @anthropic-ai/claude-code`),
migrate with `claude install` and remove the old package so `which claude`
points at the native binary — see
[Quickstart](https://code.claude.com/docs/en/quickstart).

Alternatives: Homebrew (`brew install --cask claude-code`) and WinGet
(`winget install Anthropic.ClaudeCode`) — these do not auto-update.

## Auth

Headless runs need credentials in the environment — Kelix never reads or stores
API keys.

**Recommended for CI and overnight runs:**

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

**OAuth token (long-lived CI secret):**

```bash
claude setup-token   # once interactively
export CLAUDE_CODE_OAUTH_TOKEN=...
```

Bare mode skips keychain reads, so environment variables are required for
unattended runs ([headless docs](https://code.claude.com/docs/en/headless)).

**Interactive setup (once per machine):**

```bash
claude auth login
```

## Worked example: init → plan → run

From a git repository root:

```bash
pipx install kelix
# until the first PyPI release lands:
# pipx install git+https://github.com/serversorcerer/kelix.git
cd your-repo

kelix init
# Edit GOAL.md, then draft a plan:
kelix plan --goal-file GOAL.md
kelix lint
# Promote chosen tasks from status: proposed → status: ready in .kelix/backlog.md

# Point kelix.toml at Claude (or edit the init template):
#   [agent]
#   adapter = "claude"

export ANTHROPIC_API_KEY=...   # or claude auth login
kelix run --max-iterations 25
```

After the run, inspect verified commits on the run branch, retrospectives under
`.kelix/runs/<run-id>/`, and durable notes in `.kelix/memory/project.md`.

For a flat backlog without planning, skip `kelix plan` and write tasks directly
in `.kelix/backlog.md` — see [quickstart](../quickstart.md).

## Quirks

- **Permission mode trade-off.** `dontAsk` is strict (good for safety); `acceptEdits`
  is often needed for unattended file writes. The Kelix preset uses `dontAsk` —
  override `command` if iterations verify green but produce no diffs.
- **`--bare` vs full context.** Without `--bare`, Claude loads project hooks,
  skills, and MCP — fine interactively, noisy for reproducible loops.
- **No Kiro-only features.** Spec import (`kelix init --from-spec`), the
  `.kiro/` integration package, and MCP registration live in
  [docs/kiro.md](../kiro.md) only.
- **npm vs native binary.** Stale npm shims can shadow the native install;
  run `which -a claude` if behavior differs from docs.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `claude: command not found` | CLI not installed or not on PATH | Re-run native install; ensure `~/.local/bin` is on PATH |
| Auth errors before first iteration | Missing `ANTHROPIC_API_KEY` / token | Export key or run `claude auth login` |
| Iterations verify green but no file changes | `dontAsk` denied edits | Switch to `--permission-mode acceptEdits` in custom `command` |
| Agent killed mid-task, exit 143 | Hit `timeout_seconds` or inactivity watchdog | Raise timeouts; check transcript under `.kelix/runs/` |
| Deprecation warning about npm | Old global npm install still on PATH | `claude install`; `npm uninstall -g @anthropic-ai/claude-code` |

For Kelix-side failures (circuit breaker, spec gate, backlog lint), run
`kelix status` and read the latest retrospective under `.kelix/runs/`.
