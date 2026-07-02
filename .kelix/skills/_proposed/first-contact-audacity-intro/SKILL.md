---
name: first-contact-audacity-intro
description: >-
  Lead README and docs/index with a three-part audacity intro — capability claim,
  dogfood proof link, reproducible verify command — before generic product copy.
  Use when repositioning first-contact docs or adding P-AUDIT credibility blocks.
---

# First-contact audacity intro

Goal: readers see a bold, receipt-backed claim in the first screenful — not buried
after marketing fluff.

## 1. Write the three-part block

Place this **before** the standard product explanation (loop diagram, feature list,
quickstart). Order is fixed:

1. **Capability claim** — one sentence stating what Kelix can do unattended (write
   spec once, return to verified commits gated by repo verify commands).
2. **Proof link** — anchor to the dogfood receipt with the measured stat inline
   (e.g. **12/12 tasks verified-done in 12 iterations, zero failures**).
3. **Reproduce command** — a single copy-paste command that exercises the verify
   gate mechanism (e.g. `pytest tests/test_verify.py -q`).

Every number in the block must trace to a linked proof doc section — not bare
assertions.

## 2. Mirror paths in README and docs index

Apply the same block to both entry points in one change set:

| Surface | Proof path style |
|---------|------------------|
| `README.md` | Repo-relative (`docs/proof/final-report.md#…`) |
| `docs/index.md` | Docs-relative (`proof/final-report.md#…`) |

Keep wording parallel so repositioning one surface without the other does not drift.

## 3. Verify

```bash
rg -n 'verified-done|test_verify\.py' README.md docs/index.md
pytest -q
ruff check src tests
```

Confirm both files contain the proof link and reproduce command — not just README.

## 4. Do not

- Lead with alpha disclaimers or feature bullets before the audacity block.
- Cite stats without a linked receipt or reproducible command.
- Update only one of README / docs index when the task scope is first-contact reposition.
