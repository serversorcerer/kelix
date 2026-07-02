# Value ledger

Evidence-first verdict on every Kelix module. The **value sentence** is: *you
write a well-specified goal, walk away, and come back to verified commits.*

Decision rule (REQ-VL2):

| Verdict | Rule |
|---------|------|
| **SHARPEN** | Receipt exists **and** module is on the critical path of the value sentence |
| **KEEP** | Receipt exists but module is off the critical path — freeze (no new code/docs unless a bug) |
| **SCRAP** | No receipt — delete in a named backlog task |

Critical path: **init → plan (interview) → lint/spec-gate → run → verify → verified
commits on run branch.** Adapters and state/backlog selection are on-path;
fleet, memory, skills, MCP, sync, PR automation, and Kiro-specific glue are
off-path unless the receipt proves otherwise.

Line counts from `wc -l` on cited paths (2026-07-02 worktree).

| Module | Lines of code | Receipt | Verdict |
|--------|---------------|---------|---------|
| loop | 686 (`src/kelix/loop.py`) | `tests/test_loop.py`; dogfood 12/12 verified ([final-report § D1](proof/final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd)); circuit-breaker no-diff burn (`test_circuit_breaker_on_no_diff`); worktree isolation after killed agent ([DECISIONS.md D13](../DECISIONS.md)) | SHARPEN |
| verify | 82 (`src/kelix/verify.py`) | `tests/test_verify.py`; dogfood 12/12 verified ([final-report § D1](proof/final-report.md#d1--dogfood-run-docsproofdogfood-runlog-dogfood-retrospectivemd)) | SHARPEN |
| plan+interview | 573 (`src/kelix/plan.py`) | `tests/test_plan.py`; first real `kelix plan` interview for v0.4 ([DECISIONS.md D19](../DECISIONS.md)) | SHARPEN |
| lint | 397 (`src/kelix/lint.py`) | `tests/test_lint.py` slop rejection; run spec-gate for ready tasks (`tests/test_loop.py` `test_run_spec_gate_*`) | SHARPEN |
| state/roadmap/backlog | 490 (`src/kelix/state.py`, `roadmap.py`, `backlog.py`) | `tests/test_state.py`, `tests/test_roadmap.py`, `tests/test_backlog.py`; STATE.md-driven proof run ([DECISIONS.md D21](../DECISIONS.md), run 20260702-104227) | SHARPEN |
| adapters | 273 (`src/kelix/adapters.py`) | `tests/test_adapters.py`; dogfood via `cursor-agent` headless ([docs/proof/final-report.md](proof/final-report.md), [docs/agents/cursor.md](agents/cursor.md)) | SHARPEN |
| fleet | 549 (`src/kelix/fleet.py`) | Zero claim collisions ([final-report § D2](proof/final-report.md#d2--fleet-proof-docsprooffleet-sessionlog-fleet-verifier-review-notemd), [fleet-session1-retrospective.md](proof/fleet-session1-retrospective.md)); `tests/test_fleet.py` | SHARPEN |
| memory | 359 (`src/kelix/memory.py`) | `tests/test_memory.py`; episodes persisted across dogfood run ([dogfood-retrospective.md](proof/dogfood-retrospective.md)) | KEEP |
| skills | 237 (`src/kelix/distill.py`) + skills slot in `memory.py`/`prompt.py` | `tests/test_loop.py` distillation mock; `tests/test_metrics.py` efficacy rollup; **no live learning receipt** — every v0.1 prompt showed "(no skills yet)" ([DECISIONS.md D17](../DECISIONS.md)) | KEEP |
| claims | 161 (`src/kelix/claims.py`) | `tests/test_claims.py`; fleet wave/claim receipts ([final-report § D2](proof/final-report.md#d2--fleet-proof-docsprooffleet-sessionlog-fleet-verifier-review-notemd)) | KEEP |
| mcp_server | 182 (`src/kelix/mcp_server.py`) | `tests/test_mcp_server.py`; no live MCP agent run in proof docs | KEEP |
| kiro | 80 (`src/kelix/kiro.py`) | `tests/test_kiro.py` with substituted binary; **no live Kiro CLI run** ([final-report § Unverified](proof/final-report.md#unverified--deferred--stated-plainly)) | KEEP |
| security | 87 (`src/kelix/security.py`) | `tests/test_security.py`, `tests/test_injection_drill.py`; injection drill backlog diff ([proof/injection-drill-backlog.diff](proof/injection-drill-backlog.diff)) | KEEP |
| art | 133 (`src/kelix/art.py`) | `tests/test_ci_integration.py` run-complete theming (KE25) | KEEP |
| sync/ | 304 (`src/kelix/sync/`) | Mocked transport only — no live Linear API ([final-report line 132](proof/final-report.md#unverified--deferred--stated-plainly)) | SCRAP → **KV2** |
| pr | 214 (`src/kelix/pr.py`) | Stubbed `gh` in tests only; dogfood value path is verified commits on run branch ([final-report line 134](proof/final-report.md#unverified--deferred--stated-plainly), [V-CUT CONTEXT](../.kelix/phases/V-CUT/CONTEXT.md)) | SCRAP → **KV3** |

## Owner veto

Edits to this file **before** V-SHARPEN / V-SIMPLE execution phases run are
binding. Change any row's verdict or receipt column, commit, and downstream
KV2–KV5 tasks read the updated ledger — they do not re-litigate. Predetermined
owner SCRAPs (`sync/`, `pr.py`) are documented above pending KV2/KV3 deletion.
