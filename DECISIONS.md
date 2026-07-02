# DECISIONS.md — autonomous decision log

Every decision made without the owner in the loop, one entry each, newest at
the bottom. Format: `D<N> (<phase>): decision — rationale`.

- D1 (P0): Primary agent backend is the **Kiro CLI** (`kiro-cli chat
  --no-interactive`), not the Kiro IDE. The IDE has no unattended invocation
  surface; headless mode is public, documented, and exactly matches Ralph's
  fresh-process-per-iteration semantics. IDE integration ships as `.kiro/`
  files (steering/specs/hooks/agents) that both IDE and CLI read. The owner
  mentioned using kiroom + Kiro CLI, which this targets directly.
- D2 (P0): Implementation language is **Python 3.11+** with stdlib only for
  the core (no runtime deps beyond `tomli` fallback for <3.11 not needed).
  Rationale: zero-install-friction for an OSS CLI (pipx), readable for
  auditors of a security-sensitive tool, and fast enough (the loop's cost is
  agent tokens, not runner CPU). Rust (ralph-orchestrator) rejected: build
  friction for contributors outweighs perf we don't need.
- D3 (P0): Loop state split: runner-owned state is JSON (`.kalph/runs/...`),
  human-owned state is Markdown (`backlog.md`, memory, skills). The official
  ralph-loop plugin's markdown-frontmatter state parsing bugs motivated this.
- D4 (P0): Completion sentinel is the literal line `KALPH COMPLETE` emitted by
  the agent, but it is honored **only after the runner independently re-runs
  the verification commands green**. Sentinel-only exit (the plugin's
  completion-promise) is too easy to lie into.
- D5 (P0): Skills use the agentskills.io SKILL.md format, stored under
  `.kalph/skills/<name>/SKILL.md` — portable to Kiro's native
  `.kiro/skills/` loader and to other agents (Hermes, Claude Code).
- D6 (P0): Adapters: `kiro` (default), `cmd` (arbitrary CLI template, which is
  how cursor-agent/claude/etc. run), `mock` (scripted, for CI). The build
  machine has no kiro-cli installed, so the self-hosting build will run on the
  `cmd`/`mock` adapters — an unplanned but useful proof that the loop core is
  agent-agnostic.
- D7 (P0): License Apache-2.0 per mission (patent grant matters for an agent
  tool employers will run); MIT rejected only because the mission specifies
  Apache-2.0.
