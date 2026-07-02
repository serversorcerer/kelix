"""CI integration test (mission Phase 7): a 2-iteration loop against a fixture
repo with a mock agent, exercising the real runner end to end with worktree
isolation and verification — the smoke test that proves the loop works in a
clean CI environment."""

import subprocess

from conftest import make_repo, write_mock_script

from kalph.config import load_config
from kalph.loop import Runner


def test_two_iteration_loop_on_fixture(tmp_path):
    repo = make_repo(tmp_path / "fixture")
    (repo / ".kalph" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] A1: create greeting module | priority: 90 | status: ready | by: owner\n"
        "- [ ] A2: add farewell | priority: 80 | status: ready | by: owner\n"
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
    (repo / "kalph.toml").write_text(
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
