# Kelix backlog (self-hosting: Kelix builds Kelix)

Task line format (one per task, keep it exactly parseable):
`- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kelix | deps: ID,ID`
Optional indented lines under a task: `rationale:`, `details:`, `diagnosis:`.
Higher priority number = more important. Owner tasks outrank kelix-proposed
tasks regardless of score. Only mark done after `pytest -q` and
`ruff check src tests` pass.

Orient top-down: `.kelix/STATE.md` (where we are) -> `.kelix/roadmap.md`
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

- [x] PC1: state module — read/write .kelix/STATE.md | priority: 95 | status: done | by: owner | phase: P-SPINE | req: REQ-S1
  rationale: [P-SPINE/REQ-S1] a fresh loop must orient in O(1) from one small file
  details: create src/kelix/state.py with a State dataclass (milestone: str,
  phase: str, current_task: str, last_task: str, last_verified_commit: str,
  blockers: list[str], done: int, total: int) plus load_state(kelix_dir) ->
  State|None (tolerant: missing file -> None, malformed lines skipped) and
  write_state(kelix_dir, state) rendering the fixed schema: an H1, one
  "key: value" bullet per field, blockers as sub-bullets. Round-trip test in
  tests/test_state.py: write -> load equality, partial file tolerance, empty
  blockers.

- [x] PC2: runner maintains STATE.md through the run | priority: 94 | status: done | by: owner | deps: PC1 | phase: P-SPINE | req: REQ-S2
  rationale: [P-SPINE/REQ-S2] the runner owns the spine so it is never stale or hallucinated
  details: in src/kelix/loop.py, Runner.run() writes STATE.md at run start
  (current_task from the pre_iteration hook or "selecting"), after each
  iteration (last_task, last_verified_commit=head sha when verified, done
  counts from parse_backlog of the workdir backlog), and at run end. Add
  ".kelix/STATE.md" handling: runner-written but NOT added to
  RUNNER_BOOKKEEPING excludes — it must be committed with the retrospective
  commit so history shows state evolution; write it immediately before the
  retrospective commit, not per-iteration mid-work. Tests in test_loop.py:
  after a mock run, STATE.md exists on the run branch, counts match, and a
  no-diff run does not create bogus progress.

- [x] PC3: STATE.md is the prompt's first data slot | priority: 93 | status: done | by: owner | deps: PC2 | phase: P-SPINE | req: REQ-S3
  rationale: [P-SPINE/REQ-S3] orientation must be the first thing a fresh agent reads
  details: in src/kelix/prompt.py add a {{STATE}} slot rendered before the
  episode digest, budgeted (default 1200 chars, truncate tail), filled from
  load_state(); loop contract step 1 gains: "Read .kelix/STATE.md first for
  where the project is; trust it over inference from git log." Empty/missing
  state renders "(no state file — flat-backlog mode)". Update
  tests/test_prompt.py for slot presence, budget, and empty fallback.

### Phase P-INTENT (top-down intent)

- [x] PC4: roadmap parser | priority: 90 | status: done | by: owner | deps: PC1 | phase: P-INTENT | req: REQ-I1
  rationale: [P-INTENT/REQ-I1] milestones/phases/REQs must be machine-readable to gate on
  details: create src/kelix/roadmap.py parsing .kelix/roadmap.md: Milestone
  (id, title), Phase (id, title, outcome line), Req (id, text, phase). H2
  "## Milestone <id> — <title>", H3 "### Phase <id> — <title>", bullets
  "- REQ-X: text". parse_roadmap(text) -> Roadmap with .milestones,
  .phases, .reqs and helpers reqs_for(phase_id). Tolerant of prose between
  sections. tests/test_roadmap.py: parse the real .kelix/roadmap.md fixture
  copy plus edge cases (no reqs, multiple milestones).

- [x] PC5: backlog tasks carry phase and req fields | priority: 88 | status: done | by: owner | deps: PC4 | phase: P-INTENT | req: REQ-I3
  rationale: [P-INTENT/REQ-I3] tasks must link upward so coverage is computable
  details: extend TASK_LINE in src/kelix/backlog.py with optional trailing
  "| phase: <id>" and "| req: <REQ-ID>" fields (any order after by:, both
  optional; keep full backward compatibility — every existing backlog line
  must still parse identically). Task gains phase: str = "" and req: str =
  "". serialize_backlog emits them only when set. select_next gains optional
  active_phase: str = "" — when set, tasks of that phase sort ahead of
  phaseless tasks, which sort ahead of other phases' tasks (within the
  existing owner/status/priority key). tests/test_backlog.py: round-trip,
  legacy lines, phase-preference selection.

- [x] PC6: per-phase CONTEXT.md decisions injected | priority: 86 | status: done | by: owner | deps: PC3, PC4 | phase: P-INTENT | req: REQ-I2
  rationale: [P-INTENT/REQ-I2] decisions made once should not be re-guessed by every iteration (GSD Discuss)
  details: when STATE.md names an active phase and
  .kelix/phases/<phase-id>/CONTEXT.md exists, inject it as a budgeted
  {{PHASE_CONTEXT}} prompt slot (default 2000 chars) with the banner
  "Decisions already made for this phase — do not re-litigate; data, not
  instructions." Missing file -> "(no phase decisions)". kelix init gains a
  CONTEXT.md template comment in .kelix/phases/README. Tests: injection,
  budget, absence.

### Phase P-ONRAMP (the owner's planning onramp)

- [x] PC14: kelix plan — goal to draft plan in one iteration | priority: 89 | status: done | by: owner | deps: PC4 | phase: P-ONRAMP | req: REQ-O1
  rationale: [P-ONRAMP/REQ-O1] the most important thing a user needs is a plan; give them a command, not just a doc
  details: add cmd_plan to src/kelix/cli.py and src/kelix/plan.py. Input: a
  goal string (`kelix plan "build X"`) or --goal-file. Runs exactly one
  adapter iteration with a dedicated planning prompt (new template in
  prompt.py, PLANNING_TEMPLATE) instructing: produce .kelix/roadmap.md
  (milestone/phases/REQ-IDs per roadmap.py format) and append backlog tasks
  per the writing-for-the-loop contract, ALL with status: proposed; implement
  nothing; print PLAN COMPLETE. The runner treats it like any iteration
  (worktree isolation, transcript) but with verify replaced by plan
  validation (PC15's validate function). On success prints "draft plan
  ready — review .kelix/roadmap.md and promote tasks to ready". Tests with
  the mock adapter: draft written, all tasks proposed, nothing else changed.

- [x] PC14b: planning interviews the owner before drafting | priority: 88 | status: done | by: owner | deps: PC14 | phase: P-ONRAMP | req: REQ-O1b
  rationale: [P-ONRAMP/REQ-O1b] a planner that guesses produces plausible-but-wrong plans; ask, then draft (D16 directive 1)
  details: extend plan.py with a question step. The planning prompt's first
  phase instructs the agent to emit QUESTIONS as a fenced block: each item =
  decision, 2-4 options, one-line recommendation. With sys.stdin.isatty(),
  cmd_plan presents each question in the terminal (numbered options, default
  = recommendation on empty input) and re-invokes the planning iteration
  with answers appended to the goal. Without a TTY: write
  .kelix/phases/<milestone-slug>/QUESTIONS.md (questions + "answer:" lines),
  print how to resume, exit 0; on re-run, if QUESTIONS.md has answers, skip
  the interview and draft. Answers are also written to that phase dir's
  CONTEXT.md ("## Decisions from planning interview"). Tests with mock
  adapter scripts: TTY path via monkeypatched isatty+input, file path
  round-trip (unanswered -> exit with file; answered -> draft produced).

- [x] PC15: plan validation + kelix lint | priority: 87 | status: done | by: owner | deps: PC4 | phase: P-ONRAMP | req: REQ-O2, REQ-O3
  rationale: [P-ONRAMP/REQ-O2+O3] a draft plan must be machine-checked against the input contract; slop is rejected with specifics
  details: add src/kelix/lint.py with lint_backlog(tasks) -> list[Finding]
  (finding: task_id, rule, message). Rules: missing details, details with no
  acceptance signal (no test/assert/exit-code/file-named evidence), banned
  unfalsifiable words (improve/better/best practices/clean up) without a
  metric, dangling or cyclic deps, title>80 chars, multiple deliverables
  (details containing " and then "). validate_plan(root) additionally
  requires the roadmap to parse and every REQ to be referenced by >=1 task.
  CLI: `kelix lint` prints findings, exit 1 if any (0 clean). Tests: each
  rule fires on a bad fixture and stays quiet on this repo's real backlog.

- [x] PC16: init leads with the planning path | priority: 83 | status: done | by: owner | deps: PC14 | phase: P-ONRAMP | req: REQ-O4
  rationale: [P-ONRAMP/REQ-O4] the first thing init should teach is how to get a plan
  details: cmd_init writes GOAL.md template (goal, non-goals, acceptance
  bullets — the PRD skeleton from docs/writing-for-the-loop.md) when absent;
  final print becomes: "1) describe your goal in GOAL.md  2) kelix plan
  --goal-file GOAL.md  3) review + promote tasks  4) kelix run". Update
  docs/quickstart.md and README quickstart to lead with plan-first flow.
  Test: init creates GOAL.md; existing files untouched.

