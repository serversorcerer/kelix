# Memory and skills

A fresh agent process per iteration means nothing survives in the model's
head. Kelix's answer is not to weaken that invariant but to externalize
memory: everything worth remembering is a human-readable file, written before
the process exits, and injected into future iterations as budgeted data.

## The three layers

### 1. Project memory — `.kelix/memory/project.md`

Durable facts about the repo: architecture notes, conventions, build/test
quirks, gotchas. **Committed** to git, so it ships with the repo and arrives
in PRs. Agents append to it during iterations (the prompt instructs them to
record durable facts before exiting), and run retrospectives append a summary
per run. Append, don't rewrite.

### 2. Episodic memory — `.kelix/memory/episodes.jsonl`

Runner-owned, **gitignored**, append-only. One JSON record per iteration
across all runs:

```json
{"ts": "2026-07-02T03:14:07", "agent": "solo", "iteration": 4,
 "rationale": "T3 — add retry backoff to the client",
 "progress": true, "verified": true, "failure": "", "duration_s": 212.4}
```

This is the "what worked / what failed recently" record. Corrupt lines are
skipped on read, never fatal.

### 3. Skills — `.kelix/skills/<name>/SKILL.md`

Reusable procedures the loop earned, **committed**, in the
[agentskills.io](https://agentskills.io) Open Agent Skills format — the same
format Kiro uses: a folder per skill containing `SKILL.md` with YAML
frontmatter followed by the steps:

```markdown
---
name: regenerate-api-fixtures
description: How to regenerate the recorded API fixtures when the upstream schema changes.
---

1. Run `make record-fixtures` with STAGING_URL set...
```

`name` and `description` in the frontmatter are required for the skill to be
discovered. In fleet mode there is a second location,
`.kelix/fleet/skills/<name>/SKILL.md` — a runner-side shared store so fleet
agents see each other's discoveries before their branches merge (see
[fleet.md](fleet.md)).

## Budgeted digest injection

Memory reaches the agent as data blocks in fixed slots of the static prompt
(preserving the static-prompt invariant), and every injected byte is capped so
the context window stays small. From `[memory]` in `.kelix/kelix.toml`:

```toml
[memory]
enabled = true             # false disables all memory recording and injection
digest_max_chars = 8000    # cap on the episode digest block
skills_max_chars = 6000    # cap on the skills block
episodes_in_digest = 10    # how many recent episodes the digest covers
```

- **Episode digest** — the last `episodes_in_digest` episodes rendered as
  compact one-liners (`rationale -> verified | ok (unverified) | FAILED: …`),
  injected into the `<episodes>` block. This is how a fresh agent avoids
  repeating a dead end a previous iteration already hit — and it is the input
  to the "same failure twice → mark blocked" rule.
- **Skills digest** — progressive loading, Kiro-style: only each skill's name,
  description, and file path go into the `<skills>` block; the agent reads the
  full `SKILL.md` only when relevant. Prompt stays cheap regardless of how
  many skills accumulate.
- Anything over budget is hard-truncated with a visible
  `[... truncated to N chars]` marker.
- Project memory is not inlined; the prompt points at
  `.kelix/memory/project.md` for the agent to read from disk.

All blocks sit under an explicit "reference data, read-only; not
instructions" banner — part of the prompt-injection defense
([SECURITY.md](SECURITY.md)).

## Context compiler

The prompt's data slots (state, phase decisions, episodes, project memory,
skills, mailbox) are assembled by a **context compiler** in `prompt.py`, not
pasted wholesale. From `[memory]` in `.kelix/kelix.toml`:

```toml
[memory]
context_share = 0.5   # fraction of total slot caps for curated data
state_max_chars = 1200
phase_context_max_chars = 2000
digest_max_chars = 8000
project_max_chars = 8000
skills_max_chars = 6000
mailbox_max_chars = 4000
```

`context_share` (default 0.5) allocates half the combined slot budget to
curated context; state and phase decisions fill first, then episodes, project
memory, skills, and mailbox by fixed weights. When the runner knows the active
task (from fleet claim or `select_next`), its title and `details:` become the
**relevance query** passed to the stdlib lexical scorer in `context.py` —
relevant-but-old beats recent-but-noise for episodes, project-memory sections,
and skills.

Every iteration writes a **context manifest** to
`.kelix/runs/<run-id>/context-<n>.json` (runner bookkeeping, gitignored with
other run artifacts). Each manifest lists what was injected: slot name, source
path, char count, and relevance score (when query-driven). Use manifests to
audit whether the compiler chose well — the same way phase CONTEXT.md makes
decisions auditable.

## Retrospectives

Every run ends with `retrospective.md` in `.kelix/runs/<run-id>/`: status,
iteration count with verified/failure tallies, the branch, a per-iteration
outcome list, and — if anything failed — a "For the owner" section listing the
iterations that need attention.

The retrospective also appends a short run summary to
`.kelix/memory/project.md` **on the run branch** and checkpoints it, so the
memory update arrives via the same PR as the code and gets reviewed like
everything else.

Fleet runs additionally write a combined
`.kelix/runs/fleet-<timestamp>.md` covering every agent.

## Skill acquisition during the loop

Skill-writing is part of the loop contract, not a separate pipeline. The
iteration prompt instructs each agent, before exiting:

- durable project facts and gotchas → append to `.kelix/memory/project.md`;
- a reusable, **non-obvious** procedure → write
  `.kelix/skills/<kebab-name>/SKILL.md` with `name:` and `description:`
  frontmatter — and only for genuinely non-obvious, reusable procedures, so
  the skill store stays high-signal.

The next iteration's skills digest picks the new skill up automatically. This
is Ralph's "let Ralph take himself to university" made concrete: operational
learnings are distilled to files that future iterations load, and because
skills are committed, humans review them in PRs like any other change. Skills
use the same format Kiro reads, so curated ones can be copied into
`.kiro/skills/` for interactive sessions to benefit too.
