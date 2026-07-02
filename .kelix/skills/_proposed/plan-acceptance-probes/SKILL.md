---
name: plan-acceptance-probes
description: >-
  Require plan-interview acceptance probes — one testable verification question
  per roadmap phase — before drafting backlog tasks. Use when extending kelix plan,
  PLANNING_INTERVIEW_TEMPLATE, or P-GOLD input-quality work.
---

# Plan acceptance probes

Goal: owners define how each phase will be verified **before** the loop drafts
backlog tasks, so ready tasks pass spec-gate lint instead of burning adapter iterations.

## 1. Detect phases from the goal

Parse `GOAL.md` (or equivalent) for roadmap phase headers — e.g. `### Phase <id>`.
Collect phase ids in document order. If none are found, the interview still needs
at least one acceptance probe for the whole goal.

## 2. Extend the interview template

Add a rubric section that:
- Lists detected phases by id when present
- Requires **≥ one acceptance probe per phase** (or ≥ one total when no phases)
- Defines probe content: question title/text must name the phase (when applicable)
  and ask **how to verify** — pytest path, exit code, assert, or named file

Align probe expectations with `writing-for-the-loop.md` lint rules so drafted
backlog tasks inherit testable acceptance signals.

## 3. Validate before accepting interview output

Implement validation that:
- Filters questions matching acceptance-probe heuristics (verification-themed:
  tests, exit codes, file paths, verify commands)
- Compares probe count to required count (`len(phases)` or `1`)
- Returns actionable errors listing expected vs got — block plan progression on failure

Wire validation into the plan flow **before** backlog draft — fail fast with
stderr the owner can fix in a follow-up interview turn.

## 4. Test with multi-phase fixture

Add tests that:
- Unit-test phase extraction and probe detection on synthetic goal text
- Use a two-phase goal fixture and assert the accepted interview contains
  **≥ two** acceptance-themed questions when both phases are present
- Assert validation fails when probes are missing for any phase

## 5. Verify

```bash
pytest -q tests/test_plan.py
pytest -q
ruff check src tests
```

## 6. Do not

- Draft backlog from an interview that only asks scope/priority questions.
- Count generic "how should we test?" questions that lack phase naming or concrete
  verify artifacts when phases exist in the goal.
- Defer acceptance criteria to backlog lint alone — probes are the upstream gate.
