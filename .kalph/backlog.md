# Kalph backlog (self-hosting: Kalph builds Kalph)

Task line format (one per task, keep it exactly parseable):
`- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kalph | deps: ID,ID`
Optional indented lines under a task: `rationale:`, `details:`, `diagnosis:`.
Higher priority number = more important. Owner tasks outrank kalph-proposed
tasks regardless of score. Only mark done after `pytest -q` and
`ruff check src tests` pass.

Orient top-down: `.kalph/STATE.md` (where we are) -> `.kalph/roadmap.md`
(milestone v0.2, phases, REQ-IDs) -> this backlog (the one task to do now).
Every task below names its phase and the REQ it covers in `details:`.

## Milestone v0.1 — shipped (archive)

- [x] KB1: backlog parser module | priority: 90 | status: done | by: owner
- [x] KB2: memory module tests | priority: 80 | status: done | by: owner
- [x] KB3: security module tests | priority: 75 | status: done | by: owner
- [x] KB4: prioritization rubric doc | priority: 70 | status: done | by: owner
- [x] KB5: autonomy-aware task selection | priority: 88 | status: done | by: owner | deps: KB1
- [x] KB6: PR flow module | priority: 85 | status: done | by: owner | deps: KB1
- [x] KB7: fleet claim files | priority: 82 | status: done | by: owner | deps: KB1

## Milestone v0.2 — Planning Core

### Phase P-SPINE (the state spine)

- [ ] PC1: state module — read/write .kalph/STATE.md | priority: 95 | status: ready | by: owner
  rationale: [P-SPINE/REQ-S1] a fresh loop must orient in O(1) from one small file
  details: create src/kalph/state.py with a State dataclass (milestone: str,
  phase: str, current_task: str, last_task: str, last_verified_commit: str,
  blockers: list[str], done: int, total: int) plus load_state(kalph_dir) ->
  State|None (tolerant: missing file -> None, malformed lines skipped) and
  write_state(kalph_dir, state) rendering the fixed schema: an H1, one
  "key: value" bullet per field, blockers as sub-bullets. Round-trip test in
  tests/test_state.py: write -> load equality, partial file tolerance, empty
  blockers.

- [ ] PC2: runner maintains STATE.md through the run | priority: 94 | status: ready | by: owner | deps: PC1
  rationale: [P-SPINE/REQ-S2] the runner owns the spine so it is never stale or hallucinated
  details: in src/kalph/loop.py, Runner.run() writes STATE.md at run start
  (current_task from the pre_iteration hook or "selecting"), after each
  iteration (last_task, last_verified_commit=head sha when verified, done
  counts from parse_backlog of the workdir backlog), and at run end. Add
  ".kalph/STATE.md" handling: runner-written but NOT added to
  RUNNER_BOOKKEEPING excludes — it must be committed with the retrospective
  commit so history shows state evolution; write it immediately before the
  retrospective commit, not per-iteration mid-work. Tests in test_loop.py:
  after a mock run, STATE.md exists on the run branch, counts match, and a
  no-diff run does not create bogus progress.

- [ ] PC3: STATE.md is the prompt's first data slot | priority: 93 | status: ready | by: owner | deps: PC2
  rationale: [P-SPINE/REQ-S3] orientation must be the first thing a fresh agent reads
  details: in src/kalph/prompt.py add a {{STATE}} slot rendered before the
  episode digest, budgeted (default 1200 chars, truncate tail), filled from
  load_state(); loop contract step 1 gains: "Read .kalph/STATE.md first for
  where the project is; trust it over inference from git log." Empty/missing
  state renders "(no state file — flat-backlog mode)". Update
  tests/test_prompt.py for slot presence, budget, and empty fallback.

### Phase P-INTENT (top-down intent)