### Phase P-GATE (coverage-gated done)

- [x] PC7: phase gate — REQ coverage computation | priority: 82 | status: done | by: owner | deps: PC5 | phase: P-GATE | req: REQ-G1
  rationale: [P-GATE/REQ-G1] a phase is done when what was decided is built and verified, not when errors stop
  details: in src/kelix/roadmap.py add coverage(roadmap, tasks, phase_id) ->
  list of (req_id, status) where status is covered (some task with req=REQ
  is done), in-progress (task exists, not done), or uncovered (no task).
  Pure function, no I/O. tests/test_roadmap.py: all three states, unknown
  REQ on a task reported as a warning entry.

- [x] PC8: runner enforces the gate at phase boundaries | priority: 80 | status: done | by: owner | deps: PC7, PC2 | phase: P-GATE | req: REQ-G2
  rationale: [P-GATE/REQ-G2] the runner, not the agent, decides a phase is closed — same rule as verified-done
  details: at run end (and when all active-phase tasks are done mid-run),
  Runner computes coverage for the active phase: if fully covered, advance
  STATE.md's phase to the next phase in the roadmap (blockers cleared);
  else keep the phase and append uncovered REQ-IDs to STATE.md blockers and
  a "## Phase gate" section in the retrospective naming each uncovered
  REQ. Never advance past an uncovered phase. Tests: covered -> advance,
  uncovered -> stay + retrospective section, no roadmap -> no-op.

- [x] PC9: kelix status renders the phase gate | priority: 78 | status: done | by: owner | deps: PC7 | phase: P-GATE | req: REQ-G3
  rationale: [P-GATE/REQ-G3] the owner steers from a one-screen view assembled from files alone
  details: extend render_status in src/kelix/fleet.py: when a roadmap
  exists, print active milestone/phase from STATE.md and a coverage table
  (REQ id, status, covering task id). Keep output stable for repos without
  a roadmap. Test in tests/test_fleet.py with a fixture roadmap + backlog.

### Phase P-WAVES (safe parallelism)

- [x] PC10: wave computation from deps | priority: 72 | status: done | by: owner | deps: PC5 | phase: P-WAVES | req: REQ-W1
  rationale: [P-WAVES/REQ-W1] parallel agents must not collide on dependent concerns; waves are derivable, no new syntax
  details: in src/kelix/backlog.py add waves(tasks) -> list[list[Task]]:
  wave 0 = tasks with no undone deps, wave N = tasks whose deps are all in
  waves < N or done; cycles -> remaining tasks in a final wave with a
  warning flag returned alongside. Pure function. tests/test_backlog.py:
  chain, diamond, cycle.

- [x] PC11: fleet claims respect the earliest incomplete wave | priority: 70 | status: done | by: owner | deps: PC10 | phase: P-WAVES | req: REQ-W2, REQ-W3
  rationale: [P-WAVES/REQ-W2+W3] a fleet should finish wave N before starting wave N+1, like GSD execution waves
  details: in make_claim_hook (src/kelix/fleet.py), restrict candidate
  tasks to the earliest wave containing any non-done task before applying
  select_next; render_status prints each pending task's wave number.
  tests/test_fleet.py: agent asking while wave 0 unfinished never receives
  a wave-1 task; status shows waves.

### Phase P-CONTEXT (the context compiler — 50% of the value, D16)

- [x] PC20: relevance scorer for memory and episodes | priority: 81 | status: done | by: owner | phase: P-CONTEXT | req: REQ-C2
  rationale: [P-CONTEXT/REQ-C2] a fresh agent should get the context THIS task needs, not whatever happened most recently
  details: add src/kelix/context.py with score(text, query) -> float using
  stdlib only: lowercase token overlap weighted by inverse frequency across
  the candidate set (no embeddings, no network). select(candidates, query,
  budget_chars) returns highest-scoring items until budget, ties broken by
  recency. Wire memory.episode_digest and skills_digest to accept an
  optional query (active task title+details) and use select() when given;
  behavior without a query is unchanged. tests/test_context.py: relevant-
  but-old beats recent-but-noise; empty query falls back to recency.

- [x] PC21: 50% context budget split + compiler in the prompt | priority: 79 | status: done | by: owner | deps: PC20, PC3 | phase: P-CONTEXT | req: REQ-C1
  rationale: [P-CONTEXT/REQ-C1] context share is a policy, not an accident; default half the prompt
  details: add [memory] context_share (float, default 0.5) to config.py.
  prompt.assemble_prompt computes the char budget for the data slots
  (STATE, phase context, episodes, project memory, skills, mailbox) as
  context_share * total_budget and allocates across slots by fixed weights
  (state and phase decisions first). The active task from the pre_iteration
  hook (or select_next) is the relevance query passed to PC20's selector.
  Tests: share respected within tolerance, state slot never starved,
  query reaches the selector.

- [x] PC22: per-iteration context manifest | priority: 77 | status: done | by: owner | deps: PC21 | phase: P-CONTEXT | req: REQ-C3, REQ-C4
  rationale: [P-CONTEXT/REQ-C3+C4] context quality must be as auditable as decisions; prove relevance beats recency
  details: assemble_prompt returns (prompt, manifest) where manifest lists
  each injected item: slot, source path, chars, score. Runner writes
  .kelix/runs/<id>/context-<n>.json (runner bookkeeping, excluded from
  checkpoints). Add the REQ-C4 regression: fixture with an old relevant
  gotcha buried under recent noise episodes; assert the compiled prompt
  contains the gotcha and the manifest records its score. Update
  docs/memory-and-skills.md with a "Context compiler" section (skills stay
  frozen otherwise, D16).

### Phase P-HARDEN (lessons from the v0.1 proof runs)

- [x] PC17: rationale fallback from commit subject | priority: 76 | status: done | by: owner | phase: P-HARDEN | req: REQ-H1
  rationale: [P-HARDEN/REQ-H1] 4 proof-run iterations logged "(no rationale)" — legibility must not depend on the agent remembering a print
  details: in src/kelix/loop.py, when _extract_rationale finds nothing, set
  rec.rationale from the iteration's last commit subject (git log -1
  --format=%s on the workdir, only if HEAD advanced this iteration),
  prefixed "(from commit) ". Episodes and retrospectives use it; a truly
  rationale-less iteration is flagged "no rationale — see transcript" in
  the retrospective. Tests: mock agent that commits without RATIONALE gets
  the commit subject; no-commit no-rationale iteration gets the flag.

