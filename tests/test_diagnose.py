"""Tests for ``kelix diagnose`` run selection (ST8 skeleton)."""

from pathlib import Path

import pytest

from kelix.config import load_config
from kelix.diagnose import (
    DiagnoseError,
    DiagnoseRunner,
    default_diagnosis_path,
    iteration_failed,
    select_diagnose_runs,
)
from kelix.metrics import IterationLedgerRow, save_metrics


def _write_metrics(kelix: Path, rows: list[IterationLedgerRow]) -> None:
    from kelix.metrics import LoopMetrics

    save_metrics(kelix / "memory" / "loop-metrics.json", LoopMetrics(iterations=rows))


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


def test_cmd_diagnose_prints_selection(tmp_path: Path, capsys):
    from kelix.cli import cmd_diagnose

    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    _make_run_dirs(kelix, ["20260702-040000"])
    _write_metrics(
        kelix,
        [
            IterationLedgerRow(
                run_id="20260702-040000",
                iteration=1,
                verified=False,
                failure="fail",
            ),
        ],
    )

    class Args:
        path = str(tmp_path)
        run_id = []
        last = None
        diagnosis_file = ""

    assert cmd_diagnose(Args()) == 0
    out = capsys.readouterr().out
    assert "20260702-040000" in out
    assert "diagnosis-" in out


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
