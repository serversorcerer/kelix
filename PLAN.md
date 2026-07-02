# PLAN.md — live backlog for building Kalph

This file is the bootstrap loop's plan. Loop contract: read this file + git
log, pick ONE unchecked task (top-most unblocked), implement, verify, check it
off with a one-line evidence note, commit. Fresh start each cycle — re-read
state from disk.

When `kalph run` passes the Phase 1 parity demo, switch to self-hosting:
migrate remaining tasks into `.kalph/backlog.md` and run them with Kalph
itself. Record the switchover in DECISIONS.md.

## Phase 0 — Research

- [x] R1: Extract Ralph invariants -> docs/research/ralph-invariants.md (evidence: file committed)
- [x] R2: Prior-art survey (ralph-orchestrator, ralph-loop plugin, Hermes) -> docs/research/prior-art.md (evidence: file committed)
- [x] R3: Kiro public surface map -> docs/research/kiro-surface.md (evidence: file committed)

## Phase 1 — Core loop

- [x] C1: Repo scaffold: pyproject.toml, package layout, LICENSE (Apache-2.0), .gitignore, stub README (evidence: pip install -e . succeeds)
- [x] C2: Config loader (kalph.toml): agent adapter cmd, verify commands, caps, budgets; defaults safe (evidence: 8 tests green)
- [x] C3: Agent adapter interface + `kiro` adapter (headless kiro-cli) + `mock` adapter (scripted) + `cmd` adapter (arbitrary CLI) (evidence: 16 tests green, lint clean)
- [x] C4: Iteration engine: fresh process, static prompt assembly (template + data slots), transcript capture per iteration (evidence: prompt tests green)
- [x] C5: Loop runner `kalph run`: sentinel detection, --max-iterations, per-run worktree+branch isolation, auto-checkpoint (evidence: test_loop.py green incl. worktree isolation + checkpoint tests)
- [x] C6: Verification gate: run config verify commands after each iteration; verified-done rule; failed task stays on top (evidence: sentinel-lie test proves red verification blocks completion)
- [x] C7: Circuit breaker: N consecutive errors/no-diff -> stop + diagnosis file (evidence: no-diff breaker + reset-after-success tests)
- [ ] C8: Parity demo: toy repo fixture with 5-task plan, mock agent, end-to-end green (this is the regression baseline test)

## Phase 2 — Memory

- [ ] M1: Memory store layout .kalph/memory/ (project.md, episodes.jsonl) + episode recording after every iteration
- [ ] M2: Skills: .kalph/skills/<name>/SKILL.md (agentskills.io format), acquisition rule in prompt, loading into iterations
- [ ] M3: Budgeted memory digest injection at iteration start + run retrospective updating project memory

## Phase 3 — Prioritization

- [ ] B1: Backlog model .kalph/backlog.md: priority, rationale, status, deps; parser + writer; highest-priority-unblocked selection with logged one-line reason
- [ ] B2: Scoring rubric doc + self-proposed tasks (marked proposed, ranked below owner tasks unless autonomy: high)
- [ ] B3: Decomposition rule: oversized task -> checklist subtasks before execution
- [ ] B4: Branch-per-task + PR flow via gh (kalph/<slug>, PR with evidence; never direct to main)
- [ ] B5: Tracker sync adapter interface + Linear reference adapter (inbound issues sanitized as data; outbound status/comments; non-fatal failures)

## Phase 4 — Kiro integration

- [ ] K1: .kiro/ package: steering file, agent config (kalph agent), example hooks, spec->backlog import (kalph init --from-spec)
- [ ] K2: kalph mcp: stdio MCP server (start run, status, memory inspect, stop); documented tool schema
- [ ] K3: README quickstart: spec written -> overnight run in one command

## Phase 5 — Fleet

- [ ] F1: Fleet coordination dir .kalph/fleet/: atomic task claims with staleness reclaim; collision test
- [ ] F2: Mailbox notes + shared discoveries (skills/memory shared store)
- [ ] F3: Roles via fleet.toml (builder/verifier/fixer/scribe as data); role prompt shaping + task filters
- [ ] F4: kalph fleet start/status/stop; kill switch; merge-conflict policy (verifier rebases and flags)

## Phase 6 — Security

- [ ] S1: Command allowlist/denylist engine with safe defaults + tests that dangerous commands are actually blocked
- [ ] S2: Secrets hygiene: transcript scrubber, .kalph/ gitignore defaults, no tokens in memory/commits
- [ ] S3: docs/SECURITY.md threat model + prompt-injection defenses (repo text is data) + egress policy config
- [ ] S4: CI security jobs: secret scan, dependency audit, denylist regression test

## Phase 7 — Packaging

- [ ] P1: README (what/why/quickstart/architecture/FAQ/"will and will not do unattended"), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY reporting, issue/PR templates, CHANGELOG
- [ ] P2: CI: lint + unit + 2-iteration integration loop on fixture with mock agent + secret scan; green required
- [ ] P3: docs/ static site (GitHub Pages ready): concept, quickstart, Kiro guide, security model, memory/skills reference

## Phase 8 — Proof

- [ ] D1: Dogfood: sample project, 10+ task backlog, --max-iterations 25 unattended; >=3 mergeable PRs, coherent memory, accurate retrospective
- [ ] D2: Fleet proof: 3-agent fleet (builder, verifier, scribe); zero claim collisions; verifier reviewed a builder PR
- [ ] D3: Injection drill: poisoned fixture treated as data (proof from logs)
- [ ] D4: Final report
