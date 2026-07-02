import json
from pathlib import Path

from kelix.metrics import (
    FleetSummaryRow,
    IterationLedgerRow,
    LoopMetrics,
    ProposalOutcome,
    append_run_metrics,
    empty_metrics,
    load_metrics,
    metrics_to_dict,
    save_metrics,
)


def _sample_metrics() -> LoopMetrics:
    return LoopMetrics(
        schema_version=1,
        iterations=[
            IterationLedgerRow(
                run_id="20260702-120000",
                iteration=1,
                task_id="ST1",
                verified=True,
                retry_count=0,
                duration_s=12.5,
                failure="",
                circuit_breaker_cause="",
                agent_id="solo",
                fleet_id="",
                backlog_lint={"missing-details": 2},
                skills_injected=["foo"],
                tokens=None,
            ),
            IterationLedgerRow(
                run_id="20260702-120000",
                iteration=2,
                task_id="ST2",
                verified=False,
                retry_count=1,
                duration_s=8.0,
                failure="pytest failed",
                agent_id="solo",
            ),
        ],
        fleet_summaries=[
            FleetSummaryRow(
                fleet_id="fleet-a",
                run_ids=["20260702-120000", "20260702-130000"],
                verified_rate=0.75,
                iteration_count=4,
                breaker_trips=1,
            )
        ],
        proposal_outcomes=[
            ProposalOutcome(
                proposal_id="prop-1",
                merge_sha="abc123",
                prediction="fewer retries",
                grade="improved",
            )
        ],
    )


def test_save_load_round_trip(tmp_path: Path):
    path = tmp_path / "loop-metrics.json"
    original = _sample_metrics()
    save_metrics(path, original)
    loaded = load_metrics(path)
    assert loaded == original


def test_metrics_to_dict_tokens_null_on_rows():
    metrics = LoopMetrics(
        iterations=[IterationLedgerRow(run_id="r1", iteration=1, task_id="T1")]
    )
    payload = metrics_to_dict(metrics)
    assert payload["iterations"][0]["tokens"] is None


def test_load_missing_returns_empty(tmp_path: Path):
    loaded = load_metrics(tmp_path / "missing.json")
    assert loaded == empty_metrics()
    assert loaded.schema_version == 1
    assert loaded.iterations == []
    assert loaded.fleet_summaries == []
    assert loaded.proposal_outcomes == []


def test_load_corrupt_json_returns_empty(tmp_path: Path):
    path = tmp_path / "loop-metrics.json"
    path.write_text("{ not valid json\n", encoding="utf-8")
    assert load_metrics(path) == empty_metrics()


def test_load_corrupt_entries_skipped(tmp_path: Path):
    path = tmp_path / "loop-metrics.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "iterations": [
                    {"run_id": "r1", "iteration": 1, "task_id": "ST1", "verified": True},
                    "not a row",
                    {"run_id": "r1", "iteration": 2, "task_id": "ST2", "verified": False},
                ],
                "fleet_summaries": ["bad"],
                "proposal_outcomes": [None, {"proposal_id": "p1", "grade": "inconclusive"}],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_metrics(path)
    assert len(loaded.iterations) == 2
    assert loaded.iterations[0].task_id == "ST1"
    assert loaded.iterations[1].task_id == "ST2"
    assert loaded.fleet_summaries == []
    assert len(loaded.proposal_outcomes) == 1
    assert loaded.proposal_outcomes[0].proposal_id == "p1"


def test_save_writes_indented_json(tmp_path: Path):
    path = tmp_path / "loop-metrics.json"
    save_metrics(path, _sample_metrics())
    text = path.read_text(encoding="utf-8")
    assert "\n  " in text
    parsed = json.loads(text)
    assert parsed["iterations"][0]["tokens"] is None


def test_append_run_metrics_merges_rows(tmp_path: Path):
    from kelix.config import Config

    cfg = Config(root=tmp_path)
    path = tmp_path / ".kelix" / "memory" / "loop-metrics.json"
    save_metrics(
        path,
        LoopMetrics(iterations=[IterationLedgerRow(run_id="r0", iteration=1, task_id="T0")]),
    )
    rows = [
        IterationLedgerRow(run_id="r1", iteration=1, task_id="T1", verified=True),
        IterationLedgerRow(run_id="r1", iteration=2, task_id="T2", verified=False),
    ]
    fleet = FleetSummaryRow(fleet_id="fleet-a", run_ids=["r1"], verified_rate=0.5)
    append_run_metrics(cfg, rows, fleet_summary=fleet)
    loaded = load_metrics(path)
    assert len(loaded.iterations) == 3
    assert loaded.iterations[-2].task_id == "T1"
    assert loaded.iterations[-1].task_id == "T2"
    assert len(loaded.fleet_summaries) == 1
    assert loaded.fleet_summaries[0].fleet_id == "fleet-a"
