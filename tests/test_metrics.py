import json
from pathlib import Path

from kelix.metrics import (
    FleetSummaryRow,
    IterationLedgerRow,
    LoopMetrics,
    ProposalOutcome,
    SkillEfficacyEntry,
    append_run_metrics,
    compute_skill_efficacy,
    empty_metrics,
    grade_proposal,
    load_metrics,
    metrics_to_dict,
    record_proposal_outcome,
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


def test_compute_skill_efficacy_with_beats_without():
    rows = [
        IterationLedgerRow(
            run_id="r1",
            iteration=1,
            task_id="T1",
            verified=True,
            skills_injected=["foo"],
        ),
        IterationLedgerRow(
            run_id="r1",
            iteration=2,
            task_id="T2",
            verified=True,
            skills_injected=["foo"],
        ),
        IterationLedgerRow(
            run_id="r1",
            iteration=3,
            task_id="T3",
            verified=False,
            skills_injected=[],
        ),
        IterationLedgerRow(
            run_id="r1",
            iteration=4,
            task_id="T4",
            verified=False,
            skills_injected=[],
        ),
    ]
    efficacy = compute_skill_efficacy(rows)
    assert efficacy["foo"] == SkillEfficacyEntry(
        with_rate=1.0,
        without_rate=0.0,
        matched_tasks=4,
    )


def test_append_run_metrics_updates_skill_efficacy(tmp_path: Path):
    from kelix.config import Config

    cfg = Config(root=tmp_path)
    rows = [
        IterationLedgerRow(
            run_id="r1",
            iteration=1,
            task_id="T1",
            verified=True,
            skills_injected=["foo"],
        ),
        IterationLedgerRow(
            run_id="r1",
            iteration=2,
            task_id="T2",
            verified=False,
            skills_injected=[],
        ),
    ]
    path = append_run_metrics(cfg, rows)
    loaded = load_metrics(path)
    assert loaded.skill_efficacy["foo"].with_rate == 1.0
    assert loaded.skill_efficacy["foo"].without_rate == 0.0
    assert loaded.skill_efficacy["foo"].matched_tasks == 2


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


def _rows_for_run(
    run_id: str,
    *,
    verified: list[bool],
    retries: list[int],
    breakers: list[bool] | None = None,
) -> list[IterationLedgerRow]:
    breakers = breakers or [False] * len(verified)
    rows: list[IterationLedgerRow] = []
    for idx, (ok, retry, tripped) in enumerate(
        zip(verified, retries, breakers, strict=True), start=1
    ):
        rows.append(
            IterationLedgerRow(
                run_id=run_id,
                iteration=idx,
                task_id=f"{run_id}-T{idx}",
                verified=ok,
                retry_count=retry,
                circuit_breaker_cause="consecutive_failures:3" if tripped else "",
            )
        )
    return rows


def _grading_fixture_metrics(*, post_run_count: int) -> LoopMetrics:
    iterations: list[IterationLedgerRow] = []
    for run_id in ["r01", "r02", "r03", "r04", "r05"]:
        iterations.extend(
            _rows_for_run(
                run_id,
                verified=[False, False],
                retries=[2, 3],
                breakers=[True, False],
            )
        )
    after_ids = [f"r0{i}" for i in range(6, 6 + post_run_count)]
    for run_id in after_ids:
        iterations.extend(
            _rows_for_run(
                run_id,
                verified=[True, True],
                retries=[0, 0],
                breakers=[False, False],
            )
        )
    return LoopMetrics(iterations=iterations)


def test_grade_proposal_improved_window():
    metrics = _grading_fixture_metrics(post_run_count=5)
    record_proposal_outcome(
        metrics,
        proposal_id="prop-improved",
        merge_sha="abc123",
        prediction="fewer retries",
        merged_at_run_id="r05",
    )
    outcome = metrics.proposal_outcomes[0]
    assert outcome.grade == "improved"


def test_grade_proposal_inconclusive_few_post_runs():
    metrics = _grading_fixture_metrics(post_run_count=2)
    record_proposal_outcome(
        metrics,
        proposal_id="prop-wait",
        merge_sha="def456",
        prediction="wait for more runs",
        merged_at_run_id="r05",
    )
    outcome = metrics.proposal_outcomes[0]
    assert outcome.grade == "inconclusive"


def test_grade_proposal_regrade_updates_existing(tmp_path: Path):
    metrics = _grading_fixture_metrics(post_run_count=2)
    record_proposal_outcome(
        metrics,
        proposal_id="prop-regrade",
        merge_sha="ghi789",
        prediction="later proof",
        merged_at_run_id="r05",
    )
    assert metrics.proposal_outcomes[0].grade == "inconclusive"

    metrics.iterations.extend(
        _rows_for_run("r08", verified=[True, True], retries=[0, 0], breakers=[False, False])
    )
    assert grade_proposal(metrics, "prop-regrade") == "improved"
    assert metrics.proposal_outcomes[0].grade == "improved"
