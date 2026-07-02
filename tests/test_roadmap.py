from pathlib import Path

from kelix.backlog import Task
from kelix.roadmap import (
    Milestone,
    Req,
    coverage,
    load_roadmap,
    parse_roadmap,
)

REAL_ROADMAP = Path(__file__).resolve().parents[1] / ".kelix" / "roadmap.md"


def test_parse_real_roadmap():
    text = REAL_ROADMAP.read_text(encoding="utf-8")
    roadmap = parse_roadmap(text)

    assert len(roadmap.milestones) >= 2
    assert roadmap.milestones[0].id == "v0.2"
    assert "Planning Core" in roadmap.milestones[0].title

    spine = next(p for p in roadmap.phases if p.id == "P-SPINE")
    assert spine.title == "the state spine"
    assert spine.milestone_id == "v0.2"
    assert "every iteration starts" in spine.outcome

    spine_reqs = roadmap.reqs_for("P-SPINE")
    assert {r.id for r in spine_reqs} == {"REQ-S1", "REQ-S2", "REQ-S3"}
    assert all(r.phase_id == "P-SPINE" for r in spine_reqs)

    intent_reqs = roadmap.reqs_for("P-INTENT")
    assert {r.id for r in intent_reqs} == {"REQ-I1", "REQ-I2", "REQ-I3"}


def test_load_real_roadmap():
    root = Path(__file__).resolve().parents[1]
    loaded = load_roadmap(root / ".kelix")
    assert loaded is not None
    assert any(m.id == "v0.3" for m in loaded.milestones)


def test_multiple_milestones():
    text = """\
# Roadmap

Some intro prose.

## Milestone m1 — First

### Phase P-A — alpha

Outcome: build alpha.

- REQ-A1: do alpha

## Milestone m2 — Second

Prose between milestones.

### Phase P-B — beta

Outcome: build beta.

- REQ-B1: do beta
- REQ-B2: verify beta
"""
    roadmap = parse_roadmap(text)

    assert roadmap.milestones == [
        Milestone(id="m1", title="First"),
        Milestone(id="m2", title="Second"),
    ]
    assert len(roadmap.phases) == 2
    assert roadmap.phases[0].milestone_id == "m1"
    assert roadmap.phases[1].milestone_id == "m2"
    assert roadmap.phases[1].outcome == "build beta."
    assert len(roadmap.reqs) == 3
    assert roadmap.reqs_for("P-A") == [Req(id="REQ-A1", text="do alpha", phase_id="P-A")]
    assert {r.id for r in roadmap.reqs_for("P-B")} == {"REQ-B1", "REQ-B2"}


def test_no_reqs():
    text = """\
## Milestone m1 — Empty phase

### Phase P-EMPTY — nothing here

Outcome: no requirements yet.

More prose that is not a REQ line.
"""
    roadmap = parse_roadmap(text)

    assert len(roadmap.milestones) == 1
    assert len(roadmap.phases) == 1
    assert roadmap.phases[0].outcome == "no requirements yet."
    assert roadmap.reqs == []
    assert roadmap.reqs_for("P-EMPTY") == []


def test_load_missing_returns_none(tmp_path: Path):
    assert load_roadmap(tmp_path / ".kelix") is None


def test_prose_and_malformed_lines_ignored():
    text = """\
## Milestone v1 — One

garbage header that should be skipped

### Phase P1 — phase one

Not an outcome line.

- REQ-X1: first req
- not-a-req: ignored
"""
    roadmap = parse_roadmap(text)

    assert len(roadmap.reqs) == 1
    assert roadmap.reqs[0].id == "REQ-X1"
    assert roadmap.phases[0].outcome == ""


def _mini_roadmap() -> str:
    return """\
## Milestone v1 — test

### Phase P-GATE — gate

Outcome: coverage gate.

- REQ-G1: compute coverage
- REQ-G2: enforce gate
- REQ-G3: status view
"""


def _task(task_id: str, req: str, status: str = "ready") -> Task:
    return Task(id=task_id, title="t", priority=50, status=status, by="owner", req=req)


def test_coverage_all_states():
    roadmap = parse_roadmap(_mini_roadmap())
    tasks = [
        _task("PC7", "REQ-G1", "done"),
        _task("PC8", "REQ-G2", "ready"),
    ]
    result = coverage(roadmap, tasks, "P-GATE")
    by_req = {e.req_id: e.status for e in result if e.status != "warning"}

    assert by_req["REQ-G1"] == "covered"
    assert by_req["REQ-G2"] == "in-progress"
    assert by_req["REQ-G3"] == "uncovered"


def test_coverage_done_wins_over_in_progress():
    roadmap = parse_roadmap(_mini_roadmap())
    tasks = [
        _task("A", "REQ-G1", "ready"),
        _task("B", "REQ-G1", "done"),
    ]
    result = coverage(roadmap, tasks, "P-GATE")
    assert next(e for e in result if e.req_id == "REQ-G1").status == "covered"


def test_coverage_comma_separated_req():
    roadmap = parse_roadmap(_mini_roadmap())
    tasks = [_task("PC7", "REQ-G1, REQ-G2", "done")]
    result = coverage(roadmap, tasks, "P-GATE")
    by_req = {e.req_id: e.status for e in result if e.status != "warning"}

    assert by_req["REQ-G1"] == "covered"
    assert by_req["REQ-G2"] == "covered"


def test_coverage_unknown_req_warning():
    roadmap = parse_roadmap(_mini_roadmap())
    tasks = [_task("BAD", "REQ-UNKNOWN", "ready")]
    result = coverage(roadmap, tasks, "P-GATE")
    warnings = [e for e in result if e.status == "warning"]

    assert len(warnings) == 1
    assert warnings[0].req_id == "REQ-UNKNOWN"
    assert "BAD" in warnings[0].message


def test_coverage_real_p_gate():
    text = REAL_ROADMAP.read_text(encoding="utf-8")
    roadmap = parse_roadmap(text)
    from kelix.backlog import parse_backlog

    backlog = (Path(__file__).resolve().parents[1] / ".kelix" / "backlog.md").read_text(
        encoding="utf-8"
    )
    tasks = parse_backlog(backlog)
    result = coverage(roadmap, tasks, "P-GATE")
    by_req = {e.req_id: e.status for e in result if e.status != "warning"}

    assert set(by_req) == {"REQ-G1", "REQ-G2", "REQ-G3"}
    assert all(by_req[req_id] == "in-progress" for req_id in by_req)
