"""Fleet mode tests: config, claim hook, multi-agent run with zero collisions,
status rendering from coordination files alone."""

import re

import pytest
from conftest import make_repo, write_mock_script

from kelix.backlog import Task
from kelix.claims import list_claims
from kelix.config import load_config
from kelix.fleet import (
    FleetAgent,
    FleetError,
    FleetSpec,
    _write_fleet_retrospective,
    fleet_id_from_config,
    infer_task_kind,
    load_fleet_spec,
    make_claim_hook,
    render_status,
    run_fleet,
)
from kelix.loop import IterationRecord, RunResult
from kelix.metrics import METRICS_FILE, load_metrics

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

WAVE_BACKLOG = """\
# Backlog

- [ ] W0: wave zero task | priority: 90 | status: ready | by: owner
- [ ] W1: wave one task | priority: 99 | status: ready | by: owner | deps: W0
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
p = pathlib.Path('.kelix/backlog.md')
pat = re.compile(r'- \[ \] ' + re.escape(task) + r': (.*) \| status: ready')
p.write_text(pat.sub(r'- [x] ' + task + r': \1 | status: done', p.read_text()))
PY
echo "done $task" >> fleet-work.txt
git add -A && git commit -q -m "$task: fleet work"
"""


def _fleet_repo(tmp_path, n_scripts=6):
    repo = make_repo(tmp_path / "repo")
    (repo / ".kelix" / "backlog.md").write_text(FLEET_BACKLOG)
    (repo / ".kelix" / "fleet.toml").write_text(FLEET_TOML)
    for i in range(1, n_scripts + 1):
        write_mock_script(repo / "mockdir", f"{i:03d}.sh", FLEET_SCRIPT)
    (repo / "kelix.toml").write_text(
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
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")
    assert [a.id for a in spec.agents] == ["builder-1", "scribe-1"]
    assert spec.max_iterations == 4
    assert "Custom scribe prompt" in spec.role_prompt("scribe")
    assert "one agent in a Kelix fleet" in spec.role_prompt("scribe")
    assert "builder" in spec.role_prompt("builder")


def test_fleet_spec_validation(tmp_path):
    repo = _fleet_repo(tmp_path)
    (repo / ".kelix" / "fleet.toml").write_text("[fleet]\n")
    cfg = load_config(repo)
    with pytest.raises(FleetError, match="no agents"):
        load_fleet_spec(cfg, ".kelix/fleet.toml")


def test_claim_hook_assigns_distinct_tasks(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")
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
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")
    hook = make_claim_hook(cfg, spec, "agent-a")
    first = hook(repo, 1)
    second = hook(repo, 2)
    assert "FT1" in first and "FT1" in second


def test_claim_hook_returns_none_when_all_claimed(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")
    for i in range(4):  # four distinct agents claim the four tasks
        assert make_claim_hook(cfg, spec, f"hog-{i}")(repo, 1) is not None
    starved = make_claim_hook(cfg, spec, "starved")
    assert starved(repo, 1) is None


def test_claim_hook_respects_earliest_incomplete_wave(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / ".kelix" / "backlog.md").write_text(WAVE_BACKLOG)
    (repo / ".kelix" / "fleet.toml").write_text(FLEET_TOML)
    (repo / "kelix.toml").write_text("[agent]\nadapter = \"mock\"\n")
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")

    hook_a = make_claim_hook(cfg, spec, "agent-a")
    hook_b = make_claim_hook(cfg, spec, "agent-b")

    first = hook_a(repo, 1)
    assert first is not None
    assert "W0" in first
    assert "W1" not in first

    # W0 is claimed but not done — wave 1 must stay blocked for other agents.
    second = hook_b(repo, 1)
    assert second is None or "W1" not in second


def test_render_status_shows_pending_task_waves(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / ".kelix" / "backlog.md").write_text(WAVE_BACKLOG)
    (repo / "kelix.toml").write_text("[agent]\nadapter = \"mock\"\n")
    cfg = load_config(repo)
    out = render_status(cfg)
    assert "Pending tasks (waves):" in out
    assert "wave 0: W0 (ready)" in out
    assert "wave 1: W1 (ready)" in out


def test_fleet_run_end_to_end_zero_collisions(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    rc = run_fleet(cfg, ".kelix/fleet.toml")
    assert rc == 0
    claims = list_claims(cfg.kelix_dir)
    # Every task claimed exactly once (file per task), each by a single agent.
    claimed_tasks = [c["task"] for c in claims]
    assert sorted(claimed_tasks) == ["FT1", "FT2", "FT3", "FT4"]
    # Both agents did work (fleet actually parallelized).
    agents_used = {c["agent"] for c in claims}
    assert len(agents_used) == 2
    # Fleet retrospective written and names both agents.
    retros = list((cfg.kelix_dir / "runs").glob("fleet-*.md"))
    assert retros
    body = retros[0].read_text()
    assert "builder-1" in body and "scribe-1" in body


def test_fleet_metrics_aggregation(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    rc = run_fleet(cfg, ".kelix/fleet.toml", max_iterations=2)
    assert rc == 0

    metrics = load_metrics(cfg.kelix_dir / METRICS_FILE)
    assert metrics.iterations
    agent_ids = {row.agent_id for row in metrics.iterations}
    assert agent_ids == {"builder-1", "scribe-1"}
    fleet_id = fleet_id_from_config(".kelix/fleet.toml")
    assert all(row.fleet_id == fleet_id for row in metrics.iterations)

    assert len(metrics.fleet_summaries) == 1
    summary = metrics.fleet_summaries[0]
    assert summary.fleet_id == "fleet"
    assert len(summary.run_ids) == 2
    assert summary.iteration_count == len(metrics.iterations)
    assert 0.0 <= summary.verified_rate <= 1.0
    assert summary.breaker_trips == 0


def test_render_status_reads_coordination_files(tmp_path):
    repo = _fleet_repo(tmp_path)
    cfg = load_config(repo)
    spec = load_fleet_spec(cfg, ".kelix/fleet.toml")
    make_claim_hook(cfg, spec, "agent-a")(repo, 1)
    out = render_status(cfg)
    assert "FT1" in out and "agent-a" in out
    assert "Phase gate coverage" not in out
    (cfg.kelix_dir / "STOP").write_text("halt")
    assert "KILL SWITCH" in render_status(cfg)


GATE_ROADMAP = """\
# Roadmap

## Milestone m1 — Demo

### Phase P-GATE — gate phase

Outcome: gate it.

- REQ-G1: first req
- REQ-G2: second req
- REQ-G3: third req
"""

GATE_BACKLOG = """\
# Backlog

- [x] T1: first | priority: 90 | status: done | by: owner | phase: P-GATE | req: REQ-G1
- [x] T2: second | priority: 80 | status: done | by: owner | phase: P-GATE | req: REQ-G2
- [ ] T3: third | priority: 70 | status: ready | by: owner | phase: P-GATE | req: REQ-G3
"""

GATE_STATE = """\
# Kelix state

- milestone: m1 — Demo
- phase: P-GATE
- current_task: selecting
- last_task: T2
- last_verified_commit: abc123
- done: 2
- total: 3
- blockers:
  - REQ-G3
"""


def test_render_status_phase_gate_coverage(tmp_path):
    repo = make_repo(tmp_path / "repo")
    kelix = repo / ".kelix"
    kelix.mkdir(parents=True, exist_ok=True)
    (kelix / "roadmap.md").write_text(GATE_ROADMAP)
    (kelix / "backlog.md").write_text(GATE_BACKLOG)
    (kelix / "STATE.md").write_text(GATE_STATE)
    (repo / "kelix.toml").write_text("[agent]\nadapter = \"mock\"\n")
    cfg = load_config(repo)
    out = render_status(cfg)
    assert "Milestone: m1 — Demo" in out
    assert "Phase: P-GATE — gate phase" in out
    assert "Phase gate coverage:" in out
    assert "REQ-G1     covered      T1" in out
    assert "REQ-G2     covered      T2" in out
    assert "REQ-G3     in-progress  T3" in out
    assert "Blockers:" in out
    assert "REQ-G3" in out.split("Blockers:")[1]


def test_infer_task_kind_heuristics():
    base = dict(priority=50, status="ready", by="owner")
    assert infer_task_kind(Task("T1", "add unit tests for module", **base)) == "test"
    assert infer_task_kind(Task("T2", "write planning documentation", **base)) == "docs"
    assert infer_task_kind(Task("T3", "fix broken build", **base)) == "fix"
    assert infer_task_kind(Task("T4", "add priority field to backlog", **base)) == "feature"


def test_fleet_retrospective_reports_role_drift(tmp_path):
    repo = make_repo(tmp_path / "repo")
    backlog = """\
# Backlog

- [ ] T1: add unit tests for module | priority: 90 | status: ready | by: owner
- [ ] T2: write planning documentation | priority: 80 | status: ready | by: owner
"""
    (repo / ".kelix" / "backlog.md").write_text(backlog)
    (repo / "kelix.toml").write_text("[agent]\nadapter = \"mock\"\n")
    cfg = load_config(repo)

    spec = FleetSpec(
        agents=[
            FleetAgent(id="verifier-1", role="verifier"),
            FleetAgent(id="scribe-1", role="scribe"),
        ]
    )
    results = {
        "verifier-1": RunResult(
            run_id="run-v",
            status="completed",
            branch="kelix/run-v",
            iterations=[
                IterationRecord(
                    index=1,
                    started_at="2026-07-02T00:00:00",
                    rationale="T2 — scribe task claimed by verifier",
                    verified=True,
                ),
            ],
        ),
        "scribe-1": RunResult(
            run_id="run-s",
            status="completed",
            branch="kelix/run-s",
            iterations=[
                IterationRecord(
                    index=1,
                    started_at="2026-07-02T00:00:00",
                    rationale="T1 — test task claimed by scribe",
                    verified=True,
                ),
            ],
        ),
    }
    _write_fleet_retrospective(cfg, spec, results, {})

    retros = list((cfg.kelix_dir / "runs").glob("fleet-*.md"))
    assert retros
    body = retros[0].read_text()
    assert "role-match: no (verifier vs docs)" in body
    assert "role-match: no (scribe vs test)" in body
    assert "role drift: 1/1 iterations" in body
