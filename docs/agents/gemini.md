# Gemini CLI integration guide

Kelix drives the [Gemini CLI](https://google-gemini.github.io/gemini-cli/) headlessly
for each loop iteration — a fresh process, static prompt, all state on disk.

**Not Kelix CI-tested — community corrections welcome.** The command below
matches Kelix's `gemini` named preset (`src/kelix/config.py`) and upstream
headless docs as of 2026-07; Kelix has not run a dogfood proof on this backend.
If your install uses different approval flags or auth env vars, please open a PR.

## The headless adapter

Each iteration Kelix starts one non-interactive Gemini CLI process with the
assembled prompt on the command line:

```bash
gemini -p "<prompt>" --yolo
```

- `-p` (or `--prompt`) runs headless — no interactive TUI, response on stdout
  ([headless docs](https://google-gemini.github.io/gemini-cli/docs/cli/headless.html)).
- `--yolo` auto-approves tool actions (file edits, shell commands) without
  confirmation prompts — required when nobody is at the keyboard. Kelix still
  enforces its own rails (worktree isolation, command denylist, secret scrubbing,
  verify gate).
- Kelix substitutes `{prompt}` from the assembled iteration prompt.

Upstream also documents `--approval-mode auto_edit` as a less aggressive
alternative to `--yolo`. Override `command` if you prefer that trade-off.

Use the `gemini` named preset so Kelix fills in the template automatically, or
set `adapter = "cmd"` with the same command string if you prefer explicit
control.

## Configure kelix.toml

```toml
[agent]
adapter = "gemini"                  # resolves to the upstream-sourced template
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
command = "gemini -p {prompt} --yolo"
```

You can override `command` while keeping `adapter = "gemini"` if you need
`--approval-mode auto_edit`, `--output-format json`, `--model`, or a wrapper
script.

Optional: raise `inactivity_timeout_seconds` (default 300) if Gemini finishes
work but the process hangs before exit — Kelix's adapter timeout reaps stuck
processes while keeping verified commits.

## Install

Install the Gemini CLI globally via npm (requires Node.js):

```bash
npm install -g @google/gemini-cli
```

Confirm the binary is on `PATH`:

```bash
gemini --version
```

See [Get Started](https://google-gemini.github.io/gemini-cli/docs/get-started/)
for other deployment options.

## Auth

Headless runs need credentials in the environment — Kelix never reads or stores
API keys.

**Recommended for CI and overnight runs (API key):**

```bash
export GEMINI_API_KEY=your_api_key_here
```

Obtain a key from [Google AI Studio](https://aistudio.google.com/apikey). Gemini
CLI also loads variables from `.gemini/.env` in the project or home directory
([auth docs](https://google-gemini.github.io/gemini-cli/docs/get-started/authentication.html)).

**Google account (interactive setup once per machine):**

```bash
gemini
# Select "Login with Google" when prompted
```

Cached credentials may work for later headless runs on the same machine.

**Vertex AI (enterprise / GCP):**

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
# ADC via gcloud, or GOOGLE_APPLICATION_CREDENTIALS for service accounts
```

Unset `GEMINI_API_KEY` when using Vertex ADC so credentials do not conflict.

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

# Point kelix.toml at Gemini (or edit the init template):
#   [agent]
#   adapter = "gemini"

export GEMINI_API_KEY=...   # or gemini login interactively once
kelix run --max-iterations 25
```

After the run, inspect verified commits on the run branch, retrospectives under
`.kelix/runs/<run-id>/`, and durable notes in `.kelix/memory/project.md`.

For a flat backlog without planning, skip `kelix plan` and write tasks directly
in `.kelix/backlog.md` — see [quickstart](../quickstart.md).

## Quirks

- **`--yolo` is powerful.** It auto-approves every tool call — fine inside a
  Kelix worktree with verify gates, risky on production checkouts. Prefer
  `--approval-mode auto_edit` in custom `command` if you want file writes without
  full shell auto-approval.
- **Non-interactive auth.** Headless mode exits with an error if no API key,
  cached login, or Vertex credentials are available — set env vars before
  `kelix run`.
- **JSON on stdout.** Add `--output-format json` only in custom `command` if you
  need structured output; Kelix captures combined stdout/stderr for transcripts.
- **No Kiro-only features.** Spec import (`kelix init --from-spec`), the
  `.kiro/` integration package, and MCP registration live in
  [docs/kiro.md](../kiro.md) only.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `gemini: command not found` | CLI not installed or not on PATH | `npm install -g @google/gemini-cli`; ensure npm global bin is on PATH |
| Auth errors before first iteration | Missing `GEMINI_API_KEY` / no cached login | Export key or run `gemini` once interactively |
| Iterations verify green but no file changes | Approval prompts blocked edits | Use `adapter = "gemini"` preset (`--yolo`) or `--approval-mode auto_edit` |
| Vertex "API keys not supported" | Org restricts API keys | Use service account + `GOOGLE_APPLICATION_CREDENTIALS` or ADC |
| Agent killed mid-task, exit 143 | Hit `timeout_seconds` or inactivity watchdog | Raise timeouts; check transcript under `.kelix/runs/` |
| Wrong npm package | Installed unrelated `gemini` package | `npm uninstall -g gemini`; `npm install -g @google/gemini-cli` |

For Kelix-side failures (circuit breaker, spec gate, backlog lint), run
`kelix status` and read the latest retrospective under `.kelix/runs/`.
