"""``kalph plan`` — interview the owner, then draft roadmap + backlog from a goal."""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .adapters import AdapterError, make_adapter
from .config import Config
from .gitutil import (
    add_worktree,
    checkpoint,
    create_run_branch,
    head_sha,
    is_repo,
)
from .lint import validate_plan
from .loop import LoopError, _extract_rationale
from .prompt import (
    PLAN_COMPLETE_SENTINEL,
    PLANNING_ROLE,
    assemble_planning_interview_prompt,
    assemble_planning_prompt,
)

QUESTIONS_BLOCK_RE = re.compile(r"```QUESTIONS\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
QUESTION_HEADER_RE = re.compile(r"^Q(\d+):\s*(.+)$", re.MULTILINE)
OPTION_RE = re.compile(r"^(\d+)\.\s*(.+?)(?:\s*\(recommended\))?\s*$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^answer:\s*(.*)$", re.MULTILINE | re.IGNORECASE)


@dataclass
class PlanOption:
    index: int
    text: str
    recommended: bool = False


@dataclass
class PlanQuestion:
    qid: str
    title: str
    text: str = ""
    options: list[PlanOption] = field(default_factory=list)
    answer: str = ""

    @property
    def recommended_index(self) -> int | None:
        for opt in self.options:
            if opt.recommended:
                return opt.index
        return self.options[0].index if self.options else None


@dataclass
class PlanIteration:
    started_at: str
    duration_s: float = 0.0
    adapter_exit: int = -1
    timed_out: bool = False
    rationale: str = ""
    made_progress: bool = False
    plan_complete: bool = False
    validated: bool = False
    failure: str = ""
    phase: str = "draft"  # interview | draft


@dataclass
class PlanResult:
    run_id: str
    status: str = "running"  # completed | validation_failed | error | awaiting_answers
    branch: str = ""
    workdir: str = ""
    iteration: PlanIteration | None = None
    findings: list[str] = field(default_factory=list)
    diagnosis: str = ""
    questions_path: str = ""


def planning_phase_slug(goal: str) -> str:
    """Stable directory name under ``.kalph/phases/`` derived from the goal."""
    first = goal.strip().splitlines()[0] if goal.strip() else "plan"
    slug = re.sub(r"[^a-z0-9]+", "-", first.lower()).strip("-")
    return slug[:60] or "plan"


def parse_questions_block(text: str) -> list[PlanQuestion]:
    """Parse a `` ```QUESTIONS `` fenced block from agent output."""
    match = QUESTIONS_BLOCK_RE.search(text)
    if not match:
        return []
    return _parse_questions_body(match.group(1))


def _parse_questions_body(body: str) -> list[PlanQuestion]:
    headers = list(QUESTION_HEADER_RE.finditer(body))
    if not headers:
        return []
    questions: list[PlanQuestion] = []
    for idx, header in enumerate(headers):
        qid = f"Q{header.group(1)}"
        title = header.group(2).strip()
        start = header.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        section = body[start:end].strip()
        text_lines: list[str] = []
        options: list[PlanOption] = []
        answer = ""
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            opt_match = OPTION_RE.match(stripped)
            if opt_match:
                opt_text = opt_match.group(2).strip()
                recommended = "(recommended)" in stripped.lower()
                options.append(
                    PlanOption(
                        index=int(opt_match.group(1)),
                        text=opt_text,
                        recommended=recommended,
                    )
                )
                continue
            ans_match = ANSWER_RE.match(stripped)
            if ans_match:
                answer = ans_match.group(1).strip()
                continue
            text_lines.append(stripped)
        questions.append(
            PlanQuestion(
                qid=qid,
                title=title,
                text="\n".join(text_lines).strip(),
                options=options,
                answer=answer,
            )
        )
    return questions


def serialize_questions_md(questions: list[PlanQuestion]) -> str:
    lines = [
        "# Planning interview",
        "",
        "Fill in each `answer:` line, then re-run `kalph plan` with the same goal.",
        "",
    ]
    for q in questions:
        lines.append(f"{q.qid}: {q.title}")
        if q.text:
            lines.append(q.text)
        for opt in q.options:
            rec = " (recommended)" if opt.recommended else ""
            lines.append(f"{opt.index}. {opt.text}{rec}")
        lines.append("")
        lines.append(f"answer: {q.answer}".rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_questions_md(path: Path) -> list[PlanQuestion]:
    return _parse_questions_body(path.read_text(encoding="utf-8"))


def questions_answered(questions: list[PlanQuestion]) -> bool:
    return bool(questions) and all(q.answer.strip() for q in questions)


def write_interview_context(path: Path, questions: list[PlanQuestion]):
    lines = ["## Decisions from planning interview", ""]
    for q in questions:
        lines.append(f"- **{q.qid}: {q.title}** — {q.answer.strip()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def enrich_goal_with_decisions(goal: str, questions: list[PlanQuestion]) -> str:
    lines = [goal.rstrip(), "", "## Owner decisions (from planning interview)", ""]
    for q in questions:
        lines.append(f"- {q.qid}: {q.title} → {q.answer.strip()}")
    return "\n".join(lines).rstrip() + "\n"


def present_questions_tty(
    questions: list[PlanQuestion],
    input_fn=input,
    print_fn=print,
) -> list[PlanQuestion]:
    answered: list[PlanQuestion] = []
    for q in questions:
        print_fn(f"\n{q.qid}: {q.title}")
        if q.text:
            print_fn(q.text)
        default = q.recommended_index
        for opt in q.options:
            rec = " (recommended)" if opt.recommended else ""
            print_fn(f"  {opt.index}. {opt.text}{rec}")
        prompt = f"Choice [{default}]: " if default is not None else "Choice: "
        raw = input_fn(prompt).strip()
        choice = default if not raw and default is not None else None
        if choice is None:
            try:
                choice = int(raw)
            except ValueError:
                choice = default if default is not None else 1
        selected = next((o.text for o in q.options if o.index == choice), "")
        if not selected and q.options:
            fallback = default if default is not None else q.options[0].index
            selected = next(o.text for o in q.options if o.index == fallback)
        answered.append(
            PlanQuestion(
                qid=q.qid,
                title=q.title,
                text=q.text,
                options=q.options,
                answer=selected,
            )
        )
    return answered


@dataclass
class _InterviewOutcome:
    status: str
    iteration: PlanIteration | None = None
    questions: list[PlanQuestion] = field(default_factory=list)
    diagnosis: str = ""


class PlanRunner:
    """Run planning: interview (when needed), then one draft iteration."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _prepare_workdir(self, run_id: str) -> tuple[Path, str]:
        cfg = self.cfg
        branch = f"{cfg.git.branch_prefix}plan-{run_id}"
        if cfg.git.isolation == "none":
            return cfg.root, ""
        create_run_branch(cfg.root, branch)
        if cfg.git.isolation == "branch":
            from .gitutil import git

            git(["checkout", branch], cfg.root)
            return cfg.root, branch
        workdir = cfg.kalph_dir / "worktrees" / run_id
        add_worktree(cfg.root, workdir, branch)
        return workdir, branch

    def _write_transcript(self, run_dir: Path, name: str, prompt: str, output: str):
        from .security import scrub

        if self.cfg.security.scrub_transcripts:
            output = scrub(output)
        (run_dir / name).write_text(
            f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
            encoding="utf-8",
        )

    def run(
        self,
        goal: str,
        log=print,
        is_tty: bool | None = None,
        input_fn=input,
    ) -> PlanResult:
        cfg = self.cfg
        if not is_repo(cfg.root):
            raise LoopError(f"{cfg.root} is not a git repository")
        if not goal.strip():
            raise LoopError("plan goal is empty")
        if is_tty is None:
            is_tty = sys.stdin.isatty()

        run_id = time.strftime("%Y%m%d-%H%M%S")
        run_dir = cfg.kalph_dir / "runs" / f"plan-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        workdir, branch = self._prepare_workdir(run_id)
        result = PlanResult(run_id=run_id, branch=branch, workdir=str(workdir))
        adapter = make_adapter(cfg)

        phase_slug = planning_phase_slug(goal)
        phase_dir = cfg.root / ".kalph" / "phases" / phase_slug
        questions_path = phase_dir / "QUESTIONS.md"
        context_path = phase_dir / "CONTEXT.md"
        result.questions_path = str(questions_path)

        existing = load_questions_md(questions_path) if questions_path.is_file() else []
        if existing and questions_answered(existing):
            write_interview_context(context_path, existing)
            draft_goal = enrich_goal_with_decisions(goal, existing)
            log(f"kalph plan {run_id}: using answered interview from {questions_path}")
            return self._run_draft(
                workdir,
                branch,
                run_dir,
                draft_goal,
                adapter,
                result,
                log,
            )

        if existing and not questions_answered(existing):
            if not is_tty:
                log(
                    f"Answer the questions in {questions_path}, "
                    "then re-run kalph plan with the same goal."
                )
                result.status = "awaiting_answers"
                return result
            answered = present_questions_tty(existing, input_fn=input_fn, print_fn=log)
            write_interview_context(context_path, answered)
            write_questions_file(questions_path, answered)
            draft_goal = enrich_goal_with_decisions(goal, answered)
            log(f"kalph plan {run_id}: interview complete, drafting plan")
            return self._run_draft(
                workdir,
                branch,
                run_dir,
                draft_goal,
                adapter,
                result,
                log,
            )

        log(f"kalph plan {run_id}: branch={branch or '(in place)'} — interview")
        interview = self._run_interview(workdir, run_dir, goal, adapter, log)
        if interview.status != "interview_ok":
            result.status = interview.status
            result.iteration = interview.iteration
            result.diagnosis = interview.diagnosis
            return result

        questions = interview.questions
        if not is_tty:
            write_questions_file(questions_path, questions)
            log(f"Questions written to {questions_path}")
            log("Fill in each answer: line, then re-run kalph plan with the same goal.")
            result.status = "awaiting_answers"
            result.iteration = interview.iteration
            return result

        answered = present_questions_tty(questions, input_fn=input_fn, print_fn=log)
        write_interview_context(context_path, answered)
        write_questions_file(questions_path, answered)
        draft_goal = enrich_goal_with_decisions(goal, answered)
        log(f"kalph plan {run_id}: interview complete, drafting plan")
        return self._run_draft(
            workdir,
            branch,
            run_dir,
            draft_goal,
            adapter,
            result,
            log,
        )

    def _run_interview(
        self,
        workdir: Path,
        run_dir: Path,
        goal: str,
        adapter,
        log,
    ) -> _InterviewOutcome:
        rec = PlanIteration(
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            phase="interview",
        )
        started = time.monotonic()
        prompt = assemble_planning_interview_prompt(self.cfg, goal=goal, role=PLANNING_ROLE)

        try:
            agent = adapter.run(prompt, workdir)
        except AdapterError as exc:
            rec.failure = f"adapter error: {exc}"
            rec.duration_s = round(time.monotonic() - started, 1)
            self._write_transcript(run_dir, "iter-interview.log", prompt, rec.failure)
            return _InterviewOutcome(
                status="error",
                iteration=rec,
                diagnosis=rec.failure,
            )

        rec.adapter_exit = agent.exit_code
        rec.timed_out = agent.timed_out
        rec.rationale = _extract_rationale(agent.output)
        rec.duration_s = round(time.monotonic() - started, 1)
        self._write_transcript(run_dir, "iter-interview.log", prompt, agent.output)

        if not agent.ok:
            rec.failure = (
                f"agent exit {agent.exit_code}"
                + (" (timeout)" if agent.timed_out else "")
            )
            return _InterviewOutcome(status="error", iteration=rec, diagnosis=rec.failure)

        questions = parse_questions_block(agent.output)
        if not questions:
            rec.failure = "missing ```QUESTIONS``` block in agent output"
            return _InterviewOutcome(status="error", iteration=rec, diagnosis=rec.failure)

        log(
            f"  interview: {len(questions)} question(s) "
            f"rationale={rec.rationale or '-'}"
        )
        return _InterviewOutcome(status="interview_ok", iteration=rec, questions=questions)

    def _run_draft(
        self,
        workdir: Path,
        branch: str,
        run_dir: Path,
        goal: str,
        adapter,
        result: PlanResult,
        log,
    ) -> PlanResult:
        rec = PlanIteration(
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            phase="draft",
        )
        result.iteration = rec
        started = time.monotonic()
        checkpoint(workdir, "kalph: pre-plan checkpoint")
        sha_before = head_sha(workdir)

        prompt = assemble_planning_prompt(self.cfg, goal=goal, role=PLANNING_ROLE)
        log(f"kalph plan {result.run_id}: branch={branch or '(in place)'} — draft")

        try:
            agent = adapter.run(prompt, workdir)
        except AdapterError as exc:
            rec.failure = f"adapter error: {exc}"
            rec.duration_s = round(time.monotonic() - started, 1)
            self._write_transcript(run_dir, "iter-001.log", prompt, rec.failure)
            result.status = "error"
            result.diagnosis = rec.failure
            self._save_state(run_dir, result)
            log(f"  plan: {rec.failure}")
            return result

        rec.adapter_exit = agent.exit_code
        rec.timed_out = agent.timed_out
        rec.rationale = _extract_rationale(agent.output)
        rec.plan_complete = PLAN_COMPLETE_SENTINEL in agent.output
        self._write_transcript(run_dir, "iter-001.log", prompt, agent.output)

        checkpoint(workdir, "kalph: post-plan auto-checkpoint")
        rec.made_progress = head_sha(workdir) != sha_before
        findings = validate_plan(workdir, sha_before)
        rec.validated = not findings
        rec.duration_s = round(time.monotonic() - started, 1)

        failed = (
            not agent.ok
            or not rec.made_progress
            or not rec.plan_complete
            or not rec.validated
        )
        if failed:
            parts = []
            if not agent.ok:
                parts.append(
                    f"agent exit {agent.exit_code}"
                    + (" (timeout)" if agent.timed_out else "")
                )
            if not rec.made_progress:
                parts.append("no diff produced")
            if not rec.plan_complete:
                parts.append(f"missing {PLAN_COMPLETE_SENTINEL!r} sentinel")
            if not rec.validated:
                parts.append("plan validation failed")
                from .lint import format_finding

                result.findings = [format_finding(f) for f in findings]
            rec.failure = "; ".join(parts)
            result.status = "validation_failed" if findings else "error"
        else:
            result.status = "completed"

        log(
            f"  plan: rationale={rec.rationale or '-'} "
            f"progress={rec.made_progress} validated={rec.validated} "
            f"{'FAIL: ' + rec.failure if rec.failure else 'ok'}"
        )
        self._save_state(run_dir, result)
        return result

    def _save_state(self, run_dir: Path, result: PlanResult):
        payload = asdict(result)
        (run_dir / "plan.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_questions_file(path: Path, questions: list[PlanQuestion]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_questions_md(questions), encoding="utf-8")
