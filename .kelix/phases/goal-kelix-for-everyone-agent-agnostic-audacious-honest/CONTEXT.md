## Decisions from planning interview

- **Q1: Default adapter in shipped kelix.toml** — 1 — prompt on TTY with a numbered agent list; on non-TTY require --agent, no silent default
- **Q2: Named preset invocation templates** — Ship all four presets with setup instructions. Be honest in each guide about which invocations we have verified ourselves (cursor) and which are from upstream docs and untested by us — label those clearly and ask the community for honest feedback/corrections.
- **Q3: Agent guide depth vs. kiro.md parity** — 1 — same headings everywhere; Kiro-only sections stay in kiro.md; agent guides cover headless loop wiring
- **Q4: Input-quality tagline canon** — 1 — adopt 'Gold in, diamonds out' as the one-line principle; demote good/slop to body examples
- **Q5: Run spec-gate bypass flag** — 1 — --force exactly as in the goal; document that it skips the spec gate only, never git safety
- **Q6: Run spec-gate lint scope** — 1 — gate evaluates only status: ready tasks
- **Q7: compare.md metrics without new benchmarks** — 1 — cited rows only; missing axes marked 'not measured — no receipt'; never invent numbers
- **Q8: Honest weakness rows on compare.md** — 1 — curate from known evidence: single-iteration latency, IDE pairing affordances, adapter hang/timeout wart (D13)
- **Q9: Audacity rewrite sequencing (Phase 3)** — 1 — feature docs first, then CLI strings, then README/index last
- **Q10: Kalph residue in historical proof** — 2 — rename Kelix throughout proof docs and add a one-line provenance note at the top of final-report
