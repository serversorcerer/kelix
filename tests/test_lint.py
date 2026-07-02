"""Tests for backlog lint and ``kelix lint``."""

from pathlib import Path

from kelix.backlog import Task
from kelix.cli import cmd_lint
from kelix.lint import (
    Finding,
    finding_fix,
    format_actionable_finding,
    format_finding,
    lint_backlog,
    lint_repo,
)


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


def test_finding_fix_per_rule():
    assert finding_fix(Finding("T1", "missing_details", "")) == (
        "add details: with a test path"
    )
    assert finding_fix(
        Finding("T1", "unfalsifiable_wording", "details use 'improve' without a metric")
    ) == "remove unfalsifiable word improve in details"


def test_format_actionable_finding_includes_fix():
    text = format_actionable_finding(
        Finding("T1", "missing_details", "task has no details: note with testable acceptance")
    )
    assert "T1: missing_details:" in text
    assert "  fix: add details: with a test path" in text


def test_lint_slop_fixture_actionable_findings(capsys):
    """Every finding on a slop backlog includes task id, rule, and fix (REQ-VS4)."""
    findings = lint_backlog(
        [
            _task(
                id="SLOP",
                notes={"details": "improve everything"},
            ),
            _task(
                id="NODET",
                notes={"rationale": "why"},
            ),
        ],
        scope="ready",
    )
    assert findings
    for finding in findings:
        block = format_actionable_finding(finding)
        assert finding.task_id in block
        assert finding.rule in block
        assert "  fix:" in block
        assert finding_fix(finding) in block


def test_lint_ready_scope_ignores_proposed():
    findings = lint_backlog(
        [
            _task(
                id="READY",
                notes={"details": "improve everything"},
            ),
            _task(
                id="PROP",
                status="proposed",
                by="kelix",
                notes={"details": "improve everything"},
            ),
        ],
        scope="ready",
    )
    assert all(f.task_id == "READY" for f in findings)
    assert len(findings) >= 1


def test_format_spec_gate_findings_includes_examples():
    from kelix.lint import INPUT_QUALITY_TAGLINE, format_spec_gate_findings

    lines = format_spec_gate_findings(
        [Finding("T1", "missing_details", "task has no details: note with testable acceptance")]
    )
    text = "\n".join(lines)
    assert "spec gate:" in text
    assert text.count(INPUT_QUALITY_TAGLINE) == 1
    assert "bad:" in text
    assert "good:" in text
    assert "T1:" in text
    assert "  fix:" in text


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
    assert "  fix:" in err
    assert "remove unfalsifiable word improve in details" in err or (
        "add a test path" in err
    )
    assert err.count("Gold in, diamonds out.") == 1


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


def test_kelix_proposed_edits_detects_new_and_changed():
    from kelix.lint import kelix_proposed_edits

    before = [
        _task(id="K1", by="kelix", status="proposed", notes={"details": "tests/test_x.py"}),
        _task(id="K2", by="kelix", status="proposed", notes={"details": "unchanged"}),
        _task(id="O1", by="owner", status="ready", notes={"details": "tests/test_y.py"}),
    ]
    after = [
        _task(id="K1", by="kelix", status="proposed", notes={"details": "tests/test_x.py"}),
        _task(
            id="K2",
            by="kelix",
            status="proposed",
            notes={"details": "changed acceptance in tests/test_z.py"},
        ),
        _task(id="K3", by="kelix", status="proposed", notes={"details": "tests/test_new.py"}),
        _task(id="O1", by="owner", status="ready", notes={"details": "owner edit"}),
    ]
    edited_ids = {t.id for t in kelix_proposed_edits(before, after)}
    assert edited_ids == {"K2", "K3"}


def test_lint_backlog_edits_missing_details():
    from kelix.lint import lint_backlog_edits

    before = [_task(id="T1", by="owner", status="ready", notes={"details": "tests/test_a.py"})]
    after = before + [
        _task(id="KX1", by="kelix", status="proposed", notes={"rationale": "why not"}),
    ]
    counts = lint_backlog_edits(before, after)
    assert counts.get("missing_details", 0) >= 1
