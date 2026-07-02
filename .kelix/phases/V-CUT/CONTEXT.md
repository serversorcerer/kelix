# Milestone V — owner decisions (planning interview)

Decisions captured once during the value-cut planning iteration. Do not
re-litigate; downstream tasks treat these as binding unless overridden by an
owner edit to `docs/value-ledger.md`.

## Sequencing

Finish all open v0.2 tasks (PC7–PC23), then v0.3, then v0.4, then V-*.
The value cut is the final milestone before release — quality over quantity.

## Ledger authority

D16 (MCP/skills freeze) is **input to the ledger**, not an override. Each row
is judged row-by-row from receipts. The owner may veto any verdict by editing
`docs/value-ledger.md` before execution phases run.

## Predetermined SCRAP (pending ledger documentation)

- **sync/** — SCRAP. Delete `src/kelix/sync/`, `kelix sync`, tests, and docs.
  Evidence: docs/proof/final-report.md line 130 (mocked transport only).
- **pr.py / --pr** — SCRAP. Delete `src/kelix/pr.py`, `--pr` flag, tests, and
  docs. The value demo stops at verified commits on a run branch.

## Predetermined SHARPEN

- **fleet** — SHARPEN, not cut. Improve run-complete messaging and docs within
  V-SHARPEN. Receipt: zero claim collisions in docs/proof/fleet-session*.md.

## CLI surface

Happy path: **init, plan, run** only. **lint, status, stop** stay as
documented secondary ops — out of quickstart, not deleted.

## Value demo

Use a **new minimal fresh sample repo** (stdlib toy, 3–5 tasks) under
`samples/value-demo/`. Clean cold evidence beats reusing tasklite receipts.
