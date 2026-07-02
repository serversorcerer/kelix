---
name: audacity-first-doc-intro
description: >-
  Rewrite a concept or capability doc to lead with a concrete audacity claim,
  dogfood proof links, and a repro command before the mechanics section. Use
  for P-AUDIT doc tasks (concept, memory, prioritization, planning, fleet,
  security) where readers need evidence before reference material.
---

# Audacity-first doc intro

Technical docs that open with plumbing lose readers. Kelix dogfood proved specific overnight outcomes — lead with those claims, then demote the original invariant/mechanics content below.

## When to apply

- A backlog task asks to "lead with capability claim and proof" (REQ-U2 / P-AUDIT pattern).
- The doc currently opens with architecture, invariants, or agent-specific plumbing before showing why it matters.

## Intro template (two paragraphs)

**Paragraph 1 — audacity claim:** One or two sentences stating a concrete, falsifiable outcome a solo operator can expect (overnight shipping, zero collisions, hostile-repo safety). Use present tense; avoid "we aim to" or "hypothetically."

**Paragraph 2 — evidence + repro:**
- Link to the relevant proof artifact under `docs/proof/` (final report section, retrospective, drill diff).
- End with a one-line repro command targeting the feature's test module:
  ```text
  Reproduce with `pytest tests/test_<feature>.py -q`.
  ```

Then insert a horizontal break or `##` heading before the original mechanics section (invariants, rubric, coordination rules, threat model).

## Proof link map (reuse across docs)

| Doc topic | Typical proof link | Repro test |
|-----------|-------------------|------------|
| Core concept / overnight shipping | `proof/final-report.md#d1` | full suite |
| Memory continuity | `proof/dogfood-retrospective.md` | `tests/test_memory.py` |
| Task selection | `proof/dogfood-retrospective.md` | `tests/test_backlog.py` |
| Planning | v0.3/v0.4 decomposition via `kelix plan` | `tests/test_plan.py tests/test_lint.py` |
| Fleet / parallel agents | `proof/fleet-session1-retrospective.md`, final report D2 | `tests/test_fleet.py` |
| Security / injection | `proof/injection-drill-backlog.diff` | `tests/test_injection_drill.py` |

Adjust links to match the doc's specific claim; do not paste identical intros across pages.

## Steps

1. Read the existing doc and identify the first mechanics heading to preserve unchanged below the intro.
2. Draft the audacity claim from verified dogfood or drill outcomes — cite numbers when available (12/12, zero collisions, main untouched).
3. Add proof links using relative paths from the doc's location (`proof/...` from `docs/`).
4. Append the repro pytest command for the subsystem under test.
5. Keep all downstream sections intact; only reorder by inserting the new intro above them.

## Verify

```bash
pytest -q
ruff check src tests
```

Spot-check: the first screen of the rendered doc shows claim + proof, not adapter names or rubric tables.

## Do not

- Remove or rewrite the mechanics sections — demote, don't delete.
- Claim outcomes without a proof link or repro command in the evidence paragraph.
- Re-introduce Kiro-first framing in the audacity paragraph; stay agent-agnostic unless the doc is agent-specific.
