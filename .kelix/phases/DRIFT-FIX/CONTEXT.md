# Post-V doc drift fix — owner decisions (fleet handoff)

Milestone V (KV3) deleted `pr.py` and `--pr`. Several user-facing docs and
prompt strings still promise **open PRs** or **land as PRs**. This fleet run
aligns copy with the value sentence without sandbagging the product.

## Binding language (use everywhere)

| Retire | Replace with |
|--------|----------------|
| "open PRs" / "opens PRs" / "land as PRs" | **verified commits on a `kelix/run-*` branch**; **you merge** when satisfied |
| "`kelix run --pr`" | remove — flag deleted KV3 |
| "`kelix sync`" | remove — module deleted KV2 |
| "test_pr.py" as live evidence | historical footnote only — file deleted KV3 |

## Steak vs sizzle

- **Steak:** factual accuracy — grep-clean user-facing paths; `pytest -q` green.
- **Sizzle:** keep README punchy. The value sentence stays first screen. Frame
  run branches as the **auditable happy path** (receipts you can review), not
  as "we removed a feature." Link dogfood (`final-report.md` § D1) for live-agent
  proof; label `value-demo.md` as mock runner proof where relevant.

## Scope

- **In:** README, quickstart cross-check, memory-and-skills, fleet.md, kiro docs,
  iteration prompt, gitutil/fleet role strings, DECISIONS D12 footnote,
  value-demo header, regression test `tests/test_doc_drift.py`.
- **Out:** `.kelix/backlog.md` archive lines (historical ST/KV tasks), `.kelix/phases/*`
  interview artifacts, `PLAN.md` archive checkboxes, `docs/value-ledger.md` SCRAP rows.

## Verify gate

Same as self-host: `env PYTHONPATH=src $KELIX_VENV/pytest -q` and
`$KELIX_VENV/ruff check src tests`. Doc-only tasks still run full suite.

## Fleet roles

- **builder-1 / builder-2:** README + `src/kelix/*.py` prompt strings
- **scribe-1:** `docs/**`, `integrations/**`, `DECISIONS.md`, `CHANGELOG.md`
- **verifier-1:** `tests/test_doc_drift.py` (DR11) and closure gate (DR12)
