# Kelix vs alternatives — honest comparison

This page compares Kelix to plain [Ralph](https://ghuntley.com/ralph/), to
running a single-agent CLI (Claude Code, Codex) without a loop runner, and to
GSD-style long-lived orchestrators. Every measurable claim cites a receipt in
this repo or reads **not measured — no receipt**. Numbers without a linked
artifact or reproducible command do not appear here.

## How to read the table

- **Strong** — clear advantage on this axis with a receipt, or a structural
  property documented in linked docs.
- **Weak** — works but with known warts or bootstrap interventions on record.
- **Loses** — a deliberate trade-off or a documented wart where Kelix is
  worse than the alternative for typical use.
- **N/A** — the axis does not apply to that approach.

Receipts live under [docs/proof/](proof/final-report.md) unless noted.

## Comparison matrix

| Axis | Plain Ralph | Claude Code alone | Codex CLI alone | GSD-style orchestrators | Kelix | Receipt |
| --- | --- | --- | --- | --- | --- | --- |
| **State persistence** | Git history + static `PROMPT.md` only; no structured backlog or memory slots | Session/conversation history in the CLI process; project files on disk | Same pattern as Claude Code | `.planning/` tree (STATE, roadmap, phase artifacts) maintained across subagent spawns | `.kelix/` spine: STATE, backlog, roadmap, memory, episodes — runner-maintained, git-versioned | [concept.md](concept.md), [planning.md](planning.md), [gsd-lessons.md](research/gsd-lessons.md) |
| **Verified-done rate** | Agent self-reports; no independent re-run of repo verify commands | Tool use + user judgment; no standardized runner gate | Same as Claude Code | Dedicated verifier subagent checks REQ coverage per phase | **12/12 tasks verified-done in 12 iterations, zero failures** on dogfood sample | [final-report.md § D1](proof/final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd), [dogfood-retrospective.md](proof/dogfood-retrospective.md) |
| **Unattended runtime** | Runs until iteration cap; no circuit breaker, worktree isolation, or kill switch | Interactive-first; unattended headless possible but not the default product shape | Same as Claude Code | Orchestrator session monitors subagents; runtime lifecycle hooks | Dogfood run completed unattended end-to-end; fleet session 2 verifier hung ~20 min after finishing (manual kill — see weakness rows) | [final-report.md § D1–D2](proof/final-report.md), [DECISIONS.md D13](../DECISIONS.md) |
| **Token cost per verified task** | not measured — no receipt | not measured — no receipt | not measured — no receipt | not measured — no receipt | not measured — no receipt (`loop-metrics.json` records `tokens: null`; adapter hook documented, not wired) | [memory-and-skills.md](memory-and-skills.md) Outcome ledger |
| **Injection-drill results** | No documented drill | Provider-dependent; no Kelix-equivalent receipt in this repo | Same as Claude Code | not measured — no receipt in this repo | Live agent filed injection as proposed security task; main untouched; regression tests green | [final-report.md § D3](proof/final-report.md#d3--injection-drill-docsproofinjection-drill-log-injection-drill-backlogdiff), `pytest tests/test_injection_drill.py -q` |
| **Fleet collision rate** | N/A (single loop) | N/A | N/A | Dependency waves group parallel work; collision model differs | **Zero claim collisions** across three agents in fleet session 1 (four tasks, one claim each) | [final-report.md § D2](proof/final-report.md#d2--fleet-proof-docsprooffleet-sessionlog-fleet-verifier-review-notemd), [fleet-session1-retrospective.md](proof/fleet-session1-retrospective.md) |
| **Single-iteration latency** *(Kelix loses)* | One `agent` subprocess; minimal wrapper overhead | **Loses for Kelix:** one interactive turn in-IDE — no fresh-process loop tax | Same as Claude Code for IDE pairing | Orchestrator dispatches subagent; latency profile not measured here | Each iteration: worktree setup, prompt assembly, context compiler, verify re-run — higher per-iteration overhead than a single interactive turn | Structural (Ralph invariants in [concept.md](concept.md)); no wall-clock benchmark — **not measured — no receipt** |
| **IDE pairing affordances** *(Kelix loses)* | Shell loop only | **Strong:** inline diffs, @-mentions, file tree, human-in-the-loop by default | Same class as Claude Code when used in supported IDE surfaces | Varies by host; often IDE-integrated | Headless loop; operator steers via backlog/roadmap files, not inline chat | [agents/cursor.md](agents/cursor.md) documents headless path; pairing is out of scope |
| **Adapter hang / timeout wart** *(Kelix loses)* | N/A | Provider-dependent idle behavior | Same | Orchestrator may reap stuck subagents; no Kelix receipt | Fleet session 2: verifier finished work but process idle ~20 min until manual SIGTERM (`exit 143`); 40-minute adapter timeout would cover unattended | [DECISIONS.md D13](../DECISIONS.md), [final-report.md § D2](proof/final-report.md#d2--fleet-proof-docsprooffleet-sessionlog-fleet-verifier-review-notemd) |

## When to pick what

**Plain Ralph** — smallest possible loop, you accept agent-self-reported "done,"
and you do not need memory, verify gates, or fleet coordination.

**Claude Code or Codex alone** — you are at the keyboard pairing; latency and
IDE affordances matter more than overnight unattended runs.

**GSD-style orchestrator** — you want a long-lived coordinator, Discuss → Plan →
Execute phases, and verifier subagents with REQ coverage; you accept orchestrator
session state as the control plane ([gsd-lessons.md](research/gsd-lessons.md)
documents what Kelix adopted vs rejected).

**Kelix** — you want Ralph's stateless iterations *plus* verified-done,
file-coordinated fleet mode, injection rails, and a planning onramp — and you
can write well-specified backlog tasks ([writing-for-the-loop.md](writing-for-the-loop.md)).

## Reproduce key receipts

```bash
# Verified-done gate (dogfood stat is narrative; this proves the gate mechanism)
pytest tests/test_verify.py -q

# Injection drill regression
pytest tests/test_injection_drill.py -q

# Full local verify gate for this repo
pytest -q && ruff check src tests
```

Dogfood and fleet narrative evidence: [final-report.md](proof/final-report.md).
