# Codex integration guide

Kelix drives the [OpenAI Codex CLI](https://developers.openai.com/codex/cli)
headlessly for each loop iteration — a fresh process, static prompt, all state
on disk.

**Not Kelix CI-tested — community corrections welcome.** The command below
matches Kelix's `codex` named preset (`src/kelix/config.py`) and upstream
non-interactive docs as of 2026-07; Kelix has not run a dogfood proof on this
backend. If your install uses different sandbox or approval flags, please open
a PR.

## The headless adapter

Each iteration Kelix starts one non-interactive Codex process with the assembled
prompt as the final argument:

```bash
codex exec -s workspace-write "<prompt>"
```

- `exec` runs Codex without the interactive TUI — required for CI and unattended
  loops ([non-interactive docs](https://developers.openai.com/codex/noninteractive)).
- `-s workspace-write` (same as `--sandbox workspace-write`) lets Codex edit
  files inside the checked-out repository. The default `read-only` sandbox
  cannot apply changes Kelix would verify.
- The prompt is passed as a positional argument (Kelix substitutes `{prompt}`
  from the assembled iteration prompt).

For fully unattended runs, upstream recommends also setting
`--ask-for-approval never` so Codex never waits for keyboard approval on
network access or risky commands. Kelix's preset omits it for compatibility
with saved CLI profiles; override `command` if iterations hang waiting for input.

Use the `codex` named preset so Kelix fills in the template automatically, or
set `adapter = "cmd"` with the same command string if you prefer explicit
control.

## Configure kelix.toml

```toml
[agent]
adapter = "codex"                   # resolves to the upstream-sourced template
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
command = "codex exec -s workspace-write {prompt}"
```

You can override `command` while keeping `adapter = "codex"` if you need
`--ask-for-approval never`, `--json` output, `--ephemeral` sessions, or a
wrapper script.

Optional: raise `inactivity_timeout_seconds` (default 300) if Codex finishes
work but the process hangs before exit — Kelix's adapter timeout reaps stuck
processes while keeping verified commits.

## Install

Install the Codex CLI on macOS or Linux:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

On Windows PowerShell:

```powershell
irm https://chatgpt.com/codex/install.ps1 | iex
```

Alternatives:

```bash
npm install -g @openai/codex    # requires Node.js 22+; package is @openai/codex
brew install --cask codex       # macOS
```

Confirm the binary is on `PATH`:

```bash
codex --version
```

Do not install the unscoped `codex` npm package — it is unrelated to OpenAI.
See the [Codex CLI repo](https://github.com/openai/codex) for platform binaries.

## Auth

Headless runs need credentials in the environment — Kelix never reads or stores
API keys.

**Recommended for CI and overnight runs (`codex exec` only):**

```bash
export CODEX_API_KEY=your_api_key_here
```

Set the variable only for the Kelix process (or the single `codex exec` child),
not as a job-wide secret when untrusted repo code runs in the same environment
([non-interactive auth guidance](https://developers.openai.com/codex/noninteractive)).

**ChatGPT subscription (interactive setup once per machine):**

```bash
codex login
```

**API key via CLI (persists for later runs):**

```bash
printenv OPENAI_API_KEY | codex login --with-api-key
# or: codex login --api-key
```

Check status with `codex login status`.

## Worked example: init → plan → run

From a git repository root (Codex requires a Git checkout):

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

# Point kelix.toml at Codex (or edit the init template):
#   [agent]
#   adapter = "codex"

export CODEX_API_KEY=...   # or codex login
kelix run --max-iterations 25
```

After the run, inspect verified commits on the run branch, retrospectives under
`.kelix/runs/<run-id>/`, and durable notes in `.kelix/memory/project.md`.

For a flat backlog without planning, skip `kelix plan` and write tasks directly
in `.kelix/backlog.md` — see [quickstart](../quickstart.md).

## Quirks

- **Git repository required.** Codex refuses to run outside a Git checkout by
  default. Kelix worktrees satisfy this; bare directories need `git init` first.
- **Sandbox vs approval.** `workspace-write` allows repo edits but may still
  prompt for network or out-of-workspace actions — add
  `--ask-for-approval never` in a custom `command` for overnight runs.
- **Deprecated `--full-auto`.** Upstream prints a warning; prefer explicit
  `-s workspace-write` (Kelix preset already does).
- **Progress on stderr, final message on stdout.** Kelix captures combined
  output; long runs may look quiet until Codex finishes a turn.
- **No Kiro-only features.** Spec import (`kelix init --from-spec`), the
  `.kiro/` integration package, and MCP registration live in
  [docs/kiro.md](../kiro.md) only.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `codex: command not found` | CLI not installed or not on PATH | Re-run install; ensure npm global bin or `~/.local/bin` is on PATH |
| Auth errors before first iteration | Missing `CODEX_API_KEY` / no login | `export CODEX_API_KEY=...` or `codex login` |
| "Not inside a git repository" | Running outside a checkout | `git init` or run from a cloned repo / Kelix worktree |
| Iterations verify green but no file changes | Default read-only sandbox | Use `adapter = "codex"` preset or `-s workspace-write` in custom `command` |
| Agent hangs mid-task waiting for input | Approval prompts in headless mode | Add `--ask-for-approval never` to custom `command` |
| Agent killed mid-task, exit 143 | Hit `timeout_seconds` or inactivity watchdog | Raise timeouts; check transcript under `.kelix/runs/` |
| Wrong package after npm install | Installed unscoped `codex` | `npm uninstall -g codex`; `npm install -g @openai/codex` |

For Kelix-side failures (circuit breaker, spec gate, backlog lint), run
`kelix status` and read the latest retrospective under `.kelix/runs/`.
