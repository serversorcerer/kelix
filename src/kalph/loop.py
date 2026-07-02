"""The Kalph loop runner: `kalph run`.

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
)
from .prompt import assemble_prompt, load_template
from .state import State, load_state, write_state

RATIONALE_RE = re.compile(r"^RATIONALE:\s*(.+)$", re.MULTILINE)
TASK_FROM_ROLE_RE = re.compile(r"Your assigned task for this iteration:\s*(\S+)")
TASK_FROM_RATIONALE_RE = re.compile(r"^(\S+)")
STOP_FILE = "STOP"  # .kalph/STOP — global kill switch


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
    diagnosis: str = ""


class LoopError(Exception):
    pass


def _extract_rationale(output: str) -> str:
    m = RATIONALE_RE.search(output)
    return m.group(1).strip() if m else ""


class Runner:
    def __init__(
        self,
        cfg: Config,
        role: str = "",
        agent_id: str = "solo",
        pre_iteration=None,
    ):
        self.cfg = cfg
        self.role = role
        self.agent_id = agent_id
        # Optional hook(workdir, index) -> str | None. Returns extra role text
        # for this iteration (fleet mode uses it to pin a claimed task), or
        # None to signal there is no eligible work left for this agent.
        self.pre_iteration = pre_iteration
        self._run_state: State | None = None

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
        workdir = cfg.kalph_dir / "worktrees" / run_id
        add_worktree(cfg.root, workdir, branch)
        return workdir, branch

    # -- helpers -------------------------------------------------------------

    def _kill_requested(self) -> bool:
        return (self.cfg.kalph_dir / STOP_FILE).exists()

    def _write_transcript(self, run_dir: Path, index: int, prompt: str, output: str):
        from .security import scrub

        if self.cfg.security.scrub_transcripts:
            output = scrub(output)
        (run_dir / f"iter-{index:03d}.log").write_text(
            f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
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
        kalph_dir = workdir / ".kalph"
        existing = load_state(kalph_dir)
        return existing if existing is not None else State()

    def _backlog_counts(self, workdir: Path) -> tuple[int, int]:
        from .backlog import parse_backlog

        backlog_path = workdir / self.cfg.loop.plan_file
        if not backlog_path.is_file():
            return 0, 0
        tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))
        done = sum(1 for t in tasks if t.status == "done")
        return done, len(tasks)

    @staticmethod
    def _current_task_from_role(role_extra: str) -> str:
        match = TASK_FROM_ROLE_RE.search(role_extra)
        return match.group(1) if match else ""

    @staticmethod
    def _task_from_rationale(rationale: str) -> str:
        if not rationale:
            return ""
        match = TASK_FROM_RATIONALE_RE.match(rationale.strip())
        return match.group(1).rstrip("—") if match else ""

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

    def _gather_context(self, workdir: Path) -> dict:
        from .memory import episode_digest, skills_digest
        from .prompt import load_phase_context
        from .state import STATE_FILE, load_state

        mailbox = ""
        mailbox_dir = self.cfg.kalph_dir / "fleet" / "mailbox"
        if mailbox_dir.is_dir():
            notes = sorted(mailbox_dir.glob("*.md"))
            mailbox = "\n---\n".join(
                p.read_text(encoding="utf-8") for p in notes[-5:]
            )

        kalph_dir = workdir / ".kalph"
        state = ""
        phase_context = ""
        run_state = load_state(kalph_dir)
        if run_state is not None:
            state = (kalph_dir / STATE_FILE).read_text(encoding="utf-8")
            phase_context = load_phase_context(kalph_dir, run_state.phase)

        return {
            "state": state,
            "phase_context": phase_context,
            "memory_digest": episode_digest(self.cfg),
            "skills": skills_digest(self.cfg, workdir),
            "mailbox": mailbox,
            "role": self.role,
        }

    # -- the loop ------------------------------------------------------------

    def run(self, max_iterations: int | None = None, log=print) -> RunResult:
        cfg = self.cfg
        if not is_repo(cfg.root):
            raise LoopError(f"{cfg.root} is not a git repository")
        backlog = cfg.root / cfg.loop.plan_file
        if not backlog.is_file():
            raise LoopError(
                f"no backlog at {cfg.loop.plan_file}; run `kalph init` first"
            )

        run_id = time.strftime("%Y%m%d-%H%M%S")
        if self.agent_id != "solo":
            run_id = f"{run_id}-{self.agent_id}"
        cap = max_iterations or cfg.loop.max_iterations
        run_dir = cfg.kalph_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        workdir, branch = self._prepare_workdir(run_id)
        result = RunResult(run_id=run_id, branch=branch, workdir=str(workdir))
        self._run_state = self._init_run_state(workdir)
        self._run_state.current_task = "selecting"
        template = load_template(cfg)  # loaded once: static for the whole run
        adapter = make_adapter(cfg)

        consecutive_failures = 0
        log(f"kalph run {run_id}: branch={branch or '(in place)'} cap={cap}")

        for index in range(1, cap + 1):
            if self._kill_requested():
                result.status = "killed"
                result.diagnosis = "kill switch (.kalph/STOP) present"
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
            checkpoint(workdir, f"kalph: pre-iteration {index} checkpoint")
            sha_before = head_sha(workdir)

            context = self._gather_context(workdir)
            if role_extra:
                context["role"] = (context["role"] or "") + "\n" + role_extra
            prompt = assemble_prompt(template, cfg, **context)

            try:
                agent = adapter.run(prompt, workdir)
            except AdapterError as exc:
                rec.failure = f"adapter error: {exc}"
                rec.duration_s = round(time.monotonic() - started, 1)
                self._write_transcript(run_dir, index, prompt, rec.failure)
                consecutive_failures += 1
                log(f"  iter {index}: {rec.failure}")
                if consecutive_failures >= cfg.loop.circuit_breaker_threshold:
                    self._trip_breaker(result, run_dir, consecutive_failures)
                    break
                continue

            rec.adapter_exit = agent.exit_code
            rec.timed_out = agent.timed_out
            rec.rationale = _extract_rationale(agent.output)
            rec.sentinel = COMPLETION_SENTINEL in agent.output
            self._write_transcript(run_dir, index, prompt, agent.output)

            committed = checkpoint(
                workdir, f"kalph: post-iteration {index} auto-checkpoint"
            )
            rec.made_progress = committed or head_sha(workdir) != sha_before
            rec.verified = self._verify(workdir)
            rec.duration_s = round(time.monotonic() - started, 1)

            self._update_run_state_after_iteration(current_task, rec, workdir)
            self._record_episode(rec, workdir)

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
        recent = [r for r in result.iterations if r.failure][-failures:]
        lines = [
            "# Kalph circuit breaker diagnosis",
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
        if self._run_state is not None:
            write_state(workdir / ".kalph", self._run_state)

        try:
            write_retrospective(self.cfg, result, run_dir)
        except Exception as exc:  # retrospective must never mask run status
            log(f"  (retrospective failed: {exc})")
        log(
            f"kalph run {result.run_id} finished: {result.status} "
            f"({len(result.iterations)} iterations)"
        )
        if result.diagnosis:
            log(f"  diagnosis: {result.diagnosis}")
