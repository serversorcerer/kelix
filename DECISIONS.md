# DECISIONS.md — autonomous decision log

Every decision made without the owner in the loop, one entry each, newest at
the bottom. Format: `D<N> (<phase>): decision — rationale`.

- D1 (P0): Primary agent backend is the **Kiro CLI** (`kiro-cli chat
  --no-interactive`), not the Kiro IDE. The IDE has no unattended invocation
  surface; headless mode is public, documented, and exactly matches Ralph's
  fresh-process-per-iteration semantics. IDE integration ships as `.kiro/`
  files (steering/specs/hooks/agents) that both IDE and CLI read. The owner
  mentioned using kiroom + Kiro CLI, which this targets directly.
- D2 (P0): Implementation language is **Python 3.11+** with stdlib only for
  the core (no runtime deps beyond `tomli` fallback for <3.11 not needed).
  Rationale: zero-install-friction for an OSS CLI (pipx), readable for
  auditors of a security-sensitive tool, and fast enough (the loop's cost is
  agent tokens, not runner CPU). Rust (ralph-orchestrator) rejected: build
  friction for contributors outweighs perf we don't need.
- D3 (P0): Loop state split: runner-owned state is JSON (`.kalph/runs/...`),
  human-owned state is Markdown (`backlog.md`, memory, skills). The official
  ralph-loop plugin's markdown-frontmatter state parsing bugs motivated this.
- D4 (P0): Completion sentinel is the literal line `KALPH COMPLETE` emitted by
  the agent, but it is honored **only after the runner independently re-runs
  the verification commands green**. Sentinel-only exit (the plugin's
  completion-promise) is too easy to lie into.
- D5 (P0): Skills use the agentskills.io SKILL.md format, stored under
  `.kalph/skills/<name>/SKILL.md` — portable to Kiro's native
  `.kiro/skills/` loader and to other agents (Hermes, Claude Code).
- D6 (P0): Adapters: `kiro` (default), `cmd` (arbitrary CLI template, which is
  how cursor-agent/claude/etc. run), `mock` (scripted, for CI). The build
  machine has no kiro-cli installed, so the self-hosting build will run on the
  `cmd`/`mock` adapters — an unplanned but useful proof that the loop core is
  agent-agnostic.
- D7 (P0): License Apache-2.0 per mission (patent grant matters for an agent
  tool employers will run); MIT rejected only because the mission specifies
  Apache-2.0.
- D8 (P1->P2, SELF-HOSTING SWITCHOVER): Parity demo green (test_parity_demo.py,
  commit after C8). From this commit on, the remaining build backlog lives in
  `.kalph/backlog.md` and is worked by `kalph run` against this repo, using
  the `cmd` adapter with the locally available headless agent
  (`cursor-agent --force -p`), since kiro-cli is not installed on the build
  machine. Iterations run by Kalph itself are identifiable by run branches
  (`kalph/run-*`), transcripts under `.kalph/runs/`, and episode records.
  Where a Kalph iteration fails or the bootstrap session must intervene
  (owner-style steering via backlog edits, or direct implementation when an
  iteration is beyond the loop's current capability), that is recorded here
  and in the final report — the mission asks precisely "which iterations were
  run by Kalph itself."
- D9 (P2): Verification commands for the Kalph repo itself: `pytest -q` and
  `ruff check src tests` — the same gate CI will enforce.
- D10 (P5, bootstrap intervention): Kalph's run 20260702-003053 iteration for
  KB7 produced claim code with a TOCTOU race (stale-steal via unconditional
  os.replace could yield two winners; its own thread test caught it ~5% of
  runs — exactly the backpressure working). The bootstrap session rewrote
  claim_task as unlink-then-O_EXCL, single winner guaranteed; 40/40 stress
  runs green. Recorded per the mission's honesty rule about which work was
  loop-run vs. hand-fixed.
- D11 (P8): Dogfood target is a fresh sample repo (`tasklite`, a stdlib-only
  task-tracker library) rather than a clone of an existing OSS project —
  unattended runs against third-party code would exercise the same loop
  mechanics while adding license/attribution noise to the evidence. The
  backlog has 12 owner tasks spanning features, tests, CLI, and docs.
- D12 (P8): Dogfood/fleet PR evidence is git-local: the sample repo has no
  GitHub remote (creating one would publish throwaway code and burn tokens on
  network flakes), so "mergeable PRs" is proven as run branches that merge
  cleanly into main with green tests via `git merge` — the exact operation a
  PR merge performs. The `--pr` path itself is covered by test_pr.py against
  a stubbed `gh`.
- D13 (P8, bootstrap intervention): In fleet session 2 the verifier's
  cursor-agent process finished its work (R1 commit + mailbox review note
  present on its branch) but never exited; after ~20 minutes the session
  killed the process (SIGTERM) rather than wait out the 40-minute adapter
  timeout that would have handled it automatically. The runner recorded the
  iteration honestly as `agent exit 143` while keeping the verified commit —
  exactly the intended failure accounting. No code change needed: the
  timeout rail already covers this unattended.
