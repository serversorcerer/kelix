---
name: honest-compare-matrix
description: >-
  Author an honest competitor comparison matrix with cited receipts, explicit
  Kelix-loses rows, and first-contact links from README and docs/index. Use for
  P-COMPARE docs tasks or when adding measurable positioning pages.
---

# Honest compare matrix

Goal: a comparison page that earns trust by citing receipts, admitting losses, and
saying **not measured — no receipt** instead of inventing numbers.

## 1. Create `docs/compare.md`

Open with scope: which alternatives (plain Ralph, single-agent CLIs, GSD-style
orchestrators) and the receipt discipline rule — no number without a linked
artifact or reproducible command.

### Matrix columns

Include at least: Plain Ralph, Claude Code alone, Codex CLI alone, GSD-style
orchestrators, Kelix, and a **Receipt** column.

### Rating vocabulary

Use consistent labels: **Strong**, **Weak**, **Loses**, **N/A**. Mark Kelix
weakness rows explicitly *(Kelix loses)* in the axis name so losses are scannable.

### Required honesty rows

Include at least three **Kelix loses** axes (verified pattern from dogfood):
single-iteration latency, IDE pairing affordances, adapter hang/timeout wart.
Link each to structural docs or DECISIONS entries.

### Unmeasured axes

When no receipt exists, write **not measured — no receipt** in every column —
never leave blank cells that imply parity.

## 2. Receipt column rules

Every measurable Kelix cell links to:
- A proof doc section under `docs/proof/`, or
- A DECISIONS entry for known warts, or
- A `pytest … -q` command in a **Reproduce key receipts** section at page bottom.

Token cost, wall-clock latency, and orchestrator comparisons without data stay
explicitly unmeasured.

## 3. Surface from first contact

Link `docs/compare.md` from both:
- `README.md` — under a **Why Kelix** (or equivalent) section
- `docs/index.md` — under **Reference**

Verify links exist:

```bash
rg compare.md README.md docs/index.md
```

## 4. Verify

```bash
pytest -q
ruff check src tests
```

Optionally grep for honesty markers:

```bash
rg -n 'Kelix loses|not measured — no receipt' docs/compare.md
```

## 5. Do not

- Publish competitor numbers without a receipt in this repo.
- Omit Kelix weakness rows to appear universally superior.
- Ship `compare.md` without README and docs index links when the task is discoverability.
