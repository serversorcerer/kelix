"""Tests for backlog lint and ``kelix lint``."""

from pathlib import Path

from kelix.backlog import Task
from kelix.cli import cmd_lint
from kelix.lint import Finding, format_finding, lint_backlog, lint_repo


def _task(**kwargs) -> Task:
    defaults = {
        "id": "T1",
        "title": "demo task",
        "priority": 50,
        "status": "ready",
        "by": "owner",
    }
    defaults.update(kwargs)
    notes = defaults.pop("notes", {})
    task = Task(**defaults)
    task.notes = notes
    return task


def test_format_finding_includes_task_id():
    assert format_finding(Finding("T1", "missing_details", "no details")) == (
        "T1: missing_details: no details"
    )
    assert format_finding(Finding("", "backlog_missing", "missing file")) == (
        "backlog_missing: missing file"
    )


def test_missing_details():
    findings = lint_backlog([_task(notes={"rationale": "why"})])
    assert any(f.rule == "missing_details" for f in findings)


def test_no_acceptance_signal():
    findings = lint_backlog(
        [_task(notes={"details": "make the module nicer and refactor things"})]
    )
    assert any(f.rule == "no_acceptance_signal" for f in findings)


def test_acceptance_signal_from_test_path():
    findings = lint_backlog(
        [
            _task(
                notes={
                    "details": "add src/kelix/foo.py; round-trip test in tests/test_foo.py"
                }
            )
        ]
    )
    assert not any(f.rule == "no_acceptance_signal" for f in findings)


def test_unfalsifiable_wording():
    findings = lint_backlog([_task(notes={"details": "improve the CLI experience"})])
    rules = {f.rule for f in findings}
    assert "unfalsifiable_wording" in rules


def test_unfalsifiable_wording_allowed_with_metric():
    findings = lint_backlog(
        [
            _task(
                notes={
                    "details": "improve CLI startup to under 100ms; assert in tests/test_cli.py"
                }
            )
        ]
    )
    assert not any(f.rule == "unfalsifiable_wording" for f in findings)


def test_unfalsifiable_wording_ignores_parenthetical_examples():
    findings = lint_backlog(
        [
            _task(
                notes={
                    "details": (
                        "flag banned words (improve/better/best practices/clean up); "
                        "tests in tests/test_lint.py"
                    )
                }
            )
        ]
    )
    assert not any(f.rule == "unfalsifiable_wording" for f in findings)


def test_multiple_deliverables():
    findings = lint_backlog(
        [_task(notes={"details": "add foo.py and then add bar.py; tests/test_x.py"})]
    )
    assert any(f.rule == "multiple_deliverables" for f in findings)


def test_title_too_long():
    findings = lint_backlog([_task(title="x" * 81, notes={"details": "tests/test_x.py"})])
    assert any(f.rule == "title_too_long" for f in findings)


def test_dangling_dep():
    findings = lint_backlog(
        [
            _task(
                id="A",
                deps=["MISSING"],
                notes={"details": "tests/test_a.py"},
            )
        ]
    )
    assert any(f.rule == "dangling_dep" for f in findings)


def test_cyclic_deps():
    findings = lint_backlog(
        [
            _task(id="A", deps=["B"], notes={"details": "tests/test_a.py"}),
            _task(id="B", deps=["A"], notes={"details": "tests/test_b.py"}),
        ]
    )
    assert any(f.rule == "cyclic_deps" for f in findings)


def test_done_tasks_skipped_for_slop_rules():
    findings = lint_backlog(
        [
            Task("OLD", "legacy", 10, "done", "owner"),
            _task(id="NEW", notes={"details": "tests/test_new.py"}),
        ]
    )
    assert not any(f.task_id == "OLD" for f in findings)


def test_real_backlog_is_clean():
    root = Path(__file__).resolve().parents[1]
    findings = lint_repo(root)
    assert findings == [], "\n".join(format_finding(f) for f in findings)


def test_cmd_lint_clean_on_repo(repo):
    (repo / ".kelix" / "backlog.md").write_text(
        "- [ ] T1: good task | priority: 50 | status: ready | by: owner\n"
        "  details: add foo.py; assert True in tests/test_foo.py\n"
    )

    class Args:
        path = str(repo)

    assert cmd_lint(Args()) == 0


def test_cmd_lint_reports_findings(repo, capsys):
    (repo / ".kelix" / "backlog.md").write_text(
        "- [ ] T1: bad task | priority: 50 | status: ready | by: owner\n"
        "  details: improve everything\n"
    )

    class Args:
        path = str(repo)

    assert cmd_lint(Args()) == 1
    err = capsys.readouterr().err
    assert "lint:" in err
    assert "no_acceptance_signal" in err or "unfalsifiable_wording" in err


def test_validate_plan_includes_lint_rules(repo):
    from kelix.lint import validate_plan

    (repo / ".kelix" / "roadmap.md").write_text(
        "# Roadmap\n\n"
        "## Milestone M1 — Demo\n\n"
        "### Phase P1 — phase\n\n"
        "- REQ-R1: requirement one\n"
    )
    (repo / ".kelix" / "backlog.md").write_text(
        "- [ ] T1: slop | priority: 50 | status: proposed | by: kelix | req: REQ-R1\n"
        "  details: make it better\n"
    )
    findings = validate_plan(repo)
    rules = {f.rule for f in findings}
    assert "no_acceptance_signal" in rules or "unfalsifiable_wording" in rules