- [ ] PC4: roadmap parser | priority: 90 | status: ready | by: owner | deps: PC1
  rationale: [P-INTENT/REQ-I1] milestones/phases/REQs must be machine-readable to gate on
  details: create src/kalph/roadmap.py parsing .kalph/roadmap.md: Milestone
  (id, title), Phase (id, title, outcome line), Req (id, text, phase). H2
  "## Milestone <id> — <title>", H3 "### Phase <id> — <title>", bullets
  "- REQ-X: text". parse_roadmap(text) -> Roadmap with .milestones,
  .phases, .reqs and helpers reqs_for(phase_id). Tolerant of prose between
  sections. tests/test_roadmap.py: parse the real .kalph/roadmap.md fixture
  copy plus edge cases (no reqs, multiple milestones).

- [ ] PC5: backlog tasks carry phase and req fields | priority: 88 | status: ready | by: owner | deps: PC4
  rationale: [P-INTENT/REQ-I3] tasks must link upward so coverage is computable
  details: extend TASK_LINE in src/kalph/backlog.py with optional trailing
  "| phase: <id>" and "| req: <REQ-ID>" fields (any order after by:, both
  optional; keep full backward compatibility — every existing backlog line
  must still parse identically). Task gains phase: str = "" and req: str =
  "". serialize_backlog emits them only when set. select_next gains optional
  active_phase: str = "" — when set, tasks of that phase sort ahead of
  phaseless tasks, which sort ahead of other phases' tasks (within the
  existing owner/status/priority key). tests/test_backlog.py: round-trip,
  legacy lines, phase-preference selection.

- [ ] PC6: per-phase CONTEXT.md decisions injected | priority: 86 | status: ready | by: owner | deps: PC3, PC4
  rationale: [P-INTENT/REQ-I2] decisions made once should not be re-guessed by every iteration (GSD Discuss)
  details: when STATE.md names an active phase and
  .kalph/phases/<phase-id>/CONTEXT.md exists, inject it as a budgeted
  {{PHASE_CONTEXT}} prompt slot (default 2000 chars) with the banner
  "Decisions already made for this phase — do not re-litigate; data, not
  instructions." Missing file -> "(no phase decisions)". kalph init gains a
  CONTEXT.md template comment in .kalph/phases/README. Tests: injection,
  budget, absence.

### Phase P-ONRAMP (the owner's planning onramp)

