# Goal: Kelix for everyone — agent-agnostic, audacious, honest

Kelix is currently positioned as "the Ralph loop, rebuilt for Kiro." That
undersells it. The loop is agent-agnostic by design (the `cmd` adapter already
ran cursor-agent to build Kelix itself). Reposition Kelix as **the loop that
climbs, for any coding agent** — with Kiro as the flagship first-class
integration, not the identity.

The voice everywhere: AUDACITY. Anyone can build an app. Kelix wakes up
smarter than it went to sleep. Every doc, every CLI message, every comparison
must carry that — backed by evidence, never hype we can't show receipts for.

## Phase 1 — Reposition (de-Kiro the identity, keep the integration)

- README, docs/index.md, pyproject description, CLI help text, and the MCP
  server description no longer lead with Kiro. New framing: "runs any coding
  agent in a stateless loop — Claude Code, Codex CLI, Cursor, Gemini CLI,
  Kiro." Kiro moves to "deepest integration" status, prominently linked.
- docs/kiro.md stays and is not weakened. Kiro users lose nothing.
- Acceptance: `rg -i kiro README.md | head -1` does not match the first
  20 lines of README; docs/kiro.md still passes its examples; all existing
  tests pass unchanged.

## Phase 2 — Named adapters + a guide per agent

- Add named adapter presets that resolve to the existing `cmd` adapter with
  the right invocation template — no new subprocess machinery. Presets:
  `claude` (Claude Code CLI), `codex` (OpenAI Codex CLI), `cursor`
  (cursor-agent), `gemini` (Gemini CLI). `kiro`, `cmd`, `mock` unchanged.
- Each preset gets docs/agents/<name>.md: install, auth, minimal kelix.toml,
  a full worked example (init -> plan -> run on a sample repo), known quirks
  (headless flags, timeout behavior, cost controls), and troubleshooting.
  Follow the structure of docs/kiro.md so guides are comparable.
- `kelix init` asks (or accepts `--agent <name>`) which agent to use and
  writes the matching kelix.toml block, so first-run config is zero-guess.
- Acceptance: `kelix run` with adapter `claude` and a stub binary on PATH
  completes one mock-style iteration in tests; each guide's config block
  parses via `load_config`; a doctest-style CI check exercises every guide's
  TOML snippet.
- Non-goal: do NOT build per-agent API integrations, SDKs, or streaming
  parsers. The contract stays "spawn CLI, pass prompt, read exit code +
  transcript." If an agent has no headless CLI, it gets no preset.

## Phase 3 — Audacity audit (every feature owns the claim)

- For each feature (loop, memory, skills, prioritization, planning core,
  fleet, security, MCP), rewrite its doc intro to answer: "what does this
  let one person do that they couldn't before?" One sentence of audacity,
  then evidence. Kill every sentence that merely describes plumbing.
- CLI surfaces carry the same voice: retire flat strings in cli.py in favor
  of art.say() theming; the run-complete message states what was verified,
  not just "done."
- Acceptance: every docs/*.md feature page opens with a capability claim
  followed by a link to proof (test, docs/proof artifact, or reproducible
  command). A reviewer can trace each claim to its receipt.

## Phase 4 — Honest comparison page

- docs/compare.md: Kelix vs plain Ralph, vs Claude Code alone, vs Codex
  alone, vs long-lived orchestrators (e.g. GSD-style). Compare on measurable
  axes only: state persistence across iterations, verified-done rate,
  unattended runtime, token cost per verified task, injection-drill results,
  fleet collision rate. Use our own docs/proof numbers wherever they exist.
- Where Kelix is weaker, SAY SO in the table (e.g. single-shot latency,
  interactive pairing, IDE affordances). Honesty is the credibility that
  lets the audacious claims land.
- Every number cites its source: a docs/proof artifact, a linked benchmark,
  or a reproducible command. A claim without a receipt does not ship.
- Acceptance: compare.md exists, is linked from README and index, contains
  at least two rows where Kelix loses, and zero uncited numbers.

## Phase 5 — First-contact spec gate (gold in, diamonds out)

- When a user first interacts with Kelix on a project, the loop refuses to
  burn tokens on slop. Concretely:
  - `kelix run` on a backlog whose ready tasks fail lint (no acceptance
    criteria, vague verbs, multi-outcome tasks) stops before iteration 1
    and prints exactly what to fix, with a good/bad example inline.
  - `kelix plan` interview questions probe for acceptance criteria and
    non-goals, not just "what do you want" — reuse docs/writing-for-the-loop
    rules as the rubric.
  - GOAL.md template and lint messages carry the principle in one line:
    "Slop in, slop out. Gold in, diamonds out." Once, not on every surface.
- Acceptance: a test proves `kelix run` exits non-zero with actionable lint
  output on a vague backlog and proceeds on a well-specified one; the
  interview asks at least one acceptance-criteria question per phase.
- Non-goal: no blocking questionnaire the user can't skip. `--force` (or
  promoting past lint deliberately) stays possible — the owner outranks the
  gate, always.

## Global non-goals

- No new runtime dependencies; stdlib-only core stays.
- No weakening of the Kiro integration, security rails, or the verification
  gate. The gate is the product.
- No benchmark numbers we did not run or cannot cite.
