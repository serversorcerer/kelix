"""CI integration test (mission Phase 7): a 2-iteration loop against a fixture
repo with a mock agent, exercising the real runner end to end with worktree
isolation and verification — the smoke test that proves the loop works in a
clean CI environment."""

import io
import subprocess

from conftest import make_repo, write_mock_script

from kelix.art import run_complete_receipt
from kelix.cli import cmd_init, cmd_status
from kelix.config import load_config
from kelix.loop import Runner


class _InitArgs:
    path = "."
    from_spec = ""
    agent = "mock"


class _StatusArgs:
    path = "."


def test_two_iteration_loop_on_fixture(tmp_path):
    repo = make_repo(tmp_path / "fixture")
    (repo / ".kelix" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] A1: create greeting module | priority: 90 | status: ready | by: owner\n"
        "  details: greet.py with hello(); assert in python3 -c import greet\n"
        "- [ ] A2: add farewell | priority: 80 | status: ready | by: owner\n"
        "  details: add bye() to greet.py; assert in python3 -c import greet\n"
    )
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: A1 — first task"\n'
        'echo "def hello(): return \'hi\'" > greet.py\n'
        "python3 -c \"import greet; assert greet.hello() == 'hi'\"\n"
        "git add -A && git commit -q -m 'A1: greeting'\n",
    )
    write_mock_script(
        repo / "mockdir",
        "002.sh",
        'echo "RATIONALE: A2 — second task"\n'
        'echo "def bye(): return \'bye\'" >> greet.py\n'
        "python3 -c \"import greet; assert greet.bye() == 'bye'\"\n"
        "git add -A && git commit -q -m 'A2: farewell'\n",
    )
    (repo / "kelix.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mockdir"\n'
        '[verify]\ncommands = ["python3 -c \\"import greet\\""]\n'
        '[git]\nisolation = "worktree"\n'
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True, capture_output=True
    )

    cfg = load_config(repo)
    result = Runner(cfg).run(max_iterations=2, log=lambda *_: None)

    assert result.status == "max_iterations"
    assert len(result.iterations) == 2
    assert all(r.made_progress and r.verified for r in result.iterations)
    # Isolation held: fixture working tree untouched on main.
    assert not (repo / "greet.py").exists()


def test_run_complete_receipt_names_verify_gate_and_verified_count(tmp_path):
    repo = make_repo(tmp_path / "receipt")
    (repo / ".kelix" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] A1: create greeting module | priority: 90 | status: ready | by: owner\n"
        "  details: greet.py with hello(); assert in python3 -c import greet\n"
    )
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: A1 — first task"\n'
        'echo "def hello(): return \'hi\'" > greet.py\n'
        "python3 -c \"import greet; assert greet.hello() == 'hi'\"\n"
        "git add -A && git commit -q -m 'A1: greeting'\n",
    )
    (repo / "kelix.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mockdir"\n'
        '[verify]\ncommands = ["python3 -c \\"import greet\\""]\n'
        '[git]\nisolation = "worktree"\n'
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True, capture_output=True
    )

    cfg = load_config(repo)
    captured = io.StringIO()
    result = Runner(cfg).run(
        max_iterations=1,
        log=lambda msg: captured.write(msg + "\n"),
    )
    output = captured.getvalue()

    assert result.status == "max_iterations"
    assert "2 verified-done" not in output  # guard against bare "done"
    assert "1 verified-done" in output
    assert 'verify: python3 -c "import greet" exit 0' in output
    assert result.verified_commits
    assert result.verified_commits[0] in output

    receipt = run_complete_receipt(
        run_id=result.run_id,
        status=result.status,
        iteration_count=len(result.iterations),
        verified_count=sum(1 for rec in result.iterations if rec.verified is True),
        verify_results=[(r.command, r.exit_code) for r in result.last_verify_report.results],
        verified_commits=list(result.verified_commits),
    )
    assert "verified-done" in receipt
    assert 'exit 0' in receipt
    assert result.verified_commits[0] in receipt


def test_init_and_status_use_themed_say_output(tmp_path, capsys):
    repo = make_repo(tmp_path / "cli-art")

    init_args = _InitArgs()
    init_args.path = str(repo)
    init_args.agent = "mock"
    assert cmd_init(init_args, is_tty=False) == 0
    init_out = capsys.readouterr().out
    assert "◉ initialized:" in init_out

    status_args = _StatusArgs()
    status_args.path = str(repo)
    assert cmd_status(status_args) == 0
    status_out = capsys.readouterr().out
    assert "◌ kelix status" in status_out
    assert "No task claims" in status_out