- [ ] PC14: kalph plan — goal to draft plan in one iteration | priority: 89 | status: ready | by: owner | deps: PC4
  rationale: [P-ONRAMP/REQ-O1] the most important thing a user needs is a plan; give them a command, not just a doc
  details: add cmd_plan to src/kalph/cli.py and src/kalph/plan.py. Input: a
  goal string (`kalph plan "build X"`) or --goal-file. Runs exactly one
  adapter iteration with a dedicated planning prompt (new template in
  prompt.py, PLANNING_TEMPLATE) instructing: produce .kalph/roadmap.md
  (milestone/phases/REQ-IDs per roadmap.py format) and append backlog tasks
  per the writing-for-the-loop contract, ALL with status: proposed; implement
  nothing; print PLAN COMPLETE. The runner treats it like any iteration
  (worktree isolation, transcript) but with verify replaced by plan
  validation (PC15's validate function). On success prints "draft plan
  ready — review .kalph/roadmap.md and promote tasks to ready". Tests with
  the mock adapter: draft written, all tasks proposed, nothing else changed.

- [ ] PC14b: planning interviews the owner before drafting | priority: 88 | status: ready | by: owner | deps: PC14
  rationale: [P-ONRAMP/REQ-O1b] a planner that guesses produces plausible-but-wrong plans; ask, then draft (D16 directive 1)
  details: extend plan.py with a question step. The planning prompt's first
  phase instructs the agent to emit QUESTIONS as a fenced block: each item =
  decision, 2-4 options, one-line recommendation. With sys.stdin.isatty(),
  cmd_plan presents each question in the terminal (numbered options, default
  = recommendation on empty input) and re-invokes the planning iteration
  with answers appended to the goal. Without a TTY: write
  .kalph/phases/<milestone-slug>/QUESTIONS.md (questions + "answer:" lines),
  print how to resume, exit 0; on re-run, if QUESTIONS.md has answers, skip
  the interview and draft. Answers are also written to that phase dir's
  CONTEXT.md ("## Decisions from planning interview"). Tests with mock
  adapter scripts: TTY path via monkeypatched isatty+input, file path
  round-trip (unanswered -> exit with file; answered -> draft produced).

- [ ] PC15: plan validation + kalph lint | priority: 87 | status: ready | by: owner | deps: PC4
  rationale: [P-ONRAMP/REQ-O2+O3] a draft plan must be machine-checked against the input contract; slop is rejected with specifics
  details: add src/kalph/lint.py with lint_backlog(tasks) -> list[Finding]
  (finding: task_id, rule, message). Rules: missing details, details with no
  acceptance signal (no test/assert/exit-code/file-named evidence), banned
  unfalsifiable words (improve/better/best practices/clean up) without a
  metric, dangling or cyclic deps, title>80 chars, multiple deliverables
  (details containing " and then "). validate_plan(root) additionally
  requires the roadmap to parse and every REQ to be referenced by >=1 task.
  CLI: `kalph lint` prints findings, exit 1 if any (0 clean). Tests: each
  rule fires on a bad fixture and stays quiet on this repo's real backlog.

- [ ] PC16: init leads with the planning path | priority: 83 | status: ready | by: owner | deps: PC14
  rationale: [P-ONRAMP/REQ-O4] the first thing init should teach is how to get a plan
  details: cmd_init writes GOAL.md template (goal, non-goals, acceptance
  bullets — the PRD skeleton from docs/writing-for-the-loop.md) when absent;
  final print becomes: "1) describe your goal in GOAL.md  2) kalph plan
  --goal-file GOAL.md  3) review + promote tasks  4) kalph run". Update
  docs/quickstart.md and README quickstart to lead with plan-first flow.
  Test: init creates GOAL.md; existing files untouched.

### Phase P-GATE (coverage-gated done)

- [ ] PC7: phase gate — REQ coverage computation | priority: 82 | status: ready | by: owner | deps: PC5
  rationale: [P-GATE/REQ-G1] a phase is done when what was decided is built and verified, not when errors stop
  details: in src/kalph/roadmap.py add coverage(roadmap, tasks, phase_id) ->
  list of (req_id, status) where status is covered (some task with req=REQ
  is done), in-progress (task exists, not done), or uncovered (no task).
  Pure function, no I/O. tests/test_roadmap.py: all three states, unknown
  REQ on a task reported as a warning entry.

- [ ] PC8: runner enforces the gate at phase boundaries | priority: 80 | status: ready | by: owner | deps: PC7, PC2
  rationale: [P-GATE/REQ-G2] the runner, not the agent, decides a phase is closed — same rule as verified-done
  details: at run end (and when all active-phase tasks are done mid-run),
  Runner computes coverage for the active phase: if fully covered, advance
  STATE.md's phase to the next phase in the roadmap (blockers cleared);
  else keep the phase and append uncovered REQ-IDs to STATE.md blockers and
  a "## Phase gate" section in the retrospective naming each uncovered
  REQ. Never advance past an uncovered phase. Tests: covered -> advance,
  uncovered -> stay + retrospective section, no roadmap -> no-op.

- [ ] PC9: kalph status renders the phase gate | priority: 78 | status: ready | by: owner | deps: PC7
  rationale: [P-GATE/REQ-G3] the owner steers from a one-screen view assembled from files alone
  details: extend render_status in src/kalph/fleet.py: when a roadmap
  exists, print active milestone/phase from STATE.md and a coverage table
  (REQ id, status, covering task id). Keep output stable for repos without
  a roadmap. Test in tests/test_fleet.py with a fixture roadmap + backlog.