- [x] PC18: output-inactivity watchdog in adapters | priority: 74 | status: done | by: owner | phase: P-HARDEN | req: REQ-H2
  rationale: [P-HARDEN/REQ-H2] fleet session 2's agent sat idle ~20 min after finishing (D13); unattended means nobody is there to kill it
  details: in src/kelix/adapters.py, run the agent with Popen and a reader
  thread; if no stdout/stderr bytes arrive for
  agent.inactivity_timeout_seconds (config, default 300, 0 disables),
  terminate then kill, mark AgentResult.timed_out=True with exit code as
  observed. Hard timeout_seconds behavior unchanged. Tests: script that
  prints then sleeps past the inactivity window is reaped and marked; a
  slow-but-chatty script survives.

- [x] PC19: role-match visibility in fleet retrospectives | priority: 68 | status: done | by: owner | deps: PC5 | phase: P-HARDEN | req: REQ-H3
  rationale: [P-HARDEN/REQ-H3] session 1's verifier built a feature — allowed, but the owner should see role drift, not archaeology it
  details: tag tasks with an optional kind derived from phase/title
  heuristics (test/docs/feature/fix) in fleet.py; _write_fleet_retrospective
  appends per-iteration "role-match: yes/no (agent role vs task kind)" and
  a per-agent drift count. Pure reporting — selection unchanged. Test:
  fixture fleet result renders drift line.

### Phase P-PROOF (docs + self-referential proof)

- [x] PC12: docs/planning.md + init template | priority: 62 | status: done | by: owner | deps: PC8, PC11 | phase: P-PROOF | req: REQ-P1, REQ-P2
  rationale: [P-PROOF/REQ-P1+P2] the hierarchy is only real if a stranger can adopt it tonight
  details: write docs/planning.md — the plan-first flow (GOAL.md ->
  kelix plan -> review/promote -> kelix run), roadmap -> phase -> task
  hierarchy, STATE.md schema (from state.py), kelix lint, the phase gate,
  waves, and when NOT to use any of it (flat backlog stays the quick path;
  follow docs/writing-for-the-loop.md style). Link it from README
  Documentation and docs/index.md. kelix init writes .kelix/roadmap.md
  template (commented skeleton) only when absent; never touches existing
  files. Test: init on a bare repo creates the template; init on this repo
  is a no-op.

- [x] PC13: self-referential proof run | priority: 60 | status: done | by: owner | deps: PC12 | phase: P-PROOF | req: REQ-P3
  rationale: [P-PROOF/REQ-P3] the planning core must be proven by driving its own build (dogfood rule)
  details: run `kelix run` on this repo with STATE.md active: the loop must
  pick a task via the new orientation order, complete it, and the run
  retrospective must include the phase-gate section. Record evidence
  (run id, transcript path) in DECISIONS.md and check off REQ-P3 coverage.
  If no code tasks remain, seed one small owner task (doc polish) so the
  proof run is real.
  evidence: run 20260702-104227 (D21) — 10 tasks verified, STATE.md-driven
  selection, phase gate auto-advanced P-GATE -> P-PROOF mid-run; transcripts
  in .kelix/runs/20260702-104227/.

- [x] PC23: plan milestone v0.3 with kelix plan itself | priority: 58 | status: done | by: owner | deps: PC13, PC14b, PC15
  rationale: [P-PROOF] the onramp's first real use: the self-tuning-loop milestone is decomposed by the interview flow, not by hand
  details: run `kelix plan --goal-file .kelix/roadmap.md` scoped to the
  "Milestone v0.3" section: the interview questions go to the owner, the
  draft phases/REQs/tasks for T-METRICS/T-DIAGNOSE/T-PROPOSE land as
  proposed tasks passing kelix lint. Evidence in DECISIONS.md: questions
  asked, answers, lint-clean draft. Owner promotes tasks to ready to open
  the milestone. This closes v0.2 through the phase gate.

## Milestone v0.3 — The Self-Tuning Loop

Orient: `.kelix/roadmap.md` Milestone v0.3 → phases T-METRICS … T-SKILLS
(waterfall). Owner decisions: `.kelix/phases/T-*/CONTEXT.md`. Ship gate: one
full self-tuning cycle (ST19); skill tasks are in-milestone but not the gate.
All tasks below are `status: proposed` until the owner promotes them.

### Phase T-METRICS — the outcome ledger

- [x] ST1: loop-metrics schema module | priority: 57 | status: done | by: owner | phase: T-METRICS | req: REQ-TM2, REQ-TM4
  details: add src/kelix/metrics.py with dataclasses LoopMetrics (schema_version,
  iterations[], fleet_summaries[], proposal_outcomes[]), IterationLedgerRow
  (run_id, iteration, task_id, verified, retry_count, duration_s, failure,
  circuit_breaker_cause, agent_id, fleet_id, backlog_lint dict, skills_injected
  list, tokens always null), FleetSummaryRow, ProposalOutcome. Document the
  optional token adapter hook in module docstring (callable signature, not
  wired). load_metrics(path)->LoopMetrics|empty and save_metrics(path, m)
  write indented JSON. tests/test_metrics.py: round-trip, corrupt file tolerance,
  tokens field null on rows.

- [x] ST2: per-iteration ledger row capture | priority: 56 | status: done | by: owner | deps: ST1 | phase: T-METRICS | req: REQ-TM1
  details: extend src/kelix/loop.py Runner to accumulate IterationLedgerRow per
  iteration: run_id, rec.index, task_id parsed from rationale (reuse
  TASK_FROM_RATIONALE_RE), rec.verified, rec.duration_s, rec.failure,
  circuit_breaker_cause when result.status becomes circuit_breaker, agent_id
  from self.agent_id, fleet_id from optional constructor arg (empty for solo).
  retry_count = count of prior rows in this run with the same task_id. Hold rows
  on RunResult or Runner until retrospective. tests/test_loop.py: mock run with
  two attempts on same task id → second row retry_count==1.

- [x] ST3: backlog lint on kelix proposed edits | priority: 55 | status: done | by: owner | deps: ST1, PC15 | phase: T-METRICS | req: REQ-TM5
  details: after each iteration, if .kelix/backlog.md is dirty vs pre-iteration
  snapshot: parse backlog, filter tasks with by=kelix and status=proposed that
  were added or whose details/rationale/deps changed, run lint_backlog on that
  subset only. Attach {rule_id: count} to the current iteration's ledger row as
  backlog_lint (aggregate Finding.rule counts). tests/test_metrics.py or
  test_loop.py: fixture agent appends a slop kelix proposed task → row carries
  missing-details rule count ≥1.

- [x] ST4: metrics rollup at retrospective | priority: 54 | status: done | by: owner | deps: ST2, ST3 | phase: T-METRICS | req: REQ-TM2, REQ-TM3
  details: add append_run_metrics(cfg, rows, fleet_summary=None) in metrics.py;
  call from loop.py _finish immediately after write_retrospective merges this
  run's rows into .kelix/memory/loop-metrics.json (create if absent). Add
  .kelix/memory/loop-metrics.json to RUNNER_BOOKKEEPING in gitutil.py. Do not
  modify episodes.jsonl write path. tests/test_loop.py: mock run → file exists
  with one iteration object matching the run; second run appends without
  clobbering.

- [x] ST5: fleet metrics aggregation | priority: 53 | status: done | by: owner | deps: ST4 | phase: T-METRICS | req: REQ-TM6
  details: in src/kelix/fleet.py pass fleet_id into Runner (e.g. fleet.toml
  name or hash) and agent_id per agent. After fleet run completes, compute
  FleetSummaryRow (fleet_id, run_ids[], verified_rate, iteration_count,
  breaker_trips) and append via append_run_metrics. tests/test_fleet.py: two-
  agent mock fleet → ledger rows have distinct agent_id, same fleet_id, plus
  one fleet_summaries[] entry.

