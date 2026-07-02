"""``kelix diagnose`` — select failed runs for periodic self-review.

Owner-invoked only; never called from the loop runner (see T-DIAGNOSE CONTEXT).
ST8: run selection and CLI skeleton. ST9: failed-transcript loader with budget.
The adapter iteration (ST10) builds on this module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .metrics import IterationLedgerRow, load_metrics, metrics_path


class DiagnoseError(Exception):
    pass


_TRUNCATION_MARKER = "[... truncated to {n} chars]"


def transcript_path(cfg: Config, run_id: str, iteration: int) -> Path:
    """Return the loop runner's transcript path for *run_id* / *iteration*."""
    return cfg.kelix_dir / "runs" / run_id / f"iter-{iteration:03d}.log"


def load_failed_transcripts(
    cfg: Config,
    run_ids: list[str],
    ledger_rows: list[IterationLedgerRow],
) -> str:
    """Load failed-iteration transcripts up to ``diagnose_transcript_chars``.

    For each failed row in scope (ordered by *run_ids* then iteration), read
    ``.kelix/runs/<run_id>/iter-<n>.log`` when present. Sections are prefixed
    with a markdown header naming run, iteration, and task id. Missing files are
    skipped. When the char budget is exceeded, output is cut and a truncation
    marker naming the budget is appended.
    """
    budget = cfg.loop.diagnose_transcript_chars
    if budget < 1 or not ledger_rows:
        return ""

    run_order = {run_id: idx for idx, run_id in enumerate(run_ids)}
    ordered = sorted(
        ledger_rows,
        key=lambda row: (run_order.get(row.run_id, len(run_ids)), row.iteration),
    )

    parts: list[str] = []
    used = 0
    marker = _TRUNCATION_MARKER.format(n=budget)

    for row in ordered:
        path = transcript_path(cfg, row.run_id, row.iteration)
        if not path.is_file():
            continue

        header = f"## Run {row.run_id} / iteration {row.iteration}"
        if row.task_id:
            header += f" / task {row.task_id}"
        section = f"{header}\n\n{path.read_text(encoding='utf-8')}"

        remaining = budget - used
        if remaining <= 0:
            parts.append(marker)
            break

        if len(section) <= remaining:
            parts.append(section)
            used += len(section)
            continue

        parts.append(section[:remaining])
        parts.append(marker)
        break

    return "\n\n".join(parts)


def iteration_failed(row: IterationLedgerRow) -> bool:
    """Return True when a ledger row represents a failed iteration."""
    if row.failure:
        return True
    return row.verified is False


def runs_with_failures(rows: list[IterationLedgerRow]) -> set[str]:
    """Return run ids that have at least one failed iteration in *rows*."""
    failed: set[str] = set()
    for row in rows:
        if row.run_id and iteration_failed(row):
            failed.add(row.run_id)
    return failed


def list_run_dirs(kelix_dir: Path) -> list[str]:
    """Return run ids for subdirectories of ``kelix_dir/runs``, newest first."""
    runs_root = kelix_dir / "runs"
    if not runs_root.is_dir():
        return []
    ids = [p.name for p in runs_root.iterdir() if p.is_dir()]
    ids.sort(reverse=True)
    return ids


def select_diagnose_runs(
    cfg: Config,
    *,
    run_ids: list[str] | None = None,
    last_n: int | None = None,
) -> list[str]:
    """Select run ids for diagnosis.

    When *run_ids* is non-empty, return them in caller order (deduped).
    Otherwise return up to *last_n* most recent runs under ``.kelix/runs/``
    that have at least one failed ledger row. *last_n* defaults to
    ``cfg.loop.diagnose_default_runs``.
    """
    if run_ids:
        seen: set[str] = set()
        selected: list[str] = []
        for run_id in run_ids:
            if run_id and run_id not in seen:
                seen.add(run_id)
                selected.append(run_id)
        return selected

    n = last_n if last_n is not None else cfg.loop.diagnose_default_runs
    if n < 1:
        raise DiagnoseError("--last must be at least 1")

    metrics = load_metrics(metrics_path(cfg))
    failed_ids = runs_with_failures(metrics.iterations)
    if not failed_ids:
        return []

    candidates = [run_id for run_id in list_run_dirs(cfg.kelix_dir) if run_id in failed_ids]
    return candidates[:n]


def default_diagnosis_path(cfg: Config, *, timestamp: str | None = None) -> Path:
    """Return ``.kelix/memory/diagnosis-<timestamp>.md`` under *cfg*."""
    ts = timestamp or time.strftime("%Y%m%d-%H%M%S")
    return cfg.kelix_dir / "memory" / f"diagnosis-{ts}.md"


@dataclass
class DiagnosePrepareResult:
    run_ids: list[str] = field(default_factory=list)
    diagnosis_path: Path = Path()
    ledger_rows: list[IterationLedgerRow] = field(default_factory=list)


class DiagnoseRunner:
    """Prepare a diagnose invocation (adapter iteration lands in ST10)."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def prepare(
        self,
        *,
        run_ids: list[str] | None = None,
        last_n: int | None = None,
        diagnosis_file: str = "",
    ) -> DiagnosePrepareResult:
        selected = select_diagnose_runs(self.cfg, run_ids=run_ids, last_n=last_n)
        if not selected:
            raise DiagnoseError("no runs selected — provide --run-id or ensure failed runs exist")

        if diagnosis_file:
            path = Path(diagnosis_file)
            if not path.is_absolute():
                path = self.cfg.root / path
        else:
            path = default_diagnosis_path(self.cfg)

        metrics = load_metrics(metrics_path(self.cfg))
        selected_set = set(selected)
        scoped_rows = [
            row
            for row in metrics.iterations
            if row.run_id in selected_set and iteration_failed(row)
        ]

        return DiagnosePrepareResult(
            run_ids=selected,
            diagnosis_path=path,
            ledger_rows=scoped_rows,
        )