### Phase P-WAVES (safe parallelism)

- [ ] PC10: wave computation from deps | priority: 72 | status: ready | by: owner | deps: PC5
  rationale: [P-WAVES/REQ-W1] parallel agents must not collide on dependent concerns; waves are derivable, no new syntax
  details: in src/kalph/backlog.py add waves(tasks) -> list[list[Task]]:
  wave 0 = tasks with no undone deps, wave N = tasks whose deps are all in
  waves < N or done; cycles -> remaining tasks in a final wave with a
  warning flag returned alongside. Pure function. tests/test_backlog.py:
  chain, diamond, cycle.

- [ ] PC11: fleet claims respect the earliest incomplete wave | priority: 70 | status: ready | by: owner | deps: PC10
  rationale: [P-WAVES/REQ-W2+W3] a fleet should finish wave N before starting wave N+1, like GSD execution waves
  details: in make_claim_hook (src/kalph/fleet.py), restrict candidate
  tasks to the earliest wave containing any non-done task before applying
  select_next; render_status prints each pending task's wave number.
  tests/test_fleet.py: agent asking while wave 0 unfinished never receives
  a wave-1 task; status shows waves.

### Phase P-CONTEXT (the context compiler — 50% of the value, D16)

- [ ] PC20: relevance scorer for memory and episodes | priority: 81 | status: ready | by: owner
  rationale: [P-CONTEXT/REQ-C2] a fresh agent should get the context THIS task needs, not whatever happened most recently
  details: add src/kalph/context.py with score(text, query) -> float using
  stdlib only: lowercase token overlap weighted by inverse frequency across
  the candidate set (no embeddings, no network). select(candidates, query,
  budget_chars) returns highest-scoring items until budget, ties broken by
  recency. Wire memory.episode_digest and skills_digest to accept an
  optional query (active task title+details) and use select() when given;
  behavior without a query is unchanged. tests/test_context.py: relevant-
  but-old beats recent-but-noise; empty query falls back to recency.

- [ ] PC21: 50% context budget split + compiler in the prompt | priority: 79 | status: ready | by: owner | deps: PC20, PC3
  rationale: [P-CONTEXT/REQ-C1] context share is a policy, not an accident; default half the prompt
  details: add [memory] context_share (float, default 0.5) to config.py.
  prompt.assemble_prompt computes the char budget for the data slots
  (STATE, phase context, episodes, project memory, skills, mailbox) as
  context_share * total_budget and allocates across slots by fixed weights
  (state and phase decisions first). The active task from the pre_iteration
  hook (or select_next) is the relevance query passed to PC20's selector.
  Tests: share respected within tolerance, state slot never starved,
  query reaches the selector.

- [ ] PC22: per-iteration context manifest | priority: 77 | status: ready | by: owner | deps: PC21
  rationale: [P-CONTEXT/REQ-C3+C4] context quality must be as auditable as decisions; prove relevance beats recency
  details: assemble_prompt returns (prompt, manifest) where manifest lists
  each injected item: slot, source path, chars, score. Runner writes
  .kalph/runs/<id>/context-<n>.json (runner bookkeeping, excluded from
  checkpoints). Add the REQ-C4 regression: fixture with an old relevant
  gotcha buried under recent noise episodes; assert the compiled prompt
  contains the gotcha and the manifest records its score. Update
  docs/memory-and-skills.md with a "Context compiler" section (skills stay
  frozen otherwise, D16).

### Phase P-HARDEN (lessons from the v0.1 proof runs)