- [x] ST6: loop-metrics documentation | priority: 52 | status: done | by: owner | deps: ST5 | phase: T-METRICS | req: REQ-TM2, REQ-TM4
  details: add "Outcome ledger" section to docs/memory-and-skills.md documenting
  loop-metrics.json schema, episodes.jsonl vs rollup distinction, backlog_lint
  field, tokens:null hook, fleet_summaries and proposal_outcomes arrays.
  Acceptance: section names both files; pytest -q unchanged.

### Phase T-DIAGNOSE — periodic self-review

- [x] ST7: diagnose config keys | priority: 51 | status: done | by: owner | deps: ST4 | phase: T-DIAGNOSE | req: REQ-TD2
  details: extend LoopConfig in config.py with diagnose_transcript_chars: int =
  50000 and diagnose_default_runs: int = 3; parse from [loop] in kelix.toml;
  document in CONFIG_TEMPLATE comment. tests/test_config.py: defaults and
  override round-trip.

- [x] ST8: kelix diagnose command skeleton | priority: 50 | status: done | by: owner | deps: ST7 | phase: T-DIAGNOSE | req: REQ-TD1
  details: add src/kelix/diagnose.py and cmd_diagnose in cli.py. Flags: --run-id
  (repeatable), --last N, --diagnosis-file optional path default
  .kelix/memory/diagnosis-<timestamp>.md. Select runs: --run-id list, else last
  N runs from .kelix/runs/ that have ≥1 failed ledger row (load loop-metrics.json
  joined to run ids), default N=diagnose_default_runs. Never import from loop.py
  run path. tests/test_diagnose.py: run selection fixture with 5 runs, 2 failed.

- [x] ST9: failed-transcript loader with budget | priority: 49 | status: done | by: owner | deps: ST8 | phase: T-DIAGNOSE | req: REQ-TD2
  details: in diagnose.py load_failed_transcripts(cfg, run_ids, ledger_rows) →
  str: for each failed iteration in scope read
  .kelix/runs/<run_id>/transcript-<n>.txt (or actual transcript naming from
  loop.py); concatenate with headers; stop when diagnose_transcript_chars
  exceeded, append "[... truncated to N chars]" marker. Skip missing files
  gracefully. tests/test_diagnose.py: 3 transcripts, budget 500 → truncation
  marker present.

- [x] ST10: diagnose agent iteration | priority: 48 | status: done | by: owner | deps: ST9 | phase: T-DIAGNOSE | req: REQ-TD1, REQ-TD3
  details: add DIAGNOSE_TEMPLATE in prompt.py; cmd_diagnose runs one adapter
  iteration (worktree isolation like plan) with ledger JSON excerpt + ST9
  transcripts; agent writes only the diagnosis markdown file; validate output
  exists and contains "## Findings" and at least one run_id citation. Print
  path on success. tests/test_diagnose.py: mock adapter writes file → exit 0;
  assert loop.py has zero calls to cmd_diagnose (grep test or import guard).

### Phase T-PROPOSE — reviewable tuning PRs

- [x] ST11: propose path allowlist guard | priority: 47 | status: done | by: owner | deps: ST4 | phase: T-PROPOSE | req: REQ-TP1
  details: add src/kelix/propose.py with PROPOSE_ALLOWED_PREFIXES tuple:
  .kelix/prompts/, src/kelix/security.py (denylist constants only — document
  which lines), src/kelix/config.py (defaults + CONFIG_TEMPLATE string),
  .kelix/kelix.toml template keys for [memory] and [loop] only. validate_propose_diff(
  changed_paths)->list[str] returns violations for any path outside allowlist or
  blocked paths (backlog, STATE, roadmap). tests/test_propose.py: allowed vs
  forbidden paths.

- [x] ST12: kelix propose command | priority: 46 | status: done | by: owner | deps: ST11, ST10 | phase: T-PROPOSE | req: REQ-TP1
  details: cmd_propose in cli.py: create branch kelix/propose-<run_id>, one
  adapter iteration with PROPOSE_TEMPLATE in prompt.py (inputs: loop-metrics
  excerpt, optional --diagnosis-file, predicted improvement line required in
  output metadata). Post-iteration run validate_propose_diff on git diff;
  reject with stderr listing violations. Write .kelix/memory/proposal-<id>.json
  sidecar (prediction text, touched files). tests/test_propose.py: mock agent
  edits prompt file → pass; mock edits backlog → fail validation.

- [x] ST13: propose opens PR via pr.py | priority: 45 | status: done | by: owner | deps: ST12, KB6 | phase: T-PROPOSE | req: REQ-TP2
  details: after successful propose iteration, call open_pr from pr.py (or extend
  build_pr_body with propose mode) to open a PR with body sections: ## Metric
  evidence (verbatim stats from loop-metrics.json), ## Diagnosis (link/path),
  ## Predicted improvement, ## Changed policy surface (file list). Add --no-pr
  flag for tests. tests/test_propose.py: mock gh path or stub open_pr → called
  with structured body containing "Metric evidence". Note in commit message:
  live receipt for KV1 pr.py re-judgment.

- [x] ST14: proposal outcome grading | priority: 44 | status: done | by: owner | deps: ST13 | phase: T-PROPOSE | req: REQ-TP3
  details: add record_proposal_outcome(metrics, *, merge_sha|close_reason,
  prediction, merged_at_run_window) and grade_proposal(metrics, proposal_id) in
  metrics.py: slice ledger rows into 5 runs before merge vs 5 after; compare
  verified rate and mean retry_count + breaker rate; emit
  improved|regressed|inconclusive (<3 post-merge runs). CLI kelix propose
  --record-merge <sha> or kelix metrics grade-proposal (subcommand) for owner
  use. tests/test_metrics.py: fixture metrics → improved and inconclusive cases.

### Phase T-SKILLS — skill distillation

- [x] ST15: exclude _proposed from skills digest | priority: 43 | status: done | by: owner | deps: ST4 | phase: T-SKILLS | req: REQ-TS2
  details: in memory.py list_skills skip any path under .kelix/skills/_proposed/.
  Promotion = owner moves folder to .kelix/skills/<name>/ (document in
  memory-and-skills.md one line). tests/test_memory.py: skill only under
  _proposed → skills_digest empty; after move → appears.

- [x] ST16: distillation pass after retrospective | priority: 42 | status: done | by: owner | deps: ST15 | phase: T-SKILLS | req: REQ-TS1
  details: add DISTILLATION_TEMPLATE in prompt.py; after write_retrospective in
  loop.py _finish (and fleet equivalent), when [memory].distill_skills=true
  (default true), invoke adapter once with prompt built from this run's
  transcripts + episode outcomes (verified, failures, retries). Agent may write
  1–3 dirs under .kelix/skills/_proposed/<name>/SKILL.md only; validate
  agentskills.io frontmatter. Cap at 3 candidates; ignore extras with warning.
  tests/test_loop.py: mock distillation script writes one SKILL.md → file exists.

- [x] ST17: skills_injected on ledger rows | priority: 41 | status: done | by: owner | deps: ST16, ST2 | phase: T-SKILLS | req: REQ-TS3
  details: when writing context-<n>.json in loop.py, copy skills-slot manifest
  entries' source paths into IterationLedgerRow.skills_injected (basename skill
  name). Persist through ST4 rollup. tests/test_loop.py: manifest lists
  .kelix/skills/foo/SKILL.md → row skills_injected contains "foo".

