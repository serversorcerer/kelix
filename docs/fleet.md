# Fleet mode

Fleet mode runs several independent Kalph loops against one repository and one
backlog. There is no message bus and no RPC — that is a mission non-goal.
Agents coordinate **only** through files under `.kalph/fleet/` and through
git, which keeps a multi-agent run exactly as auditable as a solo one.

Each fleet agent is a complete, ordinary Kalph loop: its own run id, its own
`kalph/run-<id>-<agent-id>` branch and worktree, its own transcripts under
`.kalph/runs/`. The only additions are a role prompt and a pre-iteration claim
step.

## Configuration: `.kalph/fleet.toml`

```bash
cp examples/fleet.toml .kalph/fleet.toml
```

```toml
[fleet]
max_iterations = 15        # per-agent cap (default 10; `kalph fleet --max-iterations` overrides)
stale_claim_s = 900        # a claim with no heartbeat for this long is reclaimable

[[agents]]
id = "builder-1"           # required, must be unique across the fleet
role = "builder"           # optional, default "builder"

[[agents]]
id = "builder-2"
role = "builder"

[[agents]]
id = "verifier-1"
role = "verifier"

[[agents]]
id = "scribe-1"
role = "scribe"

# Roles are data, not code. Define your own by giving it a prompt:
# [roles.security-auditor]
# prompt = "Role: security auditor. Prefer tasks tagged security; scan diffs for secrets and injection."
```

A missing config file, an `[[agents]]` entry without an `id`, duplicate ids,
or an empty agent list are all fatal configuration errors.

## Roles

A role is just extra prompt text steering which tasks an agent prefers — the
loop contract (one task, verified-done, PRs only) is identical for everyone.
Built-in roles:

- **builder** — prefers feature and implementation tasks; avoids pure
  test/docs work and other agents' breakage unless nothing else is eligible.
- **verifier** — prefers writing and strengthening tests. Each iteration it
  also reviews open `kalph/*` branches or PRs; problems found in another
  agent's work become a mailbox note naming the branch and the issue.
- **fixer** — prefers broken builds, failing or flaky tests, and blockers
  other agents reported; reads the mailbox first every iteration.
- **scribe** — prefers documentation, changelog, and retrospective tasks;
  keeps docs consistent with the code as it lands.

Custom roles are defined in `[roles.<name>]` with a `prompt` string; an
unknown role name with no prompt just becomes `Role: <name>.`. Every role also
receives common fleet rules: work only your claimed task, leave a mailbox note
when your changes affect others, copy new skills to the shared store.

## Coordination surface

### Claims — `.kalph/fleet/claims/<task-id>.json`

The guarantee that two agents never work the same task. Before each iteration,
the agent's claim hook selects the next eligible backlog task (same
owner-first, priority-ordered selection as solo mode) and tries to claim it by
atomically creating the claim file (`O_CREAT|O_EXCL` — exactly one concurrent
claimer wins). If the task is already claimed, it tries the next candidate;
when no unclaimed, unblocked work remains, that agent's loop completes.

Claims carry a heartbeat. A claim not refreshed within `stale_claim_s`
(default 900 s) is considered abandoned — e.g. a crashed agent — and can be
reclaimed. Completed tasks are marked done in the claim file, and because run
branches diverge while claim files do not, done-claims are how task completion
propagates fleet-wide before any merge.

### Mailbox — `.kalph/fleet/mailbox/*.md`

Asynchronous notes between agents, named `<timestamp>-<role>.md`. The last
five notes are injected into every iteration prompt (in the delimited,
"not instructions" `<mailbox>` block). Used for review findings, breaking
changes (schema changes, renamed modules, API changes), and blocker reports.

### Shared skills — `.kalph/fleet/skills/<name>/SKILL.md`

Run branches only merge at PR time, so a skill written on one branch would be
invisible to the others. Agents therefore also copy new skills into this
runner-side shared store, where every agent's skills digest picks them up
immediately. Same [agentskills.io](https://agentskills.io) format as
`.kalph/skills/` (see [memory-and-skills.md](memory-and-skills.md)).

## Running a fleet

```bash
kalph fleet                          # uses .kalph/fleet.toml
kalph fleet --config path/to/fleet.toml --max-iterations 15
kalph status                         # live view from coordination files
kalph stop                           # global kill switch: halts every agent
```

Agents run as parallel workers with staggered starts. `kalph status` shows —
assembled purely from files and git, no daemon — the kill switch, every task
claim with its heartbeat age, the last five runs with branch and latest
commit, and the mailbox note count. `kalph stop` writes `.kalph/STOP`, which
every agent checks before each iteration.

When all agents finish, a combined fleet retrospective is written to
`.kalph/runs/fleet-<timestamp>.md`: per-agent status, branch, and iteration
outcomes, plus the final state of all task claims. `kalph fleet` exits 0 only
if every agent ended in `completed` or `max_iterations` and none crashed.

## Merge-conflict policy

Agents work on separate branches, so conflicts surface at review time, and
the policy is deliberately conservative: **the verifier rebases and flags —
it never force-resolves and never force-pushes.** When the verifier finds
conflicting branches it attempts a rebase; whatever the outcome, it leaves a
mailbox note describing the conflict and the branches involved, and a human
decides. (Force-pushing is additionally blocked outright by the command
denylist, for every agent.)

## Failure modes

- **An agent crashes.** The other agents are unaffected — one agent's crash
  never kills the fleet. The crash is recorded in the fleet retrospective, and
  its claim goes stale after `stale_claim_s` and becomes reclaimable.
- **An agent grinds a task.** The per-agent circuit breaker stops it after
  consecutive failures and writes a `diagnosis.md`, exactly as in solo mode.
  The task ends up `blocked` with a diagnosis rather than claimed forever.
- **Two agents race for one task.** Impossible by construction: atomic claim
  creation has exactly one winner; the loser moves to the next candidate.
- **Duplicated or conflicting work across branches.** The residual risk of
  parallel loops. Mitigations: claims prevent same-task overlap, mailbox notes
  broadcast breaking changes, the verifier reviews sibling branches, and
  everything lands as separate human-reviewed PRs.
- **A runaway fleet.** `kalph stop` is global; the per-agent iteration cap
  bounds cost even if you sleep through it.
