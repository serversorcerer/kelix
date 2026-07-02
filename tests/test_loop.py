"""Loop runner tests: sentinel, isolation, checkpoints, verification gate,
circuit breaker, kill switch. These are the regression suite for the loop
contract itself."""

import json
import subprocess

from conftest import write_mock_script

from kalph.config import load_config
from kalph.loop import Runner


def _config(repo, extra="", mock_dir="mockdir", isolation="none"):
    (repo / "kalph.toml").write_text(
        f"""
[agent]
adapter = "mock"
mock_dir = "{mock_dir}"

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
    run_dir = cfg.kalph_dir / "runs" / result.run_id
    assert (run_dir / "iter-001.log").exists()
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
    assert result.branch.startswith("kalph/run-")
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
            'git add -A && git commit -q -m attempt\necho "KALPH COMPLETE"\n',
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
        COMMIT_TASK + 'echo "KALPH COMPLETE"\n',
    )
    cfg = _config(repo, extra='[verify]\ncommands = ["true"]\n')
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "completed"
    assert result.iterations[0].verified is True


def test_circuit_breaker_on_no_diff(repo):
    for i in (1, 2, 3):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", 'echo "did nothing"\n')
    cfg = _config(repo, extra="[loop]\ncircuit_breaker_threshold = 3\n")
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "circuit_breaker"
    assert len(result.iterations) == 3
    diagnosis = (cfg.kalph_dir / "runs" / result.run_id / "diagnosis.md").read_text()
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
    (cfg.kalph_dir).mkdir(exist_ok=True)
    (cfg.kalph_dir / "STOP").write_text("stop")
    result = Runner(cfg).run(log=lambda *_: None)
    assert result.status == "killed"
    assert len(result.iterations) == 0


def test_episodes_recorded_and_digested(repo):
    write_mock_script(repo / "mockdir", "001.sh", COMMIT_TASK)
    cfg = _config(repo)
    Runner(cfg).run(log=lambda *_: None)
    episodes = (cfg.kalph_dir / "memory" / "episodes.jsonl").read_text().splitlines()
    assert len(episodes) == 2
    from kalph.memory import episode_digest

    digest = episode_digest(cfg)
    assert "T1" in digest
