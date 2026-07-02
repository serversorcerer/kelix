from kalph.backlog import Task, parse_backlog, select_next, serialize_backlog

SAMPLE_BACKLOG = """\
# Kalph backlog

Task line format (one per task, keep it exactly parseable):
`- [ ] ID: title | priority: N | status: ready|done|blocked|proposed | by: owner|kalph`

## Tasks

- [ ] KB1: backlog parser module | priority: 90 | status: ready | by: owner
  rationale: the runner needs structured backlog access
  details: create src/kalph/backlog.py
- [ ] KB2: memory module tests | priority: 80 | status: ready | by: owner | deps: KB1
- [ ] P1: polish docs | priority: 95 | status: ready | by: kalph
- [x] DONE1: finished task | priority: 10 | status: done | by: owner
"""


def test_parse_sample_backlog():
    tasks = parse_backlog(SAMPLE_BACKLOG)
    assert len(tasks) == 4

    kb1 = tasks[0]
    assert kb1.id == "KB1"
    assert kb1.title == "backlog parser module"
    assert kb1.priority == 90
    assert kb1.status == "ready"
    assert kb1.by == "owner"
    assert kb1.deps == []
    assert kb1.notes == {
        "rationale": "the runner needs structured backlog access",
        "details": "create src/kalph/backlog.py",
    }

    kb2 = tasks[1]
    assert kb2.deps == ["KB1"]

    done = tasks[3]
    assert done.status == "done"


def test_round_trip():
    tasks = parse_backlog(SAMPLE_BACKLOG)
    again = parse_backlog(serialize_backlog(tasks))
    assert again == tasks


def test_select_next_priority_and_owner():
    tasks = parse_backlog(SAMPLE_BACKLOG)
    assert select_next(tasks).id == "KB1"

    blocked = [
        Task("A", "owner high", 50, "ready", "owner"),
        Task("B", "kalph higher", 99, "ready", "kalph"),
    ]
    assert select_next(blocked).id == "A"


def test_select_next_respects_dependencies():
    tasks = [
        Task("A", "first", 90, "ready", "owner"),
        Task("B", "blocked by A", 80, "ready", "owner", deps=["A"]),
        Task("C", "also blocked", 70, "ready", "owner", deps=["A"]),
    ]
    assert select_next(tasks).id == "A"

    tasks[0].status = "done"
    assert select_next(tasks).id == "B"


def test_select_next_skips_non_ready():
    tasks = [
        Task("A", "done", 90, "done", "owner"),
        Task("B", "blocked", 80, "blocked", "owner"),
        Task("C", "proposed", 70, "proposed", "kalph"),
    ]
    assert select_next(tasks) is None


def test_select_next_normal_autonomy_skips_proposed():
    tasks = [
        Task("A", "done", 90, "done", "owner"),
        Task("B", "proposed only", 99, "proposed", "kalph"),
    ]
    assert select_next(tasks, autonomy="normal") is None
    assert select_next(tasks) is None


def test_select_next_high_autonomy_selects_proposed():
    tasks = [
        Task("A", "done", 90, "done", "owner"),
        Task("B", "proposed work", 60, "proposed", "kalph"),
    ]
    assert select_next(tasks, autonomy="high").id == "B"


def test_select_next_high_autonomy_owner_ready_beats_proposed():
    tasks = [
        Task("A", "owner ready", 50, "ready", "owner"),
        Task("B", "owner proposed", 99, "proposed", "owner"),
        Task("C", "kalph proposed", 95, "proposed", "kalph"),
    ]
    assert select_next(tasks, autonomy="high").id == "A"


def test_select_next_high_autonomy_owner_beats_kalph_proposed():
    tasks = [
        Task("A", "owner proposed", 40, "proposed", "owner"),
        Task("B", "kalph proposed", 99, "proposed", "kalph"),
    ]
    assert select_next(tasks, autonomy="high").id == "A"


def test_malformed_lines_are_skipped():
    text = """\
# header

not a task line at all
- [ ] GOOD: ok task | priority: 1 | status: ready | by: owner
- broken task line
- [ ] ALSO: fine | priority: 2 | status: ready | by: owner
"""
    tasks = parse_backlog(text)
    assert [task.id for task in tasks] == ["GOOD", "ALSO"]
    assert select_next(tasks).id == "ALSO"


def test_serialize_includes_notes_and_deps():
    task = Task(
        "T1",
        "demo",
        50,
        "ready",
        "owner",
        deps=["X", "Y"],
        notes={"rationale": "because", "diagnosis": "n/a"},
    )
    text = serialize_backlog([task])
    assert "deps: X,Y" in text
    assert "  rationale: because" in text
    assert "  diagnosis: n/a" in text
    assert "  details:" not in text


def test_parse_phase_and_req_any_order():
    text = """\
- [ ] A: with phase first | priority: 10 | status: ready | by: owner | phase: P-SPINE | req: REQ-S1
- [ ] B: with req first | priority: 20 | status: ready | by: owner | req: REQ-I1 | phase: P-INTENT
- [ ] C: phase only | priority: 30 | status: ready | by: owner | phase: P-GATE
"""
    tasks = parse_backlog(text)
    assert tasks[0].phase == "P-SPINE"
    assert tasks[0].req == "REQ-S1"
    assert tasks[1].phase == "P-INTENT"
    assert tasks[1].req == "REQ-I1"
    assert tasks[2].phase == "P-GATE"
    assert tasks[2].req == ""


def test_round_trip_with_phase_and_req():
    tasks = [
        Task(
            "PC5",
            "link tasks",
            88,
            "ready",
            "owner",
            deps=["PC4"],
            phase="P-INTENT",
            req="REQ-I3",
        ),
        Task("LEG", "legacy line", 50, "ready", "owner"),
    ]
    again = parse_backlog(serialize_backlog(tasks))
    assert again == tasks


def test_legacy_lines_unchanged():
    tasks = parse_backlog(SAMPLE_BACKLOG)
    kb1 = tasks[0]
    assert kb1.phase == ""
    assert kb1.req == ""
    assert kb1.deps == []


def test_select_next_prefers_active_phase():
    tasks = [
        Task("A", "other phase high", 99, "ready", "owner", phase="P-ONRAMP"),
        Task("B", "active phase lower", 50, "ready", "owner", phase="P-INTENT"),
        Task("C", "phaseless middle", 80, "ready", "owner"),
    ]
    assert select_next(tasks, active_phase="P-INTENT").id == "B"
    assert select_next(tasks, active_phase="P-INTENT").id != "A"


def test_select_next_active_phase_ordering():
    tasks = [
        Task("A", "other phase", 99, "ready", "owner", phase="P-ONRAMP"),
        Task("B", "phaseless", 90, "ready", "owner"),
        Task("C", "active low priority", 10, "ready", "owner", phase="P-INTENT"),
        Task("D", "active high priority", 95, "ready", "owner", phase="P-INTENT"),
    ]
    picked = select_next(tasks, active_phase="P-INTENT")
    assert picked.id == "D"

    without_phase = select_next(tasks)
    assert without_phase.id == "A"


def test_select_next_active_phase_owner_still_wins():
    tasks = [
        Task("A", "kalph active phase", 99, "ready", "kalph", phase="P-INTENT"),
        Task("B", "owner other phase", 10, "ready", "owner", phase="P-ONRAMP"),
    ]
    assert select_next(tasks, active_phase="P-INTENT").id == "B"