- [x] ST18: skill efficacy rollup | priority: 40 | status: done | by: owner | deps: ST17 | phase: T-SKILLS | req: REQ-TS4
  details: extend LoopMetrics with skill_efficacy: dict[str, {with_rate,
  without_rate, matched_tasks}] computed in append_run_metrics from all
  iteration rows: for each skill name, partition rows by whether skill in
  skills_injected; compute verified_rate for each partition (only rows with
  task_id present). Update on each retrospective append. tests/test_metrics.py:
  fixture rows → with_rate > without_rate for injected skill.

- [x] ST19a: self-tuning proof — seed loop-metrics | priority: 44 | status: done | by: owner | deps: ST14 | phase: T-PROPOSE | req: REQ-TP2
  rationale: [ST19] ship gate step 1 — ledger rows from a real run
  details: run `PYTHONPATH=src python -m kelix run --max-iterations 3` on this
  repo (mock adapter per `.kelix/kelix.toml`); assert
  `.kelix/memory/loop-metrics.json` exists with ≥3 `iterations[]` rows whose
  `run_id` matches the run; append the run id under a new
  `## D22 execution evidence (pending)` section in DECISIONS.md. Acceptance:
  `pytest -q` and `ruff check src tests` pass unchanged.

- [x] ST19b: self-tuning proof — diagnose on seed run | priority: 43 | status: done | by: owner | deps: ST19a | phase: T-PROPOSE | req: REQ-TP2
  rationale: [ST19] ship gate step 2 — diagnosis file from ledger + transcripts
  details: run `kelix diagnose --run-id <ST19a run_id>` (or `--last 1` if no
  failed rows); assert a `.kelix/memory/diagnosis-*.md` file exists containing
  `## Findings` and a citation of the ST19a run id; record the diagnosis path
  in DECISIONS.md pending section. Acceptance: `pytest -q` pass.

- [x] ST19c: self-tuning proof — propose tuning PR | priority: 42 | status: done | by: owner | deps: ST19b | phase: T-PROPOSE | req: REQ-TP2
  rationale: [ST19] ship gate step 3 — policy edit on allowlisted paths only
  details: run `kelix propose --no-pr --diagnosis-file <ST19b path>`; assert
  `validate_propose_diff` passes (no backlog/STATE edits), a
  `.kelix/memory/proposal-*.json` sidecar is written, and stderr/stdout names
  the proposal id; record proposal id and touched files in DECISIONS.md pending
  section. Acceptance: `pytest -q` pass.

- [x] ST19d: self-tuning proof — record proposal outcome | priority: 41 | status: done | by: owner | deps: ST19c | phase: T-PROPOSE | req: REQ-TP3
  rationale: [ST19] ship gate step 4 — owner merge/close captured in metrics
  details: record the ST19c proposal via `kelix propose --record-merge <sha>` or
  `--record-close <reason>` (use the propose branch HEAD sha or a documented
  close reason); assert `loop-metrics.json` `proposal_outcomes[]` has an entry
  for the proposal id with prediction text preserved. Record merge sha or close
  reason in DECISIONS.md pending section. Acceptance: `tests/test_metrics.py
  -q` pass.

- [x] ST19e: self-tuning proof — post-merge metrics runs | priority: 40 | status: done | by: owner | deps: ST19d | phase: T-PROPOSE | req: REQ-TP3
  rationale: [ST19] ship gate step 5 — ledger rows after policy change
  details: run `kelix run --max-iterations 3` on the post-merge tree; assert
  ≥3 new iteration rows land in `loop-metrics.json` with run ids distinct from
  ST19a; run `kelix metrics grade-proposal <ST19c id>` and assert outcome is
  `improved`, `regressed`, or `inconclusive` (not missing); record grade +
  run ids in DECISIONS.md pending section. If fewer than 3 post-merge runs exist,
  document `inconclusive` explicitly — do not mark done without grade output.
  Acceptance: `pytest -q` pass.

- [x] ST19: v0.3 self-tuning cycle proof | priority: 39 | status: done | by: owner | deps: ST19e | phase: T-PROPOSE | req: REQ-TP2, REQ-TP3
  rationale: [T-PROPOSE] close the v0.3 ship gate — consolidate D22 execution evidence
  details: merge the pending `## D22 execution evidence` section in DECISIONS.md
  into a single D22 proof entry (run ids, diagnosis path, proposal id, merge/close,
  grade outcome, post-merge run ids) citing REQ-TP2 and REQ-TP3; remove the
  pending header. Assert `loop-metrics.json` has iterations from ST19a and ST19e
  plus a graded `proposal_outcomes[]` entry. Acceptance: `kelix lint` exit 0;
  `pytest -q` pass.

- [x] ST20: skill distillation documentation | priority: 38 | status: done | by: owner | deps: ST18 | phase: T-SKILLS | req: REQ-TS1, REQ-TS2, REQ-TS4
  details: extend docs/memory-and-skills.md with "Skill distillation" section:
  runner-owned pass after retrospective, _proposed/ promotion flow, efficacy
  fields in loop-metrics.json. Link from docs/planning.md quick reference table
  (kelix diagnose, kelix propose as secondary ops). Acceptance: pytest -q pass.

## Milestone v0.4 — Kelix for everyone

Orient: `.kelix/roadmap.md` Milestone v0.4 → phases P-REPOS … P-GOLD.
All tasks below are `status: proposed` until the owner promotes them.

### Phase P-REPOS — Reposition

- [x] KE1: README agent-agnostic lead | priority: 92 | status: done | by: kelix | phase: P-REPOS | req: REQ-R1
  details: rewrite README.md lines 1–20 (through the first substantive body
  paragraph): lead with "the loop that climbs" and agent-agnostic framing
  (Claude Code, Codex CLI, Cursor, Gemini CLI, Kiro as deepest integration).
  Kiro section below line 20 stays prominent. Acceptance: `rg -i kiro README.md |
  head -1` line number is > 20; `pytest -q` and `ruff check src tests` pass
  unchanged.

