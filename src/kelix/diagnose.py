"""``kelix diagnose`` — select failed runs for periodic self-review.

Owner-invoked only; never called from the loop runner (see T-DIAGNOSE CONTEXT).
ST8: run selection and CLI skeleton. ST9: failed-transcript loader with budget.
ST10: one adapter iteration writes the diagnosis markdown file.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .adapters import AdapterError, make_adapter
from .config import Config
from .gitutil import add_worktree, create_run_branch, is_repo
from .loop import LoopError, _extract_rationale
from .metrics import IterationLedgerRow, load_metrics, metrics_path
from .prompt import DIAGNOSE_ROLE, assemble_diagnose_prompt


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


@dataclass
class DiagnoseIteration:
    started_at: str
    duration_s: float = 0.0
    adapter_exit: int = -1
    timed_out: bool = False
    rationale: str = ""
    validated: bool = False
    failure: str = ""


@dataclass
class DiagnoseResult:
    run_ids: list[str] = field(default_factory=list)
    diagnosis_path: Path = Path()
    status: str = "running"  # completed | validation_failed | error
    iteration: DiagnoseIteration | None = None
    findings: list[str] = field(default_factory=list)


def diagnosis_rel_path(cfg: Config, path: Path) -> Path:
    """Return *path* relative to ``cfg.root`` when possible."""
    if path.is_absolute():
        try:
            return path.relative_to(cfg.root)
        except ValueError:
            return path
    return path


def validate_diagnosis(path: Path, run_ids: list[str]) -> list[str]:
    """Return validation errors for a diagnosis markdown file."""
    errors: list[str] = []
    if not path.is_file():
        errors.append(f"diagnosis file missing: {path}")
        return errors
    text = path.read_text(encoding="utf-8")
    if "## Findings" not in text:
        errors.append('missing "## Findings" section')
    if run_ids and not any(run_id in text for run_id in run_ids):
        errors.append("no run_id citation from scoped runs")
    return errors


class DiagnoseRunner:
    """Run ``kelix diagnose``: prepare scope, one adapter iteration, validate."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def _prepare_workdir(self, run_id: str) -> tuple[Path, str]:
        cfg = self.cfg
        branch = f"{cfg.git.branch_prefix}diagnose-{run_id}"
        if cfg.git.isolation == "none":
            return cfg.root, ""
        create_run_branch(cfg.root, branch)
        if cfg.git.isolation == "branch":
            from .gitutil import git

            git(["checkout", branch], cfg.root)
            return cfg.root, branch
        workdir = cfg.kelix_dir / "worktrees" / run_id
        add_worktree(cfg.root, workdir, branch)
        return workdir, branch

    def _write_transcript(self, run_dir: Path, prompt: str, output: str) -> None:
        from .security import scrub

        if self.cfg.security.scrub_transcripts:
            output = scrub(output)
        (run_dir / "iter-001.log").write_text(
            f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
            encoding="utf-8",
        )

    def _copy_diagnosis_to_root(self, workdir: Path, rel_path: Path, root_path: Path) -> None:
        if workdir == self.cfg.root:
            return
        src = workdir / rel_path
        if not src.is_file():
            return
        root_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, root_path)

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

    def run(
        self,
        *,
        run_ids: list[str] | None = None,
        last_n: int | None = None,
        diagnosis_file: str = "",
        log=print,
    ) -> DiagnoseResult:
        cfg = self.cfg
        if not is_repo(cfg.root):
            raise LoopError(f"{cfg.root} is not a git repository")

        prep = self.prepare(
            run_ids=run_ids,
            last_n=last_n,
            diagnosis_file=diagnosis_file,
        )
        result = DiagnoseResult(run_ids=prep.run_ids, diagnosis_path=prep.diagnosis_path)

        run_id = time.strftime("%Y%m%d-%H%M%S")
        run_dir = cfg.kelix_dir / "runs" / f"diagnose-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        workdir, branch = self._prepare_workdir(run_id)
        rel_path = diagnosis_rel_path(cfg, prep.diagnosis_path)
        prompt_path = rel_path.as_posix()
        workdir_file = workdir / rel_path
        root_file = prep.diagnosis_path

        ledger_excerpt = json.dumps(
            [asdict(row) for row in prep.ledger_rows],
            indent=2,
        )
        transcripts = load_failed_transcripts(cfg, prep.run_ids, prep.ledger_rows)
        prompt = assemble_diagnose_prompt(
            cfg,
            ledger_excerpt=ledger_excerpt,
            transcripts=transcripts,
            diagnosis_path=prompt_path,
            role=DIAGNOSE_ROLE,
        )

        rec = DiagnoseIteration(started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        result.iteration = rec
        started = time.monotonic()
        adapter = make_adapter(cfg)

        log(
            f"kelix diagnose {run_id}: selected {len(prep.run_ids)} run(s) "
            f"({', '.join(prep.run_ids)}); branch={branch or '(in place)'}"
        )
        log(f"  diagnosis file: {root_file}")

        workdir_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            agent = adapter.run(prompt, workdir)
        except AdapterError as exc:
            rec.failure = f"adapter error: {exc}"
            rec.duration_s = round(time.monotonic() - started, 1)
            self._write_transcript(run_dir, prompt, rec.failure)
            result.status = "error"
            result.findings = [rec.failure]
            log(f"  diagnose: {rec.failure}")
            return result

        rec.adapter_exit = agent.exit_code
        rec.timed_out = agent.timed_out
        rec.rationale = _extract_rationale(agent.output)
        rec.duration_s = round(time.monotonic() - started, 1)
        self._write_transcript(run_dir, prompt, agent.output)

        file_errors = validate_diagnosis(workdir_file, prep.run_ids)
        rec.validated = not file_errors

        errors: list[str] = []
        if not agent.ok:
            errors.append(
                f"agent exit {agent.exit_code}"
                + (" (timeout)" if agent.timed_out else "")
            )
        errors.extend(file_errors)

        if errors:
            rec.failure = "; ".join(errors)
            result.status = "validation_failed" if file_errors else "error"
            result.findings = errors
            log(f"  diagnose: FAIL — {rec.failure}")
            return result

        self._copy_diagnosis_to_root(workdir, rel_path, root_file)
        result.status = "completed"
        log(f"  diagnose: rationale={rec.rationale or '-'} ok")
        return result
