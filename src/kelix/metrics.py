"""Loop outcome ledger — rollup metrics for self-tuning.

Dual memory streams (see ``.kelix/phases/T-METRICS/CONTEXT.md``):

- ``episodes.jsonl`` — raw append-only per-iteration stream.
- ``loop-metrics.json`` — runner-maintained rollup written at retrospective time.

Both live under ``.kelix/memory/`` and are gitignored (only ``project.md`` is
committed).

Optional token adapter hook (future milestone — not wired in v0.3)::

    TokenAdapter = Callable[[Any], dict[str, int | None] | None]

When wired, a token adapter receives the iteration's ``AgentResult`` and may
return per-provider token counts (e.g. ``{"input": 1200, "output": 400}``).
v0.3 always writes ``"tokens": null`` on every ``IterationLedgerRow``; no
adapter is invoked by the runner in this milestone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import Config

SCHEMA_VERSION = 1
METRICS_FILE = "memory/loop-metrics.json"


@dataclass
class IterationLedgerRow:
    run_id: str = ""
    iteration: int = 0
    task_id: str = ""
    verified: bool | None = None
    retry_count: int = 0
    duration_s: float = 0.0
    failure: str = ""
    circuit_breaker_cause: str = ""
    agent_id: str = ""
    fleet_id: str = ""
    backlog_lint: dict[str, int] = field(default_factory=dict)
    skills_injected: list[str] = field(default_factory=list)
    tokens: None = None


@dataclass
class FleetSummaryRow:
    fleet_id: str = ""
    run_ids: list[str] = field(default_factory=list)
    verified_rate: float = 0.0
    iteration_count: int = 0
    breaker_trips: int = 0


@dataclass
class ProposalOutcome:
    proposal_id: str = ""
    merge_sha: str = ""
    close_reason: str = ""
    prediction: str = ""
    grade: str = ""


@dataclass
class LoopMetrics:
    schema_version: int = SCHEMA_VERSION
    iterations: list[IterationLedgerRow] = field(default_factory=list)
    fleet_summaries: list[FleetSummaryRow] = field(default_factory=list)
    proposal_outcomes: list[ProposalOutcome] = field(default_factory=list)


def _iteration_row_from_dict(data: dict[str, Any]) -> IterationLedgerRow:
    backlog_lint = data.get("backlog_lint") or {}
    if not isinstance(backlog_lint, dict):
        backlog_lint = {}
    skills = data.get("skills_injected") or []
    if not isinstance(skills, list):
        skills = []
    verified = data.get("verified")
    if verified is not None and not isinstance(verified, bool):
        verified = None
    return IterationLedgerRow(
        run_id=str(data.get("run_id") or ""),
        iteration=int(data.get("iteration") or 0),
        task_id=str(data.get("task_id") or ""),
        verified=verified,
        retry_count=int(data.get("retry_count") or 0),
        duration_s=float(data.get("duration_s") or 0.0),
        failure=str(data.get("failure") or ""),
        circuit_breaker_cause=str(data.get("circuit_breaker_cause") or ""),
        agent_id=str(data.get("agent_id") or ""),
        fleet_id=str(data.get("fleet_id") or ""),
        backlog_lint={str(k): int(v) for k, v in backlog_lint.items()},
        skills_injected=[str(s) for s in skills],
        tokens=None,
    )


def _fleet_summary_from_dict(data: dict[str, Any]) -> FleetSummaryRow:
    run_ids = data.get("run_ids") or []
    if not isinstance(run_ids, list):
        run_ids = []
    return FleetSummaryRow(
        fleet_id=str(data.get("fleet_id") or ""),
        run_ids=[str(r) for r in run_ids],
        verified_rate=float(data.get("verified_rate") or 0.0),
        iteration_count=int(data.get("iteration_count") or 0),
        breaker_trips=int(data.get("breaker_trips") or 0),
    )


def _proposal_outcome_from_dict(data: dict[str, Any]) -> ProposalOutcome:
    return ProposalOutcome(
        proposal_id=str(data.get("proposal_id") or ""),
        merge_sha=str(data.get("merge_sha") or ""),
        close_reason=str(data.get("close_reason") or ""),
        prediction=str(data.get("prediction") or ""),
        grade=str(data.get("grade") or ""),
    )


def _metrics_from_dict(data: dict[str, Any]) -> LoopMetrics:
    iterations_raw = data.get("iterations") or []
    if not isinstance(iterations_raw, list):
        iterations_raw = []
    fleet_raw = data.get("fleet_summaries") or []
    if not isinstance(fleet_raw, list):
        fleet_raw = []
    proposal_raw = data.get("proposal_outcomes") or []
    if not isinstance(proposal_raw, list):
        proposal_raw = []

    iterations = [
        _iteration_row_from_dict(item)
        for item in iterations_raw
        if isinstance(item, dict)
    ]
    fleet_summaries = [
        _fleet_summary_from_dict(item)
        for item in fleet_raw
        if isinstance(item, dict)
    ]
    proposal_outcomes = [
        _proposal_outcome_from_dict(item)
        for item in proposal_raw
        if isinstance(item, dict)
    ]
    schema_version = data.get("schema_version", SCHEMA_VERSION)
    try:
        schema_version = int(schema_version)
    except (TypeError, ValueError):
        schema_version = SCHEMA_VERSION

    return LoopMetrics(
        schema_version=schema_version,
        iterations=iterations,
        fleet_summaries=fleet_summaries,
        proposal_outcomes=proposal_outcomes,
    )


def metrics_to_dict(metrics: LoopMetrics) -> dict[str, Any]:
    """Serialize *metrics* to a JSON-ready dict."""
    payload = asdict(metrics)
    for row in payload.get("iterations", []):
        row["tokens"] = None
    return payload


def empty_metrics() -> LoopMetrics:
    """Return an empty metrics document with the current schema version."""
    return LoopMetrics()


def load_metrics(path: Path | str) -> LoopMetrics:
    """Load loop-metrics.json from *path*. Missing or corrupt files -> empty."""
    path = Path(path)
    if not path.is_file():
        return empty_metrics()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_metrics()
    if not isinstance(data, dict):
        return empty_metrics()
    return _metrics_from_dict(data)


def save_metrics(path: Path | str, metrics: LoopMetrics) -> Path:
    """Write *metrics* as indented JSON. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = metrics_to_dict(metrics)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def metrics_path(cfg: Config) -> Path:
    """Return the loop-metrics.json path for *cfg*."""
    return cfg.kelix_dir / METRICS_FILE


def append_run_metrics(
    cfg: Config,
    rows: list[IterationLedgerRow],
    *,
    fleet_summary: FleetSummaryRow | None = None,
) -> Path:
    """Merge *rows* (and optional *fleet_summary*) into loop-metrics.json."""
    path = metrics_path(cfg)
    metrics = load_metrics(path)
    metrics.iterations.extend(rows)
    if fleet_summary is not None:
        metrics.fleet_summaries.append(fleet_summary)
    save_metrics(path, metrics)
    return path
