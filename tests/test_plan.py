"""Tests for ``kelix plan`` — interview, one-iteration planning, validation."""

import json
import subprocess

from conftest import write_mock_script

from kelix.cli import cmd_plan
from kelix.config import load_config
from kelix.plan import (
    PlanRunner,
    extract_goal_phases,
    is_acceptance_probe_question,
    load_questions_md,
    parse_questions_block,
    planning_phase_slug,
    present_questions_tty,
    questions_answered,
    validate_interview_questions,
    write_questions_file,
)
from kelix.prompt import (
    PLAN_COMPLETE_SENTINEL,
    PLANNING_INTERVIEW_TEMPLATE,
    PLANNING_TEMPLATE,
    assemble_planning_interview_prompt,
    assemble_planning_prompt,
)


def _config(repo, mock_dir="mockdir", isolation="none"):
    (repo / "kelix.toml").write_text(
        f"""
[agent]
adapter = "mock"
mock_dir = "{mock_dir}"

[git]
isolation = "{isolation}"
"""
    )
    subprocess.run(["git", "add", "kelix.toml"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add kelix config"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    return load_config(repo)


def _git_out(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    ).stdout


INTERVIEW_SCRIPT = """\
cat << 'EOF'
```QUESTIONS
Q1: Demo scope
What should the demo cover?
1. Minimal API (recommended)
2. Full stack
Q2: Test style
How should we verify?
1. pytest unit tests (recommended)
2. manual checklist
```
EOF
"""

PLAN_SCRIPT = """\
cat > .kelix/roadmap.md << 'EOF'
# Roadmap

## Milestone M1 — Demo milestone

### Phase P-DEMO — demo phase
Outcome: demo works.

- REQ-D1: first requirement
EOF

cat >> .kelix/backlog.md << 'EOF'
- [ ] T10: demo task | priority: 50 | status: proposed | by: kelix | phase: P-DEMO | req: REQ-D1
  details: assert True in tests/test_demo.py
EOF
git add .kelix/roadmap.md .kelix/backlog.md && git commit -q -m "plan: draft demo"
echo "PLAN COMPLETE"
"""


def _install_plan_scripts(repo, mock_dir="mockdir"):
    write_mock_script(repo / mock_dir, "001.sh", INTERVIEW_SCRIPT)
    write_mock_script(repo / mock_dir, "002.sh", PLAN_SCRIPT)


def _seed_answered_interview(repo, goal: str):
    from kelix.plan import PlanOption, PlanQuestion, write_interview_context

    questions = [
        PlanQuestion(
            qid="Q1",
            title="Demo scope",
            text="What should the demo cover?",
            options=[
                PlanOption(1, "Minimal API", recommended=True),
                PlanOption(2, "Full stack"),
            ],
            answer="Minimal API",
        )
    ]
    phase_dir = repo / ".kelix" / "phases" / planning_phase_slug(goal)
    write_questions_file(phase_dir / "QUESTIONS.md", questions)
    write_interview_context(phase_dir / "CONTEXT.md", questions)


def test_planning_prompt_includes_goal(tmp_path):
    cfg = load_config(tmp_path)
    out = assemble_planning_prompt(cfg, goal="build a widget tracker")
    assert "build a widget tracker" in out
    assert PLAN_COMPLETE_SENTINEL in out
    assert "{{" not in out


def test_planning_interview_prompt_emits_questions_only(tmp_path):
    cfg = load_config(tmp_path)
    out = assemble_planning_interview_prompt(cfg, goal="build widgets")
    assert "build widgets" in out
    assert "```QUESTIONS" in out
    assert "Do NOT print PLAN COMPLETE" in out
    assert "acceptance-criteria probe" in out
    assert "acceptance probe" in out.lower()
    assert "{{" not in out


def test_planning_interview_prompt_lists_goal_phases(tmp_path):
    cfg = load_config(tmp_path)
    goal = (
        "## Milestone M1 — demo\n\n"
        "### Phase P-AUTH — auth\n\n"
        "### Phase P-DATA — data\n"
    )
    out = assemble_planning_interview_prompt(cfg, goal=goal)
    assert "P-AUTH" in out
    assert "P-DATA" in out
    assert "at least 2 acceptance probe" in out


def test_extract_goal_phases():
    goal = "### Phase P-A — first\n\n### Phase P-B — second\n"
    assert extract_goal_phases(goal) == ["P-A", "P-B"]


def test_is_acceptance_probe_question():
    verify_q = parse_questions_block(
        "```QUESTIONS\nQ1: Verify auth\nHow will we prove login works?\n"
        "1. pytest in tests/test_auth.py (recommended)\n2. manual\n```"
    )[0]
    scope_q = parse_questions_block(
        "```QUESTIONS\nQ1: Demo scope\nWhat should the demo cover?\n"
        "1. Minimal API (recommended)\n2. Full stack\n```"
    )[0]
    assert is_acceptance_probe_question(verify_q)
    assert not is_acceptance_probe_question(scope_q)


def test_validate_interview_questions_requires_probe_per_phase():
    goal = "### Phase P-A — first\n\n### Phase P-DATA — data\n"
    one_probe = parse_questions_block(
        "```QUESTIONS\n"
        "Q1: P-A acceptance\nHow verify auth with pytest?\n"
        "1. tests/test_auth.py (recommended)\n2. manual\n"
        "Q2: Scope\nWhat ships?\n1. API (recommended)\n2. UI\n"
        "```"
    )
    assert validate_interview_questions(goal, one_probe)
    two_probes = parse_questions_block(
        "```QUESTIONS\n"
        "Q1: P-A acceptance\nHow verify auth with pytest?\n"
        "1. tests/test_auth.py (recommended)\n2. manual\n"
        "Q2: P-DATA acceptance\nWhat test proves persistence?\n"
        "1. round-trip in tests/test_data.py (recommended)\n2. manual\n"
        "```"
    )
    assert not validate_interview_questions(goal, two_probes)


TWO_PHASE_GOAL = """\
build two-phase widget tracker

## Milestone M1 — Widgets

### Phase P-AUTH — authentication
Outcome: users can sign in.

### Phase P-DATA — persistence
Outcome: widgets survive reload.
"""

TWO_PHASE_INTERVIEW_SCRIPT = """\
cat << 'EOF'
```QUESTIONS
Q1: P-AUTH acceptance
How will we verify authentication works?
1. pytest in tests/test_auth.py (recommended)
2. manual login checklist
Q2: P-DATA acceptance
How will we prove persistence round-trips?
1. save/load test in tests/test_data.py (recommended)
2. sqlite browser inspection
Q3: Widget scope
What is the first widget feature?
1. create/list only (recommended)
2. full CRUD
```
EOF
"""


def test_plan_interview_two_phases_requires_acceptance_probes(repo):
    write_mock_script(repo / "mockdir", "001.sh", TWO_PHASE_INTERVIEW_SCRIPT)
    cfg = _config(repo)
    result = PlanRunner(cfg).run(
        goal=TWO_PHASE_GOAL,
        log=lambda *_: None,
        is_tty=False,
    )
    assert result.status == "awaiting_answers"
    questions = load_questions_md(
        repo / ".kelix" / "phases" / planning_phase_slug(TWO_PHASE_GOAL) / "QUESTIONS.md"
    )
    acceptance_questions = [q for q in questions if is_acceptance_probe_question(q)]
    assert len(acceptance_questions) >= 2


def test_planning_template_is_static():
    assert "{{GOAL}}" in PLANNING_TEMPLATE
    assert "status: proposed" in PLANNING_TEMPLATE
    assert "```QUESTIONS" in PLANNING_INTERVIEW_TEMPLATE


def test_parse_questions_block():
    text = """
Here are my questions:

```QUESTIONS
Q1: Database
Which persistence?
1. SQLite (recommended)
2. Postgres
Q2: Auth
How do users sign in?
1. API keys (recommended)
2. OAuth
3. None yet
```
"""
    questions = parse_questions_block(text)
    assert len(questions) == 2
    assert questions[0].qid == "Q1"
    assert questions[0].recommended_index == 1
    assert questions[1].options[2].text == "None yet"


def test_questions_md_round_trip(tmp_path):
    questions = parse_questions_block(INTERVIEW_SCRIPT)
    path = tmp_path / "QUESTIONS.md"
    write_questions_file(path, questions)
    loaded = load_questions_md(path)
    assert len(loaded) == 2
    assert not questions_answered(loaded)
    loaded[0].answer = "Minimal API"
    loaded[1].answer = "pytest unit tests"
    assert questions_answered(loaded)


def test_present_questions_tty_uses_recommendation_default():
    questions = parse_questions_block(INTERVIEW_SCRIPT)
    inputs = iter(["", "2"])

    def fake_input(_prompt):
        return next(inputs)

    answered = present_questions_tty(questions, input_fn=fake_input, print_fn=lambda *_: None)
    assert answered[0].answer == "Minimal API"
    assert answered[1].answer == "manual checklist"


def test_plan_tty_interview_then_draft(repo):
    _install_plan_scripts(repo)
    cfg = _config(repo)
    inputs = iter(["", ""])
    result = PlanRunner(cfg).run(
        goal="build a demo",
        log=lambda *_: None,
        is_tty=True,
        input_fn=lambda _: next(inputs),
    )
    assert result.status == "completed"
    assert (repo / ".kelix" / "roadmap.md").exists()
    context = (repo / ".kelix" / "phases" / planning_phase_slug("build a demo") / "CONTEXT.md")
    assert "Decisions from planning interview" in context.read_text()


def test_plan_file_interview_then_resume(repo):
    write_mock_script(repo / "mockdir", "001.sh", INTERVIEW_SCRIPT)
    write_mock_script(repo / "mockdir", "002.sh", PLAN_SCRIPT)
    cfg = _config(repo)
    result = PlanRunner(cfg).run(goal="build a demo", log=lambda *_: None, is_tty=False)
    assert result.status == "awaiting_answers"
    qpath = repo / ".kelix" / "phases" / planning_phase_slug("build a demo") / "QUESTIONS.md"
    assert qpath.is_file()
    answered = load_questions_md(qpath)
    answered[0].answer = "Minimal API"
    answered[1].answer = "pytest unit tests"
    write_questions_file(qpath, answered)
    write_mock_script(repo / "mockdir", "001.sh", PLAN_SCRIPT)
    result2 = PlanRunner(cfg).run(goal="build a demo", log=lambda *_: None, is_tty=False)
    assert result2.status == "completed"
    assert (repo / ".kelix" / "roadmap.md").exists()


def test_plan_happy_path_writes_draft(repo):
    _seed_answered_interview(repo, "build a demo")
    write_mock_script(repo / "mockdir", "001.sh", PLAN_SCRIPT)
    cfg = _config(repo)
    result = PlanRunner(cfg).run(goal="build a demo", log=lambda *_: None)
    assert result.status == "completed"
    assert result.iteration is not None
    assert result.iteration.plan_complete
    assert result.iteration.validated

    roadmap = (repo / ".kelix" / "roadmap.md").read_text()
    assert "## Milestone M1" in roadmap
    assert "REQ-D1" in roadmap

    from kelix.backlog import parse_backlog

    tasks = parse_backlog((repo / ".kelix" / "backlog.md").read_text())
    new_tasks = [t for t in tasks if t.id == "T10"]
    assert len(new_tasks) == 1
    assert new_tasks[0].status == "proposed"
    assert new_tasks[0].by == "kelix"

    run_dir = cfg.kelix_dir / "runs" / f"plan-{result.run_id}"
    assert (run_dir / "iter-001.log").exists()
    assert json.loads((run_dir / "plan.json").read_text())["status"] == "completed"


def test_plan_rejects_non_planning_changes(repo):
    bad = PLAN_SCRIPT.replace(
        "git add .kelix/roadmap.md .kelix/backlog.md",
        "echo oops > src.txt && git add .kelix/roadmap.md .kelix/backlog.md src.txt",
    )
    _seed_answered_interview(repo, "build a demo")
    write_mock_script(repo / "mockdir", "001.sh", bad)
    cfg = _config(repo)
    result = PlanRunner(cfg).run(goal="build a demo", log=lambda *_: None)
    assert result.status == "validation_failed"
    assert any("non_planning_change" in f for f in result.findings)


def test_plan_worktree_leaves_main_untouched(repo):
    _seed_answered_interview(repo, "build a demo")
    write_mock_script(repo / "mockdir", "001.sh", PLAN_SCRIPT)
    cfg = _config(repo, isolation="worktree")
    main_sha = _git_out(repo, "rev-parse", "main").strip()
    result = PlanRunner(cfg).run(goal="build a demo", log=lambda *_: None)
    assert result.status == "completed"
    assert _git_out(repo, "rev-parse", "main").strip() == main_sha
    assert not (repo / ".kelix" / "roadmap.md").exists()


def test_cmd_plan_goal_file(repo):
    _seed_answered_interview(repo, "build from file\n")
    write_mock_script(repo / "mockdir", "001.sh", PLAN_SCRIPT)
    _config(repo)
    goal_path = repo / "GOAL.md"
    goal_path.write_text("build from file\n")

    class Args:
        path = str(repo)
        goal = ""
        goal_file = str(goal_path)

    assert cmd_plan(Args()) == 0


def test_cmd_plan_goal_string(repo):
    _seed_answered_interview(repo, "inline goal")
    write_mock_script(repo / "mockdir", "001.sh", PLAN_SCRIPT)
    _config(repo)

    class Args:
        path = str(repo)
        goal = "inline goal"
        goal_file = ""

    assert cmd_plan(Args()) == 0
