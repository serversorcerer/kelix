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
    merged_at_run_id: str = ""
    grade: str = ""


@dataclass
class SkillEfficacyEntry:
    with_rate: float = 0.0
    without_rate: float = 0.0
    matched_tasks: int = 0


@dataclass
class _WindowStats:
    verified_rate: float = 0.0
    mean_retry_count: float = 0.0
    breaker_rate: float = 0.0
    run_count: int = 0
    row_count: int = 0


PROPOSAL_WINDOW_SIZE = 5
PROPOSAL_MIN_POST_RUNS = 3


@dataclass
class LoopMetrics:
    schema_version: int = SCHEMA_VERSION
    iterations: list[IterationLedgerRow] = field(default_factory=list)
    fleet_summaries: list[FleetSummaryRow] = field(default_factory=list)
    proposal_outcomes: list[ProposalOutcome] = field(default_factory=list)
    skill_efficacy: dict[str, SkillEfficacyEntry] = field(default_factory=dict)


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
        merged_at_run_id=str(data.get("merged_at_run_id") or ""),
        grade=str(data.get("grade") or ""),
    )


def _skill_efficacy_entry_from_dict(data: dict[str, Any]) -> SkillEfficacyEntry:
    return SkillEfficacyEntry(
        with_rate=float(data.get("with_rate") or 0.0),
        without_rate=float(data.get("without_rate") or 0.0),
        matched_tasks=int(data.get("matched_tasks") or 0),
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
    efficacy_raw = data.get("skill_efficacy") or {}
    skill_efficacy: dict[str, SkillEfficacyEntry] = {}
    if isinstance(efficacy_raw, dict):
        for name, entry in efficacy_raw.items():
            if isinstance(name, str) and isinstance(entry, dict):
                skill_efficacy[name] = _skill_efficacy_entry_from_dict(entry)
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
        skill_efficacy=skill_efficacy,
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


def _verified_rate(rows: list[IterationLedgerRow]) -> float:
    scored = [row for row in rows if row.verified is not None]
    if not scored:
        return 0.0
    return sum(1 for row in scored if row.verified) / len(scored)


def compute_skill_efficacy(
    iterations: list[IterationLedgerRow],
) -> dict[str, SkillEfficacyEntry]:
    """Compute per-skill verified rates with vs without injection."""
    skill_names: set[str] = set()
    for row in iterations:
        skill_names.update(row.skills_injected)

    efficacy: dict[str, SkillEfficacyEntry] = {}
    for skill in sorted(skill_names):
        with_rows: list[IterationLedgerRow] = []
        without_rows: list[IterationLedgerRow] = []
        for row in iterations:
            if not row.task_id:
                continue
            if skill in row.skills_injected:
                with_rows.append(row)
            else:
                without_rows.append(row)
        scored = [row for row in with_rows + without_rows if row.verified is not None]
        efficacy[skill] = SkillEfficacyEntry(
            with_rate=_verified_rate(with_rows),
            without_rate=_verified_rate(without_rows),
            matched_tasks=len(scored),
        )
    return efficacy


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
    metrics.skill_efficacy = compute_skill_efficacy(metrics.iterations)
    save_metrics(path, metrics)
    return path


def unique_run_ids(iterations: list[IterationLedgerRow]) -> list[str]:
    """Return run ids in first-seen (append) order."""
    seen: list[str] = []
    for row in iterations:
        if row.run_id and row.run_id not in seen:
            seen.append(row.run_id)
    return seen


def _rows_for_run_ids(
    iterations: list[IterationLedgerRow],
    run_ids: set[str],
) -> list[IterationLedgerRow]:
    return [row for row in iterations if row.run_id in run_ids]


def _window_stats(rows: list[IterationLedgerRow]) -> _WindowStats:
    if not rows:
        return _WindowStats()
    verified_rows = [row for row in rows if row.verified is not None]
    verified_rate = (
        sum(1 for row in verified_rows if row.verified) / len(verified_rows)
        if verified_rows
        else 0.0
    )
    mean_retry = sum(row.retry_count for row in rows) / len(rows)
    breaker_rate = sum(1 for row in rows if row.circuit_breaker_cause) / len(rows)
    return _WindowStats(
        verified_rate=verified_rate,
        mean_retry_count=mean_retry,
        breaker_rate=breaker_rate,
        run_count=len({row.run_id for row in rows if row.run_id}),
        row_count=len(rows),
    )


def split_proposal_run_windows(
    iterations: list[IterationLedgerRow],
    merged_at_run_id: str,
    *,
    window_size: int = PROPOSAL_WINDOW_SIZE,
) -> tuple[list[str], list[str]]:
    """Return (before_run_ids, after_run_ids) around *merged_at_run_id*."""
    run_ids = unique_run_ids(iterations)
    if merged_at_run_id not in run_ids:
        return [], []
    idx = run_ids.index(merged_at_run_id)
    before = run_ids[max(0, idx - window_size + 1) : idx + 1]
    after = run_ids[idx + 1 : idx + 1 + window_size]
    return before, after


def _compare_window_stats(before: _WindowStats, after: _WindowStats) -> str:
    """Return improved, regressed, or inconclusive from before/after stats."""
    better_verified = after.verified_rate > before.verified_rate
    worse_verified = after.verified_rate < before.verified_rate
    worse_retry = after.mean_retry_count > before.mean_retry_count
    worse_breaker = after.breaker_rate > before.breaker_rate

    if better_verified and not worse_retry and not worse_breaker:
        return "improved"
    if worse_verified or worse_retry or worse_breaker:
        return "regressed"
    return "inconclusive"


def grade_proposal(
    metrics: LoopMetrics,
    proposal_id: str,
    *,
    window_size: int = PROPOSAL_WINDOW_SIZE,
    min_post_runs: int = PROPOSAL_MIN_POST_RUNS,
) -> str:
    """Grade *proposal_id* from ledger windows and persist on *metrics*."""
    outcome = _find_proposal_outcome(metrics, proposal_id)
    if outcome is None:
        raise ValueError(f"unknown proposal_id: {proposal_id}")
    if not outcome.merged_at_run_id:
        outcome.grade = "inconclusive"
        return outcome.grade

    before_ids, after_ids = split_proposal_run_windows(
        metrics.iterations,
        outcome.merged_at_run_id,
        window_size=window_size,
    )
    if len(after_ids) < min_post_runs:
        outcome.grade = "inconclusive"
        return outcome.grade

    before_stats = _window_stats(_rows_for_run_ids(metrics.iterations, set(before_ids)))
    after_stats = _window_stats(_rows_for_run_ids(metrics.iterations, set(after_ids)))
    outcome.grade = _compare_window_stats(before_stats, after_stats)
    return outcome.grade


def _find_proposal_outcome(metrics: LoopMetrics, proposal_id: str) -> ProposalOutcome | None:
    for outcome in metrics.proposal_outcomes:
        if outcome.proposal_id == proposal_id:
            return outcome
    return None


def record_proposal_outcome(
    metrics: LoopMetrics,
    *,
    proposal_id: str,
    prediction: str = "",
    merge_sha: str = "",
    close_reason: str = "",
    merged_at_run_id: str = "",
) -> ProposalOutcome:
    """Append or replace a proposal outcome and grade when merge data allows."""
    if merge_sha and close_reason:
        raise ValueError("provide merge_sha or close_reason, not both")
    if not merge_sha and not close_reason:
        raise ValueError("merge_sha or close_reason is required")

    existing = _find_proposal_outcome(metrics, proposal_id)
    outcome = ProposalOutcome(
        proposal_id=proposal_id,
        merge_sha=merge_sha,
        close_reason=close_reason,
        prediction=prediction or (existing.prediction if existing else ""),
        merged_at_run_id=merged_at_run_id or (existing.merged_at_run_id if existing else ""),
    )

    if existing is not None:
        idx = metrics.proposal_outcomes.index(existing)
        metrics.proposal_outcomes[idx] = outcome
    else:
        metrics.proposal_outcomes.append(outcome)

    if merge_sha and outcome.merged_at_run_id:
        grade_proposal(metrics, proposal_id)
    elif close_reason or merge_sha:
        outcome.grade = "inconclusive"

    return _find_proposal_outcome(metrics, proposal_id) or outcome


def default_merged_at_run_id(metrics: LoopMetrics) -> str:
    """Return the last run id in the ledger (pre-merge boundary default)."""
    run_ids = unique_run_ids(metrics.iterations)
    return run_ids[-1] if run_ids else ""
