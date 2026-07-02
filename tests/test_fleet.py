"""Fleet mode tests: config, claim hook, multi-agent run with zero collisions,
status rendering from coordination files alone."""

import re

import pytest
from conftest import make_repo, write_mock_script

from kalph.claims import list_claims
from kalph.config import load_config
from kalph.fleet import (
    FleetError,
    load_fleet_spec,
    make_claim_hook,
    render_status,
    run_fleet,
)

FLEET_TOML = """\
[fleet]
max_iterations = 4

[[agents]]
id = "builder-1"
role = "builder"

[[agents]]
id = "scribe-1"
role = "scribe"

[roles.scribe]
prompt = "Custom scribe prompt for this repo."
"""

FLEET_BACKLOG = """\
# Backlog

- [ ] FT1: task one | priority: 90 | status: ready | by: owner
- [ ] FT2: task two | priority: 80 | status: ready | by: owner
- [ ] FT3: task three | priority: 70 | status: ready | by: owner
- [ ] FT4: task four | priority: 60 | status: ready | by: owner
"""

# Fleet mock agents: mark the assigned task (parsed from the prompt on stdin)
# done in the backlog and commit. This exercises the real claim/done flow.
FLEET_SCRIPT = r"""
prompt=$(cat)
marker='Your assigned task for this iteration:'
task=$(printf '%s' "$prompt" | grep -o "$marker [A-Za-z0-9_-]*" | awk '{print $NF}')
if [ -z "$task" ]; then echo "no assignment"; exit 0; fi
sleep 0.5
echo "RATIONALE: $task — assigned by fleet claim"
python3 - "$task" <<'PY'
import pathlib, re, sys
task = sys.argv[1]
p = pathlib.Path('.kalph/backlog.md')
pat = re.compile(r'- \[ \] ' + re.escape(task) + r': (.*) \| status: ready')
p.write_text(pat.sub(r'- [x] ' + task + r': \1 | status: done', p.read_text()))
PY
echo "done $task" >> fleet-work.txt
git add -A && git commit -q -m "$task: fleet work"
"""


def _fleet_repo(tmp_path, n_scripts=6):
    repo = make_repo(tmp_path / "repo")
    (repo / ".kalph" / "backlog.md").write_text(FLEET_BACKLOG)
    (repo / ".kalph" / "fleet.toml").write_text(FLEET_TOML)
    for i in range(1, n_scripts + 1):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", FLEET_SCRIPT)
    (repo / "kalph.toml").write_text(
        """
[agent]
adapter = "mock"
mock_dir = "mockdir"

[git]
isolation = "worktree"
"""
    )
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fleet setup"],
        cwd=repo, check=True, capture_output=True,
    )
    return repo


def test_load_fleet_spec(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kalph/fleet.toml")
    assert [a.id for a in spec.agents] == ["builder-1", "scribe-1"]
    assert spec.max_iterations == 4
    assert "Custom scribe prompt" in spec.role_prompt("scribe")
    assert "one agent in a Kalph fleet" in spec.role_prompt("scribe")
    assert "builder" in spec.role_prompt("builder")


def test_fleet_spec_validation(tmp_path):
    repo = _fleet_repo(tmp_path)
    (repo / ".kalph" / "fleet.toml").write_text("[fleet]\n")
    cfg = load_config(repo)
    with pytest.raises(FleetError, match="no agents"):
        load_fleet_spec(cfg, ".kalph/fleet.toml")


def test_claim_hook_assigns_distinct_tasks(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kalph/fleet.toml")
    hook_a = make_claim_hook(cfg, spec, "agent-a")
    hook_b = make_claim_hook(cfg, spec, "agent-b")
    a = hook_a(repo, 1)
    b = hook_b(repo, 1)
    assert a and b
    task_a = re.search(r"(FT\d)", a).group(1)
    task_b = re.search(r"(FT\d)", b).group(1)
    assert task_a != task_b  # never the same task
    # Priority order: a got FT1 (highest), b got FT2.
    assert task_a == "FT1" and task_b == "FT2"


def test_agent_sticks_to_its_unfinished_task(tmp_path):
    # A failed/unfinished task stays at the top for the same agent: the hook
    # re-assigns it rather than moving on (verified-done rule).
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kalph/fleet.toml")
    hook = make_claim_hook(cfg, spec, "agent-a")
    first = hook(repo, 1)
    second = hook(repo, 2)
    assert "FT1" in first and "FT1" in second


def test_claim_hook_returns_none_when_all_claimed(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kalph/fleet.toml")
    for i in range(4):  # four distinct agents claim the four tasks
        assert make_claim_hook(cfg, spec, f"hog-{i}")(repo, 1) is not None
    starved = make_claim_hook(cfg, spec, "starved")
    assert starved(repo, 1) is None


def test_fleet_run_end_to_end_zero_collisions(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    rc = run_fleet(cfg, ".kalph/fleet.toml")
    assert rc == 0
    claims = list_claims(cfg.kalph_dir)
    # Every task claimed exactly once (file per task), each by a single agent.
    claimed_tasks = [c["task"] for c in claims]
    assert sorted(claimed_tasks) == ["FT1", "FT2", "FT3", "FT4"]
    # Both agents did work (fleet actually parallelized).
    agents_used = {c["agent"] for c in claims}
    assert len(agents_used) == 2
    # Fleet retrospective written and names both agents.
    retros = list((cfg.kalph_dir / "runs").glob("fleet-*.md"))
    assert retros
    body = retros[0].read_text()
    assert "builder-1" in body and "scribe-1" in body


def test_render_status_reads_coordination_files(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kalph/fleet.toml")
    make_claim_hook(cfg, spec, "agent-a")(repo, 1)
    out = render_status(cfg)
    assert "FT1" in out and "agent-a" in out
    (cfg.kalph_dir / "STOP").write_text("halt")
    assert "KILL SWITCH" in render_status(cfg)
