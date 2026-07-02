"""Loop runner tests: sentinel, isolation, checkpoints, verification gate,
circuit breaker, kill switch. These are the regression suite for the loop
contract itself."""

import json
import subprocess

from conftest import write_mock_script

from kelix.config import load_config
from kelix.loop import Runner
from kelix.metrics import METRICS_FILE, load_metrics
from kelix.state import State, load_state, write_state


def _config(repo, extra="", mock_dir="mockdir", isolation="none", distill_skills=False):
    (repo / "kelix.toml").write_text(
        f"""
[agent]
adapter = "mock"
mock_dir = "{mock_dir}"

[memory]
distill_skills = {"true" if distill_skills else "false"}

[git]
isolation = "{isolation}"
{extra}
"""
    )
    return load_config(repo)


def _git_out(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    ).stdout


COMMIT_TASK = """\
echo "RATIONALE: T1 — highest priority ready task"
echo "work" >> work.txt
git add -A && git commit -q -m "T1: do work"
"""


def test_happy_path_completes_on_sentinel(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    result = Runner(cfg).run(log=lambda *_: None)
    # Iteration 1 does work, iteration 2 the mock emits the sentinel.
    assert result.status == "completed"
    assert len(result.iterations) == 2
    assert result.iterations[0].made_progress
    assert result.iterations[0].rationale.startswith("T1")
    assert result.iterations[1].sentinel


def test_transcripts_and_run_state_written(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    result = Runner(cfg).run(log=lambda *_: None)
    run_dir = cfg.kelix_dir / "runs" / result.run_id
    assert (run_dir / "iter-001.log").exists()
    assert (run_dir / "context-001.json").exists()
    context = json.loads((run_dir / "context-001.json").read_text())
    assert context["iteration"] == 1
    assert isinstance(context["items"], list)
    assert any(item["slot"] == "state" for item in context["items"])
    state = json.loads((run_dir / "run.json").read_text())
    assert state["status"] == "completed"
    assert (run_dir / "retrospective.md").exists()


def test_max_iterations_cap(repo):
    for i in range(1, 6):
        write_mock_script(
            repo / "mockdir",
            f"{i:03d}.sh",
            f'echo "RATIONALE: T1 — step {i}"\necho {i} >> work.txt\n'
            "git add -A && git commit -q -m step\n",
        )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=2, log=lambda *_: None)
    assert result.status == "max_iterations"
    assert len(result.iterations) == 2


def test_worktree_isolation_leaves_main_untouched(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo, isolation="worktree")
    main_sha_before = _git_out(repo, "rev-parse", "main").strip()
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "completed"
    assert _git_out(repo, "rev-parse", "main").strip() == main_sha_before
    assert not (repo / "work.txt").exists()
    # The work exists on the run branch.
    assert result.branch.startswith("kelix/run-")
    branch_files = _git_out(repo, "ls-tree", "--name-only", result.branch)
    assert "work.txt" in branch_files


def test_auto_checkpoint_commits_forgotten_work(repo):
    # Agent edits files but "forgets" to commit.
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T1 — sloppy agent"\necho data > forgotten.txt\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    assert result.iterations[0].made_progress
    log_messages = _git_out(repo, "log", "--format=%s")
    assert "auto-checkpoint" in log_messages
    assert (repo / "forgotten.txt").exists()


def test_verification_gate_blocks_sentinel_lie(repo):
    # Agent claims completion but the verify command fails: sentinel ignored,
    # iterations continue until the breaker trips. Done means verified-done.
    for i in (1, 2, 3):
        write_mock_script(
            repo / "mockdir",
            f"{i:03d}.sh",
            f'echo "RATIONALE: T1 — attempt {i}"\necho {i} >> work.txt\n'
            'git add -A && git commit -q -m attempt\necho "KELIX COMPLETE"\n',
        )
    cfg = _config(repo, extra='[verify]\ncommands = ["false"]\n')
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "circuit_breaker"
    assert all(r.verified is False for r in result.iterations)
    assert all(r.sentinel for r in result.iterations)


def test_verification_green_allows_completion(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        COMMIT_TASK + 'echo "KELIX COMPLETE"\n',
    )
    cfg = _config(repo, extra='[verify]\ncommands = ["true"]\n')
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "completed"
    assert result.iterations[0].verified is True


def test_checkpoint_ignores_runner_bookkeeping(repo):
    # Transcripts/run-state/episodes are runner-owned; committing them would
    # make every iteration look like progress and blind the no-diff breaker.
    # (Regression: CI machines without a global gitignore hit exactly this.)
    from kelix.gitutil import checkpoint

    run_dir = repo / ".kelix" / "runs" / "x"
    run_dir.mkdir(parents=True)
    (run_dir / "iter-001.log").write_text("transcript")
    (run_dir / "run.json").write_text("{}")
    (repo / ".kelix" / "memory" / "episodes.jsonl").write_text("{}\n")
    (repo / ".kelix" / "memory" / "loop-metrics.json").write_text("{}\n")
    assert checkpoint(repo, "bookkeeping only") is False

    (repo / "real-work.txt").write_text("agent output")
    assert checkpoint(repo, "agent work") is True
    tracked = _git_out(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert "real-work.txt" in tracked
    assert "iter-001.log" not in tracked
    assert "episodes.jsonl" not in tracked
    assert "loop-metrics.json" not in tracked


def test_circuit_breaker_on_no_diff(repo):
    for i in (1, 2, 3):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", 'echo "did nothing"\n')
    cfg = _config(repo, extra="[loop]\ncircuit_breaker_threshold = 3\n")
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "circuit_breaker"
    assert len(result.iterations) == 3
    diagnosis = (cfg.kelix_dir / "runs" / result.run_id / "diagnosis.md").read_text()
    assert "no diff produced" in diagnosis


def test_breaker_resets_after_success(repo):
    write_mock_script(repo / "mockdir", "001.sh", 'echo "nothing 1"\n')
    write_mock_script(repo / "mockdir", "002.sh", 'echo "nothing 2"\n')
    write_mock_script(repo / "mockdir", "003.sh", COMMIT_TASK)
    write_mock_script(repo / "mockdir", "004.sh", 'echo "nothing 3"\n')
    cfg = _config(repo, extra="[loop]\ncircuit_breaker_threshold = 3\n")
    # 2 failures, then success resets the counter, then 1 failure, then sentinel.
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "completed"


def test_kill_switch_stops_before_iteration(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    (cfg.kelix_dir).mkdir(exist_ok=True)
    (cfg.kelix_dir / "STOP").write_text("stop")
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "killed"
    assert len(result.iterations) == 0


def test_episodes_recorded_and_digested(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    Runner(cfg).run(log=lambda *_: None)
    episodes = (cfg.kelix_dir / "memory" / "episodes.jsonl").read_text().splitlines()
    assert len(episodes) == 2
    from kelix.memory import episode_digest

    digest = episode_digest(cfg)
    assert "T1" in digest


def test_state_md_written_after_run_with_matching_counts(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    result = Runner(cfg).run(log=lambda *_: None)
    state = load_state(cfg.kelix_dir)
    assert state is not None
    assert state.last_task == "T1"
    assert state.current_task == "selecting"
    assert state.done == 0
    assert state.total == 1
    tracked = _git_out(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert ".kelix/STATE.md" in tracked
    assert result.status == "completed"


def test_state_md_on_worktree_branch(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo, isolation="worktree")
    result = Runner(cfg).run(log=lambda *_: None)
    branch_files = _git_out(repo, "ls-tree", "-r", "--name-only", result.branch)
    assert ".kelix/STATE.md" in branch_files


def test_state_md_no_bogus_progress_on_no_diff(repo):
    for i in (1, 2, 3):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", 'echo "did nothing"\n')
    cfg = _config(repo, extra="[loop]\ncircuit_breaker_threshold = 3\n")
    Runner(cfg).run(log=lambda *_: None)
    state = load_state(cfg.kelix_dir)
    assert state is not None
    assert state.done == 0
    assert state.total == 1
    assert state.last_task == ""
    assert state.last_verified_commit == ""


def test_state_md_records_verified_commit(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        COMMIT_TASK + 'echo "KELIX COMPLETE"\n',
    )
    cfg = _config(repo, extra='[verify]\ncommands = ["true"]\n')
    Runner(cfg).run(log=lambda *_: None)
    state = load_state(cfg.kelix_dir)
    assert state is not None
    task_sha = None
    for line in _git_out(repo, "log", "--format=%H %s").strip().splitlines():
        sha, subject = line.split(" ", 1)
        if subject == "T1: do work":
            task_sha = sha
            break
    assert task_sha is not None
    assert state.last_verified_commit == task_sha


ROADMAP_TWO_PHASES = """\
## Milestone v1 — test

### Phase P-A — first

Outcome: first phase.

- REQ-A1: alpha requirement

### Phase P-B — second

Outcome: second phase.

- REQ-B1: beta requirement
"""


def _write_roadmap(repo, text=ROADMAP_TWO_PHASES):
    (repo / ".kelix" / "roadmap.md").write_text(text, encoding="utf-8")


def _write_state(repo, *, phase="P-A", milestone="v1"):
    write_state(
        repo / ".kelix",
        State(milestone=milestone, phase=phase, current_task="selecting"),
    )


def _write_backlog(repo, body: str):
    (repo / ".kelix" / "backlog.md").write_text(f"# Backlog\n\n{body}", encoding="utf-8")


def test_phase_gate_advances_when_covered(repo):
    _write_roadmap(repo)
    _write_state(repo, phase="P-A")
    _write_backlog(
        repo,
        "- [x] T1: finish alpha | priority: 50 | status: done | by: owner | "
        "phase: P-A | req: REQ-A1\n"
        "- [ ] T2: beta work | priority: 49 | status: ready | by: owner | "
        "phase: P-B | req: REQ-B1\n"
        "  details: emit KELIX COMPLETE sentinel; assert in tests/test_loop.py\n",
    )
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T2 — next phase task"\necho "KELIX COMPLETE"\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    state = load_state(cfg.kelix_dir)
    retrospective = (cfg.kelix_dir / "runs" / result.run_id / "retrospective.md").read_text()

    assert state is not None
    assert state.phase == "P-B"
    assert state.blockers == []
    assert "## Phase gate" not in retrospective


def test_phase_gate_blocks_and_reports_uncovered(repo):
    _write_roadmap(repo)
    _write_state(repo, phase="P-A")
    _write_backlog(
        repo,
        "- [ ] T0: unrelated work | priority: 50 | status: ready | by: owner\n"
        "  details: write work.txt; assert file exists in tests/test_loop.py\n",
    )
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T0 — unrelated work"\necho work > work.txt\n'
        "git add -A && git commit -q -m 'T0: partial'\n",
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    state = load_state(cfg.kelix_dir)
    retrospective = (cfg.kelix_dir / "runs" / result.run_id / "retrospective.md").read_text()

    assert state is not None
    assert state.phase == "P-A"
    assert state.blockers == ["REQ-A1: uncovered"]
    assert "## Phase gate" in retrospective
    assert "- REQ-A1: uncovered" in retrospective


def test_phase_gate_noop_without_roadmap(repo):
    _write_state(repo, phase="P-A")
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        COMMIT_TASK + 'echo "KELIX COMPLETE"\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(log=lambda *_: None)
    state = load_state(cfg.kelix_dir)

    assert state is not None
    assert state.phase == "P-A"
    retrospective = (cfg.kelix_dir / "runs" / result.run_id / "retrospective.md").read_text()
    assert "## Phase gate" not in retrospective


def test_rationale_fallback_from_commit_subject(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo work >> work.txt\ngit add -A && git commit -q -m "T1: forgot rationale"\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    rec = result.iterations[0]
    assert rec.rationale == "(from commit) T1: forgot rationale"
    episodes = (cfg.kelix_dir / "memory" / "episodes.jsonl").read_text()
    assert "(from commit) T1: forgot rationale" in episodes


def test_no_rationale_no_commit_flags_transcript_in_retrospective(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "thinking..."\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    assert result.iterations[0].rationale == ""
    retro = (cfg.kelix_dir / "runs" / result.run_id / "retrospective.md").read_text()
    assert "no rationale — see transcript" in retro


def test_ledger_row_retry_count_on_same_task(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T1 — attempt 1"\necho "did nothing"\n',
    )
    write_mock_script(
        repo / "mockdir",
        "002.sh",
        'echo "RATIONALE: T1 — attempt 2"\necho work >> work.txt\n'
        'git add -A && git commit -q -m "T1: done"\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=2, log=lambda *_: None)
    assert len(result.ledger_rows) == 2
    first, second = result.ledger_rows
    assert first.run_id == result.run_id
    assert first.iteration == 1
    assert first.task_id == "T1"
    assert first.retry_count == 0
    assert first.agent_id == "solo"
    assert first.fleet_id == ""
    assert first.failure
    assert second.task_id == "T1"
    assert second.retry_count == 1
    assert second.failure == ""


def test_ledger_row_circuit_breaker_cause(repo):
    for i in (1, 2, 3):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", 'echo "did nothing"\n')
    cfg = _config(repo, extra="[loop]\ncircuit_breaker_threshold = 3\n")
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "circuit_breaker"
    assert len(result.ledger_rows) == 3
    assert all(row.circuit_breaker_cause == "consecutive_failures:3" for row in result.ledger_rows)


def test_ledger_row_backlog_lint_on_kelix_proposed_edit(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        """\
echo "RATIONALE: T1 — add slop proposed task"
printf '\\n- [ ] KX1: kelix slop | priority: 10 | status: proposed | by: kelix\\n' \\
  >> .kelix/backlog.md
echo work >> work.txt
git add -A && git commit -q -m "T1: append kelix proposed slop"
""",
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    assert len(result.ledger_rows) == 1
    assert result.ledger_rows[0].backlog_lint.get("missing_details", 0) >= 1


def test_ledger_row_skills_injected_from_manifest(repo):
    skill_dir = repo / ".kelix" / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: Fixture skill for ledger capture\n---\n"
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "add foo skill fixture"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo, extra='[verify]\ncommands = ["true"]\n')
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    assert len(result.ledger_rows) == 1
    assert result.ledger_rows[0].skills_injected == ["foo"]
    context = json.loads(
        (cfg.kelix_dir / "runs" / result.run_id / "context-001.json").read_text()
    )
    assert any(
        item["slot"] == "skills" and item["source"] == ".kelix/skills/foo/SKILL.md"
        for item in context["items"]
    )
    metrics = load_metrics(cfg.kelix_dir / METRICS_FILE)
    assert metrics.iterations[0].skills_injected == ["foo"]


def test_loop_metrics_rollup_after_run(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo, extra='[verify]\ncommands = ["true"]\n')
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    metrics_path = cfg.kelix_dir / METRICS_FILE
    assert metrics_path.is_file()
    metrics = load_metrics(metrics_path)
    assert len(metrics.iterations) == 1
    assert metrics.iterations[0] == result.ledger_rows[0]


def test_loop_metrics_rollup_appends_across_runs(repo):
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T1 — first run"\necho one >> work.txt\n'
        'git add -A && git commit -q -m "T1: first"\n',
    )
    cfg = _config(repo)
    first = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T2 — second run"\necho two >> work.txt\n'
        'git add -A && git commit -q -m "T2: second"\n',
    )
    second = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    metrics = load_metrics(cfg.kelix_dir / METRICS_FILE)
    assert len(metrics.iterations) == 2
    assert metrics.iterations[0].run_id == first.run_id
    assert metrics.iterations[0].task_id == "T1"
    assert metrics.iterations[1].run_id == second.run_id
    assert metrics.iterations[1].task_id == "T2"


DISTILL_AND_COMMIT = """\
prompt=$(cat)
if echo "$prompt" | grep -q "Distillation contract"; then
  mkdir -p .kelix/skills/_proposed/test-skill
  cat > .kelix/skills/_proposed/test-skill/SKILL.md << 'EOF'
---
name: test-skill
description: Distilled from run transcripts
---
1. Reuse this procedure when the same failure mode appears.
EOF
  git add .kelix/skills/_proposed/test-skill/SKILL.md
  git commit -q -m "distill: propose test-skill"
else
  echo "RATIONALE: T1 — highest priority ready task"
  echo "work" >> work.txt
  git add -A && git commit -q -m "T1: do work"
fi
"""


def test_distillation_writes_proposed_skill(repo):
    write_mock_script(repo / "mockdir", "001.sh", DISTILL_AND_COMMIT)
    cfg = _config(repo, distill_skills=True)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    skill_md = repo / ".kelix" / "skills" / "_proposed" / "test-skill" / "SKILL.md"
    assert skill_md.is_file()
    text = skill_md.read_text()
    assert "name: test-skill" in text
    assert "description: Distilled from run transcripts" in text
    distill_log = cfg.kelix_dir / "runs" / result.run_id / "distill" / "distill.log"
    assert distill_log.is_file()


def test_distillation_skipped_when_disabled(repo):
    write_mock_script(repo / "mockdir", "001.sh", DISTILL_AND_COMMIT)
    cfg = _config(repo, distill_skills=False)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)
    skill_md = repo / ".kelix" / "skills" / "_proposed" / "test-skill" / "SKILL.md"
    assert not skill_md.exists()
    assert not (cfg.kelix_dir / "runs" / result.run_id / "distill").exists()


def test_spec_gate_blocks_vague_ready_task(repo, capsys):
    (repo / ".kelix" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] T1: vague task | priority: 50 | status: ready | by: owner\n"
        "  details: improve everything\n"
    )
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T1 — should not run"\n',
    )
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)

    assert result.status == "spec_gate"
    assert len(result.iterations) == 0
    err = capsys.readouterr().err
    assert "spec gate:" in err
    assert "T1:" in err
    assert "bad:" in err
    assert "good:" in err


def test_spec_gate_allows_well_specified_ready_task(repo):
    (repo / ".kelix" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] T1: good task | priority: 50 | status: ready | by: owner\n"
        "  details: echo work into work.txt; assert in tests/test_loop.py\n"
    )
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)

    assert result.status != "spec_gate"
    assert len(result.iterations) >= 1
