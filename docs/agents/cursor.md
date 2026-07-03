# Cursor integration guide

Kelix drives the [Cursor CLI](https://cursor.com/docs/cli/headless) headlessly
for each loop iteration — a fresh process, static prompt, all state on disk.

**Kelix-verified invocation.** The command below is what Kelix used for the
Phase 8 dogfood proof (`docs/proof/final-report.md`, 12/12 tasks verified)
and for self-hosting runs on this repository (DECISIONS.md D8). Upstream docs
sometimes show the binary as `agent`; on Kelix build machines the verified
invocation is `cursor-agent --force -p "<prompt>"`.

## The headless adapter

Each iteration Kelix starts one non-interactive Cursor agent process with the
assembled prompt on the command line:

```bash
cursor-agent --force -p "<prompt>"
```

- `--force` lets the agent edit files without interactive approval — required
  for unattended runs. Kelix still enforces its own rails (worktree isolation,
  command denylist, secret scrubbing, verify gate).
- `-p` passes the prompt inline (Kelix substitutes `{prompt}` from the
  assembled iteration prompt).

Use the `cursor` named preset so Kelix fills in the template automatically,
or set `adapter = "cmd"` with the same command string if you prefer explicit
control.

## Configure kelix.toml

```toml
[agent]
adapter = "cursor"                  # resolves to the Kelix-verified template
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
command = "cursor-agent --force -p {prompt}"
```

You can override `command` while keeping `adapter = "cursor"` if your install
uses a different binary name but the same flags.

Optional: raise `inactivity_timeout_seconds` (default 300) if your agent
finishes work but hangs before exit — fleet session 2 in the dogfood proof
needed a manual kill when the process outlived its useful output (DECISIONS.md
D13); Kelix's adapter timeout covers this unattended.

## Install

Install the Cursor CLI on macOS, Linux, or WSL:

```bash
curl https://cursor.com/install -fsS | bash
```

On Windows PowerShell:

```powershell
irm 'https://cursor.com/install?win32=true' | iex
```

Confirm the agent binary is on `PATH`:

```bash
cursor-agent --help
# or: agent --help  (some installs expose only `agent`)
```

If only `agent` is available, set a custom command in kelix.toml (see above).

See [Cursor CLI installation](https://cursor.com/help/integrations/cli) for
updates.

## Auth

Headless runs need credentials in the environment — Kelix never reads or stores
API keys.

**Recommended for CI and overnight runs:**

```bash
export CURSOR_API_KEY=your_api_key_here
```

Create keys from your Cursor account settings or, for teams, a
[service account](https://cursor.com/docs/account/enterprise/service-accounts).

**Interactive setup (once per machine):**

```bash
agent auth
```

If auth fails with "invalid API key" on a network error, check VPN/firewall
access to Cursor endpoints first — the CLI sometimes misreports connectivity
issues as bad keys ([CLI help](https://cursor.com/help/integrations/cli)).

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

# Point kelix.toml at Cursor (or edit the init template):
#   [agent]
#   adapter = "cursor"

export CURSOR_API_KEY=...   # or agent auth login
kelix run --max-iterations 25
```

After the run, inspect verified commits on the run branch, retrospectives under
`.kelix/runs/<run-id>/`, and durable notes in `.kelix/memory/project.md`.

For a flat backlog without planning, skip `kelix plan` and write tasks directly
in `.kelix/backlog.md` — see [quickstart](../quickstart.md).

## Quirks

- **Binary name.** Upstream headless docs use `agent`; Kelix dogfood and this
  repo's self-hosting config use `cursor-agent`. Both may exist on one machine;
  the preset targets `cursor-agent`.
- **`--force` is mandatory for unattended file edits.** Without it, print mode
  may analyze but not apply changes — iterations would look like no-ops.
- **Process hang after success.** The agent occasionally finishes commits but
  does not exit promptly; Kelix's `timeout_seconds` and
  `inactivity_timeout_seconds` reap stuck processes while keeping verified
  work (see D13).
- **No Kiro-only features.** Spec import (`kelix init --from-spec`), the
  `.kiro/` integration package, and MCP registration live in
  [docs/kiro.md](../kiro.md) only.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `agent command not found: cursor-agent` | CLI not installed or not on PATH | Re-run install; symlink `agent` → `cursor-agent`, or set `[agent] command` to your binary |
| Auth errors before first iteration | Missing `CURSOR_API_KEY` / no login | `export CURSOR_API_KEY=...` or `agent auth` |
| Iterations verify green but no file changes | Missing `--force` | Use `adapter = "cursor"` preset or add `--force` to custom command |
| Agent killed mid-task, exit 143 | Hit `timeout_seconds` or inactivity watchdog | Raise timeouts; check transcript under `.kelix/runs/` |
| "Invalid API key" on good key | Network/VPN blocking Cursor | Test connectivity; see Cursor CLI auth docs |

For Kelix-side failures (circuit breaker, spec gate, backlog lint), run
`kelix status` and read the latest retrospective under `.kelix/runs/`.
