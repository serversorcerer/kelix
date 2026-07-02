"""The Kelix loop runner: `kelix run`.

Each iteration spawns a fresh agent process against a static prompt, in an
isolated worktree/branch, then the runner (not the agent) decides what happens
next. Stopping is deterministic: sentinel, iteration cap, circuit breaker, or
kill switch — never the agent's mood.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import COMPLETION_SENTINEL
from .adapters import AdapterError, make_adapter
from .config import Config
from .gitutil import (
    add_worktree,
    checkpoint,
    create_run_branch,
    git,
    head_sha,
    is_repo,
    last_commit_subject,
)
from .metrics import IterationLedgerRow
from .prompt import assemble_prompt, load_template, relevance_query_for_task
from .state import State, load_state, write_state

RATIONALE_RE = re.compile(r"^RATIONALE:\s*(.+)$", re.MULTILINE)
FROM_COMMIT_RATIONALE_PREFIX = "(from commit) "
TASK_FROM_ROLE_RE = re.compile(r"Your assigned task for this iteration:\s*(\S+)")
TASK_FROM_RATIONALE_RE = re.compile(r"^(\S+?)(?:\s*[—\-:]|$)")
STOP_FILE = "STOP"  # .kelix/STOP — global kill switch


@dataclass
class IterationRecord:
    index: int
    started_at: str
    duration_s: float = 0.0
    adapter_exit: int = -1
    timed_out: bool = False
    rationale: str = ""
    made_progress: bool = False  # new commits or dirty tree after the iteration
    sentinel: bool = False
    verified: bool | None = None  # None = no verify commands configured
    failure: str = ""  # empty = not a failure iteration


@dataclass
class RunResult:
    run_id: str
    status: str = "running"  # completed|max_iterations|circuit_breaker|killed|error
    branch: str = ""
    workdir: str = ""
    iterations: list[IterationRecord] = field(default_factory=list)
    ledger_rows: list[IterationLedgerRow] = field(default_factory=list)
    diagnosis: str = ""


class LoopError(Exception):
    pass


def _extract_rationale(output: str) -> str:
    m = RATIONALE_RE.search(output)
    return m.group(1).strip() if m else ""


def _resolve_rationale(rationale: str, workdir: Path, sha_before: str) -> str:
    """Use the iteration commit subject when the agent omitted RATIONALE."""
    if rationale:
        return rationale
    if head_sha(workdir) == sha_before:
        return ""
    subject = last_commit_subject(workdir)
    if not subject:
        return ""
    return f"{FROM_COMMIT_RATIONALE_PREFIX}{subject}"


class Runner:
    def __init__(
        self,
        cfg: Config,
        role: str = "",
        agent_id: str = "solo",
        fleet_id: str = "",
        pre_iteration=None,
    ):
        self.cfg = cfg
        self.role = role
        self.agent_id = agent_id
        self.fleet_id = fleet_id
        # Optional hook(workdir, index) -> str | None. Returns extra role text
        # for this iteration (fleet mode uses it to pin a claimed task), or
        # None to signal there is no eligible work left for this agent.
        self.pre_iteration = pre_iteration
        self._run_state: State | None = None
        self._phase_gate_lines: list[str] = []

    # -- setup ---------------------------------------------------------------

    def _prepare_workdir(self, run_id: str) -> tuple[Path, str]:
        cfg = self.cfg
        branch = f"{cfg.git.branch_prefix}run-{run_id}"
        if cfg.git.isolation == "none":
            return cfg.root, ""
        create_run_branch(cfg.root, branch)
        if cfg.git.isolation == "branch":
            git(["checkout", branch], cfg.root)
            return cfg.root, branch
        workdir = cfg.kelix_dir / "worktrees" / run_id
        add_worktree(cfg.root, workdir, branch)
        return workdir, branch

    # -- helpers -------------------------------------------------------------

    def _kill_requested(self) -> bool:
        return (self.cfg.kelix_dir / STOP_FILE).exists()

    def _write_transcript(self, run_dir: Path, index: int, prompt: str, output: str):
        from .security import scrub

        if self.cfg.security.scrub_transcripts:
            output = scrub(output)
        (run_dir / f"iter-{index:03d}.log").write_text(
            f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
            encoding="utf-8",
        )

    def _write_context_manifest(
        self,
        run_dir: Path,
        index: int,
        manifest: list[dict],
        relevance_query: str = "",
    ) -> None:
        payload = {
            "iteration": index,
            "relevance_query": relevance_query,
            "items": manifest,
        }
        (run_dir / f"context-{index:03d}.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _save_state(self, run_dir: Path, result: RunResult):
        payload = asdict(result)
        (run_dir / "run.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _verify(self, workdir: Path) -> bool | None:
        from .verify import run_verification

        report = run_verification(self.cfg, workdir)
        if report is None:
            return None
        return report.ok

    def _init_run_state(self, workdir: Path) -> State:
        kelix_dir = workdir / ".kelix"
        existing = load_state(kelix_dir)
        return existing if existing is not None else State()

    def _backlog_tasks(self, workdir: Path):
        from .backlog import parse_backlog

        backlog_path = workdir / self.cfg.loop.plan_file
        if not backlog_path.is_file():
            return []
        return parse_backlog(backlog_path.read_text(encoding="utf-8"))

    def _backlog_counts(self, workdir: Path) -> tuple[int, int]:
        tasks = self._backlog_tasks(workdir)
        done = sum(1 for t in tasks if t.status == "done")
        return done, len(tasks)

    def _active_phase_tasks_done(self, workdir: Path, phase_id: str) -> bool:
        phase_tasks = [t for t in self._backlog_tasks(workdir) if t.phase == phase_id]
        if not phase_tasks:
            return False
        return all(t.status == "done" for t in phase_tasks)

    def _phase_gate_retrospective_lines(self, uncovered: list[str]) -> list[str]:
        lines = ["", "## Phase gate", ""]
        lines.extend(f"- {req_id}: uncovered" for req_id in uncovered)
        return lines

    def _apply_phase_gate(self, workdir: Path) -> None:
        """Enforce REQ coverage for the active phase; mutate run state in place."""
        if self._run_state is None or not self._run_state.phase:
            return

        from .roadmap import (
            coverage,
            load_roadmap,
            next_phase,
            phase_fully_covered,
            uncovered_reqs,
        )

        roadmap = load_roadmap(workdir / ".kelix")
        if roadmap is None:
            return

        entries = coverage(roadmap, self._backlog_tasks(workdir), self._run_state.phase)
        if phase_fully_covered(entries):
            self._run_state.blockers = []
            following = next_phase(roadmap, self._run_state.phase)
            if following:
                self._run_state.phase = following
                for phase in roadmap.phases:
                    if phase.id == following and phase.milestone_id:
                        self._run_state.milestone = phase.milestone_id
                        break
            self._phase_gate_lines = []
            return

        missing = uncovered_reqs(entries)
        self._run_state.blockers = [f"{req_id}: uncovered" for req_id in missing]
        self._phase_gate_lines = (
            self._phase_gate_retrospective_lines(missing) if missing else []
        )

    def _maybe_apply_phase_gate(self, workdir: Path, *, at_run_end: bool) -> None:
        if self._run_state is None or not self._run_state.phase:
            return
        if at_run_end or self._active_phase_tasks_done(workdir, self._run_state.phase):
            self._apply_phase_gate(workdir)

    @staticmethod
    def _current_task_from_role(role_extra: str) -> str:
        match = TASK_FROM_ROLE_RE.search(role_extra)
        return match.group(1) if match else ""

    @staticmethod
    def _task_from_rationale(rationale: str) -> str:
        if not rationale:
            return ""
        text = rationale.strip()
        if text.startswith(FROM_COMMIT_RATIONALE_PREFIX):
            text = text[len(FROM_COMMIT_RATIONALE_PREFIX) :].strip()
        match = TASK_FROM_RATIONALE_RE.match(text)
        return match.group(1).rstrip("—") if match else ""

    def _ledger_task_id(self, rec: IterationRecord, current_task: str) -> str:
        task_id = self._task_from_rationale(rec.rationale)
        if not task_id and current_task != "selecting":
            task_id = current_task
        return task_id

    def _record_ledger_row(
        self,
        result: RunResult,
        rec: IterationRecord,
        current_task: str,
        *,
        circuit_breaker_cause: str = "",
    ) -> None:
        task_id = self._ledger_task_id(rec, current_task)
        retry_count = sum(
            1 for row in result.ledger_rows if row.task_id and row.task_id == task_id
        )
        result.ledger_rows.append(
            IterationLedgerRow(
                run_id=result.run_id,
                iteration=rec.index,
                task_id=task_id,
                verified=rec.verified,
                retry_count=retry_count,
                duration_s=rec.duration_s,
                failure=rec.failure,
                circuit_breaker_cause=circuit_breaker_cause,
                agent_id=self.agent_id,
                fleet_id=self.fleet_id,
            )
        )

    def _update_run_state_after_iteration(
        self,
        current_task: str,
        rec: IterationRecord,
        workdir: Path,
    ) -> None:
        if self._run_state is None:
            return
        task_id = self._task_from_rationale(rec.rationale) or (
            current_task if current_task != "selecting" else ""
        )
        if task_id:
            self._run_state.last_task = task_id
        done, total = self._backlog_counts(workdir)
        self._run_state.done = done
        self._run_state.total = total
        if rec.verified is True:
            self._run_state.last_verified_commit = head_sha(workdir)

    def _gather_context(self, workdir: Path, current_task: str = "") -> dict:
        from .prompt import load_phase_context
        from .state import STATE_FILE, load_state

        mailbox = ""
        mailbox_dir = self.cfg.kelix_dir / "fleet" / "mailbox"
        if mailbox_dir.is_dir():
            notes = sorted(mailbox_dir.glob("*.md"))
            mailbox = "\n---\n".join(
                p.read_text(encoding="utf-8") for p in notes[-5:]
            )

        kelix_dir = workdir / ".kelix"
        state = ""
        phase_context = ""
        state_source = ".kelix/STATE.md"
        phase_source = ""
        run_state = load_state(kelix_dir)
        if run_state is not None:
            state = (kelix_dir / STATE_FILE).read_text(encoding="utf-8")
            if run_state.phase:
                phase_source = f".kelix/phases/{run_state.phase}/CONTEXT.md"
            phase_context = load_phase_context(kelix_dir, run_state.phase)

        mailbox_source = ".kelix/fleet/mailbox"
        return {
            "state": state,
            "phase_context": phase_context,
            "mailbox": mailbox,
            "role": self.role,
            "relevance_query": relevance_query_for_task(
                self.cfg, workdir, current_task
            ),
            "workdir": workdir,
            "state_source": state_source,
            "phase_source": phase_source,
            "mailbox_source": mailbox_source,
        }

    # -- the loop ------------------------------------------------------------

    def run(self, max_iterations: int | None = None, log=None) -> RunResult:
        if log is None:
            # Line-buffered progress even when stdout is a pipe (backgrounded
            # or tee'd runs): an unattended owner must see iterations land
            # live, not on process exit.
            def log(msg: str) -> None:
                print(msg, flush=True)
        cfg = self.cfg
        if not is_repo(cfg.root):
            raise LoopError(f"{cfg.root} is not a git repository")
        backlog = cfg.root / cfg.loop.plan_file
        if not backlog.is_file():
            raise LoopError(
                f"no backlog at {cfg.loop.plan_file}; run `kelix init` first"
            )

        run_id = time.strftime("%Y%m%d-%H%M%S")
        if self.agent_id != "solo":
            run_id = f"{run_id}-{self.agent_id}"
        cap = max_iterations or cfg.loop.max_iterations
        run_dir = cfg.kelix_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        workdir, branch = self._prepare_workdir(run_id)
        result = RunResult(run_id=run_id, branch=branch, workdir=str(workdir))
        self._run_state = self._init_run_state(workdir)
        self._run_state.current_task = "selecting"
        template = load_template(cfg)  # loaded once: static for the whole run
        adapter = make_adapter(cfg)

        consecutive_failures = 0
        log(f"kelix run {run_id}: branch={branch or '(in place)'} cap={cap}")

        for index in range(1, cap + 1):
            if self._kill_requested():
                result.status = "killed"
                result.diagnosis = "kill switch (.kelix/STOP) present"
                break

            role_extra = ""
            if self.pre_iteration is not None:
                role_extra = self.pre_iteration(workdir, index)
                if role_extra is None:
                    result.status = "completed"
                    result.diagnosis = "no eligible tasks left for this agent"
                    break

            current_task = "selecting"
            if role_extra:
                from_role = self._current_task_from_role(role_extra)
                if from_role:
                    current_task = from_role
            if self._run_state is not None:
                self._run_state.current_task = current_task

            rec = IterationRecord(
                index=index, started_at=time.strftime("%Y-%m-%dT%H:%M:%S")
            )
            result.iterations.append(rec)
            started = time.monotonic()
            checkpoint(workdir, f"kelix: pre-iteration {index} checkpoint")
            sha_before = head_sha(workdir)

            context = self._gather_context(workdir, current_task)
            if role_extra:
                context["role"] = (context["role"] or "") + "\n" + role_extra
            prompt, manifest = assemble_prompt(template, cfg, **context)
            self._write_context_manifest(
                run_dir,
                index,
                manifest,
                context.get("relevance_query", ""),
            )

            try:
                agent = adapter.run(prompt, workdir)
            except AdapterError as exc:
                rec.failure = f"adapter error: {exc}"
                rec.duration_s = round(time.monotonic() - started, 1)
                self._write_transcript(run_dir, index, prompt, rec.failure)
                self._record_ledger_row(result, rec, current_task)
                consecutive_failures += 1
                log(f"  iter {index}: {rec.failure}")
                if consecutive_failures >= cfg.loop.circuit_breaker_threshold:
                    self._trip_breaker(result, run_dir, consecutive_failures)
                    break
                continue

            rec.adapter_exit = agent.exit_code
            rec.timed_out = agent.timed_out
            rec.sentinel = COMPLETION_SENTINEL in agent.output
            self._write_transcript(run_dir, index, prompt, agent.output)

            committed = checkpoint(
                workdir, f"kelix: post-iteration {index} auto-checkpoint"
            )
            rec.made_progress = committed or head_sha(workdir) != sha_before
            rec.rationale = _resolve_rationale(
                _extract_rationale(agent.output), workdir, sha_before
            )
            rec.verified = self._verify(workdir)
            rec.duration_s = round(time.monotonic() - started, 1)

            self._update_run_state_after_iteration(current_task, rec, workdir)
            self._record_episode(rec, workdir)
            if not rec.failure:
                self._maybe_apply_phase_gate(workdir, at_run_end=False)

            failed = (
                not agent.ok
                or (not rec.made_progress and not rec.sentinel)
                or rec.verified is False
            )
            if failed:
                parts = []
                if not agent.ok:
                    parts.append(f"agent exit {agent.exit_code}"
                                 + (" (timeout)" if agent.timed_out else ""))
                if not rec.made_progress and not rec.sentinel:
                    parts.append("no diff produced")
                if rec.verified is False:
                    parts.append("verification failed")
                rec.failure = "; ".join(parts)
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            log(
                f"  iter {index}: rationale={rec.rationale or '-'} "
                f"progress={rec.made_progress} verified={rec.verified} "
                f"{'FAIL: ' + rec.failure if rec.failure else 'ok'}"
            )
            self._record_ledger_row(result, rec, current_task)
            self._save_state(run_dir, result)

            if rec.sentinel:
                # The sentinel is only honored when verification is green
                # (or there is nothing to verify). A sentinel with red
                # verification counts as a failure iteration: the agent said
                # "done" but done means verified-done.
                if rec.verified is not False:
                    result.status = "completed"
                    break
                log("  sentinel ignored: verification is red")

            if consecutive_failures >= cfg.loop.circuit_breaker_threshold:
                self._trip_breaker(result, run_dir, consecutive_failures)
                break
        else:
            result.status = "max_iterations"

        self._save_state(run_dir, result)
        self._finish(result, run_dir, log)
        return result

    def _trip_breaker(self, result: RunResult, run_dir: Path, failures: int):
        result.status = "circuit_breaker"
        cause = f"consecutive_failures:{failures}"
        for row in result.ledger_rows[-failures:]:
            row.circuit_breaker_cause = cause
        recent = [r for r in result.iterations if r.failure][-failures:]
        lines = [
            "# Kelix circuit breaker diagnosis",
            "",
            f"The loop stopped itself after {failures} consecutive failure "
            "iterations instead of burning more tokens.",
            "",
            "## Failure sequence",
        ]
        lines += [
            f"- iteration {r.index}: {r.failure} (rationale: {r.rationale or 'none'})"
            for r in recent
        ]
        lines += [
            "",
            "## What to look at",
            "- the transcripts for the iterations above in this directory",
            "- `git log` on the run branch for partial work",
            "- the backlog task these iterations were attempting",
        ]
        result.diagnosis = str(run_dir / "diagnosis.md")
        (run_dir / "diagnosis.md").write_text("\n".join(lines), encoding="utf-8")

    def _record_episode(self, rec: IterationRecord, workdir: Path):
        from .memory import record_episode

        record_episode(self.cfg, rec, agent_id=self.agent_id)

    def _finish(self, result: RunResult, run_dir: Path, log):
        from .memory import write_retrospective

        workdir = Path(result.workdir) if result.workdir else self.cfg.root
        self._maybe_apply_phase_gate(workdir, at_run_end=True)
        if self._run_state is not None:
            write_state(workdir / ".kelix", self._run_state)

        try:
            write_retrospective(
                self.cfg,
                result,
                run_dir,
                phase_gate_lines=self._phase_gate_lines or None,
            )
        except Exception as exc:  # retrospective must never mask run status
            log(f"  (retrospective failed: {exc})")
        log(
            f"kelix run {result.run_id} finished: {result.status} "
            f"({len(result.iterations)} iterations)"
        )
        if result.diagnosis:
            log(f"  diagnosis: {result.diagnosis}")