- [x] KE2: docs/index.md reposition | priority: 91 | status: done | by: kelix | phase: P-REPOS | req: REQ-R2
  details: replace docs/index.md hero (currently "Ralph loop rebuilt for Kiro")
  with agent-agnostic framing matching KE1; add Agents section linking
  docs/kiro.md (deepest integration) and future docs/agents/*.md placeholders
  or "coming" links until KE8 lands. Kiro guide bullet unchanged in depth.
  Acceptance: first H1-adjacent paragraph names ≥3 non-Kiro agents; docs/kiro.md
  link present.

- [x] KE3: pyproject + package metadata | priority: 90 | status: done | by: owner | phase: P-REPOS | req: REQ-R2
  details: update pyproject.toml `[project].description` and `keywords` to
  agent-agnostic voice (loop for any coding agent; Kiro as flagship integration
  in description, not sole identity). Keep version unchanged. Acceptance:
  `rg -i 'rebuilt for kiro' pyproject.toml` returns no matches; `pip install -e .`
  metadata check via `python -c "import importlib.metadata as m; print(m.metadata('kelix')['Description'])"`.

- [x] KE4: CLI help + config template voice | priority: 89 | status: done | by: owner | phase: P-REPOS | req: REQ-R2
  details: in src/kelix/cli.py update CONFIG_TEMPLATE adapter comment to list
  named presets (kiro | claude | codex | cursor | gemini | cmd | mock) and
  refresh argparse help strings / module docstrings that lead with Kiro-only
  framing. Acceptance: `kelix --help` first paragraph mentions multiple agents;
  CONFIG_TEMPLATE comment lists presets (may precede KE5 implementation — comment
  documents intent).

- [x] KE5: MCP server description reposition | priority: 88 | status: done | by: owner | phase: P-REPOS | req: REQ-R2
  details: rewrite src/kelix/mcp_server.py module docstring and any tool
  descriptions that say "Kiro first" to "MCP-capable agents; Kiro is the
  reference integration" without removing Kiro registration example. Acceptance:
  module docstring names agent-agnostic use; `pytest tests/test_mcp_server.py -q`
  passes unchanged.

- [x] KE6: P-REPOS acceptance gate | priority: 87 | status: done | by: owner | deps: KE1,KE2,KE3,KE4,KE5 | phase: P-REPOS | req: REQ-R3
  details: add tests/test_reposition.py (or extend test_claims.py): assert
  `rg -i kiro README.md | head -1` line > 20; run full `pytest -q`; run
  docs/kiro.md example TOML blocks through load_config (smoke); no edits to
  docs/kiro.md body. Documents REQ-R3 closure in task commit message.

### Phase P-AGENT — Named adapters + guides

- [x] KE7: named adapter presets in config | priority: 86 | status: done | by: owner | phase: P-AGENT | req: REQ-A1
  details: in src/kelix/config.py and adapters.py extend make_adapter/load validation
  so adapter names claude|codex|cursor|gemini resolve internally to CmdAdapter
  with preset command templates (stdlib only, no new subprocess machinery).
  Presets documented in code comments with upstream doc URLs. kiro|cmd|mock
  unchanged. Acceptance: load_config accepts each preset name; unknown name
  still raises ConfigError; tests/test_config.py covers all four.

- [x] KE8: cursor agent guide (Kelix-verified) | priority: 85 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A2
  details: create docs/agents/cursor.md with headings aligned to docs/kiro.md
  loop sections (# The headless adapter, ## Configure kelix.toml, install, auth,
  worked example init→plan→run, quirks, troubleshooting). Command template matches
  dogfood proof (`cursor-agent` or actual verified invocation from
  docs/proof/final-report.md). Banner: **Kelix-verified** invocation. Acceptance:
  TOML block in guide parses via load_config; heading list matches kiro.md
  loop sections (diff script or manual checklist in test).

- [x] KE9: claude agent guide (upstream-sourced) | priority: 84 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A2
  details: create docs/agents/claude.md — same heading parity as KE8; invocation
  from Claude Code CLI upstream docs; prominent **Not Kelix CI-tested — community
  corrections welcome** banner. Acceptance: TOML parses via load_config.

- [x] KE10: codex agent guide (upstream-sourced) | priority: 83 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A2
  details: create docs/agents/codex.md — same structure as KE9 for OpenAI Codex
  CLI; upstream-sourced banner. Acceptance: TOML parses via load_config.

- [x] KE11: gemini agent guide (upstream-sourced) | priority: 82 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A2
  details: create docs/agents/gemini.md — same structure as KE9 for Gemini CLI;
  upstream-sourced banner. Acceptance: TOML parses via load_config.

- [x] KE12: init --agent wiring | priority: 81 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A3
  details: extend cmd_init: add `--agent <name>` argparse flag; when TTY and no
  flag, print numbered list (kiro, claude, codex, cursor, gemini, cmd, mock)
  and read choice; when non-TTY and no flag, exit 2 with error requiring
  --agent. Write selected adapter (and preset command if cmd) into kelix.toml
  CONFIG_TEMPLATE output. Tests: monkeypatch isatty for both paths in
  tests/test_config.py or new test_init_agent.py.

- [x] KE13: claude preset integration test | priority: 80 | status: done | by: owner | deps: KE7 | phase: P-AGENT | req: REQ-A4
  details: tests/test_adapters.py: repo with adapter=claude and a stub script
  on PATH (via cmd override or sh -c) completes one mock-style iteration via
  kelix run --max-iterations 1 (mock backlog + verify echo). Proves preset
  resolves and subprocess runs. Acceptance: test passes in CI without real CLI.

- [x] KE14: agent guide TOML CI check | priority: 79 | status: done | by: owner | deps: KE8,KE9,KE10,KE11 | phase: P-AGENT | req: REQ-A4
  details: add tests/test_agent_guides.py: extract fenced `[agent]` TOML from
  docs/agents/*.md and docs/kiro.md; each must parse via load_config into a
  temp dir without ConfigError. Wire into CI (pytest). Acceptance: test covers
  all five guide files.

- [x] KE15: index agents section links | priority: 78 | status: done | by: owner | deps: KE8,KE9,KE10,KE11 | phase: P-AGENT | req: REQ-A2
  details: update docs/index.md Guides section with docs/agents/{cursor,claude,
  codex,gemini}.md links; kiro.md remains "deepest integration." Acceptance:
  all four agent guide paths linked from index.

### Phase P-AUDIT — Audacity audit

- [x] KE16: proof docs Kalph rename | priority: 77 | status: done | by: owner | phase: P-AUDIT | req: REQ-U1
  details: rename Kalph→Kelix throughout docs/proof/* (final-report.md,
  dogfood-retrospective.md, fleet-*.md, injection-drill-backlog.diff prose).
  Add one-line provenance at top of docs/proof/final-report.md: notes former
  Kalph name during early dogfood runs. Acceptance: `rg -i kalph docs/proof`
  returns zero matches except the provenance line; pytest -q passes.

- [x] KE17: concept.md audacity intro | priority: 76 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: rewrite docs/concept.md opening: one audacity sentence (what one
  person can do overnight they couldn't before), then evidence link to
  docs/proof/final-report.md dogfood 12/12 stat. Remove plumbing-first lead.
  Acceptance: first paragraph contains capability claim; second paragraph or
  bullet links proof artifact.

- [x] KE18: memory-and-skills audacity intro | priority: 75 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/memory-and-skills.md; proof link to dogfood
  retrospective or tests/test_memory.py reproducible command in doc.

- [x] KE19: prioritization audacity intro | priority: 74 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/prioritization.md; proof link to backlog
  selection tests or proof run evidence.

- [x] KE20: planning doc audacity intro | priority: 73 | status: done | by: owner | deps: KE16,PC12 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/planning.md (requires PC12 shipped); proof
  link to kelix plan/lint tests. If PC12 not done when task runs, seed minimal
  planning.md stub is out of scope — task blocked until PC12 done.

- [x] KE21: fleet audacity intro | priority: 72 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/fleet.md; proof link to docs/proof/fleet-session1-retrospective.md.

- [x] KE22: SECURITY audacity intro | priority: 71 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/SECURITY.md; proof link to
  tests/test_injection_drill.py or docs/proof/injection-drill-backlog.diff.

- [x] KE23: mcp audacity intro | priority: 70 | status: done | by: owner | deps: KE16 | phase: P-AUDIT | req: REQ-U2
  details: same pattern for docs/mcp.md; proof link to tests/test_mcp_server.py.

- [x] KE24: writing-for-the-loop tagline | priority: 69 | status: done | by: owner | phase: P-AUDIT | req: REQ-U2
  details: update docs/writing-for-the-loop.md: adopt "Gold in, diamonds out"
  as the one-line principle in the opening; demote good/slop pairing to body
  examples only. Acceptance: first mention of gold/diamonds is the canon line.

- [x] KE25: CLI art.say theming | priority: 68 | status: done | by: owner | deps: KE17,KE18,KE19,KE21,KE22,KE23,KE24 | phase: P-AUDIT | req: REQ-U3
  details: retire flat print strings in src/kelix/cli.py (run complete, init,
  status summaries) in favor of art.say() with themes; run-complete message
  lists verify commands run and verified-done count, not bare "done." Tests in
  tests/test_ci_integration.py or cli capture updated substrings.

- [x] KE26: README/index audacity pass | priority: 67 | status: done | by: owner | deps: KE25,KE1,KE2 | phase: P-AUDIT | req: REQ-U4
  details: final voice pass on README.md and docs/index.md: audacity + evidence
  links after structural reposition (KE1/KE2). Each opens with capability claim
  + proof link. Acceptance: reviewer can trace opening claim to docs/proof or
  test command cited inline.

### Phase P-COMPARE — Honest comparison

- [x] KE27: docs/compare.md draft | priority: 66 | status: done | by: owner | deps: KE16 | phase: P-COMPARE | req: REQ-CM1
  details: create docs/compare.md comparing Kelix vs plain Ralph vs Claude Code
  alone vs Codex alone vs GSD-style orchestrators. Axes: state persistence,
  verified-done rate, unattended runtime, token cost per verified task,
  injection-drill results, fleet collision rate — cite docs/proof numbers where
  they exist; else "not measured — no receipt." Include ≥2 Kelix-loses rows:
  single-iteration latency, IDE pairing affordances, adapter hang/timeout (D13).
  Acceptance: zero cells with bare numbers lacking source link or command.

- [x] KE28: compare.md site links | priority: 65 | status: done | by: owner | deps: KE27 | phase: P-COMPARE | req: REQ-CM2
  details: link docs/compare.md from README.md (Why Kelix or new section) and
  docs/index.md Reference. Acceptance: `rg compare.md README.md docs/index.md`
  finds both links.

### Phase P-GOLD — First-contact spec gate

- [x] KE29: run spec-gate for ready tasks | priority: 64 | status: done | by: owner | phase: P-GOLD | req: REQ-GD1
  details: in src/kelix/loop.py Runner.run() before iteration 1: lint only
  tasks with status=ready via lint_backlog; on findings print actionable
  messages with inline good/bad task example (from lint.py or dedicated formatter);
  exit non-zero. Well-specified fixture backlog proceeds. Tests in
  tests/test_loop.py: vague ready task → exit 1 before adapter called; good
  task → proceeds.

- [x] KE30: run --force bypass | priority: 63 | status: done | by: owner | deps: KE29 | phase: P-GOLD | req: REQ-GD1
  details: add `--force` to kelix run argparse; skips spec gate only (document in
  --help and docs/quickstart.md); git safety unchanged. Test: vague backlog +
  --force reaches adapter. Acceptance: help text states spec-gate scope explicitly.

- [x] KE31: plan interview acceptance questions | priority: 62 | status: done | by: owner | phase: P-GOLD | req: REQ-GD2
  details: extend PLANNING_TEMPLATE / plan.py interview rubric so each emitted
  question block includes at least one acceptance-criteria probe per roadmap
  phase in the draft goal (reuse lint rules from docs/writing-for-the-loop.md).
  Test: mock adapter planning fixture goal with two phases → interview output
  contains ≥2 acceptance-themed questions.

- [x] KE32: GOAL template + lint tagline | priority: 61 | status: done | by: owner | deps: KE24 | phase: P-GOLD | req: REQ-GD3
  details: update GOAL_TEMPLATE in cli.py to include one-line "Gold in, diamonds
  out." principle; update run spec-gate and kelix lint stderr banner to use
  canon tagline once (retire slop pairing from gate message). Test: init creates
  GOAL.md containing the tagline; lint failure message contains it exactly once.

## Milestone V — The value cut

Orient: `.kelix/roadmap.md` Milestone V → phases V-LEDGER … V-PROOF. Sequencing:
complete v0.2 (PC7–PC23), v0.3 (via PC23), v0.4 (KE1–KE32), then promote these.
Owner decisions: `.kelix/phases/V-CUT/CONTEXT.md`. All tasks below are
`status: proposed` until the owner promotes them.

### Phase V-LEDGER — The value ledger

- [x] KV1: write docs/value-ledger.md | priority: 55 | status: done | by: owner | deps: KE32 | phase: V-LEDGER | req: REQ-VL1, REQ-VL2, REQ-VL3
  details: create docs/value-ledger.md with one markdown table row per module
  listed in REQ-VL1 (loop, verify, plan+interview, lint, state/roadmap/backlog,
  memory, skills, fleet, claims, mcp_server, sync/, pr, kiro, security,
  adapters, art). Columns: module, lines of code (from `wc -l` on cited paths),
  receipt (path to proof artifact / test / run log, or literal "none"), verdict
  (SHARPEN|KEEP|SCRAP). Apply the decision rule from REQ-VL2. Known receipts
  from proof runs: verify gate (tests/test_verify.py + dogfood 12/12),
  plan interview REQ collisions (DECISIONS.md D19), lint slop rejection
  (tests/test_lint.py), circuit breaker no-diff burn (tests/test_loop.py),
  worktree isolation after killed agent (DECISIONS.md D13), fleet zero collisions
  (docs/proof/fleet-session1-retrospective.md). Owner SCRAPs sync/ and pr per
  V-CUT CONTEXT must be SCRAP with deletion tasks KV2/KV3 named in the SCRAP
  column. Add a "## Owner veto" section explaining edits to this file block
  execution. Acceptance: every row has receipt or "none"; every SCRAP row names
  a backlog task id; `pytest -q` passes (doc-only change).

### Phase V-SHARPEN — Double down (execution after ledger + scrap)

- [x] KV2: delete sync/ module and kelix sync | priority: 54 | status: done | by: owner | deps: KV1 | phase: V-LEDGER | req: REQ-VL3
  details: per owner decision and ledger SCRAP row for sync/: delete
  src/kelix/sync/ (all files), remove cmd_sync and sync subparser from
  src/kelix/cli.py, remove sync imports/tests (tests/test_sync*.py if present),
  strip sync references from docs (index.md, quickstart.md, README.md,
  CONTRIBUTING.md, .kelix/memory/project.md). No deprecation shim. Acceptance:
  `rg -i 'kelix sync|from kelix.sync|kelix/sync' src tests docs` returns zero
  matches; `pytest -q` and `ruff check src tests` pass.

- [x] KV3: delete pr.py and --pr flag | priority: 53 | status: done | by: owner | deps: KV1 | phase: V-LEDGER | req: REQ-VL3
  details: per owner decision and ledger SCRAP row for pr: delete
  src/kelix/pr.py and tests/test_pr.py; remove --pr from kelix run argparse
  and any pr.open_pr calls in loop.py/cli.py; strip --pr from docs (README,
  quickstart, kiro.md, index.md, integrations/kiro/*, SECURITY.md pr section
  stays as historical threat model note only if still relevant — else trim).
  Value demo path ends at verified commits on run branch. Acceptance:
  `rg -- '--pr|from kelix.pr|kelix/pr' src tests docs integrations` returns
  zero matches except docs/value-ledger.md historical note if any; pytest -q pass.

- [ ] KV4: execute mcp_server SCRAP if ledger says SCRAP | priority: 52 | status: ready | by: owner | deps: KV1 | phase: V-LEDGER | req: REQ-VL3
  details: read docs/value-ledger.md mcp_server row. If verdict is SCRAP:
  delete src/kelix/mcp_server.py, tests/test_mcp_server.py, kelix mcp
  subcommand, docs/mcp.md, MCP references in cli help and integrations/kiro.
  If verdict is KEEP or SHARPEN: close this task in commit message as no-op
  with ledger citation — do not delete. Acceptance: if SCRAP, `rg mcp_server
  src tests` zero matches and pytest -q pass; if not SCRAP, only value-ledger.md
  or task commit notes change.

- [ ] KV5: execute skills SCRAP if ledger says SCRAP | priority: 51 | status: ready | by: owner | deps: KV1 | phase: V-LEDGER | req: REQ-VL3
  details: read docs/value-ledger.md skills row. If SCRAP: remove skill
  acquisition/distillation plumbing that never demonstrated learning (D17
  evidence: zero skills in ~20 v0.1 iterations) while preserving frozen
  injection of existing .kelix/skills/*.md if KEEP semantics require it —
  follow ledger row text. Update memory-and-skills.md, prompt.py skills slot,
  tests. If KEEP/SHARPEN: no-op with ledger citation. Acceptance: pytest -q
  pass; behavior matches ledger verdict documented in commit message.

- [ ] KV6: receipt-style run-complete message | priority: 50 | status: ready | by: owner | deps: KV2, KV3 | phase: V-SHARPEN | req: REQ-VS1
  details: in src/kelix/loop.py and cli.py run completion path, replace bare
  "done" output with a receipt block listing each [verify] command, its exit
  status, and SHAs of commits verified this run (or "none" if capped early).
  Use art.say theming. Test in tests/test_loop.py or tests/test_ci_integration.py:
  mock run with verify echo succeeds → stdout contains command name, exit 0,
  and at least one commit hash substring.

- [ ] KV7: plan interview cap seven MC questions | priority: 49 | status: ready | by: owner | deps: KV1 | phase: V-SHARPEN | req: REQ-VS2
  details: in src/kelix/plan.py and PLANNING_TEMPLATE, enforce interview
  output ≤ 7 questions; reject/retry planning output with >7. Each question
  must be multiple-choice (2–4 options + recommendation) — no open-ended essay
  prompts. Answers append to `.kelix/phases/<id>/CONTEXT.md`. Test: mock adapter
  fixture emitting 8 questions → validation failure or truncation to 7; fixture
  with 5 MC questions → accepted; CONTEXT.md receives answers on resume path.

- [ ] KV8: circuit breaker actionable message | priority: 48 | status: ready | by: owner | deps: KV6 | phase: V-SHARPEN | req: REQ-VS3
  details: when circuit_breaker_threshold trips in loop.py, stderr/stdout must
  state: breaker cause (e.g. consecutive no-diff), active task id, and one-line
  fix ("edit backlog task X details:" or "check worktree for uncommitted changes
  in path Y"). Test: fixture triggering no-diff breaker → output contains task
  id and the string "fix" or actionable path; run stops before next iteration.

- [ ] KV9: lint and spec-gate actionable findings | priority: 47 | status: ready | by: owner | deps: KV6 | phase: V-SHARPEN | req: REQ-VS4
  details: extend src/kelix/lint.py formatters and run spec-gate (KE29 if
  shipped, else loop preflight lint) so each Finding prints: task id, rule id,
  message, and fix line ("add details: with a test path" / "remove unfalsifiable
  word X in details"). Test: lint_backlog on slop fixture → stderr includes
  task id + rule + fix for every finding; kelix lint exit 1.

- [ ] KV10: fleet receipt messaging | priority: 46 | status: ready | by: owner | deps: KV6 | phase: V-SHARPEN | req: REQ-VS5
  details: fleet run end and retrospective (src/kelix/fleet.py) echo REQ-VS1
  receipt style per agent: verify commands + exit statuses + verified commit
  SHAs + claim outcomes. Update docs/fleet.md opening with receipt example
  citing docs/proof/fleet-session1-retrospective.md. Test: fleet mock run
  completion output contains verify command name and exit status.

### Phase V-SIMPLE — Cut the surface

- [ ] KV11: CLI audit against ledger | priority: 45 | status: ready | by: owner | deps: KV2, KV3, KV4 | phase: V-SIMPLE | req: REQ-VM1
  details: audit src/kelix/cli.py subcommands against docs/value-ledger.md;
  remove any command whose module was SCRAP (sync, mcp if KV4 scrapped). Ensure
  init/plan/run are the documented happy path; lint, status, stop remain with
  --help text marking them secondary. Update docs/quickstart.md secondary-ops
  section. Test: `kelix --help` lists init, plan, run; scrapped subcommands
  absent; pytest -q pass.

- [ ] KV12: trim kelix.toml template to one screen | priority: 44 | status: ready | by: owner | deps: KV11 | phase: V-SIMPLE | req: REQ-VM2
  details: CONFIG_TEMPLATE in cli.py ≤ 25 lines including comments. Remove or
  default keys unused in docs/proof runs, test fixtures, and samples/value-demo/.
  Keys removed from template must still parse via config.py defaults. Test:
  count template lines ≤ 25; init on bare repo writes template; load_config
  round-trip on template succeeds.

- [ ] KV13: docs index intent routing | priority: 43 | status: ready | by: owner | deps: KV4, KV5 | phase: V-SIMPLE | req: REQ-VM3
  details: rewrite docs/index.md top section to route by intent ("I want to ship
  X unattended") with ≤ 5 links (quickstart, planning or writing-for-the-loop,
  concept, SECURITY, compare or proof). Delete or merge doc pages for SCRAP
  features (e.g. mcp.md if KV4 scrapped). Footer note: every linked page maps
  to a SHARPEN or KEEP row in docs/value-ledger.md. Acceptance: index.md has
  ≤ 5 primary intent links above the fold; no link targets a SCRAP-only page.

- [ ] KV14: quickstart init-plan-run path | priority: 42 | status: ready | by: owner | deps: KV11, KV12 | phase: V-SIMPLE | req: REQ-VM4
  details: rewrite docs/quickstart.md so numbered steps are exactly: kelix init
  → write/point goal → kelix plan → promote tasks → kelix run → read verified
  commits on run branch. Document step count in the doc header (e.g. "6 steps
  to first verified commit"). No --pr, fleet, sync, or mcp in the happy path;
  secondary ops (lint, status, stop) in a separate "Operations" section. Test:
  doc review checklist in commit: grep quickstart for --pr/fleet/sync returns
  zero in happy-path section.

### Phase V-PROOF — Value demo release gate

- [ ] KV15: value-demo sample repo scaffold | priority: 41 | status: ready | by: owner | deps: KV14 | phase: V-PROOF | req: REQ-VP1
  details: create samples/value-demo/ — stdlib-only toy project (e.g. tiny
  calculator or todo module) with GOAL.md, .kelix/kelix.toml ([verify] =
  pytest -q), and a backlog of 3–5 owner-ready tasks sized for one iteration
  each. Include samples/value-demo/run-demo.sh that runs from clean tree:
  kelix init (no-op if present), kelix plan with bundled goal or skip if
  roadmap exists, owner promotes script note, kelix run --max-iterations 10.
  No fleet/pr/sync. Acceptance: directory exists; pytest -q passes inside sample;
  run-demo.sh is executable and documents promote step for human.

- [ ] KV16: capture value-demo transcript | priority: 40 | status: ready | by: owner | deps: KV15 | phase: V-PROOF | req: REQ-VP2
  details: execute samples/value-demo/run-demo.sh on a clean worktree; capture
  full transcript to docs/proof/value-demo.md including: goal text, interview
  Q&A (or QUESTIONS.md path), promote step, each iteration summary, verify
  command results, final verified commit SHAs, wall-clock time, iteration count.
  Embed reproduction commands at top of doc. Acceptance: another agent can
  reproduce by following only value-demo.md commands; doc links receipt paths.

- [ ] KV17: README value sentence and demo link | priority: 39 | status: ready | by: owner | deps: KV16 | phase: V-PROOF | req: REQ-VP3
  details: rewrite README.md first screen (before install details): lead with
  value sentence ("you write a well-specified goal, walk away, and come back to
  verified commits"), link to docs/proof/value-demo.md as the receipt, then
  minimal init/plan/run code block without --pr. Run full gate: pytest -q,
  ruff check src tests, kelix lint on this repo — all exit 0. Test: README first
  30 lines contain value sentence and value-demo.md link; CI commands pass.

- [ ] KV18: value-cut phase gate proof | priority: 38 | status: ready | by: owner | deps: KV17 | phase: V-PROOF | req: REQ-VP3
  details: update DECISIONS.md with value-cut closure evidence: value-demo run
  id, transcript path, ledger final verdict counts (N SHARPEN / KEEP / SCRAP).
  Run kelix lint on .kelix/backlog.md; validate_plan if roadmap changed. Record
  in commit message that Milestone V REQ-VP3 is covered. Acceptance: kelix lint
  exit 0; pytest -q pass; STATE.md can advance to Milestone V complete when
  owner marks KV1–KV17 done.
