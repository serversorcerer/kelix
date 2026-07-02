"""Tests for ``kelix diagnose`` run selection and adapter iteration."""

import subprocess
from pathlib import Path

import pytest

from conftest import write_mock_script

from kelix.config import load_config
from kelix.diagnose import (
    DiagnoseError,
    DiagnoseRunner,
    default_diagnosis_path,
    iteration_failed,
    load_failed_transcripts,
    select_diagnose_runs,
    transcript_path,
    validate_diagnosis,
)
from kelix.metrics import IterationLedgerRow, save_metrics
from kelix.prompt import DIAGNOSE_TEMPLATE, assemble_diagnose_prompt


def _write_metrics(kelix: Path, rows: list[IterationLedgerRow]) -> None:
    from kelix.metrics import LoopMetrics

    save_metrics(kelix / "memory" / "loop-metrics.json", LoopMetrics(iterations=rows))


def _config(repo: Path, mock_dir: str = "mockdir") -> object:
    (repo / "kelix.toml").write_text(
        f"""
[agent]
adapter = "mock"
mock_dir = "{mock_dir}"

[git]
isolation = "none"
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


DIAGNOSE_SCRIPT = """\
mkdir -p .kelix/memory
cat > .kelix/memory/diagnosis-test.md << 'EOF'
# Kelix diagnosis

## Findings

Run **20260702-040000** / iteration **1** (task T2) failed verification.
The `[memory].context_share` budget may starve episode injection for retry-heavy tasks.

## Correlations

- Prompt slot: episodes digest truncated before relevant gotcha
- Policy: verify gate retries without fresh context
EOF
"""


def _make_run_dirs(kelix: Path, run_ids: list[str]) -> None:
    for run_id in run_ids:
        (kelix / "runs" / run_id).mkdir(parents=True)


def _fixture_rows() -> list[IterationLedgerRow]:
    """Five runs; runs 2 and 4 have failures (most recent first in dir listing)."""
    return [
        IterationLedgerRow(run_id="20260702-050000", iteration=1, task_id="T1", verified=True),
        IterationLedgerRow(
            run_id="20260702-040000",
            iteration=1,
            task_id="T2",
            verified=False,
            failure="verification failed",
        ),
        IterationLedgerRow(run_id="20260702-030000", iteration=1, task_id="T3", verified=True),
        IterationLedgerRow(
            run_id="20260702-020000",
            iteration=1,
            task_id="T4",
            verified=False,
            failure="no diff produced",
        ),
        IterationLedgerRow(run_id="20260702-010000", iteration=1, task_id="T5", verified=True),
    ]


def test_iteration_failed():
    assert iteration_failed(IterationLedgerRow(failure="x"))
    assert iteration_failed(IterationLedgerRow(verified=False))
    assert not iteration_failed(IterationLedgerRow(verified=True))
    assert not iteration_failed(IterationLedgerRow(verified=None))


def test_select_last_n_failed_runs(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    run_ids = [
        "20260702-050000",
        "20260702-040000",
        "20260702-030000",
        "20260702-020000",
        "20260702-010000",
    ]
    _make_run_dirs(kelix, run_ids)
    _write_metrics(kelix, _fixture_rows())

    cfg = load_config(tmp_path)
    selected = select_diagnose_runs(cfg, last_n=2)
    assert selected == ["20260702-040000", "20260702-020000"]


def test_select_default_run_count(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    _make_run_dirs(
        kelix,
        ["20260702-040000", "20260702-020000", "20260702-010000"],
    )
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(
                run_id="20260702-040000",
                iteration=1,
                verified=False,
                failure="fail",
            ),
            IterationLedgerRow(
                run_id="20260702-020000",
                iteration=1,
                verified=False,
                failure="fail",
            ),
            IterationLedgerRow(
                run_id="20260702-010000",
                iteration=1,
                verified=False,
                failure="fail",
            ),
        ],
    )
    cfg = load_config(tmp_path)
    assert cfg.loop.diagnose_default_runs == 3
    selected = select_diagnose_runs(cfg)
    assert len(selected) == 3


def test_select_explicit_run_ids(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    _make_run_dirs(kelix, ["20260702-010000", "20260702-030000"])
    _write_metrics(kelix, _fixture_rows())
    cfg = load_config(tmp_path)
    selected = select_diagnose_runs(cfg, run_ids=["20260702-030000", "20260702-010000"])
    assert selected == ["20260702-030000", "20260702-010000"]


def test_select_skips_runs_without_failures(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    _make_run_dirs(kelix, ["20260702-050000", "20260702-040000"])
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(run_id="20260702-050000", iteration=1, verified=True),
            IterationLedgerRow(
                run_id="20260702-040000",
                iteration=1,
                verified=False,
                failure="fail",
            ),
        ],
    )
    cfg = load_config(tmp_path)
    assert select_diagnose_runs(cfg, last_n=5) == ["20260702-040000"]


def test_prepare_scopes_failed_ledger_rows(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    _make_run_dirs(kelix, ["20260702-040000", "20260702-020000"])
    rows = _fixture_rows()
    _write_metrics(kelix, rows)
    cfg = load_config(tmp_path)

    result = DiagnoseRunner(cfg).prepare(last_n=2)
    assert result.run_ids == ["20260702-040000", "20260702-020000"]
    assert len(result.ledger_rows) == 2
    assert all(row.failure for row in result.ledger_rows)


def test_prepare_no_runs_raises(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    cfg = load_config(tmp_path)
    with pytest.raises(DiagnoseError, match="no runs selected"):
        DiagnoseRunner(cfg).prepare(last_n=3)


def test_default_diagnosis_path_under_memory(tmp_path: Path):
    cfg = load_config(tmp_path)
    path = default_diagnosis_path(cfg, timestamp="20260702-120000")
    assert path == tmp_path / ".kelix" / "memory" / "diagnosis-20260702-120000.md"


def test_cmd_diagnose_writes_diagnosis(repo, capsys):
    from kelix.cli import cmd_diagnose

    kelix = repo / ".kelix"
    run_id = "20260702-040000"
    _make_run_dirs(kelix, [run_id])
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(
                run_id=run_id,
                iteration=1,
                task_id="T2",
                verified=False,
                failure="fail",
            ),
        ],
    )
    write_mock_script(repo / "mockdir", "001.sh", DIAGNOSE_SCRIPT)
    _config(repo)

    selected_run = run_id

    class Args:
        path = str(repo)
        run_id = [selected_run]
        last = None
        diagnosis_file = ".kelix/memory/diagnosis-test.md"

    assert cmd_diagnose(Args()) == 0
    out = capsys.readouterr().out
    assert "diagnosis written" in out
    diagnosis = repo / ".kelix" / "memory" / "diagnosis-test.md"
    assert diagnosis.is_file()
    text = diagnosis.read_text(encoding="utf-8")
    assert "## Findings" in text
    assert run_id in text


def test_diagnose_runner_mock_adapter(repo):
    kelix = repo / ".kelix"
    run_id = "20260702-040000"
    _make_run_dirs(kelix, [run_id])
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(
                run_id=run_id,
                iteration=1,
                task_id="T2",
                verified=False,
                failure="verification failed",
            ),
        ],
    )
    write_mock_script(repo / "mockdir", "001.sh", DIAGNOSE_SCRIPT)
    cfg = _config(repo)

    result = DiagnoseRunner(cfg).run(
        run_ids=[run_id],
        diagnosis_file=".kelix/memory/diagnosis-test.md",
        log=lambda *_: None,
    )
    assert result.status == "completed"
    assert result.iteration is not None
    assert result.iteration.validated
    diagnosis = repo / ".kelix" / "memory" / "diagnosis-test.md"
    assert diagnosis.is_file()
    assert run_id in diagnosis.read_text(encoding="utf-8")


def test_validate_diagnosis_requires_findings_and_run_id(tmp_path):
    path = tmp_path / "d.md"
    path.write_text("# empty\n", encoding="utf-8")
    assert "Findings" in validate_diagnosis(path, ["20260702-040000"])[0]

    path.write_text("## Findings\n\nnothing cited\n", encoding="utf-8")
    assert "run_id" in validate_diagnosis(path, ["20260702-040000"])[0]

    path.write_text("## Findings\n\nRun 20260702-040000 failed.\n", encoding="utf-8")
    assert validate_diagnosis(path, ["20260702-040000"]) == []


def test_assemble_diagnose_prompt_substitutes_slots(tmp_path):
    cfg = load_config(tmp_path)
    out = assemble_diagnose_prompt(
        cfg,
        ledger_excerpt='[{"run_id": "r1"}]',
        transcripts="transcript body",
        diagnosis_path=".kelix/memory/diagnosis-test.md",
    )
    assert '[{"run_id": "r1"}]' in out
    assert "transcript body" in out
    assert ".kelix/memory/diagnosis-test.md" in out
    assert "## Findings" in out
    assert "{{" not in out


def test_diagnose_template_is_static():
    assert "{{LEDGER_EXCERPT}}" in DIAGNOSE_TEMPLATE
    assert "{{TRANSCRIPTS}}" in DIAGNOSE_TEMPLATE
    assert "{{DIAGNOSIS_PATH}}" in DIAGNOSE_TEMPLATE


def test_cmd_diagnose_prints_selection(repo, capsys):
    from kelix.cli import cmd_diagnose

    kelix = repo / ".kelix"
    run_id = "20260702-040000"
    _make_run_dirs(kelix, [run_id])
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(
                run_id=run_id,
                iteration=1,
                verified=False,
                failure="fail",
            ),
        ],
    )
    write_mock_script(repo / "mockdir", "001.sh", DIAGNOSE_SCRIPT)
    _config(repo)

    class Args:
        path = str(repo)
        run_id = []
        last = None
        diagnosis_file = ".kelix/memory/diagnosis-test.md"

    assert cmd_diagnose(Args()) == 0
    out = capsys.readouterr().out
    assert run_id in (repo / ".kelix" / "memory" / "diagnosis-test.md").read_text()
    assert "diagnosis written" in out


def test_transcript_path_matches_loop_naming(tmp_path: Path):
    cfg = load_config(tmp_path)
    path = transcript_path(cfg, "20260702-040000", 2)
    assert path == tmp_path / ".kelix" / "runs" / "20260702-040000" / "iter-002.log"


def test_load_failed_transcripts_concatenates_with_headers(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    run_id = "20260702-040000"
    run_dir = kelix / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "iter-001.log").write_text("first failure output", encoding="utf-8")
    (run_dir / "iter-002.log").write_text("second failure output", encoding="utf-8")

    rows = [
        IterationLedgerRow(
            run_id=run_id,
            iteration=1,
            task_id="ST1",
            verified=False,
            failure="fail",
        ),
        IterationLedgerRow(
            run_id=run_id,
            iteration=2,
            task_id="ST2",
            verified=False,
            failure="fail",
        ),
    ]
    cfg = load_config(tmp_path)
    text = load_failed_transcripts(cfg, [run_id], rows)

    assert "## Run 20260702-040000 / iteration 1 / task ST1" in text
    assert "first failure output" in text
    assert "## Run 20260702-040000 / iteration 2 / task ST2" in text
    assert "second failure output" in text
    assert "[... truncated" not in text


def test_load_failed_transcripts_truncates_at_budget(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    run_id = "20260702-040000"
    run_dir = kelix / "runs" / run_id
    run_dir.mkdir(parents=True)

    rows: list[IterationLedgerRow] = []
    for i in range(1, 4):
        (run_dir / f"iter-{i:03d}.log").write_text("x" * 200, encoding="utf-8")
        rows.append(
            IterationLedgerRow(
                run_id=run_id,
                iteration=i,
                task_id=f"T{i}",
                verified=False,
                failure="fail",
            )
        )

    cfg = load_config(tmp_path)
    cfg.loop.diagnose_transcript_chars = 500
    text = load_failed_transcripts(cfg, [run_id], rows)

    assert "[... truncated to 500 chars]" in text
    assert text.index("[... truncated to 500 chars]") > 0


def test_load_failed_transcripts_skips_missing_files(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    run_id = "20260702-040000"
    run_dir = kelix / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "iter-001.log").write_text("present", encoding="utf-8")

    rows = [
        IterationLedgerRow(
            run_id=run_id,
            iteration=1,
            task_id="T1",
            verified=False,
            failure="fail",
        ),
        IterationLedgerRow(
            run_id=run_id,
            iteration=2,
            task_id="T2",
            verified=False,
            failure="fail",
        ),
    ]
    cfg = load_config(tmp_path)
    text = load_failed_transcripts(cfg, [run_id], rows)

    assert "present" in text
    assert "iteration 2" not in text


def test_loop_does_not_import_diagnose():
    import ast
    from pathlib import Path

    loop_src = Path(__file__).resolve().parents[1] / "src" / "kelix" / "loop.py"
    tree = ast.parse(loop_src.read_text(encoding="utf-8"))
    imports = {
        node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and "diagnose" in node.module
    }
    assert not imports
