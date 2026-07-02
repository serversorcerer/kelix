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
- D14 (publish): First CI run on GitHub caught a real bug the dev machine
  masked: auto-checkpoint used `git add -A`, which swept runner bookkeeping
  (transcripts under `.kalph/runs/`, `episodes.jsonl`) into commits on
  machines without a global gitignore — making every iteration look like
  progress and blinding the no-diff circuit breaker
  (test_circuit_breaker_on_no_diff failed on CI, passed locally).
  Fix: checkpoint() excludes runner-owned paths via pathspec and commits
  only agent work; regression test added. Kept `.kalph/*` gitignore
  defaults as a second layer, not the only layer.
- D15 (v0.2 planning): Adopted four ideas from GSD Core (open-gsd/gsd-core;
  analysis in docs/research/gsd-lessons.md) as milestone v0.2 "Planning
  Core": a runner-maintained STATE.md navigation spine, a top-down
  roadmap → phase → task hierarchy with REQ-ID coverage gating, per-phase
  CONTEXT.md decision files, and dependency waves for fleet parallelism.
  Rejected GSD's long-lived orchestrator session and runtime lifecycle
  hooks as violations of the Ralph invariants — Kalph's runner holds zero
  model context, so headroom management is unnecessary by construction.
  The hierarchy is strictly optional: repos without a roadmap keep today's
  flat-backlog behavior (the "quick path"). Owner directive recorded: the
  planning layer is a core component, organized top-down, "so the stateless
  loops know how to drive the cars."
- D16 (v0.2/v0.3 planning): Four owner directives reshape the plan.
  (1) Planning must interview the owner, not guess — `kalph plan` gains a
  question step (hybrid: live terminal Q&A when a TTY exists, committed
  QUESTIONS.md otherwise; owner was offered the choice and skipped, so the
  recommended hybrid stands).   (2) MCP/skills are FROZEN: they keep working
  and stay tested, zero new investment. Clarified on owner question: the
  freeze covers skills PLUMBING (format, portability, MCP exposure) — skill
  LEARNING is core and lives in v0.3 (see D17). (3) Context is 50% of the value:
  new P-CONTEXT phase — a context compiler that fills half the prompt
  budget with task-relevant material chosen by relevance, not recency, and
  logs a context manifest per iteration so context quality is auditable.
  (4) Audacity is the point: milestone v0.3 is the self-tuning loop —
  Kalph measures its own iteration outcomes and proposes changes to its
  own prompt/policies as reviewable PRs, never self-applied; staged next:
  autonomous roadmapping (v0.4), self-reviewing fleet (v0.5).
- D17 (v0.3 scope): Skill LEARNING joins the self-tuning milestone. Evidence
  from the v0.1 proof runs: every live prompt showed "(no skills yet)" — in
  ~20 iterations the acquisition rule in the prompt never fired once. A
  prompt suggestion alone does not produce learning; acquisition must be a
  step the runner drives (retrospective-time distillation from verified
  episodes), and skill efficacy must be measured (was a skill injected, was
  the task it matched verified faster/with fewer retries). Self-tuning =
  the loop learning policies; skill building = the loop learning
  procedures; same audacious bet at two granularities. Skills plumbing
  (format/portability/MCP exposure) stays frozen per D16.
- D18 (rebrand): Kalph -> KELIX, owner-approved. Rationale: the project's
  identity moved past "Ralph for Kiro" the moment v0.3 made self-improvement
  the headline — a circle that gains altitude each pass is a helix; K keeps
  the Kiro/Kalph lineage. Verified `kelix` free on PyPI before choosing.
  Scope: package (src/kelix), CLI (`kelix`), runtime dir (`.kelix/`), config
  (`kelix.toml`), sentinel (`KELIX COMPLETE`), branch prefix (`kelix/`),
  env (`KELIX_VENV`), docs, Kiro integration files, GitHub repo rename
  (old URLs redirect). Historical evidence (docs/proof/, PLAN.md, earlier
  DECISIONS entries) intentionally keeps the name Kalph — history is not
  rewritten. CLI art ships with the rebrand (src/kelix/art.py): gradient
  wordmark + helix banner on init/run/help, themed status glyphs, honest
  fallbacks (NO_COLOR, KELIX_NO_ART, non-TTY -> plain text, banners never
  enter transcripts or parsed output).
