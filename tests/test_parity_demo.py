"""Phase 1 parity demo (PLAN.md C8).

A toy repo with a 5-task plan is completed end-to-end by the loop with real
verification after every iteration, worktree isolation, and an agent-emitted
completion sentinel. This is the regression baseline for everything built
after Phase 1: if this breaks, the loop core broke.
"""

import subprocess

from conftest import make_repo, write_mock_script

from kelix.config import load_config
from kelix.loop import Runner

TOY_BACKLOG = """\
# Toy project backlog

- [ ] T1: add() function | priority: 90 | status: ready | by: owner
- [ ] T2: sub() function | priority: 80 | status: ready | by: owner
- [ ] T3: mul() function | priority: 70 | status: ready | by: owner
- [ ] T4: div() with zero guard | priority: 60 | status: ready | by: owner
- [ ] T5: cli entrypoint | priority: 50 | status: ready | by: owner
"""

# Each script: implement one task, extend the executable spec (checks.py),
# mark the task done in the backlog, commit. Exactly the loop contract.
TASK_SNIPPETS = {
    1: ("def add(a, b):\n    return a + b\n", "assert calc.add(2, 3) == 5"),
    2: ("def sub(a, b):\n    return a - b\n", "assert calc.sub(5, 3) == 2"),
    3: ("def mul(a, b):\n    return a * b\n", "assert calc.mul(4, 3) == 12"),
    4: (
        "def div(a, b):\n    if b == 0:\n        raise ValueError('division by zero')\n"
        "    return a / b\n",
        "assert calc.div(8, 2) == 4",
    ),
    5: (
        "def main(argv):\n    op, a, b = argv[0], float(argv[1]), float(argv[2])\n"
        "    return {'add': add, 'sub': sub, 'mul': mul, 'div': div}[op](a, b)\n",
        "assert calc.main(['add', '1', '2']) == 3",
    ),
}


def _script(n: int) -> str:
    code, check = TASK_SNIPPETS[n]
    lines = [
        f'echo "RATIONALE: T{n} — highest-priority ready task"',
        f"cat >> calc.py <<'EOF'\n{code}EOF",
        f'echo "{check}" >> checks_body.py',
        "cat checks_header.py checks_body.py > checks.py",
        "python3 checks.py",  # agent-side verification before claiming done
        f"""python3 -c "
import pathlib
p = pathlib.Path('.kelix/backlog.md')
p.write_text(p.read_text().replace('- [ ] T{n}:', '- [x] T{n}:'))
" """,
        f'git add -A && git commit -q -m "T{n}: implemented and verified"',
    ]
    if n == 5:
        lines.append('echo "KELIX COMPLETE"')
    return "\n".join(lines) + "\n"


def test_parity_demo_five_task_plan(tmp_path):
    repo = make_repo(tmp_path / "toy")
    (repo / ".kelix" / "backlog.md").write_text(TOY_BACKLOG)
    (repo / "calc.py").write_text("# toy calculator\n")
    (repo / "checks_header.py").write_text("import calc\n")
    (repo / "checks_body.py").write_text("")
    (repo / "checks.py").write_text("import calc\n")
    for n in range(1, 6):
        write_mock_script(repo / "mockdir", f"{n:03d}.sh", _script(n))
    (repo / "kelix.toml").write_text(
        """
[agent]
adapter = "mock"
mock_dir = "mockdir"

[verify]
commands = ["python3 checks.py"]

[git]
isolation = "worktree"
"""
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "toy project setup"],
        cwd=repo, check=True, capture_output=True,
    )

    cfg = load_config(repo)
    result = Runner(cfg).run(log=lambda *_: None)

    # End-to-end: completed within the cap, every iteration verified green.
    assert result.status == "completed"
    assert len(result.iterations) == 5
    assert all(r.verified is True for r in result.iterations)
    assert all(r.made_progress for r in result.iterations)
    assert result.iterations[-1].sentinel

    # All five tasks checked off on the run branch; main untouched.
    branch_backlog = subprocess.run(
        ["git", "show", f"{result.branch}:.kelix/backlog.md"],
        cwd=repo, capture_output=True, text=True,
    ).stdout
    assert branch_backlog.count("- [x]") == 5
    main_backlog = subprocess.run(
        ["git", "show", "main:.kelix/backlog.md"],
        cwd=repo, capture_output=True, text=True,
    ).stdout
    assert main_backlog.count("- [ ]") == 5

    # Auditable trail: transcripts + retrospective + episodes exist.
    run_dir = cfg.kelix_dir / "runs" / result.run_id
    assert len(list(run_dir.glob("iter-*.log"))) == 5
    retro = (run_dir / "retrospective.md").read_text()
    assert "completed" in retro and "5 verified" in retro
