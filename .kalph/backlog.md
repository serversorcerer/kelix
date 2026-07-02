# Kalph backlog (self-hosting: Kalph builds Kalph)

Task line format (one per task, keep it exactly parseable):
`- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kalph | deps: ID,ID`
Optional indented lines under a task: `rationale:`, `details:`, `diagnosis:`.
Higher priority number = more important. Owner tasks outrank kalph-proposed
tasks regardless of score. Only mark done after `pytest -q` and
`ruff check src tests` pass.

## Tasks

- [x] KB1: backlog parser module | priority: 90 | status: done | by: owner
- [x] KB2: memory module tests | priority: 80 | status: done | by: owner
- [x] KB3: security module tests | priority: 75 | status: done | by: owner
- [x] KB4: prioritization rubric doc | priority: 70 | status: done | by: owner

- [ ] KB5: autonomy-aware task selection | priority: 88 | status: ready | by: owner | deps: KB1
  rationale: proposed tasks must be selectable under autonomy high, and never outrank owner tasks otherwise
  details: extend src/kalph/backlog.py select_next(tasks, autonomy="normal") so that
  tasks with status "proposed" are treated as candidates only when autonomy="high"
  (still ranked below owner-authored ready tasks: sort key stays owner-first). A
  proposed task selected for work counts like ready. Under autonomy normal, proposed
  tasks are never selected. Update tests/test_backlog.py with cases for both levels.
  Keep backward compatibility: select_next(tasks) with one argument must still work.

- [ ] KB6: PR flow module | priority: 85 | status: ready | by: owner | deps: KB1
  rationale: overnight mode must end in reviewable PRs, never direct pushes to main
  details: create src/kalph/pr.py with open_pr(cfg, result, run_dir) -> str|None that
  (1) refuses (returns None, logs via the returned message being None) if result.branch
  is empty or is main/master; (2) pushes the run branch with
  `git push -u origin <branch>` (never --force, never main); (3) builds a PR body from
  the run: title "kalph: <first task rationale or run id>", body sections: Summary
  (task rationales from result.iterations), Verification evidence (verified flags per
  iteration and the verify commands from config), Backlog (task ids mentioned in
  rationales), and a footer "Opened by Kalph run <run_id>; review before merging.";
  (4) runs `gh pr create --title ... --body ... --base main --head <branch>` via
  subprocess and returns the PR URL from stdout, or None on any subprocess failure
  (log-and-skip, never raise out). Wire into cli.py: `kalph run --pr` calls open_pr
  after a run whose status is completed or max_iterations. Add tests/test_pr.py
  that monkeypatch subprocess.run to record invocations: assert refusal on main
  branch, assert push before gh, assert no --force anywhere, assert body contains
  verification evidence, assert None (not exception) when gh fails.

- [ ] KB7: fleet claim files | priority: 82 | status: ready | by: owner | deps: KB1
  rationale: two fleet agents must never work the same task; claims are the mechanism
  details: create src/kalph/claims.py managing .kalph/fleet/claims/<task-id>.json.
  Functions: claim_task(kalph_dir, task_id, agent_id, branch) -> bool using
  atomic O_CREAT|O_EXCL open so exactly one concurrent claimer wins; the file holds
  json {task, agent, branch, ts (epoch float), heartbeat (epoch float)};
  heartbeat(kalph_dir, task_id, agent_id) updates heartbeat if owned by agent_id;
  release_claim(kalph_dir, task_id, agent_id); is_claimed(kalph_dir, task_id,
  stale_after_s=900) -> bool treating claims with heartbeat older than stale_after_s
  as reclaimable (is_claimed returns False and claim_task may steal them by rewriting
  the file atomically via os.replace of a temp file); list_claims(kalph_dir) -> list.
  Add tests/test_claims.py: single winner among 8 threads claiming the same task
  concurrently (ThreadPoolExecutor), stale claim reclaim, release allows re-claim,
  wrong agent cannot release or heartbeat.