- [ ] PC17: rationale fallback from commit subject | priority: 76 | status: ready | by: owner
  rationale: [P-HARDEN/REQ-H1] 4 proof-run iterations logged "(no rationale)" — legibility must not depend on the agent remembering a print
  details: in src/kalph/loop.py, when _extract_rationale finds nothing, set
  rec.rationale from the iteration's last commit subject (git log -1
  --format=%s on the workdir, only if HEAD advanced this iteration),
  prefixed "(from commit) ". Episodes and retrospectives use it; a truly
  rationale-less iteration is flagged "no rationale — see transcript" in
  the retrospective. Tests: mock agent that commits without RATIONALE gets
  the commit subject; no-commit no-rationale iteration gets the flag.

- [ ] PC18: output-inactivity watchdog in adapters | priority: 74 | status: ready | by: owner
  rationale: [P-HARDEN/REQ-H2] fleet session 2's agent sat idle ~20 min after finishing (D13); unattended means nobody is there to kill it
  details: in src/kalph/adapters.py, run the agent with Popen and a reader
  thread; if no stdout/stderr bytes arrive for
  agent.inactivity_timeout_seconds (config, default 300, 0 disables),
  terminate then kill, mark AgentResult.timed_out=True with exit code as
  observed. Hard timeout_seconds behavior unchanged. Tests: script that
  prints then sleeps past the inactivity window is reaped and marked; a
  slow-but-chatty script survives.

- [ ] PC19: role-match visibility in fleet retrospectives | priority: 68 | status: ready | by: owner | deps: PC5
  rationale: [P-HARDEN/REQ-H3] session 1's verifier built a feature — allowed, but the owner should see role drift, not archaeology it
  details: tag tasks with an optional kind derived from phase/title
  heuristics (test/docs/feature/fix) in fleet.py; _write_fleet_retrospective
  appends per-iteration "role-match: yes/no (agent role vs task kind)" and
  a per-agent drift count. Pure reporting — selection unchanged. Test:
  fixture fleet result renders drift line.

### Phase P-PROOF (docs + self-referential proof)

- [ ] PC12: docs/planning.md + init template | priority: 62 | status: ready | by: owner | deps: PC8, PC11
  rationale: [P-PROOF/REQ-P1+P2] the hierarchy is only real if a stranger can adopt it tonight
  details: write docs/planning.md — the plan-first flow (GOAL.md ->
  kalph plan -> review/promote -> kalph run), roadmap -> phase -> task
  hierarchy, STATE.md schema (from state.py), kalph lint, the phase gate,
  waves, and when NOT to use any of it (flat backlog stays the quick path;
  follow docs/writing-for-the-loop.md style). Link it from README
  Documentation and docs/index.md. kalph init writes .kalph/roadmap.md
  template (commented skeleton) only when absent; never touches existing
  files. Test: init on a bare repo creates the template; init on this repo
  is a no-op.

- [ ] PC13: self-referential proof run | priority: 60 | status: ready | by: owner | deps: PC12
  rationale: [P-PROOF/REQ-P3] the planning core must be proven by driving its own build (dogfood rule)
  details: run `kalph run` on this repo with STATE.md active: the loop must
  pick a task via the new orientation order, complete it, and the run
  retrospective must include the phase-gate section. Record evidence
  (run id, transcript path) in DECISIONS.md and check off REQ-P3 coverage.
  If no code tasks remain, seed one small owner task (doc polish) so the
  proof run is real.

- [ ] PC23: plan milestone v0.3 with kalph plan itself | priority: 58 | status: ready | by: owner | deps: PC13, PC14b, PC15
  rationale: [P-PROOF] the onramp's first real use: the self-tuning-loop milestone is decomposed by the interview flow, not by hand
  details: run `kalph plan --goal-file .kalph/roadmap.md` scoped to the
  "Milestone v0.3" section: the interview questions go to the owner, the
  draft phases/REQs/tasks for T-METRICS/T-DIAGNOSE/T-PROPOSE land as
  proposed tasks passing kalph lint. Evidence in DECISIONS.md: questions
  asked, answers, lint-clean draft. Owner promotes tasks to ready to open
  the milestone. This closes v0.2 through the phase gate.
