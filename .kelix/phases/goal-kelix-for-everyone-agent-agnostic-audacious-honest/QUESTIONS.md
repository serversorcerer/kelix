# Planning interview

Fill in each `answer:` line, then re-run `kelix plan` with the same goal.

Q1: Default adapter in shipped kelix.toml
After repositioning, what should `kelix init` write into `[agent]` when the user does not pass `--agent` (non-interactive CI, scripts, muscle memory)?
1. Prompt on TTY (numbered agent list); on non-TTY require `--agent` with no silent default (recommended)
2. Keep `adapter = "kiro"` as today for backward compatibility; repositioning is docs-only
3. Default to the `cursor` preset (matches dogfood proof in `.kelix/kelix.toml` and `docs/proof/final-report.md`)
4. Default to `cmd` with a commented `# command = "..."` block and no preset until the user edits

answer: 1 — prompt on TTY with a numbered agent list; on non-TTY require --agent, no silent default

Q2: Named preset invocation templates
Phase 2 adds `claude`, `codex`, `cursor`, and `gemini` presets as thin wrappers over `cmd`. We only have a verified headless invocation on this machine (`cursor-agent --force -p {prompt}`). How should we treat the other three command lines?
1. Ship presets only for invocations we can cite from our own runs or pinned public CLI docs; mark others "verify locally" until dogfooded (recommended)
2. Ship all four with best-effort templates from upstream docs; CI only checks TOML parses, not that binaries exist
3. Ship `cursor` + built-in `kiro` only in v1; defer `claude`/`codex`/`gemini` presets to a follow-up
4. Ship all four and require stub-binary iteration tests (like `mock`) for each preset before merge

answer: Ship all four presets with setup instructions. Be honest in each guide about which invocations we have verified ourselves (cursor) and which are from upstream docs and untested by us — label those clearly and ask the community for honest feedback/corrections.

Q3: Agent guide depth vs. kiro.md parity
Each `docs/agents/<name>.md` should mirror `docs/kiro.md` (install, auth, config, full worked example, quirks, troubleshooting). Kiro also covers spec→backlog, `.kiro/` package, hooks, and MCP — surfaces other CLIs lack. What parity bar do you want?
1. Same section headings everywhere; Kiro-only sections stay in `docs/kiro.md` only; agent guides cover headless loop wiring only (recommended)
2. Full structural parity including placeholder sections ("N/A for this agent") so every guide is the same length
3. Minimal quickstart per agent (install + 10-line kelix.toml + one command); expand only after user feedback
4. Single `docs/agents/README.md` index plus one deep guide per agent only when that preset ships

answer: 1 — same headings everywhere; Kiro-only sections stay in kiro.md; agent guides cover headless loop wiring

Q4: Input-quality tagline canon
`docs/writing-for-the-loop.md` and `kelix lint` already use "good input in, good output out" / "slop in, slop out." Phase 5 introduces "Gold in, diamonds out." Which voice wins?
1. Adopt "Gold in, diamonds out" as the one-line principle (GOAL.md template + first lint/run-gate mention); demote good/slop to body examples in writing-for-the-loop (recommended)
2. Keep good/slop everywhere; add gold/diamonds once in GOAL.md only
3. Replace all surfaces globally with gold/diamonds in one sweep
4. Pair them everywhere: "Gold in, diamonds out — slop in, slop out"

answer: 1 — adopt 'Gold in, diamonds out' as the one-line principle; demote good/slop to body examples

Q5: Run spec-gate bypass flag
Phase 5 requires a deliberate owner override when ready tasks fail lint. The goal names `--force`, which collides with forbidden `git push --force` in security messaging. What flag should `kelix run` accept?
1. `--force` exactly as in the goal; document that it skips the spec gate only, not git safety (recommended)
2. `--skip-spec-gate` (or `--no-spec-gate`) to avoid confusion with git semantics
3. Reuse `--no-lint` because the gate reuses lint rules
4. Environment variable only (`KELIX_SKIP_SPEC_GATE=1`) — no CLI flag

answer: 1 — --force exactly as in the goal; document that it skips the spec gate only, never git safety

Q6: Run spec-gate lint scope
When `kelix run` stops before iteration 1, which backlog tasks should the gate evaluate?
1. Only `status: ready` tasks (what the loop can actually pick) (recommended)
2. Same scope as `kelix lint` today — all non-`done` tasks
3. Ready tasks plus any `blocked` tasks (surface dependency issues early)
4. Ready tasks only, but stricter rules than today's lint (new checks beyond writing-for-the-loop)

answer: 1 — gate evaluates only status: ready tasks

Q7: compare.md metrics without new benchmarks
Phase 4 wants measurable axes (verified-done rate, token cost per verified task, unattended runtime, fleet collision rate, injection-drill results). `docs/proof/final-report.md` has dogfood/fleet/injection numbers but not every axis, and labels still say "kalph." What do we ship?
1. Publish `compare.md` with cited rows only; missing axes explicitly marked "not measured — no receipt"; do not invent numbers (recommended)
2. Block Phase 4 until we run a fresh benchmark pass and update proof artifacts (including Kalph→Kelix rename)
3. Qualitative comparison ( prose strengths/weaknesses) for axes we cannot cite yet
4. Cite existing proof numbers as-is with a footnote that runs predated the Kelix rename

answer: 1 — cited rows only; missing axes marked 'not measured — no receipt'; never invent numbers

Q8: Honest weakness rows on compare.md
The goal requires at least two rows where Kelix loses. Which weaknesses should we lead with?
1. Curate from known evidence: single-iteration latency vs interactive agents, IDE pairing affordances, adapter hang/timeout wart from fleet proof (D13) (recommended)
2. Owner picks the two rows in a follow-up review after a draft table is written
3. Only weaknesses already documented in README "will and will not do" — no new admissions
4. Include "requires well-specified backlog / spec gate friction" as a primary weakness row

answer: 1 — curate from known evidence: single-iteration latency, IDE pairing affordances, adapter hang/timeout wart (D13)

Q9: Audacity rewrite sequencing (Phase 3)
Eight feature areas plus CLI `art.say()` theming. What order minimizes risk while meeting the acceptance criterion (every feature doc opens with claim + receipt link)?
1. Feature docs first (`concept`, `memory`, `fleet`, `mcp`, `prioritization`, `SECURITY`, planning core), then CLI strings, then README/index last (recommended)
2. README + index + pyproject/MCP description first (Phase 1 voice), audacity pass on feature docs second
3. CLI `art.say()` first for user-visible wins; docs follow
4. Single vertical slice: rewrite `concept.md` + `run` completion message as the template, then apply pattern to remaining pages

answer: 1 — feature docs first, then CLI strings, then README/index last

Q10: Kalph residue in historical proof
`docs/proof/final-report.md`, run logs, and `DECISIONS.md` still say "kalph" while the product is Kelix. How should Phase 1–4 treat them?
1. User-facing repositioning only (README, index, pyproject, CLI, MCP); leave proof artifacts verbatim as historical receipts (recommended)
2. Rename Kelix throughout proof docs and add a one-line provenance note at the top of final-report
3. Keep "formerly known as Kalph" in README for discoverability; do not touch proof
4. Duplicate proof as Kelix-branded summaries linking to unchanged raw logs

answer: 2 — rename Kelix throughout proof docs and add a one-line provenance note at the top of final-report