- D19 (v0.4 planning — first real `kelix plan` interview): milestone v0.4
  "Kelix for everyone" was planned by `kelix plan --goal-file GOAL.md`, not
  by hand. The interview emitted 10 questions; the owner answered all
  (notable: ship all four agent presets with honest verified/unverified
  labeling and community feedback; rename Kalph residue in proof docs with
  a provenance note — overriding D18's leave-verbatim choice). The drafted
  plan (phases P-REPOS/P-AGENT/P-AUDIT/P-COMPARE/P-GOLD, tasks KE1–KE32,
  all proposed) failed its own validation gate, exposing two real defects:
  (1) the draft reused REQ-C*/REQ-G* ids already taken by v0.2 phases —
  fixed by renaming v0.4 ids to REQ-CM*/REQ-GD*; (2) legacy PC tasks carried
  REQ tags only in rationale text, invisible to coverage — fixed by
  backfilling `| phase: | req:` fields, with multi-REQ tasks now supported
  via comma-separated `req:` in lint coverage. The gate catching its own
  planner's slop is the system working as designed.
- D20 (Milestone V — the value cut): planned via `kelix plan` interview
  (7 questions, validated clean on the first draft — the REQ-collision fix
  from D19 held). Owner decisions: finish ALL open work first (v0.2 →
  v0.3 → v0.4 → V; quality over quantity); the value ledger judges every
  module row-by-row from receipts with owner veto (D16 freeze is input,
  not override); sync/ and pr.py are predetermined SCRAP (mocked-transport
  and stubbed-gh receipts only); fleet is predetermined SHARPEN (zero
  claim collisions is a real receipt); happy path narrows to init/plan/run
  with lint/status/stop as secondary ops; value demo runs cold on a fresh
  minimal sample repo. Milestone V (KV1–KV18) gates the release: the demo
  transcript in docs/proof/value-demo.md is the ship criterion.
- D21 (REQ-P3 — self-referential proof, PC13): run 20260702-104227 is the
  proof. 10 iterations, 10 tasks verified-done (PC9–PC12, PC17–PC22): the
  loop oriented from STATE.md, selected by the new phase-aware order, built
  the context compiler (relevance scorer, 50% budget split, context
  manifest), the harden rails (rationale fallback, inactivity watchdog),
  waves + fleet wave gating, role-drift reporting, and the planning guide —
  and the phase gate auto-advanced STATE.md from P-GATE through P-PROOF
  mid-run with zero owner intervention. Iteration 10 hit the 2400s hard
  timeout attempting to nest a proof run inside itself; the already-merged
  run satisfies REQ-P3's intent (a real run driving the planning core), so
  PC13 is marked done by the owner with this entry as evidence. Transcripts:
  .kelix/runs/20260702-104227/. Wart for the ledger: iterations 4–6 logged
  "(no rationale)" — PC17's fallback was built in this very run and only
  takes effect after merge; also the runner's buffered stdout hid live
  progress from a piped run (fixed same day: flush per log line).
- D22 (v0.3 planning + ship gate — PC23 closes v0.2, ST19 closes v0.3):
  Milestone v0.3 was decomposed by `kelix plan` interviewing the owner (14
  decisions, binding copies in `.kelix/phases/T-*/CONTEXT.md`). Ship gate:
  one full self-tuning cycle (ledger → diagnose → propose → grade); T-SKILLS
  ships in-milestone but is not the gate. Strict waterfall T-METRICS →
  T-DIAGNOSE → T-PROPOSE → T-SKILLS. Dual memory: episodes.jsonl stays the
  raw stream, loop-metrics.json is the runner rollup at retrospective; both
  gitignored. No token fields in v0.3 (tokens: null + documented adapter
  hook). `kelix diagnose` is owner-invoked only; `kelix propose` works the
  policy surface only (prompt templates, denylist, config defaults) and opens
  PRs via pr.py — which hands pr.py a live receipt and obliges KV1 to
  re-judge its predetermined SCRAP at ledger time. Grading: last-5 vs
  next-5 run windows, inconclusive under 3 post-merge runs. Skills:
  `_proposed/` distillation (1–3 candidates/run), per-skill efficacy in the
  ledger. Draft tasks ST1–ST20 landed proposed and lint-clean. Bootstrap
  note: the draft agent also tried to write this very entry into DECISIONS.md
  and the non_planning_change guard rejected the iteration — correct
  behavior; the owner writes the decision log, the planner writes the plan.
  **Execution proof (ST19, REQ-TP2 + REQ-TP3):** seed run `20260702-133736`
  (mock `.kelix/st19a-mock/`, 3 verified ledger rows, transcripts
  `.kelix/runs/20260702-133736/`); diagnose →
  `.kelix/memory/diagnosis-st19b.md` (`## Findings`, cites seed run);
  propose id `20260702-134659` (branch `kelix/propose-20260702-134659`,
  merge sha `a6fe858`, sidecar `.kelix/memory/proposal-20260702-134659.json`,
  touched `.kelix/prompts/iteration.md` only, `validate_propose_diff` clean);
  merge recorded in `loop-metrics.json` `proposal_outcomes[]` with prediction
  preserved; post-merge run `20260702-135224` (3 verified rows, distinct
  run_id, transcripts `.kelix/runs/20260702-135224/`); grade
  `inconclusive` (1 post-merge run — need ≥3 for improved/regressed).
  ST19 closes the v0.3 ship gate.
- D23 (kelix watch — owner-directed, built outside the loop): live
  observability for running agents. The adapter's reader thread now streams
  chunks to `.kelix/runs/<id>/iter-NNN.live.log` (flushed per chunk); the
  runner writes `heartbeat.json` (run id, iteration, task, pid, status) at
  iteration start and run end; `kelix watch` tails the active run across
  iteration hops, `--run-id` selects among fleet runs, ctrl-c detaches
  without touching the run; `kelix status` lists live runs. All bookkeeping
  stays gitignored/checkpoint-excluded. Side effect worth its own line: the
  reader switched from blocking `read(4096)` to `read1(4096)`, which also
  fixes a latent inactivity-watchdog unfairness (a slowly-chatty agent's
  activity clock only ticked per full 4KB buffer). Built directly by the
  owner-side assistant for immediate use on the next runs; recorded here
  per the bootstrap-intervention rule.
