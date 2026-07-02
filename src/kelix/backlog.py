"""Parse and serialize `.kelix/backlog.md` task lists."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TASK_LINE = re.compile(
    r"^- \[([ x])\] (\S+): (.+?) \| priority: (\d+) \| status: (\w+) \| by: (\w+)(.*)$"
)
TRAILING_FIELD = re.compile(r" \| (deps|phase|req): (.+?)(?= \| (?:deps|phase|req): |$)")
NOTE_LINE = re.compile(r"^  (rationale|details|diagnosis): (.*)$")
CONTINUATION_LINE = re.compile(r"^  (.+)$")


@dataclass
class Task:
    id: str
    title: str
    priority: int
    status: str
    by: str
    deps: list[str] = field(default_factory=list)
    phase: str = ""
    req: str = ""
    notes: dict[str, str] = field(default_factory=dict)


def _parse_trailing_fields(rest: str) -> tuple[list[str], str, str]:
    """Parse optional ``| deps:``, ``| phase:``, ``| req:`` segments in any order."""
    deps: list[str] = []
    phase = ""
    req = ""
    if not rest:
        return deps, phase, req
    for key, value in TRAILING_FIELD.findall(f"{rest} "):
        if key == "deps":
            deps = [part.strip() for part in value.split(",") if part.strip()]
        elif key == "phase":
            phase = value.strip()
        elif key == "req":
            req = value.strip()
    return deps, phase, req


def parse_backlog(text: str) -> list[Task]:
    """Parse backlog markdown into tasks. Malformed lines are skipped."""
    tasks: list[Task] = []
    current: Task | None = None
    last_note_key = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        match = TASK_LINE.match(line)
        if match:
            checked, task_id, title, priority, status, by, trailing = match.groups()
            if checked == "x" and status != "done":
                status = "done"
            deps, phase, req = _parse_trailing_fields(trailing)
            current = Task(
                id=task_id,
                title=title,
                priority=int(priority),
                status=status,
                by=by,
                deps=deps,
                phase=phase,
                req=req,
            )
            tasks.append(current)
            last_note_key = ""
            continue

        note_match = NOTE_LINE.match(line)
        if note_match and current is not None:
            key, value = note_match.groups()
            current.notes[key] = value
            last_note_key = key
            continue

        cont_match = CONTINUATION_LINE.match(line)
        if cont_match and current is not None and last_note_key:
            extra = cont_match.group(1)
            current.notes[last_note_key] = f"{current.notes[last_note_key]}\n{extra}"

    return tasks


def serialize_backlog(tasks: list[Task]) -> str:
    """Serialize tasks to backlog markdown (task lines + optional notes)."""
    lines: list[str] = []
    for task in tasks:
        checkbox = "x" if task.status == "done" else " "
        parts = [
            f"- [{checkbox}] {task.id}: {task.title}",
            f"priority: {task.priority}",
            f"status: {task.status}",
            f"by: {task.by}",
        ]
        if task.deps:
            parts.append(f"deps: {','.join(task.deps)}")
        if task.phase:
            parts.append(f"phase: {task.phase}")
        if task.req:
            parts.append(f"req: {task.req}")
        lines.append(" | ".join(parts))
        for key in ("rationale", "details", "diagnosis"):
            if key in task.notes:
                lines.append(f"  {key}: {task.notes[key]}")
    return "\n".join(lines) + ("\n" if lines else "")


def select_next(
    tasks: list[Task],
    autonomy: str = "normal",
    active_phase: str = "",
) -> Task | None:
    """Return the highest-priority selectable task whose dependencies are done.

    Owner-authored tasks outrank kelix-proposed tasks regardless of priority.
    Ready tasks are always candidates. Proposed tasks are candidates only when
    ``autonomy`` is ``"high"`` and rank below owner ready tasks.

    When ``active_phase`` is set, tasks in that phase sort ahead of phaseless
    tasks, which sort ahead of tasks in other phases (within the usual keys).
    """
    done_ids = {task.id for task in tasks if task.status == "done"}

    def candidate(task: Task) -> bool:
        if not all(dep in done_ids for dep in task.deps):
            return False
        if task.status == "ready":
            return True
        if task.status == "proposed" and autonomy == "high":
            return True
        return False

    candidates = [task for task in tasks if candidate(task)]
    if not candidates:
        return None

    def phase_rank(task: Task) -> int:
        if not active_phase:
            return 0
        if task.phase == active_phase:
            return 0
        if not task.phase:
            return 1
        return 2

    def sort_key(task: Task) -> tuple[int, int, int, int]:
        owner_rank = 0 if task.by == "owner" else 1
        status_rank = 0 if task.status == "ready" else 1
        return (owner_rank, status_rank, phase_rank(task), -task.priority)

    return min(candidates, key=sort_key)
